# RoboParts 健康度扫描报告 2026-11-15

> 扫描时间：2026-11-15 09:03–09:44（Asia/Shanghai） · 工作区：`C:\Users\xing\Desktop\所有项目\2.robopart`
> 模式：只读核对（未改代码/未提交）；门禁副产物已按 AGENTS.md 还原，工作树 clean。

---

## 1. Git 状态

- 分支 `main`，HEAD = `24110d1`（RoboParts: 数据侧真红清零+定位闸门假红修复+适配器文档增强）
- 最近 3 commit：`24110d1` → `88bfcbd`（跨引擎一致性重放测试 gate 91→92）→ `8cff0f9`（P1 状态报告）
- 工作树 **clean**（untracked=0, modified=0）
- ⚠️ **发现分叉**：远程 `origin/main` 顶端 = `897fe5a`（2026-11-13 22:55 `chore: sync 1 local commit(s) via Git Data API (GFW bypass)`），父提交同为 `88bfcbd`；本地 `24110d1` 与远程 `897fe5a` 是**同父兄弟提交**。内容对比 `--ignore-cr-at-eol` = **0 行差异**（即内容完全一致，仅行尾/哈希不同）。ahead=1 / behind=1。
- 判断：11-13 push 因 GFW 阻断失败后，内容已由 Git Data API 同步到远端（新哈希）。无内容分歧，仅提交图分叉；建议 `git reset --hard origin/main` 或 `git pull --rebase` 收敛（内容无损）。

## 2. CI 闸门

- 运行：`scripts/ci_gate.py`，`PYTHONIOENCODING=utf-8`，真实退出码 **GATE_EXIT=1**
- 结果：**147 过 / 3 阻塞**（2026-11-15 09:13 完成，运行约 8 分钟）
- 3 项阻塞均为**线上拉取类**：① OpenAPI 契约测试（5 稳定端点线上拉取）② 资产分级一致性（线上 library vs download）③ ROSRuntimeProfile 线上契约（响应头+结构完整性）。另有「部署新鲜度对账」因 SSL 握手超时跳过（软通过）。
- 网络探测（决定性证据）：`roboparts.cc` root **TLSv1.3 + HTTP 200**（21964B）；`/api/llms.json` **200**（64KB, 2.8s）；但 `/api/actuators.json`（SSL 握手超时）、`/api/entities.json`、`/api/data.json`（大文件读超时）。
- 结论：**站点在线、小文件可达，大文件传输从本网络视角超时**——属网络层干扰（GFW/ISP 对大流量节流），**非数据/代码真红**。离线自证未在本轮单独重跑；11-13 同类离线自证 5/5 PASS。数据/代码真红 = 0。

## 3. 文档完备度

- 核心文档全存在：README.md / AGENTS.md / docs/iso22166-conformance-mapping.md / docs/roboparts-phyrc2026-submission-paper.md / docs/roboparts-interface-adapter-analysis-20261111.md / docs/health-scan-2026-11-11.md
- 文档与代码一致：PhyRC2026 提交包/论文、接口适配器分析已于 11-13 commit（24110d1）同步入库
- 诚实边界声明完整：ISO 映射 honest_limits（静态映射表边界）、adapter BOM 螺栓长度近似边界均显式声明
- 无过时/悬空文档。

## 4. 数据/资产新鲜度

- `entities.json` updated=`2026-11-13T10:38:38Z`；`data.json` updated=`2026-11-13T10:38:38Z`；`data.js` updated=`2026-11-13T10:38:38Z`（三源一致）
- `compose_frontier.json` updated=`2026-11-13T10:51:20+00:00`；`compose_semantics.json` updated=`2026-11-13T18:57:37+08:00`
- 全部关键资产 11-13 刷新（≤2 天），无 stale；门禁「产物新鲜度检查」PASS、「对外数据集端点一致性」PASS（generated_at 新鲜）
- 数据来源可追溯：entities.json 为单一事实源，派生产物由 regen_derived.py 统一重生（11-13 已验证幂等）

## 5. 未决问题

- 待修复 bug/TODO：13 个脚本文件含 TODO/FIXME/XXX 标记（多为注释性标注，需人工甄别是否含隐含缺陷）
- 未提交内容：0（工作树 clean）
- 待决策（本 Bot 层面）：无阻塞项；线上 3 门阻塞待网络恢复后复核
- 全局待决（Chief/用户层面，非本 Bot）：MVA2027 方向、蜂群agent 提交授权、WorldModel 元数据决策（11-15 截止）——本报告仅记录，不代决

## 6. 能力边界自评

- **已完成（有证据）**：868 实体全合规（schema 契约 PASS）；confidence_tier 区间 0 违规、Tier-C 上限 252 条 ≤0.30（source_tier=C 实测 299 条 max=0.30）；无出处政策 0 违规；last_verified 覆盖率 66.47%（577/868）；数据侧真红清零；定位闸门假红修复；跨引擎一致性重放测试落地（88bfcbd）
- **未达成/负结果（如实）**：3 项线上拉取门禁无法从本网络视角确认（大文件超时）；部署新鲜度对账跳过；last_verified 未探测 291 条（已显式标记，非缺陷）
- **与项目目标差距**：本轮无新增阻塞；P0 全部 12 项已于 11-13 提交

## 7. 本周建议动作（≤3，按优先级）

1. **[高] 收敛 git 分叉**：`git reset --hard origin/main`（内容无损，因 `24110d1` 与 `897fe5a` 内容一致）或 `git pull --rebase`——理由：避免后续 push 冲突/双历史。
2. **[中] 网络恢复后错峰复核 3 项线上拉取门禁** + 部署新鲜度对账——理由：本轮阻塞为网络层大文件超时，非代码缺陷，需复核确认归零。
3. **[低] 甄别 13 处 TODO/FIXME**：区分真待办与注释性标注——理由：数量较多，避免隐含缺陷被长期掩盖。

---

*扫描完成。只读核对，未改代码/未提交；门禁副产物 10 个已还原。*
