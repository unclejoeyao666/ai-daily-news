#!/usr/bin/env python3
"""Render translated articles from DB into site/src/content/articles/<slug>.md.

Tag taxonomy is loaded from data/tags.json (single source of truth).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib.news_db import NewsDB

DB_PATH = ROOT / "data" / "news.db"
TAGS_JSON = ROOT / "data" / "tags.json"
ARTICLES_DIR = ROOT / "site" / "src" / "content" / "articles"


def load_valid_tags() -> set:
    with open(TAGS_JSON, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return {t["slug"] for t in cfg["tags"]}


def slugify(text: str, max_len: int = 50) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s\-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len].rstrip("-")


def make_slug(row) -> str:
    """Build slug from English original title (transliteration-friendly) + pubDate.

    Chinese translated_title would yield empty slugs after slugify, so we
    use the original title for the alphanumeric part. Date suffix is
    always preserved in full (10 chars: YYYY-MM-DD)."""
    pub = (row["published_at"] or row["discovered_at"])[:10]
    base = slugify(row["title"] or "")
    if not base:
        base = slugify(row["translated_title"] or "")
    if not base:
        url = row["source_url"] or ""
        base = slugify(url.rstrip("/").rsplit("/", 1)[-1])[:30] or "article"
    base_max = 60 - len(pub) - 1
    return f"{base[:base_max].rstrip('-')}-{pub}"


def yaml_escape(s: str) -> str:
    s = (s or "").replace('"', '\\"').replace("\n", " ").strip()
    return f'"{s}"'


def render_frontmatter(row, slug: str, tags) -> str:
    pub = (row["published_at"] or row["discovered_at"])[:10]
    return "\n".join([
        "---",
        f"title: {yaml_escape(row['translated_title'])}",
        f"titleOriginal: {yaml_escape(row['title'])}",
        f"description: {yaml_escape(row['translated_summary'])}",
        f"pubDate: {pub}",
        f"sourceName: {yaml_escape(row['source_name'])}",
        f"sourceUrl: {yaml_escape(row['source_url'])}",
        f"sourceLang: {row['lang'] or 'en'}",
        f"tags: [{', '.join(yaml_escape(t) for t in tags)}]",
        "---",
        "",
    ])


def render_body(row) -> str:
    body = row["translated_body"] or ""
    impact = row["impact_analysis"] or ""
    out = body.strip() + "\n\n"
    if impact.strip():
        out += "## 对 AI 行业的影响\n\n"
        out += impact.strip() + "\n\n"
    out += "---\n\n## 原文参考\n\n"
    out += f"来源：[{row['source_name']}]({row['source_url']})"
    if row["published_at"]:
        out += f" · {row['published_at'][:10]}"
    out += "\n\n"
    if row["summary"]:
        out += "> " + row["summary"].replace("\n", "\n> ") + "\n"
    return out


def write_article(row, db: NewsDB, valid_tags: set, force: bool = False) -> Path:
    tags = json.loads(row["industry_tags"] or "[]")
    invalid = [t for t in tags if t not in valid_tags]
    if invalid:
        raise ValueError(f"Invalid tags for article {row['id']}: {invalid}")
    if not tags:
        raise ValueError(f"Article {row['id']} has no tags")

    slug = row["slug"] or make_slug(row)
    if not row["slug"]:
        conn = db.connect()
        n = 1
        candidate = slug
        while conn.execute(
            "SELECT 1 FROM news_articles WHERE slug = ? AND id != ?",
            (candidate, row["id"]),
        ).fetchone():
            n += 1
            candidate = f"{slug}-{n}"
        slug = candidate
        conn.execute("UPDATE news_articles SET slug = ? WHERE id = ?", (slug, row["id"]))
        row = db.get_by_id(row["id"])

    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARTICLES_DIR / f"{slug}.md"
    if out_path.exists() and not force:
        print(f"⚠️  exists, skipping: {out_path.name}")
        return out_path

    content = render_frontmatter(row, slug, tags) + render_body(row)
    out_path.write_text(content, encoding="utf-8")
    print(f"✅ wrote {out_path.relative_to(ROOT)}")
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--id", type=int, help="Publish single article by id")
    p.add_argument("--all-pending", action="store_true",
                   help="Publish all with translated_body but no slug")
    p.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = p.parse_args()

    if not args.id and not args.all_pending:
        p.error("--id or --all-pending required")

    valid_tags = load_valid_tags()

    with NewsDB(str(DB_PATH)) as db:
        if args.id:
            row = db.get_by_id(args.id)
            if not row:
                print(f"❌ article {args.id} not found")
                sys.exit(1)
            if not row["translated_body"]:
                print(f"❌ article {args.id} has no translation")
                sys.exit(1)
            write_article(row, db, valid_tags, force=args.force)
        else:
            rows = db.get_articles_pending_publication()
            print(f"📂 {len(rows)} translated articles")
            for row in rows:
                try:
                    write_article(row, db, valid_tags, force=args.force)
                except ValueError as e:
                    print(f"⚠️  {e}")


if __name__ == "__main__":
    main()
