#!/usr/bin/env python3
"""Render daily audio_script.md → audio.mp3, then mirror into site/public/audio/."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.lib.normalize import sanitize_for_tts

TTS_SCRIPT = Path("/Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py")
DAILY_ROOT = ROOT / "daily"
SITE_AUDIO = ROOT / "site" / "public" / "audio"


def parse_date(s) -> str:
    if not s or s == "today":
        return datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")
    return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default="today")
    p.add_argument("--provider", default="microsoft", choices=["microsoft", "minimax"])
    p.add_argument("--voice", default=None,
                   help="Voice ID. Defaults: microsoft=zh-CN-XiaoxiaoNeural, minimax=male-qn-qingse")
    p.add_argument("--rate", default="+0%")
    p.add_argument("--no-fallback", action="store_true",
                   help="Disable automatic MiniMax fallback when microsoft fails")
    args = p.parse_args()
    if args.voice is None:
        args.voice = "zh-CN-XiaoxiaoNeural" if args.provider == "microsoft" else "male-qn-qingse"

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
    print(f"📝 sanitized {len(raw)} → {len(plain)} chars → {plain_txt.relative_to(ROOT)}")

    out_mp3 = day_dir / "audio.mp3"

    if not TTS_SCRIPT.exists():
        print(f"❌ TTS helper not found: {TTS_SCRIPT}")
        print(f"    install minimax_tts.py at that path or pass --provider minimax with API key")
        sys.exit(2)

    def run_tts(provider: str, voice: str) -> subprocess.CompletedProcess:
        cmd = [
            "python3", str(TTS_SCRIPT),
            "--file", str(plain_txt),
            str(out_mp3),
            "--provider", provider,
            "--voice", voice,
        ]
        if provider == "microsoft":
            cmd += ["--rate", args.rate]
        print(f"🎙️  {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    r = run_tts(args.provider, args.voice)
    if r.returncode != 0 and args.provider == "microsoft" and not args.no_fallback:
        print("⚠️  microsoft TTS failed, falling back to MiniMax")
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        r = run_tts("minimax", "male-qn-qingse")
    if r.returncode != 0:
        print("❌ TTS failed:")
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        sys.exit(2)
    print(r.stdout.strip())

    SITE_AUDIO.mkdir(parents=True, exist_ok=True)
    target = SITE_AUDIO / f"{date_str}.mp3"
    shutil.copy2(out_mp3, target)
    size_kb = target.stat().st_size / 1024
    print(f"✅ {target.relative_to(ROOT)} ({size_kb:.1f} KB)")

    plain_txt.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
