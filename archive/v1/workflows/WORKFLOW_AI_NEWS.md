# AI 科技早报 — 工作流文档

> 本文档记录 AI 科技早报完整工作流的每一步骤、操作命令与配置说明。
> 由 Fanli 维护，2026-04-05 验证通过。

---

## 工作流概览

```
05:00 UTC (07:00 Berlin)          05:30 UTC (07:30 Berlin)
┌────────────────────────────┐    ┌────────────────────────────┐
│   步骤 1-3                 │    │   步骤 4                   │
│   Tavily 新闻搜索           │    │   MiniMax TTS 语音生成     │
│   → 整理筛选               │    │   → 保存 → 发送 Discord   │
│   → 保存文字早报           │    └────────────────────────────┘
│   → 发送 Discord
└────────────────────────────┘
```

| 步骤 | 内容 | 执行者 | 触发方式 |
|---|---|---|---|
| 1 | 信息搜集（Tavily 新闻搜索） | OpenClaw Cron | 自动 05:00 UTC |
| 2 | 整理与筛选（去重 + 重要性排序） | OpenClaw Cron | 自动 |
| 3 | 文字早报存档 + 发送 Discord | OpenClaw Cron | 自动 |
| 4 | 语音生成 + 存档 + 发送 Discord | OpenClaw Cron | 自动 05:30 UTC |

---

## 每日三个文件（最终交付物）

每个工作日文件夹必须包含以下三个文件，缺一不可：

| 文件 | 说明 | 是否必须 |
|---|---|---|
| `<YYYYMMDD>.md` | 完整新闻搜集文档（10条，含标题/来源/摘要/意义） | ✅ 每天必须 |
| `<YYYYMMDD>_audio_script.md` | 文字简报播报脚本（朗读版，完整口语化文稿） | ✅ 每天必须 |
| `<YYYYMMDD>_audio.mp3` | 音频文件（由播报脚本生成） | ✅ 每天必须 |

**三个文件全部存入 `daily/YYYYMMDD/` 目录，不仅仅是发送到 Discord。**

---

## 步骤详解

### 步骤 1 — 信息搜集

**工具：** `tavily_search`（OpenClaw 内置 Tavily 插件）

**搜索配置：**
```python
tavily_search(
    query="<具体主题>",
    search_depth="basic",        # 或 "advanced"
    topic="news",               # 必须为 news
    time_range="day",           # 必须为 day（过去 24 小时）
    max_results=5               # 每个主题最多 5 条
)
```

**搜索主题（按优先级）：**

| # | 搜索关键词 | 原因 |
|---|---|---|
| 1 | `Anthropic Claude Code OR Claude 4 news` | Anthropic 最新动态 |
| 2 | `OpenAI GPT-5 OR GPT-4.5 OR GPT-o3 news` | OpenAI 最新动态 |
| 3 | `MiniMax M2.7 OR MiniMax AI news today` | MiniMax 最新动态 |
| 4 | `Google Gemini 2 OR Google AI news today` | 大模型竞争格局 |
| 5 | `Meta Llama 4 OR Meta AI open source news` | 开源模型动态 |
| 6 | `Mistral AI OR DeepSeek OR open source LLM news` | 其他大模型 |
| 7 | `OpenClaw AI agent news` | 自身平台动态 |
| 8 | `AI technology breakthrough OR major AI update today` | 重大行业更新 |

**注意：**
- 每个 query 独立调用 `tavily_search`
- 所有结果合并后再去重
- 去重依据：`title` 相同或高度相似（90%+）的新闻只保留一条
- 优先保留：发布时间更新、内容更具体、有具体数据/产品名的条目

---

### 步骤 2 — 整理与筛选

**输出格式（10 条精选）：**

```markdown
## [日期] AI 科技早报

**标题** — [来源] — [发布时间]
> 核心内容摘要（1-2 句话）

**为什么重要：**[一句话说明影响或意义]
```

**筛选标准（按优先级）：**
1. 爆炸性新闻（新产品发布、重大更新）优先
2. 有具体数据、发布时间、版本号的信息优先
3. 与目标受众（AI 开发者/创业者/科技爱好者）相关度
4. 非广告、非软文、非纯营销内容
5. 去重后保留最具影响力的版本

**最终输出：** 精选 10 条（不足 10 条时按实际数量输出）

---

### 步骤 3 — 文字早报存档与发送

**存档路径：**
```
/Users/unclejoe/Doc_Workspace/ai-daily-news/daily/<YYYYMMDD>/<YYYYMMDD>.md
```
示例：`/Users/unclejoe/Doc_Workspace/ai-daily-news/daily/2026/2026-04/2026-04-05.md`

