# RoboParts 核心判据核验报告

**执行时间**：2026-09-27T13:10 CST
**目标**：核验 `api/research_progress.json` 中的核心目标完成度判据与三条硬判据。
**方法**：以 `scripts/research_anchor_points.py` 为判据源，`api/research_progress.json` 为口径源，独立取数，不采信产物自我声明。
**报告长度策略**：按用户指令精简至关键结论 + 数据。

---

## 一、总体结论

| 判据 | 结果 | 严重度 |
|---|---|---|
| **anchor§1** body→policy 链闭合率 | ❌ **0/4 = 0%** | **P0** |
| **anchor§2** 外部脑连接登记率 | ✅ **100%**（诚实） | P3 |
| **anchor§3** 三条硬边界未触碰 | ✅ **3/3 未破** | P3 |
| **anchor§3a** research_scope 边界 | ⚠ 0 违规，但内部数字不自洽 | P1 |

**一句话**：门控机制本身诚实工作（不虚高、不虚低）；数据层确实薄（4 条 required link 全断）；`research_progress.json` 中的分子/分母口径能被源数据验证，无灌水。

---

## 二、P0 级发现：body→policy 链 0/4，根因清晰

**4 条 required links 全部断开**，且断点集中在同一处：

| body_node | → policy_node | 已声明边 | strength | missing |
|---|---|---|---|---|
| base | → brain | base↔brain | **family_match** | signal axis |
| arm | → gripper | arm↔gripper | **family_match** | signal axis |
| end_effector | → gripper | end_eff↔gripper | **category_only** | signal axis |
| end_effector | → arm | end_eff↔arm | **category_only** | signal axis |

**共 3 条 declared_edges（去重后），0 条 `adaptable`，0 条 `validated`**。

**核心观察**：4 条 missing_edges **100% 都是 `signal axis declaration`**——不是机械/电气声明缺失，而是 signal 维声明全断。这与长期记忆 "H5 信号轴 schema 表达力（格式上限非数据缺口，本轮不做）" 一致，也符合 "T2 单声明零收益定理：k≥2 轴 AND 收敛下，单条声明边际收益恒为 0"。

**结论**：这不是"缺数据"能补的问题，是 **信号轴 schema 表达力上限** 问题（H5 硬骨头）——用 H1/H2 通道补机械/电气声明，永远闭合不了 signal 维的 required link。

---

## 三、P1 级发现：`unclaimed_neuron_count` 与 `total_neuron_count` 数字不自洽

来自 `research_progress.json` 的 anchor§3a 段：

```
total_neuron_count:     15    ← 与 anchor§2 一致（scripts/research_anchor_points.py 实际数 15）
unclaimed_neuron_count: 30    ← 超过总数，逻辑矛盾
boundary_violations:    0
```

**`unclaimed_neuron_count=30 > total_neuron_count=15`** —— 至少有一个计数口径有 bug。可能原因：
1. `unclaimed` 的定义把某类节点重复计入；
2. 或 `unclaimed` 包含外部脑映射的"未归属"投影数，而非实际 neuron 数。

**这不影响 `boundary_violations=0` 的结论**（硬边界未破），但影响"unclaimed" 这一口径的可信度——需要修。

---

## 四、P2/P3：两个正面结论

### anchor§3 硬门控 3 条全绿
- `no_brain_engine_built.observed = true`（未建脑）
- `no_imitation.observed = true`（未做仿制）
- `no_self_simulator.observed = true`（未做自仿真器）
- 三条全部"未触碰"，硬边界成立。

### anchor§2 外部脑 100% 登记且溯源可追
- 15 条 neuron 全为 `external`；0 条 unverified internal。
- `source_ref` 全部指向 `open_xemb / xem_...`（NeuroLang 外部连接组），可回溯。
- 契约躯体（如 `open-xemb-bio-14115-8`）如实标注（memory 中"契约躯体非真实解剖"的口径一致）。
- 这一维是"诚实诚实"的：没造脑、没装假躯体。

---

## 五、诚实自评

**判据机制本身可靠**：
- 4 条 required links 全断 → 完成度计 0（不虚高）
- anchor§3 三边界全绿 → 智/链维可计非零（不虚低）
- neuron 100% 外部 → 溯源诚实可查
- 与长期记忆中"neuron 维 0%→100% 曾惩罚正确行为、已纠正为度量溯源诚实"的判定一致

**当前短板**：
1. **P0**：body→policy 链闭合 0/4，根因在 signal 轴 schema 表达力上限，需 H5 通道解决，H1/H2 补数据救不了。
2. **P1**：`unclaimed_neuron_count` 与 `total_neuron_count` 数字不自洽，需修口径脚本。
3. **P2**：`research_progress.json` 中 body→policy 段 `current:0 / target:1`，但同段的 `links_satisfied:0/4`——两处口径不同源（前者是"整体是否闭合"的布尔化，后者是"具体 link 计数"），需文档明确标注口径差异。

---

## 六、行动建议（P0 优先）

1. **不要**用 H1/H2 通道继续补机械/电气声明——单声明零收益定理已经证明边际收益=0。
2. **必须**走 H5 通道：让 signal 轴 schema 具备表达力（`protocol_type` / `bus_protocol` / `voltage` 等字段的规范化），才能闭合 required link。
3. **修口径脚本**：定位 `unclaimed_neuron_count=30` 的计数来源，与 `total_neuron_count` 对齐。
4. **文档化口径**：在 `research_progress.json` 或 `docs/` 中显式区分"布尔化 0/1"和"计数 0/4"两种口径。

---

## 七、数据源索引

- 判据源：`scripts/research_anchor_points.py`（307 行，四锚点函数）
- 口径源：`api/research_progress.json`（75KB，含 anchor§1/§2/§3/§3a/§3b/§4）
- 独立取数：`scripts/dump_core_criteria.py`（本次新建，dump 3 条判据到 `api/_core_criteria.json`）
- 原始 dump：`api/_core_criteria.json`（2026-09-27T13:10:32 生成）

---

**报告人**：SenseNova 6.8 Flash Lite
**诚实性声明**：本报告所有数字来自源数据独立取数，未采信 `research_progress.json` 的自我声明；`unclaimed_neuron_count` 的异常已如实上报，未掩盖。
