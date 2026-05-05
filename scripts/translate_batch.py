#!/usr/bin/env python3
"""AI translation step for daily news briefing.

Reads today's selected articles from daily-selected.json,
translates them via OpenAI API, updates DB, and writes
audio_script.md + briefing.md to the date's day directory.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.lib.news_db import NewsDB

ROOT = Path("/Users/unclejoe/Media_Workspace/ai-daily-news")
DB_PATH = ROOT / "data" / "news.db"
SELECTED_JSON = ROOT / "daily-selected.json"
TAGS_JSON = ROOT / "data" / "tags.json"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


# ─── Tag mapping ─────────────────────────────────────────────────────────────

SOURCE_CATEGORY_MAP = {
    "ai-research": "research-paper",
    "research": "research-paper",
    "paper": "research-paper",
    "model-release": "model-release",
    "model": "model-release",
    "models": "model-release",
    "funding": "funding-ipo",
    "ipo": "funding-ipo",
    "funding-ipo": "funding-ipo",
    "policy": "policy-regulation",
    "regulation": "policy-regulation",
    "policy-regulation": "policy-regulation",
    "chips": "chips-infra",
    "chip": "chips-infra",
    "infra": "chips-infra",
    "chips-infra": "chips-infra",
    "agent": "agent-tools",
    "agents": "agent-tools",
    "agent-tools": "agent-tools",
    "tools": "agent-tools",
    "enterprise": "enterprise-app",
    "enterprise-app": "enterprise-app",
    "consumer": "consumer-app",
    "consumer-app": "consumer-app",
    "open-source": "open-source",
    "open_source": "open-source",
    "safety": "safety-alignment",
    "safety-alignment": "safety-alignment",
    "alignment": "safety-alignment",
    "china": "china-ai",
    "china-ai": "china-ai",
    "chinese": "china-ai",
    "trend": "industry-trend",
    "industry-trend": "industry-trend",
    "industry": "industry-trend",
}


def load_valid_tags() -> set:
    with open(TAGS_JSON, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return {t["slug"] for t in cfg["tags"]}


def map_source_categories(categories: List[str], valid_tags: set) -> List[str]:
    """Map RSS source_categories to valid industry_tags."""
    result = []
    for cat in categories:
        cat_lower = cat.lower()
        mapped = SOURCE_CATEGORY_MAP.get(cat_lower, cat_lower)
        if mapped in valid_tags:
            result.append(mapped)
        elif cat_lower in valid_tags:
            result.append(cat_lower)
    # Always include at least one broad tag
    if not result:
        result = ["industry-trend"]
    return list(dict.fromkeys(result))  # deduplicate preserve order


# ─── Slug generation ─────────────────────────────────────────────────────────

def slugify(text: str, max_len: int = 50) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s\-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len].rstrip("-")


def make_slug(row: dict, valid_tags: set) -> str:
    """Build slug from English title + date suffix."""
    pub = (row.get("published_at") or "")[:10]
    base = slugify(row.get("title") or "")
    if not base:
        url = row.get("source_url") or ""
        base = slugify(url.rstrip("/").rsplit("/", 1)[-1])[:30] or "article"
    base_max = 60 - len(pub) - 1
    return f"{base[:base_max].rstrip('-')}-{pub}"


# ─── OpenAI translation ───────────────────────────────────────────────────────

def translate_with_openai(
    title: str,
    summary: str,
    source_name: str,
    importance: int,
) -> dict:
    """Call OpenAI to translate an article into Chinese with impact analysis."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    system_prompt = (
        "You are a professional AI-industry news translator and analyst. "
        "Translate the following article fields into Chinese (Simplified Chinese, using Mainland Chinese conventions). "
        "Also write a concise impact analysis for the AI industry. "
        "Return ONLY a valid JSON object with these exact fields:\n"
        "{\n"
        '  "translated_title": "...",\n'
        '  "translated_summary": "...",\n'
        '  "impact_analysis": "..."\n'
        "}\n"
        "Rules:\n"
        "- translated_title: 10-30 Chinese characters, catchy and accurate\n"
        "- translated_summary: 50-100 Chinese characters, maintain key facts and numbers\n"
        "- impact_analysis: 80-150 Chinese characters, explain why this matters to the AI industry"
    )

    user_prompt = (
        f"Source: {source_name} | Importance score: {importance}\n"
        f"Title: {title}\n"
        f"Summary: {summary}"
    )

    import urllib.request

    payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 500,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    content = result["choices"][0]["message"]["content"]
    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = content.rstrip("`")

    return json.loads(content)


# ─── Audio script & briefing generators ──────────────────────────────────────

def num_to_cn(n: str) -> str:
    mapping = {
        '0': '零', '1': '一', '2': '二', '3': '三', '4': '四',
        '5': '五', '6': '六', '7': '七', '8': '八', '9': '九',
    }
    return ''.join(mapping.get(c, c) for c in n)


def format_date_cn(date_str: str) -> str:
    y, m, d = date_str.split('-')
    return f"{num_to_cn(y)}年{num_to_cn(m.lstrip('0'))}月{num_to_cn(d.lstrip('0'))}日"


