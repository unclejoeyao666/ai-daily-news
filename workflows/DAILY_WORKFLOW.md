# AI Daily News — 每日工作流

> 由本地 OpenClaw 在 Europe/Berlin 06:00 触发；总耗时约 5–15 分钟（视新闻条数和翻译长度）。

## 7 步流水线

```
1. 抓取 RSS    → 入 SQLite
2. 选篇 Top10  → daily-selected.json
3. AI 翻译     → 写回 DB（translated_*）+ 生成 audio_script.md
4. 渲染文章    → site/src/content/articles/*.md
5. 渲染简报    → site/src/content/briefings/<date>.md + daily/<date>/{briefing.md, meta.json}
6. 合成音频    → daily/<date>/audio.mp3 + site/public/audio/<date>.mp3
7. 推送        → git pull/add/commit/push → GH Action 自动部署
```

## 完整命令序列

```bash
cd /Users/unclejoe/Media_Workspace/ai-daily-news

# 1. 抓取
python3 scripts/harvest.py

# 2. 选篇
python3 scripts/select_top.py --count 10

# 3. AI 翻译（OpenClaw 在自己的会话内做的认知工作；不调外部 API）
#   - 读 daily-selected.json 的每条
#   - WebFetch 原文（必要时；正文 < 500 字符或付费墙时降级）
#   - 翻译标题 / 全文 / 摘要 + 写影响分析 + 选 1-3 个 industry_tags
#   - 调用 NewsDB.update_translation(...) 写回 DB
#   - 生成 daily/<YYYY>/<YYYY-MM>/<DATE>/audio_script.md（朗读串稿）

# 4. 渲染文章
python3 scripts/publish_article.py --all-pending

# 5. 渲染简报
python3 scripts/publish_briefing.py --date today

# 6. 音频合成
python3 scripts/render_audio.py --date today

# 7. 推送
python3 scripts/git_publish.py --date today
```

每个脚本支持 `--date YYYY-MM-DD` 参数，幂等可重跑。

## 标签规则（步骤 3 必须遵守）

合法标签 slug 由 [`data/tags.json`](../data/tags.json) 定义（可扩展）：

| slug | 中文 |
|---|---|
| `model-release` | 模型发布 |
| `agent-tools` | 智能体·工具 |
| `research-paper` | 论文·研究 |
| `funding-ipo` | 融资·上市 |
| `policy-regulation` | 政策·监管 |
| `chips-infra` | 芯片·算力 |
| `enterprise-app` | 企业应用 |
| `consumer-app` | 消费应用 |
| `open-source` | 开源生态 |
| `safety-alignment` | 安全·对齐 |
| `china-ai` | 中国 AI |
| `industry-trend` | 行业趋势 |

每篇必须 1–3 个标签，写到 `news_articles.industry_tags` 字段（JSON 数组）。
增加新标签只需编辑 `data/tags.json` 并重跑 `npm run build`。

## audio_script.md 模板

```markdown
早上好，欢迎收听 AI 科技每日早报。今天是 二零二六 年 四 月 二十八 日，星期X。

今天为您播报 十 条值得关注的 AI 新闻。

第一条。<中译标题>。
<重点 + 影响分析浓缩，约 30-60 秒>。

第二条。<中译标题>。
<...>

[第 3-10 条]

以上就是今天的简报。详情请访问网站 unclejoeyao666 点 github 点 io 斜杠 ai-daily-news。
祝您今天工作顺利，明天见。
```

要点：
- 总长度目标 8-12 分钟（约 1500-2500 中文字符）
- 不要写 Markdown 标题（render_audio.py 会 strip）
- 不要嵌入 URL（TTS 会读出 https）
- 数字与日期写汉字（TTS 更自然）

## DB 写入示例（步骤 3 用）

```python
from scripts.lib.news_db import NewsDB

with NewsDB('data/news.db') as db:
    db.update_translation(
        article_id=row['id'],
        translated_title="OpenAI 发布 GPT-5 多模态模型",
        translated_summary="新一代旗舰模型，支持 1M token 上下文……（≤160 字符）",
        translated_body="# 中文全文 Markdown\n\n……",
        impact_analysis="# 对 AI 行业的影响\n\n……（2-3 段）",
        industry_tags=["model-release", "consumer-app"],  # 1-3 个
        # slug 留空，publish_article.py 会自动生成 + 检查唯一
    )
```

## Discord 投递（OpenClaw 的另一个 cron）

读 `daily/<YYYY>/<YYYY-MM>/<DATE>/`：
- `briefing.md` — Markdown 文字简报（含网页链接 + 音频链接）
- `audio.mp3` — 附件
- `meta.json` — 解析 `article_slugs` / `briefing_url` / `audio_url`

推送到 Discord 频道 `#fanli-news-daily` (channel id `1490344209847287830`)。

## 失败重入

任何步骤失败：
1. 修复问题
2. 从失败步骤往后重跑（脚本都是 `--date YYYY-MM-DD` 幂等）
3. 重跑步骤 7（git_publish）会先 `git pull --rebase`

如 GH Action build 失败：
```bash
cd site && npm run build
```
本地复现，多半是 frontmatter schema 校验或标签 slug 不在 `data/tags.json`。

## 监测

- DB 健康：`python3 -m scripts.lib.news_db data/news.db --stats`
- 站点状态：`curl -sI https://unclejoeyao666.github.io/ai-daily-news/`
- 最近 5 期 broadcast_log：
  ```bash
  sqlite3 data/news.db "SELECT broadcast_date, article_count FROM broadcast_log ORDER BY broadcast_date DESC LIMIT 5;"
  ```
- 最近 GH Action 运行：`gh run list --limit 5`

## 文件路径速查

| 路径 | 用途 |
|---|---|
| `data/news.db` | 主 SQLite 库（进版本控制） |
| `data/sources.json` | RSS 源清单 |
| `data/tags.json` | 行业标签分类（可扩展） |
| `daily/<Y>/<Y-M>/<DATE>/briefing.md` | Discord 文字简报 |
| `daily/<Y>/<Y-M>/<DATE>/audio.mp3` | TTS 成品 |
| `daily/<Y>/<Y-M>/<DATE>/audio_script.md` | TTS 源稿 |
| `daily/<Y>/<Y-M>/<DATE>/meta.json` | 元信息（slug 列表 / URL） |
| `site/src/content/articles/<slug>.md` | 文章详情页 |
| `site/src/content/briefings/<DATE>.md` | 简报集合页 |
| `site/public/audio/<DATE>.mp3` | 站内音频镜像（可直链） |
| `daily-selected.json` | 步骤 2-3 中间态（gitignored） |
| `archive/v1/` | v1 历史资料（不再使用） |
