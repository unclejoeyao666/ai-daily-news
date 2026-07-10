#!/usr/bin/env python3
"""Thin shim → daily-news-engine shared watchdog.

The hourly watchdog lives in ONE place now
(daily-news-engine/daily_news_engine/daily_wake.py); this project's behavior
(selection strategy="freshness" → ai-news flavor: three-gate short-circuit,
day-walk, Stage-A/Stage-D scheduling gates, drop-untranslated force fallback,
delivery backstop; no aging tail) is driven by ../project.json. Fix the
watchdog once, both ai-daily-news and berlin-gastro-news get it.

Crons still call `python3 scripts/daily_wake.py [--days … | --date … |
--budget-seconds …]` exactly as before — no cron migration needed.
`from scripts import daily_wake` resolves to the engine module (sys.modules
replacement), so tests/test_reliability.py (which uses dw._past_drop_deadline)
keep working.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE_ROOT = Path(os.environ.get(
    "NEWS_ENGINE_ROOT", "/Users/unclejoe/.openclaw/runtime/daily-news-engine/current"))

os.environ["NEWS_PROJECT_ROOT"] = str(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from daily_news_engine import daily_wake as _engine_daily_wake  # noqa: E402

# Allow `import scripts.daily_wake` / `from scripts import daily_wake` to
# resolve to the engine module — every symbol (main, walk_days,
# _past_drop_deadline, force_translate_fallback, …) is covered.
sys.modules[__name__] = _engine_daily_wake

if __name__ == "__main__":
    _engine_daily_wake.main()
