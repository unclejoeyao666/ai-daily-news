# deliveries 字段缺失 — 完整日志
**报告生成时间：** 2026-05-07 00:15 GMT+2  
**覆盖范围：** 2026-05-05 ～ 2026-05-07（共3天）  
**相关 Job：** Stage D (`7ffd5e3d-ea37-4130-9088-e6db25b92d55`)

---

## 问题描述

2026-05-06 和 2026-05-07 的 pipeline 所有步骤（harvest/select/translate/publish_article/publish_brief/audio/push）全部正确完成，但 `.state.json` 中 `deliveries` 字段完全缺失。

---

## 三天 .state.json 对比

### 2026-05-05 ✅ 正常

```json
{
  "date": "2026-05-05",
  "started_at": "2026-05-04T22:05:55.087042+00:00",
  "steps": {
    "harvest": { "status": "ok" },
    "select": { "status": "ok" },
    "translate": { "status": "ok" },
    "publish_article": { "status": "ok" },
    "publish_brief": { "status": "ok", "finished_at": "2026-05-05T05:33:30.168295+00:00" },
    "audio": { "status": "ok", "mp3_size": 7281204 },
    "push": { "status": "ok", "finished_at": "2026-05-05T05:33:32.652424+00:00" }
  },
  "deliveries": {
    "discord_text": {
      "status": "ok",
      "finished_at": "2026-05-05T06:05:17.765944+00:00",
      "chars": 1929
    },
    "discord_audio": {
      "status": "ok",
      "finished_at": "2026-05-05T06:06:04.853667+00:00",
      "mp3_size": 7281204
    }
  }
}
```

### 2026-05-06 ❌ 缺失

```json
{
  "date": "2026-05-06",
  "started_at": "2026-05-05T22:01:49.455023+00:00",
  "steps": {
    "harvest": { "status": "ok" },
    "select": { "status": "ok" },
    "translate": { "status": "ok" },
    "publish_article": { "status": "ok" },
    "publish_brief": { "status": "ok" },
    "audio": { "status": "ok", "mp3_size": 1582940 },
    "push": { "status": "ok", "finished_at": "2026-05-06T18:05:08.860014+00:00" }
  }
  // ← deliveries 字段完全缺失
}
```

### 2026-05-07 ❌ 缺失

```json
{
  "date": "2026-05-07",
  "started_at": "2026-05-06T22:04:04.437206+00:00",
  "steps": {
    "harvest": { "status": "ok" },
    "select": { "status": "ok" },
    "translate": { "status": "ok" },
    "publish_article": { "status": "ok" },
    "publish_brief": { "status": "ok" },
    "audio": { "status": "ok", "mp3_size": 1298684 },
    "push": { "status": "ok", "finished_at": "2026-05-06T22:04:34.248636+00:00" }
  }
  // ← deliveries 字段完全缺失
}
```

---

## Stage D Cron Runs 数据（2026-05-04 ~ 2026-05-07）

| 时间 (UTC) | 日期 | 状态 | 耗时 | Summary 内容 | delivered |
|-----------|------|------|------|-------------|-----------|
| 06:00 | 05-07 | ✅ ok | 452,421ms | "sent文字+音频, 成功" | false |
| 06:00 | 05-06 | ✅ ok | 385,905ms | "sent文字+音频, 成功" | false |
| 06:00 | 05-04 | ✅ ok | 298,226ms | "音频版, 成功" | false |
| 05:30 | 05-04 | ❌ error | 160,527ms | "Read discord-delivery.md failed" | false |
| 06:00 | 05-03 | ✅ ok | 311,800ms | "文字简报, 成功" | false |
| 05:30 | 05-02 | ✅ ok | 527,954ms | "音频版, 成功" | false |
| 05:30 | 05-01 | ✅ ok | 244,609ms | "文字+音频, 成功" | **true** |

---

## 关键发现

### 发现1：Discord 消息确实发送了，但 delivery 标记为 false

Stage D 的 delivery 记录显示：
```json
"delivery": {
  "intended": { "channel": "discord", "to": "channel:1490344209847287830" },
  "resolved": { "ok": true, "channel": "discord", "to": "channel:1490344209847287830" },
  "messageToolSentTo": [
    { "channel": "discord", "to": "channel:1490344209847287830" },
    { "channel": "discord", "to": "channel:1490344209847287830" }
  ],
  "fallbackUsed": false,
  "delivered": false  // ← delivery=false 但 message() 工具确实调用了
}
```

