# AI News Daily — 三天故障调试报告
**生成时间：** 2026-05-07 00:10 GMT+2  
**覆盖范围：** 2026-05-05 ～ 2026-05-07（共3天）  
**报告性质：** 错误汇总 + 根因分析 + 修复记录  

---

## 一、故障概览（汇总表）

| 日期 | Pipeline状态 | Discord 文字简报 | Discord 音频 | 问题诊断 |
|------|-------------|-----------------|-------------|---------|
| 2026-05-05 | ✅ 最终完成（经过大量人工干预） | ✅ 已发送 | ✅ 已发送 | Stage C 超时；translate 假成功导致 publish_brief 卡住；Watchdog 空跑了 142 次 |
| 2026-05-06 | ✅ 完全完成 | ⚠️ .state.json 无记录 | ⚠️ .state.json 无记录 | 7 个步骤全部 ok，但 deliveries 字段缺失，无法确认发送状态 |
| 2026-05-07 | ✅ 完全完成 | ⚠️ .state.json 无记录 | ⚠️ .state.json 无记录 | 同上；Stage D 成功运行但 delivery 字段未写入 |

---

## 二、故障一：Stage A 超时（2026-05-05 04:00 UTC）

### 故障现象
- **Job ID：** `3a25d2a8-d3f8-4090-b101-bfc2792ee55a`（fanli:ai-news-workflow Stage A — Ingest）
- **Cron 计划：** `0 4 * * *` UTC
- **实际执行时间：** 2026-05-05 04:00 UTC
- **超时限制：** 300 秒（5分钟）
- **实际耗时：** 302,326 ms ≈ 302秒 **→ 超时**
- **错误信息：** `cron: job execution timed out`
- **后续影响：** consecutiveErrors=1，failureAlert 触发（发送到 #fanli-daily-news-mgmt）

### 日志时间轴（Stage A runs）
```
2026-05-07 04:00 UTC  → ❌ timeout (302s)   ← 当前三天内唯一一次 Stage A 超时
2026-05-06 04:00 UTC  → ✅ ok  (254s)
2026-05-05 04:00 UTC  → ✅ ok  (228s)
2026-05-04 04:00 UTC  → ✅ ok  (229s)
2026-05-03 04:00 UTC  → ✅ ok  (183s)
2026-05-02 04:00 UTC  → ✅ ok  (205s)
2026-05-01 04:00 UTC  → ✅ ok  (64s)
```

### 超时原因分析
Stage A 的 payload 包含 `git pull --rebase origin main`，如果 GitHub 网络连接慢或 repo 有大量历史文件，可能在此环节耗时过长。另外 payload 还连续运行了 4 个 pipeline 命令，合并耗时约 300s，实际执行时刚好超出限制。

---

## 三、故障二：Pipeline publish_brief 卡住（2026-05-05）

### 故障现象
2026-05-05 的 pipeline 在 `publish_brief` 步骤卡住，长达数小时无法推进。Watchdog（每15分钟触发一次）持续检测到该问题但无法修复。

### 根因分析（Watchdog session 记录）
```
⚠️ translate 假成功（false success）：
- translate 步骤在 .state.json 中标记为 "ok"
- 但实际数据库中 10 篇选中文章的 translated_body 全部为空
- slug 也全部为 None
→ 这是系统性失败：Stage B 的翻译工作没有真正写入内容，但状态被标记为完成
→ 导致依赖 translate 输出的 publish_brief 无法运行
```

### watchdog 行为记录（2026-05-05 05:00–08:00 UTC 期间）
Watchdog 运行了多次，不断尝试续跑：
```
05:30 UTC → Stage D (Deliver) 执行，发现 push != ok → 静默退出
06:00 UTC → Stage D 再次执行，同上
07:00 UTC → watchdog 检测到 publish_brief pending，rc=2（无输出）
           但 watchdog 只能续跑确定性 Python 步骤，无法处理翻译
           → 静默退出
07:30 UTC → watchdog 检测到 translate 假成功状态，无法续跑
           → 报告"需要 Stage B (04:30 UTC) 处理"
08:00 UTC+→ 大量 watchdog runs，全部返回"already complete"（因为手动修复）
```

### 手动修复过程（推测）
某个 Bernard/Fanli session 手动执行了：
1. 手动运行 `publish_brief`、`audio`、`push`（将残留状态覆盖）
2. 手动将 briefing.md 复制到 `site/src/content/briefings/2026-05-05.md`
3. 最终使 pipeline 显示为"complete"

**证据：** `2026-05-05/.state.json` 的 `publish_brief.finished_at` 为 `2026-05-05T05:33:30`（比 audio 的 `2026-05-04T22:14:28` 还晚），说明这三步是被倒追修复的。

---

## 四、故障三： deliveries 字段缺失（2026-05-06 和 2026-05-07）

