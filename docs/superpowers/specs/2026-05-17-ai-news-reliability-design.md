# AI Daily News —「每日必达」可靠性改造设计

- 日期: 2026-05-17
- 状态: 已批准, 实施中
- Owner: Fanli (OpenClaw) / 人工介入: 本次由 Claude Code 实施

## 1. 背景与真实根因

经独立核查(非沿用问题报告), 确认:

- **根因**: `translate` 是流水线唯一的认知步骤, 由 isolated session 的
  `minimax-portal/MiniMax-M2.7` agent (Stage B) 完成。已确认 **2026-05-12 /
  05-13 / 05-17 三天**全部卡在 `translate` 且全天零产出。
  `daily_pipeline.run_steps` 遇第一个 `failed` 步骤即整条 `break`
  (`daily_pipeline.py:347`), watchdog (`daily_wake.py`) 只能重跑确定性步骤、
  做不了翻译 → translate 失败后**没有任何自动恢复路径**(只能等次日
  04:30 Stage B, 即 ~24h 后)。
- **报告误判**(已排除): Stage D 2026-05-18 实际 06:02 UTC 正常触发, 当天
  完整成功; `thinking xhigh` 是无害降级。这两条 P0/P2 不成立。
- **次生灾害**: 失败日选中的文章从未 `mark_played` → 堆成 backlog;
  `news_db.get_unplayed` 用 `ORDER BY importance DESC`
  (`news_db.py:244`), 高分老文持续压过新文 → 表现为"播 6 天前旧闻"。
- **文档与现实脱节**: `~/.agents/skills/ai-news-workflow/` 的 SKILL.md /
  recovery-playbook.md 描述 v3.1(11 cron、Stage B retry、健康检查), 但
  `~/.openclaw/cron/jobs.json` 实际只有 5 个 cron、朴素 hourly watchdog、
  零 retry/健康 cron。文档里的自愈机制是幻觉。

## 2. 设计原则

> **选稿灵活, 翻译必达, 降级有底, 失败自愈。** 一个会超时/会抽风的 LLM,
> 不能让任何一天归零。

不变式: `harvest/select` 确定性成功 → `translate` 在多个 retry 窗口里把
**当日选定的全部文章**逐条翻完(逐条 checkpoint, 幂等重入) → 到最后期限
仍有翻不动的"毒文章"则**丢回 unplayed 池、用已翻完的发**(≥ MIN_BRIEFING
即出报, 绝不归零) → `publish/audio/push/deliver` 由 cron + 增强 watchdog
接力, translate 一 ok 立即推进。

## 3. 模块设计

### 共享配置 `scripts/lib/config.py`(新增, 唯一真相源)

```
HALFLIFE_HOURS   = 36     # 选稿时间衰减半衰期
AGING_DAYS       = 5      # unplayed 超此天数 → archived
MIN_BRIEFING     = 3      # 低于此条数不出报(drop 兜底的硬闸)
SELECT_POOL      = 200    # 选稿候选池上限(按新鲜度取, Python 再算衰减分)
DEFAULT_MAX_AGE_DAYS = 7  # select 硬截断(冗余安全网)
DROP_DEADLINE_UTC = (6, 25)  # 过此 UTC 时刻 watchdog 触发确定性兜底 finalize
```

非"为单次任务建抽象": 这些常量被 select_top / translate_helper /
daily_wake 三处共用, 集中是为消除漂移(本次工作主题)。

### 模块 1 — 选稿: 时间衰减评分 + 数量灵活 + aging

`scripts/lib/news_db.py`:

- 废弃 `get_unplayed` 的 `ORDER BY importance DESC`(仅 select_top 调用,
  无其他 caller)。改 `ORDER BY COALESCE(published_at, discovered_at) DESC
  LIMIT pool` —— 返回**按新鲜度排序**的候选池(保证新文一定进池, 不会
  被高分老文挤出池)。`min_importance` / `published_after` 过滤保留。
