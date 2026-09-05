# 机械接口声明贡献闭环设计（v1 · 2026-09-05）

> 目标：把 P0 缺口（418 applicable 实体中 declared=2 / partial=5 / **not_declared=411**）
> 从「AI 不能编造、只能等」转变为「结构化贡献流水线持续供数」。
> 模式借鉴 Tnkr 社区贡献闭环 + XLeRobot 四区域 BOM schema，但**必须加证据闸门**（Tnkr 自认质量管控是短板）。

## 1. 数据结构（对齐现有 schema，零迁移）

提交物 = 单实体 `mechanical_interface` 增量，字段与 `api/entities.json` 现行 schema 完全一致：

```json
{
  "entity_ref": "robotiq_2f85",            // 现有实体 id
  "status": "declared",                     // declared | partial
  "mount_type": "flange",                   // flange | shaft | bolt_pattern | ...
  "standard": ["ISO 9409-1-50-4-M6"],      // 官方标号；非标孔位写 PCD{n}({k}×M{t})
  "declared_note": "≤300 字，含耦合件前提等边界条件",
  "source": "《手册全名》§章节",
  "source_url": "https://...",              // 必填
  "confidence": 0.95
}
```

校验要点：`standard` 标号必须匹配 `^(ISO ?9409-1-)?A(\d+(\.\d+)?)-(\d+)-M(\d+)$` 或 `PCD\d+(\.\d+)?\(\d+×M\d+\)`；
A{n} 中 n=PCD（节圆直径），与 `build_negative_compat.py` 的 canonical 梯级一致；相邻 PCD 差 <2mm 判为可疑录入。

## 2. 证据分级（evidence_tier，决策声明能否公开为 declared）

| tier | 来源 | 处理 |
|---|---|---|
| T1 official | 厂商手册/官方 repo（AgibotTech、fourier-grx-n1、x-humanoid、openloong、Seeed、robotiq.com…） | 可 declared，confidence≥0.9 |
| T2 authorized | 授权分销商页、ISO/国标正文（白名单 host：ttbz、std.samr、openstd.samr、cssn、iso.org） | 可 declared，confidence≥0.8 |
| T3 community | 实测报告、拆机照片、论坛 | 只能 partial 或 `community_claim`（页面显著标注「社区声明·未官方证实」），不进兼容引擎现算 |
| T0 none | 无 source_url | **拒收**。这是「AI 不编造」纪律的机械化：没有证据=不存在 |

白名单落在 `scripts/decl_evidence_hosts.py`，与 L1.75 的 host 白名单机制同源。

## 3. 提交流水线（三阶段，Phase 1 零成本先行）

### Phase 1 — GitHub PR 流（本周可上线）
- 仓库根建 `declarations/` 目录 + `_template.json` + `README.md`（中英双语提交指引）。
- 贡献者 fork → 按 template 填 JSON → PR。
- CI（GitHub Actions）跑 `scripts/validate_declaration.py`：
  schema 校验、标号正则、source_url 可达性（HEAD 200）、host 白名单分级、与现有 `mechanical_interfaces.json` 冲突检测（改口径必须附分歧说明，格式对齐 Robotiq 2F-85 的 gap 写法）。
- 通过的 PR 由维护者 merge → `scripts/merge_declarations.py` 现算合并进 `entities.json`（**禁手改**，对齐真相源纪律）→ 下次 deploy 自动上线，verify_live_numbers 回探。

### Phase 2 — 站内表单（Phase 1 跑通后）
- `functions/api/declarations.js`：POST 提交（rate-limit + KV 暂存 pending 队列）。
- 表单智能预填：输入厂商+型号 → copilot（已带 grounding）抓取公开手册**只生成 draft**，用户逐字段确认（对齐既定决策：「厂商确认 AI 预填 draft 而非从零填」），source_url 必填不可由 AI 编。
- pro 会员（虎皮椒 `plan=pro`）可查看提交状态与署名展示。

### Phase 3 — 厂商门户
- 厂商认证（免费：域名邮箱验证 + 官网互链）→ T1 直通通道 + 实体卡「厂商认证声明」徽章。
- 商业点：认证厂商可挂购买链接（反向给平台带来供给侧动力）。

## 4. 闸门矩阵（防 Tnkr 式质量塌方）

| 提交者 | 可达最高 tier | 落库后展示 | 进兼容引擎现算 |
|---|---|---|---|
| 匿名 web 表单 | T3 | community_claim 标注 | 否 |
| GitHub 账号（≥1 已 merge PR） | T3 | community_claim | 否 |
| pro 会员 | T2 | partial | 仅 partial 参与保守裁决 |
| 认证厂商 | T1 | declared + 徽章 | 是 |

## 5. 对外口径纪律

- 声明率唯一对外口径仍由 `onboarding_block.facts()` 现算（declared+partial)/applicable，merge 脚本同步更新，
  禁止在文案里手写百分比（1.52% 口径随声明数自然演进，禁硬编码）。
- 首批「现摘果实」：§生态报告所列 6 个开源整机 repo（AgiBot X1/Fourier N1/OpenLoong/天工/XLeRobot/reBot Arm）
  的官方 BOM 属 T1——不依赖外部贡献者，由维护者直接走 `ingest_oss_bom.py` 批量入声库（`declarations/oss/`），
  这是 411 缺口最快的填法。

## 6. 与 Tnkr 的衔接位

- Tnkr 项目的 BOM 区支持外链供应商——我们的实体卡/兼容裁决 URL 可直接作为其 BOM 条目的 parts-supplier 引用；
- 反向：Tnkr 项目公开 BOM 页若开放 API，纳入 `ingest_oss_bom.py` 来源白名单（evidence_tier=T2，需项目方许可）。
