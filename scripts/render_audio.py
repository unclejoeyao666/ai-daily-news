#!/usr/bin/env python3
"""Render daily audio_script.md → audio.mp3 via the shared 3-tier TTS
cascade (edge-tts → MiniMax → local say+ffmpeg), then mirror into
site/public/audio/.

Replaces the previous hard-coded external dependency on
``/Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py``: the
self-contained cascade in ``scripts/lib/tts.py`` adds a local ``say``
tier so audio survives BOTH cloud providers failing (not just one), and
removes the brittle external-path coupling. (Backported from
berlin-gastro-news; same Chinese voice family.)
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib.normalize import sanitize_for_tts
from scripts.lib.tts import synthesize

DAILY_ROOT = ROOT / "daily"
SITE_AUDIO = ROOT / "site" / "public" / "audio"


def parse_date(s) -> str:
    if not s or s == "today":
        return datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")
    return s


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--date", default="today")
    # Accepted for backward-compat with existing callers; the cascade now
    # selects providers and handles fallback internally, so these are
    # advisory only.
    p.add_argument("--provider", default=None)
    p.add_argument("--voice", default=None)
    p.add_argument("--rate", default=None)
    p.add_argument("--no-fallback", action="store_true")
    args = p.parse_args()

    date_str = parse_date(args.date)
    year, month, _ = date_str.split("-")
    day_dir = DAILY_ROOT / year / f"{year}-{month}" / date_str
    script_md = day_dir / "audio_script.md"
    if not script_md.exists():
        print(f"❌ {script_md.relative_to(ROOT)} not found")
        sys.exit(1)

    raw = script_md.read_text(encoding="utf-8")
    plain = sanitize_for_tts(raw)
    plain_txt = day_dir / "audio_script.tts.txt"
    plain_txt.write_text(plain, encoding="utf-8")
    print(f"📝 sanitized {len(raw)} → {len(plain)} chars → "
          f"{plain_txt.relative_to(ROOT)}")

    out_mp3 = day_dir / "audio.mp3"
    log_path = day_dir / ".tts.log"
    try:
        provider = synthesize(plain, out_mp3, log_path=log_path)
    except RuntimeError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(2)

    SITE_AUDIO.mkdir(parents=True, exist_ok=True)
    target = SITE_AUDIO / f"{date_str}.mp3"
    shutil.copy2(out_mp3, target)
    size_kb = target.stat().st_size / 1024
    print(f"✅ {target.relative_to(ROOT)} ({size_kb:.1f} KB) via {provider}")

    plain_txt.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
