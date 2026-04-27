#!/usr/bin/env python3
"""Select top N unplayed articles for the daily briefing.

Outputs daily-selected.json (intermediate state for Claude curation).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib.news_db import NewsDB

DB_PATH = ROOT / "data" / "news.db"
OUT_PATH = ROOT / "daily-selected.json"


def row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "summary": row["summary"],
        "source_id": row["source_id"],
        "source_name": row["source_name"],
        "source_name_cn": row["source_name_cn"],
        "source_url": row["source_url"],
        "published_at": row["published_at"],
        "lang": row["lang"],
        "source_categories": json.loads(row["source_categories"] or "[]"),
        "importance": row["importance"],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=10)
    p.add_argument("--min-importance", type=int, default=0)
    p.add_argument("--out", default=str(OUT_PATH))
    args = p.parse_args()

    with NewsDB(str(DB_PATH)) as db:
        rows = db.get_unplayed(limit=args.count, min_importance=args.min_importance)
        if not rows:
            print("⚠️  no unplayed articles — run scripts/harvest.py first")
            sys.exit(0)
        selected = [row_to_dict(r) for r in rows]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({
            "selected_at": datetime.now(timezone.utc).isoformat(),
            "count": len(selected),
            "articles": selected,
        }, f, ensure_ascii=False, indent=2)

    print(f"✅ selected {len(selected)} articles → {args.out}")
    for i, a in enumerate(selected, 1):
        label = (a["source_name_cn"] or a["source_name"])[:24]
        print(f"  [{i:2d}] imp={a['importance']:3d} | {label:24s} | {a['title'][:60]}")


if __name__ == "__main__":
    main()
