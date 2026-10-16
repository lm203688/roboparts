# 灾备 Runbook · RoboParts

> 审计依据：`docs/RoboParts-地基审计与硬骨头攻坚报告-20261016.md` §F6
> **场景目标**：任何数据事故 → 90 分钟内恢复业务连续性

## 1. 备份清单

| 资产 | 位置 | 工具 | 频率 | 保留期 |
|---|---|---|---|---|
| `api/*.json` 数据 | `backdrops/<snap_id>/` | `python scripts/backup/snapshot_api.py` | 部署前 + 每日 | 90 天 |
| `api/data.js` | 同上 | 同上 | 同上 | 90 天 |
| Cloudflare KV × 5 | `backdrops/<snap_id>/<NS>.json` | `python scripts/backup/snapshot_kv.py` | 每 6h（需自动化） | 90 天 |
| Git commit 锚点 | GitHub main branch | Git tag（deploy.mjs 自动生成） | 每次部署 | 永久 |

**注意**：`backdrops/` 已被 `.gitignore` 忽略（快照含 API_KEYS 敏感数据，不入仓）。
长期归档需要人工拷贝到对象存储或本地外接盘。

## 2. 触发条件（何时回滚）

| 事故类型 | 严重级 | 处置 |
|---|---|---|
| 线上 `curl /api/data.json` 数字对不上 `entities.json.count` | 🔴 P0 | 立即回滚到最近一个通过 CI 的快照 |
| 用户投诉 KV 数据丢/错（积分、供应商） | 🔴 P0 | 立即恢复 KV 快照 |
| CI gate `产物新鲜度检查` 大面积红 | 🟠 P1 | 排查 producer，必要时回滚 |
| 前端 502/504 大面积 | 🟠 P1 | 检查 CF Pages 部署，必要时回滚 tag |
| 单个页面错字/样式 | 🟢 P3 | 正常走 PR，不回滚 |

## 3. 恢复流程

### 3.1 数据恢复（api/ 目录）

```bash
# 步骤 1：查看可用快照
python scripts/backup/restore.py --list

# 步骤 2：预演（不动文件，只看会恢复哪些）
python scripts/backup/restore.py <snap_id> --dry-run

# 步骤 3：实际恢复（自动备份当前 api/ 到 .pre_restore_*）
python scripts/backup/restore.py <snap_id> --confirm

# 步骤 4：跑 CI 验证
python scripts/ci_gate.py
python scripts/check_freshness.py

# 步骤 5：重新部署
node scripts/deploy.mjs
```

### 3.2 KV 恢复（Cloudflare namespace）

```bash
# 前置：设置环境变量
export CLOUDFLARE_API_TOKEN=xxx
export CLOUDFLARE_ACCOUNT_ID=xxx

# 步骤 1：查看可用快照
python scripts/backup/snapshot_kv.py --list

# 步骤 2：单个 namespace 恢复（如 USER_CREDITS 出问题）
python scripts/backup/snapshot_kv.py \
  --restore USER_CREDITS backdrops/<snap_id> \
  --confirm

# 步骤 3：验证（挑关键 key 抽样）
npx wrangler kv get USER_CREDITS <some_key>
```

### 3.3 部署回滚（Cloudflare Pages）

```bash
# Cloudflare Pages 支持从任意 deployment 回滚，也可用 Git tag：
git tag -l "deploy-*"                # 列所有部署 tag
git checkout deploy-YYYYMMDD-HHMMSS  # 切到那个 tag
node scripts/deploy.mjs              # 重新部署那个 commit

# 或者用 Cloudflare Dashboard → Deployments → Rollback 按钮
```

## 4. 演练节奏（P0 必须演练）

| 演练 | 频率 | 负责人 |
|---|---|---|
| 恢复演练（api/ 全量） | 每季度一次 | 值班工程师 |
| KV 恢复演练 | 每季度一次 | 值班工程师 |
| 部署回滚演练 | 每月一次 | 值班工程师 |

**演练记录**：完成后在 `docs/runbook/drills/YYYYMMDD.md` 写一次简短报告（用时、坑、改进项）。

## 5. 常见故障排查

### Q: 快照 SHA256 校验失败
A: 快照文件可能被修改过（拷贝错误、恶意篡改）。
   - 检查 `backdrops/<snap_id>/manifest.json` 里的 sha256 是否与实际文件匹配
   - 如果不匹配，视为快照损坏，跳到下一个可用快照

### Q: KV 恢复后线上仍然异常
A: 可能是应用层缓存（Cloudflare 边缘节点）未刷新。
   - 用 Cloudflare Dashboard → Caching → Purge Everything 强制刷新
   - 或等 15 分钟自然过期

### Q: 恢复后发现新版本已被下游消费
A: 触发 `X-Data-Version` 变更事件（见 `docs/api-versioning.md`）。
   - 在 `docs/runbook/api-version-bumps.md` 记录版本变更
   - 通知下游 Agent 更新缓存

## 6. 备份自动化（TODO）

当前脚本是手工执行。生产环境应加：
- GitHub Actions schedule：每天凌晨 3 点跑 `snapshot_api.py --upload`
- Cloudflare Workers Cron：每 6 小时跑 `snapshot_kv.py`
- Slack/Discord webhook：备份失败时告警

（本阶段未做，需用户凭据配置后启用）
