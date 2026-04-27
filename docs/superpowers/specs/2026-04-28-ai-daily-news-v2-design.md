# AI Daily News v2 — Architecture Design

> Date: 2026-04-28
> Status: Approved
> Owner: unclejoe + Fanli (OpenClaw)

---

## 0. 目标

把当前 `ai-daily-news`（v1：RSS 抓取 + Discord 文字/音频播报）升级成端到端的多语种 AI 新闻自动化平台：

```
RSS 抓取 → SQLite 去重 → AI 翻译 → 静态站点发布 → 音频生成 → Discord 推送
                                          ↓
                          GitHub Pages 公开站点
                          （日历 / 全文搜索 / 标签分类）
```

参考 `berlin-gastro-news` 项目结构 1:1 同构，本项目作为该模板在 AI 新闻领域的实例化。

---

## 1. 总体架构

```
ai-daily-news/
├── .github/workflows/deploy.yml          # GH Pages CI
├── data/
│   ├── news.db                           # SQLite (从 db/ 迁移，schema 升级)
│   ├── schema.sql                        # v2 schema
│   ├── sources.json                      # 20 RSS 源 (升级到 v2 字段)
│   └── tags.json                         # ★ 12 个 AI 标签 (可扩展, single source of truth)
├── scripts/
│   ├── __init__.py
│   ├── harvest.py                        # Step 1: RSS → DB
│   ├── select_top.py                     # Step 2: Top 10 → daily-selected.json
│   ├── publish_article.py                # Step 4: DB → site/src/content/articles/
│   ├── publish_briefing.py               # Step 5: → briefings/ + daily/<DATE>/
│   ├── render_audio.py                   # Step 6: TTS
│   ├── git_publish.py                    # Step 7: commit + push
│   ├── migrate_v1_schema.py              # 一次性 schema 升级
│   └── lib/
│       ├── __init__.py
│       ├── news_db.py                    # SQLite ORM
│       └── normalize.py                  # URL/TTS 文本清洗
├── site/                                 # Astro 6 静态站
├── daily/<YYYY>/<YYYY-MM>/<DATE>/        # OpenClaw 取件目录
├── archive/v1/                           # 旧 daily/、workflows/、knowledge/ 归档
├── docs/superpowers/specs/               # 设计文档
├── workflows/DAILY_WORKFLOW.md           # OpenClaw 每日 runbook
├── README.md
└── .gitignore
```

**部署目标**：`https://unclejoeyao666.github.io/ai-daily-news/`

---

## 2. 数据库 Schema (v2)

在现有 `data/news.db`（1285 条）基础上 in-place 升级，所有数据保留：

### 新增字段

`news_articles`：
- `summary` (TEXT) — RSS summary（v1 是 `content`）
- `source_name_cn` (TEXT) — 中文源名
- `source_categories` (TEXT JSON) — 分类
- `lang` (TEXT, default 'en')
- `translated_title`, `translated_summary`, `translated_body` (TEXT)
- `impact_analysis` (TEXT)
- `industry_tags` (TEXT JSON) — 1-3 个标签 slug
- `slug` (TEXT UNIQUE)
- `published_briefing_date` (TEXT)

`sources`：
- `source_id` (TEXT UNIQUE) — 稳定字符串 ID
- `name_cn` (TEXT)
- `tier` (INTEGER 1=官方源, 2=二手媒体)
- `categories` (TEXT JSON)

### FTS5 重建

将 FTS 索引扩展为：`title + summary + content + translated_title + translated_body + impact_analysis`。

### 历史数据处理（方案 A）

所有现存 1285 条（931 played + 354 unplayed）一律 `broadcast_status='archived'`，从 2026-04-29 起只播报新抓取的。旧 `daily/` 整体移到 `archive/v1/daily/`。

---

## 3. 7 步流水线

| Step | 脚本 | 自动 / 手动 | 说明 |
|---|---|---|---|
| 1 | `harvest.py` | 自动 | RSS 抓取 → 三层去重 → 评分 → 入库 |
| 2 | `select_top.py --count 10` | 自动 | 选 Top10 → `daily-selected.json` |
| 3 | (Claude 认知工作) | OpenClaw 内 | WebFetch + 翻译 + 影响分析 + 打标 + 写 audio_script |
| 4 | `publish_article.py --all-pending` | 自动 | DB → `site/src/content/articles/<slug>.md` |
| 5 | `publish_briefing.py --date today` | 自动 | 简报集合 + Discord briefing.md + meta.json + mark played |
| 6 | `render_audio.py --date today` | 自动 | TTS (Microsoft Edge / MiniMax fallback) |
| 7 | `git_publish.py --date today` | 自动 | pull/add/commit/push |

每个脚本都支持 `--date YYYY-MM-DD`，幂等可重跑。

### 重要性评分 (Step 1)

```python
score = (3 - tier) * 20  # tier 1 = +40, tier 2 = +20
score += sum(CATEGORY_WEIGHTS[c] for c in categories)
score += 15 if hours_old < 24 else 10 if < 48 else 5 if < 72 else 0
score = min(score, 100)
```

`CATEGORY_WEIGHTS`（针对 AI 领域调整）：
```
"ai-research": 10, "model-launch": 10, "agent": 9, "open-source": 8,
"funding": 7, "policy": 7, "chips": 6, "enterprise": 6,
"safety": 6, "consumer": 5, "china": 5, "general": 1
```

---

## 4. Tag 分类（可扩展）

**Single Source of Truth**：`data/tags.json`

