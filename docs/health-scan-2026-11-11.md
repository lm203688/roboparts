# RoboParts 统一健康度扫描报告（2026-11-11）

> 模板：`C:\Users\xing\.dsh\bot\workspace\intel\_boards\健康度扫描模板-v1.md`（v1，固定 7 项）
> 扫描请求 ID：healthscan-roboparts-1111（统一版 m00060）
> 工作区：`C:\Users\xing\Desktop\所有项目\2.robopart`
> 诚实边界：不确定项已标"未核实"，未编造数字。

---

### 1. Git 状态

- 状态：main 分支，HEAD `88bfcbde68c3e8b7f0e9bac71fa8bf551431a60f`（2026-11-11 09:03:52 +0800，`feat(ci): 跨引擎一致性重放测试 gate 91->92`）。
- 证据：工作树 6 条改动 = 1 modified（`adapters/README.md`，11-11 11:39，179 行 / 8075 B）+ 5 untracked（`docs/phyrc2026-final-summary.md`、`docs/roboparts-interface-adapter-analysis-20261111.md`、`docs/roboparts-phyrc2026-submission-package.md`、`docs/roboparts-phyrc2026-submission-paper.md`、`docs/submission/`）。此前 gate 改写的 12 个 `api/*.json` 副产物已 `git checkout` 还原。
- 最近 3 commit：`88bfcbd`（11-11 09:03 feat(ci) gate 91→92）→ `8cff0f9`（11-09 17:28 docs: P1 status reports）→ `f9cca2b`（11-09 17:27 docs: clear add 7 untracked）。
- 建议：无回退；`adapters/README.md` + 5 个 docs 文件待 Chief 授权后合并为一次 commit。

### 2. CI 闸门

- 状态：闸门总数 151，**145 通过 / 6 失败**（exit 1）；最近一次运行 2026-11-11 17:2x（日志 `%TEMP%\rp_gate_1111.txt`，26758 B）。
- 证据（6 失败逐项归因）：
  1. **定位口径（本地扫描）= 真红（文档表述）**：`DATA-LICENSE-MATRIX.md` 仍含退役表述"RobotParts"，应改回"机器人零件兼容性判定层"（源改了要重新部署）。判据阴阳自证 PASS 16 项，仅此文件未改。
  2. **OpenAPI 契约测试（5 稳定端点线上拉取）= 假红（网络）**：`/api/deployment`、`/api/entities.json` TimeoutError，search / compatibility-not-found / funnel 通过，3/5；离线模式 5/5 PASS。
  3. **资产分级一致性（线上）= 假红（网络）**：`FETCH_FAIL https://roboparts.cc/api/urdf/libr`；schema_integrity / library_default_tier / l2_plus_has_source PASS。
  4. **ROSRuntimeProfile 线上契约 = 假红（网络）**：线上超时；离线模式 3/3 PASS，自证 6/6 PASS。
  5. **产物新鲜度检查（upstream mtime 兜底）= 真红（数据新鲜度）**：`api/compose_frontier.json` lag=5.1d > tol=3d（tracked 14 / stale 1 / 豁免 1）；再生命令 `python scripts/build_compose_frontier.py`。
  6. **对外数据集端点一致性 = 真红（数据新鲜度）**：`data.json.meta.generated_at=2026-11-07T09:18:48.586905Z` 陈旧 4 天 > 3 天上限；再生命令 `scripts/normalize_categories.py`。
- 建议：3 项网络假红在 GitHub Actions Linux 上不成立，非缺陷；2 项数据新鲜度是真实待办（见第 4 项）；1 项文档表述需改回。

### 3. 文档完备度

- 状态：核心文档齐备且较新——`README.md` 18055 B、`AGENTS.md` 782 B、`CONTRIBUTING.md` 10855 B、`docs/PROJECT_DIRECTIONS_V2.md` 15244 B、`docs/deploy.md` 3720 B、`docs/risk-matrix.md` 3500 B、`docs/negative-results.md` 3485 B；`docs/` 118 文件。`PROJECT_VISION.md` 不存在（实际锚点为 `docs/PROJECT_DIRECTIONS_V2.md`，已登记）。
- 证据：`adapters/README.md` 已于 11-11 从 61 行扩展为 **179 行**（ISO 9409-1 映射表 / 命名规则 / 法兰互换规则 / 材料与公差 / 可打印性 / 装配红线 / BOM / 最佳实践 / 质控 / 开源生态）；`docs/roboparts-interface-adapter-analysis-20261111.md` 已产出（FlyBrain + 世界模型契约映射，DRAFT 待审）。诚实边界声明在 `data.json` / `entities.json` / `compose_frontier.json` 的 `access.honest_limits` 与 `honest_limits` 字段均完整（cross_vendor_comparable_grade_a=0、mechanical_interface_declared_pct=16.2）。
- 建议：`DATA-LICENSE-MATRIX.md` 退役表述改回（与闸门 2.1 同源）；2 个 DRAFT 文档待 Chief 审阅后定稿。

