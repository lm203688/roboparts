# RoboParts 健康度扫描 · 2026-11-13

> 模板 v1（7 项固定格式，每项 ≤3 行，证据用数字/路径，不确定标"未核实"）
> 执行：RoboParts 工程 Agent ｜ 工作区：C:\Users\xing\Desktop\所有项目\2.robopart
> 上一份：2026-11-11（docs/health-scan-2026-11-11.md）

## 1. Git 状态
- HEAD `88bfcbd`（feat(ci): 跨引擎一致性重放测试 gate 91→92，2026-11-11 09:03）。
- 工作树未提交改动：M `scripts/positioning_contract.py`（P0 定位闸门 false-red 修复）、M `adapters/README.md`；未跟踪 6 项 docs（含 health-scan-2026-11-11.md、phyrc2026 提交包/论文、interface-adapter 分析）。
- P0 全部 12 项修复自 2026-11-01 起仍未 git commit（需用户授权）。

## 2. CI 闸门
- 本轮实测 `python scripts/ci_gate.py --format text`：**149 项断言通过 / 2 项失败**（前轮 148/3）。
- 失败 2 项均为**数据新鲜度**，非代码问题：① api/compose_frontier.json 陈旧 6.9 天（阈值 3 天，再生命令 build_compose_frontier.py）② data.json generated_at 陈旧 5 天（>3 天上限，跑 normalize_categories.py 重生）。
- 定位闸门 false-red 已闭环：**定位口径（本地扫描）** 由红转绿，定位口径契约自证 PASS（16 项，含 4 阴性对照 + 3 端到端）。

## 3. 文档完备度
- docs/ 共 119 个文件；根目录 README.md、AGENTS.md、CONTRIBUTING.md 均存在。
- ARCHITECTURE.md、PROJECT_VISION.md 不在根目录也非 docs/（未见，未核实是否存在其他路径）。
- 6 项未跟踪 docs 为 PhyRC2026 提交与近期分析产出，尚未入库。

## 4. 数据新鲜度
- api/entities.json：meta.updated = 2026-11-07T09:18:48.586905Z（**6 天前**），868 实体 / 20 品类 / 声明率 16.20%。
- 对外数据端点 data.json：generated_at 同 2026-11-07T09:18:48Z，**陈旧 5 天**（本轮闸门红）。
- api/compose_frontier.json：2026-11-06 06:45:33，**陈旧 6.9 天**（本轮闸门红）。

## 5. 未决问题
- 数据新鲜度 2 红：compose_frontier + data.json 端点需重生（属数据侧，不在本次工程修复范围）。
- P0 改动（2026-11-01 起）未提交；用户已定集中授权策略（git add+commit+push+tag 合并一次调用）。
- "清理孤儿 data.js" 需重估：被 112 文件引用，非孤儿（结论保留；历史 76 为过时口径）。

## 6. 能力边界自评
- 工程范围：代码完善、闸门维护、系统运行、数据新鲜度核对——均可执行。
- 超出边界：外部情报采集（情报官）、外部市场/科研（相应 Agent）、git 提交/推送/部署（Chief 决策）。
- 本轮定位闸门修复属工程范围，已验证闭环。

## 7. 本周建议
- 数据侧：跑 build_compose_frontier.py + normalize_categories.py 重生 compose_frontier 与 data.json 端点，清 2 红（建议情报官/Chief 确认数据语义是否需更新）。
- 工程侧：P1 高价值项实际进度 — adapter 5 源门 ✅、论文数字更新 ✅、pipeline→production ✅、包锁提交 ✅、regen_derived --check ✅、lint/format 进 CI ✅、前端构建 ✅、JS↔Py 重放 ✅（HEAD `88bfcbd` 已落地，gate 91→92）。剩余：data.js 重评估决策。
- 提交侧：待用户授权后合并提交 P0 修复 + 新增 docs + 本次定位闸门修复。
