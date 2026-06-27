# Verification Contract

The single source of truth for **what each verifier checks**, **what input it expects**, and **what it returns**. Used by `daily_pipeline.py`, `daily_wake.py`, `health.py`, and operator manual runs — all should call the same scripts with the same arguments.

## Invariant: verifiers are pure judges

A verifier reads state, makes a determination, prints it, and exits. **Verifiers MUST NOT write `.state.json`** — that's the caller's job. This separation lets the same verifier run from CI, smoke tests, and the orchestrator without pulling state-writing logic into every context.

The single exception is `translate_helper.py finalize`, which is a *step closer* (not a verifier) — it runs the verifier and writes state on success. Use `finalize` when you need a one-shot Stage B closure; use `verify_translations.py` directly when you only need the judgment.

## Standard contract

Each verifier supports:

```
python3 <verifier> [--date YYYY-MM-DD]
```

`--date` defaults to `today` (Europe/Berlin).

**stdout:**

- success: a single line of JSON `{"stats": {...}}`
- failure: a single line of JSON `{"errors": [...], "stats": {...}}`

**stderr:** human-readable progress (only when running interactively).

**exit code:**

- `0` — all checks passed
- `1` — one or more checks failed
- `2` — environment problem (DB missing, ffprobe absent etc.)

`verify_translations.py` is the legacy exception — it prints human-readable text instead of JSON. `health.py`'s `run_verifier` falls back to text scraping for that one. New verifiers should always print JSON.

## Per-verifier specifics

### `verify_harvest.py`

**Path:** `/Users/unclejoe/.agents/skills/ai-news-workflow/scripts/verify_harvest.py`

**Asks:** "Did harvest pull in real new articles today?"

**Checks:**
- `news_articles` rows with `discovered_at >= <date>` ≥ `--min-new` (default 10)
- `sources` rows with `enabled = 1` ≥ `--min-sources` (default 15)

**Stats:** `{new_articles, active_sources, date}`

### `verify_select.py`

**Path:** `/Users/unclejoe/.agents/skills/ai-news-workflow/scripts/verify_select.py`

**Asks:** "Did select_top pick exactly N fresh articles?"

**Source priority:** `daily/<date>/meta.json` (historical) → `daily-selected.json` (today only).

**Checks:**
- `articles` array length == `--count` (default 10)
- every id resolves to a row in `news_articles`
- every row's `COALESCE(published_at, discovered_at)` is within `--max-age-days` (default 14) of the target date

The `published_at` field matters because RSS feeds occasionally re-emit old entries with new fetch timestamps — `discovered_at` alone wouldn't catch the 2025-October entries that polluted 2026-05-07's briefing.

**Stats:** `{date, selected_count, cutoff}`

### `verify_translations.py`

**Path:** `/Users/unclejoe/.agents/skills/ai-news-workflow/scripts/verify_translations.py`

**Asks:** "Did Stage B fill all 4 translation fields with non-empty content?"

**Source priority:** `daily/<date>/meta.json` → `daily-selected.json`.

**Checks (for each id in selection):**
- `translated_title`, `translated_summary`, `translated_body`, `impact_analysis` all non-empty
- `translated_summary` ≤ 300 chars (Astro `description.max(300)`)
- `source_url` is `http(s)://...`
- `industry_tags` is a 1–3 element JSON array of slugs from `data/tags.json`

Plus:
- `daily/<date>/audio_script.md` exists and is ≥ 800 chars

**Output:** human-readable (legacy). Will be JSON-ified once SKILL.md is rewired to read JSON.

### `verify_publish.py`

**Path:** `/Users/unclejoe/.agents/skills/ai-news-workflow/scripts/verify_publish.py`

**Asks:** "Did publish_article + publish_brief produce real Astro pages?"

**Source priority:** `daily/<date>/meta.json` → `daily-selected.json`.

**Checks (per article):**
- DB row has `slug`
- `site/src/content/articles/<slug>.md` exists
- frontmatter has `title`, `description` (≤ 300), `pubDate`
- markdown body has ≥ `--min-body` CJK characters (default 150) — protects against the "fallback to English summary" failure mode

Plus:
- `site/src/content/briefings/<date>.md` exists

**Stats:** `{date, articles_checked, articles_ok, selection_source}`

### `verify_audio.py`

**Path:** `/Users/unclejoe/.agents/skills/ai-news-workflow/scripts/verify_audio.py`

**Asks:** "Is the day's audio listenable?"

**Checks:**
- `site/public/audio/<date>.mp3` exists
- size ≥ `--min-size-kb` (default 200)
- duration ≥ `--min-duration` seconds (default 60) — uses `ffprobe`; skipped if absent
- `daily/<date>/audio_script.md` exists and ≥ `--min-script-chars` (default 1500)

**Stats:** `{date, mp3_size_kb, mp3_duration_seconds, audio_script_chars}`

### `stage_d_delivery.py` (delivery helper; not a verifier)

**Path:** `/Users/unclejoe/Media_Workspace/ai-daily-news/scripts/stage_d_delivery.py`

**Role:** Deterministic Stage D send/prepare/record/clear interface. `send` is
the path the cron uses: it builds payloads, sends via `openclaw message send
--json`, and records the real Discord message ids.

**Send (cron path):**

```bash
python3 scripts/stage_d_delivery.py send --date today            # send + record
python3 scripts/stage_d_delivery.py send --date today --dry-run  # preview only
```

**Prepare (inspect payload without sending):**

```bash
python3 scripts/stage_d_delivery.py prepare --date today --json-out /tmp/ai-news-stage-d.json
```

Returns `status=skip` when push is not ok, `status=complete` when both
delivery records have real Discord message ids, or `status=ready` with the
exact text/audio payloads to send.

**Record:**

```bash
python3 scripts/stage_d_delivery.py record --date <DATE> --key discord_text --message-id <ID> --chars <CHARS>
python3 scripts/stage_d_delivery.py record --date <DATE> --key discord_audio --message-id <ID> --mp3-size <BYTES>
```

It writes `state.deliveries.<key>`, refuses non-snowflake ids such as
`cron-announce`, and returns rc=2 if a real id is already recorded and
`--force` was not passed.

## When to add a new verifier

1. The pipeline gained a step that has a measurable success criterion.
2. The verification can be expressed as a deterministic Python check (no LLM).
3. Its target failure mode has actually happened in production.

Don't add speculative verifiers. Each one can turn an operator health check
red, so cost and noise compound.

## When a verifier reports red

1. Read its stderr for the first 3 errors — usually that's the root cause.
2. Check `recovery-playbook.md` for the symptom-by-symptom fix table.
3. Fix the underlying state (DB rows, .state.json, file regeneration) and re-run the verifier.
4. Once green, the orchestrator (or operator manual `/cron run`) can advance the pipeline.
