#!/usr/bin/env python3
"""Thin shim → daily-news-engine shared daily_pipeline orchestrator.

The end-to-end orchestrator lives in ONE place now
(daily-news-engine/daily_news_engine/daily_pipeline.py); this project's
behavior (selection strategy="freshness" → ai-news flavor: select args,
STEP_LABELS status format, run_steps from/to + --resume, verify-only
translate, drop-untranslated fallback) is driven by ../project.json. Fix
the orchestrator once, both berlin-gastro-news and ai-daily-news get it.

The per-project publish layer (publish_article.py, publish_briefing.py,
render_audio.py, git_publish.py) is NOT merged — the engine shells out to
`python3 scripts/<x>.py` with cwd=ROOT, so each step runs THIS project's
own scripts.

Crons and daily_wake.py call `python3 scripts/daily_pipeline.py …`
exactly as before, and `import scripts.daily_pipeline` resolves to the
engine module (sys.modules replacement) so any import keeps working.
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

from daily_news_engine import daily_pipeline as _engine_daily_pipeline  # noqa: E402

# Allow `import scripts.daily_pipeline` to resolve to the engine module too —
# every symbol (main, run_stage, …) is covered.
sys.modules[__name__] = _engine_daily_pipeline

if __name__ == "__main__":
    _engine_daily_pipeline.main()
