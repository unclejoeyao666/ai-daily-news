# 🤖 AI Daily News — 每日AI科技早报

## 项目说明

Fanli 每天早上 7:00 (Europe/Berlin) 自动搜集过去 24 小时内 AI 科技领域最热新闻，精选 10 条发送到 Discord `#fanli-news-daily` 频道，同时生成详细音频播报版本。

## 覆盖主题

Anthropic · OpenAI · MiniMax · Google Gemini · Meta Llama · Mistral · DeepSeek · OpenClaw · AI 科技重大更新

## 目录结构

```
ai-daily-news/
├── README.md
├── workflows/
│   └── WORKFLOW_AI_NEWS.md          # 🔸 完整工作流文档（必读）
├── knowledge/                         # 🔸 专项经验文档
│   ├── README.md
│   └── TTS.md                      # TTS 语音生成经验
├── scripts/                         # 工具脚本
│   └── (TTS 脚本位于 /Users/unclejoe/Doc_Workspace/scripts/minimax_tts.py)
└── daily/                            # 按年份/月份分层
    2026/
    └── 2026-04/                     # 当前月份
        ├── 2026-04-01.md
        ├── 2026-04-02.md
        ├── 2026-04-03.md
        ├── 2026-04-04.md
        ├── 2026-04-04_audio.mp3    # ⚠️ 已损坏（需补录）
        ├── 2026-04-05.md
        ├── 2026-04-05_audio_script.md
        └── 2026-04-05_audio.mp3
    2027/2027-01/                    # 未来占位
    2028/2028-01/                    # 未来占位
```

**每日存档路径格式：** `daily/<YYYY>/<YYYY-MM>/<YYYY-MM-DD>.md`
示例：`daily/2026/2026-04/2026-04-05.md`

## 每日三个文件（最终交付物）

每个工作日生成以下三个文件，缺一不可：

| 文件 | 说明 |
|---|---|
| `YYYY/YYYY-MM/YYYY-MM-DD.md` | 完整新闻搜集文档（10条） |
| `YYYY/YYYY-MM/YYYY-MM-DD_audio_script.md` | 文字简报播报脚本（朗读版） |
| `YYYY/YYYY-MM/YYYY-MM-DD_audio.mp3` | 音频文件 |

## Cron 任务

| 任务 | Job ID | Schedule |
|---|---|---|
| 文字早报 | `3c687e42-5c02-4393-b4fd-93c69a58e4a6` | 每天 05:00 UTC |
| 音频早报 | `3d981359-a949-4d42-b267-9c63b0f585a4` | 每天 05:30 UTC |

## TTS 方案

| | 主力（当前） | 备用 |
|---|---|---|
| 提供商 | Microsoft Edge TTS（免费） | MiniMax TTS（TokenPlan 额度） |
| 音色 | `zh-CN-XiaoxiaoNeural` | `male-qn-qingse` |

详见 [knowledge/TTS.md](knowledge/TTS.md)

## 故障排查

详见 [WORKFLOW_AI_NEWS.md](workflows/WORKFLOW_AI_NEWS.md#故障排查)

## 维护者

Fanli（@fanli）| 接管自 Shell | 2026-04-05
