# RoboParts 零件标注规范（Part Annotation Spec）

> **本文件是贡献零件的「唯一权威格式」。** 它定义一条零件实体在 `api/entities.json`
> 里应该长什么样、每个字段怎么填才算数。读它一次，就能产出一条能通过 CI 闸门的实体。
> 流程与「无出处不收」的硬规矩见 [`CONTRIBUTING.md`](../CONTRIBUTING.md)；本规范是它的
> **格式层补充**——CONTRIBUTING 讲「什么能收」，本规范讲「收进来长什么样」。

---

## 0. 为什么要有这份规范

截至 2026-09-01，全库 768 实体里**机械接口有线索的仅 6 条（1.52%）**。
项目最缺的不是代码，是一条带出处的孔位数据。这份规范的目标，是让任何手上有
厂商手册的人，能**零歧义地**补一条零件进来——不用猜字段、不用等维护者往返问。

规范的设计原则（借鉴标品化数据集「统一 schema + 统一标注规范 + 开放贡献」打法）：

1. **单一真相源**：所有枚举、Tier 定义都从代码/registry 现读，本文不另抄一份（避免分叉失修）。
2. **宁可留空，不可臆造**：缺证据就写 `null` / `gap`，绝不填「应该是这样」的值。
3. **机器可校验**：每条规则都有对应 CI 闸门，提交即验，不靠人肉 review 兜底。

---

## 1. 实体级 Canonical Schema

一条零件实体（物理零部件）的**必备骨架**，契约见 `scripts/schema_contract.py`
（`SCHEMA_VERSION = 1.1.0`，`CORE_REQUIRED`）：

| 字段 | 类型 | 必填 | 规则 | 示例 |
|---|---|---|---|---|
| `id` | string | ✅ | 全局唯一短 ID，厂商/型号缩写，如 `ACT-028` | `"ACT-028"` |
| `rp_id` | string | ✅ | 格式 `RP-{前缀}-{4位序号}`，前缀见下表；合并时维护者校验唯一性 | `"RP-ACT-0028"` |
| `entity_kind` | enum | ✅ | 物理零件统一 `"component"`（其余值：`market_intelligence` / `software` / `specification` / `organization`，非零件勿用） | `"component"` |
| `name` | string | ✅ | 中文或通用名 | `"Robotiq 2F-85 夹爪"` |
| `category` | enum | ✅ | 20 品类之一，决定 `rp_id` 前缀 | `"actuators"` |
| `manufacturer` | string | 推荐 | 厂商名；市场情报/多供应商可填「多家」 | `"Robotiq"` |
| `source` | string | ✅ | 出处描述（一手来源优先） | `"Robotiq 官方产品手册…"` |
| `source_url` | string | ✅* | 可点开复核的链接；`source_tier=A` 时**强制** | `"https://assets.robotiq.com/…"` |
| `source_tier` | enum | ✅ | `A` / `B` / `C`，由证据形态推导，不自封 | `"A"` |
| `confidence` | number | ✅ | 0–1，由 `source_tier` 与证据详略决定 | `0.95` |
| `confidence_basis` | string | 推荐 | 置信度依据短码，如 `vendor_official_manual_with_dimensioned_drawings` | — |
| `verified` | bool | 推荐 | 是否经维护者点开链接复核 | `true` |
| `quarantine` | bool | 推荐 | 存疑待复核置 `true`，否则 `false` | `false` |
| `mechanical_interface` | object | ✅ | 机械接口声明（见 §2）；软件/协议类实体填 `{"status":"n_a"}` | — |

> `*` `source_url` 在 `source_tier=A` 时必填；`B`/`C` 若无链接可不填但会被降权。

### `rp_id` 前缀映射（按 `category`）

| category | 前缀 | category | 前缀 |
|---|---|---|---|
| actuators | ACT | sensors | SENS |
| controllers | CTRL | frames | FRAME |
| end_effectors | EFF | cables | CABLE |
| bearings | BRG | motors | MOTOR |
| adapters | ADPT | fasteners | FAST |
| gears | GEAR | encoders | ENC |
| grippers | GRIP | couplings | CPL |

> 不在上表的品类，前缀取 category 前 4 字母大写；序号从 `0001` 起，合并时维护者确认不撞号。

