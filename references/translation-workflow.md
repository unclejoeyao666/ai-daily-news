# AI Daily News translation contract

This is the pipeline's only cognitive work. Process only IDs returned for the
explicit run date:

```bash
python3 scripts/translate_helper.py work-items --date DATE --json
```

This single compact bundle contains only pending items and the valid tag slugs;
do not call `show` once per article. If `pending_count` is zero, generate
nothing and run only `finalize`.

## Per pending article

Use the selected record and stored source text. Fetch the original only when
the available facts are genuinely insufficient; do not spend context on
routine enrichment or invent paywalled details.

Produce exactly:

```json
{
  "translated_title": "简洁中文标题",
  "translated_summary": "单段中文摘要",
  "translated_body": "中文正文",
  "impact_analysis": "对 AI 行业的具体影响",
  "industry_tags": ["valid-slug"]
}
```

Rules:

- Preserve facts, attribution, uncertainty, dates, amounts, and company names.
- Use a factual title without clickbait or decorative punctuation.
- Summary is plain text within the configured 300-character cap.
- Body explains the event and material details; do not put URLs in it.
- Impact analysis states a concrete mechanism, affected actors, and likely
  consequence. Clearly separate inference from reported fact.
- Choose 1–3 exact slugs from `data/tags.json`; never invent one.
- For a Chinese AI company, include `china-ai` plus the most specific second
  tag when justified.
- Do not generate an audio script, slug, page Markdown, or delivery copy.

Write through the helper only:

```bash
python3 scripts/translate_helper.py write \
  --date DATE --id ID --json-file /tmp/ai-news-ID.json
```

Never update SQLite, checkpoints, selection flags, `.state.json`, or site
files directly. Fix validation errors in the payload and retry.

Use `skip` only for a proven off-topic item—not for timeout, short source,
provider error, or difficult translation:

```bash
python3 scripts/translate_helper.py skip \
  --date DATE --id ID --reason "specific editorial reason"
```

## Finish

Re-run `pending`; when every item is translated or explicitly skipped:

```bash
python3 scripts/translate_helper.py finalize --date DATE
```

Finalize verifies content/tags and deterministically assembles
`audio_script.md`. After interruption, resume only returned pending IDs;
valid checkpoints are idempotent.
