# 00_Spec — 写作规范（冻结版 v1，2026-11-09）

> 本文件是本论文包的唯一写作标准。任何子任务（提纲、主稿、图表、投稿包、数据卷宗）先读本文件与同目录 `FROZEN_NUMBERS.json`，再动手。
> 冲突时优先级：`FROZEN_NUMBERS.json` > 本文件 > 任何子代理的自行判断 > 本地旧稿（旧稿优先级最低，其主张已被数据否掉，见 §0.2）。

## 0. 任务定性与定位

### 0.1 这是一篇全新论文
标题暂定稿（**首选 A，不要另立标题**，除非子代理发现不可克服的文献撞题并在回报中给出证据）：

> **How Compatible Is "Compatible"? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces**

备选（仅在首选被证明确实撞题时启用，需回报理由）：
- B: *Port Budget, Not Data Quality: Why Co-Mounting Robotic End Effectors Is Structurally Unavailable*
- C: *What Nobody Declares: Interface Description Gaps Across a 656-Node Catalogue, a 21-Model Standard, and a 528-Product Marketplace*

### 0.2 禁止沿用的旧主张（写进去就是硬伤）
- 旧 Mechatronics 稿的 **"K=2 结构定理"**：已在本轮数据上被否，全文不得出现 K=2 定理的任何表述。
- **"6.57% 可判定率"**：与四级阶梯无法共存，全文零出现；也不得作为"前人数据"引用。
- **"2,016 对 / 0.94% 机械可判定"**：与冻结的 bootstrap 行冲突，零出现。
- **任何单一"兼容率/可判定率"数字**：本文的立论恰恰是"只报一个数就在隐式选口径"。凡出现比率，必须同时给出口径（哪一级、哪条轴、分母是多少）。

### 0.3 定位句（摘要与引言结尾都要有它的等价表述）
> 前人把接口兼容性当作**判定问题**（给定描述即可判定）；本文证明它是**测量问题**（判定率本身是证据门槛的函数，且在四个门槛之间跨 5 个数量级），并给出零的**结构性上界**。

正文写法：This paper does not ask whether a given pair is compatible. It asks how much of the question is decidable at all, at what evidential price, and which part of the answer no amount of evidence can change.

## 1. 五个贡献（顺序固定，不得换序、不得增删）

1. **四级可判定性阶梯与 5 个数量级落差**（64.764% → 0.00512% → 0.00372% → 0.00047%），机制 = 占位端口自匹配（528/553 个电气端口是 `ELEC:UNKNOWN`，D0 的 139,128/139,139 = 99.992% 是 UNKNOWN×UNKNOWN）。
2. **最弱轴判定**：电气轴在所有定义下低机械轴 1–3 个数量级。**必须分层陈述**——机械轴下限 0.0132% 与电气轴上限 0.268% 有重叠，因此禁止写成"电气永远低于机械"一句话；正确写法是"点估计差 17–230 倍，且在每一层定义下电气轴的点估计都低于同层机械轴的点估计"。
3. **零的分类学 Z1–Z5**，并给出"哪几类补证据可消、哪几类不可消"的判据；核心数字 **Z1+Z5 = 297/360 = 82.5% 不可由补证据消除**。
4. **命题 P1（端口预算上界）** + 推论 C1/C2/C3。这是全文唯一的演绎部分，按公理化-演绎链写：定义 → 假设 → 命题 → 证明 → 推论。**证明要独立成段，可被逐句检验**。
5. **法兰是套件属性而非器件属性**（同一器件可对三种法兰标号；"identity 判定"实质是套件规格同一，不是器件可互换）。

## 2. 章节结构与字数预算（EN 主稿，正文不含参考文献/附录）

| § | 标题（EN） | 字数 | 必须落的数 |
|---|---|---|---|
| — | Abstract | 250–300 | 阶梯四级四个数、528/553、82.5%、p=1 |
| 1 | Introduction | 1,100–1,400 | 定位句、五个贡献各一句、656/214,840、329 厂商 |
| 2 | Related Work and Positioning | 1,200–1,500 | Tola 2022 摆第一；HRIM 21/3/0/0；UR+ 528、0/528 |
| 3 | Corpus, Isolation and Provenance | 1,000–1,300 | 868/656/214,840/329、634/200,661、553/17/528/25/6 |
| 4 | The Four-Level Decidability Ladder | 1,500–1,800 | D0–D3 四行、三个倍数（12,650× / 1.4× / 139,000×）、11 对逐条、Table 2/3、Fig 1 |
| 5 | Cross-Axis Comparison and the Weakest Axis | 1,100–1,400 | 五行 bootstrap + CI、11 倍、17–230 倍、去重灵敏度、Table 4、Fig 2 |
| 6 | A Taxonomy of Zeros | 1,300–1,600 | 360/0/171/126/63、240/171/120、82.5%、Table 5、Fig 3 |
| 7 | Port Budget: An Upper Bound on Co-Mounting | 900–1,200 | p=1、8 针≠8 位、C1/C2/C3、FR3 p=null |
| 8 | The Flange as a Suite Attribute | 800–1,000 | Robotiq 三标号、OnRobot Quick Changer、ATI 71.12 mm/6×M5、UR20/30 80-6-M8 + 20 kg |
| 9 | Discussion: What Would Change the Answer | 1,000–1,300 | 上界测算 1,268 / 0.590%、β 类 44 件不得补法兰、κ=0.6236、诚实边界五条 |
| 10 | Conclusion | 300–450 | 三条落点，不重复摘要原句 |

