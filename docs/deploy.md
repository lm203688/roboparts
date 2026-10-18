# 部署指南（Deploy Guide）

> 适用：RoboParts 主站（Cloudflare Pages + Workers）
> 最后更新：2026-10-18

---

## 一、部署架构

```
GitHub main 分支
  │
  ▼
GitHub Actions (deploy.yml)
  │
  ├─ pre_deploy_check.py    ← 数字漂移 + dirty-tree 守卫
  ├─ npm run build          ← 前端构建
  ├─ python scripts/regen_derived.py  ← 产物再生成
  └─ npm run deploy         ← Cloudflare Pages 部署
        │
        ▼
Cloudflare Pages (roboparts.pages.dev)
        │
        ▼
Cloudflare Workers (roboparts.cc/api/*)
        │
        ▼
Cloudflare KV (USER_CREDITS, IDEMPOTENCY_KV)
```

---

## 二、本地部署（开发/测试）

```bash
# 1. 安装依赖
npm install

# 2. 运行 CI 闸门
python scripts/ci_gate.py

# 3. 重新生成产物
python scripts/regen_derived.py

# 4. 预部署检查（数字漂移 + dirty tree）
python scripts/pre_deploy_check.py

# 5. 部署到 Cloudflare Pages
npm run deploy
```

---

## 三、GitHub Actions 自动部署

- **触发条件**：push 到 main 分支
- **流程**：见 `.github/workflows/deploy.yml`
- **环境**：Node 20 + Python 3.11

### 关键步骤

1. **pre_deploy_check.py**
   - 检查 `entities.json` 数字与 README 一致
   - 检查工作区无未提交变更
   - 失败则阻止部署

2. **regen_derived.py**
   - 重新生成所有派生产物（api/*.json）
   - 校验新鲜度（产物 mtime > 上游 mtime）

3. **deploy.mjs**
   - 上传到 Cloudflare Pages
   - 配置环境变量
   - 部署 Workers

---

## 四、手动部署（紧急修复）

```bash
# 1. 推送 commit
git push origin main

# 2. 或手动触发 GitHub Actions
#    访问 https://github.com/lm203688/roboparts/actions

# 3. 或直接用 Cloudflare CLI
npx wrangler pages deploy dist --project-name roboparts
```

---

## 五、环境变量

### Cloudflare Pages

| 变量 | 说明 | 示例 |
|---|---|---|
| `ANALYTICS_API_KEY` | 分析端点 key | sk-xxx |
| `ANALYTICS_SECRET` | 分析端点 secret | eyJxxx |
| `BOM_STORAGE_KEY` | BOM 存储 key | sk-xxx |
| `SELECTION_STORAGE_KEY` | 选型存储 key | sk-xxx |

### Cloudflare Workers

| 变量 | 说明 | 示例 |
|---|---|---|
| `USER_CREDITS` | 用户积分 KV 命名空间 | user-credits |
| `IDEMPOTENCY_KV` | 幂等性 KV 命名空间 | idempotency |
| `ANALYTICS_KV` | 分析 KV 命名空间 | analytics |

### 新增环境变量

1. 在 `wrangler.toml` 的 `[vars]` 节添加
2. 在 `functions/_lib/env_contract.json` 登记
3. 更新 CI 闸门（如有引用）

---

## 六、部署验证

```bash
# 1. 线上回探
curl https://roboparts.cc/api/data.json | python -c "import sys,json;d=json.load(sys.stdin);print(d['meta']['total_entities'])"

# 2. 数字一致性
python scripts/verify_live_numbers.py

# 3. 新鲜度检查
python scripts/check_freshness.py
```

---

## 七、回滚

见 `docs/rollback.md`

---

## 八、常见问题

### Q: 部署失败，提示数字漂移？

**A**: 跑 `python scripts/inject_readme_stats.py` 刷新 README，再重试。

### Q: 部署成功，但线上数字不对？

**A**: 可能是 Cloudflare 缓存。访问 `https://roboparts.cc/api/data.json?cache-bust=<timestamp>` 强制刷新。

### Q: Workers 部署失败？

**A**: 检查 `wrangler.toml` 配置，确认 KV 命名空间已创建：
```bash
npx wrangler kv namespace list
```

---

## 九、部署频率

- **日常**：每次 push 到 main 自动部署
- **紧急**：手动触发 GitHub Actions 或 Cloudflare CLI
- **批量**：使用 `scripts/deploy_api.py` 批量更新 API 端点

---

*本文档由部署链路自动生成部分 + 人工编写部分组成。环境变量与配置变更请同步更新本文档。*
