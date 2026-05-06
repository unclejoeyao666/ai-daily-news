#!/usr/bin/env bash
# Local-only aging of intermediate pipeline artifacts.
#
# After v3 the pipeline writes audio.mp3 to two places:
#   1. daily/<Y>/<Y-M>/<DATE>/audio.mp3   ← intermediate, not tracked
#   2. site/public/audio/<DATE>.mp3       ← tracked, served by GitHub Pages
#
# (1) is purely a working copy for render_audio.py + Stage D delivery.
# Once the day is published and Discord-delivered, (1) has no further
# purpose locally. (2) is the canonical artifact — the website serves
# it, and operators can always re-fetch via the public URL if needed.
#
# This script deletes (1) for any DATE older than AGING_DAYS days.
# Companion files (briefing.md, audio_script.md, .state.json, meta.json)
# are tiny and kept indefinitely — they are the per-day audit trail.
#
# Idempotent: re-running deletes nothing new if everything within
# AGING_DAYS is already absent.
#
# Defaults:
#   AGING_DAYS=14   override via env or first arg
#   DRY_RUN=0       set DRY_RUN=1 to print actions without deleting
#
# Called by:
#   - manually
#   - optional cron (consider weekly: e.g. `0 8 * * 0` UTC sundays)

set -euo pipefail

PROJECT_ROOT="/Users/unclejoe/Media_Workspace/ai-daily-news"
DAILY_ROOT="${PROJECT_ROOT}/daily"
AGING_DAYS="${1:-${AGING_DAYS:-14}}"
DRY_RUN="${DRY_RUN:-0}"

if [ ! -d "${DAILY_ROOT}" ]; then
    echo "❌ daily root missing: ${DAILY_ROOT}" >&2
    exit 2
fi

# Find audio.mp3 files older than AGING_DAYS days (mtime-based).
# `find -mtime +N` matches files modified more than N*24h ago.
# Portable to macOS default bash 3.2 — no `mapfile`.
TOTAL_BYTES=0
COUNT=0
TMP=$(mktemp)
trap 'rm -f "${TMP}"' EXIT

find "${DAILY_ROOT}" -type f -name 'audio.mp3' -mtime +"${AGING_DAYS}" > "${TMP}" 2>/dev/null || true

if [ ! -s "${TMP}" ]; then
    echo "✓ no daily/<>/audio.mp3 older than ${AGING_DAYS} days"
    exit 0
fi

while IFS= read -r f; do
    [ -z "$f" ] && continue
    sz=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)
    TOTAL_BYTES=$((TOTAL_BYTES + sz))
    COUNT=$((COUNT + 1))
    if [ "${DRY_RUN}" = "1" ]; then
        echo "would delete: $f (${sz} bytes)"
    else
        rm -- "$f"
        echo "deleted: $f"
    fi
done < "${TMP}"

if [ "${DRY_RUN}" = "1" ]; then
    echo "✓ DRY_RUN: would have freed $((TOTAL_BYTES / 1024 / 1024)) MB across ${COUNT} files"
else
    echo "✅ aged out ${COUNT} files, freed $((TOTAL_BYTES / 1024 / 1024)) MB"
fi
