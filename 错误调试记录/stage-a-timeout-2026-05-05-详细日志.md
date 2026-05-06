# Stage A 超时 — 完整日志
**日期：** 2026-05-05 04:00 UTC  
**Job ID：** `3a25d2a8-d3f8-4090-b101-bfc2792ee55a`  
**Cron 表达式：** `0 4 * * *` UTC  
**Timeout 设置：** 300 秒  
**实际耗时：** 302,326 ms（约302秒）

---

## Cron Job 状态（截图数据）

```json
{
  "id": "3a25d2a8-d3f8-4090-b101-bfc2792ee55a",
  "name": "fanli:ai-news-workflow Stage A — Ingest (04:00 UTC)",
  "enabled": true,
  "schedule": { "kind": "cron", "expr": "0 4 * * *", "tz": "UTC" },
  "payload": {
    "kind": "agentTurn",
    "message": "执行 ai-news-workflow skill 的 Stage A (Ingest)。\n项目根: /Users/unclejoe/Media_Workspace/ai-daily-news\n\ncd /Users/unclejoe/Media_Workspace/ai-daily-news\ngit pull --rebase origin main\npython3 scripts/daily_pipeline.py --date today --status\npython3 scripts/daily_pipeline.py --date today --from harvest --to select\npython3 scripts/daily_pipeline.py --date today --status\n\n完成后打印一行数据库统计:\npython3 -m scripts.lib.news_db data/news.db --stats\n\n注意: 仅运行 Stage A；不要做翻译、推送或 Discord 发送。静默执行，前置条件不满足时以 rc=0 静默退出。\n\n最后请仅回复字面量 NO_REPLY — delivery.mode=none, 你的回复不会被发布；出错由 failureAlert 自动告警。",
    "timeoutSeconds": 300,
    "model": "minimax-portal/MiniMax-M2.7"
  },
  "failureAlert": {
    "after": 1,
    "mode": "announce",
    "channel": "discord",
    "to": "channel:1490362785949814905"
  },
  "state": {
    "lastRunAtMs": 1778040000014,
    "lastRunStatus": "error",
    "lastStatus": "error",
    "lastDurationMs": 302326,
    "lastError": "cron: job execution timed out",
    "lastErrorReason": "timeout",
    "lastFailureAlertAtMs": 1778040302358,
    "consecutiveErrors": 1
  }
}
```

---

## Runs 历史（最近7次）

| 时间 (UTC) | 状态 | 耗时 | 备注 |
|-----------|------|------|------|
| 2026-05-07 04:00 | ❌ error | 302,326ms | timeout — 当前故障 |
| 2026-05-06 04:00 | ✅ ok | 254,163ms | 正常 |
| 2026-05-05 04:00 | ✅ ok | 228,112ms | 正常 |
| 2026-05-04 04:00 | ✅ ok | 228,960ms | 正常 |
| 2026-05-03 04:00 | ✅ ok | 183,367ms | 正常 |
| 2026-05-02 04:00 | ✅ ok | 205,257ms | 正常 |
| 2026-05-01 04:00 | ✅ ok | 64,432ms | 最快一次 |

---

## 故障分析

### 直接原因
Job 执行时间 302 秒，超过了 300 秒（5分钟）的 timeout 限制。

### 超时发生点（推测）
Payload 命令序列：
1. `git pull --rebase origin main` → 若 GitHub 网络慢，可能耗时 30–120s
2. `python3 scripts/daily_pipeline.py --date today --status` → ~1–2s
3. `python3 scripts/daily_pipeline.py --date today --from harvest --to select` → ~5–10s
4. `python3 scripts/daily_pipeline.py --date today --status` → ~1–2s
5. `python3 -m scripts.lib.news_db data/news.db --stats` → ~1–2s

正常总计：~50–140s。但实际耗时 302s，说明某一步卡住了。

### 可能卡住的原因
1. **git pull --rebase origin main**：如果 repo 有大量历史或网络慢，可能耗时 200s+
2. **RSS 抓取（harvest）**：如果网络问题导致 RSS 请求慢，可能耗时过长
3. **OpenClaw agent 调度延迟**：job 在 04:00 触发后，agent 队列可能已经积压，导致实际开始时间延迟

### 后续影响
- `consecutiveErrors: 1`（仅一次）
- `failureAlert` 已触发，发送到 `#fanli-daily-news-mgmt` 频道
- 后续 2026-05-06 Stage A 恢复正常（254s），说明这是偶发性问题

---

## 建议修复方案

1. **增大 Timeout**：Stage A timeout 从 300s 提升至 600s
2. **优化 git pull**：改用 `git pull --ff-only --autostash`，避免 rebase 卡住
3. **分离 git pull**：不让 git pull 占用 Stage A 的主要时间，可提前在 watchdog 或其他时间做
4. **添加重试机制**：如果 git pull 超时，自动重试一次