# CodaBench Neural Interfaces 2026 标准对标评估（RoboParts，2026-11-06）

> Chief 派（m00895）：以 CodaBench Neural Interfaces 2026 比赛要求为**标准参考**，评估 RoboParts 可补充提升项。
> 本轮为**纯评估**，无代码/数据改动，不走发布闭环。研究资助官已核实 6 项标准为官网一手来源。
> 诚实边界：RoboParts 是**机械组合校验层**（非神经网络分类/预测项目），与神经接口赛道**本质不同**——多数标准"不适用"是**定位不匹配**，如实说明，不虚构提升项。

---

## 一、结论先行

**RoboParts 与 CodaBench Neural Interfaces 2026 赛道定位不匹配**（神经接口=跨人脑电迁移分类/预测；RoboParts=静态机械组合校验）。6 项标准中 **3 项已实质达标、1 项部分达标、2 项不适用**（定位原因），**1 项存在可操作提升项**（可复现性硬门槛——依赖锁定完整性）。

### 对标总表

| # | 标准要素 | 现状 | 结论 | 可操作提升项 |
|---|---|---|---|---|
| 1 | 可复现性硬门槛（±2σ 重跑） | 派生产物 hash 连跑一致（morphology a94cb68e / lattice 4e347246e 两次相同）；CI 固定 node 22.22.2 + python 3.12 | **部分达标**（产物确定 OK，但 Python 依赖未版本钉死） | **P1-1 依赖版本钉死**（value/成本/优先级见 §三） |
| 2 | 数据合规 | api/ + roboparts-dataset-github + 线上同源数据 **CC BY 4.0**（DATA-LICENSE.md 显式声明）；代码 MIT（LICENSE）；来源分级 tier + provenance.json（PROV-O 对齐） | **已达标**（有证据） | 无（已合规） |
| 3 | 评测标准化（60min 单 A100） | 非 GPU 推理：组合判定 O(N²×轴×类型²) 本机约 1 秒级（build_evidence_valuation.py 明示"无需 GPU/网络"）；CI 门禁约 4 分钟跑完 150 项 | **已达标**（无 GPU 依赖，性能预算绰绰有余） | 无（不适用 GPU 预算） |
| 4 | 提交约束（15GB/profile） | 全仓 388M（.deploy-staging 205M + api 33M）远小于 15GB | **已达标**（有实测） | 无 |
| 5 | IP 归属 | LICENSE MIT（code）+ DATA-LICENSE CC BY 4.0（data）双轨清晰；数据自有/来源分级；无组织外传 | **已达标** | 无 |
| 6 | 能力基线（Constant 33.3% 等） | 专业模型刚过 chance（跨人迁移极难）说明**标准门槛低**；RoboParts 是**三态判定**（compatible/incompatible/unknown，fail-closed），不是分类预测——"能力基线"概念不直接适用 | **不适用**（定位不同） | 无（非同一赛道） |

---

## 二、逐项现状证据

### 1. 可复现性硬门槛（±2σ 重跑训练管线）
- **已达标部分**：派生管线确定性——`regen_derived.py` 连跑两次，产物 hash 完全一致（morphology_graph.json `a94cb68e9b08`、compose_lattice_tests.json `4e347246eb3d`，两次相同）。`build_synthesized_pair_pool.py` RNG 种子固定（`RNG_SEED='__synth_v0__'`，line 71/118，自带"连跑两次输出一致"证明）；`build_assembly_typecheck.py` seed=20261015。
- **已有质量文化**：变异测试/阴阳自证（ci_gate.py line 214-216：阳性当前数据通过 + 阴性注入 1 真缺陷判红）；`build_compose_frontier.py` line 163-164 明确处理 PYTHONHASHSEED 键序问题（加 sorted() 确定性 tiebreaker）。
- **可提升缺口**：`requirements-dev.txt` **无版本钉**（PyYAML>=6,<7 / usd-core>=25.11,<27 / jsonschema>=4.20,<5 都是范围，非精确版本）；CI line 56 `pip install -r requirements-dev.txt`。**Python 依赖漂移可能**导致 ±2σ 重跑在依赖升级后不同。package-lock.json（lockfileVersion 3，174 包）已锁 npm 依赖（npm ci 可用），**但 Python 侧缺精确锁定**。
- **诚实边界**：我们**没有训练管线**（非神经网络训练项目）——"重跑训练管线"不适用；等价物是**数据/派生管线确定性**，已验证。

### 2. 数据合规
- **证据**：`DATA-LICENSE.md` 显式声明 api/ + roboparts-dataset-github/ + roboparts.cc/api/ 同源数据 **CC BY 4.0**；`LICENSE`（code）**MIT**（GitHub 识别器此前 NOASSERTION 问题已修复，双轨拆分）。来源分级（source tier）+ `api/provenance.json`（PROV-O 对齐，schema contract）。无密封测试集/非许可临床数据（本赛道无临床数据）。
- **结论**：已合规，无需提升。

