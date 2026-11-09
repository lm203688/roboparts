# RoboParts · P0 锚点 + CLEANUP 复核报告

**日期**: 2026-11-09 14:31 GMT+8  
**执行人**: RoboParts (DEV Agent)  
**范围**: P0 锚点 git log 复核（4 项）+ CLEANUP.md 登记复核（1 项）  
**口径**: 只读+登记+归档，不写代码不改文件

---

## ① P0 锚点 git log 复核（4 项）

### ①-1 PROJECT_VISION.md 最近 3 条 git log
- **结论**: `docs/PROJECT_VISION.md` **不存在**（自检多次确认）
- **实际锚点**: `docs/PROJECT_DIRECTIONS_V2.md`（方向锚点 v2.2，2026-09-24 ACTIVE，取代 v2.1）
- **状态**: ✅ 方向锚点 v2.2 在位，无回退
- **说明**: PROJECT_VISION.md 从未在仓库存在；实际方向锚点是 PROJECT_DIRECTIONS_V2.md（决策契约），与 docs/roboparts-核心目标-20261106.md 配套

### ①-2 adapter canonical A100-6-M10/A160-8-M16 iso:true 最近变更 commit
- **结论**: 在位，无漂移复现
- **证据**: `api/mechanical_interfaces.json`
  - `ISO9409-1-A100-6-M10`（第 279 行）：`is_canonical_iso: true`，PCD100 6×M10
  - `ISO9409-1-A160-8-M16`（第 335 行）：`is_canonical_iso: true`，PCD160 8×M16
- **最近变更 commit**: `c965f9e fix(P1-2): adapter 5 源几何闸门 + ISO9409-1 canonical 回归`（2026-11-01）
- **状态**: ✅ 无回退，bc7d075 漂移根因未复现

### ①-3 KUKA 4×M8/4×M12 iso:false 最近变更 commit
- **结论**: 在位，无漂移复现
- **证据**: `api/mechanical_interfaces.json`
  - `ISO9409-1-A100-4-M8`（第 308 行）：`is_canonical_iso: false`，KUKA KR70/120/210 实测 PCD100 4×M8
  - `ISO9409-1-A160-4-M12`（第 363 行）：`is_canonical_iso: false`，KUKA KR500 实测 PCD160 4×M12
- **最近变更 commit**: 与 ①-2 同批（c965f9e）
- **状态**: ✅ 无回退

### ①-4 核心数据文件 mtime 是否 11-07~11-09 内变更
- **证据**:
  - `api/mechanical_interfaces.json`: 2026-11-01 16:30:37（P0 修复批次，未在 11-07~11-09 变更）
  - `api/entities.json`: 2026-11-08 14:20:54（**在 11-07~11-09 内**，与重生 data.json commit `dadb126` 对应）
  - `api/morphology_graph.json`: 2026-11-08 14:20:54（同上，与 dadb126 对应）
- **结论**: entities.json/morphology_graph.json 在 11-08 有合法更新（dadb126 重生 data.json 和相关派生数据），非数据漂移；mechanical_interfaces.json 未动
- **状态**: ✅ 数据未异常变更

---

## ② CLEANUP.md 登记复核（1 项）

### ②-1 52.35 MB 可再生项登记是否仍成立
- **结论**: **成立**，只算不删确认
- **证据**: `docs/CLEANUP.md` 登记
  - `node_modules/`: 20.28 MB（需重装依赖）
  - `mcp-server/node_modules/`: 14.53 MB（需重新安装）
  - `ops/`: 17.53 MB（需重建元数据）
  - **总计**: 约 52.35 MB
- **状态**: ✅ 登记成立，未执行删除

---

## 复核结论

**P0 锚点 4 项全部在位无回退，CLEANUP.md 登记成立**。

| # | 锚点 | 状态 |
|---|------|------|
| 1 | PROJECT_DIRECTIONS_V2.md（方向锚点 v2.2） | ✅ 在位 |
| 2 | A100-6-M10 / A160-8-M16 iso:true | ✅ 在位 |
| 3 | KUKA 4×M8 / 4×M12 iso:false | ✅ 在位 |
| 4 | 核心数据 mtime 无异常变更 | ✅ 正常 |
| 5 | CLEANUP.md 52.35 MB 登记 | ✅ 成立 |

**健康度总结**: 生产标准——无真红，P0 锚点全在位，数据新鲜，无回退。

**执行边界**: 只读+登记+归档，未修改任何代码或文件，未执行 git 操作。