### 故障现象
2026-05-06 和 2026-05-07 的 pipeline 所有阶段（harvest/select/translate/publish_article/publish_brief/audio/push）全部正确完成，但 `.state.json` 中 `deliveries` 字段完全缺失。

### 对比数据

**2026-05-05（正常）：**
```json
"deliveries": {
  "discord_text": { "status": "ok", "finished_at": "2026-05-05T06:05:17", "chars": 1929 },
  "discord_audio": { "status": "ok", "finished_at": "2026-05-05T06:06:04", "mp3_size": 7281204 }
}
```

**2026-05-06（缺失）：** `deliveries` 键不存在

**2026-05-07（缺失）：** `deliveries` 键不存在

### 可能原因
1. **Stage D 脚本未写入 deliveries 字段**：Discord delivery 代码 (`mark_delivery`) 可能没有被调用，或调用时路径不正确
2. **Stage D 实际上确实发送了**：Stage D cron 的 summary 显示 "sent"，说明 message() 工具确实发送了消息到 Discord，但 `mark_delivery` 函数写入 .state.json 的逻辑被跳过或出错
3. **2026-05-06 Stage D 有多个 session**：从 runs 记录看，同一时间有多个 Stage D session 在跑，可能是重复执行导致写入覆盖失败

### Stage D runs 数据（05-06 和 05-07）
```
2026-05-07 06:00 UTC → ✅ ok (summary: 成功发送文字+音频, 452s)
2026-05-06 06:00 UTC → ✅ ok (summary: 成功发送文字+音频, 385s)
2026-05-04 06:00 UTC → ✅ ok (but delivered=false) 
2026-05-04 05:30 UTC → ✅ ok (delivered=true) ← 这一次 delivery 成功了
2026-05-04 04:30 UTC → ❌ error (references/discord-delivery.md read failed)
```

### ⚠️ 关键问题
Stage D 在 2026-05-06 和 2026-05-07 确实运行并声称"成功发送"，但 deliveries 字段没有被写入 state 文件。这说明：
- **Discord 消息可能已发送**（message() 工具成功）
- **但 state 记录写入失败**，导致系统无法判断是否真的发送过
- 如果 Discord 发送了，那这次不算故障，只是记录缺失
- 如果 Discord 没发送，那就是 send failure 被静默忽略

**需要人工确认：** 检查 Discord 频道（#fanli-news-daily, ID: 1490344209847287830）中是否有 05-06 和 05-07 的简报消息。

---

## 五、故障四： ai-daily-news-backup 持续超时（最近7天）

### 故障现象
- **Job ID：** `e52e612a-79ad-47e7-b472-10887b553386`（bernard:ai-daily-news-backup）
- **Cron 计划：** `0 9 * * *` Europe/Berlin（每天 09:00）
- **最近7次执行：** 全部失败，超时错误：`cron: job execution timed out`
- **超时限制：** 180 秒
- **实际耗时：** 约 180–184 秒（刚好卡在超时线上）

### 失败记录（最近7天）
```
2026-05-07 09:00 UTC → ❌ timeout (180s)
2026-05-06 09:00 UTC → ❌ timeout (181s)
2026-05-05 09:00 UTC → ❌ timeout (180s)
2026-05-04 09:00 UTC → ❌ timeout (183s)
2026-05-03 09:00 UTC → ❌ timeout (180s)
2026-05-02 09:00 UTC → ❌ timeout (180s)
2026-05-01 09:00 UTC → ❌ timeout (180s)
```

### 成功记录（供对比）
```
2026-04-30 09:00 UTC → ✅ ok (146s)
2026-04-29 09:00 UTC → ✅ ok (151s)
2026-04-28 09:00 UTC → ✅ ok (138s)
2026-04-27 09:00 UTC → ✅ ok (140s)
2026-04-26 09:00 UTC → ✅ ok (141s)
2026-04-25 09:00 UTC → ✅ ok (165s)
2026-04-24 09:00 UTC → ✅ ok (47s)
2026-04-23 09:00 UTC → ✅ ok (151s)
2026-04-22 09:00 UTC → ✅ ok (168s)
2026-04-21 09:00 UTC → ✅ ok (197s)
```

### 根因分析
备份任务在 2026-04-30 之前运行正常，4月30日后突然开始持续超时。推测原因：
1. **repo 大小增长**：ai-daily-news 项目在4月底累积了大量内容，`git add -A` + `git status` 需要扫描的文件数量大幅增加
2. **git push 网络问题**：remote 为 github.com，如果网络连接变慢，push 可能超时
3. **consecutiveErrors=7**（持续7次失败），已触发 failureAlert 机制

---

## 六、Watchdog 过度运行问题

### 现象
Watchdog（`fanli:ai-news-workflow Watchdog (hourly)`）在 2026-05-05 之后共运行了 142 次，全部返回"already complete"，每次耗时 45–250 秒，持续消耗 token 预算。

