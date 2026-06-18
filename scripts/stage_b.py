#!/usr/bin/env python3
"""Stage B controller — deterministic gate around the cognitive translate.

This is the ONLY place in the pipeline that invokes a language model, and
it does so only when translation is actually pending. The Stage B / retry /
deep-retry crons run this script as a `command` payload (no agent turn), so:

  * on a healthy day the 04:30 run translates and the 05:15 / 06:00 runs
    gate-skip in milliseconds with ZERO model tokens;
  * the model is reached only via `openclaw agent`, bounded by --timeout,
    so a hung/zero-token model call cannot wedge the cron — it is killed,
    translate stays not-ok, and the next retry (or the 06:25 deterministic
    drop-untranslated fallback) still ships the day.

Exit-code contract (so the cron's failureAlert behaves):
  0  translated ok, OR nothing to do (gate skip)
  1  translation still not ok after a real attempt (retry / alert)

The cognitive work itself (reading articles, writing translated JSON,
writing audio_script.md, calling translate_helper.py finalize) is done by
the fanli agent per references/translation-workflow.md.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib import state as st  # noqa: E402

AGENT_ID = os.environ.get("STAGE_B_AGENT", "fanli")
MODEL = os.environ.get("STAGE_B_MODEL", "deepseek/deepseek-v4-flash")
# openclaw agent's own budget; kept below the cron timeoutSeconds so the
# cron never has to hard-kill a still-running model call.
AGENT_TIMEOUT_SECONDS = int(os.environ.get("STAGE_B_AGENT_TIMEOUT", "1050"))
# Subprocess wall-clock cap (a little above the agent budget).
SUBPROCESS_TIMEOUT_SECONDS = AGENT_TIMEOUT_SECONDS + 90
# Stale-tolerant lock so two near-simultaneous invocations never double-spend
# the model. Longer than one agent budget; a crashed run's lock ages out.
LOCK_TTL_SECONDS = AGENT_TIMEOUT_SECONDS + 250

PROMPT = """执行 ai-news-workflow skill 的 Stage B（认知翻译）。项目根: /Users/unclejoe/Media_Workspace/ai-daily-news

只翻译尚未翻译的文章，不重复劳动：
1. cd /Users/unclejoe/Media_Workspace/ai-daily-news
2. 查待翻 ID: python3 scripts/translate_helper.py pending --date today
   - 若 0 条 pending 且已 finalize → 无需操作。
3. 阅读 references/translation-workflow.md 的全部规则。
4. 对每个 pending ID：翻译 5 个字段（translated_title / translated_summary /
   translated_body / impact_analysis / 1-3 个来自 data/tags.json 的合法 industry_tags），
   写入 /tmp/article-<ID>.json，调用:
   python3 scripts/translate_helper.py write --id <ID> --json-file /tmp/article-<ID>.json
5. 写 daily/<Y>/<Y-M>/<DATE>/audio_script.md（1500-2500 中文字符，TTS 安全）。
6. 关闭本阶段: python3 scripts/translate_helper.py finalize --date today

硬规则：绝不直接改 news_articles 的翻译字段（只用 translate_helper write）；绝不手写 state.translate=ok；
绝不编造 tag slug；中途失败已写入的翻译会保留，后续只处理剩余 pending。
最后仅回复字面量 NO_REPLY。"""


def berlin_today() -> str:
    return datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")


def parse_date(value: str) -> str:
    if not value or value == "today":
        return berlin_today()
    return value


def day_dir_for(date_str: str) -> Path:
    year, month, _ = date_str.split("-")
    return ROOT / "daily" / year / f"{year}-{month}" / date_str


def state_path_for(date_str: str) -> Path:
    return day_dir_for(date_str) / ".state.json"


def openclaw_bin() -> str:
    return (
        os.environ.get("OPENCLAW_BIN")
        or shutil.which("openclaw")
        or "/opt/homebrew/bin/openclaw"
    )


def translate_is_ok(date_str: str) -> bool:
    state = st.load(state_path_for(date_str), date_str)
    return st.is_done(state, "translate")


def select_is_ok(date_str: str) -> bool:
    state = st.load(state_path_for(date_str), date_str)
    return st.is_done(state, "select")


def acquire_lock(date_str: str) -> Path | None:
    """Return the lock path if acquired, or None if a fresh lock is held."""
    dd = day_dir_for(date_str)
    dd.mkdir(parents=True, exist_ok=True)
    lock = dd / ".stage_b.lock"
    if lock.exists():
        age = time.time() - lock.stat().st_mtime
        if age < LOCK_TTL_SECONDS:
            return None
        # stale: a previous run crashed without releasing — reclaim it.
    lock.write_text(f"{os.getpid()} {datetime.now(timezone.utc).isoformat()}\n",
                    encoding="utf-8")
    return lock


def invoke_translate_agent(date_str: str) -> dict:
    """Run one cognitive translate turn via `openclaw agent`.

    Uses a fresh per-run session key so the model starts from a small,
    clean context (it re-derives the pending set itself) — no carried-over
    history, which keeps token cost down.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    session_key = f"cron:ai-news-stage-b:{date_str}:{stamp}"
    cmd = [
        openclaw_bin(), "agent",
        "--agent", AGENT_ID,
        "--session-key", session_key,
        "--message", PROMPT,
        "--model", MODEL,
        "--timeout", str(AGENT_TIMEOUT_SECONDS),
        "--json",
    ]
    print(f"🤖 invoking translate agent (session={session_key}, model={MODEL}, "
          f"timeout={AGENT_TIMEOUT_SECONDS}s)")
    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=SUBPROCESS_TIMEOUT_SECONDS)
        elapsed = time.time() - start
        if proc.stdout.strip():
            print(proc.stdout.strip()[:1000])
        if proc.returncode != 0 and proc.stderr.strip():
            print(proc.stderr.strip()[:500], file=sys.stderr)
        return {"rc": proc.returncode, "elapsed": elapsed}
    except subprocess.TimeoutExpired:
        return {"rc": -1, "elapsed": time.time() - start, "timeout": True}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default="today")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report the gate decision without invoking the model")
    args = ap.parse_args()
    date_str = parse_date(args.date)

    # ── Deterministic gate — no model tokens spent here ──────────────
    if not select_is_ok(date_str):
        print(json.dumps({"stage": "B", "date": date_str, "action": "skip",
                          "reason": "select not ok (Stage A not done)"}))
        return 0
    if translate_is_ok(date_str):
        print(json.dumps({"stage": "B", "date": date_str, "action": "skip",
                          "reason": "translate already ok"}))
        return 0

    if args.dry_run:
        print(json.dumps({"stage": "B", "date": date_str, "action": "would-invoke",
                          "reason": "translation pending"}))
        return 0

    lock = acquire_lock(date_str)
    if lock is None:
        print(json.dumps({"stage": "B", "date": date_str, "action": "skip",
                          "reason": "another Stage B run in flight (lock held)"}))
        return 0

    try:
        result = invoke_translate_agent(date_str)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass

    # Single source of truth: did translate reach ok? (set only by
    # translate_helper.finalize after the verifier passed.)
    ok = translate_is_ok(date_str)
    out = {"stage": "B", "date": date_str,
           "action": "translated" if ok else "incomplete",
           "agent_rc": result.get("rc"),
           "elapsed_s": round(result.get("elapsed", 0)),
           "translate_ok": ok}
    print(json.dumps(out, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
