# 人形机器人数据第 2 批 · RoboParts 资产登记（2026-11-19）

> 落地位置：`2.robopart/intel/datasets/`（沿用 11-18 MotionDecode 的资产登记纪律：只登记、不接端点、不提交数据本体）
> 触发：用户指示"你看看哪个方便就下哪个"，目标是体积可控、免授权、通道能跑满的同类数据

## 一、通道实测（决定"哪个方便"的依据）

| 通道 | 实测速率 | 结论 |
|---|---|---|
| `huggingface.co` 直连 | 20 s 超时 | 不可用 |
| `hf-mirror.com`（HF 镜像） | 本次对大文件 **0.03–0.20 MB/s**，网页/CDN 侧近乎僵死 | 放弃（LAFAN1 那轮尚有 2.9 MB/s，属镜像侧波动） |
| `modelscope.cn` | 单流 1.95 MB/s，6 并发 **≈5.0 MB/s** 稳定 | **采用** |

因此本批全部走 ModelScope；HF 侧仅保留 11-19 上一批已完成的 LAFAN1/LAFAN1_npz。

## 二、落地清单（已校验）

### 1）`RoboMIND2.0/` —— 汇总仓（直臂/移动操作真机数据）

- 仓库：`X-Humanoid/RoboMIND2.0`（ModelScope，无需账号、无 gating）
- 实下：132 文件 / **6.85 GB**，目录 `data/`、`annotation/`、`assets/`、`README*`
- 校验：脚本收尾 `DONE ok=132 fail=0 bad=0`，逐文件字节数与远端清单一致，无残留 `.part`
- 内容结构：
  - `data/`：12 个本体各 1 个 `trajectory.hdf5`（tienkung 392 MB、tianyi 556 MB、tianyi_mobile 202 MB、agilex 762 MB、agilex_mobile 608 MB、franka 551 MB、franka_sim 213 MB、tienkung_sim 46 MB、ur 366 MB、ur_dex 286 MB、ark 1,264 MB、ark_mobile 1,239 MB）
  - `annotation/`：107 个 JSON（`meta_info/` 按 task_name 映射 episode，`mobile_manipulation/` 轨迹级子任务标注 + README_CN/EN）
  - HDF5 口径（见 README）：`metadata/language_instruction`、`camera_model`、`camera_intrinsics`、多路彩色/深度、`joint_actions` 等
- **未下**：`camera_extrinsics_intrinsics/`（1,761 文件 / **41.2 GB** 标定数据）——本批判断其价值低于轨迹本体，跳过
- **重要事实**：该汇总仓 `data/` 仅 6.3 GB，官方完整数据分散在 16 个子仓（`RoboMIND2.0-Tienkung`、`-Tianyi`、`-Tianyi-mobile`、`-Agilex`、`-Agilex-mobile`、`-Franka-Part-1..5`、`-UR5`、`-UR5-Dex`、`-Ark`、`-Ark-mobile`、`-Tienkung-sim`、`-Franka-sim`）。实测**单个 `Tianyi-mobile` 子仓即 1,791 文件 / 286.75 GB**，全量属 TB 级，与本机剩余空间不匹配，故本批不展开

### 2）`bones-seed/` —— BONES-SEED 的 Unitree G1 动作（本批最大收益）

- 仓库：`bones-studio/seed`（ModelScope 上的同命名空间公开副本；HF 原仓 `gated=auto` 匿名 403，本批改走 ModelScope 取得同一份数据）
- 已下并解压：
  - `g1.tar.gz` **23.50 GB**（8 段并行，76.6 min，`parts done=8 23.50/23.50 GB`）
  - 解压结果 `g1/csv/{日期}/{motion}.csv`：**142,220 条 CSV / 47.99 GB / 124 个日期目录**（与官方 Schedule 1 的 142,000+ 序列一致）
  - `metadata/`：`seed_metadata_v004.csv` 139.6 MB、`seed_metadata_v002_temporal_labels.jsonl` 55.7 MB、`seed_metadata_v004.parquet` 4.3 MB
  - `soma_shapes/`（含 `soma_base_rig` 的 usd/其他小件）、`LICENSE.md`、`README.md`
- 完整性校验：`tarfile` 全流读通过（无截断/CRC 错误），`files=142220  uncompressed=51.53 GB  2.9 min`；解压 `extracted=142346 10.6 min`
- **未下**：`soma_proportional.tar.gz` 45.47 GB、`soma_uniform.tar.gz` 45.19 GB（SOMA 原始/统一比例骨架的 BVH+NPZ），属重定向源数据，本批只需要 G1 侧

## 三、数据口径（与 MotionDecode / LAFAN1 可直接混用）

- BONES-SEED G1 CSV：**无表头，36 列 = root_joint(XYZ + QX QY QZ QW，7 列) + 29 关节角(rad)**；抽样 `g1/csv/210531/jump_and_land_heavy_001__A001_M.csv` 1,464 行 × 36 列
- 与 MotionDecode（36 列 CSV）、LAFAN1_Retargeting（36 列 CSV）**同一口径**，三者可直接拼训练集
- 语义侧：`seed_metadata_v004.csv` 提供分类/风格/表演信息与最多 6 种语言描述变体；`temporal_labels.jsonl` 提供时间轴分段标注 —— 这是 MotionDecode 没有的"动作-文本"对齐能力
- RoboMIND2.0 HDF5：`metadata.language_instruction` + 多视角图像 + `joint_actions`，是**操作任务**口径，不与上面三类动作数据混用

## 四、许可

| 数据 | 许可要点 |
|---|---|
| BONES-SEED | `bones-seed-license`（AIDVISORY / bones.studio）：仅限 **Academic User（非营利科研/教育）** 或 **年营收 < 100 万美元的合格初创**；禁止转售/再分发/上公开镜像、禁止再识别表演者、禁止做竞品数据集与"可替代原数据"的生成模型；论文与模型卡必须署名 *Motion Data by Bones Studio* |
| RoboMIND2.0 | 仓库 README 未显式标注许可（HF 卡无 license tag）；上游 RoboMIND 项目对外口径为 Apache-2.0，正式使用前请以官方页面/许可文件确认 |
| LAFAN1（上批） | Ubisoft 非商业研究/教育 |
| MotionDecode（11-18） | chingmu-terms，非商业原型，商用需书面许可 |

红线不变：**RoboParts 对外端点不得打包分发这些数据本体**，用途限于本地训练/评测；`bones-seed` 目录已放 `.gitignore(*)`，不进入 git。

## 五、遗留与下一步

1. `Humanoid-X/`：`USC-PSI-Lab/Humanoid-X`（14 文件 / 41.27 GB，G1 动作 + 文本，免 gating）在 HF 镜像侧被限速到 0.03 MB/s 后中止，仅留 1.48 GB 前缀（`human_pose.zip.part` 612 MB、`humanoid_keypoint.zip.part` 522 MB、`humanoid_action.zip.part` 367 MB）。**镜像恢复后可用 `hf-mirror-同步.py` 断点续传**。
2. BONES SOMA 两包（45.5 + 45.2 GB）与 `soma_shapes` 之外的 SOMA 资产未下；如需训练重定向管线再补。
3. RoboMIND2.0 子仓（单仓已见 286.75 GB，全量 TB 级）未展开，若后续要真机操作数据，建议按本体单独拉（`Tienkung` / `Ark-mobile` 优先）。
4. 本机 C 盘剩余 **160.9 GB**，已不足以容纳任一 TB 级子仓全集。

---
*登记完成。数据本体留在 `intel/datasets` 本地，未接入 RoboParts 端点、未提交 git。*