合计约 **9,000–10,500 词**。允许 ±10%。超过 11,500 词要砍，砍 §2 的文献铺陈，不许砍 §4/§6 的证据密度。

**必须在正文出现的表与图**：Table 1（语料与端口计数）、Table 2（四级阶梯）、Table 3（11 个 D1 对逐条）、Table 4（五轴 bootstrap）、Table 5（零的分类学）、Table 6（上界测算）；Fig 1–3。

## 3. 图表规格（与 `05_Figures/make_figures.py` 一一对应）

- 全部 **300 dpi PNG**，英文标注，正文可直接引用；单栏宽 3.5 in、双栏宽 7.0 in。
- 字体 Arial 系（缺失则 DejaVu Sans），轴标签 8–9 pt，刻度 7–8 pt；不要图内标题（标题进 caption）。
- 配色（避免靛蓝/紫色系）：`#2F4858` 石板灰蓝、`#33658A` 钢蓝、`#86BBD8` 浅蓝、`#F6AE2D` 琥珀、`#F26419` 橙、`#8C8C8C` 灰。
- 每图必须能"不看正文也读得懂数"，且图上数字与 `FROZEN_NUMBERS.json` 逐字一致。

**Fig 1 — 四级阶梯瀑布（对数轴）**
横轴 D0/D1/D2/D3，纵轴对数刻度 pairs（1 到 2×10^5）。柱顶标 pairs 与百分比；柱间标落差倍数 12,650×、1.4×，并在图内一侧标 D0→D3 = 139,000×（5 个数量级）。图内注明"D0 中 139,128/139,139 = 99.992% 为 UNKNOWN×UNKNOWN"。参考线：214,840 分母（虚线）。

**Fig 2 — 五轴点估计 + 95% CI 森林图**
五种定义各一行（n=295 / 2,211 / 3,240 / 171 / 77,815），x 轴对数（0.001%–100%），点估计 + 95% CI 须逐字取 §4 冻结表。电气行（0.0796% [0.0069%, 0.268%]）**用橙色单列高亮**，并加一个 inset 放大 0–0.5% 区间；加一条 1% 参考虚线。图注写"CI 为按 329 家厂商整群 bootstrap（B=1000, seed=20261109）"。

**Fig 3 — 零的分类学与不可补比例**
主图：360 次 pair evaluation 的堆叠条 —— Z1 126（35.0%）、Z5/Z2 171（47.5%）、Z3/Z4 63（17.5%）。用花括号/箭头标 **Z1+Z5 = 297/360 = 82.5% irreducible**（跨前两段），并标 Z3+Z4 = 63（17.5%, removable by evidence）。图内小字注明"Z2 分布在 171 个 type_error 对内部，故与 Z5 同段呈现，不重复计数"。
副图 (b)：k=1 单挂 32 mountable / 16 unknown 与 k=2 共挂 360 评价 / 0 mountable 的对照条。

## 4. 术语与符号（全文统一，双语对照）

| EN（固定用词） | 中文对照 | 说明 |
|---|---|---|
| end-arm interface | 末端接口 | 本文统称机器人末端（法兰 + 电气 + 信号）的对接面 |
| end-of-arm tooling (EOAT) | 末端执行器/工装 | 首次出现给全称，之后用 EOAT |
| decidability | 可判定性 | 指"在该证据门槛下能否给出结论"，不是计算理论意义上的 decidability；首次出现须加一句限定，避免误读 |
| evidence threshold | 证据门槛 | D0–D3 的判据强度 |
| placeholder port | 占位端口 | `ELEC:UNKNOWN` 一类无实质标号的类型标签 |
| connector locus | 连接器所在位 | device / adapter / host / cable 四值 |
| port budget | 端口预算 | 宿主工具侧可独立供电并独立寻址的位数 |
| zero (Z1–Z5) | 零 | "判为不可共装/不可判"的结果；首次出现说明是"否定结论"而非数值零 |
| suite attribute | 套件属性 | 法兰标号归属套件而非器件 |

