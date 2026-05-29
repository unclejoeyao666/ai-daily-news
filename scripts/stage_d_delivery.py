#!/usr/bin/env python3
"""Prepare and record Stage D Discord deliveries.

This script deliberately does not send Discord messages. OpenClaw's message
tool is only available in agent sessions, so Stage D uses this helper to make
all non-network work deterministic:

1. validate the daily pipeline state
2. build the exact Discord payloads
3. copy the mp3 into OpenClaw's allow-listed media directory
4. record a delivery only after the agent provides a real Discord message id
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback only.
    ZoneInfo = None  # type: ignore


PROJECT_ROOT = Path(
    os.environ.get(
        "AI_NEWS_PROJECT_ROOT",
        "/Users/unclejoe/Media_Workspace/ai-daily-news",
    )
)
NEWS_CHANNEL_ID = "1490344209847287830"
NEWS_CHANNEL_TARGET = f"channel:{NEWS_CHANNEL_ID}"
MEDIA_DIR = Path("/Users/unclejoe/.openclaw/media/manual")
DISCORD_CHAR_LIMIT = 1900
OPENCLAW_MEDIA_LIMIT = 8 * 1024 * 1024
DELIVERY_KEYS = ("discord_text", "discord_audio")
INVALID_MESSAGE_IDS = {"", "cron-announce", "unknown", "none", None}


def today_berlin() -> str:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d")
    return datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")


def parse_date(value: str) -> str:
    if not value or value == "today":
        return today_berlin()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise SystemExit(f"bad date: {value}")
    return value


def day_dir(date_str: str) -> Path:
    year, month, _ = date_str.split("-")
    return PROJECT_ROOT / "daily" / year / f"{year}-{month}" / date_str


def state_path(date_str: str) -> Path:
    return day_dir(date_str) / ".state.json"


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".state-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_state(date_str: str) -> dict[str, Any]:
    return load_json(state_path(date_str))


def is_real_message_id(value: Any) -> bool:
    if value in INVALID_MESSAGE_IDS:
        return False
    return bool(re.fullmatch(r"\d{12,25}", str(value)))


def delivery_is_ok(state: dict[str, Any], key: str) -> bool:
    entry = state.get("deliveries", {}).get(key, {})
    return entry.get("status") == "ok" and is_real_message_id(entry.get("message_id"))


def build_text_message(date_str: str, meta: dict[str, Any]) -> str:
    ids = meta.get("article_ids") or []
    if not ids:
        raise SystemExit("meta.article_ids is empty")

    placeholders = ",".join("?" for _ in ids)
    db_path = PROJECT_ROOT / "data" / "news.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = {
            row["id"]: row
            for row in conn.execute(
                f"SELECT id, slug, translated_title FROM news_articles "
                f"WHERE id IN ({placeholders})",
                ids,
            )
        }
    finally:
        conn.close()

    site_base = str(meta.get("site_base") or "https://unclejoeyao666.github.io/ai-daily-news").rstrip("/")
    briefing_url = str(meta["briefing_url"])
    audio_url = str(meta["audio_url"])

    for title_limit in (60, 52, 44, 36, 30):
        lines = [
            f"🤖 **AI 科技每日早报 — {date_str}**",
            "",
            f"🎧 [今日音频]({audio_url}) · 🌐 [完整网页]({briefing_url})",
            "",
        ]
        for index, article_id in enumerate(ids, 1):
            row = rows.get(article_id)
            if row is None:
                continue
            title = (row["translated_title"] or "").strip()
            if len(title) > title_limit:
                title = title[: title_limit - 1].rstrip() + "…"
            url = f"{site_base}/articles/{row['slug']}/"
            lines.append(f"{index}. [{title}]({url})")
        message = "\n".join(lines)
        if len(message) < DISCORD_CHAR_LIMIT:
            return message

    raise SystemExit(f"compact Discord message is still too long: {len(message)} chars")


def prepare(date_str: str, json_out: Path | None) -> dict[str, Any]:
    state = load_state(date_str)
    push_status = state.get("steps", {}).get("push", {}).get("status")
    if push_status != "ok":
        payload = {
            "status": "skip",
            "reason": f"push is {push_status or 'missing'}",
            "date": date_str,
        }
        write_payload(payload, json_out)
        return payload

    needs_text = not delivery_is_ok(state, "discord_text")
    needs_audio = not delivery_is_ok(state, "discord_audio")
    if not needs_text and not needs_audio:
        payload = {
            "status": "complete",
            "reason": "discord_text and discord_audio already have real message ids",
            "date": date_str,
        }
        write_payload(payload, json_out)
        return payload

    dd = day_dir(date_str)
    meta = load_json(dd / "meta.json")
    text_message = build_text_message(date_str, meta)

    audio_src = dd / "audio.mp3"
    if not audio_src.exists():
        raise SystemExit(f"missing audio: {audio_src}")
    mp3_size = audio_src.stat().st_size
    if mp3_size >= OPENCLAW_MEDIA_LIMIT:
        raise SystemExit(
            f"audio too large for OpenClaw media allow-list: {mp3_size} bytes"
        )
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    audio_dest = MEDIA_DIR / f"{date_str}_audio.mp3"
    shutil.copy2(audio_src, audio_dest)

    audio_message = (
        f"🎧 **AI 科技每日早报 · 音频版** — {date_str}\n\n"
        f"📎 在线收听：{meta['audio_url']}\n"
        f"🌐 完整网页：{meta['briefing_url']}"
    )

    payload = {
        "status": "ready",
        "date": date_str,
        "channel": "discord",
        "target": NEWS_CHANNEL_TARGET,
        "deliveries": {
            "discord_text": {
                "needed": needs_text,
                "chars": len(text_message),
                "message": text_message,
            },
            "discord_audio": {
                "needed": needs_audio,
                "message": audio_message,
                "media_path": str(audio_dest),
                "mp3_size": mp3_size,
            },
        },
    }
    write_payload(payload, json_out)
    return payload


def write_payload(payload: dict[str, Any], json_out: Path | None) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    if json_out is not None:
        json_out.write_text(data + "\n", encoding="utf-8")
    print(data)


def record(args: argparse.Namespace) -> int:
    date_str = parse_date(args.date)
    if not is_real_message_id(args.message_id):
        print(f"refusing non-Discord message id: {args.message_id}", file=sys.stderr)
        return 1

    state = load_state(date_str)
    deliveries = state.setdefault("deliveries", {})
    existing = deliveries.get(args.key, {})
    if (
        existing.get("status") == "ok"
        and is_real_message_id(existing.get("message_id"))
        and not args.force
    ):
        print(
            f"delivery {args.key} already recorded with real message id "
            f"{existing.get('message_id')}",
            file=sys.stderr,
        )
        return 2

    entry: dict[str, Any] = {
        "status": "ok",
        "message_id": str(args.message_id),
        "channel_id": NEWS_CHANNEL_ID,
        "method": "openclaw_message",
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    if args.chars is not None:
        entry["chars"] = args.chars
    if args.mp3_size is not None:
        entry["mp3_size"] = args.mp3_size

    deliveries[args.key] = entry
    atomic_write_json(state_path(date_str), state)
    print(json.dumps({"status": "recorded", "date": date_str, "key": args.key, **entry}, ensure_ascii=False))
    return 0


def clear(args: argparse.Namespace) -> int:
    date_str = parse_date(args.date)
    state = load_state(date_str)
    deliveries = state.setdefault("deliveries", {})
    removed: dict[str, Any] = {}
    for key in args.key:
        if key in deliveries:
            removed[key] = deliveries.pop(key)
    atomic_write_json(state_path(date_str), state)
    print(json.dumps({"status": "cleared", "date": date_str, "removed": removed}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_prepare = sub.add_parser("prepare", help="Build exact Stage D payload JSON")
    p_prepare.add_argument("--date", default="today")
    p_prepare.add_argument("--json-out", type=Path, default=None)

    p_record = sub.add_parser("record", help="Record one successful Discord send")
    p_record.add_argument("--date", default="today")
    p_record.add_argument("--key", required=True, choices=DELIVERY_KEYS)
    p_record.add_argument("--message-id", required=True)
    p_record.add_argument("--chars", type=int, default=None)
    p_record.add_argument("--mp3-size", type=int, default=None)
    p_record.add_argument("--force", action="store_true")

    p_clear = sub.add_parser("clear", help="Clear delivery state during operator recovery")
    p_clear.add_argument("--date", default="today")
    p_clear.add_argument("--key", nargs="+", required=True, choices=DELIVERY_KEYS)

    args = parser.parse_args()
    if args.command == "prepare":
        prepare(parse_date(args.date), args.json_out)
        return 0
    if args.command == "record":
        return record(args)
    if args.command == "clear":
        return clear(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    sys.exit(main())
