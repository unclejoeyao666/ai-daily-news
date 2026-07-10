#!/usr/bin/env python3
"""Thin shim → daily-news-engine shared translate_helper.

The translation writer / pending gate / finalize logic lives in ONE place
now (daily-news-engine/daily_news_engine/translate_helper.py); this project's
behavior is driven by ../project.json (selection.strategy="freshness" →
per-article checkpoint files, deferred slug, verify+mark-state finalize;
translate.semantic_tag_check=false → plain tag-membership check). Fix it
once, both ai-daily-news and berlin-gastro-news get it.

Crons and the Stage B agent still call
`python3 scripts/translate_helper.py <verb> …` exactly as before, and
`from scripts import translate_helper as th` still resolves to the engine
module (sys.modules replacement) so tests/imports keep working.
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

from daily_news_engine import translate_helper as _engine_th  # noqa: E402

# Replace this module object with the engine module so `from scripts import
# translate_helper as th` (and any `th.<symbol>` access) hits the real code.
sys.modules[__name__] = _engine_th

if __name__ == "__main__":
    _engine_th.main()