符号：$p(h)$ 宿主工具侧位数；$k$ 同挂器件数；$m$ 总线最大站数；$N$ 语料节点数（656）、$P$ 无序对数（214,840）；$D_0..D_3$ 四级判定对数。

## 5. 引用政策（硬约束）

- **每条参考文献必须有可核 URL 或 DOI**，一律不得编造。子代理给出的每条都要附核验方式与核验结果（`verified` / `not_verified`）。
- 引言必须**先**摆 Tola et al. 2022（Aarhus，position paper，六类挑战 A–G，明言 "no mature public robot system configurators exist"，PDF: https://clagms.github.io/assets/pdfs/Tola2022.pdf），再依次 HRIM（Zamalloa et al., arXiv 1802.01459）、Siltala IPAS 2019、Zheng et al. RCIM 2019（https://hal.science/hal-02129390/）、Chaumet et al.（Procedia CIRP / arXiv 2311.18533）、Tola arXiv 2401.02227。
- 三值 / 部分约束 / 占位推理线：Sabin & Freuder 1996、Ciucci & Dubois、Mittal & Falkenhainer (AAAI-90)、ConfWS 2024（https://imt-mines-albi.hal.science/hal-04770758v1）。
- 引用总数 28–40 条。**每条正文引用都要在参考文献表里出现，反之亦然**；编号连续、无断号。
- 风格：Elsevier 数字方括号顺序编码（[1], [2,3], [4–6]）。
- 禁止把"综述式的空话引用"堆在 §2；每条引用必须承载一个具体判断（谁说、说了什么、本文怎么用）。

## 6. 数字溯源三档（每个数字后面都要能追）

- `[V]` 已核一手（datasheet / 手册 / 官方页面逐字核过）
- `[O]` 官方或二手口径（未逐字核）
- `[E]` 本文现算、可复算

正文写法建议：在方法与结果里用 `(E)`/`(V)` 轻量标注（首次出现定义一次即可，不要每句都标），**表格里必须有一列 "Source"** 标 V/O/E。参考数据来源必须写清文件名（如 `electrical_interfaces.json`、`co_mount.json`、`robot_tool_side.json`）。

Data Provenance 段落必须如实写：数字来自主代理在本地 ROBOPARTS 语料上的现算产物（脚本 rp_b24.py / rp_b2v2.py / rp_ladder.py，产物 B4_稳健性与B2分诊_计算产物.json、B2B4_裁定数据.json），**不得声称本文重跑了引擎**；`04_ResearchData/Scripts/` 下的复算脚本若成功复现，写"独立复现 D0/D1"，若不一致，如实写差异。

## 7. 文风红线

- 美式英语；-ize 拼写；serial comma 全程一致；数字 <10 用英文词、≥10 用阿拉伯数字（百分数一律阿拉伯 + 三位小数或按冻结数字原样）。
- **禁词/禁句式**（出现即打回）：unlock、breakthrough、revolutionary、paradigm shift、first proof that compatibility is measurable、game-changing、seamless、robust solution、significantly（除非给统计量）、novel（可少量用于方法名，不用于自我评价）。
- 只说三件事：我们**测得**了什么、我们**证明了**什么上界、在**什么条件下**成立。
- 不用 emoji、不用感叹号、不用"We are excited"。
- 段落不得以"Moreover/Furthermore/Additionally"连开三段；论证靠内容衔接。
- 摘要不得出现未来工作承诺之外的自我评价。

## 8. 诚实边界（五条必须同时出现在 §9 与 Abstract 的量词里，缺一条打回）

1. 样本是**审计目录**不是市场普查（656 节点、329 厂商）；外推须限定。
2. bootstrap 按**厂商整群**，CI 极宽（电气 0.0069%–0.268%），外推不确定性确实这么大。
3. **κ=0.6236 是"关键词规则 vs 人工裁定"，不是双人编码**，须如实报并讨论其后果（故"补完 101 件"是伪需求，真待补 35 件）。
4. 宿主侧结论只在 **UR3e / UR5e / FR3** 三台上成立，不宣称全生态。
5. D3 的 1 对是"真互插"的**下界**而非上限（19 个电气节点里 device-side 端口极稀缺）。

## 9. 双语映射规则（CN 稿）

