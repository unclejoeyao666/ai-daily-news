#!/usr/bin/env python3
"""Publish the daily briefing.

Outputs:
  1. site/src/content/briefings/<YYYY-MM-DD>.md
  2. daily/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/{briefing.md, meta.json}
  3. Marks all selected articles broadcast_status='played'
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
SELECTED_JSON = ROOT / "daily-selected.json"
SITE_BRIEFINGS = ROOT / "site" / "src" / "content" / "briefings"
DAILY_ROOT = ROOT / "daily"
SITE_BASE = "/ai-daily-news"


def yaml_escape(s):
    s = (s or "").replace('"', '\\"').replace("\n", " ").strip()
    return f'"{s}"'


def parse_date(s) -> str:
    if not s or s == "today":
        return datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")
    return s


def render_briefing_collection(date_str, audio_url, slugs, intro) -> str:
    parts = [
        "---",
        f"title: {yaml_escape(f'AI 科技每日早报 — {date_str}')}",
        f"date: {date_str}",
        f"audioUrl: {yaml_escape(audio_url)}",
        "articles:",
    ]
    for s in slugs:
        parts.append(f"  - {yaml_escape(s)}")
    parts.append("---")
    parts.append("")
    if intro and intro.strip():
        parts.append(intro.strip())
        parts.append("")
    return "\n".join(parts)


def render_discord_briefing(date_str, rows, audio_url, site_url) -> str:
    """Markdown for Discord — short, link-heavy."""
    lines = [
        f"# 🤖 AI 科技每日早报 — {date_str}",
        "",
        f"🎧 [今日音频]({audio_url}) · 🌐 [完整网页]({site_url})",
        "",
    ]
    for i, row in enumerate(rows, 1):
        slug = row["slug"]
        title = row["translated_title"]
        summary = row["translated_summary"]
        url = f"{site_url.rstrip('/')}/articles/{slug}"
        lines.append(f"## {i}. [{title}]({url})")
        if summary:
            lines.append(summary)
        lines.append("")
    lines.append("---")
    sources = sorted(set(r["source_name_cn"] or r["source_name"] for r in rows))
    lines.append(f"*共 {len(rows)} 条 · 来源：{', '.join(sources)}*")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default="today")
    p.add_argument("--intro-file", help="Optional intro markdown file")
    p.add_argument("--selected", default=str(SELECTED_JSON))
    p.add_argument("--site-url",
                   default="https://unclejoeyao666.github.io/ai-daily-news")
    args = p.parse_args()

    date_str = parse_date(args.date)
    selected = json.loads(Path(args.selected).read_text(encoding="utf-8"))
    ids = [a["id"] for a in selected["articles"]]
    if not ids:
        print("⚠️  no articles in daily-selected.json")
        sys.exit(0)

    audio_rel = f"{SITE_BASE}/audio/{date_str}.mp3"
    audio_url_full = f"{args.site_url}/audio/{date_str}.mp3"
    briefing_url_full = f"{args.site_url}/briefings/{date_str}"

    intro = ""
    if args.intro_file and Path(args.intro_file).exists():
        intro = Path(args.intro_file).read_text(encoding="utf-8")

    with NewsDB(str(DB_PATH)) as db:
        rows = []
        for aid in ids:
            row = db.get_by_id(aid)
            if not row:
                print(f"⚠️  article {aid} missing")
                continue
            if not row["slug"]:
                print(f"❌ article {aid} has no slug — run publish_article first")
                sys.exit(2)
            if not row["translated_title"]:
                print(f"❌ article {aid} has no translation")
                sys.exit(2)
            rows.append(row)

        # Mark them played + assign briefing date
        db.mark_played([r["id"] for r in rows], briefing_date=date_str)

        # Briefing collection (Astro)
        SITE_BRIEFINGS.mkdir(parents=True, exist_ok=True)
        coll_path = SITE_BRIEFINGS / f"{date_str}.md"
        coll_content = render_briefing_collection(
            date_str, audio_rel, [r["slug"] for r in rows], intro,
        )
        coll_path.write_text(coll_content, encoding="utf-8")
        print(f"✅ {coll_path.relative_to(ROOT)}")

        # Daily pickup files
        year, month, _ = date_str.split("-")
        daily_dir = DAILY_ROOT / year / f"{year}-{month}" / date_str
        daily_dir.mkdir(parents=True, exist_ok=True)

        discord_path = daily_dir / "briefing.md"
        discord_path.write_text(
            render_discord_briefing(date_str, rows, audio_url_full, args.site_url),
            encoding="utf-8",
        )
        print(f"✅ {discord_path.relative_to(ROOT)}")

        meta = {
            "date": date_str,
            "article_ids": [r["id"] for r in rows],
            "article_slugs": [r["slug"] for r in rows],
            "briefing_url": briefing_url_full,
            "audio_url": audio_url_full,
            "site_base": args.site_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = daily_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ {meta_path.relative_to(ROOT)}")

        db.log_broadcast(
            broadcast_date=date_str,
            article_ids=[r["id"] for r in rows],
            briefing_url=briefing_url_full,
            audio_url=audio_url_full,
            audio_path=str((daily_dir / "audio.mp3").relative_to(ROOT)),
        )


if __name__ == "__main__":
    main()
