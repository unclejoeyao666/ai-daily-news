#!/usr/bin/env bash
# Independent backup of the SQLite news database.
#
# This is the canonical backup path for `data/news.db` after v3 — that
# file is no longer tracked in the main git repo (too large, rewritten
# every harvest). We instead dump it via SQLite's online backup (safe
# while the DB is open elsewhere) and gzip the result.
#
# Output: $BACKUP_ROOT/news-YYYY-MM-DD.db.gz (UTC date)
# Retention: most recent 30 dumps; older ones are deleted.
#
# Called by:
#   - The OpenClaw bernard:ai-daily-news-backup cron (07:30 UTC)
#   - Manually for ad-hoc recovery
#
# Exits non-zero on:
#   - sqlite3 not on PATH
#   - .backup command fails (DB locked / corrupt / no disk space)
#   - gzip fails

set -euo pipefail

PROJECT_ROOT="/Users/unclejoe/Media_Workspace/ai-daily-news"
BACKUP_ROOT="${HOME}/Backups/ai-daily-news-db"
DB_PATH="${PROJECT_ROOT}/data/news.db"
RETAIN_DAYS=30

DATE=$(date -u +%Y-%m-%d)
DEST="${BACKUP_ROOT}/news-${DATE}.db"

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "❌ sqlite3 not found on PATH" >&2
    exit 2
fi

if [ ! -f "${DB_PATH}" ]; then
    echo "❌ database missing: ${DB_PATH}" >&2
    exit 2
fi

mkdir -p "${BACKUP_ROOT}"

# SQLite online backup — atomic and safe even if DB is open elsewhere.
sqlite3 "${DB_PATH}" ".backup '${DEST}'"
gzip -9 -f "${DEST}"

# Retention: keep the most recent N dumps.
# shellcheck disable=SC2012
ls -t "${BACKUP_ROOT}"/news-*.db.gz 2>/dev/null \
    | tail -n +$((RETAIN_DAYS + 1)) \
    | xargs -r rm -- || true

SIZE=$(stat -f%z "${DEST}.gz" 2>/dev/null || stat -c%s "${DEST}.gz" 2>/dev/null || echo 0)
echo "✅ db backup → ${DEST}.gz ($((SIZE / 1024)) KB)"
