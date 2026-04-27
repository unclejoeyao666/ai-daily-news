-- AI Daily News v2 schema
-- SQLite 3 + FTS5
-- 复刻 berlin-gastro-news v2，针对 AI 领域调整字段语义

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       TEXT NOT NULL UNIQUE,    -- 稳定字符串 ID（来自 sources.json）
    name            TEXT NOT NULL,
    name_cn         TEXT,
    feed_url        TEXT NOT NULL,
    type            TEXT NOT NULL DEFAULT 'rss',
    lang            TEXT NOT NULL DEFAULT 'en',
    tier            INTEGER NOT NULL DEFAULT 2,
    categories      TEXT,                    -- JSON array
    enabled         INTEGER NOT NULL DEFAULT 1,
    last_fetched    TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS news_articles (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    title                    TEXT NOT NULL,
    summary                  TEXT,
    content                  TEXT,
    source_id                TEXT REFERENCES sources(source_id) ON DELETE SET NULL,
    source_name              TEXT NOT NULL,
    source_name_cn           TEXT,
    source_url               TEXT,
    url_normalized           TEXT,
    published_at             TEXT,
    discovered_at            TEXT NOT NULL DEFAULT (datetime('now')),
    story_hash               TEXT NOT NULL,
    lang                     TEXT NOT NULL DEFAULT 'en',
    source_categories        TEXT,                  -- JSON array (from sources.json)
    importance               INTEGER NOT NULL DEFAULT 0,
    broadcast_status         TEXT NOT NULL DEFAULT 'unplayed',  -- unplayed/played/archived
    broadcast_date           TEXT,

    -- v2 additions: translation + tagging + slug
    translated_title         TEXT,
    translated_summary       TEXT,
    translated_body          TEXT,
    impact_analysis          TEXT,
    industry_tags            TEXT,                  -- JSON array of tag slugs
    slug                     TEXT,
    published_briefing_date  TEXT,

    raw_json                 TEXT,
    -- v1 残留字段（保留兼容）
    topic_tags               TEXT,
    author                   TEXT,
    CONSTRAINT uq_story_hash UNIQUE (story_hash)
);

CREATE VIRTUAL TABLE IF NOT EXISTS news_fts USING fts5(
    title,
    summary,
    content,
    translated_title,
    translated_body,
    impact_analysis,
    content='news_articles',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 1'
);

CREATE TRIGGER IF NOT EXISTS news_articles_ai AFTER INSERT ON news_articles BEGIN
    INSERT INTO news_fts(rowid, title, summary, content, translated_title, translated_body, impact_analysis)
    VALUES (new.id, new.title, new.summary, new.content, new.translated_title, new.translated_body, new.impact_analysis);
END;

CREATE TRIGGER IF NOT EXISTS news_articles_ad AFTER DELETE ON news_articles BEGIN
    INSERT INTO news_fts(news_fts, rowid, title, summary, content, translated_title, translated_body, impact_analysis)
    VALUES ('delete', old.id, old.title, old.summary, old.content, old.translated_title, old.translated_body, old.impact_analysis);
END;

CREATE TRIGGER IF NOT EXISTS news_articles_au AFTER UPDATE ON news_articles BEGIN
    INSERT INTO news_fts(news_fts, rowid, title, summary, content, translated_title, translated_body, impact_analysis)
    VALUES ('delete', old.id, old.title, old.summary, old.content, old.translated_title, old.translated_body, old.impact_analysis);
    INSERT INTO news_fts(rowid, title, summary, content, translated_title, translated_body, impact_analysis)
    VALUES (new.id, new.title, new.summary, new.content, new.translated_title, new.translated_body, new.impact_analysis);
END;

CREATE TABLE IF NOT EXISTS broadcast_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    broadcast_date  TEXT NOT NULL UNIQUE,
    article_ids     TEXT NOT NULL,
    article_count   INTEGER NOT NULL DEFAULT 0,
    briefing_url    TEXT,
    audio_url       TEXT,
    audio_path      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_articles_status ON news_articles(broadcast_status);
CREATE INDEX IF NOT EXISTS idx_articles_hash ON news_articles(story_hash);
CREATE INDEX IF NOT EXISTS idx_articles_pub ON news_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_disc ON news_articles(discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_unplayed_queue
    ON news_articles(broadcast_status, importance DESC, discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_url_norm
    ON news_articles(url_normalized) WHERE url_normalized IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_slug
    ON news_articles(slug) WHERE slug IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_articles_briefing
    ON news_articles(published_briefing_date) WHERE published_briefing_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sources_enabled ON sources(enabled);

PRAGMA user_version = 2;
