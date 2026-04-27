# 🤖 AI Daily News — 每日 AI 科技早报

每日全球 AI 科技自动播报系统 — 抓取 → 翻译 → 站点发布 → 音频 → Discord。

**站点**：[https://unclejoeyao666.github.io/ai-daily-news/](https://unclejoeyao666.github.io/ai-daily-news/)
**架构设计**：[docs/superpowers/specs/2026-04-28-ai-daily-news-v2-design.md](docs/superpowers/specs/2026-04-28-ai-daily-news-v2-design.md)
**每日工作流**：[workflows/DAILY_WORKFLOW.md](workflows/DAILY_WORKFLOW.md)

## 项目结构

```
data/         SQLite 新闻数据库 + RSS 源 + Tag 配置
scripts/      Python 流水线脚本（lib + 7 步主脚本 + migrate）
site/         Astro 静态站点（含 Pagefind 全文搜索）
daily/        每日成品文件包（briefing.md / audio_script.md / audio.mp3 / meta.json）
.github/      GitHub Actions CI（部署到 GH Pages）
docs/         设计文档与执行计划
workflows/    OpenClaw 每日 runbook
archive/v1/   v1 历史代码与数据（已停用）
```

## 覆盖范围

模型发布 · 智能体与工具 · 研究论文 · 融资上市 · 政策监管 · 芯片算力 · 企业应用 · 消费应用 · 开源生态 · 安全与对齐 · 中国 AI · 行业趋势

数据来源：20 个全球权威 RSS 源（OpenAI / Anthropic / DeepMind / Meta AI / Mistral 一手 + TechCrunch / Verge / VentureBeat / Wired / MIT Tech Review / Bloomberg / Reuters / Hacker News 等）。

## 运行方式

由本地 OpenClaw 每天 06:00 (Europe/Berlin) 触发，按 `workflows/DAILY_WORKFLOW.md` 7 步流水线执行。

```bash
python3 scripts/harvest.py            # 1. RSS → DB
python3 scripts/select_top.py         # 2. Top 10 → daily-selected.json
# 3. (Claude 翻译/打标，写回 DB + audio_script.md)
python3 scripts/publish_article.py --all-pending   # 4. → site/articles/
python3 scripts/publish_briefing.py --date today   # 5. → briefings/ + daily/<date>/
python3 scripts/render_audio.py --date today       # 6. TTS → audio.mp3
python3 scripts/git_publish.py --date today        # 7. commit + push
```

GitHub Actions 自动接管：Astro 构建 + Pagefind 索引 + 部署到 GitHub Pages。

## 添加新的 RSS 源 / 标签

- **RSS 源**：编辑 `data/sources.json`，下次 `harvest.py` 运行时自动 import
- **标签**：编辑 `data/tags.json`，下次 `npm run build` 自动反映到站点

## 数据库

```bash
# 查看统计
python3 -m scripts.lib.news_db data/news.db --stats

# 全文搜索
sqlite3 data/news.db "SELECT title, source_name FROM news_articles WHERE id IN \
  (SELECT rowid FROM news_fts WHERE news_fts MATCH 'gpt OR claude') LIMIT 10;"
```

## TTS

主力：Microsoft Edge TTS（`zh-CN-XiaoxiaoNeural`，免费）。
备份：MiniMax TTS（`male-qn-qingse`）。
合成脚本：`/Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py`。

## 维护者

Fanli (@fanli) · 接管自 Shell · 2026-04-05 → v2 升级 2026-04-28