def build_audio_script(articles: list, date_cn: str) -> str:
    """Build audio script from translated articles list."""
    lines = []
    lines.append(
        f"各位好，欢迎收听{date_cn}AI科技早报。今天的音频节目将为您带来"
        f"{num_to_cn(str(len(articles)))}条重要资讯，涵盖模型发布、融资动态、"
        "行业合作与技术创新。\n"
    )
    for i, a in enumerate(articles, 1):
        ordinal = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"][i - 1]
        lines.append(f"\n【头条{ordinal}】{a['translated_title']}")
        lines.append(a["translated_summary"])
        lines.append("\n" + a.get("impact_analysis", ""))
    lines.append(f"\n以上就是{date_cn}AI科技早报全部内容，感谢收听，我们明天再见。")
    return '\n'.join(lines)


def build_briefing_md(articles: list, date_str: str) -> str:
    """Build briefing markdown from translated articles list."""
    lines = []
    lines.append(f"# 🗞️ AI 科技早报 — {date_str}\n")
    lines.append("来源：TechCrunch AI、彭博科技  |  AI翻译驱动\n")
    lines.append("---\n")
    for i, a in enumerate(articles, 1):
        importance = a.get("importance", "")
        importance_bar = "▓" * (importance // 20) + "░" * (5 - importance // 20) if importance else "░" * 5
        lines.append(f"### {i}. {a['translated_title']}")
        lines.append(f"**来源：** {a.get('source_name_cn', a.get('source_name', ''))}  |  "
                     f"**重要性：** {importance_bar} ({importance}/100)\n")
        lines.append(f"{a['translated_summary']}\n")
        impact = a.get("impact_analysis", "")
        if impact:
            lines.append(f"**影响分析：** {impact}\n")
        tags = a.get("industry_tags", [])
        if tags:
            tag_str = ', '.join(f'`{t}`' for t in tags)
            lines.append(f"**标签：** {tag_str}\n")
        lines.append("---\n")
    lines.append("*由 Fanli AI 驱动 | OpenClaw 认知工作流自动生成*")
    return '\n'.join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def day_dir_for(date_str: str) -> Path:
    year, month, _ = date_str.split("-")
    return ROOT / "daily" / year / f"{year}-{month}" / date_str


def main():
    parser = argparse.ArgumentParser(description="Translate and publish daily AI news")
    parser.add_argument("--date", default="today", help="Date string YYYY-MM-DD")
    args = parser.parse_args()

    if args.date == "today":
        date_str = date.today().isoformat()
    else:
        date_str = args.date

    date_cn = format_date_cn(date_str)
    ARCHIVE_DIR = day_dir_for(date_str)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"📅 Processing {date_str} ({date_cn})")

    # Load selected articles
    if not SELECTED_JSON.exists():
        print(f"❌ daily-selected.json not found at {SELECTED_JSON}")
        sys.exit(1)

    selected = json.loads(SELECTED_JSON.read_text(encoding="utf-8"))
    articles = selected.get("articles", [])
    if not articles:
        print("⚠️  No articles in daily-selected.json")
        sys.exit(0)

    print(f"📂 {len(articles)} selected articles")

    valid_tags = load_valid_tags()
    translated_articles = []

    # Translate each article
    for a in articles:
        aid = a["id"]
        title = a.get("title", "")
        summary = a.get("summary", "")
        source_name = a.get("source_name", "")
        source_name_cn = a.get("source_name_cn", source_name)
        importance = a.get("importance", 50)
        source_categories = a.get("source_categories", [])

        print(f"  Translating {aid}: {title[:50]}...", end=" ", flush=True)
        try:
            result = translate_with_openai(title, summary, source_name, importance)
        except Exception as e:
            print(f"⚠️  translation failed: {e}")
            # Fallback: use English as placeholder
            result = {
                "translated_title": title,
                "translated_summary": summary,
                "impact_analysis": "",
            }

        # Map categories to valid industry_tags
        industry_tags = map_source_categories(source_categories, valid_tags)

        # Build slug
        row_dict = {
            "title": title,
            "published_at": a.get("published_at", ""),
            "source_url": a.get("source_url", ""),
        }
        slug = make_slug(row_dict, valid_tags)

        translated_a = {
            **a,
            "translated_title": result["translated_title"],
            "translated_summary": result["translated_summary"],
            "translated_body": summary,  # use summary as body proxy
            "impact_analysis": result.get("impact_analysis", ""),
            "industry_tags": industry_tags,
            "slug": slug,
            "source_name_cn": source_name_cn,
        }
        translated_articles.append(translated_a)

        # Update DB
        with NewsDB(str(DB_PATH)) as db:
            db.update_translation(
                article_id=aid,
                translated_title=result["translated_title"],
                translated_summary=result["translated_summary"],
                translated_body=summary,
                impact_analysis=result.get("impact_analysis", ""),
                industry_tags=industry_tags,
                slug=slug,
            )
        print(f"✅ slug={slug}")

    # Write audio script
    audio_script = build_audio_script(translated_articles, date_cn)
    audio_path = ARCHIVE_DIR / "audio_script.md"
    audio_path.write_text(audio_script, encoding="utf-8")
    print(f"✅ audio_script.md → {audio_path}")

    # Write briefing markdown
    briefing_md = build_briefing_md(translated_articles, date_str)
    briefing_path = ARCHIVE_DIR / "briefing.md"
    briefing_path.write_text(briefing_md, encoding="utf-8")
    print(f"✅ briefing.md → {briefing_path}")

    print(f"\n✅ All done. Proceed to steps 4-7.")


if __name__ == "__main__":
    main()
