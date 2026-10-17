# 灾备与恢复演练

> **Phase 3 承重结构 7**（审计 §4 "灾备"）。
>
> 之前项目无恢复演练记录——`scripts/backup/` 里的 snapshot/restore 脚本
> 存在但**从未在生产环境跑过一次**。本文件把演练口径锁死：不做演练的
> 备份等于没备份。

## 一、备份资产清单

| 资产 | 快照脚本 | 快照位置 | 恢复脚本 | 上次演练 |
|---|---|---|---|---|
| `api/*.json` 全量 | `scripts/backup/snapshot_api.py` | `.backups/api-YYYY-MM-DD/` | `scripts/backup/restore.py --api` | 从未 |
| Cloudflare KV 全表 | `scripts/backup/snapshot_kv.py` | `.backups/kv-YYYY-MM-DD/` | `scripts/backup/restore.py --kv` | 从未 |
| Git 仓库（含 SBOM/lock） | `git log` | GitHub 远端 | `git clone && npm ci` | 从未 |

**注**：以上"从未"是诚实登记，不是营销话术。首次演练是 Phase 3 收口的一部分。

## 二、恢复流程（RTO 目标：2 小时）

```bash
# 1. 拉最新快照
ls -t .backups/api-*/ | head -1

# 2. 恢复 API 数据（会写回 api/*.json）
python scripts/backup/restore.py --api --from .backups/api-2026-10-17/ --dry-run
python scripts/backup/restore.py --api --from .backups/api-2026-10-17/ --apply

# 3. 恢复 KV（需要 wrangler token）
python scripts/backup/restore.py --kv --from .backups/kv-2026-10-17/ --namespace API_KEYS --apply

# 4. 验证：跑完整 CI
python scripts/ci_gate.py
```

## 三、演练记录（append-only）

格式：日期 / 触发原因 / 步骤耗时 / 结果 / 修复项

| 日期 | 触发原因 | RTO 实测 | 结果 | 修复项 |
|---|---|---|---|---|
| 2026-10-17 | 首次登记，尚未实际演练 | — | 未执行 | 建 CI 恢复演练闸门 |

## 四、RTO/RPO 目标

- **RTO**（Recovery Time Objective）：≤ 2 小时
- **RPO**（Recovery Point Objective）：≤ 24 小时
- **恢复验证**：恢复后必须跑 `scripts/ci_gate.py` 全绿，否则视为恢复失败

## 五、待办（Phase 3 完整收口）

- [ ] 首次全量演练（预计 2026-11-XX）
- [ ] 演练自动化脚本 `scripts/dr_drill.py`（模拟 KV 丢表 → 恢复 → CI 校验）
- [ ] 与 Cloudflare 支持确认 KV 官方备份能力（当前只能自研）
- [ ] 演练记录进 `api/performance_history.json` 同一份季度快照

---

**状态**：v0.1（2026-10-17 首次登记），首次真实演练为 Phase 3 收口门槛。
