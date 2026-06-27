"""Thin shim → daily-news-engine shared state module.

The pipeline state machine (.state.json: steps, deliveries, completeness) is
ONE codebase in daily-news-engine; this re-exports it so every project script
that does `from scripts.lib import state` gets the shared implementation.
Delivery keys resolve per-project from project.json (combined vs split).
"""
import os
import sys
from pathlib import Path

_ENGINE = Path(os.environ.get(
    "NEWS_ENGINE_ROOT", "/Users/unclejoe/Media_Workspace/daily-news-engine"))
os.environ.setdefault(
    "NEWS_PROJECT_ROOT", str(Path(__file__).resolve().parent.parent.parent))
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from daily_news_engine.lib import state as _engine_state  # noqa: E402

# Replace this module object with the engine module so ALL symbols (including
# any added later) are covered, not just a copied subset.
sys.modules[__name__] = _engine_state
