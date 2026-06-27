# Pipeline protocol — `.state.json` and the cron stages

This file is the contract every cron / agent / watchdog follows when touching the AI Daily News pipeline. Read it once at the start of any Stage to know exactly what to inspect and what to write.

## TL;DR

The pipeline has **7 ordered Python steps** plus **2 Discord deliveries**. State for one date lives in a single file:

```
/Users/unclejoe/Media_Workspace/ai-daily-news/daily/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/.state.json
```

Seven stage crons advance it forward (Stage A; Stage B + 2 retries + 1
deterministic fallback; Stage C; Stage D). **All 8 crons are deterministic
`command` payloads** — the model is invoked only inside `scripts/stage_b.py`,
and only when translation is pending. A watchdog (`daily_wake.py`) every hour
sweeps the last 3 days, resumes anything pending, runs the deterministic
drop-untranslated fallback for today past 06:25 UTC, and (today, past 07:00 UTC)
backstops Discord delivery if Stage D missed it.

## The 7 pipeline steps + 2 deliveries

| # | step (key in `state["steps"]`) | runner | side effects |
|---|---|---|---|
| 1 | `harvest` | `scripts/harvest.py` | inserts new rows in `data/news.db` |
| 2 | `select` | `scripts/select_top.py` | writes `daily-selected.json` |
| 3 | `translate` | `scripts/translate_helper.py finalize` (gate; agent does the actual work via `write`) | updates `news_articles.translated_*` + `audio_script.md` |
| 4 | `publish_article` | `scripts/publish_article.py --all-pending` | writes `site/src/content/articles/<slug>.md` |
| 5 | `publish_brief` | `scripts/publish_briefing.py --date today` | writes `site/src/content/briefings/<DATE>.md`, `daily/.../briefing.md`, `daily/.../meta.json`; `mark_played` |
| 6 | `audio` | `scripts/render_audio.py --date today` | writes `daily/.../audio.mp3` + `site/public/audio/<DATE>.mp3` |
| 7 | `push` | `scripts/git_publish.py --date today` | `git pull --rebase` then commit + push |

Discord deliveries live in `state["deliveries"]`, **not** in `state["steps"]`. They are produced by the deterministic Stage D `command` cron (`stage_d_delivery.py send`), which the watchdog does not run.

| key (in `state["deliveries"]`) | runner | when |
|---|---|---|
| `discord_text` | `scripts/stage_d_delivery.py send` → `openclaw message send --json` → records real `messageId` | Stage D, after `push=ok` |
| `discord_audio` | `scripts/stage_d_delivery.py send` → `openclaw message send --media ... --json` → records real `messageId` | Stage D, after `push=ok` |

## `.state.json` shape

```json
{
  "date": "2026-04-29",
  "started_at": "2026-04-29T04:00:11.412Z",
  "steps": {
    "harvest":         {"status": "ok", "finished_at": "...", "stats": {"unplayed": 178, "total": 1480}},
    "select":          {"status": "ok", "finished_at": "...", "selected_count": 10},
    "translate":       {"status": "ok", "finished_at": "...", "translated_count": 10, "skipped_count": 0, "audio_chars": 1973},
    "publish_article": {"status": "ok", "finished_at": "..."},
    "publish_brief":   {"status": "ok", "finished_at": "..."},
    "audio":           {"status": "ok", "finished_at": "...", "mp3_size": 6184320},
    "push":            {"status": "ok", "finished_at": "..."}
  },
  "deliveries": {
    "discord_text":  {"status": "ok", "message_id": "1508793194547249285", "finished_at": "..."},
    "discord_audio": {"status": "ok", "message_id": "1508793319424135318", "finished_at": "..."}
  }
}
```

Status values: `pending` | `running` | `ok` | `failed` | `skipped`. Only `ok` counts as done. Writes are atomic (`tempfile + os.replace`), so a SIGKILL mid-write can never produce half-written JSON — the next reader sees the previous coherent state.

