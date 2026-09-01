# 给 RoboParts 贡献数据

先说结论：**这个项目最缺的不是代码，是一条带出处的孔位数据。**

截至 2026-08-31，全库 768 个实体里机械接口有线索的只有 **6 条（1.52%）**——
2 条 `declared` + 4 条 `partial`，分母是 395 个适用实体（373 个软件/协议类实体不适用）。
换句话说，「这两个零件能不能拧到一起」这个问题，我们目前 98% 答不了。

所以补一条 Robotiq 手册里的 PCD 尺寸，比重构一遍推荐算法有用得多。

---

## 一、三条通道，按门槛从低到高

| 你的情况 | 走这条 |
|---|---|
| 手上有厂商手册，但不想碰 JSON | [机械接口声明 Issue](https://github.com/lm203688/roboparts/issues/new?template=mechanical-interface.yml) —— 贴链接，我们代录并署名 |
| 发现某条数据错了 | [数据纠错 Issue](https://github.com/lm203688/roboparts/issues/new?template=data-correction.yml) |
| 会写 JSON，想直接改 | Fork → 改 `api/entities.json` → 本地跑闸门 → PR |

**不必会写 JSON。** 第一条通道就是为「有资料但懒得学格式」的人准备的。

---

## 二、唯一的硬规矩：无出处不收

这不是客套。registry 的 `coverage_policy` 原文：

> 只登记有公开可溯源出处的规格。无出处的尺寸一律不写，宁可留空，不可臆造。

具体到会被拒的四种情况：

1. **凭记忆填的尺寸。** 哪怕你是这行做了十年的工程师，也请给链接。
2. **替厂商「翻译」成 ISO 编码。** 这条最容易犯，也最有害。
   厂商手册写「P.C.D. 56, 8×M4」时，请**原样照抄**，不要写成 `ISO 9409-1-56-8-M4`。
   我们在 ACT-028（Robotiq 2F-85）上正踩着这个坑：2019 版手册 §6.1.1 记作简写、
   Robotiq 现行知识库记作 ISO 编码，两处厂商出处自己就不一致，且未核到 ISO 9409-1
   原文是否收录 56-8-M4 尺寸——所以这条至今**悬置不收**，理由写在实体的 `gap` 字段里。
   把厂商简写当 ISO 编码发布，既可能凭空造出一个编码被爬虫抄走，也会与他方写法产生假阴。
3. **论坛帖 / 经销商汇编页 / 二手转述。** 会被降为 Tier C（`confidence` 上限 0.30），
   多数情况直接不收。
4. **补全「应该是这样」的缺失项。** 手册没给螺纹旋入深度，就写进 `gap` 公开承认判不了，
   不要按标准梯级推一个值填上去。

判据不由录入者自封：`source_tier` 由证据形态推导，唯一源是
`scripts/govern_source_tier.py`。三档定义：

| Tier | 含义 |
|---|---|
| A | 可点开复核的一手来源（官方规格书 / 标准文本 / 带链接厂商文档） |
| B | 弱归因（厂商目录声明值、官网首页，无原始链接） |
| C | 无溯源（历史导入，待补来源，`confidence` 上限 0.30） |

---

## 三、机械接口声明的最小可核验格式

字段挂在实体的 `mechanical_interface` 下。下面是库里**真实在用**的一条
（ACT-028 Robotiq 2F-85，节选，可在 `api/entities.json` 逐字核对）：

```json
"mechanical_interface": {
  "status": "declared",
  "mount_type": "flange",
  "standard": [
    "ISO 9409-1-50-4-M6",
    "ISO 9409-1-31.5-4-M5",
    "ISO 9409-1-40-4-M6"
  ],
  "flange": null,
  "declared_note": "孔位随官方耦合件可变，非单一法兰：AGC-CPL-062-002=ISO 9409-1-50-4-M6……耦合件为必需件（集成电子与电触点），故「可装」的前提是选配对应型号耦合件。",
  "source": "Robotiq 官方手册《2F-85 & 2F-140 Instruction Manual》§6.1.1 Couplings",
  "source_url": "https://assets.robotiq.com/website-assets/support_documents/document/2F-85_2F-140_TM-OMRON_InstructionManual_20190206.pdf",
  "confidence": 0.95,
  "registry_ref": "/api/mechanical_interfaces.json",
  "gap": "PCD56(6×M4)/PCD60(4×M5) 无 ISO 编码，未纳入自动比对集合；夹爪本体与耦合件之间的接口（Ø63 F8 止口）未单列为可比对标识。……"
}
```

### 字段规矩

**`status`** —— 四个合法值，越界会被闸门判红：

| 值 | 什么时候用 |
|---|---|
| `declared` | 厂商明确给出可比对的孔位标识（节圆 + 孔数 + 螺纹三者齐全） |
| `partial` | 厂商说了安装方式但缺关键尺寸，做不了孔位级互换判定 |
| `not_declared` | 适用机械接口，但厂商没公开 |
| `n_a` | 不适用（软件、协议、AI 模型等无物理接口的实体） |

**`mount_type`** —— 合法取值以
[`/api/mechanical_interfaces.json#mount_type_enum`](https://roboparts.cc/api/mechanical_interfaces.json)
为准（当前 10 个），分两组：`standard_derived` 有标准出处，
`roboparts_extension` 是本平台内部键名、**不是标准术语**。
`null` 表示未采集/不适用——不要写字符串 `"N/A"`（`status` 已经承载这个语义）。

**`standard`** —— 数组。格式 `ISO 9409-1-{节圆}-{孔数}-M{螺纹}`（无 `A` 形式，
库内统一此写法）。一个零件配多种耦合件就列多个，像上面 ACT-028 那样。

**`declared_note`** —— **前提条件写这里，别省。**
「必须选配官方耦合件才能装」这种前提，直接决定「可装」这个结论成不成立。
省掉它，数据就从有用变成误导。

**`gap`** —— **必填，且不许写「无」。**
这个字段存在的意义是公开承认「这条数据判不了什么」。
上面 ACT-028 的 gap 老老实实写了两件事判不了。
一条没有 gap 的声明，我们会退回来问你到底核了什么。

**`confidence`** —— 由证据形态决定，不自封。参考库内实际档位：
官方手册逐项列出规格 → 0.92~0.95（ACT-028 / SENS-31）；
厂商只声明安装方式无尺寸 → 0.7（宇立 C025XX 等 partial 条目）；
Tier C 无溯源 → 上限 0.30。

---

## 四、提 PR 的话

```bash
# 1. 改 api/entities.json（唯一真相源，别改派生文件）
# 2. 重生成派生文件
python scripts/normalize_categories.py

# 3. 本地跑闸门自检（CI 跑的就是这套，本地绿了再提）
python scripts/ci_gate.py
```

`ci_gate.py` 会校验：实体 schema 契约、`mount_type` 枚举、对外数据集分发一致性、
agent 技能清单一致性、JSON 可解析、`meta` 与实体一致、Functions 顶层安全、无凭据泄漏。
PR 推上来后 GitHub Actions 会自动跑同一套，红了会告诉你具体哪条越界、怎么修。

**不要手改这些文件**（它们由脚本从真相源现算，手改会被闸门判红）：
`api/data.json`、`api/<category>.json`、`data.js`、`roboparts-dataset-github/`
下的任何文件、页面里的数字。

---

## 五、我们会怎么处理你的数据

- **署名收录**，许可 CC BY 4.0（数据）。
- 我们会**逐条点开你给的链接复核**。核不上的会回帖问，不会静默丢弃。
- 如果我们判断你的出处与另一处厂商出处冲突（像 ACT-028 那样），
  会把**分歧本身**写进 `gap` 公开挂着，而不是单方面选一个信。
- 数据改动留痕，不静默改数。

## 六、代码贡献

同样欢迎，但请先跑通 `python scripts/ci_gate.py`。

一个容易踩的坑：Cloudflare Functions 里**禁止在模块顶层**调用
`Math.random()` / `Date.now()` / `crypto.getRandomValues()` / `crypto.randomUUID()`。
顶层求值发生在 isolate 启动期，违规会让 worker 启动即失败，
配合 `_routes.json` 的 `/*` 造成**全站 404**（2026-08-05 已出过一次这类事故）。
把这些调用挪进请求处理函数内部即可。闸门会拦，报错会指出具体文件和行号。

## 许可

代码 MIT，数据 CC BY 4.0。详见根目录 [`LICENSE`](./LICENSE)。
