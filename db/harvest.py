#!/usr/bin/env python3
"""
harvest.py — 从订阅源抓取新闻、查重、入库
Fanli | 2026-04-14

用法:
    python3 harvest.py /path/to/news.db /path/to/sources.json

流程:
    1. 读取订阅源清单
    2. 对每个 RSS 源抓取最新条目
    3. 用 story_hash 查重，已存在则跳过
    4. 存入数据库
    5. 输出统计

依赖: feedparser (pip install feedparser)
"""

import sys
import os
import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# 路径设置
DB_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DB_DIR)
from news_db import NewsDB


# ── RSS 抓取 ─────────────────────────────────────────────

try:
    import feedparser
    FEEDPARSER_OK = True
except ImportError:
    FEEDPARSER_OK = False
    print("[harvest] feedparser not installed. Run: pip install feedparser", file=sys.stderr)


def fetch_rss(url: str, source_name: str, source_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """抓取单个 RSS 源，返回标准化的文章列表"""
    if not FEEDPARSER_OK:
        return []

    articles = []
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            print(f"[harvest] ⚠ {source_name}: feed bozo (possibly malformed), entries: {len(feed.entries)}", file=sys.stderr)

        for entry in feed.entries[:20]:  # 最多取最新 20 条
            title = (entry.get('title') or '').strip()
            if not title:
                continue

            # 摘要/内容
            content = ''
            if hasattr(entry, 'summary'):
                content = strip_tags(entry.summary)
            elif hasattr(entry, 'content') and entry.content:
                content = strip_tags(entry.content[0].value)
            content = content[:500].strip()  # 截断

            # 发布时间
            published_at = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    from time import mktime
                    dt = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
                    published_at = dt.isoformat()
                except Exception:
                    pass
            elif hasattr(entry, 'published'):
                published_at = entry.published

            # 文章链接
            url_ = None
            if hasattr(entry, 'link'):
                url_ = entry.link
            elif hasattr(entry, 'id'):
                url_ = entry.id

            # 来源
            feed_source = getattr(entry, 'author_detail', None)
            author = None
            if feed_source and hasattr(feed_source, 'name'):
                author = feed_source.name

            # 重要性评分（关键词匹配）
            importance = score_importance(title, content)

            # 提取标签
            tags = extract_tags(entry)

            articles.append({
                'title': title,
                'content': content,
                'source_name': source_name,
                'source_id': source_id,
                'source_url': url_,
                'published_at': published_at,
                'importance': importance,
                'tags': tags,        # → 传入 add_articles → topic_tags JSON
            })

    except Exception as e:
        print(f"[harvest] ❌ {source_name}: {e}", file=sys.stderr)

    return articles


def strip_tags(html: str) -> str:
    """移除 HTML 标签"""
    return re.sub(r'<[^>]+>', '', html).strip()


def score_importance(title: str, content: str) -> int:
    """
    基于关键词对文章进行重要性评分 0-10。
    只做启发式评估，不做绝对判断。
    """
    score = 5  # 基准分
    text = (title + ' ' + content).lower()

    boost_keywords = [
        'launch', 'release', 'announce', 'launches', 'releases', 'announced',
        ' debut', 'unveils', 'debuts', 'introduces', 'breaking',
        ' acquires ', 'acquisition', 'acquired', 'acquires',
        ' raises ', 'funding', 'invests', 'investment', 'series ',
        'opens', 'opensource', 'open-source', 'open source',
        'beta', 'preview', 'research', 'breakthrough', 'discovered',
        'cvss', 'vulnerability', 'exploit', 'security flaw',
        'ceo', 'cto', 'founder', 'president', 'dario', 'sam altman',
        'partnership', 'collaboration', 'deal',
    ]
    for kw in boost_keywords:
        if kw in text:
            score += 0.5

    # 品牌词加权
    brand_boost = [
        'anthropic', 'claude', 'openai', 'gpt', 'google deepmind',
        'gemini', 'meta ai', 'llama', 'mistral', 'deepseek',
        'openclaw', 'nvidia', 'microsoft copilot', 'apple ai',
    ]
    for brand in brand_boost:
        if brand in text:
            score += 1

    return min(int(score), 10)


def extract_tags(entry) -> List[str]:
    """从 entry 的 tags 字段提取标签"""
    tags = []
    if hasattr(entry, 'tags'):
        for t in entry.tags:
            label = (t.get('term') or t.get('label') or '').strip()
            if label and len(label) < 40:
                tags.append(label.lower())
    return list(set(tags))[:8]  # 去重，最多 8 个


# ── 主流程 ──────────────────────────────────────────────

def harvest(db: NewsDB, sources_path: str, dry_run: bool = False) -> Dict[str, Any]:
    """对所有活跃订阅源执行抓取-去重-入库"""

    # 读取订阅源
    with open(sources_path, 'r', encoding='utf-8') as f:
        sources_list = json.load(f)

    active_sources = [s for s in sources_list if s.get('enabled', True)]

    # 更新数据库中的订阅源记录
    db.import_sources(sources_path)
    db_sources = {row['url']: row for row in db.get_active_sources()}

    total_new = 0
    total_dup = 0
    errors = []

    for src in active_sources:
        url = src['url']
        name = src['name']
        db_source = db_sources.get(url)

        print(f"[harvest] Fetching: {name} ...", end=' ', flush=True)
        articles = fetch_rss(url, name, source_id=db_source['id'] if db_source else None)
        print(f"→ {len(articles)} entries", flush=True)

        if not articles:
            continue

        # 批量入库（查重在 add_articles 内完成）
        stats = db.add_articles(articles)
        print(f"       new={stats['new']} dup={stats['duplicate']}")

        total_new += stats['new']
        total_dup += stats['duplicate']

        # 更新抓取时间
        if db_source and not dry_run:
            db.update_source_fetched(db_source['id'])

    return {
        'total_new': total_new,
        'total_duplicate': total_dup,
        'sources_processed': len(active_sources),
    }


# ── CLI ─────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='RSS 新闻抓取与入库')
    parser.add_argument('db_path', help='SQLite 数据库路径')
    parser.add_argument('sources_json', help='订阅源 JSON 路径')
    parser.add_argument('--dry-run', action='store_true', help='只抓取不入库')
    args = parser.parse_args()

    if not os.path.exists(args.sources_json):
        print(f"[harvest] Sources JSON not found: {args.sources_json}", file=sys.stderr)
        sys.exit(1)

    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"[harvest] DB not found, creating: {db_path}", file=sys.stderr)
        with NewsDB(db_path) as db:
            db.init()

    with NewsDB(db_path) as db:
        result = harvest(db, args.sources_json, dry_run=args.dry_run)
        print(f"\n[harvest] Done. new={result['total_new']} dup={result['total_duplicate']} "
              f"sources={result['sources_processed']}")
        db.print_stats()