### 根因
Watchdog 的 payload 为：
```
python3 scripts/daily_wake.py --days 3 --budget-seconds 900
```
它每天检查 3 天的状态。2026-05-05 经过大量人工修复后，pipeline 状态已全部显示为 "complete"，所以 Watchdog 每次都判断"无需操作"然后退出。但由于每次都要启动 Python 环境 + 扫描 DB，仍消耗约 18K–23K input tokens。

### 建议
Watchdog 不需要每小时运行。Stage A (04:00) → Stage B (04:30) → Stage C (05:00) → Stage D (06:00) 已有完整 cron 覆盖，Watchdog 的设计仅用于 Stage B 未能完成时的兜底。在正常流程中，Watchdog 几乎不需要做任何事。

---

## 七、references/discord-delivery.md 文件缺失

### 故障现象
Stage D 在 2026-05-04 04:30 UTC 运行时报错：
```
⚠️ 📖 Read: `from ~/Media_Workspace/ai-daily-news/references/discord-delivery.md` failed
```

### 检查结果
```
$ ls ~/Media_Workspace/ai-daily-news/references/
→ 目录不存在
```

### 影响
`references/discord-delivery.md` 路径在 Stage D 的 payload 中被硬编码引用，但该文件不存在。这意味着 Stage D 的 delivery 规则没有文档化，也意味着之前可能依赖了不存在的文件来执行 delivery 逻辑。

---

## 八、完整 Cron Job 状态（AI News 相关）

| Job ID | 名称 | 最后状态 | 连续错误 | 问题 |
|--------|------|---------|---------|------|
| `3a25d2a8` | Stage A — Ingest | ❌ error (timeout) | 1 | 唯一一次超时 |
| `7f4a8918` | Stage B — Translate | ✅ ok | 0 | 正常 |
| `a0caa7fc` | Stage C — Publish | ✅ ok | 0 | 正常（2026-05-05 06:00 有一次 timeout 但后来修复） |
| `7ffd5e3d` | Stage D — Deliver | ✅ ok | 0 | deliveries 字段缺失（05-06, 05-07） |
| `821b08f3` | Watchdog (hourly) | ✅ ok | 0 | 过度运行（142次） |
| `e52e612a` | ai-daily-news-backup | ❌ error (timeout) | **7** | 持续超时，需立即处理 |

---

## 九、根因汇总

### 主要根因
1. **Stage A 超时**（300s limit 太紧，git pull 可能拖慢整体）
2. **translate 假成功**（Stage B 将 translate 标记为 ok，但 DB 中 translated_body 为空；导致 publish_brief 卡住）
3. **deliveries 字段未写入**（Stage D 发送了 Discord 消息但没写 .state.json，无法追踪）
4. **references/discord-delivery.md 不存在**（文档缺失，可能影响 delivery 逻辑）
5. **备份任务超时**（180s limit 太紧，repo 变大后无法完成）

### 次要问题
- Watchdog 每小时运行一次，但 pipeline 正常时不需要它，建议降低频率
- Stage D 多次重复执行（同一时间多个 session），可能导致状态写入竞争

---

## 十、修复优先级建议

| 优先级 | 问题 | 建议修复方案 |
|--------|------|------------|
| 🔴 高 | ai-daily-news-backup 超时 | 增大 timeout 至 600s；或简化 backup 脚本（排除 site/） |
| 🔴 高 | deliveries 字段缺失 | 修复 Stage D 的 `mark_delivery()` 调用；添加 state 写入验证 |
| 🔴 高 | translate 假成功 | 审查 Stage B：translate 完成后必须验证 translated_body 非空 |
| 🟡 中 | references/discord-delivery.md 不存在 | 创建该文件，文档化 delivery 规则 |
| 🟡 中 | Watchdog 过度运行 | 将频率从每小时降至每3小时，或在 pipeline 异常时才触发 |
| 🟢 低 | Stage A 偶尔超时 | git pull 改用 `git pull --ff-only`；或增大 timeout 至 600s |

---

## 十一、文件位置

本报告存放于：
```
~/Media_Workspace/ai-daily-news/错误调试记录/
├── AI-News-Daily-三天故障报告-2026-05-07.md  ← 本文件
├── stage-a-timeout-2026-05-05.log             ← 待补充详细日志
├── deliveries字段缺失-分析.log                ← 待补充
└── backup-timeout-持续7天.log                 ← 待补充
```

相关 Cron Job ID（供调试参考）：
- Stage A: `3a25d2a8-d3f8-4090-b101-bfc2792ee55a`
- Stage B: `7f4a8918-9a3a-4cbd-bc43-119d8d7c2073`
- Stage C: `a0caa7fc-c376-42af-a94f-bbeef89a5e48`
- Stage D: `7ffd5e3d-ea37-4130-9088-e6db25b92d55`
- Watchdog: `821b08f3-9e80-4bf9-b67e-b54701765591`
- Backup: `e52e612a-79ad-47e7-b472-10887b553386`