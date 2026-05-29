"""Daily pipeline state file (daily/<date>/.state.json).

Each step writes its own block — the orchestrator decides what to run
based on the recorded status and finished_at timestamps. The file is
small and human-editable, so a stuck pipeline can be unstuck by hand.

Writes use a temp file + os.replace so a SIGKILL mid-write can't leave
a half-written .state.json — the next wake-up reads the previous
coherent state.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

STEPS = [
    "harvest",
    "select",
    "translate",
    "publish_article",
    "publish_brief",
    "audio",
    "push",
]

STEP_LABELS = {
    "harvest": "RSS 抓取",
    "select": "精选 10 篇",
    "translate": "AI 翻译",
    "publish_article": "发布文章",
    "publish_brief": "生成简报",
    "audio": "TTS 音频",
    "push": "GitHub 推送",
}


def empty_state(date_str: str) -> Dict[str, Any]:
    return {
        "date": date_str,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "steps": {s: {"status": "pending"} for s in STEPS},
    }


def load(state_path: Path, date_str: str) -> Dict[str, Any]:
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = empty_state(date_str)
        # Forward-compat: ensure all known steps exist.
        for s in STEPS:
            data.setdefault("steps", {}).setdefault(s, {"status": "pending"})
        data["date"] = date_str
        return data
    return empty_state(date_str)


def save(state_path: Path, state: Dict[str, Any]) -> None:
    """Atomic write — temp file in same dir, then rename."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".state-", dir=str(state_path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, state_path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def reset_running(state: Dict[str, Any]) -> List[str]:
    """Demote any 'running' steps back to 'pending'.

    Returns the list of step names that were reset. Use this on load
    if you want the next run to redo a step that was interrupted
    mid-flight.
    """
    reset: List[str] = []
    for step, block in state.get("steps", {}).items():
        if block.get("status") == "running":
            reset.append(step)
            block["status"] = "pending"
            block.pop("started_at", None)
    return reset


def mark(state: Dict[str, Any], step: str, status: str,
         **extra) -> Dict[str, Any]:
    """Set step status. Status: pending | running | ok | failed | skipped."""
    block: Dict[str, Any] = {"status": status}
    if status in ("ok", "failed", "skipped"):
        block["finished_at"] = datetime.now(timezone.utc).isoformat()
    elif status == "running":
        block["started_at"] = datetime.now(timezone.utc).isoformat()
    block.update(extra)
    state.setdefault("steps", {})[step] = block
    return state


def get(state: Dict[str, Any], step: str) -> Dict[str, Any]:
    return state.get("steps", {}).get(step, {"status": "pending"})


def is_done(state: Dict[str, Any], step: str) -> bool:
    return get(state, step).get("status") == "ok"


DELIVERY_KEYS = ("discord_text", "discord_audio")


def is_real_delivery_id(value: Any) -> bool:
    """True for a real Discord snowflake, false for cron placeholders."""
    if value in (None, "", "cron-announce", "unknown", "none"):
        return False
    s = str(value)
    return s.isdigit() and 12 <= len(s) <= 25


def is_delivery_done(state: Dict[str, Any], key: str) -> bool:
    block = state.get("deliveries", {}).get(key, {})
    return (
        block.get("status") == "ok"
        and is_real_delivery_id(block.get("message_id"))
    )


def is_complete(state: Dict[str, Any]) -> bool:
    """True when every required step AND both deliveries are ok.

    Used by daily_wake.py to short-circuit watchdog runs and by
    health.py to compute the green/red verdict.
    """
    if not all(is_done(state, s) for s in STEPS):
        return False
    return all(is_delivery_done(state, k) for k in DELIVERY_KEYS)


def mark_started(state: Dict[str, Any], step: str, **extra) -> Dict[str, Any]:
    """Convenience: write status='running' with started_at.

    Equivalent to mark(state, step, 'running', **extra) — exposed as a
    named entry point so callers explicitly distinguish 'I'm starting'
    from 'I'm running' and never silently skip the start mark.
    """
    return mark(state, step, "running", **extra)


def has_running_step(state: Dict[str, Any]) -> Optional[str]:
    """Return the first step in 'running' state, or None.

    Watchdog uses this to defer when a stage cron is mid-flight, to
    avoid two processes advancing the same .state.json concurrently.
    """
    for s in STEPS:
        if get(state, s).get("status") == "running":
            return s
    return None


def next_pending(state: Dict[str, Any],
                 from_step: Optional[str] = None) -> Optional[str]:
    """First step that isn't 'ok'. from_step skips ahead."""
    started = from_step is None
    for s in STEPS:
        if not started:
            started = (s == from_step)
            if not started:
                continue
        if not is_done(state, s):
            return s
    return None
