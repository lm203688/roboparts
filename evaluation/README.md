# RoboParts L5 评估层

RoboParts 有**两层评估**，覆盖"规则引擎"与"MCP 语义"两个不同口径：

| 层 | 文件 | 测什么 | 跑法 |
|---|---|---|---|
| 规则引擎锚点 | [`api/eval/compatibility-golden.json`](../api/eval/compatibility-golden.json) | 6 条冻结锚点 + 2 条 badcase，验证 compose_engine 规则稳定 | `node scripts/eval_compat.mjs` |
| MCP 语义评估 | [`promptfoo/promptfooconfig.yaml`](promptfoo/promptfooconfig.yaml) | 8 个 Agent 场景，验证 MCP 工具对 LLM 可复现 + fail-closed 诚实 | `npx promptfoo eval --config evaluation/promptfoo/promptfooconfig.yaml` |

## 三态 fail-closed 契约（评估的核心判据）

1. **未声明维度必须判 `unknown`**，不得 fail-open 判 `compatible`。
2. **每个判定必须带 `evidence[]` 链**（引用了哪些实体的哪些字段 + 各自 tier）。
3. **未收录的型号必须诚实说"不知道"**，不能编造型号详情。

违反任一条即视为评估失败——这是 RoboParts 的护城河，比"判定率高"更重要。

## 与 CI 的关系

- `api/eval/compatibility-golden.json` 已挂 ci_gate（每次 commit 都跑）。
- promptfoo 目前是**可选跑**（需要 npm install promptfoo），未来会加入 nightly。
- 三层评估（规则 → MCP → 语义）确保从底层到 Agent 层都可校验——这是"验证即服务"的技术底座。
