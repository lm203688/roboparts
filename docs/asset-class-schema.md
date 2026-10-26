# Asset Class Schema — RoboParts 资产分级

**版本**：v1（2026-10-26）  
**适用范围**：URDF/MJCF/3D 模型等所有可下载、可导入仿真器的资产。  
**权威**：所有 `/api/urdf/download` 响应头 `X-RoboParts-AssetClass` 与 XML/JSON 内的 `assetClass` 字段必须与本表一致。

---

## 为什么要有分级

RoboParts 曾经在所有 URDF/MJCF 注释里写"仿真就绪（MuJoCo / Isaac Sim）"。这个说法：

- **技术上不精确**：仿真"就绪"没有可验证的定义。是 XML 能加载？能跑一步物理？能收敛不爆炸？能真机部署？
- **商业上误导**：客户以为拿到 L4 级资产，实际是 L1，用于产线部署必然出问题，责任无法界定。
- **诚实上有悖**：RoboParts 的立身之本是"能/不能/不知道"三态。宣称"就绪"是把"不知道"包装成"能"。

分级把"能到什么程度"变成可查询、可对比、可追责的公开字段。

---

## 五个等级

| 等级 | 名称 | 定义 | 可做什么 | 不能做什么 | 数据要求 |
|------|------|------|----------|------------|----------|
| **L0** | 元数据/描述 | 只有规格描述（品牌、型号、自由度、负载），无几何 | 选型对比、BOM 清单 | 任何 3D 显示、任何仿真 | 实体条目 |
| **L1** | 参数化骨架 | 几何由程序按关节数与 robot_type 拼接（box/cylinder），物理参数按预设表估算 | 结构演示、脚本级仿真、教学 | 碰撞敏感任务、真机部署、力学分析 | 骨架生成器 + 物理预设表 |
| **L2** | 骨架 + 厂商声明物理 | 几何仍为骨架，但质量/惯量/负载来自厂商 datasheet（可溯源） | 动力学仿真、控制算法验证 | 真机部署、精度要求高的运动规划 | L1 + 厂商 datasheet URL |
| **L3** | 骨架 + 实测物理 | 骨架几何 + 第三方实测复现的物理参数（有实验记录） | 高精度动力学、部分真机部署 | 结构分析、碰撞检测 | L2 + 实测记录 |
| **L4** | 真实 CAD / 全量实测 | STEP/IGES 原始 CAD + 全量物理参数实测 | 全部用途，可交付产线 | — | CAD 文件 + 实测报告 |

**当前所有 `/api/urdf/download` 导出物均为 L1**。没有 L2 及以上资产。这是诚实边界，不是功能缺失。

---

## 判定准则（严格）

**判 L1 而非更高，除非满足以下全部条件**：

1. 几何来源非程序生成（必须是 STEP/IGES/STL 文件或至少 mesh 化 CAD）
2. 质量/惯量/摩擦系数有明确出处（datasheet 页码 + URL，或实测记录 ID）
3. 已在至少一个主流仿真器（MuJoCo / Isaac Sim / Gazebo）跑过 1 分钟稳定仿真
4. 记录在 `api/asset_provenance.json`，可审计

**任一条件不满足 → 必须降到 L1**。宁可低标，不可虚标。

---

## 响应头契约

所有资产下载响应必须包含：

| Header | 值示例 | 说明 |
|--------|--------|------|
| `X-RoboParts-AssetClass` | `L1` | 等级代号（L0/L1/L2/L3/L4） |
| `X-RoboParts-AssetClass-Label` | `Parametric skeleton (not real CAD, physics estimated)` | 人类可读说明 |
| `X-RoboParts-AssetClass-Schema` | `https://roboparts.cc/docs/asset-class-schema.md` | 本文件 |

客户端（含 AI Agent）应程序化读取 `X-RoboParts-AssetClass`，不要 grep XML 注释。

---

## 升级到 L2+ 的路径

用户希望为某个机型拿到 L2 及以上资产，流程：

1. 在 `/spec-declare` 提交实体信息
2. 附上厂商 datasheet URL（可公开访问）
3. RoboParts 团队核验 URL 可访问 + 字段与 URL 内容一致
4. 升级 `assetProvenance` 记录 + 在下次导出时打上 L2 标签

**当前（2026-10-26）无任何实体达到 L2**。这一栏是承诺，不是功能。

---

## 参考

- P0-12 in docs/RoboParts-全面提升与前沿演进报告-20261026.md §资产表
- 项目纪律："能/不能/不知道"—— L1 就是"能加载能跑一步，不能真机部署，不知道具体碰撞行为"的三态展开
