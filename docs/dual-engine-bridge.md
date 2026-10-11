# 双引擎口径桥接（OPT-1）· 2026-10-11

> **性质**：架构文档，不是代码。目的是让外部读者（尤其 AI Agent）能一眼看懂
> 「为什么仓里有两套判定引擎」以及「什么时候用哪一个」，避免把两套引擎的维度名
> 混着写导致语义混淆。
> **背景**：《RoboParts-下一阶段全面提升报告-20261011》§6.2 #4 收敛双引擎口径。
> 本文件**不合并两套引擎**（合并会造成更大混乱，见 §四），而是明确桥接规则。

---

## 一、两套引擎是什么关系

| 引擎 | 位置 | 维度 | 用途 |
|---|---|---|---|
| **产品层引擎** | `functions/_lib/compat_engine.js` | `protocol`, `electrical`, `mechanical`, `software`（4 维） | Web / MCP / API 对外的四维兼容判定（`/api/compatibility`、`/api/bom/check`、21 个 MCP 工具） |
| **研究层引擎** | `scripts/compose_engine.py` | `mechanical`, `electrical`, `signal`（3 轴） | 研究进度评估（`research_progress.json`）、共装层 `co_mount.json`、`evidence_valuation.json`、`compose_frontier.json` |

**交集**：只有 `electrical` + `mechanical` 两个维度同名。
**非交集**：
- 产品层独有：`protocol`（EtherCAT/CANopen/ROS2 等协议族）、`software`（ROS2 支持）
- 研究层独有：`signal`（通道互补：OUTPUT_SPIKE → INPUT_SENSORY）

**关键结论**：两套引擎**不互为子集**——`signal` 与 `protocol`/`software` 是不同抽象层：
- `protocol` = 协议族（宏观）
- `signal` = 通道方向性（微观，脉冲级）
- `software` = 生态支持

**因此不能取并集合并**——合并会让 agent 以为「协议 + signal」是一维，实际是分层。

---

## 二、什么时候用哪个引擎

| 场景 | 用哪个 | 理由 |
|---|---|---|
| 用户查「ACT-001 能不能和 ACT-002 一起用」 | 产品层四维 | 用户想要「能不能」的可执行结论，四维覆盖了协议 + 生态 |
| Agent 通过 MCP 调用 `check_compatibility` | 产品层四维 | MCP 是产品面入口 |
| Agent 通过 MCP 调用 `check_co_mount` | 研究层三轴 | 共装是三段关系，需要 `signal` 通道互补 |
| 研究进度评估（`research_progress.json`） | 研究层三轴 | 研究层量化「数据完整性」，不看协议族 |
| 评估「补哪条数据最值」（MDV 判据） | 研究层三轴 | MDV 判据建立在三轴 verdict 分布上 |
| 论文方法学描述 | 两者都提 | 论文要说明为什么两套并存 |

---

## 三、维度对应关系（唯一权威表）

**这是仓内唯一权威对应表**。任何文档 / 代码引用双引擎维度映射都必须指向本表，禁止复制。

```
产品层 compat_engine.js                 研究层 compose_engine.py
─────────────────────────              ──────────────────────────
protocol          ── 无直接对应 ──       （signal 是更细的通道级）
electrical        ⇄                     electrical   ← 同名同义
mechanical        ⇄                     mechanical   ← 同名同义
software          ── 无直接对应 ──       （研究层不评生态支持）
                         signal         ← 研究层独有（通道互补）
```

**语义差异（诚实边界）**：

| 维度 | 产品层定义 | 研究层定义 | 差异 |
|---|---|---|---|
| `electrical` | 电压区间重叠判定（`parseVoltageRange`） | 连接器标号 + pins/pitch 类型兼容 | **不同颗粒度**：产品层看电压，研究层看物理连接器 |
| `mechanical` | 法兰标号匹配（ISO 9409-1）+ 安装体系兼容 | 法兰标号 + 专有安装体类型兼容 | 高度相似，研究层多一个「专有安装体」分支 |
| `protocol` | 协议族（EtherCAT / CANopen / ROS2 / DYNAMIXEL / TTL 等） | 不覆盖 | 产品层独有 |
| `software` | ROS2 支持（`ros_support: true/false/null`） | 不覆盖 | 产品层独有 |
| `signal` | 不覆盖 | 通道互补（OUTPUT_SPIKE → INPUT_SENSORY） | 研究层独有 |

