# 回滚指南（Rollback Guide）

> 适用：RoboParts 主站（Cloudflare Pages + Workers）
> 最后更新：2026-10-18
> 关联：`docs/deploy.md`

---

## 一、回滚触发条件

满足以下任一条件即执行回滚：

| 级别 | 条件 | 目标 RTO |
|---|---|---|
| P0 | 线上 API 5xx > 5% 持续 5 分钟 | 15 分钟 |
| P0 | 线上数字与仓内不一致（>10%） | 15 分钟 |
| P1 | 核心功能不可用（兼容性判定 / BOM 导出） | 1 小时 |
| P1 | 新增功能导致回归（CI 全绿但线上红） | 1 小时 |
| P2 | 性能劣化 > 50%（P95 延迟） | 4 小时 |

---

## 二、回滚层级

```
L1 · 内容回滚（Pages 静态资产）
  └─ 适用：页面/文档/样式问题
  └─ 时间：< 5 分钟

L2 · 产物回滚（api/*.json 派生数据）
  └─ 适用：数字漂移 / 判定结果异常
  └─ 时间：< 15 分钟

L3 · 代码回滚（Workers 函数）
  └─ 适用：API 端点逻辑错误
  └─ 时间：< 30 分钟

L4 · 数据回滚（KV 存储）
  └─ 适用：KV 数据污染 / 配置错误
  └─ 时间：< 1 小时
```

---

## 三、L1 · 内容回滚

Cloudflare Pages 保留最近 100 个部署版本，可直接切换。

### 步骤

1. **找到目标版本**：访问 https://dash.cloudflare.com/ → Pages → roboparts → Deployments
2. **回滚**：点击目标版本的 "Promote to production"
3. **验证**：`curl https://roboparts.cc/api/data.json | python -c "import sys,json;print(json.load(sys.stdin)['meta']['total_entities'])"`

### 或通过 CLI

```bash
# 列出部署历史
npx wrangler pages deployments list --project-name roboparts

# 回滚到指定部署
npx wrangler pages deploy . --project-name roboparts --branch <deployment-id>
```

---

## 四、L2 · 产物回滚

派生产物（`api/*.json`）由 `scripts/regen_derived.py` 从真相源生成。回滚真相源即可。

### 步骤

1. **定位问题产物**：检查 `api/` 下哪些 JSON 有异常
2. **回滚真相源**：
   ```bash
   # 查看真相源变更
   git log --oneline -10 -- api/entities.json

   # 回滚到指定 commit
   git checkout <commit-hash> -- api/entities.json
   ```
3. **重新生成产物**：
   ```bash
   python scripts/regen_derived.py
   ```
4. **跑 CI 闸门**：
   ```bash
   python scripts/ci_gate.py
   ```
5. **推送部署**：
   ```bash
   git add -A && git commit -m "rollback: 回滚派生产物到 <commit>" && git push origin main
   ```

---

## 五、L3 · 代码回滚

Workers 函数通过 Git commit 回滚。

### 步骤

1. **找到故障 commit**：
   ```bash
   git log --oneline -20 -- functions/
   ```
2. **回滚**：
   ```bash
   # 软回滚（保留历史）
   git revert <commit-hash>

   # 或硬回滚（危险，会丢失后续 commit）
   git reset --hard <commit-hash>
   ```
3. **重新部署**：
   ```bash
   git push origin main
   ```

---

## 六、L4 · 数据回滚

KV 数据无版本历史，回滚需从备份恢复。

### 步骤

1. **定位问题 KV**：检查 `USER_CREDITS` / `IDEMPOTENCY_KV` / `ANALYTICS_KV`
2. **导出当前数据**：
   ```bash
   npx wrangler kv key list --namespace-id <kv-namespace-id> > backup-$(date +%Y%m%d).txt
   ```
3. **恢复备份**：
   ```bash
   # 从备份文件恢复
   npx wrangler kv key put --namespace-id <kv-namespace-id> <key> <value>
   ```
4. **验证**：检查关键端点是否恢复

### 备份策略

- **自动**：每日快照到 `backups/kv-YYYYMMDD.json`（见 `scripts/backup_kv.py`）
- **手动**：重大变更前 `npx wrangler kv key list > manual-backup.txt`

---

## 七、回滚验证

回滚完成后必须验证：

```bash
# 1. 线上数字一致
python scripts/verify_live_numbers.py

# 2. CI 闸门全绿
python scripts/ci_gate.py

# 3. 核心端点可用
curl -s https://roboparts.cc/api/data.json | python -c "import sys,json;d=json.load(sys.stdin);print('OK:',d['meta']['total_entities'],'entities')"
curl -s https://roboparts.cc/api/compatibility -X POST -H 'Content-Type: application/json' -d '{"a":"ACT-001","b":"GIP-001"}' | python -c "import sys,json;print('OK:',json.load(sys.stdin)['verdict'])"
```

---

## 八、回滚演练记录

| 日期 | 层级 | 触发条件 | 回滚目标 | 耗时 | 结果 |
|---|---|---|---|---|---|
| 2026-10-18 | - | 文档初建，尚未演练 | - | - | 待首次演练 |

> **纪律**：RTO/RPO 只登记不演练 = 假安全。首次演练应在 Phase 3 收口前完成。

---

## 九、回滚禁止事项

| 禁止 | 原因 |
|---|---|
| 硬回滚 main 分支（`git reset --hard` + `--force`） | 会丢失其他 commit，需团队同步 |
| 回滚 KV 数据前不备份 | 数据污染场景下备份是唯一救命绳 |
| 跳过 CI 闸门直接部署回滚 | 回滚本身可能引入新 bug |
| 回滚后不更新部署文档 | 下次回滚会踩同一个坑 |

---

## 十、与灾难恢复的关系

| 维度 | 回滚 | 灾难恢复 |
|---|---|---|
| 范围 | 单次部署 / 单份产物 | 整个站点 / 全量数据 |
| 时间 | 分钟级 | 小时级 |
| 文档 | 本文档 | `docs/disaster-recovery.md` |
| 演练频率 | 按需 | 季度 |

回滚是灾难恢复的子集——**能回滚就回滚，不能回滚才启用灾难恢复**。

---

*本文档初建于 2026-10-18。首次回滚演练应在 Phase 3 收口前完成，并更新第八节演练记录。*
