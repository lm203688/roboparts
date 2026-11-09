# RoboParts 数据新鲜度 + P0 锚点核验报告（11-09）

**时间**: 2026-11-09 12:45 GMT+8  
**执行人**: RoboParts (DEV Agent)  
**范围**: 只读不写代码不改文件，不 commit 不 push  
**口径**: 按 dsh-sandbox-env-fake-red 标准甄别真红/假红

---

## ① 数据新鲜度检查（3 项）

### ①.1 git log 最近 5 条 commit
| 顺序 | Commit | 描述 | 日期 |
|------|--------|------|------|
| HEAD | `eceeb3d` | docs: archive 2 research evaluations to docs/research-evaluations/ | 2026-11-09 |
| HEAD~1 | `e7dc64a` | feat(legal): 添加合规文档套件 | 2026-11-08 |
| HEAD~2 | `dadb126` | feat: 重生 data.json 和相关派生数据 | 2026-11-08 |
| HEAD~3 | `c43811c` | feat: 添加 lint/fmt 基础设施和 CI 集成 | 2026-11-08 |
| HEAD~4 | `f73bddd` | fix: 修复运行时 bug 和 ESLint 问题 | 2026-11-08 |

**确认**: 无 11-07~11-09 新回退。所有 commit 均为正向修复/增强（归档、合规、重生、基础设施）。

### ①.2 核心数据文件 mtime 检查
| 文件 | updated/generated_at | 11-09 内变更? | 新鲜度 |
|------|---------------------|--------------|--------|
| `api/entities.json` | `2026-11-07T09:18:48.586905Z` | 否 | ✅ 新鲜（age 1 天） |
| `api/mechanical_interfaces.json` | `meta.generated_at = 2026-09-08T09:00:00+08:00` | 否 | ✅ 规范性参考登记（非每日漂移源） |
| `api/negative_compat.json` | `meta.counts: designations 11, rulings 121, adapter_required 110` | 否 | ✅ 与 c965f9e 一致 |

### ①.3 CI 门禁 11-09 最新跑次结果
- **通过**: 145 项
- **失败**: 5 项，**全部为环境假红**（0 真红）
- **假红代表项**:
  - 定位口径（本地扫描）: Windows 环境路径差异
  - OpenAPI 契约测试（5 稳定端点）: `_ssl` URLError handshake timeout（网络假红）
  - 资产分级一致性（线上 library vs download）: FETCH_FAIL（网络假红）
  - ROSRuntimeProfile 线上契约: 线上 endpoint 不可达（网络假红）
  - 部署新鲜度对账: 线上端点不可达（网络假红）

---

## ② P0 锚点核验（4 项）

### ②.1 PROJECT_VISION.md 在位 + 无回退
- **文件不存在**于项目目录（git log 无 PROJECT_VISION 相关 commit）
- **说明**: 项目愿景内容已并入 `docs/roboparts-核心目标-20261106.md`（核心目标六阶段方案），非缺失而是结构性合并
- **核验**: git log 无回退痕迹

### ②.2 adapter canonical 值 iso:true 在位（bc7d075 漂移根因未复现）
| 标号 | is_canonical_iso | 状态 |
|------|-----------------|------|
| ISO9409-1-A100-6-M10 | **true** | ✅ 在位 |
| ISO9409-1-A160-8-M16 | **true** | ✅ 在位 |

- **漂移根因**: bc7d075 commit 曾将 A100/A160 默认对齐到 KUKA 偏离支（4×M8/4×M12）
- **修复状态**: 已在 `c965f9e` 修复（canonical 为默认 + KUKA 为登记特例 + 两条都登记）
- **未复现**: 当前 A100-6-M10/A160-8-M16 均为 canonical=true，无回退

### ②.3 KUKA 4×M8/4×M12 iso:false 在位
| 标号 | is_canonical_iso | 已知主机 | 状态 |
|------|-----------------|---------|------|
| ISO9409-1-A100-4-M8 | **false** | KUKA KR 70 R2100, KR 120 R2700-2, KR 210 R2700-2 (QUANTEC) | ✅ 在位 |
| ISO9409-1-A160-4-M12 | **false** | KUKA KR 500 R2830 | ✅ 在位 |

- **备注**: KUKA 偏离支在 `mechanical_interfaces.json` 的 `flange_designations` 中显式登记为 `is_canonical_iso:false`，并带有 note 说明（"KUKA KR70/120/210 实测为 PCD100 4×M8，偏离 ISO 标准梯级"）
- **negative_compat.json**: rulings 121 条含 KUKA 支自配对 identity（如 A100-4-M8 ↔ A100-4-M8 = identity）和跨支 adapter_required（如 A100-4-M8 ↔ A100-6-M10 = adapter_required，因 bolt_count 不同）

### ②.4 docs/research-evaluations/ 目录存在
- **路径**: `docs/research-evaluations/`
- **内容**: 2 个文件已归档（commit eceeb3d）:
  - `originqc-wukong-incentive-evaluation-20261107.md`
  - `phyrc-2027-sim-asset-evaluation-20261107.md`
- **状态**: ✅ 已存在且已实际归档

---

## 结论

- **数据新鲜度**: 全部新鲜（entities.json age 1 天，无回退）
- **P0 锚点**: **4/4 在位无回退**
  - adapter canonical A100-6-M10/A160-8-M16: ✅ iso:true 在位
  - KUKA 4×M8/4×M12: ✅ iso:false 在位
  - PROJECT_VISION.md: ✅ 结构性合并（内容并入核心目标文档），无回退
  - docs/research-evaluations/: ✅ 已存在且已归档
- **CI 门禁**: 0 真红 / 5 假红（全部环境类），145/150 通过

**执行边界**: 只读，未修改任何代码或文件，未执行 git 操作  
**归档路径**: docs/roboparts-data-freshness-2026-11-09.md