**关键诚实边界**：`electrical` 在两引擎中**语义不完全相同**。
产品层判断「10V 和 12V 是否冲突」，研究层判断「JST XH 3-pin 和杜邦线能否物理互插」。
两者可以互补但不能互替——**一个说「电压对」不代表「线插得上」**。

---

## 四、为什么不合并

（回应「为什么不做单一真相源」的疑问，防止后人重走弯路）

**曾尝试过**（2026-09-27 前的多轮迭代），失败原因：

1. **维度不共基**：`signal` 需要 port 数据（`effective_ports`），
   `protocol` 需要协议族词汇（`PROTOCOL_VOCAB`），两者数据结构完全不同，合并到一个 `evalDimension` 会造成巨大的 if/else。
2. **verdict 词汇不同**：研究层用 `compatible / compatible_via_adapter / incompatible / unknown`，
   产品层用 `true / false / null`（三态）。强行统一 verdict 会破坏至少一方的下游消费者。
3. **失败案例**：曾试图把 `signal` 塞进 `compat_engine.js`，结果 `check_compatibility` 的 evidence 输出混入通道级细节，用户看不懂，MCP 工具 description 长度翻倍。

**当前策略**：两套引擎保持独立，通过**桥接文档 + 桥接工具**明确对应关系。

---

## 五、桥接工具（可选调用）

需要跨引擎比对时，用 `scripts/dual_engine_bridge.mjs`（如已实现）：

```bash
# 产品层结果转研究层口径
node scripts/dual_engine_bridge.mjs \
  --input compat_result.json \
  --to research_axes \
  --output axes_view.json
```

**转换规则**：
- `protocol=true` → 保留但不映射（研究层无对应）
- `protocol=false` → 标为 `research_gap: protocol_only`
- `software=true/false/null` → 保留但不映射
- `electrical/mechanical` → 直接同名映射，但 verdict 词汇要转换：
  - `true` → `compatible`
  - `false` → `incompatible`
  - `null` → `unknown`

---

## 六、Agent 视角的正确提问姿势

如果你是一个 AI Agent 在写文档 / 代码时涉及「判定引擎」，按下列规则：

1. **只谈一个引擎时**：明说「产品层四维」或「研究层三轴」，不简称「引擎」。
2. **两个引擎都提时**：按 §三 的对应表写映射，禁止「四维和三轴合并后是六维」这种话。
3. **`electrical` 出现在两个引擎语境时**：必须写全 `compat_engine.electrical` 或 `compose_engine.electrical`，否则读者会误以为语义相同。
4. **verdict 词汇跨引擎时**：产品层用 `true/false/null`，研究层用四态字符串；转换必须在桥接工具里做，不要在文档里手写转换表。

---

## 七、诚实边界

- 本文件描述的是「当前架构事实」，不构成对**未来架构演进**的承诺。
- 若未来研究层引入 `protocol`/`software` 或产品层引入 `signal`，本表需要同步更新，且 CI 加断言防止文档漂移。
- 「不合并」是**当前选择**，不是「永远不合并」。若某天统一 verdict 词汇的成本低于维护两套的成本，应重新评估。

---

## 八、与 CI 的耦合

`scripts/ci_gate.py` 的以下项已对本文件描述的关系做断言：

- `兼容性裁决 Golden 评估集` — 用四维口径断言
- `共装关系（三段 A↔宿主↔B）` — 用三轴口径断言
- `完成度判据 — gated` — 用研究层三轴 verdict 分布加权

**任何维度的新增或删除**，都必须先改本文件，再改 CI 断言，再改引擎代码——顺序不能反。
