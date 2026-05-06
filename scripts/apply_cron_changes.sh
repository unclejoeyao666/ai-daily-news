#!/usr/bin/env bash
# Apply v3.1 cron changes to ~/.openclaw/cron/jobs.json
#
# This script DOES NOT modify jobs.json directly. It produces a backup
# + a JSON patch file the operator can review before applying via the
# OpenClaw client (`/cron update`, `/cron create`, etc.).
#
# Why not patch directly:
#   - jobs.json is owned by the OpenClaw daemon; it watches the file
#     and reloads. Direct edits while it's running can corrupt state.
#   - Operator should be in the loop for cron changes — they affect
#     billing (model invocations) and visibility.
#
# Output:
#   - ~/.openclaw/cron/jobs.json.pre-v3.1.backup-<timestamp>
#   - /tmp/cron-changes-v3.1.md (human-readable instructions)
#
# Usage:
#   bash scripts/apply_cron_changes.sh

set -euo pipefail

JOBS_JSON="${HOME}/.openclaw/cron/jobs.json"
BACKUP="${JOBS_JSON}.pre-v3.1.backup-$(date -u +%Y%m%dT%H%M%S)"
INSTRUCTIONS=/tmp/cron-changes-v3.1.md

if [ ! -f "${JOBS_JSON}" ]; then
    echo "❌ ${JOBS_JSON} not found" >&2
    exit 2
fi

cp "${JOBS_JSON}" "${BACKUP}"
echo "✅ jobs.json backed up to: ${BACKUP}"

cat > "${INSTRUCTIONS}" <<'EOF'
# AI News Workflow v3.1 — Cron Changes

Apply each change via your OpenClaw client (`/cron` commands or whatever
GUI is wired up). All changes are listed with the canonical payload from
`/Users/unclejoe/.agents/skills/ai-news-workflow/references/cron-payload-templates.md`.

## A. Modify existing 5 jobs

### 1. Stage A — Ingest (id starts with `3a25d2a8`)

```diff
- "schedule": {"kind": "cron", "expr": "0 4 * * *", "tz": "UTC"},
+ "schedule": {"kind": "cron", "expr": "0 4 * * *", "tz": "UTC"},
- "payload": {"kind": "agentTurn", "timeoutSeconds": 300, ...}
+ "payload": {"kind": "agentTurn", "timeoutSeconds": 600, ...}
```

Replace the `payload.message` with the **Stage A** template from
cron-payload-templates.md.

### 2. Stage B Translate main (id starts with `7f4a8918`)

```diff
- "timeoutSeconds": 1200
+ "timeoutSeconds": 1500
```

Replace the `payload.message` with the **Stage B** template.

### 3. Watchdog (id starts with `821b08f3`)

```diff
- "schedule": {"kind": "cron", "expr": "0 * * * *", ...}
+ "schedule": {"kind": "cron", "expr": "0,30 4-7 * * *", "tz": "UTC", "staggerMs": 300000}
- "timeoutSeconds": 1200
+ "timeoutSeconds": 300
```

Replace `payload.message` with the **Watchdog** template (uses
`--days 1 --budget-seconds 240`).

### 4. ai-daily-news-backup (id starts with `e52e612a`)

```diff
- "schedule": {"kind": "cron", "expr": "0 9 * * *", "tz": "Europe/Berlin"}
+ "schedule": {"kind": "cron", "expr": "30 7 * * *", "tz": "UTC"}
- "timeoutSeconds": 180
+ "timeoutSeconds": 300
```

Replace `payload.message` with the **Backup** template (calls
backup_db.sh + backup_repo.sh).

### 5. Stage D Deliver (id starts with `7ffd5e3d`) — payload only, schedule unchanged

Replace `payload.message` with the **Stage D** template (now uses
record_delivery.py + double-send guard).

## B. Create 5 new jobs

For each, set:
- `delivery: {mode: "none"}`
- `failureAlert: {after: 1, mode: "announce", channel: "discord", to: "channel:1490362785949814905"}` (use `after: 3` for watchdog if you regenerate it)
- `agentId: "fanli"` for Stage B/D retries and health; `agentId: "fanli"` is fine for backup-related too if you want them owned by fanli, otherwise use bernard.
- `payload.kind: "agentTurn"`
- `payload.model: "minimax-portal/MiniMax-M2.7"` (same as existing)

### 1. Stage B retry — schedule `15 5 * * *` UTC, timeout 1500s, payload = Stage B template

### 2. Stage B deep retry — schedule `30 6 * * *` UTC, timeout 1500s, payload = Stage B template

### 3. Stage D retry — schedule `0 7 * * *` UTC, timeout 600s, payload = Stage D template

### 4. Health Check — schedule `0 9 * * *` UTC, timeout 120s, payload = Health Check template

### 5. Health Recheck — schedule `0 12 * * *` UTC, timeout 120s, payload = Health Recheck template (with `--rescue`)

## C. Verify

After applying, sanity-check:

```bash
# 1. Backup integrity (rollback if anything goes wrong)
ls -la ~/.openclaw/cron/jobs.json.pre-v3.1.backup-*

# 2. Check the new schedules are picked up by OpenClaw
python3 -c "
import json
d = json.load(open('$HOME/.openclaw/cron/jobs.json'))
for j in d['jobs']:
    if 'ai-news' in j.get('name','').lower() or 'fanli' in j.get('name','').lower() or 'ai-daily-news' in j.get('name','').lower():
        print(f\"{j['schedule']['expr']:20s} {j['payload']['timeoutSeconds']:5d}s  {j['name']}\")
" | sort

# 3. Health check should now run at 09:00 UTC daily
# After tomorrow's 09:00, look for either:
#   - A message in Discord channel 1490362785949814905
#   - Or ~/Backups/ai-daily-news-db/needs_attention/<DATE>.md
```

## D. Rollback

If anything breaks, restore from backup:

```bash
cp ~/.openclaw/cron/jobs.json.pre-v3.1.backup-<timestamp> ~/.openclaw/cron/jobs.json
# Then signal OpenClaw to reload (kill+restart or whatever your daemon expects)
```
EOF

echo "✅ instructions written to: ${INSTRUCTIONS}"
echo
echo "Next steps:"
echo "  1. Read ${INSTRUCTIONS}"
echo "  2. Apply each change via your OpenClaw client (/cron commands)"
echo "  3. Use payload templates from:"
echo "     /Users/unclejoe/.agents/skills/ai-news-workflow/references/cron-payload-templates.md"
echo "  4. Verify with the snippets in section C"
