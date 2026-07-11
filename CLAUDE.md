# AI Daily News — project memory

Current system: RSS harvest -> fresh selection -> cognitive Chinese translation
-> Astro article/briefing publish -> TTS audio -> GitHub Pages push -> Discord
delivery.

Canonical runbook:

```text
/Users/unclejoe/.agents/skills/ai-news-workflow/SKILL.md
```

## Active responsibilities

Stage B is the only cognitive stage. Use:

```bash
python3 scripts/translate_helper.py work-items --date today --json
python3 scripts/translate_helper.py write --id <ID> --json-file /tmp/article-<ID>.json
python3 scripts/translate_helper.py finalize --date today
```

Each translation JSON must contain:

- translated_title: concise Chinese title.
- translated_summary: short Chinese summary within schema limits.
- translated_body: 250-600 Chinese characters, factual, no URLs.
- impact_analysis: why this matters and to whom.
- industry_tags: 1-3 valid slugs from data/tags.json.

Do not write the audio script; finalize creates it deterministically.

Stage D is not manual prose delivery. Normal operation uses:

```bash
python3 scripts/stage_d_delivery.py send --date today
```

`record`/`clear` are audited operator recovery commands for an ambiguous
outbox; never use them as the routine send flow.

## Coding conventions

- Python: from __future__ import annotations, pathlib.Path, argparse.
- Scripts accept --date where date-specific.
- DB writes should use project helpers or translate_helper.py, not raw UPDATE
  for normal workflow.
- State writes go through scripts/lib/state.py helpers.
- Do not raw-edit ~/.openclaw/cron/jobs.json.
- Do not use cron announce delivery for public news.
- Do not force push.
- Do not modify archive/ unless explicitly working on historical files.

## Common checks

```bash
python3 scripts/daily_pipeline.py --date today --status
bash /Users/unclejoe/.agents/skills/ai-news-workflow/scripts/check_skill_drift.sh
python3 /Users/unclejoe/.agents/skills/ai-news-workflow/scripts/health.py --date today
```