这说明：
1. `message()` 工具被调用了两次（文字+音频）
2. OpenClaw 收到调用指令
3. 但 delivery 状态被标记为 `false`
4. 可能原因：delivery 检测的是 announce 模式（mode=none 不走 announce），而 message() 工具调用是直接发送，不经过 announce 机制

### 发现2：2026-05-01 是唯一一次 delivered=true

2026-05-01 Stage D 的 delivery 状态：
```json
"delivered": true,
"delivery": {
  "resolved": { "ok": true, "channel": "discord", "to": "channel:1490344209847287830" }
}
```

这说明 05-01 的 delivery 走了不同的代码路径，导致 `delivered=true`。而 05-06 和 05-07 虽然同样调用了 message()，但 delivered=false。

### 发现3：2026-05-06 有多个 Stage D session 同时运行

从 runs 数据看，同一时间（05-06 06:00 UTC 左右）有多个 Stage D session 被触发：
```
05-06 06:00 → session A (d71ef408) ✅ ok
05-06 06:00 → session B (e0256583) ✅ ok (实际是 05-07 的)
```

这可能导致状态写入竞争。

---

## messageToolSentTo 记录（2026-05-06 Stage D）

```json
"messageToolSentTo": [
  { "channel": "discord", "to": "channel:1490344209847287830" },
  { "channel": "discord", "to": "channel:1490344209847287830" }
]
```

说明 Stage D 确实发送了两次 Discord 消息（文字简报 + 音频）。

---

## 根因分析

### 主要原因：announce vs message() 工具的差异

Stage D 的 payload 设置了 `delivery.mode=none`：
```json
"delivery": { "mode": "none" }
```

这意味着 cron 任务的 delivery 机制被关闭。Stage D 通过直接调用 `message()` 工具发送 Discord 消息，而不是通过 cron 的 announce 机制。

但 `message()` 工具的调用结果被记录在 `delivery.messageToolSentTo` 中，而 `delivered` 字段检查的却是 `announce` 的 delivery 状态。因此即使 message() 成功，delivered 仍然=false。

### 次要原因：mark_delivery() 函数未被调用

Stage D 的 payload 中提到：
> - § A: 调用 `mark_delivery(state, "discord_text", "ok", ...)`
> - § B: 调用 `mark_delivery(state, "discord_audio", "ok", ...)`

如果 `mark_delivery()` 函数没有被正确调用（例如路径错误、函数不存在），则 .state.json 中的 deliveries 字段就不会被写入。

### 第三原因：delivery mode=none 时 cron 不等待 tool 结果

当 `delivery.mode=none` 时，OpenClaw 的 cron 可能不会等待 message() 工具的最终执行结果，导致 delivery 记录不完整。

---

## 修复建议

### 1. 在 Stage D 中显式调用 mark_delivery()

确保每次发送 Discord 消息后，显式更新 .state.json：
```python
def mark_delivery(state, key, status, **extra):
    state.setdefault("deliveries", {})
    state["deliveries"][key] = {**extra, "status": status, "finished_at": now()}
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)
```

### 2. 添加 delivery 验证步骤

在 Stage D 结束时，读取 .state.json 验证 deliveries 字段是否存在：
```python
with open(state_path) as f:
    state = json.load(f)
if "deliveries" not in state:
    raise RuntimeError("deliveries field not written — delivery may have failed")
```

### 3. 将 delivery.mode 改为 announce

如果希望 cron 的 delivery 机制记录结果，需要将 delivery.mode 改为 `announce` 或直接移除（让 OpenClaw 使用默认 announce）。

### 4. 在发送后读取 Discord 消息 ID

发送消息后记录返回的 messageId，便于追踪和验证。

---

## 待确认事项

1. **Discord 频道（#fanli-news-daily, ID: 1490344209847287830）中是否有 05-06 和 05-07 的消息？**
   - 如果有 → 只是 .state.json 记录缺失，实际发送成功
   - 如果没有 → 消息确实没发送成功，需要修复 message() 调用

2. **检查 05-06 和 05-07 的实际 Discord 历史**
   - 需要人工登录 Discord 查看频道消息

---

## 建议立即采取的行动

1. **检查 Discord 频道**：确认 05-06 和 05-07 是否有消息记录
2. **修复 mark_delivery()**：确保每次发送后更新 .state.json
3. **添加验证逻辑**：Stage D 结束时检查 deliveries 字段
4. **记录 messageId**：便于后续追踪每条消息的状态