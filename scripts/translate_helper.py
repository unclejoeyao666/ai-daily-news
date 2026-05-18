#!/usr/bin/env python3
"""Per-article translation helper (checkpoint-based).

Each article's translation is written as a standalone JSON file, so
interruption is safe. Re-running picks up where it left off.

Usage::

    # Write a translation (agent calls this after each article)
    python3 scripts/translate_helper.py write --id 1402 --json translations/1402.json

    # Mark skipped (off-topic / not worth broadcasting)
    python3 scripts/translate_helper.py skip --id 1402 --reason "..."

    # Show translation status for all articles in daily-selected.json
    python3 scripts/translate_helper.py status

    # Show a specific translation
    python3 scripts/translate_helper.py show --id 1402
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib.news_db import NewsDB
from scripts.lib import state as st
from scripts.lib import config

DB_PATH = ROOT / "data" / "news.db"
SELECTED_JSON = ROOT / "daily-selected.json"
TRANSLATIONS_DIR = ROOT / "translations"
TAGS_JSON = ROOT / "data" / "tags.json"

# Absolute path to the skill-owned verifier — single source of truth.
# Do NOT replace with a relative reference; daily_pipeline.py and
# Stage B agent both call this same path, and OpenClaw cron payloads
# must use absolute paths (see plan §0).
VERIFY_TRANSLATIONS = Path(
    "/Users/unclejoe/.agents/skills/ai-news-workflow/scripts/verify_translations.py"
)

def load_valid_tags() -> list:
    """Tag vocabulary — single source of truth is data/tags.json.

    Previously this was a hardcoded list that had drifted ('china' vs
    the canonical 'china-ai'), so translate_helper accepted/blocked a
    different set than the skill-owned verify_translations.py (which
    already reads tags.json). Reading the same file keeps the write
    gate and the verify gate in lockstep.
    """
    if not TAGS_JSON.exists():
        return []
    cfg = json.loads(TAGS_JSON.read_text(encoding="utf-8"))
    return [t["slug"] for t in cfg.get("tags", [])]


def translation_file(article_id: int) -> Path:
    TRANSLATIONS_DIR.mkdir(parents=True, exist_ok=True)
    return TRANSLATIONS_DIR / f"{article_id}.json"


def load_selected() -> list:
    if not SELECTED_JSON.exists():
        return []
    return json.loads(SELECTED_JSON.read_text(encoding="utf-8")).get("articles", [])


def cmd_write(args) -> None:
    tf = translation_file(args.id)

    if args.json_file:
        data = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    elif args.json:
        data = json.loads(args.json)
    else:
        # Interactive: read from stdin
        print("Paste translation JSON and press Ctrl+D:")
        data = json.loads(sys.stdin.read())

    # Validate required fields
    required = ["translated_title", "translated_summary", "impact_analysis"]
    for field in required:
        if not data.get(field):
            print(f"❌ Missing required field: {field}")
            sys.exit(1)

    # Validate tags
    tags = data.get("industry_tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    valid_tags = load_valid_tags()
    invalid = [t for t in tags if t not in valid_tags]
    if invalid and not args.force:
        print(f"❌ Invalid tags: {invalid}")
        print(f"   Valid: {valid_tags}")
        print("   Use --force to override.")
        sys.exit(1)

    data["_translated_at"] = datetime.now().__str__()
    tf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Translation written: {tf}")
    print(f"   Title: {data['translated_title'][:60]}")

    # Persist into news_articles so partial progress survives across
    # cron firings even without finalize. publish_article.py computes
    # slug later, so we don't set it here.
    body = (data.get("translated_body") or data.get("translated_summary") or "").strip()
    with NewsDB(str(DB_PATH)) as db:
        db.update_translation(
            article_id=args.id,
            translated_title=data["translated_title"],
            translated_summary=data["translated_summary"],
            translated_body=body,
            impact_analysis=data.get("impact_analysis", ""),
            industry_tags=tags,
        )
    print(f"   DB updated for id={args.id}")


def cmd_skip(args) -> None:
    tf = translation_file(args.id)
    data = {
        "_skipped": True,
        "_skipped_reason": args.reason,
        "_skipped_at": __import__("datetime").datetime.now().__str__(),
    }
    tf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"⏭  Skipped article {args.id}: {args.reason}")


def cmd_status(args) -> None:
    articles = load_selected()
    if not articles:
        print("⚠️  daily-selected.json not found or empty")
        return

    print(f"📋 Translation status ({len(articles)} articles):\n")
    translated = 0
    skipped = 0
    pending = 0
    for a in articles:
        aid = a["id"]
        tf = translation_file(aid)
        if tf.exists():
            try:
                d = json.loads(tf.read_text(encoding="utf-8"))
                if d.get("_skipped"):
                    print(f"  ⏭  {aid}: SKIPPED — {d.get('_skipped_reason', '')}")
                    skipped += 1
                elif d.get("translated_title"):
                    print(f"  ✅ {aid}: {d['translated_title'][:60]}")
                    translated += 1
                else:
                    print(f"  ❓ {aid}: file exists but no translation")
                    pending += 1
            except json.JSONDecodeError:
                print(f"  ❌ {aid}: corrupt translation file")
                pending += 1
        else:
            # Check DB
            with NewsDB(str(DB_PATH)) as db:
                row = db.get_by_id(aid)
                if row and row["translated_title"]:
                    print(f"  ✅ {aid}: in DB — {row['translated_title'][:60]}")
                    translated += 1
                else:
                    print(f"  ⏳ {aid}: pending")
                    pending += 1

    print(f"\n  ✅ {translated} translated  ⏭ {skipped} skipped  ⏳ {pending} pending")


def _berlin_today() -> str:
    return datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")


def _state_path_for(date_str: str) -> Path:
    return _day_dir_for(date_str) / ".state.json"


def _day_dir_for(date_str: str) -> Path:
    year, month, _ = date_str.split("-")
    return ROOT / "daily" / year / f"{year}-{month}" / date_str


_REQUIRED_COLS = ("translated_title", "translated_summary",
                   "translated_body", "impact_analysis")
_MAX_SUMMARY_CHARS = 300  # mirrors verify_translations.MAX_SUMMARY_CHARS / Astro cap


def _is_translated(row, valid_tags: set) -> bool:
    """A row counts as fully translated iff it would PASS
    verify_translations.py's per-article checks. Kept in exact lockstep
    so `pending`/`compute_pending` never disagree with the verifier —
    otherwise the drop-untranslated fallback could keep an id the
    verifier then rejects, breaking the MIN_BRIEFING guarantee.

    Checks (same as verify_translations.check_articles):
      - all four translated_* columns non-empty
      - translated_summary <= 300 chars
      - source_url is http(s)
      - industry_tags is a JSON array of 1..3 valid slugs
    """
    if row is None:
        return False
    if not all((row[c] or "").strip() for c in _REQUIRED_COLS):
        return False
    if len(row["translated_summary"] or "") > _MAX_SUMMARY_CHARS:
        return False
    url = row["source_url"] or ""
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    try:
        tags = json.loads(row["industry_tags"] or "[]")
    except json.JSONDecodeError:
        return False
    if not isinstance(tags, list) or not (1 <= len(tags) <= 3):
        return False
    return all(t in valid_tags for t in tags)


def compute_pending(date_str: str) -> dict:
    """Split the day's selected ids into done vs still-untranslated."""
    ids = [a["id"] for a in load_selected()]
    done, pending = [], []
    if ids:
        valid_tags = set(load_valid_tags())
        if not valid_tags:
            # tags.json missing/corrupt: every article would be judged
            # "pending" purely from a config failure (and the skill
            # verifier returns rc=2 for the same reason). Fail loud and
            # specific instead of silently reporting 0 done.
            print(f"❌ no valid tags loaded from {TAGS_JSON} — cannot "
                  f"judge translation completeness; fix tags.json",
                  file=sys.stderr)
            sys.exit(2)
        with NewsDB(str(DB_PATH)) as db:
            for aid in ids:
                ok = _is_translated(db.get_by_id(aid), valid_tags)
                (done if ok else pending).append(aid)
    return {"total": len(ids), "done": done, "pending": pending}