### 4. 数据/资产新鲜度

- 状态：**总体健康但有 2 处过期**。`api/entities.json` updated=2026-11-07T09:18:48Z（868 实体 / 20 品类），`api/gap_classification.json` 2026-11-11 09:19:58（lag=-4.0d），`api/co_mount.json` 2026-11-07 16:46:30（lag=-0.3d）正常。
- 证据（过期项）：`api/compose_frontier.json` generated_at=2026-11-06T06:45:33Z（lag 5.1d，阈值 3d）；`api/data.json` generated_at=2026-11-07T09:18:48.586905Z（滞后 4 天，阈值 3 天）。其余 12 个跟踪产物 lag ≤ 2.1d 或属 2026-09-29/10-16 批次（受 `freshness_exemptions.json` 豁免，未核实豁免理由全文）。
- 溯源：provenance_coverage source_pct 94.59 / traceable_pct 28.23 / last_verified 66.47，tier A245 / B324 / C299；data_quality 868 中 clean 755 / quarantined 113（13.02%，ok755/placeholder_id51/unverifiable_vendor30/duplicate6/non_entity14/no_source12），重复对已解析 6 对；mechanical_interface_coverage applicable 500 / declared 67（fill_pct 16.2）。
- 建议：跑 `python scripts/build_compose_frontier.py` + `scripts/normalize_categories.py` 重生两项过期产物；修订后需重新部署。

### 5. 未决问题

- 状态：待修 bug 无已知失败项；待决策 3 项；阻塞 0 项。
- 证据：代码文件（py/mjs/js）397 个，TODO=35、FIXME=0（高优先待办集中在构建脚本，未逐条定性，未核实）。
- 待决策：① `adapters/README.md` + 5 个 docs 文件的 commit（需 Chief 授权，合并为一次）；② `DATA-LICENSE-MATRIX.md` 表述修复是否需要随下次部署上线；③ Cloudflare 部署链路失败提示（`部署后置新鲜度校验` ⚠️）需用户修。
- 建议：本周末前把①做成一次 commit，②③合并到下一次部署前处理。

### 6. 能力边界自评

- 已完成（有证据）：静态组合校验核心闭环——compose 三态（430336 三态 + 三轴边际守恒）、共装前沿（L1=28500/395 nodes、L2=63 pairs/16 nodes、L3=0）、跨引擎一致性重放 `--check` PASS 6 条、双引擎口径桥接、电气取证（15 devices/20 connectors）、ISO 22166 条款级映射覆盖率、变异评分 6/6 全杀死、3D 打印转接件生成器（在线 + CLI）。
- 未达成/负结果：`composed` 恒为 0（L3=0）——`compose_frontier.json` 结论为"高度可能是关系类型错配而非数据缺口"，仅 9 样本强假说、非定理；跨厂商可比 A 级条目 **0 条**；机械接口有线索比例 16.20%；标准符合度覆盖 assessed 88/768（11.46%）。未实现动态仿真（策略能不能跑），MuJoCo 引入评估结论为不引入生产依赖。
- 与目标差距：阶段二（生态接入契约）文档已产出但未实现运行时对接；阶段四 3D 打印链路已通文档+CLI，缺真实打印验证（未核实）。
- 建议：把"composed=0 归因"的 9 样本升级为定理（补更多取证样本），是阶段二/五的关键负结果转化项。

### 7. 本周建议动作（按优先级，最多 3 项）

- 建议1：**[高]** 生成两项过期数据产物——`python scripts/build_compose_frontier.py` + `scripts/normalize_categories.py`，跑闸门确认 6 失败降为 1（仅剩文档表述项）。理由：直接消除唯一 2 项真红数据新鲜度问题。
- 建议2：**[高]** 修 `DATA-LICENSE-MATRIX.md` 退役表述"RobotParts"→"机器人零件兼容性判定层"，源改后重新部署。理由：闸门 2.1 唯一真红，属文档修复，零风险。
- 建议3：**[中]** 将 `adapters/README.md` + 5 个 docs 文件合并为一次 commit（纯文档，不动其它），纳入待 push 批次。理由：集中授权策略下一次调用，保持工作树干净。

---

## 附：扫描方法与复现

- CI 闸门：`python scripts/ci_gate.py`，输出重定向 `%TEMP%\rp_gate_1111.txt`（`PYTHONIOENCODING=utf-8`），exit 1 / 145 pass / 6 fail。
- 线上探测：`/api/provenance.json` → 200 / 10503 B / 2.3s；`/api/entities.json` → 200 / 1564003 B（本轮首次探测）；`/` 与 `llms.txt` 多次 TimeoutError —— **Windows 沙箱网络不稳定，未核实是否真为线上故障**。
- 副产物还原：`git checkout -- api/{assembly_typecheck,behavior_evidence,compose_lattice_tests,electrical_evidence,evidence_ledger,gap_classification,iso22166_conformance,mutation-score,open_vla_binding,provenance,reachability_gap,research_progress}.json`，已执行，工作树现仅剩 6 条预期改动。
