# 生态链接评估（2026-09-08）：CIS 器件库是否值得接 + 真正的开放生态路径

> 背景：用户批准三项落地（电气接口轴 / connector 补丁 / 对外免责），并追问「若我们不自建，能否链接其他项目让应用度更完整——例如接 CIS 器件库，能否提升项目」。
> 结论先行：**CIS 不是该接的目标（企业封闭 EDA 库，接不了也不该接）；但「链接外部生态」这个方向是对的，只是该链开放生态（JLCPCB/LCSC、KiCad、atopile、Octopart），而非 CIS。**

---

## 1. CIS 器件库是什么、为什么接不了

**CIS = Cadence OrCAD Component Information System**（以及 Altium 的 DbLib / Vault），本质是企业级**封闭 ODBC 中心器件库**：

- 数据存于企业私有数据库（SQL Server / Oracle / 自建 ODBC），经 EDA 软件内部的 CIS 插件读取；
- 访问需 Cadence/Altium **商业许可证 + 企业内网 + DBA 授权**，无公开 API、无匿名端点；
- 库内容是厂商**已购买/已签约**的零件符号+封装+SPN，受 IP 与 NDA 约束，**不能对外分发**。

**对 RoboParts 的三重不兼容：**

| 维度 | CIS | RoboParts | 结论 |
|---|---|---|---|
| 授权模型 | 商业闭源、企业内网 | CC-BY-4.0 开放数据集 | 方向相反，强耦合会污染开放定位 |
| 接入方式 | ODBC + 商业许可证 | 无凭证、无网络可达端点 | 技术上不可达 |
| 数据语义 | EDA 符号/封装/SPN | 机器人 BOM 零部件 + 机械/电气兼容判定 | 不是同一层数据，强行映射无增益 |

**诚实判断：** 接 CIS 既不能提升项目，还会把开放项目绑进商业 EDA 许可墙。用户的直觉「链接能补全应用度」方向正确，但 CIS 是反例——它是**最不该接**的那一类（封闭、需付费、语义错位）。

> 补充：即便退一步想「借 CIS 的零件数据」，也拿不到——CIS 数据随 Cadence 许可证走，无公开导出通道。能公开拿到的零件数据在下面第 2 节的开放生态里。

---

## 2. 真正该链的开放生态（按 ROI 排序）

RoboParts 的护城河是「零件级 + 兼容判定」——它解决的是**设计→选型→BOM** 的上游，而应用度补全要靠把上下游接出去。以下按「接入成本 / 对应用度的杠杆」排序：

### 🥇 P0 · JLCPCB / LCSC（开源硬件制造 + 零件目录）
- **是什么**：LCSC 是公开零件商城（带 API 可查库存/价格/参数），JLCPCB 是配套 SMT 打样厂；两者共享零件编号体系。
- **为什么杠杆最大**：RoboParts 的 BOM 输出可直接映射到 LCSC 零件号 → 一键下单打样，把「兼容性判定」落到「真能买、真能焊」。**这是把开放 BOM 工具变成可制造闭环的最短路径。**
- **接入成本**：低。LCSC 有公开产品 API（无需许可证）；只需在实体加 `lcsc_part` 字段（与现有 `connector` 同机制，走真相源派生）。
- **风险**：商业 API 有速率/鉴权，但比 CIS 低一个数量级且公开可达。

### 🥇 P0 · KiCad 官方库 + atopile catalog（AI-PCB 流水线）
- **是什么**：KiCad 官方符号/封装库是开源事实标准；atopile（MIT, YC W24）把「代码即电路板」做成开源流水线，**已与 KiCad MCP 生态打通**。
- **为什么杠杆大**：上一轮已确认 GPT-6 × KiCad 是「机电接口规格上游」——RoboParts 的电气接口轴（`api/electrical_interfaces.json`：供电轨/总线/连接器/电平）正好是 AI-PCB 流水线的**输入规格**。RoboParts 供给「这块板要接什么、电平多少、连接器型号」，atopile/KiCad 负责出 Gerber。
- **接入成本**：中。需定义 RoboParts→atopile 的接口契约（连接器型号 + 供电轨 → 引脚分配），但无许可墙。

### 🥈 P1 · Octopart / SnapEDA（参数化零件数据 + 符号封装）
- **做什么**：补全「零件参数化事实」——RoboParts 现在 connector 在 actuators 上仅覆盖 4/220（1.8%），voltage/protocol 各 5.0%。Octopart API 可批量回填规格书参数（不必像本轮那样逐条人工核实）。
- **为什么是补数据缺口的正解**：上轮 `electrical_interfaces.json` 的 `coverage.verdict` 已写明——「手工逐条查规格书不可行，必须链接外部器件数据源」。Octopart 就是那个外部源（有公开 API，按 MPN 查）。
- **接入成本**：中。Octopart 有免费档 API（速率受限），SnapEDA 提供符号/封装下载。

### 🥈 P1 · 连接器原厂 datasheet（JST / Molex / Hirose）
- **做什么**：把本轮已核实的 JST EHR-03/04、5264-3P、XT30PW-M 扩成**带官方 drawing 的连接器库**，喂给 adapter-generator 出转接盘 BOM。
- **为什么**：机械转接盘（第十类 Robotis Horn 接口）的下游就是「买对的连接器 + 画对的中介板」，原厂 drawing 是权威源。
- **接入成本**：低。原厂 PDF 公开，需结构化抽取（可挂脚本）。

### 🥉 P2 · OSHW / GrabCAD（机械 CAD 模型）
- **做什么**：给已收录实体补 STEP/STL，让「兼容性判定」能直接进 CAD 装配预览。
- **接入成本**：中。模型来源分散，需逐一核对授权（CC/MIT vs 商用保留）。

---

## 3. 推荐落地顺序（复用既有纪律）

1. **先链 LCSC + KiCad/atopile（P0）**：把 RoboParts 从「判定工具」升级为「可制造 BOM 工具」，应用度提升最大。
2. **再链 Octopart（P1）**：一次性把电气字段覆盖率从 1.8% 拉到可对外宣称的水平，顺带消解 `electrical_interfaces.json` 的 `honest_limits` 自陈缺口。
3. **连接器原厂库（P1）** 与机械转接盘（adapter-generator）合并推进。
4. **CIS 明确不接**——写进项目边界声明，避免后续再次被提议消耗决策带宽。

---

## 4. 一句话回答用户

> 「链接外部生态让应用度更完整」这个方向对，但**不该接 CIS**（封闭商业 EDA 库，技术上不可达、语义错位、会污染开放定位）。真正该链的是**开放生态**：LCSC/JLCPCB（制造闭环）、KiCad/atopile（AI-PCB 上游）、Octopart（批量补数据）。这三者把 RoboParts 的护城河（零件级 + 兼容判定）从「判定」延伸到「真能买、真能造」。

---

*生成日期：2026-09-08 · 关联：`api/electrical_interfaces.json`（coverage.verdict 已引用本文件）· 纪律：所有链接均走开放 API，不引入商业许可耦合。*
