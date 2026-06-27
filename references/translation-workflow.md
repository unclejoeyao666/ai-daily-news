# Stage B — Translation, Tagging, Audio Script

This is the **cognitive step** of the daily pipeline. The calling Claude session (the OpenClaw agent firing the Stage B cron at 04:30 UTC) does it directly — no external LLM API, no script.

The flow per article is:

1. Read the article's record from `daily-selected.json` (and optionally WebFetch the original — see "WebFetch fallback" below).
2. Translate / synthesize the 5 fields (see "Style rules").
3. Save them to `/tmp/article-<id>.json` and call:
   ```bash
   python3 scripts/translate_helper.py write --id <id> --json-file /tmp/article-<id>.json
   ```
4. Repeat for all 10 articles.
5. Write `daily/<Y>/<Y-M>/<DATE>/audio_script.md` (1500–2500 中文字符, TTS-safe — see "audio_script.md" section).
6. Call `python3 scripts/translate_helper.py finalize --date today` — this runs the `verify_translations.py` hard gate and flips `.state.json` `translate=ok` so Stage C (05:00 UTC) is unblocked.

`translate_helper.py write` validates each payload (required fields, ≤300 char summary, valid 1–3 tag slugs from `data/tags.json`, no URLs in body) and updates SQLite atomically — partial progress survives interruptions because each call commits independently. If you're interrupted mid-batch, run `translate_helper.py status` to see which IDs are still pending and continue from there.

## Inputs

After Stage A (`select_top.py`), `daily-selected.json` at the project root contains exactly 10 articles, each like:

```json
{
  "id": 1404,
  "title": "OpenAI could be making a phone with AI agents, report says",
  "summary": "Supply-chain analyst Kuo claims OpenAI is partnering with MediaTek …",
  "source_id": "techcrunch-ai",
  "source_name": "TechCrunch AI",
  "source_name_cn": "TechCrunch AI 频道",
  "source_url": "https://techcrunch.com/...",
  "published_at": "2026-04-27T14:32:00+00:00",
  "lang": "en",
  "source_categories": ["consumer-app", "industry-trend"],
  "importance": 88
}
```

If `summary` is empty or < 500 characters, fetch the original article first — see "WebFetch fallback" below.

## Industry tag vocabulary (controlled — `industry_tags`)

The 12 valid slugs live in `data/tags.json` (single source of truth, also drives the Astro site sidebar). Every article must carry **1–3** tags from this exact list:

| slug | 中文 | 适用范围 |
|---|---|---|
| `model-release` | 模型发布 | 新版/新模型：GPT, Claude, Gemini, Llama, DeepSeek, Mistral 等 |
| `agent-tools` | 智能体·工具 | Claude Code, Cursor, Devin, AutoGPT 类 agent 与开发工具 |
| `research-paper` | 论文·研究 | arXiv, DeepMind, AI 学术突破, 新算法 |
| `funding-ipo` | 融资·上市 | OpenAI / xAI / Anthropic 等 AI 公司融资、估值、IPO |
| `policy-regulation` | 政策·监管 | EU AI Act, 白宫行政令, 版权诉讼, AI 法规 |
| `chips-infra` | 芯片·算力 | Nvidia, TSMC, 数据中心, AI 训练硬件 |
| `enterprise-app` | 企业应用 | 企业级 AI 落地, SaaS 集成, 生产力工具 |
| `consumer-app` | 消费应用 | ChatGPT, Gemini App, Copilot 等终端用户产品 |
| `open-source` | 开源生态 | HuggingFace, Llama, Mistral, 开源模型与工具链 |
| `safety-alignment` | 安全·对齐 | 越狱, 幻觉, 对齐, 红队, AI 风险与安全 |
| `china-ai` | 中国 AI | MiniMax, 智谱, 月之暗面, DeepSeek, 阿里通义等中国 AI |
| `industry-trend` | 行业趋势 | 综合分析, 市场动态, AI 公司并购, 人事变动 |

Hard rules:

