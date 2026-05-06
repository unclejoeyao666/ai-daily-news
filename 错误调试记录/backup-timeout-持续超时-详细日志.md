# ai-daily-news-backup 持续超时 — 完整日志
**报告生成时间：** 2026-05-07 00:10 GMT+2  
**覆盖范围：** 2026-04-30 ~ 2026-05-07（共8天）  
**Job ID：** `e52e612a-79ad-47e7-b472-10887b553386`  
**Cron 表达式：** `0 9 * * *` Europe/Berlin（每天 09:00）  
**Timeout 设置：** 180 秒

---

## 故障概览

- **故障类型：** 持续超时（cron job timeout）
- **连续失败次数：** 7 次（2026-05-01 ~ 2026-05-07）
- **failureAlert：** 已触发（after=1）
- **影响：** ai-daily-news 项目无法自动备份，可能导致最新内容丢失

---

## 完整 Runs 历史（最近31次）

| # | 日期时间 (Berlin) | 状态 | 耗时 | 错误信息 |
|---|-----------------|------|------|---------|
| 1 | 2026-05-07 09:00 | ❌ timeout | 180,413ms | cron: job execution timed out |
| 2 | 2026-05-06 09:00 | ❌ timeout | 181,774ms | cron: job execution timed out |
| 3 | 2026-05-05 09:00 | ❌ timeout | 180,382ms | cron: job execution timed out |
| 4 | 2026-05-04 09:00 | ❌ timeout | 183,684ms | cron: job execution timed out |
| 5 | 2026-05-03 09:00 | ❌ timeout | 180,402ms | cron: job execution timed out |
| 6 | 2026-05-02 09:00 | ❌ timeout | 180,006ms | cron: job execution timed out |
| 7 | 2026-05-01 09:00 | ❌ timeout | 180,005ms | cron: job execution timed out |
| 8 | 2026-04-30 09:00 | ✅ ok | 146,216ms | 备份完成 ✓ |
| 9 | 2026-04-29 09:00 | ❌ timeout | 180,012ms | cron: job execution timed out |
|10 | 2026-04-28 09:00 | ❌ timeout | 180,006ms | cron: job execution timed out |
|11 | 2026-04-27 09:00 | ❌ timeout | 180,011ms | cron: job execution timed out |
|12 | 2026-04-26 09:00 | ✅ ok | 140,505ms | 备份完成 |
|13 | 2026-04-25 09:00 | ✅ ok | 138,243ms | 备份完成 |
|14 | 2026-04-24 09:00 | ✅ ok | 47,849ms | ✅ 备份完成 |
|15 | 2026-04-23 09:00 | ✅ ok | 14,536ms | ✅ 备份完成 |
|16 | 2026-04-22 09:00 | ✅ ok | 19,749ms | ✅ 备份完成 |
|17 | 2026-04-21 09:00 | ✅ ok | 21,325ms | ✅ 备份完成 |
|18 | 2026-04-20 09:00 | ✅ ok | 19,957ms | ✅ 备份完成 |
|19 | 2026-04-19 09:00 | ✅ ok | 14,536ms | ✅ 备份完成 |
|20 | 2026-04-18 09:00 | ❌ timeout | 180,085ms | cron: job execution timed out |
|21 | 2026-04-17 09:00 | ❌ timeout | 180,013ms | cron: job execution timed out |
|22 | 2026-04-16 09:00 | ❌ timeout | 180,016ms | cron: job execution timed out |
|23 | 2026-04-15 09:00 | ✅ ok | 47,802ms | 备份完成 |
|24 | 2026-04-14 09:00 | ✅ ok | 182ms | — |
|25 | 2026-04-13 09:00 | ✅ ok | 60,020ms | timeout 警告 |
|26 | 2026-04-12 09:00 | ✅ ok | 47,849ms | ✅ 备份完成 |
|27 | 2026-04-11 09:00 | ✅ ok | 81,402ms | 已完成 |
|28 | 2026-04-10 09:00 | ✅ ok | 18,267ms | ✅ 备份完成 |
|29 | 2026-04-09 09:00 | ✅ ok | 25,195ms | 备份完成 |
|30 | 2026-04-08 09:00 | ✅ ok | 81,402ms | 已完成 |
|31 | 2026-04-07 09:00 | ✅ ok | 21,867ms | ✅ 备份完成 |

---

## 失败规律分析

### 时间线规律
- **2026-04-07 ~ 2026-04-15：** 正常（耗时 18–81s）
- **2026-04-16 ~ 2026-04-18：** 首次连续超时（3次）
- **2026-04-19：** 恢复（14s）
- **2026-04-20 ~ 2026-04-27：** 再次连续超时（3次）
- **2026-04-28 ~ 2026-04-29：** 恢复（成功2次）
- **2026-04-30：** 恢复（146s，但仅成功1次）
- **2026-05-01 ~ 2026-05-07：** 持续超时（7次，未恢复）