## Stage ↔ step mapping

All crons are `command` payloads; the `command` column is the exact shell run.

| Stage | Cron (UTC) | command | Steps it advances | Required precondition |
|---|---|---|---|---|
| **A. Ingest** | `0 4 * * *` | `daily_pipeline.py --stage ingest` | `harvest`, `select` (incl. DB aging) | none |
| **B. Translate** | `30 4 * * *` | `stage_b.py` (gate → `openclaw agent`: `pending`→`write`→`finalize`) | `translate` | `select=ok ∧ translate≠ok` |
| **B. retry** | `15 5 * * *` | `stage_b.py` | `translate` (pending ids only) | same |
| **B. deep-retry** | `0 6 * * *` | `stage_b.py` | `translate` (pending ids only) | same |
| **B. fallback-finalize** | `25 6 * * *` | `daily_pipeline.py --stage fallback` | `translate` via `finalize --drop-untranslated` | same |
| **C. Publish** | `30 6 * * *` | `daily_pipeline.py --stage publish` | `publish_article`, `publish_brief`, `audio`, `push` | `translate=ok` |
| **D. Deliver** | `0 7 * * *` | `stage_d_delivery.py send` | (writes `state["deliveries"]`) | `push=ok` |
| Watchdog | `0 * * * *` | `daily_wake.py --days 3` | resumes pending steps; today-past-06:25 drop fallback; today-past-07:00 delivery backstop | none |

## What each Stage does FIRST

Before doing any work, every Stage runs:

```bash
cd /Users/unclejoe/Media_Workspace/ai-daily-news
python3 scripts/daily_pipeline.py --date today --status
```

Then inspects the relevant precondition step. If the precondition is not `ok`, the stage **exits silently** (rc=0, no Discord noise) — the watchdog or the next Stage cron will catch up.

| Stage | Stage exits silently if … |
|---|---|
| A | (no precondition; always proceeds) |
| B / B-retry / B-deep / B-fallback | `select != ok` **or** `translate == ok` |
| C | `translate != ok` |
| D | `push != ok` |

## CLI reference — `scripts/daily_pipeline.py`

```bash
# inspect today's state
python3 scripts/daily_pipeline.py --date today --status

# run a single step
python3 scripts/daily_pipeline.py --date today --step harvest

# deterministic stage commands used by the A / C / fallback crons
# (gated precondition; exit 0 = ok/skip, nonzero = real failure)
python3 scripts/daily_pipeline.py --stage ingest   --date today   # Stage A: harvest+select
python3 scripts/daily_pipeline.py --stage publish  --date today   # Stage C: gated on translate=ok
python3 scripts/daily_pipeline.py --stage fallback --date today   # Stage B fallback: drop-untranslated

# (internals) single step / contiguous range / auto-resume — used by --stage and the watchdog
python3 scripts/daily_pipeline.py --date today --step harvest
python3 scripts/daily_pipeline.py --date today --from publish_article --to push
python3 scripts/daily_pipeline.py --date today --resume

# backfill a specific past date
python3 scripts/daily_pipeline.py --date 2026-04-28 --resume
```

