# tests/ — 集成测试与单元测试

**范围**：本项目里能独立运行、不依赖外部网络与凭据的测试脚本。

**与其他测试的关系**：
- **`scripts/regression.py`**：主回归闸门（L1/L2/L4 数百项断言），走 CI 强校验；本目录是它**之外的补充**。
- **`scripts/verify_*_injections.py`**：反向注入验证（mutation tests），仍在 `scripts/` 保留，因为它们验证的是 `regression.py` 的判据是否真的能抓缺陷。
- **`scripts/ci_gate.py`**：仓库自证闸门（84 项），走 CI；本目录不参与。

**当前测试（5 个）**：
| 文件 | 覆盖对象 | 触发方式 |
|---|---|---|
| `test_bom_assembly.mjs` | `functions/api/bom/check.js` 装配序列算法 | `node tests/test_bom_assembly.mjs` |
| `test_feedback_loop.mjs` | `functions/api/adapter-feedback.js` + `recommend-feedback.js` 聚合规则 | `node tests/test_feedback_loop.mjs` |
| `test_p0_multifactor.mjs` | P0 安全多因子逻辑 | `node tests/test_p0_multifactor.mjs` |
| `test_p1_recommender.mjs` | P1 推荐器 | `node tests/test_p1_recommender.mjs` |
| `test_promote_ledger.mjs` | 晋升台账 | `node tests/test_promote_ledger.mjs` |

**跑全套**：
```bash
for f in tests/test_*.mjs; do node "$f" || exit 1; done
```

或在 `package.json` 里加一条 `test:integration` 脚本自动跑。

**约束**：
- 测试**不写**任何外部状态（KV/DB/API），只调用纯函数或本地文件系统。
- 断言失败必须让进程以非零码退出，方便 CI 集成。
- 每个测试文件头部必须说明**测的是什么判据**——否则跑绿了也不知道绿在哪。
