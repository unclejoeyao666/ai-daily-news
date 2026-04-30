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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib.news_db import NewsDB

DB_PATH = ROOT / "data" / "news.db"
SELECTED_JSON = ROOT / "daily-selected.json"
TRANSLATIONS_DIR = ROOT / "translations"

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

    data["_translated_at"] = __import__("datetime").datetime.now().__str__()
    tf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Translation written: {tf}")
    print(f"   Title: {data['translated_title'][:60]}")


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


if __name__ == "__main__":
    main()