- **1 ≤ len(industry_tags) ≤ 3** (Astro schema enforces this at build time).
- Slugs must match exactly — typos = build failure.
- For Chinese AI lab stories (DeepSeek/MiniMax/智谱/通义/百度/腾讯), always include `china-ai` and one specific tag (`model-release` / `chips-infra` / etc.).
- For pure macro / M&A / personnel stories with no specific product angle, prefer `industry-trend` + one secondary.
- For papers / benchmarks / new algorithms, use `research-paper` (the source story, e.g. "Anthropic's RLHF paper", outranks where it was reported).

## DB writeback (one call per article via `translate_helper.py write`)

Save the translation as a JSON file, then call the helper. **Never write `update_translation` by hand** — the helper validates schema, tag slugs, summary length, and refuses URLs in the body, all of which would otherwise fail the Astro build silently or trip `verify_translations.py`.

```bash
# 1. Compose JSON payload (5 required fields)
cat > /tmp/article-1404.json <<'JSON'
{
  "translated_title": "OpenAI 据传开发 AI 手机：智能体将取代传统应用",
  "translated_summary": "供应链分析师郭明錤透露，OpenAI 正与联发科、高通、立讯精密合作开发一款主打 AI 智能体的手机，目标是用 agent 完全取代传统 App 的交互模式。",
  "translated_body": "## 报道核心\n\nOpenAI 已在过去几个月秘密与 ...\n\n## 硬件细节\n\n据郭明錤的供应链调研 ...\n\n## 产品路径\n\n这台设备的最大变量在于 ...",
  "impact_analysis": "如果 OpenAI 真的在 2027 年推出原生 agent 手机，App Store 的统治可能在数年内被颠覆，Apple 的护城河面临首次正面挑战；同时 Anthropic 和 Google 不会坐视，预计 2026-2027 年会有平行的硬件生态战。",
  "industry_tags": ["consumer-app", "industry-trend"]
}
JSON

# 2. Write to DB (validates + commits atomically)
python3 scripts/translate_helper.py write --id 1404 --json-file /tmp/article-1404.json
```

What `write` checks (and rejects) before touching SQLite:

- All five required fields present and non-empty.
- `translated_summary` length ≤ 300 raw characters (Astro `description` schema cap).
- `translated_body` contains no `http://` / `https://` (`publish_article.py` appends the source-link block automatically; manual URLs duplicate it).
- `industry_tags` is a JSON array of **1–3** valid slugs (slugs loaded from `data/tags.json` at runtime — single source of truth).
- Article id exists in `news_articles`.

`slug` is intentionally not part of the payload — `publish_article.py` auto-generates it from the Chinese title.

Use `translate_helper.py status [--date today]` at any point to see a 10-row table of which IDs are ✅ done / ⚠️ partial / ⏳ pending, plus whether `audio_script.md` exists and is long enough.

To skip an article entirely (rare — only if it turned out to be off-topic on closer read):

```bash
python3 scripts/translate_helper.py skip --id 1404 --reason "actually about EVs, not AI"
```

Skipped articles are excluded from `finalize`'s gate and from `verify_translations.py`. Stage C will not generate an Astro page for them.

## Style rules for the Chinese body

- `translated_title`: ≤ 30 中文字, 一句话点明事件，no decorative book-mark quotes (no `《》【】`).
- `translated_summary`: ≤ 160 中文字, single sentence/段, no Markdown.
- `translated_body`: 250–600 中文字, level-2 headings (`##`) ok, lists ok. **No URLs in body** — `publish_article.py` adds the source-link block automatically. Cover: 报道核心 / 关键细节 / 行业反应 (or 类似的三段式).
- `impact_analysis`: 80–250 字, concrete impact on the AI industry. Mention specific companies (OpenAI / Anthropic / Google / Nvidia / DeepSeek / 智谱 / 百川 …) where relevant. Always end with "对 X 的影响" type angle.

## WebFetch fallback (when source summary is too short)

```python
# Try in order; stop at first that returns enough content.
candidates = [
    f"https://r.jina.ai/{source_url}",
    f"https://markdown.new/{source_url}",
    f"https://defuddle.md/{source_url}",
    source_url,  # direct
]
```

If all fail (paywall, JS-only), translate from the RSS summary alone and add this disclaimer to `translated_body` end:

```
> 原文为付费内容/动态页，本文基于 RSS 摘要翻译，未含全文细节。
```

## audio_script.md — template & rules

Path:

```
daily/<YEAR>/<YEAR-MONTH>/<YYYY-MM-DD>/audio_script.md
```

(`render_audio.py` reads this file via Europe/Berlin local date.)

Template:

```markdown
早上好，欢迎收听 AI 科技每日早报。今天是二零二六年四月二十八日，星期二。今天为您播报十条值得关注的全球 AI 科技动态。

第一条。<中文标题>。<重点 + 影响分析浓缩，约 30-60 秒>。

第二条。<中文标题>。<...>

[第 3-10 条 同样格式]

以上就是今天的全球 AI 科技早报。详情请访问网站 unclejoeyao666 点 github 点 io 斜杠 ai-daily-news。祝您今天工作顺利，明天见。
```

Hard rules (else TTS will read garbage):

- **Total length 8–12 minutes** ≈ **1500–2500 中文字符**.
- **No Markdown headings, no `**bold**`, no `*italic*`, no list bullets.** `render_audio.py` calls `sanitize_for_tts()` which strips them, but the script reads better when the source is already plain.
- **No URLs.** Pronounce them as "<domain> 点 com" if absolutely required.
- **Numbers and dates in Hanzi** (e.g. "二零二六年", "百分之七", "一百一十亿美元", "GPT 五"). TTS reads "2026" as digits.
- **English product names stay in English ASCII** (TTS reads them naturally): `OpenAI`, `Claude`, `Gemini`, `DeepSeek`, `Anthropic`, `Nvidia`, `H100`, `Llama 3`. But spell out long acronyms (LLM → "L L M" or "大语言模型").
- **Em dashes / ellipses → 中文逗号或句号**. Avoid `—` `–` `…`.
- **Mark the beginning of each story** with "第N条。" so the listener can mentally segment.
- **Read the source name in Chinese** (use `source_name_cn`) when the article is from an English outlet.

After writing, verify length:

```bash
DATE=$(TZ='Europe/Berlin' date +%Y-%m-%d)
wc -m "daily/${DATE:0:4}/${DATE:0:7}/$DATE/audio_script.md"
```

Should print 1500–2500. `verify_translations.py` (run by `translate_helper.py finalize`) enforces ≥ 800 as a sanity floor and will block Stage C if the script is too short.

## Closing the stage with `finalize`

Once all 10 articles are written and `audio_script.md` is in place:

```bash
python3 scripts/translate_helper.py finalize --date today
```

This:

1. Reloads `daily-selected.json` and skips any rows marked `_skipped`.
2. Re-checks every active row in SQLite for complete translation + valid tags.
3. Confirms `audio_script.md` exists and is ≥ 800 chars.
4. Runs `/Users/unclejoe/.agents/skills/ai-news-workflow/scripts/verify_translations.py` (the hard gate — 1–3 valid tags from `data/tags.json`, summary ≤ 300, source_url valid).
5. Writes `.state.json` → `translate=ok` (so Stage C cron at 05:00 sees the green light) on success, or → `translate=pending` with `pending_ids` on partial completion (so the next Stage B fire resumes from the same point).

**Do not skip finalize** — Stage C's `daily_pipeline.py --from publish_article --to push` won't run if it sees `translate != ok`, and the watchdog can't fill in cognitive work.

## Common pitfalls

- Forgetting to convert numbers to Hanzi → TTS reads "GPT-5 in 2026" as "G P T dash five in two zero two six".
- Adding a URL inline → TTS reads "h-t-t-p-s-colon-slash-slash".
- Picking too many tags (>3) → Astro build fails with `tags: Array must contain at most 3 element(s)`.
- Picking a tag not in `data/tags.json` → Astro build fails with `tags.0: Invalid enum value`.
- Leaving `translated_summary` > 300 chars → Astro build fails with `description: String must contain at most 300 character(s)`.
- Writing impact analysis that is generic ("将对行业产生重大影响") instead of naming specific companies + concrete mechanisms → defeats the purpose of the column.
