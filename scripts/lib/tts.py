"""Thin adapter to the shared, deadline-bounded TTS cascade."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ENGINE_ROOT = Path(os.environ.get(
    "NEWS_ENGINE_ROOT",
    "/Users/unclejoe/.openclaw/runtime/daily-news-engine/current"))
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from daily_news_engine.lib import tts as _engine_tts  # noqa: E402

sys.modules[__name__] = _engine_tts