```json
{
  "version": "1.0",
  "updated": "2026-04-28",
  "tags": [
    { "slug": "model-release",    "label_cn": "模型发布",    "color": "#1d4ed8" },
    { "slug": "agent-tools",      "label_cn": "智能体·工具", "color": "#7c3aed" },
    { "slug": "research-paper",   "label_cn": "论文·研究",   "color": "#0e7490" },
    { "slug": "funding-ipo",      "label_cn": "融资·上市",   "color": "#15803d" },
    { "slug": "policy-regulation","label_cn": "政策·监管",   "color": "#1e293b" },
    { "slug": "chips-infra",      "label_cn": "芯片·算力",   "color": "#b45309" },
    { "slug": "enterprise-app",   "label_cn": "企业应用",     "color": "#52525b" },
    { "slug": "consumer-app",     "label_cn": "消费应用",     "color": "#be185d" },
    { "slug": "open-source",      "label_cn": "开源生态",     "color": "#0f766e" },
    { "slug": "safety-alignment", "label_cn": "安全·对齐",   "color": "#b91c1c" },
    { "slug": "china-ai",         "label_cn": "中国 AI",     "color": "#c2410c" },
    { "slug": "industry-trend",   "label_cn": "行业趋势",     "color": "#7e22ce" }
  ]
}
```

Astro `consts.ts` 在构建时 `import` 此 JSON，生成 `TAG_LABELS` / `TAG_COLORS` / `TAG_SLUGS`。新增标签只需改 JSON。

---

## 5. Astro 站点

完全复刻 `berlin-gastro-news` v2.1 站点，仅修改：
- `astro.config.mjs`: `base: '/ai-daily-news'`
- `consts.ts`: `SITE_TITLE = "AI 科技每日早报"`，`SITE_TAGLINE = "AI Daily News — 中文"`
- `consts.ts`: 标签从 `data/tags.json` 动态导入
- `about.astro`: 重写文案（AI 领域、20 个 RSS 源、覆盖范围）
- `SiteHeader.astro`: brand-mark 字 `柏` → `AI`
- `SiteFooter.astro`: 文案改 `AI 科技每日早报`，链接改 `unclejoeyao666/ai-daily-news`
- 所有页面 (index/archive/about/search/briefings/articles/tags) 文案微调

页面：
- `/` 首页（最新简报 hero + 本期精选 + 最新文章）
- `/briefings` 简报库（日历视图 + 月份分组列表）
- `/briefings/<DATE>` 单期简报
- `/articles/<slug>` 单篇文章
- `/tags/<slug>` 标签筛选
- `/archive` 全部文章按月归档
- `/search` Pagefind 全文搜索
- `/about` 关于页
- `/rss.xml` RSS feed

---

## 6. 自动化

### GitHub Actions

`.github/workflows/deploy.yml`（与 berlin-gastro-news 同款）：
- 触发：`push` to `main`，paths: `site/**`
- 构建：`npm ci && npm run build`（含 pagefind 索引）
- 部署：`actions/deploy-pages@v4`

### OpenClaw 每日 cron

| 时刻 | 任务 |
|---|---|
| 04:00 UTC (06:00 Berlin) | `harvest.py` |
| 04:30 UTC (06:30 Berlin) | `select_top.py` + Claude 认知工作 + `publish_article.py` + `publish_briefing.py` + `render_audio.py` + `git_publish.py` |
| 05:30 UTC (07:30 Berlin) | Discord 推送 (读 `daily/<DATE>/briefing.md` + `audio.mp3`) |

cron 配置由 OpenClaw 端管理，不在本仓库内（与 berlin-gastro-news 一致）。

---

## 7. Discord

继续推送到 `#fanli-news-daily` (channel id `1490344209847287830`)。

每天发送两条消息：
1. **文字简报**：内容来自 `daily/<DATE>/briefing.md`，含 `🌐 完整网页` 链接指向 GitHub Pages 中文页 + `🎧 音频` 链接指向 mp3。
2. **音频附件**：`daily/<DATE>/audio.mp3`。

---

## 8. 迁移步骤

```bash
cd /Users/unclejoe/Media_Workspace/ai-daily-news

# 1. 归档 v1 资产
mkdir -p archive/v1
git mv daily archive/v1/daily
git mv workflows archive/v1/workflows
git mv knowledge archive/v1/knowledge

# 2. 重命名 db → data
git mv db data

# 3. 升级 sources.json (加 source_id / name_cn / tier / categories)
# 4. 写 data/tags.json
# 5. 替换 data/schema.sql
# 6. 跑 migrate_v1_schema.py（幂等 ALTER + FTS5 重建 + 旧数据归档）
# 7. 写 scripts/ + site/ + .github/ + docs/ + workflows/
# 8. cd site && npm install && npm run build (本地验证)
# 9. 端到端 dry run
# 10. commit + push
```

---

## 9. 验证标准

- ✅ `python3 scripts/harvest.py` 成功，新增 N 条 unplayed
- ✅ `python3 scripts/select_top.py --count 10` 输出 `daily-selected.json`
- ✅ Claude 翻译并 update_translation 至少 3 条作为 dry run
- ✅ `python3 scripts/publish_article.py --all-pending` 生成 `.md` 文件
- ✅ `python3 scripts/publish_briefing.py --date today` 生成简报 + meta.json
- ✅ `cd site && npm run build` 无错误，`dist/` 含所有页面 + pagefind 索引
- ✅ 提交 + 推送（首推后 GitHub Actions 在 1-2 分钟内部署）
- ✅ `curl -sI https://unclejoeyao666.github.io/ai-daily-news/` 返回 200

---

## 10. 不在本期范围

- 多语言 UI（仅中文 UI；翻译来源仅英文 → 中文，未加德语/西班牙语等其他语种源）
- 用户账号 / 评论
- 邮件订阅
- 私有仓库；本仓库须改为 public 以启用 GitHub Pages 免费版
