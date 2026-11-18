# `meta/roboparts.json` 具体 JSON Schema 草案

- 日期：2026-11-18
- 状态：**schema 草案**（未实现、未写入任何数据集；不动 `api/`、不动 `export_training_dataset.mjs`）
- 前置证据：真实 v3 实例 `lerobot/pusht` 的 [`meta/info.json`](https://hf-mirror.com/datasets/lerobot/pusht/resolve/main/meta/info.json)（`codebase_version=v3.0`，206 集 / 25650 帧，经 hf-mirror 取）
- 上游依据：[lerobot-dataset-v3.mdx](https://github.com/huggingface/lerobot/blob/main/docs/source/lerobot-dataset-v3.mdx)、[using_dataset_tools.mdx](https://github.com/huggingface/lerobot/blob/main/docs/source/using_dataset_tools.mdx)

---

## A. 前置结论（由 info.json 实例证明）

1. **`meta/info.json` 的 `features` 是完全开放的 map**：任意 feature 名 → `{dtype, shape, names, fps?, video_info?}`。v3 不限定 feature 白名单。
2. **每个声明的 feature 必须在数据分片** `data/chunk-*/file-*.parquet` **的每一帧出现**（pusht 里 `episode_index`/`frame_index`/`timestamp`/`task_index` 都是每帧标量列）。
3. **推论**：RoboParts 的静态参数若作为 feature，需逐帧重复写入——浪费空间、且与 v3 "frame-by-frame signals" 语义不符。**故 RoboParts 参数不应进 `features`，应进 meta 扩展**。
4. `modify_tasks` 工具会原地改 `meta/tasks.parquet` + `task_index` 列 + `tasks` 列（episode meta）+ `total_tasks`（info.json）——**任务层是 v3 原生可写入口**，但只适合"任务串"，不适合结构化的零部件/兼容性数据。

## B. `meta/roboparts.json` Schema 草案

顶层对象。与 `export_training_dataset.mjs` 已核实的字段**逐一同名**，不造新词。

```jsonc
{
  "schema_version": "1.0",                     // 本扩展的 schema 版本（非 v3 的）
  "dataset_binding": {                         // 绑定到哪个 v3 数据集
    "dataset_id": "<HF_REPO_ID>",              // 例 lerobot/pusht 或消费方自建集
    "bound_at": "<ISO8601>",
    "roboparts_snapshot": "api/training_dataset.json@2026-11-13T10:38:46.656Z"
  },

  "parts": [                                   // 零部件元数据（声明级，非实测）
    {
      "part_id": "<components[].id>",          // 例 ACT-001
      "name": "<name>", "name_en": "<name_en>",
      "manufacturer": "<manufacturer>",
      "category": "<category>",                // 16 类，例 actuators
      "type": "<type>",                        // 例 smart_servo
      "specs": {                               // 7 键全覆盖（659/659）
        "protocol": "<protocol>", "interface": "<interface>",
        "position_resolution": "<...>", "voltage": "<...>",
        "torque": "<...>", "speed": "<...>", "weight": "<...>"
      },
      "modalities": ["geometric","electrical","force","tactile","vision"], // 子集
      "modality_details": {
        "force": { "declared": true, "torque_nm": <num|null>, "weight_kg": <num|null>,
                   "force_control_precision_nm": <num|null>,   // 657/659 为 null → 不写或 null
                   "basis": "厂商公开声明字段，非实测" },
        "tactile": { "declared": <bool>, "basis": "...", "note": "无原始触觉传感" },
        "vision":  { "declared": <bool>, "note": "本平台不提供原始图像流" },
        "geometric": { "declared": <bool>, "identity": "<...>" },
        "electrical": { "declared": <bool>, "voltage_range": "<...>", "protocols": ["..."] }
      },
      "ros_support": <bool|null>,              // 49 True / 27 False / 583 null
      "price_range": "<price_range>",          // 自由字符串，例 "500-2000"；多为空
      "applications": ["..."],
      "standards": { "caee060_relevant": <bool>, "iso22166_relevant": <bool>,
                     "bus_class": "<...>", "ros2": <bool>, "interop_posture": "<...>" },
      "entity_kind": "component",             // 659 全部为 component（已校验）
      "evidence": {                       // 保持源嵌套，不扁平化
        "source_tier": "A|B|C",            // A=189/B=245/C=225
        "confidence": <num>, "verified": <bool>, "quarantine": <bool>,
        "source_url": "<url|null>"            // 值以 null 为主（175/659 为空值/null）；键在个别组件缺失
      }
    }
  ],

  "assemble_pairs": [                          // 已知真值装配对（判定器输出）
    {
      "pair_id": "<a>__<b>",
      "part_a": "<components[].id>",
      "part_b": "<components[].id>",
      "interaction_type": "flange_mount|bus_coupling|connector_insert",  // 2485/7189/630
      "overall_compatible": <bool>,            // 3663 True / 6641 False
      "compatibility_score": <int>,            // 整数百分制（真实样例：100 / 62）
      "dimensions": [                          // 恒 4 条（已校验）
        { "dimension": "mechanical|electrical|protocol|software",
          "compatible": <bool|null>, "score": <num|null>, "notes": "<...>" }
      ],
      "decided_dimensions": <int>,             // ⚠ 已判定维度**计数**，非数组（真实样例 3）
      "undecided_dimensions": <int>,            // 未判定维度**计数**（真实样例 1）
      "hard_dimensions_decided": <int>,        // 已判定硬约束**计数**（真实样例 2）
      "force_profile": { "force_senses": ["insertion_force","electrical_contact"],  // 随 interaction_type 变
                         "guidance": "<接插件插拔：关注插入力与接触力；本平台无原始插拔力曲线，需传感采集补充>" },
      "verdict_reason": "<3 个维度有双方声明且均兼容（含 2 项硬约束）>",
      "evidence_basis": "基于厂商公开声明字段的规则推断，非实测；未声明维度记为无法判定，不计入分子也不计入分母；判 true 至少需一项硬约束（协议/电气/机械）有双方声明"
      // ⚠ 边级**没有** source_tier / confidence / verified / quarantine —— 这些是零件级 evidence 字段（见 parts[]）
    }
  ],                                           // 全量 10304 条（decided 口径）

  "standards_ref": [                           // 20 项标准
    { "id": "<id>", "name": "<name>", "type": "<type>", "status": "<status>",
      "issued_at": "<date|null>", "issuer": "<...>", "evidence_tier": "<...>" }
  ],

  "honesty": { /* 原样带入 meta.honesty：声明级/非实测/剔除 undecided 无证据 */ },
  "provenance": { /* 原样带入 meta.provenance：tier_a=245/tier_b=324/tier_c=299、traceable_pct=28.23 */ },
  "consumption_note": "RoboParts 不提供原始图像/力觉/触觉时序与本体轨迹；本文件仅承载声明级参数与兼容性判定，供消费方作先验。"
}
```

## C. 消费方读取约定

- 消费方（TurboVLA / Isaac / MoziSim）读 `meta/roboparts.json` 获取：① 目标装配对的兼容性真值（`assemble_pairs[].overall_compatible`）→ 作动作/装配先验；② 零部件声明级参数（`parts[].specs`/`modality_details`）→ 作物理约束先验。
- **与 v3 标准共存**：`meta/roboparts.json` 是 RoboParts 自定义扩展。标准 v3 阅读器（`LeRobotDataset`）**忽略未知 meta 文件**，不破坏；需要先验的消费方显式读取。
- **绝不写入 `features`**：静态参数不进逐帧列（见 A.3），避免与 v3 语义冲突与空间浪费。
- **诚实标签**：`consumption_note` + 每条 `evidence_basis` 强制保留"非实测/声明级"字样；`source_tier` 供消费方按溯源过滤（A 可点开复核 / B 弱归因 / C 无溯源）。

## D. 未决 / 待拍板

1. **体积（已实测）**：全量导出约 **10.14 MB**（`perPart~1234B`×659 + `perPair~952B`×10304 + `perStd~464B`×20）。相对 v3 数据集声明的 `data_files_size_in_mb=100` / `video_files_size_in_mb=500`，meta 扩展偏小；但 10 MB 单文件进 git 仓库偏重，**建议分片**：`roboparts.pairs-NNN.json`（每条 ~2000 对）或按 `dataset_id` 只导出所需装配对。`parts[]` 带 `quarantine=true` 标记（113 条）但消费方可过滤（与前端"未核验数据"策略一致）。
2. **`assemble_pairs` 全量 10304 条**：若仅需"已知真值"装配对，可只导出 `overall_compatible=true` 的 3663 条，但会丢失"判定为不兼容"的负样本——建议保留全量，负样本对 VLA 的"禁止装配"监督同样有价值。
3. **`modify_tasks` 通道**：若要把"任务串"写进 `meta/tasks.parquet`（B 方案），属 v3 原生入口，安全；但结构化先验仍走 `meta/roboparts.json`（A 方案）。二者不互斥。

*本草案不实现、不写入任何数据集；工作区未提交项仅 `intel/reports/lerobot-v3-列映射草案-2026-11-18.md` 与本文件（均待批是否入库）。*
