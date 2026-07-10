#!/usr/bin/env python3
"""Thin shim → daily-news-engine shared select_top.

Selection logic for BOTH projects lives in ONE place now
(daily-news-engine/daily_news_engine/select_top.py). This project's behavior is
driven by ../project.json (selection.strategy="freshness" + selection.args). Fix
the selector once, both berlin-gastro-news and ai-daily-news get it.

Crons / daily_pipeline still call `python3 scripts/select_top.py <args>` exactly
as before — no cron migration needed.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_ROOT = Path(os.environ.get(
    "NEWS_ENGINE_ROOT", "/Users/unclejoe/.openclaw/runtime/daily-news-engine/current"))

os.environ["NEWS_PROJECT_ROOT"] = str(ROOT)
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from daily_news_engine import select_top as _engine_select_top  # noqa: E402

# Allow `import scripts.select_top` to resolve to the engine module too.
sys.modules[__name__] = _engine_select_top

if __name__ == "__main__":
    sys.exit(_engine_select_top.main())
