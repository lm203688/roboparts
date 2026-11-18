# Data License Matrix — RoboParts

> Effective Date: November 8, 2026  
> Last Updated: November 15, 2026

## License Matrix Overview

This document provides a comprehensive matrix of licenses for all data assets in the RoboParts project, ensuring clarity and compliance for users and contributors.

## Data Categories and Licenses

### 1. Core Dataset Files (`api/`)

| File Category | License | Attribution Required | Commercial Use | Derivatives | Notes |
|---------------|---------|---------------------|----------------|-------------|-------|
| `entities.json` | CC BY 4.0 | Yes | Yes | Yes | Primary dataset, 868 entities |
| `mechanical_interfaces.json` | CC BY 4.0 | Yes | Yes | Yes | Interface definitions and compatibility |
| `actuators.json` | CC BY 4.0 | Yes | Yes | Yes | Actuator specifications |
| `sensors.json` | CC BY 4.0 | Yes | Yes | Yes | Sensor specifications |
| `controllers.json` | CC BY 4.0 | Yes | Yes | Yes | Controller specifications |
| `structural_components.json` | CC BY 4.0 | Yes | Yes | Yes | Structural component data |
| `mechanical_joints.json` | CC BY 4.0 | Yes | Yes | Yes | Joint specifications |
| `grippers.json` | CC BY 4.0 | Yes | Yes | Yes | Gripper specifications |
| `wheels.json` | CC BY 4.0 | Yes | Yes | Yes | Wheel specifications |
| `other_all.json` | CC BY 4.0 | Yes | Yes | Yes | Miscellaneous components |
| `peripheral.json` | CC BY 4.0 | Yes | Yes | Yes | Peripheral devices |
| `power_systems.json` | CC BY 4.0 | Yes | Yes | Yes | Power system components |
| `communication_modules.json` | CC BY 4.0 | Yes | Yes | Yes | Communication hardware |
| `processing_units.json` | CC BY 4.0 | Yes | Yes | Yes | Computing hardware |
| `software_components.json` | CC BY 4.0 | Yes | Yes | Yes | Software-related components |
| `tooling.json` | CC BY 4.0 | Yes | Yes | Yes | Manufacturing and tooling |
| `materials.json` | CC BY 4.0 | Yes | Yes | Yes | Material specifications |
| `fasteners.json` | CC BY 4.0 | Yes | Yes | Yes | Fastener specifications |
| `connectors.json` | CC BY 4.0 | Yes | Yes | Yes | Connector specifications |
| `cables.json` | CC BY 4.0 | Yes | Yes | Yes | Cable specifications |
| `mounting_systems.json` | CC BY 4.0 | Yes | Yes | Yes | Mounting hardware |
| `mobility_systems.json` | CC BY 4.0 | Yes | Yes | Yes | Mobility components |
| `manipulation_systems.json` | CC BY 4.0 | Yes | Yes | Yes | Manipulation hardware |
| `perception_systems.json` | CC BY 4.0 | Yes | Yes | Yes | Sensing hardware |
| `control_systems.json` | CC BY 4.0 | Yes | Yes | Yes | Control hardware |
| `power_systems.json` | CC BY 4.0 | Yes | Yes | Yes | Power hardware |
| `structural_systems.json` | CC BY 4.0 | Yes | Yes | Yes | Structural hardware |
| `integration_systems.json` | CC BY 4.0 | Yes | Yes | Yes | Integration hardware |
| `specialized_systems.json` | CC BY 4.0 | Yes | Yes | Yes | Specialized components |
| `legacy_components.json` | CC BY 4.0 | Yes | Yes | Yes | Legacy/historical data |
| `experimental_components.json` | CC BY 4.0 | Yes | Yes | Yes | Experimental components |
| `emerging_components.json` | CC BY 4.0 | Yes | Yes | Yes | Emerging technology components |
| `custom_components.json` | CC BY 4.0 | Yes | Yes | Yes | Custom/fabricated components |
| `derived_components.json` | CC BY 4.0 | Yes | Yes | Yes | Derived/compatibility data |
| `compatibility_data.json` | CC BY 4.0 | Yes | Yes | Yes | Compatibility matrices |
| `assembly_guidelines.json` | CC BY 4.0 | Yes | Yes | Yes | Assembly instructions |
| `safety_data.json` | CC BY 4.0 | Yes | Yes | Yes | Safety specifications |
| `certification_data.json` | CC BY 4.0 | Yes | Yes | Yes | Certification information |
| `technical_specs.json` | CC BY 4.0 | Yes | Yes | Yes | Technical specifications |
| `performance_data.json` | CC BY 4.0 | Yes | Yes | Yes | Performance metrics |
| `market_data.json` | CC BY 4.0 | Yes | Yes | Yes | Market/availability data |