- 新增 `archive_stale_unplayed(cutoff_iso) -> int`:
  `UPDATE news_articles SET broadcast_status='archived' WHERE
  broadcast_status='unplayed' AND COALESCE(published_at,discovered_at)
  < ?`, 事务包裹, 返回受影响行数。

`scripts/select_top.py`:

- 先 aging: 归档 unplayed 中 `COALESCE(pub,disc)` 早于
  `now-AGING_DAYS` 的(失败日 backlog 自然清除, 永不再选)。
- 取候选池(recency 序, ≤ SELECT_POOL), Python 计算
  `score = importance * 0.5 ** (age_hours / HALFLIFE_HOURS)`,
  按 score 降序取前 `count`。`age_hours` 由 `COALESCE(published_at,
  discovered_at)` 到 `now(UTC)`; 健壮解析 `YYYY-MM-DD` /
  完整 ISO / `Z` / `+00:00`; 不可解析按"很旧"处理(score≈0)。
- **数量灵活**: 候选不足 `count` 则有几条选几条。修复当前 0 行时
  `sys.exit(0)` **不写文件**导致 step_select 误判 failed 的 bug ——
  始终写 `daily-selected.json`(哪怕 0 条); 0 条时打印明确
  `NO-NEWS DAY` 警告并 exit 0(真·无新闻日由后续 verifier 失败 +
  failureAlert 暴露, 不伪造)。
- 不依赖 SQLite `power()`(遵循 evidence-first: 不假设外部系统能力);
  衰减数学在 Python, 可单测。

### 模块 2 — 翻译必达: `pending` + `finalize --drop-untranslated`

`scripts/translate_helper.py`:

- 新增子命令 `pending --date [--json]`: 对比 `daily-selected.json` ids
  与 DB。一条算"已翻完"当且仅当 DB 行的 `translated_title /
  translated_summary / translated_body / impact_analysis` 四列均非空
  (与 verifier 完整性口径一致)。打印未翻 id 列表; `--json` 输出
  `{"pending":[...],"done":[...],"total":N}` 供 watchdog 用; 恒 exit 0。
- `finalize` 新增 `--drop-untranslated`(仅兜底用; 默认行为不变,
  仍是全量 all-or-nothing):
  1. 算 pending; `done_ids = selected - pending`。
  2. `len(done_ids) < MIN_BRIEFING` → 报错 exit 1, **不**改 state
     (translate 仍非 ok, 由 failureAlert 暴露)。
  3. 否则重写 `daily-selected.json` 仅保留 `done_ids`(保序、保留
     原文 dict)。被丢 id **不** mark_played → 仍 unplayed, 5 天内可
     被重新选中(下次带新衰减分再战), 超 AGING_DAYS 自然归档。
  4. 确保 `audio_script.md` 存在且 ≥ `MIN_AUDIO_SCRIPT_CHARS`(800);
     缺失/过短 → **确定性合成**一份: 由 `done_ids` 的
     `translated_title/summary` 拼一段口语化中文稿(开场白 + 逐条
     "第N条, <标题>。<摘要>" + 结语), 保证 ≥ 800 字。这是 watchdog
     无需认知即可兜底的关键。
  5. 跑 verifier(此时仅校验保留的 ids + audio_script)。rc=0 →
     `state.translate=ok` + `mark_played(done_ids)`; rc≠0 → exit 1。

### 模块 4 — watchdog 增强: 确定性翻译兜底

`scripts/daily_wake.py`:

- 处理某日(walk_days 与 `--date` 两条路径)前, 若该日
  `next_pending == 'translate'` 且 `select == ok` 且
  (日期 < 今天 **或** 今天且 `now_utc >= DROP_DEADLINE_UTC`):
  先跑 `python3 scripts/translate_helper.py finalize --date <d>
  --drop-untranslated`(确定性子进程, 受 budget 约束)。成功则
  translate 解锁, 随后正常 `run_pipeline` 自动推进 publish→push。
  这是 translate 失败**首次**拥有的自动恢复路径, 同时自愈历史卡死日。