---

## 2. `mechanical_interface` 子对象详规

挂在实体下的机械接口声明。**这是兼容性引擎能算「能不能拧一起」的唯一输入**，务必填实。

| 字段 | 类型 | 必填 | 规则 |
|---|---|---|---|
| `status` | enum | ✅ | `declared` / `partial` / `not_declared` / `n_a`（见 §2.1） |
| `mount_type` | enum\|null | 推荐 | `null`（未采集）或 10 个合法键之一（见 §2.2）；**禁止写字符串 `"N/A"`** |
| `standard` | array<string> | 条件 | `status∈{declared,partial}` 时建议填；格式 `ISO 9409-1-{节圆}-{孔数}-M{螺纹}`，无 `A` 形式 |
| `flange` | object\|null | 否 | 法兰几何明细（PCD/孔数/螺纹/止口），有则填，无则 `null` |
| `declared_note` | string | 条件 | `status=declared` 时必填：**前提条件写这里**（如「须选配官方耦合件」） |
| `gap` | string | ✅ | **必填且不许写「无」**——公开承认这条数据判不了什么 |
| `source` | string | ✅ | 机械接口出处（可与顶层 `source` 不同，指向手册具体章节） | 
| `source_url` | string | ✅* | 机械接口出处链接；`status=declared` 时强制 |
| `confidence` | number | ✅ | 机械接口子置信度，可与顶层不同 |
| `registry_ref` | string | 否 | 固定 `"/api/mechanical_interfaces.json"` |

### §2.1 `status` 取值

| 值 | 何时用 |
|---|---|
| `declared` | 厂商明确给出可比对孔位标识（**节圆 + 孔数 + 螺纹三者齐全**） |
| `partial` | 厂商说了安装方式但缺关键尺寸，做不了孔位级互换判定 |
| `not_declared` | 适用机械接口，但厂商未公开 |
| `n_a` | 不适用（软件、协议、AI 模型、市场情报等无物理接口实体） |

### §2.2 `mount_type` 合法键（10 个，单一真相源 `api/mechanical_interfaces.json#mount_type_enum`）

- **标准派生组**（有标准出处）：`flange` / `shaft_sleeve` / `embedded` / `direct_mount` / `unknown`
- **本平台扩展组**（roboparts 内部键名，**非标准术语**，仅本平台使用）：
  `wire_to_board` / `press_fit` / `surface_mount` / `adhesive` / `integrated`

> `null` 合法，表示「未采集/不适用」——语义已由 `status` 承载，不要再写 `"N/A"` 字符串。

### §2.3 `standard` 编码格式

```
ISO 9409-1-{PCD}-{holes}-M{thread}
```

- 例：`ISO 9409-1-50-4-M6` = 节圆 Ø50、4 孔、M6 螺纹。
- 库内**统一无 `A` 形式**（不要写 `ISO 9409-1-A50-…`）。
- 一个零件配多种耦合件就列多个（见 §3 范本）。
- **不要把厂商简写当 ISO 编码发布**（见 §4 拒收情形 2）。

---

## 3. 最小可复制模板（完整一条，可直接过闸门）

下面是一条「黄金样例」骨架，字段均取自库内真实实体 `ACT-028`（Robotiq 2F-85）。
复制后替换你的零件信息即可：

```json
{
  "id": "ACT-028",
  "rp_id": "RP-ACT-0028",
  "entity_kind": "component",
  "name": "Robotiq 2F-85 Gripper",
  "category": "actuators",
  "manufacturer": "Robotiq",
  "source": "Robotiq 官方手册《2F-85 & 2F-140 Instruction Manual》§6.1.1 Couplings",
  "source_url": "https://assets.robotiq.com/website-assets/support_documents/document/2F-85_2F-140_TM-OMRON_InstructionManual_20190206.pdf",
  "source_tier": "A",
  "confidence": 0.95,
  "confidence_basis": "vendor_official_manual_with_dimensioned_drawings",
  "verified": true,
  "quarantine": false,
  "mechanical_interface": {
    "status": "declared",
    "mount_type": "flange",
    "standard": [
      "ISO 9409-1-50-4-M6",
      "ISO 9409-1-31.5-4-M5",
      "ISO 9409-1-40-4-M6"
    ],
    "flange": null,
    "declared_note": "孔位随官方耦合件可变，非单一法兰：须选配对应型号耦合件（含电触点）方可安装。",
    "gap": "PCD56(6×M4)/PCD60(4×M5) 无 ISO 编码，未纳入自动比对集合；夹爪本体与耦合件间接口（Ø63 F8 止口）未单列为可比对标识。",
    "source": "Robotiq 官方手册 §6.1.1 Couplings",
    "source_url": "https://assets.robotiq.com/website-assets/support_documents/document/2F-85_2F-140_TM-OMRON_InstructionManual_20190206.pdf",
    "confidence": 0.95,
    "registry_ref": "/api/mechanical_interfaces.json"
  }
}
```