### 2. Derived and Computed Data

| File | License | Attribution Required | Notes |
|------|---------|---------------------|-------|
| `co_mount.json` | CC BY 4.0 | Yes | Mount compatibility data |
| `morphology_graph.json` | CC BY 4.0 | Yes | Morphology relationship graph |
| `evidence_valuation.json` | CC BY 4.0 | Yes | Evidence scoring data |
| `compose_semantics.json` | CC BY 4.0 | Yes | Semantic composition data |
| `gap_classification.json` | CC BY 4.0 | Yes | Gap classification data |
| `compatibility_matrix.json` | CC BY 4.0 | Yes | Compatibility matrix |
| `assembly_rules.json` | CC BY 4.0 | Yes | Assembly rule definitions |
| `validation_results.json` | CC BY 4.0 | Yes | Validation outcomes |
| `confidence_scores.json` | CC BY 4.0 | Yes | Confidence metrics |
| `tier_assessments.json` | CC BY 4.0 | Yes | Data tier evaluations |

### 3. Supporting Files

| File | License | Attribution Required | Notes |
|------|---------|---------------------|-------|
| `data.js` | CC BY 4.0 | Yes | JavaScript data loader |
| `agent-discovery.json` | CC BY 4.0 | Yes | Agent discovery data |
| `llms.txt` | CC BY 4.0 | Yes | LLM specification data |
| `skills_manifest.json` | CC BY 4.0 | Yes | Skills manifest |

### 4. Distribution Files

| Directory | License | Attribution Required | Notes |
|-----------|---------|---------------------|-------|
| `roboparts-dataset-github/` | CC BY 4.0 | Yes | GitHub distribution package |
| `public/api/` | CC BY 4.0 | Yes | Public API endpoints |

### 5. Third-Party Sources and Re-licensing Matrix

> 依据 `api/entities.json` 实测：868 实体中 409 个 distinct `source` 值。第三方来源分四类，再许可状态与处理方式如下（逐类登记，非笼统声明）。本矩阵随数据更新复核；新增来源先对照本表归类再入库。

| 来源类别 | 典型来源（实测计数） | 版权/许可性质 | RoboParts 再许可状态 | 处理方式 |
|----------|---------------------|----------------|----------------------|----------|
| ① 厂商官方公开规格值 | ATI (26)、Industrial Robotics Hub ISO 9409-1 lookup (50)、Festo、Molex、hebirobotics、NVIDIA/Qualcomm/Intel/AMD (各 6–14)、Tesla、ROBOTIS、T-Motor、Unitree、CubeMars、Harmonic Drive、Nabtesco、Schunk、Robotiq、OnRobot、Maxon、ShadowRobot、Schaeffler、agibot | 公开规格**事实数据**（规格/尺寸/参数），版权一般不覆盖事实本身；厂商手册/网站文本与商标另计 | ✅ 可再许可（CC BY 4.0 分发），但**保留来源署名 + 不得暗示厂商背书** | 已在 `source`/`source_url` 字段保留溯源；分发时附来源与厂商名；**禁**用厂商 logo 或"官方认证"措辞 |
| ② 标准/规范文本摘录 | ISO 9409-1 尺寸族、IEC 61158、USB、DisplayPort、3GPP、openstd.samr.gov.cn 国标 | **标准正文/表格有版权**，第三方转载需授权；推荐性/团体标准无法定公开例外 | ⚠️ **不直接再许可转载**；仅可引用标准号 + 自撰转述 | 数据里只存标准号/尺寸**事实值**，不存标准正文；`/iso-9409-flange` 等页面改自撰转述 + 引标准号/来源/授权状态（P2 项，见 A6） |
| ③ 研究/开源项目 | facebookresearch/project_superdex (**Apache-2.0**, 13)、Seeed Studio reBot-DevArm (**github, 4287 stars**, 4)、arxiv/robotics-transformer、各 research | 开源许可（Apache-2.0 等）需遵守；arXiv 论文内容需注明 | ✅ 可再许可，但**保留上游 LICENSE/NOTICE 与版权声明** | 保持 source 字段注明项目 + 许可；分发包内保留 NOTICE；Apache-2.0 需随附许可证文本 |
| ④ 聚合/媒体/搜索证据 | web aggregation (A/B/C 共 102)、google.com URL (76)、web_search_2026 (18)、eefocus、linkedin、wikipedia (6) | 聚合值与媒体报道**不可再许可给第三方**；仅可作证据引用 | ❌ **不再许可**；仅作引用/证据，不进入可再分发值 | 标记为 evidence-only（已有 `source_tier`/`confidence` 分级）；对外分发以①厂商值或①+③为准，④仅作置信度佐证 |

