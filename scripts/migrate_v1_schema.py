#!/usr/bin/env python3
"""Migrate ai-daily-news v1 SQLite schema to v2 in place.

Idempotent: safe to run multiple times. Detects existing columns/tables
and only applies missing changes.

Operations:
  1. ALTER TABLE news_articles: add v2 columns if missing
  2. ALTER TABLE sources: add source_id, name_cn, tier, categories if missing
  3. Backfill source_id from name (using sources.json mapping)
  4. Drop + recreate news_fts with extended columns
  5. Recreate triggers
  6. Mark all v1 unplayed articles as 'archived' (per design decision A)
  7. PRAGMA user_version = 2

Run: python3 scripts/migrate_v1_schema.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "news.db"
SCHEMA_PATH = ROOT / "data" / "schema.sql"
SOURCES_JSON = ROOT / "data" / "sources.json"


def existing_columns(conn: sqlite3.Connection, table: str) -> set:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def add_missing_columns(conn: sqlite3.Connection, table: str, specs: list):
    """specs is list of (column_name, sql_decl)."""
    have = existing_columns(conn, table)
    for col, decl in specs:
        if col not in have:
            print(f"  + ALTER TABLE {table} ADD COLUMN {col}")
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def main():
    if not DB_PATH.exists():
        print(f"❌ DB not found: {DB_PATH}")
        sys.exit(1)

    print(f"📦 Migrating {DB_PATH.relative_to(ROOT)} → schema v2")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Step 1: news_articles new columns
    print("\n[1] news_articles columns")
    add_missing_columns(conn, "news_articles", [
        ("summary", "TEXT"),
        ("source_name_cn", "TEXT"),
        ("source_categories", "TEXT"),
        ("lang", "TEXT NOT NULL DEFAULT 'en'"),
        ("translated_title", "TEXT"),
        ("translated_summary", "TEXT"),
        ("translated_body", "TEXT"),
        ("impact_analysis", "TEXT"),
        ("industry_tags", "TEXT"),
        ("slug", "TEXT"),
        ("published_briefing_date", "TEXT"),
    ])

    # Step 2: sources new columns
    print("\n[2] sources columns")
    add_missing_columns(conn, "sources", [
        ("source_id", "TEXT"),     # add nullable first; will populate then add UNIQUE index
        ("name_cn", "TEXT"),
        ("tier", "INTEGER NOT NULL DEFAULT 2"),
        ("categories", "TEXT"),
        ("notes", "TEXT"),
        ("feed_url", "TEXT"),
        ("lang", "TEXT NOT NULL DEFAULT 'en'"),
    ])
    # Backfill lang from legacy `language` column if present
    try:
        conn.execute("UPDATE sources SET lang = COALESCE(language, lang) WHERE lang IS NULL OR lang = ''")
    except sqlite3.OperationalError:
        pass  # legacy column may not exist on fresh installs

    # Step 2b: broadcast_log new columns (v2 adds briefing_url / audio_url)
    print("\n[2b] broadcast_log columns")
    add_missing_columns(conn, "broadcast_log", [
        ("briefing_url", "TEXT"),
        ("audio_url", "TEXT"),
    ])

    # Step 3: backfill source_id from sources.json (match by name)
    print("\n[3] backfill source_id + tier + name_cn from sources.json")
    with open(SOURCES_JSON, "r", encoding="utf-8") as f:
        sj = json.load(f)
    name_to_meta = {s["name"]: s for s in sj["sources"]}
    name_to_url_meta = {s["feed_url"]: s for s in sj["sources"]}

    rows = conn.execute("SELECT id, name, url, source_id FROM sources").fetchall()
    updated = 0
    for row in rows:
        if row["source_id"]:
            continue
        meta = name_to_meta.get(row["name"]) or name_to_url_meta.get(row["url"])
        if not meta:
            print(f"  ⚠️  no metadata for source: {row['name']} (id={row['id']})")
            continue
        cats = json.dumps(meta.get("categories", []), ensure_ascii=False)
        conn.execute("""
            UPDATE sources
               SET source_id=?, name_cn=?, tier=?, categories=?, notes=?, feed_url=?
             WHERE id=?
        """, (
            meta["id"], meta.get("name_cn"), meta.get("tier", 2),
            cats, meta.get("notes"), meta["feed_url"], row["id"],
        ))
        updated += 1
    print(f"  → updated {updated} source rows")

    # Drop legacy column 'category' is non-trivial in SQLite; leave it.
    # Add unique index on source_id (only if all rows now have one)
    null_sources = conn.execute(
        "SELECT COUNT(*) FROM sources WHERE source_id IS NULL"
    ).fetchone()[0]
    if null_sources == 0:
        try:
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_source_source_id ON sources(source_id)")
            print("  + UNIQUE INDEX on sources(source_id)")
        except sqlite3.OperationalError as e:
            print(f"  ⚠️  could not create unique index: {e}")

    # Step 4: Drop & recreate FTS5
    print("\n[4] Rebuild news_fts (extended columns)")
    conn.execute("DROP TABLE IF EXISTS news_fts")
    for trig in ("news_articles_ai", "news_articles_ad", "news_articles_au"):
        conn.execute(f"DROP TRIGGER IF EXISTS {trig}")

    # Apply schema additions (CREATE IF NOT EXISTS will skip existing tables)
    print("  → applying data/schema.sql (CREATE IF NOT EXISTS / triggers)")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    # Backfill FTS for existing rows
    print("\n[5] Populate FTS index")
    conn.execute("""
        INSERT INTO news_fts(rowid, title, summary, content, translated_title, translated_body, impact_analysis)
        SELECT id, title,
               COALESCE(summary, ''),
               COALESCE(content, ''),
               COALESCE(translated_title, ''),
               COALESCE(translated_body, ''),
               COALESCE(impact_analysis, '')
          FROM news_articles
    """)
    fts_n = conn.execute("SELECT COUNT(*) FROM news_fts").fetchone()[0]
    print(f"  → indexed {fts_n} articles")

    # Step 6: Archive all old articles per design decision A
    print("\n[6] Archive all v1 articles (broadcast_status → 'archived')")
    cur = conn.execute(
        "UPDATE news_articles SET broadcast_status = 'archived' "
        "WHERE broadcast_status IN ('unplayed', 'played')"
    )
    print(f"  → archived {cur.rowcount} rows")

    # Step 7: Final
    conn.execute("PRAGMA user_version = 2")
    conn.commit()

    # Stats
    print("\n[7] Final stats")
    stats = conn.execute("""
        SELECT broadcast_status, COUNT(*) FROM news_articles GROUP BY broadcast_status
    """).fetchall()
    for status, n in stats:
        print(f"  {status:12s} {n}")
    n_sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    print(f"  sources      {n_sources}")

    conn.close()
    print("\n✅ migration complete")


if __name__ == "__main__":
    main()
