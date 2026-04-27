"""SQLite news DB wrapper for AI Daily News v2.

Adapted from berlin-gastro-news; defaults tuned for English-source AI news.
"""
from __future__ import annotations

import sqlite3
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from .normalize import normalize_url

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "data" / "schema.sql"


class BloomFilter:
    """Memory-efficient probabilistic dedupe pre-check."""

    def __init__(self, size: int = 1_000_000, hashes: int = 7):
        self.size = size
        self.hashes = hashes
        self.bits = bytearray((size + 7) // 8)
        self.seeds = [i * 31 + 17 for i in range(hashes)]

    def _positions(self, item: str) -> List[int]:
        h = hashlib.sha256(item.encode("utf-8")).hexdigest()
        out = []
        for s in self.seeds:
            hh = hashlib.sha256((h + str(s)).encode()).hexdigest()
            out.append(int(hh, 16) % self.size)
        return out

    def add(self, item: str) -> None:
        for p in self._positions(item):
            self.bits[p // 8] |= 1 << (p % 8)

    def __contains__(self, item: str) -> bool:
        return all(self.bits[p // 8] & (1 << (p % 8)) for p in self._positions(item))

    def load_from_db(self, conn: sqlite3.Connection) -> None:
        try:
            for (h,) in conn.execute("SELECT story_hash FROM news_articles"):
                self.add(h)
        except sqlite3.OperationalError:
            pass


class NewsDB:
    def __init__(self, db_path: Union[str, Path], use_bloom: bool = True):
        self.db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._bloom: Optional[BloomFilter] = None
        self._use_bloom = use_bloom

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA cache_size=-64000")
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.connect()
        if self._use_bloom:
            self._bloom = BloomFilter()
            self._bloom.load_from_db(self._conn)
        return self

    def __exit__(self, *args):
        self.close()

    def init(self) -> None:
        conn = self.connect()
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

    @staticmethod
    def make_hash(title: str, source_name: str) -> str:
        raw = f"{title.strip()}::{source_name.strip()}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    # ── Sources ────────────────────────────────────────

    def import_sources(self, sources_json_path: Union[str, Path]) -> Dict[str, int]:
        conn = self.connect()
        with open(sources_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        sources = data.get("sources", data) if isinstance(data, dict) else data
        stats = {"imported": 0, "updated": 0}
        conn.execute("BEGIN")
        try:
            for s in sources:
                row = conn.execute(
                    "SELECT id FROM sources WHERE source_id = ?", (s["id"],)
                ).fetchone()
                cats = json.dumps(s.get("categories", []), ensure_ascii=False)
                if row:
                    conn.execute("""
                        UPDATE sources SET
                            name=?, name_cn=?, feed_url=?, type=?, lang=?,
                            tier=?, categories=?, enabled=?, notes=?
                        WHERE source_id=?
                    """, (
                        s["name"], s.get("name_cn"), s["feed_url"],
                        s.get("type", "rss"), s.get("lang", "en"),
                        s.get("tier", 2), cats,
                        1 if s.get("active", True) else 0,
                        s.get("notes"), s["id"],
                    ))
                    stats["updated"] += 1
                else:
                    conn.execute("""
                        INSERT INTO sources
                            (source_id, name, name_cn, feed_url, type, lang,
                             tier, categories, enabled, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        s["id"], s["name"], s.get("name_cn"), s["feed_url"],
                        s.get("type", "rss"), s.get("lang", "en"),
                        s.get("tier", 2), cats,
                        1 if s.get("active", True) else 0,
                        s.get("notes"),
                    ))
                    stats["imported"] += 1
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return stats

    def get_active_sources(self) -> List[sqlite3.Row]:
        conn = self.connect()
        return conn.execute(
            "SELECT * FROM sources WHERE enabled = 1 ORDER BY tier, source_id"
        ).fetchall()

    def update_source_fetched(self, source_id: str) -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE sources SET last_fetched = ? WHERE source_id = ?",
            (datetime.now(timezone.utc).isoformat(), source_id),
        )

    # ── Articles ───────────────────────────────────────

    def add_article(self, article: Dict[str, Any]) -> Optional[int]:
        """Insert one article. Returns rowid on insert, None on duplicate."""
        conn = self.connect()
        title = article["title"].strip()
        source_name = article["source_name"].strip()
        story_hash = self.make_hash(title, source_name)
        url_norm = normalize_url(article.get("source_url"))

        if url_norm:
            row = conn.execute(
                "SELECT id FROM news_articles WHERE url_normalized = ?",
                (url_norm,),
            ).fetchone()
            if row:
                return None

        try:
            cur = conn.execute("""
                INSERT OR IGNORE INTO news_articles
                    (title, summary, content, source_id, source_name, source_name_cn,
                     source_url, url_normalized, published_at, story_hash, lang,
                     source_categories, importance, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title,
                article.get("summary", ""),
                article.get("content", ""),
                article.get("source_id"),
                source_name,
                article.get("source_name_cn"),
                article.get("source_url"),
                url_norm,
                article.get("published_at"),
                story_hash,
                article.get("lang", "en"),
                json.dumps(article.get("source_categories", []), ensure_ascii=False),
                article.get("importance", 0),
                json.dumps(article.get("raw_json"), ensure_ascii=False)
                if article.get("raw_json") else None,
            ))
            if cur.lastrowid and cur.rowcount > 0:
                if self._bloom:
                    self._bloom.add(story_hash)
                return cur.lastrowid
            return None
        except sqlite3.IntegrityError:
            return None

    def get_unplayed(self, limit: int = 10, min_importance: int = 0) -> List[sqlite3.Row]:
        conn = self.connect()
        return conn.execute("""
            SELECT * FROM news_articles
            WHERE broadcast_status = 'unplayed' AND importance >= ?
            ORDER BY importance DESC, discovered_at DESC
            LIMIT ?
        """, (min_importance, limit)).fetchall()

    def get_by_id(self, article_id: int) -> Optional[sqlite3.Row]:
        conn = self.connect()
        return conn.execute(
            "SELECT * FROM news_articles WHERE id = ?", (article_id,)
        ).fetchone()

    def update_translation(
        self,
        article_id: int,
        translated_title: str,
        translated_summary: str,
        translated_body: str,
        impact_analysis: str,
        industry_tags: List[str],
        slug: Optional[str] = None,
    ) -> None:
        conn = self.connect()
        if slug:
            conn.execute("""
                UPDATE news_articles
                   SET translated_title = ?,
                       translated_summary = ?,
                       translated_body = ?,
                       impact_analysis = ?,
                       industry_tags = ?,
                       slug = ?
                 WHERE id = ?
            """, (
                translated_title, translated_summary, translated_body,
                impact_analysis,
                json.dumps(industry_tags, ensure_ascii=False),
                slug, article_id,
            ))
        else:
            conn.execute("""
                UPDATE news_articles
                   SET translated_title = ?,
                       translated_summary = ?,
                       translated_body = ?,
                       impact_analysis = ?,
                       industry_tags = ?
                 WHERE id = ?
            """, (
                translated_title, translated_summary, translated_body,
                impact_analysis,
                json.dumps(industry_tags, ensure_ascii=False),
                article_id,
            ))

    def mark_played(self, article_ids: List[int], briefing_date: str) -> None:
        if not article_ids:
            return
        conn = self.connect()
        placeholders = ",".join("?" * len(article_ids))
        conn.execute("BEGIN")
        try:
            conn.execute(f"""
                UPDATE news_articles
                   SET broadcast_status = 'played',
                       broadcast_date = ?,
                       published_briefing_date = ?
                 WHERE id IN ({placeholders})
            """, [briefing_date, briefing_date] + list(article_ids))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def get_articles_pending_publication(self) -> List[sqlite3.Row]:
        """Articles with translation that need a published .md file."""
        conn = self.connect()
        return conn.execute("""
            SELECT * FROM news_articles
            WHERE translated_body IS NOT NULL
              AND translated_body != ''
            ORDER BY published_at DESC
        """).fetchall()

    def get_articles_for_briefing(self, briefing_date: str) -> List[sqlite3.Row]:
        conn = self.connect()
        return conn.execute("""
            SELECT * FROM news_articles
            WHERE published_briefing_date = ?
            ORDER BY importance DESC, id ASC
        """, (briefing_date,)).fetchall()

    def log_broadcast(
        self,
        broadcast_date: str,
        article_ids: List[int],
        briefing_url: Optional[str] = None,
        audio_url: Optional[str] = None,
        audio_path: Optional[str] = None,
    ) -> None:
        conn = self.connect()
        conn.execute("""
            INSERT OR REPLACE INTO broadcast_log
                (broadcast_date, article_ids, article_count,
                 briefing_url, audio_url, audio_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            broadcast_date,
            json.dumps(article_ids, ensure_ascii=False),
            len(article_ids), briefing_url, audio_url, audio_path,
        ))

    def stats(self) -> Dict[str, int]:
        conn = self.connect()
        row = conn.execute("""
            SELECT COUNT(*) AS total,
                   SUM(broadcast_status = 'unplayed') AS unplayed,
                   SUM(broadcast_status = 'played') AS played,
                   SUM(broadcast_status = 'archived') AS archived,
                   SUM(slug IS NOT NULL) AS published
              FROM news_articles
        """).fetchone()
        sources_n = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE enabled = 1"
        ).fetchone()[0]
        return {
            "total_articles": row["total"] or 0,
            "unplayed": row["unplayed"] or 0,
            "played": row["played"] or 0,
            "archived": row["archived"] or 0,
            "published": row["published"] or 0,
            "active_sources": sources_n,
        }


def cli():
    import argparse
    p = argparse.ArgumentParser(description="news_db tooling")
    p.add_argument("db_path")
    p.add_argument("--init", action="store_true")
    p.add_argument("--import-sources", metavar="JSON")
    p.add_argument("--stats", action="store_true")
    args = p.parse_args()
    with NewsDB(args.db_path) as db:
        if args.init:
            db.init()
            print(f"[news_db] initialized {args.db_path}")
        if args.import_sources:
            stats = db.import_sources(args.import_sources)
            print(f"[news_db] sources: imported={stats['imported']} updated={stats['updated']}")
        if args.stats:
            for k, v in db.stats().items():
                print(f"  {k}: {v}")


if __name__ == "__main__":
    cli()
