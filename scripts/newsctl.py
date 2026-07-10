#!/usr/bin/env python3
"""Thin AI Daily News entrypoint for the shared daily-news-engine V4 CLI.

This file intentionally contains no pipeline logic.  It only pins the project
root, locates the shared engine, and leaves ``sys.argv`` untouched so every
subcommand and exit code comes from ``daily_news_engine.v4.cli``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ENGINE_ROOT = Path(
    os.environ.get(
        "NEWS_ENGINE_ROOT",
        "/Users/unclejoe/.openclaw/runtime/daily-news-engine/current",
    )
).expanduser()


def main() -> int:
    os.environ["NEWS_PROJECT_ROOT"] = str(ROOT)
    os.environ.setdefault("NEWS_ENGINE_ROOT", str(ENGINE_ROOT))

    if not (ENGINE_ROOT / "daily_news_engine").is_dir():
        print(
            f"newsctl: shared engine not found at {ENGINE_ROOT}",
            file=sys.stderr,
        )
        return 2

    engine_path = str(ENGINE_ROOT)
    if engine_path not in sys.path:
        sys.path.insert(0, engine_path)

    try:
        from daily_news_engine.v4.cli import main as engine_main
    except ImportError as exc:
        print(
            "newsctl: shared engine V4 CLI is unavailable "
            f"({exc.__class__.__name__}: {exc})",
            file=sys.stderr,
        )
        return 2

    result = engine_main()
    return int(result) if result is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