**发送 Discord：**
- 频道 ID：`1490344209847287830`（`#fanli-news-daily`）
- 发送方式：`message` tool，`action=send`，`media` 不使用（纯文字）
- 消息格式：
  ```
  🗞️ **AI 科技早报** — <日期>
  
  <10 条精选新闻>
  
  本早报由 Fanli 自动整理 | 数据来源：Tavily News Search
  ```

---

### 步骤 4 — 语音播报生成

**触发时间：** 每天 05:30 UTC（即文字版完成 30 分钟后）

**前置条件：** 文字早报存档文件存在

#### 4a. 读取存档文件

文件路径：`/Users/unclejoe/Doc_Workspace/ai-daily-news/daily/<YYYYMMDD>/<YYYYMMDD>.md`

#### 4b. 生成音频播报脚本

将 10 条新闻扩展为适合朗读的播报脚本：

**脚本格式要求：**
- 开头：「早上好，这里是 Fanli AI 科技早报。今天是 [日期]，以下是今天最重要的 AI 科技动态。」
- 每条新闻：2-4 句话详细说明发生了什么、为什么重要、有什么影响
- 结尾：「以上是今天的 AI 科技早报，全部内容由 Fanli 自动整理。我们明天见。」
- 文字总长度：**400-900 字**（注意 MiniMax TokenPlan 每日字符限额）
- 目标时长：2-4 分钟

**脚本保存位置：** `/tmp/news_briefing_script.txt`（临时文件，供 TTS 脚本读取）

#### 4c. 调用 MiniMax TTS 生成音频

**Python 脚本路径：** `/Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py`

**调用命令（exec 工具，默认 Microsoft Edge TTS）：**
```bash
python3 /Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py \
  --file /tmp/news_briefing_script.txt \
  /tmp/news_audio_today.mp3 \
  --provider microsoft \
  --voice zh-CN-XiaoxiaoNeural
```

**自动分片：** Microsoft Edge TTS 单次上限约 1500 字符；脚本自动拆分为 ≤1200 字符/段，逐段合成后用 ffmpeg 拼接。

**切换 MiniMax（如需）：**
```bash
python3 /Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py \
  --file /tmp/news_briefing_script.txt \
  /tmp/news_audio_today.mp3 \
  --provider minimax \
  --voice male-qn-qingse
```

**MiniMax TTS 配置：**
| 配置项 | 值 |
|---|---|
| API Endpoint | `https://api.minimaxi.com/v1/t2a_v2` |
| 模型 | `speech-2.8-hd` |
| 音色 | `male-qn-qingse`（男声青少） |
| 认证 | Bearer Token（TokenPlan key，`sk-cp-` 格式） |
| 认证文件 | `~/.minimax/tts_config.json` |
| 字符限额 | Plus 计划：4000 字符/天 |
| 每次消耗 | 约 1200-1500 字符（738 字早报） |

**音频脚本参数：**
```python
generate_speech(
    text=text,
    output_path=output_path,
    voice_id="male-qn-qingse",
    model="speech-2.8-hd",
    speed=1.0
)
```

#### 4d. 保存音频文件

**存档路径：**
```
/Users/unclejoe/Doc_Workspace/ai-daily-news/daily/<YYYYMMDD>/<YYYYMMDD>_audio.mp3
```
示例：`/Users/unclejoe/Doc_Workspace/ai-daily-news/daily/2026/2026-04/2026-04-05_audio.mp3`

**音频播报脚本存档路径（文本版，供追溯）：**
```
/Users/unclejoe/Doc_Workspace/ai-daily-news/daily/<YYYYMMDD>/<YYYYMMDD>_audio_script.md
```

**操作：** 使用 `exec cp /tmp/news_audio_today.mp3 <存档路径>` 复制文件

#### 4e. 发送音频到 Discord

**频道 ID：** `1490344209847287830`（`#fanli-news-daily`）

**消息格式：**
```
🎧 **AI 科技早报 · 音频版** — <日期>

_详细播报版，每条新闻都有深度解读_（MiniMax speech-2.8-hd）

本早报由 Fanli 自动整理 | 数据来源：Tavily News Search
```

**附件：** `/tmp/news_audio_today.mp3`

**发送方式：**
```python
message(
    action="send",
    channel="discord",
    target="1490344209847287830",
    message="<消息文字>",
    media="/tmp/news_audio_today.mp3"
)
```

---

## Cron 任务配置