`run_steps` automatically demotes any `running` block back to `pending` on load (interrupted runs don't get stuck), and any step that finishes `failed` halts the loop.

## CLI reference — `scripts/translate_helper.py`

Used inside Stage B by the model turn that `scripts/stage_b.py` invokes (via `openclaw agent`) when translation is pending. `daily_pipeline.py --step translate` and `translate_helper.py finalize` are **independent implementations of the same gate** — each calls the skill verifier (`verify_translations.py`) directly and, on rc=0, writes `state.translate=ok` + `mark_played`. They are equivalent in outcome, not one calling the other. Use `translate_helper.py finalize` in Stage B (it alone has `--drop-untranslated`); `--step translate` is the watchdog/resume verify-only path.

```bash
python3 scripts/translate_helper.py pending --date today        # ids still untranslated (retries use this)
python3 scripts/translate_helper.py status                      # progress table
python3 scripts/translate_helper.py write --id N --json-file PATH
python3 scripts/translate_helper.py skip  --id N --reason "..."
python3 scripts/translate_helper.py show  --id N
python3 scripts/translate_helper.py finalize --date today        # the gate (all selected must verify)
python3 scripts/translate_helper.py finalize --date today --drop-untranslated  # deterministic floor: drop stuck ids, ship >=MIN_BRIEFING
```

See `references/translation-workflow.md` for the JSON schema and style rules.

## Watchdog — `scripts/daily_wake.py`

Runs every hour as its own `command` cron (deterministic Python, no model). For each of the last 3 days (newest first):

1. If no `.state.json` and the day is today **and now ≥ 04:00 UTC** → start a fresh `daily_pipeline.py` run (Stage A backstop). Before 04:00 UTC it leaves the fresh harvest to the Stage A cron (so the briefing isn't built from stale, too-early news).
2. If `next_pending(state) == "translate"`, it's **today**, and now ≥ 06:25 UTC → run `translate_helper.py finalize --drop-untranslated` (deterministic; the only translate recovery the watchdog can do), then continue.
3. If `.state.json` exists and `next_pending(state)` returns a step → run `daily_pipeline.py --resume` with a soft 900 s budget.
4. If all 7 steps and both real delivery ids are `ok` → skip. The short-circuit also exits on skill drift and defers when any step is `running`.

**Delivery backstop:** for **today only**, and only **after 07:00 UTC** (Stage D's time), if all 7 steps are `ok` but a delivery is still pending, the watchdog runs `stage_d_delivery.py send` — deterministic, lock-guarded against double-posting, idempotent. This makes delivery as resilient as translation: a transient Stage D send error or a late push is retried on the next hourly tick. The watchdog never broadcasts a **past** day (stale news must not resurface) and never invokes the model.

## Idempotency contract (all steps respect this)

- `harvest.py` — `INSERT OR IGNORE` on `story_hash`; safe to re-run any number of times.
- `select_top.py` — overwrites `daily-selected.json`; the `_skipped` flags survive because `translate_helper.py skip` writes them back.
- `translate_helper.py write` — `UPDATE news_articles SET translated_*` (no INSERT); writing the same id twice just overwrites.
- `publish_article.py --all-pending` — skips slugs that already exist unless `--force`.
- `publish_briefing.py` — overwrites `briefing.md` / `meta.json`; `mark_played` uses the exact selected ids.
- `render_audio.py` — overwrites `audio.mp3`; auto-falls back to MiniMax if Microsoft Edge TTS fails.
- `git_publish.py` — `git pull --rebase` first, then commit only if there are staged changes; double-runs become no-ops.
- `stage_d_delivery.py prepare` — emits only missing deliveries; `record` refuses non-Discord ids and refuses to overwrite a real id unless forced.

## Hard rules — never violate

- Do **not** mark a step `ok` from outside its runner. The runner is the one that knows whether it really succeeded (e.g., audio mp3 ≥ 100 KB, briefing files actually exist).
- Do **not** edit `.state.json` by hand to "skip ahead." If a step is genuinely OK by inspection, run that step's runner with `--force` (where supported); otherwise fix the underlying issue.
- Do **not** add new top-level `state["steps"]` keys without updating `scripts/lib/state.py STEPS`. The list is the source of truth for the orchestrator and watchdog.
- `mark_played` is called by the translate gate (`translate_helper.py finalize` / `daily_pipeline.step_translate`) **and** `publish_briefing.py`, always with the **exact selected ids** (never a broad `WHERE date<=today` — that caused the v1 4/20 duplicate bug). It is intentionally called at the translate gate so a finished-but-not-yet-published day still removes those ids from tomorrow's pool. Do **not** add a broad/date-ranged `mark_played` call anywhere.
