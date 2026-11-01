# R1 变更说明：ISO 9409-1 法兰 adapter 默认值回归 canonical（2026-11-01）

> 本文档记录 P1-2（adapter 5 源几何闸门）实施过程中发现并修复的一处**历史数据漂移**：
> adapter 生成器把 A100/A160 的默认几何从 ISO canonical 标准梯级漂移到了 KUKA 厂商偏离。
> 按"诚实、可追溯、fail-closed"价值，向已下载旧版的用户说明根因、影响与处置。

---

## 1. 结论摘要

- **修复后默认**：`adapter-generator.html`、`adapters/gen_adapter.py`、`roboparts-dataset/scripts/gen_adapter.py` 三处
  adapter 预设的 A100 / A160 默认值**回归 ISO canonical 标准梯级**：
  - `ISO9409-1-A100-6-M10`（节圆 100mm / 6 孔 / M10）
  - `ISO9409-1-A160-8-M16`（节圆 160mm / 8 孔 / M16）
- **KUKA 偏离保留为显式登记变体**（默认不选）：
  - `ISO9409-1-A100-4-M8 (KUKA)`、`ISO9409-1-A160-4-M12 (KUKA)`
- **两条支都登记为真实存在**：`api/mechanical_interfaces.json` 的 `flange_designations` 从 **9 条 → 11 条**，
  canonical 支 `is_canonical_iso:true`（A100-6-M10 / A160-8-M16），KUKA 支 `is_canonical_iso:false` 保留。
- `api/negative_compat.json` 由 `scripts/build_negative_compat.py` 从 `flange_designations` **现算重新生成**：
  designations 9→11、rulings 81→121（identity=11, adapter_required=110）。
- **5 源几何闸门**（`scripts/check_adapter_geometry.py`）：HTML 预设 / 主 CLI / 数据集 CLI / 示例 +
  阴阳自证 **11 例全 PASS**，校验"默认=canonical 且两条都登记"。

## 2. 漂移根因：bc7d075 为何引入误导

`bc7d075`（2026-09-07，feat(scan): step.parts 互补落地 + 转接盘 BOM 物料清单）的提交说明写着：

> adapter-generator.html: 对齐真相源 api/negative_compat.json (A100 4xM8/A160 4xM12 修正，9/9 档零偏差)

**核实当时的登记表（`git show bc7d075:api/mechanical_interfaces.json`）**：

| Designation | is_canonical_iso | 说明 |
|---|---|---|
| ISO9409-1-A20-4-M3 | false | |
| ISO9409-1-A31.5-4-M5 | false | |
| ISO9409-1-A40-4-M6 | **true** | canonical |
| ISO9409-1-A50-4-M6 | **true** | canonical |
| ISO9409-1-A63-6-M6 | **true** | canonical |
| ISO9409-1-A80-6-M8 | **true** | canonical |
| ISO9409-1-A100-4-M8 | **false** | KUKA 偏离 |
| ISO9409-1-A160-4-M12 | **false** | KUKA 偏离 |
| ISO9409-1-A250-4-M16 | **false** | KUKA 偏离 |

**关键事实**：canonical 标准梯级在 A100 / A160 两档**没有登记**（登记表只到 A80-6-M8 为 canonical）。
当时的数据源是 step.parts 开放索引（命中 KUKA KR 70/120/210/500 等机型），
因此登记表只有 KUKA 偏离支，**canonical 支（A100-6-M10 / A160-8-M16）缺失**。

bc7d075 把 adapter 的 A100/A160 默认值对齐到当时"登记表里唯一存在"的 KUKA 支（4×M8 / 4×M12），
并声称"9/9 档零偏差"。**这个"零偏差"是相对当时不完整的登记表而言的**——登记表本身缺了 canonical 支，
导致**把厂商偏离当成了默认**，用户（最可能遇到标准法兰）生成的 adapter 默认就是 KUKA 几何。

### 旧版错在哪

1. **漏登记 canonical 支**：A100-6-M10 / A160-8-M16 未进 `flange_designations`（`is_canonical_iso:true` 缺失）。
2. **把特例当默认**：adapter 三处预设的 A100/A160 默认值指向 KUKA 偏离（4×M8 / 4×M12），
   而 KUKA 是少数厂商特例，不应作为用户默认。

## 3. 已下载旧版用户怎么办

- **如果用户生成的 adapter 用于 KUKA KR 70/120/210/500 等真实 KUKA 机型**：旧版默认（4×M8 / 4×M12）**恰好正确**，
  无需重新生成；新版把该几何保留为显式变体 `A100-KUKA` / `A160-KUKA`，手动选择即可。
- **如果用户生成的 adapter 用于标准法兰机型（UR、ABB、FANUC、Doosan 等，或不确定）**：
  旧版默认是错的（4×M8 / 4×M12 而非 6×M10 / 8×M16）。**应重新生成**，用新版默认（A100-6-M10 / A160-8-M16），
  并核对孔数/螺纹是否与手腕匹配。旧版已导出的 `.step` / `.stl` 不建议装机，需重新导出。
- **5 源闸门已把"默认=canonical 且两条都登记"纳入 CI**，今后此类漂移会被 CI 抓住（阴阳自证 11 例覆盖
  A100 孔数分叉、A80 pin_pcd 分叉、销孔节圆分叉、label/字段不一致、半径口径误用等）。

## 4. 涉及文件清单

| 文件 | 改动 |
|---|---|
| `api/mechanical_interfaces.json` | flange_designations 9→11：补 canonical 支 A100-6-M10/A160-8-M16（is_canonical_iso:true），KUKA 支保留 |
| `api/negative_compat.json` | 由 build_negative_compat.py 现算重新生成（designations 11, rulings 121） |
| `adapter-generator.html` | A100/A160 默认回归 canonical，新增 A100-KUKA/A160-KUKA 显式变体 |
| `adapters/gen_adapter.py` | 同上（主 CLI） |
| `roboparts-dataset/scripts/gen_adapter.py` | 同上（数据集分发副本） |
| `example_adapter.scad` | 已是 canonical（A50-4-M6 ↔ A80-6-M8，pin_pcd 63/100），无 A100/A160，无需改 |
| `scripts/build_articles.py` | 文章摘要同步 canonical 标准梯级 + KUKA 偏离说明 |
| `scripts/build_flange_page.py` | desc/kws 同步 canonical；尺寸族表格由 flange_designations 现算（11 条） |
| `scripts/check_adapter_geometry.py` | 修复正则假绿（key 支持 `-KUKA` 含字母）；阴阳自证 11 例；5 源闸门 |
| `iso-9409-flange.html` | 重新构建（11 个尺寸族全在） |
| `ops/roboparts-conformance-review-20260818.md` | 08-18 全部"待修"项关闭（复核状态标注） |

## 5. 验证

- `python scripts/check_adapter_geometry.py` → **PASS**（HTML 11 条 / 主 CLI 11 条 / 数据集 CLI 11 条）
- `python scripts/check_adapter_geometry.py --self-test` → **阴阳自证 11 例 PASS**
- `python scripts/ci_gate.py` → 63 通过 / 14 失败（14 失败全部 `PermissionError: [WinError 5]` 环境假红，
  Windows 沙箱 Temp/命名管道限制，GitHub Actions Linux 不会出现；本次改动未引入真红）
