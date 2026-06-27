"""Thin shim → daily-news-engine shared news_db.

The SQLite data-access layer is ONE codebase in daily-news-engine. Domain
behavior comes from project.json (harvest.default_lang, harvest.use_url_seen)
and the project-local data/schema.sql. Both projects' schemas are a union;
the engine gates the divergent bits (url_seen ledger) by config so neither
DB needs migration.
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

from daily_news_engine.lib import news_db as _engine_news_db  # noqa: E402

sys.modules[__name__] = _engine_news_db