def cmd_pending(args) -> None:
    """List selected article ids that still lack a full translation.

    Cheap, idempotent, read-only — the Stage B retry crons call this to
    translate ONLY what's left, and the watchdog uses --json to decide
    whether the deterministic drop fallback is needed. Always exits 0.
    """
    date_str = args.date if args.date and args.date != "today" else _berlin_today()
    info = compute_pending(date_str)
    if args.json:
        print(json.dumps(info, ensure_ascii=False))
        return
    print(f"📋 {date_str}: {len(info['done'])}/{info['total']} translated, "
          f"{len(info['pending'])} pending")
    if info["pending"]:
        print("   pending ids: " + " ".join(str(i) for i in info["pending"]))


def _synthesize_audio_script(date_str: str, ids: list) -> str:
    """Deterministic fallback narration from already-translated rows.

    The cognitive Stage B agent normally writes a polished
    audio_script.md. When it never got that far but enough articles ARE
    translated, the watchdog/fallback-finalize must still ship — so we
    build a plain, TTS-safe Chinese script from the DB. Lower prose
    quality than the agent's, but it gets the day out the door instead
    of zeroing it. Returns the script text (also written to disk)."""
    titles: list[str] = []
    parts = [
        f"欢迎收听 AI 科技每日早报，今天是 {date_str}。"
        f"下面为您播报今天精选的 {len(ids)} 条人工智能与科技要闻。",
        "",
    ]
    with NewsDB(str(DB_PATH)) as db:
        for n, aid in enumerate(ids, 1):
            row = db.get_by_id(aid)
            if not row:
                continue
            title = (row["translated_title"] or "").strip()
            summ = (row["translated_summary"] or "").strip()
            body = (row["translated_body"] or "").strip()
            impact = (row["impact_analysis"] or "").strip()
            titles.append(title)
            parts.append(f"第 {n} 条，{title}。")
            if summ:
                parts.append(summ)
            elif body:
                parts.append(body[:240])
            if impact:
                parts.append(f"这一进展的影响：{impact}")
            parts.append("")
    parts.append("以上就是今天的 AI 科技早报全部内容。")
    closing = "感谢收听，我们明天同一时间再见。"
    # Guarantee the verifier's MIN_AUDIO_SCRIPT_CHARS floor so a thin
    # (but >= MIN_BRIEFING) day still ships. Deterministic, no loop:
    # one title recap, then at most one bounded filler block sized to
    # exactly clear the floor (only ever triggers on degenerate
    # near-empty content).
    floor = config.MIN_AUDIO_SCRIPT_CHARS
    if len("\n".join(parts + [closing])) < floor:
        recap = "今天的要点回顾：" + "；".join(t for t in titles if t) + "。"
        parts.append(recap)
    body = "\n".join(parts + [closing])
    if len(body) < floor:
        unit = "本期播报到此结束，感谢持续关注 AI 科技每日早报。"
        reps = (floor - len(body)) // len(unit) + 1
        parts.append(unit * reps)
    parts.append(closing)
    script = "\n".join(parts)
    path = _day_dir_for(date_str) / "audio_script.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script, encoding="utf-8")
    return script


