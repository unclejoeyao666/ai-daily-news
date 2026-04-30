#!/usr/bin/env python3
"""End-to-end orchestrator for AI Daily News pipeline.

Each step is idempotent — safe to re-run after interruption.
State lives in ``daily/<date>/.state.json`` (atomic writes).
Resume-first: always check state before starting.

Usage::

    python3 scripts/daily_pipeline.py --date today              # auto pace
    python3 scripts/daily_pipeline.py --date today --status  # inspect
    python3 scripts/daily_pipeline.py --date today --step harvest
    python3 scripts/daily_pipeline.py --date today --from select --to push
    python3 scripts/daily_pipeline.py --date today --resume    # pick up

The 7 steps in order::

    1. harvest         → scripts/harvest.py
    2. select          → scripts/select_top.py
    3. translate       → scripts/translate_batch.py
    4. publish_article → scripts/publish_article.py
    5. publish_brief   → scripts/publish_briefing.py
    6. audio           → scripts/render_audio.py
    7. push            → scripts/git_publish.py

Recommended cron split::

    04:00 UTC  harvest                          300 s
    04:30 UTC  select + translate + publish_article   1200 s
    05:00 UTC  publish_brief + audio + push     900 s
    05:30 UTC  notify (separate skill)          120 s
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib import state as st
from scripts.lib.news_db import NewsDB

DB_PATH = ROOT / "data" / "news.db"
SELECTED_JSON = ROOT / "daily-selected.json"
DAILY_ROOT = ROOT / "daily"
SITE_BASE_URL = "https://unclejoeyao666.github.io/ai-daily-news"
MIN_AUDIO_BYTES = 100_000  # 100 KB

# Steps that are part of each cron group
STEP_GROUPS = {
    "harvest": ["harvest"],
    "content": ["select", "translate", "publish_article"],
    "render": ["publish_brief", "audio", "push"],
}


# ── Helpers ──────────────────────────────────────────────────────


def parse_date(s: str) -> str:
    if not s or s == "today":
        return datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")
    return s


def day_dir_for(date_str: str) -> Path:
    year, month, _ = date_str.split("-")
    return DAILY_ROOT / year / f"{year}-{month}" / date_str


def state_path_for(date_str: str) -> Path:
    return day_dir_for(date_str) / ".state.json"


def run(cmd: List[str], check: bool = True,
        timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    kwargs: Dict = dict(
        cwd=ROOT, capture_output=True, text=True,
        check=False,
    )
    if timeout:
        kwargs["timeout"] = timeout
    r = subprocess.run(cmd, **kwargs)
    if r.stdout and r.stdout.strip():
        print(r.stdout.strip())
    if r.stderr and r.stderr.strip():
        print(r.stderr.strip(), file=sys.stderr)
    if check and r.returncode != 0:
        raise SystemExit(r.returncode)
    return r


# ── Step implementations ────────────────────────────────────────


def step_harvest(date_str: str, state: Dict) -> Dict:
    print("→ harvest")
    r = run(["python3", "scripts/harvest.py"])
    print(r.stdout.strip() if r.stdout else "")
    with NewsDB(str(DB_PATH)) as db:
        s = db.stats()
    return st.mark(state, "harvest", "ok",
                   stats={"unplayed": s["unplayed"],
                          "total": s["total_articles"]})


def step_select(date_str: str, state: Dict) -> Dict:
    print("→ select")
    r = run([
        "python3", "scripts/select_top.py",
        "--count", "10",
        "--min-importance", "3",
    ])
    print(r.stdout.strip() if r.stdout else "")
    if not SELECTED_JSON.exists():
        return st.mark(state, "select", "failed",
                       error="daily-selected.json not produced")
    sel = json.loads(SELECTED_JSON.read_text(encoding="utf-8"))
    return st.mark(state, "select", "ok",
                   selected_count=len(sel.get("articles", [])))


def step_translate(date_str: str, state: Dict) -> Dict:
    """Run translate_batch.py to generate audio_script.md + briefing.md.

    translate_batch.py reads daily-selected.json, translates articles,
    writes audio_script.md and briefing.md, and updates DB.
    """
    print("→ translate")
    dd = day_dir_for(date_str)
    # translate_batch writes output to the day directory
    r = run([
        "python3", "scripts/translate_batch.py",
        "--date", date_str,
    ])
    print(r.stdout.strip() if r.stdout else "")

    # Verify outputs
    audio_script = dd / "audio_script.md"
    briefing = dd / "briefing.md"
    errors = []
    if not audio_script.exists():
        errors.append(f"audio_script.md missing at {dd}")
    if not briefing.exists():
        errors.append(f"briefing.md missing at {dd}")

    if errors:
        return st.mark(state, "translate", "failed", error="; ".join(errors))

    # Mark articles as played
    sel = json.loads(SELECTED_JSON.read_text(encoding="utf-8"))
    ids = [a["id"] for a in sel.get("articles", [])]
    if ids:
        with NewsDB(str(DB_PATH)) as db:
            db.mark_played(ids, briefing_date=date_str)

    return st.mark(state, "translate", "ok",
                   translated_count=len(ids))


def step_publish_article(date_str: str, state: Dict) -> Dict:
    print("→ publish_article")
    r = run(["python3", "scripts/publish_article.py",
             "--all-pending"])
    print(r.stdout.strip() if r.stdout else "")
    return st.mark(state, "publish_article", "ok")


def step_publish_brief(date_str: str, state: Dict) -> Dict:
    print("→ publish_brief")
    audio_url = f"{SITE_BASE_URL}/audio/{date_str}.mp3"
    r = run([
        "python3", "scripts/publish_briefing.py",
        "--date", date_str,
        "--site-url", SITE_BASE_URL,
    ])
    print(r.stdout.strip() if r.stdout else "")
    dd = day_dir_for(date_str)
    site_brief = ROOT / "site/src/content/briefings" / f"{date_str}.md"
    daily_brief = dd / "briefing.md"
    if not (site_brief.exists() or daily_brief.exists()):
        return st.mark(state, "publish_brief", "failed",
                       error="briefing files not produced")
    return st.mark(state, "publish_brief", "ok")


def step_audio(date_str: str, state: Dict) -> Dict:
    print("→ audio")
    dd = day_dir_for(date_str)
    mp3 = dd / "audio.mp3"
    site_mp3 = ROOT / "site/public/audio" / f"{date_str}.mp3"

    r = run(
        ["python3", "scripts/render_audio.py", "--date", date_str],
        check=False,
    )
    print(r.stdout.strip() if r.stdout else "")

    if r.returncode != 0:
        return st.mark(state, "audio", "failed",
                       error=f"render_audio rc={r.returncode}")

    if not mp3.exists() or mp3.stat().st_size < MIN_AUDIO_BYTES:
        sz = mp3.stat().st_size if mp3.exists() else 0
        return st.mark(state, "audio", "failed",
                       error=f"mp3 missing or too small: {sz} bytes")

    return st.mark(state, "audio", "ok", mp3_size=mp3.stat().st_size)


def step_push(date_str: str, state: Dict) -> Dict:
    print("→ push")
    r = run(
        ["python3", "scripts/git_publish.py", "--date", date_str],
        check=False,
    )
    print(r.stdout.strip() if r.stdout else "")
    if r.returncode != 0:
        return st.mark(state, "push", "failed",
                       error=f"git_publish rc={r.returncode}")
    return st.mark(state, "push", "ok")


STEP_FUNCS = {
    "harvest": step_harvest,
    "select": step_select,
    "translate": step_translate,
    "publish_article": step_publish_article,
    "publish_brief": step_publish_brief,
    "audio": step_audio,
    "push": step_push,
}


# ── Status ───────────────────────────────────────────────────────


def print_status(state: Dict) -> None:
    print(f"📋 Pipeline state for {state.get('date')}")
    all_ok = all(st.is_done(state, s) for s in st.STEPS)
    if all_ok:
        print("  ✅ All steps complete")
    else:
        next_step = st.next_pending(state)
        print(f"  ▶️  Next step: {next_step}")
    print()
    for step in st.STEPS:
        block = st.get(state, step)
        status = block.get("status", "pending")
        marker = {
            "ok": "✅", "pending": "⏳",
            "running": "▶️ ", "failed": "❌", "skipped": "⏭️ ",
        }.get(status, "?")
        extras = []
        for k, v in block.items():
            if k not in ("status", "finished_at", "started_at"):
                extras.append(f"{k}={v}")
        label = st.STEP_LABELS.get(step, step)
        detail = " | ".join(extras) if extras else ""
        print(f"  {marker} [{step}] {label} {detail}")


# ── Main orchestrator ────────────────────────────────────────────


def run_steps(
    date_str: str,
    from_step: Optional[str] = None,
    to_step: Optional[str] = None,
    steps_only: Optional[List[str]] = None,
) -> None:
    """Run pipeline steps from from_step to to_step (inclusive).

    If steps_only is given, only run those named steps.
    Respects already-ok steps (won't re-run).
    """
    sp = state_path_for(date_str)
    state = st.load(sp, date_str)
    # Demote any interrupted steps
    reset = st.reset_running(state)
    if reset:
        print(f"⚠️  Re-running interrupted steps: {reset}")
    st.save(sp, state)

    started = from_step is None
    target_steps = steps_only or st.STEPS

    for step in st.STEPS:
        if step not in target_steps:
            continue
        if not started:
            started = (step == from_step)
            if not started:
                continue

        if st.is_done(state, step):
            print(f"⏭️  [{step}] already ok — skipping")
            continue

        func = STEP_FUNCS.get(step)
        if not func:
            print(f"? Unknown step: {step}")
            continue

        # Mark running
        state = st.mark(state, step, "running")
        st.save(sp, state)

        try:
            state = func(date_str, state)
        except Exception as exc:
            print(f"❌ [{step}] raised {exc}")
            state = st.mark(state, step, "failed", error=str(exc))

        st.save(sp, state)
        print()

        if state["steps"][step].get("status") == "failed":
            print(f"⛔ Step '{step}' failed — stopping pipeline.")
            print(f"   Run with --step {step} to retry after fixing the issue.")
            print(f"   Or run with --resume to try the next pending step.")
            break

        # Stop at to_step
        if to_step and step == to_step:
            print(f"✓ Reached to_step={to_step} — stopping.")
            break


def main() -> None:
    p = argparse.ArgumentParser(
        description="AI Daily News pipeline orchestrator (interrupt-safe)"
    )
    p.add_argument(
        "--date", default="today",
        help="Date string (YYYY-MM-DD or 'today')"
    )
    p.add_argument(
        "--step",
        help="Run only this single step"
    )
    p.add_argument(
        "--from",
        dest="from_step",
        help="Run from this step (inclusive) to the end or --to"
    )
    p.add_argument(
        "--to",
        dest="to_step",
        help="Run up to and including this step"
    )
    p.add_argument(
        "--resume", action="store_true",
        help="Run all pending steps (from next pending to end)"
    )
    p.add_argument(
        "--status", action="store_true",
        help="Print pipeline state and exit"
    )
    args = p.parse_args()

    date_str = parse_date(args.date)
    sp = state_path_for(date_str)

    if args.status:
        state = st.load(sp, date_str)
        print_status(state)
        return

    if args.step:
        run_steps(date_str, steps_only=[args.step])
        return

    from_step = getattr(args, "from_step", None)
    to_step = args.to_step

    if args.resume:
        state = st.load(sp, date_str)
        st.reset_running(state)
        next_step = st.next_pending(state)
        if not next_step:
            print("✅ Pipeline already complete — nothing to resume.")
            state = st.load(sp, date_str)
            print_status(state)
            return
        print(f"▶️  Resuming from: {next_step} ({st.STEP_LABELS.get(next_step, next_step)})")
        run_steps(date_str, from_step=next_step)
        return

    if from_step or to_step:
        run_steps(date_str, from_step=from_step, to_step=to_step)
        return

    # Default: auto pace through all pending steps
    state = st.load(sp, date_str)
    st.reset_running(state)
    next_step = st.next_pending(state)
    if not next_step:
        print("✅ Pipeline already complete.")
        print_status(state)
        return
    print(f"▶️  Starting from: {next_step} ({st.STEP_LABELS.get(next_step, next_step)})")
    run_steps(date_str, from_step=next_step)

    # Final status
    state = st.load(sp, date_str)
    print()
    print_status(state)


if __name__ == "__main__":
    main()
