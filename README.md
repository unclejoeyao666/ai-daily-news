# AI Daily News

Daily AI/tech briefing pipeline: RSS harvest, freshness-first selection,
Chinese translation, Astro site publishing, TTS audio, GitHub Pages deploy, and
Discord delivery.

Site: https://unclejoeyao666.github.io/ai-daily-news/

Subscribe: https://unclejoeyao666.github.io/ai-daily-news/rss.xml

## Current workflow

The canonical runbook is:

```text
/Users/unclejoe/.agents/skills/ai-news-workflow/SKILL.md
```

Production is one adapter on the shared Daily News Engine V4. The global
14-job manifest is the only schedule source:

`/Users/unclejoe/.openclaw/scripts/daily-news-v4-crons.json`

AI slots (Europe/Berlin):

| Stage | Local | Role |
|---|---:|---|
| ingest | 06:30 | harvest + minimum-gated immutable selection |
| translate | 06:40 / 07:00 / 07:20 | gated pending-only model slots |
| publish | 07:45 | zero-model fallback, site push, then audio branch |
| deliver | 08:05 | idempotent Discord text/audio parts |
| SLA | 08:55 / 12:00 | deterministic repair, then escalation |

Stage D is the only Discord path. `send` writes an intent before transport and
records only real message IDs; cron announce delivery is not used.

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
python3 scripts/daily_pipeline.py --date today --stage ingest
python3 scripts/newsctl.py snapshot --date today
python3 scripts/translate_helper.py work-items --date today --json
python3 scripts/translate_helper.py finalize --date today
python3 scripts/daily_pipeline.py --date today --stage fallback
python3 scripts/daily_pipeline.py --date today --stage publish
python3 scripts/stage_d_delivery.py send --date today
python3 -m scripts.lib.news_db data/news.db --stats
```

## TTS

Providers are bounded Edge TTS, MiniMax TTS, then local system TTS.
The active renderer is `scripts/render_audio.py`.

## Feeds & open data

The published site exposes its content in open, machine-readable formats so
anyone can subscribe or build on it — no API key, no quota.

| Endpoint | Format | Contents |
|---|---|---|
| `/rss.xml` | RSS 2.0 | Full article body (`content:encoded`), 1200×630 cover (`media:content`), source attribution, tags, and MP3 enclosures for each daily briefing |
| `/feed.json` | JSON Feed 1.1 | Same items as RSS, as JSON |
| `/api/news.json` | JSON | Flat structure: `articles[]` + `briefings[]` + site index |
| `/feeds` | HTML | Human-facing docs: endpoints, field reference, examples |

Each article item carries: Chinese title, Chinese summary, full body HTML
(translation + impact analysis), cover image, original-language title, source
name and URL, Chinese tag labels, and a link to the daily briefing that
included it. Briefing items add the audio enclosure (`length` = real byte
size) so podcast clients can subscribe directly.

Custom metadata lives in the `ainews:` namespace
(`https://unclejoeyao666.github.io/ai-daily-news/ns/ainews/1.0/`), which
standard readers ignore harmlessly.

Implementation lives in `site/src/lib/feeds.ts` (shared data layer),
`site/src/lib/xml.ts` (XML serialisation), `site/src/lib/cover.ts` (cover
cards), and the endpoints under `site/src/pages/`. Feeds are generated at
build time from the content collections, so they always match the published
site. `FEED_LIMIT` / `BRIEFING_FEED_LIMIT` in `feeds.ts` control how many
items each feed publishes.

## Maintenance

- RSS sources: edit `data/sources.json`.
- Tags: edit `data/tags.json`.
- Runtime/schedule behavior belongs to the shared engine/manifest; this project
  owns only domain config and editorial references.
- Do not raw-edit OpenClaw jobs.json; use OpenClaw cron tools.
- Do not force push.