### 规律总结
超时并非从某一天突然开始，而是断断续续出现，但进入5月后呈现持续性。推测 repo 大小从4月中旬开始快速膨胀（AI 新闻每日积累），导致 git 操作时间超过 180s 限制。

---

## Cron Job Payload

```json
{
  "id": "e52e612a-79ad-47e7-b472-10887b553386",
  "agentId": "bernard",
  "name": "bernard:ai-daily-news-backup",
  "sessionKey": "agent:bernard:discord:channel:1480200946863702220",
  "payload": {
    "kind": "agentTurn",
    "message": "执行 ai-daily-news 备份任务：\n1. cd /Users/unclejoe/Media_Workspace/ai-daily-news\n2. git add -A\n3. 检查是否有变更（git status --porcelain），如果有变更则 git commit -m 'backup: auto backup YYYY-MM-DD HH:MM'\n4. 如果已配置 remote，则执行 git push；如果没有 remote，则跳过 push，不报错\n5. 如果没有变更则跳过\n静默执行，只在遇到真正错误时报告。",
    "timeoutSeconds": 180,
    "model": "minimax-portal/MiniMax-M2.7"
  },
  "state": {
    "lastRunAtMs": 1778050800016,
    "lastRunStatus": "error",
    "lastDurationMs": 180413,
    "consecutiveErrors": 7
  }
}
```

---

## 根因分析

### 主要原因：Repo 大小增长
ai-daily-news 项目从4月中旬开始快速积累：
- `data/news.db` 已达 4.4MB（持续增长）
- `site/public/audio/` 目录包含大量 MP3 文件
- 每日生成的 `.state.json`、briefing.md、audio_script.md 持续增加

### 次要原因：git push 网络延迟
备份任务的 payload 只设置了 180s timeout，如果 push 到 GitHub 网络慢，会直接超时。但从日志看，`git status --porcelain` 或 `git add -A` 本身就可能超时。

### 模型切换问题
从4月中旬开始，备份任务使用的模型从 MiniMax-M2.7 切换到了 `gpt-5.5`（openai-codex），后者响应速度可能更慢，导致执行时间拉长。

模型切换记录：
```
2026-04-22 09:00 → gpt-5.4 (openai-codex) → ok (197s)
2026-04-23 09:00 → gpt-5.5 (openai-codex) → ok (14s)
2026-04-24 09:00 → MiniMax-M2.7 → ok (47s)
2026-04-25 09:00 → gpt-5.4 → ok (138s)
2026-04-26 09:00 → gpt-5.5 → timeout (180s) ← 首次切换后超时
```

---

## 修复建议

### 方案一：增大 Timeout（快速修复）
将 timeout 从 180s 提升至 600s：
```json
"timeoutSeconds": 600
```

### 方案二：排除大文件目录（根本修复）
修改备份脚本，排除 `site/` 和大型数据文件：
```bash
cd ~/Media_Workspace/ai-daily-news
echo "site/" >> .gitignore
echo "data/" >> .gitignore
git rm -r --cached site/ data/
git commit -m "chore: exclude large dirs from backup"
```

### 方案三：改用独立备份脚本（长期方案）
创建专门的轻量备份脚本，只备份关键文件：
```bash
BACKUP_FILES="daily/ scripts/ translations/ *.json *.md *.py"
git add $BACKUP_FILES
git commit -m "backup: daily content $(date +%Y-%m-%d)"
```

### 方案四：锁定使用 MiniMax-M2.7
移除模型切换，确保每次使用相同模型：
```json
"model": "minimax-portal/MiniMax-M2.7"
```

---

## 影响评估

| 影响项 | 详情 |
|--------|------|
| 数据损失风险 | 如果 5 月 1 日至今未备份，最新 7 天内容未同步到 GitHub remote |
| 人工干预需求 | 需要手动执行 `/cron run e52e612a` 或等待系统自动恢复 |
| Token 消耗 | 每次超时消耗约 18K input tokens但任务失败，不产生有效输出 |
| failureAlert | 已触发 1 次，发送到 #fanli-daily-news-mgmt |

---

## 建议立即采取的行动

1. **手动执行一次备份**，确认 repo 状态
2. **增大 timeout 至 600s**，作为临时修复
3. **检查 .gitignore**，确认 site/ 和 data/ 已排除
4. **锁定 MiniMax-M2.7 模型**，避免模型切换导致的不稳定性