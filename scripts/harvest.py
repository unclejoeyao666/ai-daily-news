#!/usr/bin/env python3
"""Thin shim → daily-news-engine shared harvest.

The RSS harvest logic lives in ONE place now
(daily-news-engine/daily_news_engine/harvest.py). This project's behavior is
driven by ../project.json (harvest.scorer="keyword_boosts" + AI keyword/
category weights). Fix the harvester once, both ai-daily-news and
berlin-gastro-news get it.

Crons still call `python3 scripts/harvest.py` exactly as before — no cron
migration needed. Importing this module (e.g. `from scripts import harvest`)
also works and exposes the engine module's `main`.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_ROOT = Path(os.environ.get(
    "NEWS_ENGINE_ROOT", "/Users/unclejoe/Media_Workspace/daily-news-engine"))

os.environ["NEWS_PROJECT_ROOT"] = str(ROOT)
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from daily_news_engine.harvest import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