| | 文字早报 | 音频早报 |
|---|---|---|
| **Job ID** | `3c687e42-5c02-4393-b4fd-93c69a58e4a6` | `3d981359-a949-4d42-b267-9c63b0f585a4` |
| **Schedule** | `0 5 * * *` UTC | `30 5 * * *` UTC |
| **Berlin 时间** | 07:00 | 07:30 |
| **Agent** | fanli | fanli |
| **模式** | isolated agentTurn | isolated agentTurn |
| **Timeout** | 300s | 600s |
| **delivery** | announce → `channel:1490344209847287830` | announce → `channel:1490344209847287830` |

---

## 关键文件路径

```
/Users/unclejoe/Doc_Workspace/ai-daily-news/
├── README.md
├── workflows/
│   └── WORKFLOW_AI_NEWS.md
├── scripts/                          # TTS 工具脚本
│   └── (脚本位于 /Users/unclejoe/Doc_Workspace/scripts/)
daily/                                # 按年份/月份分层
    2026/
    └── 2026-04/                            # 当前月份
        ├── 2026-04-01.md
        ├── 2026-04-02.md
        ├── 2026-04-03.md
        ├── 2026-04-04.md
        ├── 2026-04-04_audio.mp3       # ⚠️ 已损坏，需补录
        ├── 2026-04-05.md
        ├── 2026-04-05_audio_script.md  # ✅
        └── 2026-04-05_audio.mp3        # ✅
    2027/2027-01/                           # 未来占位
    2028/2028-01/                           # 未来占位

~/.minimax/tts_config.json            # MiniMax API 认证配置
```

---

## 故障排查

### 文字早报未发出
1. 检查 Tavily API 是否有效：`plugins.entries.tavily.enabled: true`
2. 检查 cron job 是否触发：`cron(action="runs", jobId="3c687e42-5c02-4393-b4fd-93c69a58e4a6")`
3. 检查上次运行状态

### 音频 TTS 失败
1. **Microsoft TTS timeout**（单段 >1500 字符）：脚本已内置自动分片，如仍失败检查网络
2. **MiniMax 2056 usage limit exceeded**：TokenPlan 今日额度耗尽，切换到 Microsoft Edge TTS
3. **MiniMax 2049 invalid api key**：确认用的是 `api.minimaxi.com` 而非 `api.minimax.io`
4. **MiniMax 1004**：确认 Authorization 使用 `Bearer <token>` 格式，不带 GroupId
5. **分片拼接失败**：确认 ffmpeg 已安装：`which ffmpeg`
6. 测试命令：`python3 /Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py --test`
7. 监控 TokenPlan 额度：`https://platform.minimaxi.com` TTS 仪表盘

### 音频发送失败（Discord）
1. 确认媒体路径在允许目录下（`~/.openclaw/media/manual/`）
2. 文件大小限制：Discord 通常接受 < 8MB 的 MP3

---

## TTS 方案选择

| | 主力（当前使用） | 备用 |
|---|---|---|
| **方式** | Microsoft Edge TTS | MiniMax API TTS |
| **音色** | `zh-CN-XiaoxiaoNeural` | `male-qn-qingse` |
| **费用** | 免费 | TokenPlan 额度内免费 |
| **质量** | 高（Neural） | 极高（speech-2.8-hd） |
| **每日消耗** | 无限制 | 4000 字符/天 |
| **无需 API Key** | ✅ | ❌ |
| **切换条件** | — | Microsoft TTS 不可用时 |

**详细说明与避坑指南：** `../knowledge/TTS.md`

## 升级记录

| 日期 | 变更内容 |
|---|---|
| 2026-04-05 | 初始工作流建立，文字版 + 音频版双轨并行 |
| 2026-04-05 | 音频版从 Microsoft TTS 切换至 MiniMax TTS（speech-2.8-hd） |
| 2026-04-05 | 目录结构重命名：`YYYY/MM/YYYYMMDD` → `YYYY/YYYY-MM/YYYY-MM-DD` |
| 2026-04-05 | 恢复 Microsoft Edge TTS 作为主力 TTS，MiniMax 备用；TTS 经验抽离为独立文档 |
| 2026-04-05 | 完善每日三文件标准：`_audio_script.md` 文字简报必须存档 |
| 2026-04-05 | Microsoft Edge TTS 增加自动分片（≤1200字/段）+ ffmpeg 拼接，解决 1500 字符上限问题 |
| 2026-04-05 | 目录重组：`YYYY/YYYY-MM/YYYY-MM-DD` 三层嵌套格式，2027/2028 已占位 |
