#!/usr/bin/env bash
# Lightweight git push for the daily content repo.
#
# Replaces the legacy agent-driven backup. Only pushes text content
# (briefings, articles, daily/.state.json, daily/audio_script.md, code) —
# binary artifacts (data/news.db, daily/<>/audio.mp3) are intentionally
# untracked per .gitignore and backed up via separate channels:
#
#   data/news.db         → scripts/backup_db.sh (sqlite dump, ~/Backups/)
#   site/public/audio/   → still git-tracked (GitHub Pages serves it;
#                          consider future remote aging via Releases)
#   daily/<>/audio.mp3   → local-only intermediate; aged out by aging.sh
#
# Called by:
#   - bernard:ai-daily-news-backup cron (07:30 UTC, after all stages done)
#
# Exits 0 when nothing changed (silent no-op for empty days).

set -euo pipefail

PROJECT_ROOT="/Users/unclejoe/Media_Workspace/ai-daily-news"
PUSH_TIMEOUT=120

cd "${PROJECT_ROOT}"

git add -A

if git diff --cached --quiet; then
    echo "✓ nothing to commit"
    exit 0
fi

DATE=$(date -u +%Y-%m-%d)
git commit -m "backup: ${DATE}"

# Use the system `timeout` (coreutils on macOS via brew, or built-in on linux).
# If unavailable, fall back to no timeout — the cron-level timeout still applies.
if command -v timeout >/dev/null 2>&1; then
    timeout "${PUSH_TIMEOUT}" git push origin main
elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "${PUSH_TIMEOUT}" git push origin main
else
    echo "⚠️  no timeout command — pushing without local timeout (cron timeout still applies)"
    git push origin main
fi

echo "✅ repo push complete"
