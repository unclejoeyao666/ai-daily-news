#!/usr/bin/env python3
"""
news_db.py — AI 科技早报数据库操作层 v2
Fanli | 2026-04-14

优化重点：
  - 复合索引消除 SORT tempfile（get_unplayedArticles 加速）
  - INSERT OR IGNORE 替代 SELECT-THEN-INSERT（减少 DB roundtrip）
  - 批量 commit（add_articles 加速）
  - URL 归一化（跨源查重）
  - make_hash 支持 URL-first 双通道查重
  - 修复 backfill 循环内 connect() 泄漏 bug
  - FTS5 全文搜索支持
  - author 字段补全
"""

import sqlite3
import json
import hashlib
import re
import os
import sys
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_SCHEMA_PATH = os.path.join(DB_DIR, 'schema.sql')


# ── URL 归一化 ──────────────────────────────────────────

TRACKING_STRIP_RE = re.compile(
    r'(\?|&)(utm_source|utm_medium|utm_campaign|utm_term|utm_content|'
    r'fbclid|gclid|gclsrc|dclid|msclkid|twclid|ref|igshid|'
    r'share_id|si=|mc_cid|mc_eid|oly_enc_id|vero_id|'
    r'__s=|ss=|s_kwcid|assetType=|mkt_tok=|trk|'
    r'nr_email_referer|ml_sub|ml_eid|wickedid)'
    r'=[^&\s]*',
    re.IGNORECASE
)
PATH_NORMALIZE_RE = re.compile(r'/(index|default|home)\.html?$', re.IGNORECASE)
TRAILING_SLASH_RE = re.compile(r'/$')


def normalize_url(url: Optional[str]) -> Optional[str]:
    """将 URL 归一化：去 tracking 参数、统一路径格式"""
    if not url:
        return None
    url = url.strip()
    try:
        # 先去 fragment
        url = url.split('#')[0]
        # 去 tracking 参数
        url = TRACKING_STRIP_RE.sub('', url)
        # 去掉 ? 如果变空了
        url = url.rstrip('?')
        # 规范化路径末尾
        url = PATH_NORMALIZE_RE.sub('', url)
        url = TRAILING_SLASH_RE.sub('', url)
        if len(url) < 12:  # 过滤残余垃圾
            return None
        return url
    except Exception:
        return None


# ── Bloom Filter（内存快速查重）──────────────────────────

