"""Three-tier TTS cascade for Berlin Gastro News audio rendering.

Order: node-edge-tts (free, online) → MiniMax HD API (paid) → macOS
``say`` + ffmpeg (always works locally). Each provider is a callable
that takes ``(text, mp3_path, log_lines)`` and returns ``True`` on
success.

Why this exists: ``Doc_Workspace/scripts/minimax_tts.py`` hard-coded an
edge-tts path that no longer exists in newer OpenClaw layouts, and the
MiniMax fallback silently fails when the API key is missing. This
module discovers the right edge-tts JS automatically and *guarantees*
we always produce an mp3 by falling through to ``say``.
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

# ── Paths ───────────────────────────────────────────────────────


def _find_node_edge_tts() -> Optional[Path]:
    """Find the highest-versioned ``node-edge-tts/dist/edge-tts.js``."""
    candidates: List[Path] = []
    home = Path.home()

    # 1. OpenClaw plugin-runtime-deps versioned drops (newest first)
    for p in sorted(
        glob.glob(str(home / ".openclaw/plugin-runtime-deps/openclaw-*"
                       "/node_modules/node-edge-tts/dist/edge-tts.js")),
        reverse=True,
    ):
        candidates.append(Path(p))

    # 2. Global npm install
    candidates.append(Path(
        "/opt/homebrew/lib/node_modules/openclaw/node_modules/"
        "node-edge-tts/dist/edge-tts.js"
    ))
    candidates.append(Path(
        "/opt/homebrew/lib/node_modules/node-edge-tts/dist/edge-tts.js"
    ))

    # 3. Project-local npm install (rare but possible)
    candidates.append(
        Path.cwd() / "node_modules/node-edge-tts/dist/edge-tts.js"
    )

    for c in candidates:
        if c.exists():
            return c
    return None


# ── Provider 1: node-edge-tts (Microsoft Edge TTS) ──────────────


EDGE_VOICE = "zh-CN-XiaoxiaoNeural"
EDGE_MAX_CHARS = 1200


def _edge_tts_chunk(text: str, out_file: Path,
                    edge_js: Path, voice: str = EDGE_VOICE,
                    rate: str = "+0%", pitch: str = "+0Hz",
                    log_lines: Optional[List[str]] = None) -> bool:
    """Single chunk via node-edge-tts. Returns True on success."""
    script = (
        f"const {{EdgeTTS}} = require('{edge_js}');\n"
        f"const tts = new EdgeTTS({{\n"
        f"  voice: '{voice}', lang: 'zh-CN',\n"
        f"  outputFormat: 'audio-24khz-48kbitrate-mono-mp3',\n"
        f"  rate: '{rate}', pitch: '{pitch}', proxy: ''\n"
        f"}});\n"
        f"const text = {json.dumps(text)};\n"
        f"tts.ttsPromise(text, '{out_file}')\n"
        f"  .then(() => {{ console.log('OK'); process.exit(0); }})\n"
        f"  .catch(err => {{\n"
        f"    console.error('ERR:' + (err.message || String(err)));\n"
        f"    process.exit(1);\n"
        f"  }});\n"
    )
    try:
        r = subprocess.run(
            ["node", "--eval", script],
            capture_output=True, text=True, timeout=180,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        if log_lines is not None:
            log_lines.append(f"[edge] subprocess error: {e}")
        return False
    ok = r.returncode == 0 and "OK" in r.stdout
    if not ok and log_lines is not None:
        log_lines.append(f"[edge] failed: rc={r.returncode} "
                         f"stderr={r.stderr.strip()[:200]}")
    return ok


def synthesize_edge(text: str, mp3_path: Path,
                    log_lines: Optional[List[str]] = None) -> bool:
    """Try Microsoft Edge TTS via node-edge-tts."""
    edge_js = _find_node_edge_tts()
    if not edge_js:
        if log_lines is not None:
            log_lines.append("[edge] no node-edge-tts module found")
        return False
    if log_lines is not None:
        log_lines.append(f"[edge] using {edge_js}")

    if shutil.which("node") is None:
        if log_lines is not None:
            log_lines.append("[edge] no `node` on PATH")
        return False

    if not text.strip():
        return False

    if len(text) <= EDGE_MAX_CHARS:
        return _edge_tts_chunk(text, mp3_path, edge_js, log_lines=log_lines)

    # Chunked synthesis + ffmpeg concat
    tmp_dir = Path(tempfile.mkdtemp(prefix="edge_tts_"))
    try:
        chunks = [text[i:i + EDGE_MAX_CHARS]
                  for i in range(0, len(text), EDGE_MAX_CHARS)]
        files = []
        for i, chunk in enumerate(chunks):
            out = tmp_dir / f"c{i:03d}.mp3"
            if not _edge_tts_chunk(chunk, out, edge_js, log_lines=log_lines):
                return False
            files.append(out)
        return _concat_mp3(files, mp3_path, log_lines=log_lines)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _concat_mp3(parts: List[Path], out: Path,
                log_lines: Optional[List[str]] = None) -> bool:
    """Concatenate MP3s via ffmpeg; fallback to byte concat."""
    if not parts:
        return False
    list_txt = out.parent / f".{out.stem}.list.txt"
    list_txt.write_text(
        "\n".join(f"file '{p}'" for p in parts), encoding="utf-8",
    )
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(list_txt), "-acodec", "copy", str(out)],
            capture_output=True, text=True, timeout=120,
        )
        list_txt.unlink(missing_ok=True)
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return True
        if log_lines is not None:
            log_lines.append(f"[concat] ffmpeg failed rc={r.returncode}: "
                             f"{r.stderr.strip()[:200]}")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        if log_lines is not None:
            log_lines.append(f"[concat] ffmpeg error: {e}")

    # byte-concat fallback (works for same-encoding MP3s)
    with open(out, "wb") as o:
        for p in parts:
            o.write(p.read_bytes())
    return out.exists() and out.stat().st_size > 0


# ── Provider 2: MiniMax HD API ──────────────────────────────────


MINIMAX_BASE = "https://api.minimaxi.com"
MINIMAX_MODEL = "speech-2.8-hd"
MINIMAX_VOICE = "female-shaonv-jingpin"  # 清亮中文女声


def _load_minimax_token() -> Optional[str]:
    token = os.environ.get("MINIMAX_API_KEY")
    if token:
        return token
    cfg = Path.home() / ".minimax/tts_config.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            return None
        return data.get("api_key") or data.get("token")
    return None


def synthesize_minimax(text: str, mp3_path: Path,
                       log_lines: Optional[List[str]] = None) -> bool:
    """Try MiniMax HD API. Skips silently if no token configured."""
    import binascii
    import urllib.error
    import urllib.request

    token = _load_minimax_token()
    if not token:
        if log_lines is not None:
            log_lines.append("[minimax] no MINIMAX_API_KEY / config — "
                             "skipped")
        return False
    if not text.strip():
        return False

    payload = {
        "model": MINIMAX_MODEL,
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": MINIMAX_VOICE,
            "speed": 1.0, "vol": 1.0, "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000, "bitrate": 128000,
            "format": "mp3", "channel": 1,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    req = urllib.request.Request(
        f"{MINIMAX_BASE}/v1/t2a_v2",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if log_lines is not None:
            log_lines.append(f"[minimax] HTTP {e.code}: {body}")
        return False
    except Exception as e:
        if log_lines is not None:
            log_lines.append(f"[minimax] request error: {e}")
        return False

    base_resp = result.get("base_resp", {})
    if base_resp.get("status_code") != 0:
        if log_lines is not None:
            log_lines.append(f"[minimax] api error: {base_resp}")
        return False

    audio_hex = (result.get("data") or {}).get("audio")
    if not audio_hex:
        if log_lines is not None:
            log_lines.append("[minimax] empty audio in response")
        return False

    mp3_path.write_bytes(binascii.unhexlify(audio_hex))
    return mp3_path.exists() and mp3_path.stat().st_size > 0


# ── Provider 3: macOS say + ffmpeg ──────────────────────────────


SAY_VOICE = "Tingting"  # zh_CN, ships with macOS


def synthesize_say(text: str, mp3_path: Path,
                   log_lines: Optional[List[str]] = None,
                   voice: str = SAY_VOICE) -> bool:
    """Last-resort: macOS ``say`` to AIFF then ffmpeg to MP3.

    Note: ``log_lines`` is the 3rd positional arg to match the
    ``(text, mp3_path, log_lines)`` calling convention the cascade in
    ``synthesize`` uses for every provider; ``voice`` is keyword-only
    in practice. (Previously ``voice`` sat 3rd, so the cascade passed
    the ``log_lines`` list in as the voice — breaking the only
    network-free fallback.)"""
    if shutil.which("say") is None:
        if log_lines is not None:
            log_lines.append("[say] not on PATH (non-macOS?)")
        return False
    if shutil.which("ffmpeg") is None:
        if log_lines is not None:
            log_lines.append("[say] need ffmpeg to convert to MP3")
        return False
    if not text.strip():
        return False

    tmp_dir = Path(tempfile.mkdtemp(prefix="say_tts_"))
    aiff = tmp_dir / "out.aiff"
    txt = tmp_dir / "in.txt"
    txt.write_text(text, encoding="utf-8")
    try:
        r = subprocess.run(
            ["say", "-v", voice, "-f", str(txt), "-o", str(aiff)],
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            if log_lines is not None:
                log_lines.append(f"[say] say failed: {r.stderr[:200]}")
            return False
        r2 = subprocess.run(
            ["ffmpeg", "-y", "-i", str(aiff),
             "-acodec", "libmp3lame", "-ar", "32000",
             "-b:a", "128k", "-ac", "1", str(mp3_path)],
            capture_output=True, text=True, timeout=300,
        )
        if r2.returncode != 0:
            if log_lines is not None:
                log_lines.append(f"[say] ffmpeg failed: "
                                 f"{r2.stderr[:200]}")
            return False
        return mp3_path.exists() and mp3_path.stat().st_size > 0
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        if log_lines is not None:
            log_lines.append(f"[say] subprocess error: {e}")
        return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Cascade ──────────────────────────────────────────────────────


PROVIDERS: List[Callable[[str, Path, Optional[List[str]]], bool]] = [
    synthesize_edge,
    synthesize_minimax,
    synthesize_say,
]


def synthesize(text: str, mp3_path: Path,
               log_path: Optional[Path] = None,
               providers: Optional[List[Callable]] = None) -> str:
    """Run the cascade until one provider succeeds.

    Returns the *name* of the provider that succeeded (e.g.
    ``"synthesize_edge"``). Raises ``RuntimeError`` with the captured
    log if every provider failed.
    """
    log_lines = [
        f"-- TTS cascade @ {datetime.now(timezone.utc).isoformat()} --",
        f"text length: {len(text)} chars",
        f"target: {mp3_path}",
    ]
    chosen = providers or PROVIDERS
    for fn in chosen:
        log_lines.append(f"[try] {fn.__name__}")
        ok = False
        try:
            ok = fn(text, mp3_path, log_lines)
        except Exception as e:  # provider should not raise but be safe
            log_lines.append(f"  unexpected: {e}")
        if ok and mp3_path.exists() and mp3_path.stat().st_size > 100:
            log_lines.append(f"[ok] {fn.__name__} → "
                             f"{mp3_path.stat().st_size} bytes")
            if log_path:
                log_path.write_text("\n".join(log_lines), encoding="utf-8")
            return fn.__name__
    if log_path:
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
    raise RuntimeError(
        "All TTS providers failed. See log:\n  " +
        "\n  ".join(log_lines[-12:])
    )
