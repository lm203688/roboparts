# RoboParts 维护者手册

> **目的**：让新人在无原作者情况下能跑通一次变更。
> **适用对象**：新贡献者、新维护者、临时接手者。
> **阅读时间**：首次 30 分钟，日常 5 分钟（查速查表）。

---

## 一、五分钟速查表

| 场景 | 命令 / 操作 |
|------|------------|
| 本地开发启动 | `npx wrangler pages dev .` |
| 跑全套闸门（49 项） | `python scripts/ci_gate.py` |
| 只跑闸门清单 | `python scripts/ci_gate.py --list` |
| 部署到线上 | `node scripts/deploy.mjs` |
| 回滚部署 | `node scripts/deploy.mjs --rollback` |
| 提交推送 | `git add -A && git commit -m "..." && git push` |
| 查 CI 状态 | `python scripts/ci_gate.py --status` |
| 查部署新鲜度 | `curl https://roboparts.cc/api/freshness.json` |
| 查账本状态 | `curl https://roboparts.cc/api/credits/balance?key=YOUR_KEY` |

---

## 二、目录结构

```
robopart/
├── functions/              # Cloudflare Pages Functions（后端 API）
│   ├── _middleware.js      # 全局中间件（遥测、认证）
│   ├── mcp.js              # MCP 协议服务
│   ├── api/
│   │   ├── bom/            # BOM 相关（check/export/import）
│   │   ├── selection/      # 选型引擎
│   │   ├── credits/        # 积分账本
│   │   ├── payment/        # 支付回调
│   │   └── ...             # 其他端点
│   └── _lib/               # 共享库（compat_engine, ledger, paywall）
├── scripts/                # Python/Node 脚本
│   ├── ci_gate.py          # CI 闸门（49 项）
│   ├── deploy.mjs          # 部署脚本
│   ├── mutation_score.py   # 变异评分
│   └── ...                 # 其他自动化
├── docs/                   # 文档
│   ├── module-reports/     # 10 个模块评估报告
│   ├── MAINTAINER.md       # ← 你在这里
│   └── ...
├── api/                    # 静态 API 产物（JSON）
├── .github/workflows/      # GitHub Actions CI/CD
└── ...                     # 前端页面（HTML）
```

---

## 三、核心工作流

### 3.1 日常变更流程

```
1. 修改代码
2. 跑 CI: python scripts/ci_gate.py
3. 全部通过后提交
4. 推送部署: node scripts/deploy.mjs
5. 回探验证: curl 关键端点确认
```

### 3.2 添加新闸门

```python
# 1. 在 scripts/ci_gate.py 中添加检查函数
def check_xxx():
    """检查说明"""
    # 检查逻辑
    return pass/fail

# 2. 在 GATES 列表末尾添加
GATES = [..., ('check_xxx', '闸门名称')]

# 3. 跑全套确认
python scripts/ci_gate.py
```

### 3.3 处理假绿（False Green）

**症状**：CI 全绿但线上行为异常。

**排查步骤**：
1. 检查 `functions/_middleware.js` 的遥测是否记录到请求
2. 检查 `scripts/ci_gate.py` 的对应闸门是否真的执行
3. 用 `--verbose` 模式跑闸门，看输出细节
4. 检查 `docs/verification-antipatterns-2026.md` 是否有匹配的 AP 条目

**常见假绿原因**：
- 闸门只测 happy path，没测边界条件
- 闸门依赖外部状态（KV、网络），测试时不可达
- 闸门测的是 mock，不是真实端点

### 3.4 记录负结果

```markdown
## NR-XX: 标题

**尝试时间**：2026-XX-XX
**假设**：XXX
**尝试方案**：XXX
**结果**：失败
**证据**：XXX（链接到脚本输出/日志）
**结论**：此路不通
**改道建议**：XXX
```

添加到 `docs/negative-results.md`。

---

## 四、关键纪律（红线）

### 4.1 三态语义

```
compatible = true   → 肯定兼容
compatible = false  → 肯定不兼容
compatible = null   → 不知道（默认值）
```

**禁止**：用 truthy 判断（`if (compat)`）替代三态判断（`if (compat === true)`）。

### 4.2 账本诚实

```
不可读 ≠ 空
不可读时汇总必须是 null，不能是 0
```

### 4.3 不抽佣

RoboParts 不销售、不代理任何零件。判定必须保持中立。

### 4.4 机械接口必须附 source_url

没有出处的机械接口声明 = 污染。宁可空白，不可臆造。

---

## 五、常见故障排查

### 5.1 部署失败

```bash
# 检查部署状态
node scripts/deploy.mjs --status

# 检查 Cloudflare 配置
cat wrangler.toml

# 手动部署
npx wrangler pages deploy . --project-name roboparts
```

### 5.2 端点 404

```bash
# 检查路由配置
cat _routes.json

# 检查 _headers 配置
cat _headers

# 测试端点
curl -v https://roboparts.cc/api/your-endpoint
```

### 5.3 KV 读写问题

```javascript
// 检查 KV 绑定
console.log(env.USER_CREDITS);  // undefined = 未绑定

// 测试 KV 读写
await env.USER_CREDITS.put('test', 'value');
const val = await env.USER_CREDITS.get('test');
```

### 5.4 CI 失败

```bash
# 只看失败项
python scripts/ci_gate.py --failed

# 看闸门清单
python scripts/ci_gate.py --list

# 单项测试
python scripts/ci_gate.py --only check_xxx
```

---

## 六、关键文件索引

| 文件 | 用途 |
|------|------|
| `functions/_lib/compat_engine.js` | 兼容性判定引擎（核心） |
| `functions/_lib/ledger.js` | 积分账本（唯一入口） |
| `functions/_lib/paywall.js` | 付费墙字段清单 |
| `scripts/ci_gate.py` | CI 闸门（49 项） |
| `scripts/mutation_score.py` | 变异评分 |
| `docs/verification-antipatterns-2026.md` | 反模式档案 |
| `docs/negative-results.md` | 负结果档案 |
| `docs/technical-decisions-20261014.md` | 技术决策留痕 |

---

## 七、紧急联系人

- **原作者**：lm203688
- **GitHub**：https://github.com/lm203688/roboparts
- **线上站点**：https://roboparts.cc

---

*最后更新：2026-10-14*