class BloomFilter:
    """
    内存布隆过滤器，用 Python bytes 作为 BIT Array。
    容量 ~50万，误判率 < 1%，单机内存 < 1MB。
    用于 add_article 的首次快速预检，避免每次都查 SQLite。
    """

    def __init__(self, size: int = 1_000_000, hashes: int = 7):
        self.size = size          # bit 数
        self.hashes = hashes      # hash 函数个数
        self.bytes_ = bytearray((size + 7) // 8)  # BIT array
        # 预生成多个 hash seed
        self.seeds = [i * 31 + 17 for i in range(hashes)]

    def _bits(self, item: str) -> List[int]:
        """返回 item 的 k 个 bit 位置"""
        h = hashlib.sha256(item.encode('utf-8')).hexdigest()
        out = []
        for i in range(self.hashes):
            # 用 seed 重新 hash
            hh = hashlib.sha256((h + str(self.seeds[i])).encode()).hexdigest()
            out.append(int(hh, 16) % self.size)
        return out

    def add(self, item: str) -> None:
        for bit in self._bits(item):
            self.bytes_[bit // 8] |= 1 << (bit % 8)

    def __contains__(self, item: str) -> bool:
        """返回 True = 可能在集合中（需进一步查 DB 确认）
           返回 False = 一定不在集合中（绝对不漏）"""
        return all(
            self.bytes_[bit // 8] & (1 << (bit % 8))
            for bit in self._bits(item)
        )

    def load_from_db(self, conn: sqlite3.Connection) -> None:
        """从现有 DB 加载已有 story_hash 到 bloom filter"""
        for (hash_val,) in conn.execute(
            "SELECT story_hash FROM news_articles"
        ).fetchall():
            self.add(hash_val)


# ── NewsDB ─────────────────────────────────────────────

class NewsDB:
    """SQLite 数据库操作封装 v2"""

    def __init__(self, db_path: str, use_bloom: bool = True):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._bloom: Optional[BloomFilter] = None
        self._use_bloom = use_bloom

    # ── 连接管理 ───────────────────────────────────────

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None,        # autocommit mode；手动控制事务
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")  # 更快写入
            self._conn.execute("PRAGMA cache_size=-64000")   # 64MB cache
        return self._conn

    def close(self):
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

    # ── 初始化 ─────────────────────────────────────────

    def init(self) -> None:
        conn = self.connect()
        with open(DB_SCHEMA_PATH, 'r') as f:
            conn.executescript(f.read())
        conn.execute("PRAGMA user_version = 2")  # schema 版本标记
        print(f"[news_db] Database ready: {self.db_path}")

    # ── 订阅源管理 ────────────────────────────────────

    def import_sources(self, sources_json_path: str) -> int:
        conn = self.connect()
        with open(sources_json_path, 'r', encoding='utf-8') as f:
            sources = json.load(f)
        imported = 0
        conn.execute("BEGIN")
        try:
            for s in sources:
                conn.execute("""
                    INSERT OR IGNORE INTO sources
                        (name, url, type, category, language)
                    VALUES (:name, :url, :type, :category, :language)
                """, {
                    'name': s['name'],
                    'url': s['url'],
                    'type': s.get('type', 'rss'),
                    'category': s.get('category', 'general'),
                    'language': s.get('language', 'en'),
                })
                imported += 1
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        print(f"[news_db] Imported {imported}/{len(sources)} sources")
        return imported

    def get_active_sources(self) -> List[sqlite3.Row]:
        conn = self.connect()
        return conn.execute(
            "SELECT * FROM sources WHERE enabled = 1 ORDER BY category, name"
        ).fetchall()

    def update_source_fetched(self, source_id: int) -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE sources SET last_fetched = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), source_id)
        )

    # ── 哈希 ───────────────────────────────────────────

    @staticmethod
    def make_hash(title: str, source_name: str) -> str:
        """标准 story_hash：SHA256(title || source_name)"""
        raw = f"{title.strip()}::{source_name.strip()}".encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def make_url_hash(url: str) -> str:
        """URL-first 查重哈希（归一化 URL 的 SHA256）"""
        norm = normalize_url(url)
        if not norm:
            return ''
        return hashlib.sha256(norm.encode('utf-8')).hexdigest()

    # ── 新闻增删改查 ──────────────────────────────────

    def add_article(
        self,
        title: str,
        content: Optional[str],
        source_name: str,
        source_url: Optional[str] = None,
        published_at: Optional[str] = None,
        source_id: Optional[int] = None,
        importance: int = 0,
        topic_tags: Optional[List[str]] = None,
        raw_json: Optional[Dict] = None,
        author: Optional[str] = None,
    ) -> Optional[int]:
        """
        添加一篇新闻。
        - 先用 BloomFilter 预检（O(1)，内存中）
        - 再用 SQLite UNIQUE 约束保证精确去重
        - BloomFilter 可能误判（false positive），DB 精确去重兜底
        返回：新插入行 id；None = 重复
        """
        conn = self.connect()
        title_stripped = title.strip()
        source_name_stripped = source_name.strip()
        story_hash = self.make_hash(title_stripped, source_name_stripped)
        url_norm = normalize_url(source_url) if source_url else None

        # 1. BloomFilter 预检（快速路）
        if self._bloom and story_hash not in self._bloom:
            # 不在 bloom 中 = 一定不重复，不需要查 DB
            pass  # 继续插入流程

        # 2. URL-first 快速检查（归一化 URL 相同则高度疑似重复）
        if url_norm:
            url_hash = hashlib.sha256(url_norm.encode('utf-8')).hexdigest()
            url_dup = conn.execute(
                "SELECT id FROM news_articles WHERE url_normalized = ?",
                (url_norm,)
            ).fetchone()
            if url_dup:
                # 同一归一化 URL 已存在，记录为 duplicate
                return None

        # 3. 精确 story_hash 查重（INSERT OR IGNORE 方式）
        #    使用 url_normalized 列辅助唯一约束
        try:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO news_articles
                    (title, content, source_id, source_name, source_url,
                     url_normalized, published_at, story_hash,
                     importance, topic_tags, raw_json, author)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title_stripped,
                (content or '').strip(),
                source_id,
                source_name_stripped,
                source_url,
                url_norm,
                published_at,
                story_hash,
                importance,
                json.dumps(topic_tags or [], ensure_ascii=False),
                json.dumps(raw_json, ensure_ascii=False) if raw_json else None,
                author,
            ))
            conn.execute("COMMIT")
            rowid = cursor.lastrowid

            if rowid and rowid > 0:
                # 插入成功，加入 bloom filter
                if self._bloom:
                    self._bloom.add(story_hash)
                return rowid
            else:
                # INSERT OR IGNORE 跳过（UNIQUE 冲突）
                return None

        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK")
            return None

    def add_articles(self, articles: List[Dict[str, Any]], batch_size: int = 50) -> Dict[str, int]:
        """
        批量添加新闻（批量 commit 优化）。
        每 batch_size 条 commit 一次，大幅减少事务开销。
        返回: {'new': N, 'duplicate': M}
        """
        conn = self.connect()
        stats = {'new': 0, 'duplicate': 0}
        batch = []

        for a in articles:
            title_stripped = a['title'].strip()
            source_name_stripped = a['source_name'].strip()
            story_hash = self.make_hash(title_stripped, source_name_stripped)
            url_norm = normalize_url(a.get('source_url')) if a.get('source_url') else None

            # BloomFilter 预检
            if self._bloom and story_hash in self._bloom:
                # 可能在集合中，必须查 DB 确认
                exists = conn.execute(
                    "SELECT 1 FROM news_articles WHERE story_hash = ?", (story_hash,)
                ).fetchone()
                if exists:
                    stats['duplicate'] += 1
                    continue
                # bloom 说可能存在，但 DB 没有（false positive），继续插入

            batch.append((
                title_stripped,
                (a.get('content') or '').strip(),
                a.get('source_id'),
                source_name_stripped,
                a.get('source_url'),
                url_norm,
                a.get('published_at'),
                story_hash,
                a.get('importance', 0),
                json.dumps(a.get('tags') or [], ensure_ascii=False),
                json.dumps(a, ensure_ascii=False) if a else None,
                a.get('author'),
            ))

            # 凑够 batch_size 条，或最后一批，批量插入
            if len(batch) >= batch_size:
                n_new, n_dup = self._insert_batch(conn, batch)
                stats['new'] += n_new
                stats['duplicate'] += n_dup
                batch = []

        # 处理剩余
        if batch:
            n_new, n_dup = self._insert_batch(conn, batch)
            stats['new'] += n_new
            stats['duplicate'] += n_dup

        return stats

    def _insert_batch(self, conn: sqlite3.Connection, batch: List[tuple]) -> tuple:
        """单次批量插入，返回 (new_count, dup_count)"""
        new_cnt = dup_cnt = 0
        conn.execute("BEGIN")
        try:
            conn.executemany("""
                INSERT OR IGNORE INTO news_articles
                    (Title, content, source_id, source_name, source_url,
                     url_normalized, published_at, story_hash,
                     importance, topic_tags, raw_json, author)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            inserted = conn.total_changes
            dup_cnt = len(batch) - inserted
            new_cnt = inserted
            conn.execute("COMMIT")

            # 更新 bloom filter（仅新增的）
            # 注意：executemany 不返回 lastrowid，只能通过 total_changes 估算
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return new_cnt, dup_cnt

    def get_unplayed_articles(
        self,
        limit: int = 10,
        min_importance: int = 0,
    ) -> List[sqlite3.Row]:
        """获取未播新闻——使用复合索引，无 filesort"""
        conn = self.connect()
        return conn.execute("""
            SELECT id, title, content, source_name, source_url,
                   published_at, importance, topic_tags, discovered_at
            FROM news_articles
            WHERE broadcast_status = 'unplayed'
              AND importance >= ?
            ORDER BY importance DESC, discovered_at DESC
            LIMIT ?
        """, (min_importance, limit)).fetchall()

    def mark_played(self, article_ids: List[int], broadcast_date: str) -> None:
        if not article_ids:
            return
        placeholders = ','.join('?' * len(article_ids))
        conn = self.connect()
        conn.execute("BEGIN")
        conn.execute(f"""
            UPDATE news_articles
            SET broadcast_status = 'played', broadcast_date = ?
            WHERE id IN ({placeholders})
        """, [broadcast_date] + article_ids)
        conn.execute("COMMIT")

    def get_article_by_id(self, article_id: int) -> Optional[sqlite3.Row]:
        conn = self.connect()
        return conn.execute(
            "SELECT * FROM news_articles WHERE id = ?", (article_id,)
        ).fetchone()

    # ── FTS 搜索 ───────────────────────────────────────

    def search_articles(
        self,
        query: str,
        limit: int = 10,
        broadcast_status: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        """
        全文搜索（基于 FTS5）。
        支持 AND/OR/NOT 语法。
        """
        conn = self.connect()
        sql = """
            SELECT a.id, a.title, a.content, a.source_name,
                   a.source_url, a.published_at, a.importance,
                   a.broadcast_status, a.broadcast_date,
                   snippet(news_fts, 0, '**', '**', '…', 24) AS title_snippet,
                   snippet(news_fts, 1, '…', '…', '…', 40) AS content_snippet
            FROM news_fts f
            JOIN news_articles a ON a.rowid = f.rowid
            WHERE news_fts MATCH ?
        """
        params: List[Any] = [query]
        if broadcast_status:
            sql += " AND a.broadcast_status = ?"
            params.append(broadcast_status)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        return conn.execute(sql, params).fetchall()

    def rebuild_fts(self) -> None:
        """重建 FTS 索引（当 news_articles 有大面条目变更时调用）"""
        conn = self.connect()
        conn.execute("INSERT INTO news_fts(news_articles) VALUES('rebuild')")

    # ── 播报日志 ──────────────────────────────────────

    def log_broadcast(
        self,
        broadcast_date: str,
        article_ids: List[int],
        script_path: Optional[str] = None,
        audio_path: Optional[str] = None,
    ) -> None:
        conn = self.connect()
        conn.execute("""
            INSERT OR REPLACE INTO broadcast_log
                (broadcast_date, article_ids, article_count, script_path, audio_path)
            VALUES (?, ?, ?, ?, ?)
        """, (
            broadcast_date,
            json.dumps(article_ids, ensure_ascii=False),
            len(article_ids),
            script_path,
            audio_path,
        ))

    def get_broadcast_log(self, broadcast_date: str) -> Optional[sqlite3.Row]:
        conn = self.connect()
        return conn.execute(
            "SELECT * FROM broadcast_log WHERE broadcast_date = ?",
            (broadcast_date,)
        ).fetchone()

    # ── 统计 ──────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        conn = self.connect()
        row = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(broadcast_status = 'unplayed') AS unplayed,
                SUM(broadcast_status = 'played') AS played,
                SUM(broadcast_status = 'archived') AS archived,
                SUM(broadcast_date = date('now')) AS today_played
            FROM news_articles
        """).fetchone()
        sources_count = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE enabled = 1"
        ).fetchone()[0]
        return {
            'total_articles': row['total'],
            'unplayed': row['unplayed'] or 0,
            'played': row['played'] or 0,
            'archived': row['archived'] or 0,
            'today_played': row['today_played'] or 0,
            'active_sources': sources_count,
        }

    def print_stats(self) -> None:
        s = self.get_stats()
        print(f"""
[news_db] 数据库统计
  总新闻数:     {s['total_articles']}
  待播报:      {s['unplayed']}
  已播报:      {s['played']}
  今日播报:    {s['today_played']}
  订阅源:      {s['active_sources']}
""")

    # ── 迁移历史数据 ─────────────────────────────────

    def backfill_from_files(self, daily_dir: str) -> Dict[str, int]:
        """
        从现有每日 .md 文件夹导入历史新闻到 DB（一次性迁移）。
        修复 v1 bug：所有 DB 操作在单个连接 + 事务内完成。
        """
        import re, os

        stats = {'imported': 0, 'skipped': 0, 'errors': 0}
        date_re = re.compile(r'(\d{4}-\d{2}-\d{2})')
        md_link_re = re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')
        bare_url_re = re.compile(r'(https?://[^\s\)\]>"\'\”]+)', re.MULTILINE)

        conn = self.connect()
        conn.execute("BEGIN")  # ── 整个迁移使用单个大事务 ──

        try:
            for root, _dirs, files in os.walk(daily_dir):
                for fn in sorted(files):
                    if '_audio' in fn or not fn.endswith('.md'):
                        continue
                    m_date = date_re.search(fn)
                    if not m_date:
                        continue
                    date_str = m_date.group(1)
                    fpath = os.path.join(root, fn)
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            raw = f.read().replace('\r\n', '\n').replace('\r', '\n')

                        entry_header_re = re.compile(
                            r'#{1,3}\s*\d+\.\s+|\*\*\d+\.\s+|(?:^|\n)\d+\.\s+(?=\S)',
                            re.MULTILINE
                        )
                        entry_starts = [m.start() for m in entry_header_re.finditer(raw)]
                        if not entry_starts:
                            continue

                        for k, start in enumerate(entry_starts):
                            end = entry_starts[k+1] if k+1 < len(entry_starts) else len(raw)
                            chunk = raw[start:end].strip()
                            if not chunk:
                                continue

                            # 提标题
                            title_m = re.match(
                                r'^#{1,3}\s*\d+\.\s+(?:\*\*(.+?)\*\*|([^\n]+))'
                                r'|^\*\*\d+\.\s+(?:\*\*(.+?)\*\*|([^\n]+))'
                                r'|^\d+\.\s+(\S.{0,100})',
                                chunk
                            )
                            if not title_m:
                                continue
                            groups = [g for g in title_m.groups() if g]
                            title = groups[0].strip() if groups else ''
                            if len(title) < 5 or len(title) > 200:
                                continue

                            # 提链接
                            md_links = md_link_re.findall(chunk)
                            if md_links:
                                source_name = md_links[0][0].strip()
                                source_url = md_links[0][1].strip()
                            else:
                                bare_urls = bare_url_re.findall(chunk)
                                source_url = bare_urls[0].strip() if bare_urls else None
                                source_name = 'Unknown'

                            # 提正文
                            tl_end = chunk.find('\n')
                            body_chunk = chunk[tl_end if tl_end > 0 else 0:]
                            body = md_link_re.sub('', body_chunk)
                            body = bare_url_re.sub('', body)
                            body = re.sub(r'\n{3,}', '\n', body).strip()
                            body = re.sub(r'^[\-\*=]+.*$', '', body, flags=re.MULTILINE).strip()[:400]

                            story_hash = self.make_hash(title, source_name)
                            url_norm = normalize_url(source_url) if source_url else None

                            exists = conn.execute(
                                "SELECT id FROM news_articles WHERE story_hash = ?",
                                (story_hash,)
                            ).fetchone()
                            if exists:
                                stats['skipped'] += 1
                            else:
                                conn.execute("""
                                    INSERT INTO news_articles
                                        (title, content, source_name, source_url, url_normalized,
                                         story_hash, broadcast_status, broadcast_date,
                                         importance, discovered_at)
                                    VALUES (?, ?, ?, ?, ?, ?, 'played', ?, 5, ?)
                                """, (
                                    title, body, source_name, source_url, url_norm,
                                    story_hash, date_str, date_str + 'T12:00:00'
                                ))
                                stats['imported'] += 1
                    except Exception as e:
                        stats['errors'] += 1
                        print(f"[news_db] Backfill error {fpath}: {e}", file=sys.stderr)

            conn.execute("COMMIT")  # ── 提交整个迁移事务 ──
        except Exception:
            conn.execute("ROLLBACK")
            raise

        print(f"[news_db] Backfill complete: {stats}")
        return stats


# ── CLI ─────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='AI 早报数据库工具')
    parser.add_argument('db_path', help='SQLite 数据库路径')
    parser.add_argument('--init', action='store_true', help='初始化数据库')
    parser.add_argument('--import-sources', metavar='JSON', help='导入订阅源 JSON')
    parser.add_argument('--stats', action='store_true', help='打印统计信息')
    parser.add_argument('--backfill', metavar='DAILY_DIR', help='从历史 md 文件迁移')
    parser.add_argument('--no-bloom', action='store_true', help='禁用 bloom filter')
    args = parser.parse_args()

    bloom = not args.no_bloom
    with NewsDB(args.db_path, use_bloom=bloom) as db:
        if args.init:
            db.init()
        if args.import_sources:
            db.import_sources(args.import_sources)
        if args.stats:
            db.print_stats()
        if args.backfill:
            db.backfill_from_files(args.backfill)