### 3. 评测标准化（60min 单 A100）
- **证据**：`build_evidence_valuation.py` line 137/385 明示复杂度 O(N²×轴×类型²)，N=593 ⇒ 本机约 1 秒级，"无需 GPU/网络"。CI 门禁 150 项约 4 分钟跑完（Linux runner）。
- **结论**：无 GPU 推理依赖，性能预算远低于 60min 单 A100 上限（甚至不用 A100）。**不适用**（非 GPU 评测）。

### 4. 提交约束（15GB/profile）
- **证据**：全仓 `du -sh` = **388M**（.deploy-staging 205M + api 33M + 其余）。远小于 15GB。
- **结论**：达标（有实测）。

### 5. IP 归属
- **证据**：LICENSE MIT（code）+ DATA-LICENSE CC BY 4.0（data）双轨清晰；数据自有（868 实体，来源分级）；无组织外传（organizers 不外传要求与我们"数据自有 + CC BY 开放"一致，且更强）。
- **结论**：达标。

### 6. 能力基线（Constant 33.3% / EEGNet 32.6% / CTNet 35.0% / REVE 36.0%）
- **解读**：专业模型刚过 chance（33.3% = 三分类随机），说明**跨人迁移极难**、标准门槛低。这是神经接口赛道的特性。
- **RoboParts 定位**：**三态判定**（compatible/incompatible/unknown，fail-closed 不偷换 unknown），非分类/预测。我们有 3 条代数律（可靠性/证据单调性/不可判定边界）+ 91 项 CI 闸门 + 变异测试 + 阴阳自证作质量保障——但这**不是**"能力基线%"概念可比。
- **结论**：**不适用**（不同赛道）。诚实说明：我们的"能力"是**判定正确性**（三态 + fail-closed），不是**预测准确率**（百分比）。

---

## 三、可操作提升项清单

**仅 1 项可操作**（其余已达标或不适用）：

| 维度 | 现状 | 提升方向 | 价值 | 成本 | 优先级 |
|---|---|---|---|---|---|
| **P1-1 可复现性：Python 依赖版本钉死** | requirements-dev.txt 无精确版本（PyYAML/usd-core/jsonschema 都是范围）；CI pip install -r 不锁定 | 生成 requirements-dev.lock（pip freeze 精确版本）或 CI 用 pip-tools/pip-compile 生成精确锁定，CI 安装锁定版本 | 消除依赖漂移导致的"重跑不同"；±2σ 等价的可复现性更硬 | 低（生成一次 lock + CI 一行改动 + 本地验证）；风险低（版本范围已限制） | **P1**（中等，非 P0） |

**P1-1 详细**：
- **为什么有价值**：当前范围依赖（PyYAML>=6,<7 等）在 CI 上每次 `pip install -r` 可能装到不同 minor/patch → 理论上派生产物或闸门行为可能漂移。虽然我们已用确定性 tiebreaker + RNG seed 保证**产物**确定，但**工具链版本**未锁死是硬门槛的残余缺口。
- **为什么优先级 P1 非 P0**：非线上故障、非数据错误；当前实测产物确定（hash 连跑一致），依赖漂移未造成实际事故——属"加固"而非"救火"。
- **验收标准**：CI 安装依赖后 `pip show PyYAML` 版本与 lock 一致；连跑两次 regen_derived 产物 hash 仍一致（回归）。
- **成本**：约 1-2 小时（生成 lock + ci.yml 一行 + 本地回归）。

---

## 四、诚实边界声明

1. **赛道不匹配**：CodaBench Neural Interfaces 是**脑电跨人迁移分类/预测**竞赛；RoboParts 是**静态机械组合校验**（ISO 9409 法兰 + ISO 22166 + 三态 fail-closed compose）。**本质不同**，直接参赛无意义（数据/评测/模型都不兼容）。本次对标是**能力提升参考**，非参赛评估。
2. **无训练管线**：标准①"重跑训练管线"不适用——我们没有训练管线，等价物是数据/派生管线确定性（已验证）。
3. **无 GPU 评测**：标准③"60min 单 A100"不适用——我们无 GPU 推理，性能预算用不上。
4. **不虚构提升项**：数据合规/IP/体积均已达标，如实标注"已达标"，不制造伪提升项。

---

## 五、归档信息
- 生成日期：2026-11-06
- 生成者：RoboParts 工程 Agent
- 类型：纯评估（无代码/数据改动，工作区 clean）
- 关联：docs/competition-recheck-20260910.md（此前竞赛路径复核，结论"不建议现在把竞赛当主路径"——本对标**强化**该判断：不同赛道 + 无直接参赛价值，但能力对标有 1 项可加固）