- 守卫: 仅当存在 ≥1 已翻文章才兜底(否则保持 failed 让 failureAlert
  暴露真·无内容日)。`reset_running` / 三闸短路 / Stage D 边界不变。

### 模块 3 — cron: 落地 retry 集 + 重排时序

`~/.openclaw/cron/jobs.json`(改前已备份
`jobs.json.bak-<ts>`; 改后 cron list 验证)。新时序(UTC):

| Cron | expr | timeout | 职责 | 前置(payload 内判断) |
|---|---|---|---|---|
| Stage A · Ingest | `0 4 * * *` | 300 | harvest+select(含 aging) | 无 |
| Stage B · Translate | `30 4 * * *` | 1200 | 翻 pending(认知) | select=ok ∧ translate≠ok |
| **Stage B retry**(新) | `15 5 * * *` | 1200 | 翻剩余 pending | 同上 |
| **Stage B deep-retry**(新) | `0 6 * * *` | 1200 | 最后一次认知重翻 | 同上 |
| **Stage B fallback-finalize**(新) | `25 6 * * *` | 300 | `finalize --drop-untranslated`(确定性) | select=ok ∧ translate≠ok |
| Stage C · Publish | `30 6 * * *` | 1200 | publish+audio+push | translate=ok |
| Stage D · Deliver | `0 7 * * *` | 600 | Discord 文字+音频 | push=ok |
| Watchdog | `0 * * * *` | 1200 | 确定性接力 + 过 06:25 兜底翻译 | 无 |

新 cron 全部 `agentTurn` / isolated / `wakeMode:now`, 镜像现有 Stage B
结构(`sessionKey`、`delivery.mode=none`、`failureAlert after:1 → 管理
频道); payload 内脚本一律绝对路径; 前置不满足时 agent 以 rc=0 静默退出。
fallback-finalize 与增强 watchdog 互为冗余(双保险), fallback-finalize
给确定性时点, watchdog 给兜底。

### 模块 5 — 文档对齐 + 2 个真实小 bug

- `scripts/translate_helper.py`: `VALID_TAGS` 硬编码含 `"china"`, 而
  `data/tags.json` / verifier 用 `"china-ai"` → 改为运行时从
  `data/tags.json` 读(与 `verify_translations.py:38` 同源)。
- `scripts/git_publish.py:45`: `git -check-ignore`(少一横杠, 永远
  rc≠0, gitignore 跳过分支从不生效) → 改 `git check-ignore`。
- 重写 `~/.agents/skills/ai-news-workflow/` 的 `SKILL.md` /
  `recovery-playbook.md` / `cron-payload-templates.md` /
  `pipeline-protocol.md` 对齐**实际部署的 8-cron 集**, 删除幻觉 v3.1
  描述; 增加脚本→所有者→绝对路径归属表(遵循 explicit-paths 记忆)。

### 模块 6 — 验证 & 回放

- `tests/`(新增, pytest): 衰减评分排序、pending 计算、drop 的
  MIN_BRIEFING 闸、aging 截断、ISO 解析健壮性。
- 只读 dry-run: 对真实 DB 跑选稿纯函数, 核对新旧排序差异。
- 历史 05-12/05-13/05-17: 选稿已丢(daily-selected.json 每日覆盖、
  失败日无 meta.json), 文章亦将随 aging 归档 → **不自动回放**,
  在收尾向 owner 说明, 由其决定是否手工补。

## 4. 风险与取舍

- 无"100% 全翻完"硬保证(对抽风 LLM 不可能): 用多窗口 retry 争取
  正常全翻 + 确定性兜底保 ≥ MIN_BRIEFING 出报。最差 = 发 ≥3 条 +
  毒文章下次再战, 而非归零。
- 已知遗留(本次不修, 风险隔离): `harvest.py:67` 无 pubDate 时
  `published_at=now()` 会让重发旧条目显新 —— 与衰减/aging 正交,
  另案处理。
- 复杂度集中在 cron 时序与 watchdog; 模块 5/6 保证可排障、可回归。
```
