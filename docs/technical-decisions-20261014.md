# RoboParts 技术决策登记册 · 2026-10-14

> **性质**：留痕决策文档。目的不是「证明决策正确」，而是把「判断依据、备选方案、
> 最终选择、验证判据」写下来，让下一个版本能查到为什么这样决定，也能推翻它。
> **锚点原则**：只信仓内产物 + 一手 curl 数据，不采信「业界普遍观点」。
> **验证机制**：`scripts/ci_gate.py` 里的 `gate_world_model_exclusion` 闸门会
> 在每次 CI 上核对本文档的关键锚点，避免留痕文档被静默篡改。

---

## TDD-2026-01 · 世界模型适配性判断（H-JEPA / Odyssey-3 / Cosmos 3）

- **决策日期**：2026-10-14
- **状态**：已定案
- **关联 CI 闸门**：`gate_world_model_exclusion`（第 47 号闸门）
- **关联报告**：`docs/RoboParts-下一阶段前沿提升方案报告-四维深化-20261013.md`
- **候选模型**（截至 2026-10-14）：
  - **H-JEPA**：Meta/AMI（Yann LeCun 团队）分层 JEPA 世界模型，代码+权重开源，Visual AntMaze 三层成功率 73%
  - **Odyssey-3**：Odyssey 公司 14B 参数自回归扩散 Transformer，仅 research preview，权重未开源
  - **Cosmos 3**：NVIDIA MoT 架构世界基础模型，4B / 16B / 64B，OpenMDW-1.1 许可

### 结论

**不引入 H-JEPA / Odyssey-3 / Cosmos 3 到 RoboParts 核心链路。**

### 理由（4 条硬指标）

| # | 判据 | 世界模型要求 | RoboParts 现状 | 是否冲突 |
|---|---|---|---|---|
| 1 | **范式** | 生成式 / 预测式（预测下一帧、动作流） | 规则确定性（符号 / 规则组合校验） | ✅ 冲突 |
| 2 | **输入** | 视觉观测序列 + 动作序列 | 结构化 attributes（868 entities × 20 categories） | ✅ 冲突 |
| 3 | **可追溯** | 黑盒推理输出 | ISO 22166-1 / GB/T 20255807-T-604 明确要求每条判定可回溯到证据来源 | ✅ 冲突 |
| 4 | **部署** | VRAM 数十 GB（Cosmos Nano 16B / Odyssey 14B） | Cloudflare Pages 静态部署 + 20s / 30% 冷启动指标 | ✅ 冲突 |

四条判据同时冲突 → 核心链路不引入是自然结论，不是「业界普遍观点」的复述。

### 替代路径（同样能实现「世界模型带来的价值」）

世界模型的间接价值 = **更好的训练数据**。对 RoboParts 而言，"更好的数据" 是**更多高质量 entities 和 evidence**，而不是视频。

- **B 阶段（推荐）**：VLM 证据抽取。用多模态 LLM 从厂商 PDF / 手册页抽取结构化属性，扩充 868 entities。
  - 输出走现有 4 维 schema
  - 抽取结果必须过 `gate_cross_dimensional_signals`（跨维信号一致性）
  - confidence < 0.7 的条目进 pending，不进主库
- **C 阶段（可选）**：规则合成测试对。基于 MDV 排序合成更多组合测试对，比例 ≤ 20%（避免污染 fitness 计算）。

**为什么不直接生成新 entities**：违反 `docs/verification-antipatterns-2026-2026.md` 里的 AP-05（不可追溯的合成数据）。

### Cosmos 3 的唯一实际用途（非核心）

若阶段 B 走 VLM 抽取后，需要**产品照片→属性识别**的能力，可评估 Cosmos 3 Nano 的 **API 调用**（build.nvidia.com）——注意：

- OpenMDW-1.1 许可对商业部署有约束，需单独核对
- 引入 NVIDIA 生态依赖，与"vendor-neutral"定位有张力
- 只走 API 调用，**不落地权重**

### 验证判据（可被 CI 核对）

1. **本文档存在**：路径 `docs/technical-decisions-20261014.md`，包含 `TDD-2026-01` 与三个模型名。
2. **依赖声明面无世界模型库**：`requirements-dev.txt` 不含 `torch` / `transformers` / `diffusers` / `accelerate` / `openvla` / `cosmos` / `odyssey` / `jepa`。
3. **定位声明面无具体模型名**：`agent-discovery.json` / `llms.txt` / `positioning_contract.py` / `scripts/gen_public_manifests.py` / `scripts/gen_agent_card.mjs` 五处定位声明面不出现 `H-JEPA` / `Odyssey-3` / `Cosmos 3` / `Cosmos3`。
4. **允许列表**：`world model` / `world models` 作为**数据分类类别词**可在 README 数据分类段合法出现（描述 `robot_ai_models` 生态实体目录，共 46 条），不构成引擎依赖声明。

### 边界澄清

- **不禁止**在 `api/robot_ai_models.json` / `api/data.json` / `api/entities.json` 里追踪这些模型作为**生态实体**（竞品监测的一部分，与本项目引擎无关）。
- **不禁止**在 `docs/RoboParts-*.md` 报告里引用这些模型作为**行业对标锚点**（研究背景的一部分，与本项目引擎无关）。
- **不禁止**在 `articles/` / `content/` 里做**技术评论文章**（对外发表的内容，与本项目引擎无关）。

### 可推翻条件

如果未来出现同时满足以下三条的世界模型，可重新评估本决策：

1. **确定性推理**：同一 inputs 输出完全一致（不是「8 次采样选最好」的 best-of-N 语义）
2. **可解释机制**：能给出"为什么判定为不兼容"的因果链（对齐 ISO 22166-1 证据回溯要求）
3. **静态部署兼容**：能在无 GPU / VRAM 数十 MB 级 / 冷启动 < 5s 的部署形态下运行

截至 2026-10-14，公开信息里没有任何世界模型同时满足这三条。Odyssey-3 的 Physics-IQ 66.1 分是 best-of-8 采样产物，Cosmos 3 的开源权重仍需 NVIDIA Blackwell 硬件，H-JEPA 的分层设计解决的是视觉规划而非规则推理。

### 决策人

- 决策执行：项目自动化管线（scripts/ci_gate.py 第 47 号闸门）
- 决策审阅：项目维护者
- 最后审阅日期：2026-10-14

---

## 决策登记索引

| 编号 | 主题 | 日期 | 关联闸门 |
|---|---|---|---|
| TDD-2026-01 | 世界模型适配性判断 | 2026-10-14 | `gate_world_model_exclusion` |

> 新增决策按时间倒序插入本索引，编号连续不跳号。已废弃的决策不要删除，标注「已废弃 · YYYY-MM-DD · 由 TDD-YYYY-NN 取代」保留在文档内以维持历史可追溯。
