# AI Daily News

Daily AI/tech briefing pipeline: RSS harvest, freshness-first selection,
Chinese translation, Astro site publishing, TTS audio, GitHub Pages deploy, and
Discord delivery.

Site: https://unclejoeyao666.github.io/ai-daily-news/

## Current workflow

The canonical runbook is:

```text
/Users/unclejoe/.agents/skills/ai-news-workflow/SKILL.md
```

Production uses 8 OpenClaw cron jobs:

| Stage | UTC | Role |
|---|---:|---|
| A | 04:00 | harvest + select |
| B | 04:30 | cognitive translation |
| B retry | 05:15 | pending-only translation retry |
| B deep | 06:00 | final cognitive retry |
| B fallback | 06:25 | deterministic drop-untranslated floor |
| C | 06:30 | publish article/brief/audio/push |
| D | 07:00 | Discord text + audio delivery |
| Watchdog | hourly | deterministic resume |

Stage D is the only public delivery path. It uses
`scripts/stage_d_delivery.py prepare`, OpenClaw message(action="send"), then
`scripts/stage_d_delivery.py record` with real Discord message ids. Cron
announce delivery is not used.

## Project structure

```text
data/       SQLite news database, RSS sources, tag config
scripts/    Python pipeline, watchdog, Stage D helper, maintenance scripts
site/       Astro static site and Pagefind search
daily/      daily outputs: briefing.md, audio_script.md, audio.mp3, meta.json, .state.json
.github/    GitHub Actions deploy workflow
archive/    inactive historical code only
docs/       historical design notes, not the current runbook
```

## Useful commands

```bash
cd /Users/unclejoe/Media_Workspace/ai-daily-news

python3 scripts/daily_pipeline.py --date today --status
python3 scripts/daily_pipeline.py --date today --from harvest --to select
python3 scripts/translate_helper.py pending --date today
python3 scripts/translate_helper.py finalize --date today
python3 scripts/daily_pipeline.py --date today --from publish_article --to push
python3 scripts/stage_d_delivery.py prepare --date today
python3 -m scripts.lib.news_db data/news.db --stats
```

## TTS

Primary provider: Microsoft Edge TTS. Fallback provider: MiniMax TTS.
The active renderer is `scripts/render_audio.py`.

## Maintenance

- RSS sources: edit `data/sources.json`.
- Tags: edit `data/tags.json`.
- Workflow docs and cron payloads: update the ai-news-workflow skill.
- Do not raw-edit OpenClaw jobs.json; use OpenClaw cron tools.
- Do not force push.