**非机械实体最简形态**（软件/协议/市场情报）：只需 `mechanical_interface: {"status":"n_a"}`，
其余顶层字段照 §1 填，不写任何几何字段。

---

## 4. 标注纪律：四类一律不收（详见 CONTRIBUTING §二）

1. **凭记忆填的尺寸**——哪怕你是十年工程师，也给链接。
2. **替厂商「翻译」成 ISO 编码**——厂商写「P.C.D. 56, 8×M4」请**原样照抄**，勿写成 `ISO 9409-1-56-8-M4`。
   真实悬置案例：`ACT-028` 厂商手册简写与现行知识库 ISO 编码两处自不一致、且未核到 ISO 原文是否收录该尺寸，
   故该条 PCD56/PCD60 至今**悬置不收**，分歧写进 `gap` 公开挂着。把简写当 ISO 发布，既可能造出空编码被爬虫抄走，也会与他方写法产生假阴。
3. **论坛帖 / 经销商汇编 / 二手转述**——降为 Tier C（`confidence` 上限 0.30），多数直接不收。
4. **补全「应该是这样」的缺失项**——手册没给的就写进 `gap` 承认判不了，勿按标准梯级推值填上。

---

## 5. 溯源 Tier 与置信度档位

| Tier | 含义 | 典型 confidence | source_url |
|---|---|---|---|
| A | 可点开复核的一手来源（官方规格书/标准文本/带链接厂商文档） | 0.92–0.95 | **必填** |
| B | 弱归因（厂商目录声明值、官网首页，无原始链接） | 0.6–0.8 | 可选 |
| C | 无溯源（历史导入，待补来源） | **上限 0.30** | 无 |

`source_tier` 由证据形态推导，唯一源 `scripts/govern_source_tier.py`，录入者不得自封。

---

## 6. 提交后会发生什么

1. **PR 通道**：Fork → 改 `api/entities.json` → 本地跑 `python scripts/ci_gate.py` → 推 PR。
   GitHub Actions 自动跑同一套闸门，红了会告诉你具体哪条越界。
2. **Issue 通道**：不想碰 JSON，走[机械接口声明 Issue](https://github.com/lm203688/roboparts/issues/new?template=mechanical-interface.yml)
   或[数据纠错 Issue](https://github.com/lm203688/roboparts/issues/new?template=data-correction.yml)，维护者代录并署名。
3. **复核**：维护者**逐条点开你给的链接复核**；核不上的回帖问，不静默丢弃；出处冲突时把分歧写进 `gap` 公开挂着。
4. **署名与许可**：署名收录，数据 CC BY 4.0（代码 MIT）。详见根目录 [`LICENSE`](../LICENSE)。

> ⚠️ **不要手改这些派生文件**（由脚本从真相源现算，手改会被闸门判红）：
> `api/data.json`、`api/<category>.json`、`data.js`、`roboparts-dataset-github/` 下任何文件、页面里的数字。

---

## 7. 本地自检清单（提交前必跑）

```bash
python scripts/normalize_categories.py     # 重生成派生文件
python scripts/ci_gate.py                  # 实体契约 + mount_type 枚举 + 分发一致性 + 安全 + 凭据
```

闸门全绿再提。一条实体缺 `id`/`rp_id`/`entity_kind`/`name`/`category` 任一，
或 `mechanical_interface.status` 越界、或 `mount_type` 不在 10 枚举内（非 null），都会判红。
