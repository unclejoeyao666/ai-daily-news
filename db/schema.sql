-- AI 科技早报数据库 schema v2
-- SQLite 3
-- v2 新增：复合索引、FTS5、url_normalized、author、bloom filter 支持

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- 新闻来源订阅表
CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    url             TEXT NOT NULL UNIQUE,
    type            TEXT NOT NULL DEFAULT 'rss',
    category        TEXT NOT NULL DEFAULT 'general',
    language        TEXT NOT NULL DEFAULT 'en',
    enabled         INTEGER NOT NULL DEFAULT 1,
    last_fetched    TEXT,
    fetch_interval  INTEGER NOT NULL DEFAULT 1440,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    CONSTRAINT uq_source_url UNIQUE (url)
);

-- 新闻文章主表
CREATE TABLE IF NOT EXISTS news_articles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    content          TEXT,
    source_id        INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    source_name      TEXT NOT NULL,
    source_url       TEXT,
    url_normalized   TEXT,    -- 归一化 URL（含 tracking 参数去除），用于跨源查重
    published_at     TEXT,
    discovered_at    TEXT NOT NULL DEFAULT (datetime('now')),
    story_hash       TEXT NOT NULL,   -- SHA256(title || source_name)，唯一约束
    broadcast_status TEXT NOT NULL DEFAULT 'unplayed',  -- unplayed / played / archived
    broadcast_date   TEXT,
    importance       INTEGER NOT NULL DEFAULT 0,  -- 0-10
    topic_tags       TEXT,   -- JSON 数组
    author           TEXT,   -- RSS entry author (v2 新增)
    raw_json         TEXT,   -- 原始条目 JSON
    CONSTRAINT uq_story_hash UNIQUE (story_hash)
);

-- FTS5 全文搜索虚拟表（title + content）
CREATE VIRTUAL TABLE IF NOT EXISTS news_fts USING fts5(
    title,
    content,
    content='news_articles',     -- 关联主表
    content_rowid='id',          -- 主表 rowid 映射
    tokenize='unicode61 remove_diacritics 1'
);

-- 触发器：自动同步 news_articles 的 FTS 索引
CREATE TRIGGER IF NOT EXISTS news_articles_ai AFTER INSERT ON news_articles BEGIN
    INSERT INTO news_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS news_articles_ad AFTER DELETE ON news_articles BEGIN
    INSERT INTO news_fts(news_fts, rowid, title, content)
    VALUES ('delete', old.id, old.title, old.content);
END;

CREATE TRIGGER IF NOT EXISTS news_articles_au AFTER UPDATE ON news_articles BEGIN
    INSERT INTO news_fts(news_fts, rowid, title, content)
    VALUES ('delete', old.id, old.title, old.content);
    INSERT INTO news_fts(rowid, title, content)
    VALUES (new.id, new.title, new.content);
END;

-- 每日播报日志表
CREATE TABLE IF NOT EXISTS broadcast_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    broadcast_date   TEXT NOT NULL UNIQUE,
    article_ids     TEXT NOT NULL,   -- JSON 数组
    article_count   INTEGER NOT NULL DEFAULT 0,
    script_path     TEXT,
    audio_path      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 索引
-- 1. 播放状态（已有）
CREATE INDEX IF NOT EXISTS idx_articles_status ON news_articles(broadcast_status);

-- 2. story_hash 精确查重（已有）
CREATE INDEX IF NOT EXISTS idx_articles_hash ON news_articles(story_hash);

-- 3. 发布时间排序（已有）
CREATE INDEX IF NOT EXISTS idx_articles_date ON news_articles(published_at DESC);

-- 4. 入库时间排序（已有）
CREATE INDEX IF NOT EXISTS idx_articles_discovery ON news_articles(discovered_at DESC);

-- 5. 🔑 复合索引：消除 get_unplayed_articles 的 filesort（v2 新增）
--    覆盖 WHERE broadcast_status = 'unplayed' + ORDER BY importance DESC, discovered_at DESC
--    SQLite 可以只用这个索引完成整个查询，无需 tempfile sort
CREATE INDEX IF NOT EXISTS idx_articles_unplayed_queue
    ON news_articles(broadcast_status, importance DESC, discovered_at DESC);

-- 6. url_normalized 快速查重（v2 新增）
CREATE INDEX IF NOT EXISTS idx_articles_url_norm
    ON news_articles(url_normalized) WHERE url_normalized IS NOT NULL;

-- 7. 订阅源启用状态（已有）
CREATE INDEX IF NOT EXISTS idx_sources_enabled ON sources(enabled);
