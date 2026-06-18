#!/usr/bin/env python3
"""Prepare, send, and record Stage D Discord deliveries.

Stage D delivery is fully deterministic. It does NOT require a cognitive agent
turn. The `openclaw message send --json` CLI sends a Discord message (with
optional media) directly through the running Gateway and returns the real
Discord message id, so this helper can:

1. validate the daily pipeline state
2. build the exact Discord payloads
3. copy the mp3 into OpenClaw's allow-listed media directory
4. send each needed delivery via `openclaw message send --json`
5. record a delivery only after a real Discord snowflake message id is returned

Subcommands:
  prepare  build the exact payload JSON (no send)
  send     build, send via openclaw message send, and record (the cron path)
  record   record one delivery from an externally-obtained message id
  clear    clear delivery state during operator recovery
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
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
SEND_TIMEOUT_SECONDS = 300
# Stale-tolerant lock so the Stage D cron (07:00) and the watchdog delivery
# backstop (hourly) can never both post the same briefing. A SIGKILLed run's
# lock ages out after this many seconds.
SEND_LOCK_TTL_SECONDS = 600
# Only the `fanli` Discord bot account has access to the news + management
# channels (guild 1482433009666887967). The CLI default account does not, so
# `openclaw message send` must be told which account to use.
DISCORD_ACCOUNT = os.environ.get("STAGE_D_DISCORD_ACCOUNT", "fanli")


def openclaw_bin() -> str:
    """Resolve the openclaw CLI used to send Discord messages."""
    return (
        os.environ.get("OPENCLAW_BIN")
        or shutil.which("openclaw")
        or "/opt/homebrew/bin/openclaw"
    )


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


def build_payload(date_str: str) -> dict[str, Any]:
    """Build the exact Stage D payload without printing or sending."""
    state = load_state(date_str)
    push_status = state.get("steps", {}).get("push", {}).get("status")
    if push_status != "ok":
        return {
            "status": "skip",
            "reason": f"push is {push_status or 'missing'}",
            "date": date_str,
        }

    needs_text = not delivery_is_ok(state, "discord_text")
    needs_audio = not delivery_is_ok(state, "discord_audio")
    if not needs_text and not needs_audio:
        return {
            "status": "complete",
            "reason": "discord_text and discord_audio already have real message ids",
            "date": date_str,
        }

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

    return {
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


def prepare(date_str: str, json_out: Path | None) -> dict[str, Any]:
    payload = build_payload(date_str)
    write_payload(payload, json_out)
    return payload


def write_payload(payload: dict[str, Any], json_out: Path | None) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    if json_out is not None:
        json_out.write_text(data + "\n", encoding="utf-8")
    print(data)


def record_delivery(
    date_str: str,
    key: str,
    message_id: str,
    *,
    chars: int | None = None,
    mp3_size: int | None = None,
    force: bool = False,
) -> tuple[int, dict[str, Any]]:
    """Record one delivery. Returns (exit_code, entry_or_info)."""
    if not is_real_message_id(message_id):
        return 1, {"error": f"refusing non-Discord message id: {message_id}"}

    state = load_state(date_str)
    deliveries = state.setdefault("deliveries", {})
    existing = deliveries.get(key, {})
    if (
        existing.get("status") == "ok"
        and is_real_message_id(existing.get("message_id"))
        and not force
    ):
        return 2, {
            "error": (
                f"delivery {key} already recorded with real message id "
                f"{existing.get('message_id')}"
            ),
            "message_id": existing.get("message_id"),
        }

    entry: dict[str, Any] = {
        "status": "ok",
        "message_id": str(message_id),
        "channel_id": NEWS_CHANNEL_ID,
        "method": "openclaw_message",
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    if chars is not None:
        entry["chars"] = chars
    if mp3_size is not None:
        entry["mp3_size"] = mp3_size

    deliveries[key] = entry
    atomic_write_json(state_path(date_str), state)
    return 0, entry


def record(args: argparse.Namespace) -> int:
    date_str = parse_date(args.date)
    code, info = record_delivery(
        date_str,
        args.key,
        args.message_id,
        chars=args.chars,
        mp3_size=args.mp3_size,
        force=args.force,
    )
    if code != 0:
        print(info.get("error", "record failed"), file=sys.stderr)
        return code
    print(json.dumps({"status": "recorded", "date": date_str, "key": args.key, **info}, ensure_ascii=False))
    return 0


def find_message_id(obj: Any) -> str | None:
    """Recursively find a real Discord snowflake under a messageId key.

    Only keys explicitly naming a message id are accepted, so a channelId
    (also a snowflake) is never mistaken for the delivered message id.
    """
    if isinstance(obj, dict):
        for key in ("messageId", "message_id", "id"):
            if key in obj and is_real_message_id(obj[key]):
                return str(obj[key])
        for value in obj.values():
            found = find_message_id(value)
            if found:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find_message_id(value)
            if found:
                return found
    return None


def parse_send_stdout(stdout: str) -> dict[str, Any] | None:
    """Parse the JSON object emitted by `openclaw message send --json`."""
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
    return None


def send_discord(target: str, message: str, media: str | None, dry_run: bool) -> str | None:
    """Send one Discord message via the openclaw CLI.

    Returns the real Discord message id on success, or None on a dry run.
    Raises SystemExit (loudly) on any failure so no delivery is recorded.
    """
    cmd = [
        openclaw_bin(),
        "message",
        "send",
        "--channel",
        "discord",
        "--account",
        DISCORD_ACCOUNT,
        "--target",
        target,
        "--message",
        message,
        "--json",
    ]
    if media:
        cmd += ["--media", media]
    if dry_run:
        cmd += ["--dry-run"]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SEND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(f"openclaw message send timed out after {SEND_TIMEOUT_SECONDS}s")

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"openclaw message send failed (rc={proc.returncode}): {detail}")

    if dry_run:
        return None

    result = parse_send_stdout(proc.stdout)
    message_id = find_message_id(result) if result is not None else None
    if not message_id:
        raise SystemExit(
            "openclaw message send returned no real Discord message id: "
            f"{proc.stdout.strip()[:500]}"
        )
    return message_id


def _acquire_send_lock(date_str: str) -> Path | None:
    """Return the lock path if acquired, or None if a fresh lock is held."""
    dd = day_dir(date_str)
    dd.mkdir(parents=True, exist_ok=True)
    lock = dd / ".stage_d.lock"
    if lock.exists():
        age = datetime.now(timezone.utc).timestamp() - lock.stat().st_mtime
        if age < SEND_LOCK_TTL_SECONDS:
            return None
    lock.write_text(
        f"{os.getpid()} {datetime.now(timezone.utc).isoformat()}\n",
        encoding="utf-8",
    )
    return lock


def send(args: argparse.Namespace) -> int:
    """Build payloads, send each needed delivery, and record the message ids.

    Deterministic, single-shot per delivery, idempotent across runs. On any
    send failure it exits non-zero without recording a partial success. A
    stale-tolerant lock serializes concurrent senders (Stage D cron vs the
    watchdog backstop) so a briefing can never be double-posted.
    """
    date_str = parse_date(args.date)
    payload = build_payload(date_str)
    status = payload.get("status")
    if status in ("skip", "complete"):
        print(json.dumps({"status": status, "date": date_str, "reason": payload.get("reason"), "sent": []}, ensure_ascii=False))
        return 0
    if status != "ready":
        raise SystemExit(f"unexpected prepare status: {status}")

    lock = None
    if not args.dry_run:
        lock = _acquire_send_lock(date_str)
        if lock is None:
            print(json.dumps({"status": "skip", "date": date_str,
                              "reason": "another Stage D send in flight (lock held)",
                              "sent": []}, ensure_ascii=False))
            return 0
    try:
        return _send_locked(date_str, payload, args.dry_run)
    finally:
        if lock is not None:
            try:
                lock.unlink()
            except FileNotFoundError:
                pass


def _send_locked(date_str: str, payload: dict[str, Any], dry_run: bool) -> int:
    target = payload["target"]
    deliveries = payload["deliveries"]
    results: list[dict[str, Any]] = []

    text = deliveries["discord_text"]
    if text.get("needed"):
        message_id = send_discord(target, text["message"], None, dry_run)
        if dry_run:
            results.append({"key": "discord_text", "dryRun": True})
        else:
            code, info = record_delivery(date_str, "discord_text", message_id, chars=text.get("chars"))
            if code not in (0, 2):
                raise SystemExit(f"failed to record discord_text: {info.get('error')}")
            results.append({"key": "discord_text", "message_id": message_id, "recorded": code == 0})

    audio = deliveries["discord_audio"]
    if audio.get("needed"):
        message_id = send_discord(target, audio["message"], audio.get("media_path"), dry_run)
        if dry_run:
            results.append({"key": "discord_audio", "dryRun": True})
        else:
            code, info = record_delivery(date_str, "discord_audio", message_id, mp3_size=audio.get("mp3_size"))
            if code not in (0, 2):
                raise SystemExit(f"failed to record discord_audio: {info.get('error')}")
            results.append({"key": "discord_audio", "message_id": message_id, "recorded": code == 0})

    print(json.dumps({"status": "sent" if not dry_run else "dry-run", "date": date_str, "results": results}, ensure_ascii=False))
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

    p_send = sub.add_parser("send", help="Build, send via openclaw, and record (deterministic, no agent)")
    p_send.add_argument("--date", default="today")
    p_send.add_argument("--dry-run", action="store_true", help="Build and call openclaw with --dry-run; record nothing")

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
    if args.command == "send":
        return send(args)
    if args.command == "record":
        return record(args)
    if args.command == "clear":
        return clear(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    sys.exit(main())
