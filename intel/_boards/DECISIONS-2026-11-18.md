# DECISIONS-2026-11-18

> 决议登记板 · 用户 2026-11-18 16:05 拍板（"拍板的都同意"），RoboParts lead 执行。
> 每项含：决议 / 执行状态 / 证据。

---

## D1 · MotionDecode 许可边界

- **决议**：确认 ChingMu MotionDecode 数据集非商业许可红线成立（academic / research / prototyping only，禁止商用分发与作为竞品托管）。未来若将 G1 动作资产接入 RoboParts 公开端点，**必须先二次确认许可边界**，且不得打包转售。
- **执行状态**：✅ 已确认并登记。
- **证据**：`intel/datasets/MotionDecode-资产登记-2026-11-18.md` 第五节「用户拍板确认」。
- **接入前置条件（三项齐备才启用）**：
  1. 补入 G1 构型链至 `kinematics/source.json`（当前仅 2 条 `topology_only` 链：KC-OMY-ARM、KC-ODM-BIPED，缺 link_mm / joint_limits）
  2. 关节限位元数据补齐
  3. 许可边界二次确认
- **本次动作**：不搬数据、不建消费管线、不提交数据文件本体。数据仍在 `1.swarmlabs/intel/datasets/MotionDecode` 原处。

## D2 · 工作树新增文件提交

- **决议**：授权提交 `intel/reports/` 与 `intel/datasets/` 两个新目录。
- **执行状态**：✅ 已提交并推送。
- **证据**：commit `f8418e6`「docs(intel): 入库 MotionDecode 资产登记 + 天池 OpenLET 契合评估」，2 files changed, 75 insertions(+)。
- **提交内容**：
  - `intel/reports/天池OpenLET契合评估-RoboParts-2026-11-18.md`
  - `intel/datasets/MotionDecode-资产登记-2026-11-18.md`

## D3 · git 分叉收敛

- **决议**：授权收敛本地 / 远程分叉。
- **状态变化（重要）**：扫描报告记录的 `24110d1 ↔ 897fe5a` 同父分叉（ahead=1/behind=1）**已不存在**。当前 `4b4512f` 直接建在远程顶端 `897fe5a` 之上，`rev-list --left-right --count origin/main...HEAD` = **ahead=1 / behind=0** → 线性领先，无需 rebase。
- **执行状态**：✅ 已推送，分叉彻底收敛。
- **证据**：
  - push 输出 `897fe5a..f8418e6 main -> main`（exit 1 为 PowerShell 将 git stderr 进度误判，非失败）
  - push 后 `rev-list --left-right --count origin/main...HEAD` = **0 / 0**
  - `origin/main` 与本地 HEAD 均为 `f8418e6`

---

## 未处理项（不在本次授权范围，如实登记）

工作树仍有以下改动，**非本 Bot 本轮造成**，未经指示不擅动：

| 类型 | 条目 |
|---|---|
| modified (7) | `CONTRIBUTING.md` / `DATA-LICENSE-MATRIX.md` / `README.md` / `api-pricing.html` / `data-hub.html` / `index.html` / `waitlist.html` |
| untracked (5) | `.memsearch/` / `RoboParts_DecidabilityLadder_SCI.zip` / `RoboParts_DecidabilityLadder_SCI/` / `RoboParts_兼容性四级阶梯_SCI/` / `切口核验_RoboParts可判定性/` |

*如需一并入库，请给出明确指示。*

---

*登记时间：2026-11-18 16:12 +08:00 · 执行者：RoboParts lead*
