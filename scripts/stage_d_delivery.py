#!/usr/bin/env python3
"""Thin shim → daily-news-engine shared Stage D delivery controller.

The deterministic Discord delivery (prepare/send/record/clear) lives in ONE
place now (daily-news-engine/daily_news_engine/stage_d_delivery.py); this
project's behavior is driven by ../project.json (discord.mode="split", channel,
account → TWO messages: discord_text links + discord_audio with the mp3). Fix
the delivery once, both ai-daily-news and berlin-gastro-news get it.

Crons still call `python3 scripts/stage_d_delivery.py send --date today`
exactly as before — no cron migration needed.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_ROOT = Path(os.environ.get(
    "NEWS_ENGINE_ROOT", "/Users/unclejoe/.openclaw/runtime/daily-news-engine/current"))

os.environ["NEWS_PROJECT_ROOT"] = str(ROOT)
sys.path.insert(0, str(ENGINE_ROOT))

from daily_news_engine.stage_d_delivery import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
