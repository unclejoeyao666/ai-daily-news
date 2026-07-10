#!/usr/bin/env python3
"""Thin shim to the safe shared daily-news Git publisher."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_ROOT = Path(os.environ.get(
    "NEWS_ENGINE_ROOT", "/Users/unclejoe/.openclaw/runtime/daily-news-engine/current"))
os.environ["NEWS_PROJECT_ROOT"] = str(ROOT)
sys.path.insert(0, str(ENGINE_ROOT))

from daily_news_engine.git_publish import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
