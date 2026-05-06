#!/usr/bin/env python3
"""Select top N unplayed articles for the daily briefing.

Outputs daily-selected.json (intermediate state for Claude curation).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib.news_db import NewsDB

DB_PATH = ROOT / "data" / "news.db"
OUT_PATH = ROOT / "daily-selected.json"

DEFAULT_MAX_AGE_DAYS = 7  # 不再选 7 天前的旧文章 — 防止 importance 高的老文反复占名额


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
    p.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS,
                   help=f"Reject articles older than N days (default {DEFAULT_MAX_AGE_DAYS})")
    p.add_argument("--out", default=str(OUT_PATH))
    args = p.parse_args()

    cutoff = (datetime.now(timezone(timedelta(hours=2)))
              - timedelta(days=args.max_age_days)).strftime("%Y-%m-%d")

    with NewsDB(str(DB_PATH)) as db:
        # Filter by published_at (fall back to discovered_at when NULL)
        # — see news_db.get_unplayed docstring for the bug history.
        rows = db.get_unplayed(
            limit=args.count,
            min_importance=args.min_importance,
            published_after=cutoff,
        )
        if not rows:
            print(f"⚠️  no unplayed articles since {cutoff} — run scripts/harvest.py first")
            sys.exit(0)
        if len(rows) < args.count:
            print(f"⚠️  only {len(rows)}/{args.count} unplayed articles since {cutoff}")
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
