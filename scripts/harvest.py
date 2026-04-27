#!/usr/bin/env python3
"""Harvest RSS feeds → SQLite. No translation, just raw ingestion.

Usage:
    python3 scripts/harvest.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib.news_db import NewsDB

DB_PATH = ROOT / "data" / "news.db"
SOURCES_JSON = ROOT / "data" / "sources.json"

# Category weights tuned for AI / tech news
CATEGORY_WEIGHTS = {
    "ai-research": 10, "model-launch": 10,
    "agent": 9, "open-source": 8, "safety": 6,
    "funding": 7, "policy": 6, "chips": 6,
    "enterprise": 5, "consumer": 4, "china": 4,
    "general": 1,
}

# AI-related keywords give a boost to title relevance
AI_KEYWORD_BOOSTS = {
    # tier-1 brand boost
    "anthropic": 8, "openai": 8, "claude": 7, "gpt": 6,
    "deepmind": 7, "gemini": 6, "meta ai": 6, "llama": 6,
    "mistral": 6, "deepseek": 6, "minimax": 6,
    # mechanism boost
    "ai agent": 5, "agentic": 4, "multimodal": 4,
    "open source": 3, "release": 3, "launch": 3,
    "funding": 3, "raises": 3, "acquires": 3,
    "regulation": 3, "policy": 3, "ban": 3,
    "chip": 2, "nvidia": 4, "tsmc": 3,
    "research": 2, "paper": 2, "breakthrough": 4,
}


def clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_published(entry) -> str:
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()


def is_noise(url: str, title: str, summary: str) -> bool:
    if len(title) < 10 and not summary:
        return True
    return False


def keyword_boost(title: str, summary: str) -> int:
    text = (title + " " + (summary or "")).lower()
    score = 0
    for kw, weight in AI_KEYWORD_BOOSTS.items():
        if kw in text:
            score += weight
    return min(score, 30)  # cap keyword influence


def compute_importance(source_tier: int, categories, published_iso: str,
                       title: str, summary: str) -> int:
    score = 0
    score += (3 - source_tier) * 20  # tier 1 → +40, tier 2 → +20, tier 3 → 0
    for c in categories or []:
        score += CATEGORY_WEIGHTS.get(c, 0)
    try:
        pub = datetime.fromisoformat(published_iso.replace("Z", "+00:00"))
        hours_old = (datetime.now(timezone.utc) - pub).total_seconds() / 3600
        if hours_old < 24:
            score += 15
        elif hours_old < 48:
            score += 10
        elif hours_old < 72:
            score += 5
    except Exception:
        pass
    score += keyword_boost(title, summary)
    return min(score, 100)


def harvest_source(db: NewsDB, source_row) -> dict:
    stats = {"new": 0, "dup": 0, "noise": 0, "error": None}
    try:
        feed = feedparser.parse(source_row["feed_url"])
        if feed.bozo and not feed.entries:
            stats["error"] = str(getattr(feed, "bozo_exception", "parse error"))
            return stats
        cats = json.loads(source_row["categories"] or "[]")
        for entry in feed.entries:
            url = entry.get("link", "")
            title = clean_html(entry.get("title", ""))
            summary = clean_html(entry.get("summary", entry.get("description", "")))
            if not title:
                continue
            if is_noise(url, title, summary):
                stats["noise"] += 1
                continue
            published = parse_published(entry)
            importance = compute_importance(
                source_row["tier"], cats, published, title, summary,
            )
            article = {
                "title": title,
                "summary": summary[:1000],
                "content": "",
                "source_id": source_row["source_id"],
                "source_name": source_row["name"],
                "source_name_cn": source_row["name_cn"],
                "source_url": url,
                "published_at": published,
                "lang": source_row["lang"],
                "source_categories": cats,
                "importance": importance,
            }
            rid = db.add_article(article)
            if rid:
                stats["new"] += 1
            else:
                stats["dup"] += 1
        db.update_source_fetched(source_row["source_id"])
    except Exception as e:
        stats["error"] = str(e)
    return stats


def main():
    print(f"📰 Harvest start — {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 60)
    with NewsDB(str(DB_PATH)) as db:
        # ensure sources are up to date
        s_stats = db.import_sources(str(SOURCES_JSON))
        print(f"sources: imported={s_stats['imported']} updated={s_stats['updated']}")
        print("-" * 60)

        sources = db.get_active_sources()
        totals = {"new": 0, "dup": 0, "noise": 0, "errors": 0}
        for s in sources:
            stats = harvest_source(db, s)
            totals["new"] += stats["new"]
            totals["dup"] += stats["dup"]
            totals["noise"] += stats["noise"]
            label = (s["name_cn"] or s["name"])[:24]
            if stats["error"]:
                totals["errors"] += 1
                print(f"  ❌ {label:24s} error: {stats['error'][:60]}")
            else:
                print(f"  ✅ {label:24s} new={stats['new']:3d} dup={stats['dup']:3d} noise={stats['noise']:3d}")
            time.sleep(0.3)
        print("=" * 60)
        print(f"📊 Total: new={totals['new']} dup={totals['dup']} noise={totals['noise']} errors={totals['errors']}")
        s = db.stats()
        print(f"📦 DB: total={s['total_articles']} unplayed={s['unplayed']} played={s['played']} archived={s['archived']}")


if __name__ == "__main__":
    main()