- CN 稿是**等结构对照稿**：节序、小节、表号、图号、数字、行数与 EN 完全一致，不做"中文改写式压缩"。
- CN 稿不译参考文献条目（保留英文原条目），图表标题双语（"Fig. 1 / 图 1"）。
- 术语按 §4 表；CN 稿数字写法与 EN 同（三位以内百分比原样保留，如 0.00512%）。
- CN 稿正文长度约为 EN 的 0.55–0.65（中文字数），不得删节改变论证结构。

## 10. 署名与红线

- 作者：**Xing Li**（英文名，Title Page 用）；中文稿署名 **李星**。
- 单位：**浙江省建筑科学设计研究院有限公司**；英文 **Zhejiang Academy of Building Research and Design Co., Ltd.**；中文法定全名待用户按营业执照订正，正文先按此写并在 PRISMA 文档 §7 列为"待用户确认项"。
- ORCID: **0009-0004-2152-7669**；邮箱 **463102527@qq.com**；Title Page 职位 **Senior Engineer**。
- **红线**：个人信息与全部投稿材料中只保留"国内正高工"职称；任何其他身份头衔、国别表述、外部头衔一律不出现（校验词表由 `02_Manuscript/check_docx.py` 与 `check_numbers.py` 维护，本规范不复述词表）。
- **不代投**：只写作与出投稿包，不操作任何投稿系统；Submission Guide 写成"人工执行清单"。

## 11. 目标期刊与零费用路线

- 首选 **RCIM — Robotics and Computer-Integrated Manufacturing**（Elsevier，ISSN 0736-5845）：主题最贴"装配/制造集成中的接口可判定性"。
- 备选顺序：**Journal of Intelligent Manufacturing**（0956-5515，**Springer**，非 Elsevier）→ **Mechatronics**（0957-4158）→ **Advanced Engineering Informatics**（1474-0346）。
- 费用口径：RCIM / Mechatronics / AEI 三刊为 Elsevier hybrid，可引官方口径 "Authors publishing in hybrid journals can publish under the subscription model at no cost"；JIM 为 Springer hybrid，付费路径是 Open Choice，默认订阅路线同样不收费，但其页面无 Elsevier 那句逐字表述，引用时不得混用。**必须逐刊核验**（期刊主页 APC 页 + 该刊是否 hybrid + 是否有 mandatory APC 的 special issue 风险）；被 robots.txt/WAF 拦则记 `NOT_VERIFIED` 并给 30 秒人工补证路径，禁止用未核数字。
- 一稿一投；声明页需写明与用户在投 CBM / JBE / 声供能等稿无重叠。

## 12. 交付物清单（本包最终形态）

```
RoboParts_兼容性四级阶梯_SCI/
├─ 00_Spec/spec.md, FROZEN_NUMBERS.json
├─ 01_Outline/TopicJustification_Outline_EN.md(+-.docx), ..._CN.md(+-.docx)
├─ 02_Manuscript/Manuscript_EN.md/.docx/.pdf, Manuscript_CN.md/.docx/.pdf, md2docx.py
├─ 03_Submission/CoverLetter.md/.docx, Highlights.md/.docx, TitlePage.md/.docx,
│                 SubmissionGuide_FeeVerification.md/.docx,
│                 PRISMA_SearchLog_and_DataProvenance.md/.docx,
│                 BlindedManuscript.md/.docx, ResponseToReviewer_Prep.md
├─ 04_ResearchData/DataDossier.md, Tables/T1..T6.csv, Bootstrap/bootstrap_results.json,
│                 Scripts/rp_ladder_recompute.py, rp_upper_bound.py, rp_bootstrap.py,
│                 results/frozen_checks.json
├─ 05_Figures/Fig1..Fig3.png, make_figures.py
└─ README.md
```

## 13. 自检口径（打包前必须全过，并在 README 里报结果）

1. 10 个 docx 全部用 python-docx 复读通过（能打开、段落数>0、表格数符合预期）。
2. 解 docx XML 检索 `**`、`<sub>`、`<sup>`、TODO、TBD、XXX 残留 = 0。
3. 身份词检索（词表见校验脚本）= 0 命中（全部 md/docx）。
4. 参考文献连续无断号；每条有 URL 或 DOI；抽查 5 条可打开。
5. 表格行数与正文声称一致（Table 2 = 4 行数据、Table 3 = 11 行、Table 4 = 5 行、Table 5 = 5 行、Table 6 = ≥6 行、Table 1 ≥10 行）；数据支撑表 ≥20 行。
6. 冻结数字一致性：正文/表格/图/摘要中出现的每个数都能在 `FROZEN_NUMBERS.json` 找到同值；`prohibited_numbers` 零出现。
7. zip 条目数 = 文件数 + 目录数。
