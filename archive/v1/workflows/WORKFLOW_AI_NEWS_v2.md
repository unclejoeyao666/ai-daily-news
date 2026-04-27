# AI 科技早报 — 工作流文档 v2
# 数据库驱动版（查重 + 订阅源管理）

> 本文档记录 AI 科技早报数据库驱动工作流，替代旧版 Tavily 盲搜索流程。
> Fanli | 2026-04-14 验证通过

---

## 核心改进

| | 旧版 (v1) | 新版 (v2) |
|---|---|---|
| **信息来源** | 每次盲目 Tavily 搜索 | 精选订阅源 + 按需补充搜索 |
| **查重机制** | 无，导致重复播报 | SQLite 哈希查重，已播不重复 |
| **播放状态** | 无记录 | `unplayed / played / archived` |
| **订阅源** | 每次临时指定关键词 | 20 个精选 RSS 订阅源固化 |
| **历史积累** | 无 | 新闻库持续沉淀，价值可追溯 |

---

## 数据库

**路径：** `/Users/unclejoe/Media_Workspace/ai-daily-news/db/news.db`

**核心表：**
- `sources` — 订阅源清单（20 个 RSS 源）
- `news_articles` — 新闻主库（带 story_hash 查重 + 播放状态）
- `broadcast_log` — 每日播报日志

**DB 操作脚本：**
- `db/news_db.py` — Python DB 操作层
- `db/harvest.py` — RSS 抓取脚本
- `db/sources.json` — 精选订阅源清单

---

## 工作流概览

```
04:00 UTC (06:00 Berlin)          05:00 UTC (07:00 Berlin)          05:30 UTC (07:30 Berlin)
┌────────────────────────────┐    ┌────────────────────────────┐    ┌────────────────────────────┐
│   步骤 1                    │    │   步骤 2-3                 │    │   步骤 4                   │
│   RSS 订阅源抓取            │    │   从 DB 读 unplayed 新闻   │    │   MiniMax TTS 语音生成     │
│   harvest.py → DB          │    │   生成文字早报 → 发送      │    │   → 保存 → 发送 Discord   │
│   自动查重入库              │    │   标记 played             │    └────────────────────────────┘
└────────────────────────────┘    └────────────────────────────┘
```

---

## 每日三个文件（最终交付物）

| 文件 | 说明 |
|---|---|
| `YYYY/YYYY-MM/YYYY-MM-DD.md` | 完整新闻存档 |
| `YYYY/YYYY-MM/YYYY-MM-DD_audio_script.md` | 播报脚本 |
| `YYYY/YYYY-MM/YYYY-MM-DD_audio.mp3` | 音频文件 |

---

## 步骤详解

### 步骤 1 — RSS 订阅源抓取（04:00 UTC）

**目的：** 从精选订阅源抓取最新新闻，自动查重入库

**执行命令：**
```bash
cd /Users/unclejoe/Media_Workspace/ai-daily-news/db
python3 harvest.py /Users/unclejoe/Media_Workspace/ai-daily-news/db/news.db sources.json
```

**订阅源清单（20 个）：**

| 源 | 类型 | 说明 |
|---|---|---|
| TechCrunch AI | RSS | AI 初创与大公司动态 |
| The Verge AI | RSS | AI 产品与文化 |
| VentureBeat AI | RSS | 深度 AI 技术与产业 |
| Ars Technica Technology Lab | RSS | AI 技术深度报道 |
| MIT Technology Review | RSS | AI 研究与社会影响 |
| Wired AI | RSS | AI 商业与文化 |
| Bloomberg Technology | RSS | AI 投融资与市场 |
| Reuters Technology | RSS | 科技新闻 |
| TechCrunch (综合) | RSS | 综合科技 |
| The Verge (综合) | RSS | 综合科技产品 |
| Hacker News | RSS | 开发者社区热点 |
| VentureBeat (综合) | RSS | 综合创业 |
| OpenAI Blog | RSS | OpenAI 官方发布 |
| Anthropic News | RSS | Anthropic 官方发布 |
| Google DeepMind Blog | RSS | DeepMind 研究 |
| Meta AI Blog | RSS | Meta AI 研究 |
| Mistral AI News | RSS | Mistral 最新动态 |
| TechCrunch Startups | RSS | AI 初创融资 |
| Axios Tech | RSS | 简洁高效科技新闻 |
| Semafor Tech | RSS | AI 政策与商业 |

**查重逻辑：** SHA256(title + source_name)，已存在则跳过

**重要性评分：** 基于关键词匹配自动打分 0-10

---

### 步骤 2 — 从数据库读取待播新闻（05:00 UTC）

**执行逻辑：**
1. 从 `news_db.get_unplayed_articles(limit=10)` 读取未播新闻
2. 按 `importance DESC, published_at DESC` 排序
3. 若 DB 中不足 10 条，从 Tavily 补充搜索（补充搜索也自动入库查重）

**补充搜索关键词（当 DB 条目不足时）：**
```
"Claude Code OR Anthropic news today"
"OpenAI GPT news today"
"MiniMax AI update today"
"large language model breakthrough today"
"AI agent OpenClaw news today"
```

---

### 步骤 3 — 生成文字早报、存档、发送 Discord

**格式：** 同 v1（10 条精选，含标题/摘要/来源/链接）

**存档路径：** `daily/YYYY/YYYY-MM/YYYY-MM-DD.md`

**发送 Discord：** 频道 `1490344209847287830`（`#fanli-news-daily`）

**标记 played：** `news_db.mark_played(article_ids, date)`

---

### 步骤 4 — 语音播报（05:30 UTC）

同 v1，从存档的 `_audio_script.md` 读取并生成 TTS

---

## 数据库管理命令

```bash
# 初始化数据库
cd /Users/unclejoe/Media_Workspace/ai-daily-news/db
python3 news_db.py /Users/unclejoe/Media_Workspace/ai-daily-news/db/news.db --init

# 导入订阅源
python3 news_db.py /path/to/news.db --import-sources sources.json

# 查看统计
python3 news_db.py /path/to/news.db --stats

# 迁移历史文件（一次性）
python3 news_db.py /path/to/news.db --backfill /Users/unclejoe/Media_Workspace/ai-daily-news/daily

# 手动抓取订阅源
python3 harvest.py /path/to/news.db sources.json
```

---

## Cron 任务配置（v2）

| | Harvest | 文字早报 | 音频早报 |
|---|---|---|---|
| **Job ID** | `NEW_UUID` | `3c687e42...`（更新 prompt） | `3d981359...`（更新 prompt） |
| **Schedule** | `0 4 * * *` UTC | `0 5 * * *` UTC | `30 5 * * *` UTC |
| **Berlin 时间** | 06:00 | 07:00 | 07:30 |
| **Agent** | fanli | fanli | fanli |
| **模式** | isolated agentTurn | isolated agentTurn | isolated agentTurn |

---

## 升级记录

| 日期 | 变更内容 |
|---|---|
| 2026-04-14 | v2：新增 SQLite 数据库查重机制，固化 20 个精选 RSS 订阅源，建立播放状态追踪 |
