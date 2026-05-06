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

DB_PATH = ROOT / "data" / "news.db"
SELECTED_JSON = ROOT / "daily-selected.json"
TRANSLATIONS_DIR = ROOT / "translations"

# Absolute path to the skill-owned verifier — single source of truth.
# Do NOT replace with a relative reference; daily_pipeline.py and
# Stage B agent both call this same path, and OpenClaw cron payloads
# must use absolute paths (see plan §0).
VERIFY_TRANSLATIONS = Path(
    "/Users/unclejoe/.agents/skills/ai-news-workflow/scripts/verify_translations.py"
)

VALID_TAGS = [
    "model-release", "research-paper", "enterprise-app", "consumer-app",
    "agent-tools", "safety-alignment", "policy-regulation", "industry-trend",
    "funding-ipo", "chips-infra", "open-source", "china",
]


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
        data = json.parse(sys.stdin.read())

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
    invalid = [t for t in tags if t not in VALID_TAGS]
    if invalid and not args.force:
        print(f"❌ Invalid tags: {invalid}")
        print(f"   Valid: {VALID_TAGS}")
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
    year, month, _ = date_str.split("-")
    return ROOT / "daily" / year / f"{year}-{month}" / date_str / ".state.json"


def cmd_finalize(args) -> None:
    """Close Stage B: run verify_translations.py and mark state.translate=ok.

    Contract (see plan §0.1, §2.4 A):
      - rc=0 + state.steps.translate=ok when all 10 articles pass verification
      - rc=1 + state.steps.translate untouched (caller decides retry) when
        any article is missing a required field

    The verifier is the single source of truth for "translate done".
    Agent must NEVER write translate=ok directly.
    """
    date_str = args.date if args.date and args.date != "today" else _berlin_today()
    print(f"▶️  finalize Stage B for {date_str}")

    if not VERIFY_TRANSLATIONS.exists():
        print(f"❌ verifier not found at {VERIFY_TRANSLATIONS}", file=sys.stderr)
        print("   This is a skill-installation problem. Re-clone or check the path.",
              file=sys.stderr)
        sys.exit(2)

    rc = subprocess.call(["python3", str(VERIFY_TRANSLATIONS), "--date", date_str])
    if rc != 0:
        print(f"⛔ verifier exited rc={rc} — translate stage NOT marked ok",
              file=sys.stderr)
        print("   Inspect output above; fix the rows in SQLite or rewrite",
              file=sys.stderr)
        print("   audio_script.md, then re-run finalize.", file=sys.stderr)
        sys.exit(1)

    sp = _state_path_for(date_str)
    state = st.load(sp, date_str)
    selected = load_selected()
    ids = [a["id"] for a in selected]
    state = st.mark(state, "translate", "ok", translated_count=len(ids))
    st.save(sp, state)
    print(f"✅ translate marked ok ({len(ids)} articles) → {sp}")

    # Mark articles as played so they don't re-appear in select tomorrow.
    if ids:
        with NewsDB(str(DB_PATH)) as db:
            db.mark_played(ids, briefing_date=date_str)
        print(f"✅ mark_played({len(ids)} ids, briefing_date={date_str})")


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

    finalize = sub.add_parser(
        "finalize",
        help="Close Stage B: run verify_translations and write state.translate=ok",
    )
    finalize.add_argument("--date", default="today",
                          help="YYYY-MM-DD (Europe/Berlin) or 'today' (default)")

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
    elif args.cmd == "finalize":
        cmd_finalize(args)


if __name__ == "__main__":
    main()
