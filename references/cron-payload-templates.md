# Cron Payload Templates (v3.5)

This is the current ai-news-workflow cron contract. Verify deployed state with
`openclaw cron list` / `openclaw cron get <id>`. Do not raw-edit jobs.json — use
`openclaw cron edit`.

**All 8 jobs are `command`-payload crons (`payload.kind=command`).** There are
no agent-turn crons. The language model is invoked at exactly one point —
inside `scripts/stage_b.py`, via `openclaw agent`, and only when translation is
actually pending. Every other stage is deterministic Python.

Common settings for all 8 jobs:

- sessionTarget: isolated
- wakeMode: now
- delivery.mode: none (public delivery is Stage D's `openclaw message send`)
- payload.cwd: `/Users/unclejoe/Media_Workspace/ai-daily-news`
- payload.env: `OPENCLAW_BIN=/opt/homebrew/bin/openclaw` (Stage B and Stage D
  also set `STAGE_B_*` / `STAGE_D_DISCORD_ACCOUNT=fanli` so the model + the
  Discord send use the `fanli` agent/account)

Exit-code contract (command crons): **0** = success OR precondition not met
(skip — no alert); **nonzero** = real failure (failureAlert fires).

Failure alerts:

- Stage A / B / B retry / B deep / B fallback / C / D: after 1 failure to Discord
  channel:1490362785949814905 (management).
- Watchdog: after 3 consecutive failures to the same management channel; keeps a
  5-minute stagger so it never collides with a stage cron's exact minute.

## Schedule

| Job | cron UTC | timeout | command | model? |
|---|---:|---:|---|---|
| Stage A — Ingest | 0 4 * * * | 300 | `python3 scripts/daily_pipeline.py --stage ingest --date today` | no |
| Stage B — Translate | 30 4 * * * | 1200 | `python3 scripts/stage_b.py --date today` | only if pending |
| Stage B retry | 15 5 * * * | 1200 | `python3 scripts/stage_b.py --date today` | only if pending |
| Stage B deep-retry | 0 6 * * * | 1200 | `python3 scripts/stage_b.py --date today` | only if pending |
| Stage B fallback | 25 6 * * * | 300 | `python3 scripts/daily_pipeline.py --stage fallback --date today` | no |
| Stage C — Publish | 30 6 * * * | 1200 | `python3 scripts/daily_pipeline.py --stage publish --date today` | no |
| Stage D — Deliver | 0 7 * * * | 300 | `python3 scripts/stage_d_delivery.py send --date today` | no |
| Watchdog | 0 * * * * | 1200 | `python3 scripts/daily_wake.py --days 3 --budget-seconds 900` | no |

There is no health-check cron, backup cron, raw jobs.json patch workflow, or
cron announce delivery path in the active workflow.

## Recreating a cron (example)

Each job is a `command` cron. Edit an existing one in place to preserve its id,
schedule, and failure-alert config:

```bash
openclaw cron edit <STAGE_A_ID> \
  --command 'python3 scripts/daily_pipeline.py --stage ingest --date today' \
  --command-cwd /Users/unclejoe/Media_Workspace/ai-daily-news \
  --command-env OPENCLAW_BIN=/opt/homebrew/bin/openclaw \
  --timeout-seconds 300
```

Stage B crons additionally set the agent/model env:

```bash
openclaw cron edit <STAGE_B_ID> \
  --command 'python3 scripts/stage_b.py --date today' \
  --command-cwd /Users/unclejoe/Media_Workspace/ai-daily-news \
  --command-env OPENCLAW_BIN=/opt/homebrew/bin/openclaw \
  --command-env STAGE_B_AGENT=fanli \
  --command-env STAGE_B_MODEL=deepseek/deepseek-v4-flash \
  --timeout-seconds 1200
```

Stage D sets the Discord account env:

```bash
openclaw cron edit <STAGE_D_ID> \
  --command 'python3 scripts/stage_d_delivery.py send --date today' \
  --command-cwd /Users/unclejoe/Media_Workspace/ai-daily-news \
  --command-env OPENCLAW_BIN=/opt/homebrew/bin/openclaw \
  --command-env STAGE_D_DISCORD_ACCOUNT=fanli \
  --timeout-seconds 300
```

## What each stage does

- **Stage A `--stage ingest`**: harvest RSS + select the daily set. No gate.
- **Stage B `stage_b.py`**: deterministic gate — skip (exit 0, zero model
  tokens) if `select!=ok` or `translate==ok`; otherwise invoke `openclaw agent`
  once (fresh isolated session, stale-tolerant lock) to translate per
  references/translation-workflow.md, then re-check state (translate ok → exit
  0; else exit 1 so the next retry / 06:25 fallback handles it).
- **Stage B fallback `--stage fallback`**: gate on `select=ok and translate!=ok`,
  then `translate_helper.py finalize --drop-untranslated`. Ships only if
  ≥ MIN_BRIEFING translated remain; else exit 1 (failureAlert). Never fakes an
  empty day.
- **Stage C `--stage publish`**: gate on `translate=ok`, then render articles +
  briefing + audio + push. Never sends Discord.
- **Stage D `stage_d_delivery.py send`**: `openclaw message send --account fanli
  --json` for each pending delivery → record the real `messageId`. Idempotent,
  lock-guarded, exits nonzero without recording on send failure.
- **Watchdog `daily_wake.py`**: drift check; defer if a step is running; resume
  deterministic steps for 3 days; does NOT initiate today before 04:00 UTC
  (leaves the fresh harvest to Stage A); post-deadline drop-untranslated
  fallback for today; and, after 07:00 UTC, today's deterministic delivery
  backstop if Stage D missed it.

## Do NOT

- Do NOT convert any of these back to agent-turn (`payload.kind=agentTurn`)
  payloads. The old Stage D agent-turn delivery hung on the model and broke
  broadcasts for days; the same risk applies to every stage. The model belongs
  only inside `stage_b.py`'s gated `openclaw agent` call.

Update this file whenever a deployed payload changes.