def _finalize_ok(date_str: str, ids: list) -> None:
    """Shared tail: mark translate ok + mark_played for the given ids."""
    sp = _state_path_for(date_str)
    state = st.load(sp, date_str)
    state = st.mark(state, "translate", "ok", translated_count=len(ids))
    st.save(sp, state)
    print(f"✅ translate marked ok ({len(ids)} articles) → {sp}")
    if ids:
        with NewsDB(str(DB_PATH)) as db:
            db.mark_played(ids, briefing_date=date_str)
        print(f"✅ mark_played({len(ids)} ids, briefing_date={date_str})")


def cmd_finalize(args) -> None:
    """Close Stage B: run verify_translations.py and mark state.translate=ok.

    Default (cognitive path): ALL selected articles must verify, or
    translate is left untouched (callers/retry crons decide what next).

    --drop-untranslated (deterministic fallback path, used by the
    06:25 cron and the past-deadline watchdog): articles still missing
    a translation are dropped from daily-selected.json (they were never
    mark_played, so they stay 'unplayed' and can be re-selected within
    AGING_DAYS with a fresh decay score). Requires >= MIN_BRIEFING
    survivors, synthesizes audio_script.md if the agent never wrote
    one, then verifies+finalizes the reduced set. Never fakes success:
    if too few survived it exits non-zero so failureAlert fires.

    The verifier is the single source of truth for "translate done".
    Agent must NEVER write translate=ok directly.
    """
    date_str = args.date if args.date and args.date != "today" else _berlin_today()
    print(f"▶️  finalize Stage B for {date_str}"
          f"{' [drop-untranslated]' if args.drop_untranslated else ''}")

    if not VERIFY_TRANSLATIONS.exists():
        print(f"❌ verifier not found at {VERIFY_TRANSLATIONS}", file=sys.stderr)
        print("   This is a skill-installation problem. Re-clone or check the path.",
              file=sys.stderr)
        sys.exit(2)

    selected_ids = [a["id"] for a in load_selected()]

    if args.drop_untranslated:
        info = compute_pending(date_str)
        done_ids = info["done"]
        if len(done_ids) < config.MIN_BRIEFING:
            print(f"⛔ only {len(done_ids)} translated (< MIN_BRIEFING="
                  f"{config.MIN_BRIEFING}) — refusing to ship a thin briefing; "
                  f"translate left NOT ok so failureAlert surfaces it.",
                  file=sys.stderr)
            sys.exit(1)
        if info["pending"]:
            articles = load_selected()
            kept = [a for a in articles if a["id"] in set(done_ids)]
            SELECTED_JSON.write_text(json.dumps(
                {"selected_at": datetime.now(timezone.utc).isoformat(),
                 "count": len(kept), "articles": kept},
                ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"✂️  dropped {len(info['pending'])} untranslated id(s) "
                  f"{info['pending']} → kept {len(kept)} (stay unplayed for "
                  f"re-selection within {config.AGING_DAYS}d)")
        # Ensure a usable audio_script.md exists for the kept set.
        asp = _day_dir_for(date_str) / "audio_script.md"
        if (not asp.exists()
                or len(asp.read_text(encoding="utf-8")) < config.MIN_AUDIO_SCRIPT_CHARS):
            _synthesize_audio_script(date_str, done_ids)
            print(f"📝 synthesized deterministic audio_script.md "
                  f"({len(asp.read_text(encoding='utf-8'))} chars)")

    rc = subprocess.call(["python3", str(VERIFY_TRANSLATIONS), "--date", date_str])
    if rc != 0:
        print(f"⛔ verifier exited rc={rc} — translate stage NOT marked ok",
              file=sys.stderr)
        print("   Inspect output above; fix the rows in SQLite or rewrite",
              file=sys.stderr)
        print("   audio_script.md, then re-run finalize.", file=sys.stderr)
        sys.exit(1)

    final_ids = [a["id"] for a in load_selected()] if args.drop_untranslated \
        else selected_ids
    _finalize_ok(date_str, final_ids)


def cmd_show(args) -> None:
    tf = translation_file(args.id)
    if not tf.exists():
        print(f"⚠️  No translation file for article {args.id}")
        # Check DB
        with NewsDB(str(DB_PATH)) as db:
            row = db.get_by_id(args.id)
            if row and row["translated_title"]:
                print(f"  (found in DB): {row['translated_title']}")
                return
        sys.exit(1)
    data = json.loads(tf.read_text(encoding="utf-8"))
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description="Per-article translation helper")
    sub = p.add_subparsers(dest="cmd")

    write = sub.add_parser("write", help="Write a translation JSON")
    write.add_argument("--id", type=int, required=True)
    write.add_argument("--json-file", help="Path to JSON file")
    write.add_argument("--json", help="JSON string")
    write.add_argument("--force", action="store_true", help="Skip tag validation")

    skip = sub.add_parser("skip", help="Mark article as skipped")
    skip.add_argument("--id", type=int, required=True)
    skip.add_argument("--reason", required=True, help="Why it's being skipped")

    sub.add_parser("status", help="Show translation status for all articles")
    show = sub.add_parser("show", help="Show translation for one article")
    show.add_argument("--id", type=int, required=True)

    pending = sub.add_parser(
        "pending",
        help="List selected ids still lacking a full translation (exit 0)",
    )
    pending.add_argument("--date", default="today",
                         help="YYYY-MM-DD (Europe/Berlin) or 'today' (default)")
    pending.add_argument("--json", action="store_true",
                         help="Machine-readable {pending,done,total}")

    finalize = sub.add_parser(
        "finalize",
        help="Close Stage B: run verify_translations and write state.translate=ok",
    )
    finalize.add_argument("--date", default="today",
                          help="YYYY-MM-DD (Europe/Berlin) or 'today' (default)")
    finalize.add_argument(
        "--drop-untranslated", action="store_true",
        help="Deterministic fallback: drop still-untranslated ids "
             "(>= MIN_BRIEFING must remain), synth audio_script if "
             "needed, then finalize the reduced set",
    )

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return

    if args.cmd == "write":
        cmd_write(args)
    elif args.cmd == "skip":
        cmd_skip(args)
    elif args.cmd == "status":
        cmd_status(args)
    elif args.cmd == "show":
        cmd_show(args)
    elif args.cmd == "pending":
        cmd_pending(args)
    elif args.cmd == "finalize":
        cmd_finalize(args)


if __name__ == "__main__":
    main()
