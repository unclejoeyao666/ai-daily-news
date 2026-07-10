"""Thin shim → daily-news-engine shared config (constants from project.json)."""
import os
import sys
from pathlib import Path

_ENGINE = Path(os.environ.get(
    "NEWS_ENGINE_ROOT", "/Users/unclejoe/.openclaw/runtime/daily-news-engine/current"))
os.environ.setdefault(
    "NEWS_PROJECT_ROOT", str(Path(__file__).resolve().parent.parent.parent))
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from daily_news_engine.lib import config as _engine_config  # noqa: E402

sys.modules[__name__] = _engine_config
