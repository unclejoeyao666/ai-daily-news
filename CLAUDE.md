# AI Daily News — Claude 项目记忆

每日全球 AI 科技自动播报系统：抓取 → 翻译 → 站点发布 → 音频 → Discord。Python 7 步流水线 + Astro 静态站。
**OpenClaw 06:00 (Europe/Berlin) 触发**；Claude（这就是你）的角色集中在第 3 步翻译/打标。

## 必读上下文

- 项目结构与命令一览：@README.md
- 每日 7 步流水线运行时约定：@workflows/DAILY_WORKFLOW.md
- v2 架构设计（决策背景）：@docs/superpowers/specs/2026-04-28-ai-daily-news-v2-design.md

## 你的核心角色（第 3 步）

OpenClaw 跑完 step 1（`harvest.py`）和 step 2（`select_top.py`）后，会唤醒你处理 `daily-selected.json`。每条文章你要：

1. **必要时 WebFetch 原文**——只在 summary < 500 字符或被付费墙截断时；其余情况直接用 DB 里的 `summary`
2. **翻译三段**：`title_zh` / `body_zh`（全文译）/ `summary_zh`（120–180 字）
3. **写一条影响分析**`impact_zh`：≤ 100 字，回答"对哪个领域意味着什么"
4. **打 1–3 个标签**，slug 必须来自 `data/tags.json`，合法值：
   `model-release` / `agent-tools` / `research-paper` / `funding-ipo` / `policy-regulation` / `chips-infra` / `enterprise-app` / `consumer-app` / `open-source` / `safety-alignment` / `china-ai` / `industry-trend`
5. **写回 DB**：`from scripts.lib.news_db import NewsDB; db.update_translation(article_id, ...)`
6. **生成朗读串稿**`daily/<YYYY>/<YYYY-MM>/<DATE>/audio_script.md`（中文播报口语化）

## 编码与风格约定

- Python 一律 `from __future__ import annotations`、`pathlib.Path`、`argparse`，**不用 click**
- 路径用 `ROOT = Path(__file__).resolve().parent.parent` 锚定项目根，不假设 cwd
- 新脚本支持 `--date YYYY-MM-DD`（默认 today）；幂等可重跑
- DB 操作走 `scripts/lib/news_db.NewsDB`，不直接写 SQL
- 时间戳一律 ISO 8601 UTC（DB 存）/ Asia/Shanghai 展示（站点）
- 日期目录命名严格 `daily/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>/`（注意中间是 `YYYY-MM` 不是 `MM`）
- shell 脚本必须 `set -euo pipefail`

## 不要做的事

- **不要改 `archive/v1/`**——v1 历史代码已停用，仅留作参考
- **不要直接改 `data/news.db`**——通过 `NewsDB` API 走，否则 FTS 索引会脏
- **不要 `git add -A`**——`.openclaw-secrets.json`、`*.draft`、SQLite WAL 必须排除（`.gitignore` 已覆盖大部分，但加文件时还是 explicit）
- **不要在脚本里写绝对路径**（除了 README 里明确列出的 TTS 脚本 `/Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py`）
- **不要为单次任务建抽象**——这是个数据流水线，三处类似 ≠ 该抽函数

## 常用命令速查

```bash
# 数据库统计
python3 -m scripts.lib.news_db data/news.db --stats

# 全文搜索
sqlite3 data/news.db "SELECT title, source_name FROM news_articles \
  WHERE id IN (SELECT rowid FROM news_fts WHERE news_fts MATCH 'gpt OR claude') LIMIT 10;"

# 单步重跑（每个脚本都接 --date）
python3 scripts/publish_briefing.py --date 2026-05-06
python3 scripts/render_audio.py --date 2026-05-06

# 整条流水线重放（幂等）
python3 scripts/daily_pipeline.py --date 2026-05-06
```

## 维护者与历史

- 当前 owner：Fanli（OpenClaw agent）。从 Shell 接管于 2026-04-05；v2 升级 2026-04-28
- 这个项目通常由 OpenClaw 自动跑；人工介入点是改源（`data/sources.json`）、改标签（`data/tags.json`）、修流水线 bug
