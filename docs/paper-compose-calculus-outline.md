# 方法论文提纲（占学术位）——「具身组合的三轴类型语义」

> 状态：**提纲占位，非投稿稿**。对应方向锚点 Phase B3
> （`docs/PROJECT_DIRECTIONS_V2.md` §4；路线图 Phase B
> `docs/direction-evolution-roadmap-20260923.md`）。
> 路线图原话：**「发表方法论文（占学术位，非数据集 paper）」——先轻量
> effect system 原型（B1 已落地），视反馈再决定是否上 Lean。**
>
> 纪律：本提纲不声明任何「已完成」的实验结果；所有数字引用一律走
> `scripts/onboarding_block.py::facts()` 或产物现算，不手写。

---

## 1. 主张（Claim）

具身系统的零件组合问题（「这个脑能不能配这个体」）当前以散文、BOM 表和
经验试错处理；我们把它形式化为一个**三轴类型系统上的可判定函数**：

```
compose(a, b) ∈ { composed, type_error, unknown }
```

- **机械轴**：安装接口类型（ISO 9409-1 标号 = 类型；reflexivity 公理：同型必配）。
- **电气轴**：连接器类型（针数/间距不容 ⇒ incompatible）。
- **信号轴**：通道互补（OUTPUT_SPIKE → INPUT_SENSORY；REWARD 不参与正向判定）。
- **fail-closed 语义**：无证据的轴恒为 `unknown`，`unknown` 优先级高于
  `composed`——系统对「不知道」的回答是一等公民，而非缺失值。

## 2. 与现有工作的差异（为什么是新问题）

- URDF/MJCF 描述**单个**机器人；没有跨厂商零件间的**组合裁决**。
- 兼容性矩阵类工具回答「A 配 B 吗」时把无数据当「不兼容」或当「兼容」——
  两者都是谎言；三态语义是我们与它们的分界线。
- 形式化方法圈（Lean/Coq 机器人学）尚无「零件级组合类型系统」的落地物；
  我们从轻量 effect system 起步，保留升级到依赖类型的路径
  （`MECH:ISO9409-1-A{n}` 的参数化标号天然是 indexed type）。

## 3. 论文结构（拟）

1. **引言**：具身智能供应链的「组合 不动点」问题；5.69% 机械声明率的
   成因二分（真数据缺口 vs 生态碎片化）作为动机——声明率是覆盖率地图，
   不是 benchmark。
2. **形式化**：端口类型格（`port_types` + `type_compat`）；裁决代数
   （identity / adapter_required / incompatible / unknown 四值序）；
   best-pair 语义；总裁决优先级；reflexivity 公理及其边界。
3. **实现**：`compose_engine/v1`（约 300 行纯函数 Python）；数据底座
   593 节点形态图；闸门工程（阳性/阴性/变异自证）作为方法的一部分——
   **把「可判定」本身变成被检验的对象**。
4. **评估**：351,649 全对评测的聚合三态分布（composed=0 的诚实含义）；
   与溯源层五层链（连接条件 L1–L4）的一致性；失效案例
   （JST-EHR-03 × JST-EHR-04 针数不容）的可解释性。
5. **讨论**：unknown 主导是否使系统无用？——反论：unknown 是**可行动的**
   （它精确指出补哪个声明能把多少 unknown 对变成可判定对，即
   「缺口枢纽入度」的意义）；这正是数据飞轮的排序依据。
6. **未来工作**：依赖类型升级路径（Lean 4 化的触发条件）；转接盘几何
   （adapter_required 的可打印可信）；信号轴的电气-时序联合语义。

## 4. 目标出口（候选，按投稿成本升序）

1. 工作坊/短文：ROSCon / IROS workshop（具身组件标准化方向）。
2. 期刊短文：Science Robotics「Technical Comment」类 / RAM（RA-Letters）。
3. 预印本先行：arXiv（cs.RO），占时间戳与优先权。

> 投稿决策走锚点 §2 三问闸门；写作启动前本文档不承诺日期。

## 5. 已具备的证据链（写作时的引用清单）

- 形态图：`api/morphology_graph.json`（593 节点 / 2185 端口 / 147 类型对；
  缺口枢纽 ELEC:UNKNOWN=540 / MECH:UNKNOWN=414 入度现算）。
- 组合语义：`api/compose_semantics.json`（规则表 R0–R5 / 全对聚合 / 判例）。
- 跨层溯源：`api/provenance.json`（五层链 / 连接条件满足 0/4 / 首断点 body）。
- Croissant 元数据：`api/croissant.json`（引用入口）。
- 闸门：`scripts/verify_compose_semantics.py` 21 项自证、
  `scripts/verify_morphology_graph.py` 21 项、`scripts/verify_provenance.py` 12 项、
  `scripts/verify_croissant.py` 7 项。
