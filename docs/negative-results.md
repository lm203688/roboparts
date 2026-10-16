# Negative Results Log — 负结果档案

> **性质**：自动淘汰入库。所有未通过判据、实验失败、假设被推翻的记录必须留痕，防止同一错误重复踩。
> 
> **设计纪律**（§6.4.6 自进化红线）：
> 1. 不得删除负结果——它们是系统的免疫记忆
> 2. 每条负结果必须带：假设、方法、结果、根因、下次如何避免
> 3. 负结果自动入库，不需人工审批

---

## 2026-10-16

### NR-001: T2 定理证伪「单条声明有边际收益」

| 字段 | 值 |
|---|---|
| 假设 | 补一条声明（如 ACT-028 法兰）能解锁至少 1 个可判定对 |
| 方法 | 跑 evidence_valuation.py，对单条声明计算 MDV |
| 结果 | MDV = 0。在 k≥2 轴 AND 收敛下，单条声明边际收益恒为 0 |
| 根因 | 三轴 AND 收敛的数学性质——单条声明只能覆盖 1 个轴，另 2 轴仍缺 |
| 下次避免 | 停止按单条取证；按最小可行同质集（MVC）批量推送 |
| 判据 | `api/evidence_valuation.json` → `targeting_rationale` 字段 |

### NR-002: 旧 P0「机械声明率→30%」被证伪

| 字段 | 值 |
|---|---|
| 假设 | 提高机械声明率能提升 composed 数 |
| 方法 | 查 compose_semantics.json，看 composed 与机械声明率的相关性 |
| 结果 | composed 恒为 0，与机械声明率无关。binding_axis=electrical |
| 根因 | 电气轴是 AND 收敛点，机械轴贡献 0（零贡献轴定理） |
| 下次避免 | 取证按轴定向，不做全轴均匀补数 |
| 判据 | `api/evidence_valuation.json` → `by_axis.mechanical.contribution=0` |

### NR-003: 世界模型 API 接入判定层

| 字段 | 值 |
|---|---|
| 假设 | 世界模型 API（192.168.2.6:8899）能补 RoboParts 的像素动力学缺口 |
| 方法 | 10 个模型全部被 applicability 查询 reject（n_matched=0） |
| 结果 | 每个模型 contract 明写 `not_for: 任何真实物理预测` |
| 根因 | 能力不匹配（像素动力学 vs 符号级接口判定）+ 契约自证不可信 + 破坏三态纪律 |
| 下次避免 | 判定层只接受有明确契约 + 一手验证的组件；像素动力学留 Phase B 的 VLM 离线辅助 |
| 判据 | 世界模型 API 评估报告（2026-10-16） |

### NR-004: A6 ISO 映射 10/20 FAIL

| 字段 | 值 |
|---|---|
| 假设 | ISO 22166 条款级映射能 20/20 通过 |
| 方法 | conformance_test.py 检查 20 条映射 |
| 结果 | 10 条 FAIL，因为 10 个 ISO 字段确实未建 |
| 根因 | Phase B 的取证路径就是这些字段——FAIL 是诚实边界，不是 bug |
| 下次避免 | ISO 映射必须分 Phase 推进，Phase A 只建骨架，Phase B 补字段 |
| 判据 | `api/iso22166_conformance.json` → `summary.passed=10, total=20` |

### NR-005: A3 装配级类型检查全部 ill_typed

| 字段 | 值 |
|---|---|
| 假设 | 6 个装配案例至少 1 个 well_typed |
| 方法 | assembly_typecheck.py 跑 6 个案例 |
| 结果 | 全部 ill_typed，MDV 对账不通过 |
| 根因 | 当前所有轴都是零贡献轴（binding_axis=electrical），无轴可解锁 |
| 下次避免 | 装配级类型检查是度量层，不是判定层——ill_typed 是诚实画像，不是 bug |
| 判据 | `api/assembly_typecheck.json` → `summary.ill_typed=6` |

---

## 统计

| 指标 | 值 |
|---|---|
| 总负结果 | 5 |
| 证伪假设 | 5 |
| 已入库 | 5 |
| 自动淘汰 | 0（全部留痕） |

---

_生成时间：2026-10-16 · 关联：stages/fitness.py §6.4.6 自进化红线_