**登记规则（后续新增来源遵守）**：
1. 新来源先对号入座（①–④）；无法归类则暂挂"待核"，不直接分发。
2. ①③ 可再许可，② 仅引标准号，④ 仅作证据。
3. `source`/`source_url` 字段为溯源强制字段——缺 source 的实体不得进入对外分发（fail-closed）。
4. 本表由 `scripts/ci_gate.py` 资产分级一致性门（L0–L4）配套核验；第三方来源字段完整性由 `regen_derived.py --check` 校验。

## License Terms Summary

### CC BY 4.0 International (Creative Commons Attribution 4.0)

**You are free to:**
- Share — copy and redistribute the material in any medium or format
- Adapt — remix, transform, and build upon the material
- Use — for any purpose, including commercial purposes

**Under the following conditions:**
- Attribution — You must give appropriate credit, provide a link to the license, and indicate if changes were made. You may do so in any reasonable manner, but not in any way that suggests the licensor endorses you or your use.

**No additional restrictions:**
- You may not apply legal terms or technological measures that legally restrict others from doing anything the license permits.

## Attribution Requirements

### Standard Attribution Format
```
Data source: RoboParts (https://roboparts.cc), CC BY 4.0
```

### Detailed Attribution Format
```
RoboParts Dataset
Source: https://roboparts.cc
License: Creative Commons Attribution 4.0 International (CC BY 4.0)
Original source: https://github.com/roboparts/roboparts
```

### In Academic/Citation Contexts
```
RoboParts (2026). Robot Parts Compatibility Dataset. Version 2026.11.08. 
https://roboparts.cc, CC BY 4.0 International.
```

## Data Quality and Limitations

### Important Data Quality Notes
1. **Vendor-Stated Values**: All parameters are vendor public-stated values, not independently tested
2. **Coverage**: Mechanical interface coverage is limited (see `api/entities.json` for current percentage)
3. **Confidence**: Each data point includes confidence scores - judge credibility accordingly
4. **Tier System**: Data is tiered (A/B/C) based on source reliability and verification status

### Tier Definitions
- **Tier A**: Direct vendor data with high confidence (0.80-1.00)
- **Tier B**: Vendor data with moderate confidence (0.50-0.79)
- **Tier C**: Historical/imported data with low confidence (0.00-0.49)

### Usage Limitations
- **No Warranty**: Data is provided "as-is" without warranties
- **No Liability**: We are not liable for decisions based on this data
- **Verification**: Critical applications should verify data independently
- **Updates**: Data is updated periodically - check for latest versions

## Compliance and Legal Considerations

### Applicable Laws
- Personal Information Protection Law of China (PIPL)
- General Data Protection Regulation (GDPR)
- Copyright Law of the People's Republic of China
- International data protection standards

### Data Processing
- All data processing complies with applicable data protection laws
- User data is handled according to our Privacy Policy
- International data transfers comply with relevant regulations

### Enforcement
- License violations should be reported to legal@roboparts.cc
- We reserve the right to suspend access for serious violations
- Legal action may be taken for willful infringement

## Updates and Changes

### Version Control
- All license changes are tracked in git
- Version history is available in the repository
- Major changes will be announced with advance notice

### Notification of Changes
- Material changes will be communicated to users
- Changes will be reflected in the "Last Updated" date
- Continued use after changes constitutes acceptance

## Contact and Support

### License Inquiries
- Email: legal@roboparts.cc
- GitHub Issues: [License Discussions](https://github.com/roboparts/roboparts/issues)
- Documentation: [License Documentation](https://roboparts.cc/docs)

### Data Quality Inquiries
- Email: data@roboparts.cc
- GitHub Issues: [Data Quality Issues](https://github.com/roboparts/roboparts/issues)

### Technical Support
- Email: support@roboparts.cc
- Documentation: [API Documentation](https://roboparts.cc/api-docs)

---

*This license matrix is designed to provide clear guidance for users of RoboParts data assets. For specific legal advice, please consult with legal counsel familiar with your jurisdiction's requirements.*