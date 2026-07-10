#!/usr/bin/env python3
"""Thin shim → daily-news-engine shared Stage B controller.

The token-saving translate gate lives in ONE place now
(daily-news-engine/daily_news_engine/stage_b.py); this project's behavior is
driven by ../project.json (prompt, model, agent; no reconcile_step — ai-news's
translate_helper.finalize marks the pipeline step itself). Fix the gate once,
both ai-daily-news and berlin-gastro-news get it.

Crons still call `python3 scripts/stage_b.py [--date … | --dry-run]` exactly
as before — no cron migration needed.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_ROOT = Path(os.environ.get(
    "NEWS_ENGINE_ROOT", "/Users/unclejoe/.openclaw/runtime/daily-news-engine/current"))

os.environ["NEWS_PROJECT_ROOT"] = str(ROOT)
sys.path.insert(0, str(ENGINE_ROOT))

from daily_news_engine.stage_b import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
