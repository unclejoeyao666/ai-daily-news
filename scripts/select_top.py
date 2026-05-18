#!/usr/bin/env python3
"""Select top N unplayed articles for the daily briefing.

Selection is freshness-first: a recency-ordered candidate pool is
pulled from SQL, then each article gets a time-decay score
``importance * 0.5 ** (age_hours / HALFLIFE_HOURS)`` computed in
Python and the top ``--count`` by score win. A genuinely important
older story can still rank via high importance, but it can no longer
permanently crowd out fresh news (the 2026-05 "播 6 天前旧闻"
regression). Stale unplayed backlog is archived before selection so a
failed day cannot poison later days.

Outputs daily-selected.json (intermediate state for Stage B curation).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib.news_db import NewsDB
from scripts.lib import config

DB_PATH = ROOT / "data" / "news.db"
OUT_PATH = ROOT / "daily-selected.json"

DEFAULT_MAX_AGE_DAYS = config.DEFAULT_MAX_AGE_DAYS


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


def parse_dt(value: str | None) -> datetime | None:
    """Best-effort parse of the timestamp formats found in news.db.

    Handles 'YYYY-MM-DD', 'YYYY-MM-DDTHH:MM:SS[+00:00|Z]' and
    'YYYY-MM-DD HH:MM:SS' (sqlite datetime('now'), naive → assume UTC).
    Returns an aware UTC datetime, or None if unparseable.
    """
    if not value:
        return None
    s = value.strip().replace("Z", "+00:00").replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def decay_score(importance: int, ts: str | None, now: datetime) -> float:
    """importance * 0.5 ** (age_hours / HALFLIFE_HOURS).

    Unparseable / future / missing timestamps are treated as very old
    (score ≈ 0) so they sink rather than spuriously top the list.
    """
    dt = parse_dt(ts)
    if dt is None:
        return 0.0
    age_hours = max(0.0, (now - dt).total_seconds() / 3600.0)
    return importance * math.pow(0.5, age_hours / config.HALFLIFE_HOURS)


def write_selection(out_path: str, selected: list) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "selected_at": datetime.now(timezone.utc).isoformat(),
            "count": len(selected),
            "articles": selected,
        }, f, ensure_ascii=False, indent=2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=10)
    p.add_argument("--min-importance", type=int, default=0)
    p.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS,
                   help=f"Reject articles older than N days (default {DEFAULT_MAX_AGE_DAYS})")
    p.add_argument("--aging-days", type=int, default=config.AGING_DAYS,
                   help=f"Archive unplayed older than N days (default {config.AGING_DAYS})")
    p.add_argument("--out", default=str(OUT_PATH))
    args = p.parse_args()

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=args.max_age_days)).strftime("%Y-%m-%d")
    aging_cutoff = (now - timedelta(days=args.aging_days)).strftime("%Y-%m-%d")

    with NewsDB(str(DB_PATH)) as db:
        # 1. Aging: archive stale unplayed BEFORE selecting so a failed
        #    day's backlog can never be picked again.
        archived = db.archive_stale_unplayed(aging_cutoff)
        if archived:
            print(f"🗄  archived {archived} unplayed article(s) older than {aging_cutoff}")

        # 2. Recency-ordered candidate pool (see news_db.get_unplayed).
        rows = db.get_unplayed(
            limit=config.SELECT_POOL,
            min_importance=args.min_importance,
            published_after=cutoff,
        )
        # 3. Time-decay score, highest first; flexible count.
        scored = sorted(
            rows,
            key=lambda r: decay_score(r["importance"], r["published_at"] or r["discovered_at"], now),
            reverse=True,
        )
        chosen = scored[:args.count]
        selected = [row_to_dict(r) for r in chosen]

    # 4. Always write the file (even 0 articles) so step_select has a
    #    coherent artifact — the old "0 rows → no file → step marked
    #    failed" inconsistency is fixed here.
    write_selection(args.out, selected)

    if not selected:
        print(f"⚠️  NO-NEWS DAY: 0 unplayed articles since {cutoff} "
              f"(min-importance={args.min_importance}). Wrote empty "
              f"{args.out}; downstream verify will surface this via "
              f"failureAlert. Run scripts/harvest.py if unexpected.")
        return
    if len(selected) < args.count:
        print(f"⚠️  only {len(selected)}/{args.count} fresh articles "
              f"(MIN_BRIEFING={config.MIN_BRIEFING}) — degraded but shipping")

    print(f"✅ selected {len(selected)} articles → {args.out}")
    for i, (r, a) in enumerate(zip(chosen, selected), 1):
        sc = decay_score(r["importance"], r["published_at"] or r["discovered_at"], now)
        label = (a["source_name_cn"] or a["source_name"])[:24]
        print(f"  [{i:2d}] imp={a['importance']:3d} score={sc:6.1f} | "
              f"{label:24s} | {a['title'][:54]}")


if __name__ == "__main__":
    main()
