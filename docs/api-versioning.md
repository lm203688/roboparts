# API 版本化契约 · RoboParts

> 阶段 3-lite · 预埋结构（L3 Agent 原生）
> 审计依据：`docs/RoboParts-地基审计与硬骨头攻坚报告-20261016.md` §4
> **核心问题**：Agent 会缓存你的接口契约。字段一改，下游 Agent 静默失效。

## 1. 契约原则

1. **每次数据文件变更必须带版本头**（HTTP `X-Data-Version` + JSON `meta.schema_version`）
2. **语义版本**：`MAJOR.MINOR`
   - `MAJOR` 变更 = 破坏性（字段删除/类型变更/语义反转）
   - `MINOR` 变更 = 兼容（新增字段/枚举扩项/精度提升）
3. **弃用期**：字段标记弃用后至少保留 **1 个 MAJOR 版本** 才能删除
4. **不可静默**：所有破坏性变更必须 (a) 写进本文件，(b) 在响应头打 `X-Data-Deprecation` 提示

## 2. 版本头清单

### 2.1 HTTP 响应头（_headers + 后端 handler 注入）

```
X-Data-Version: 1.0          # 该响应数据的契约版本
X-Data-Updated-At: 2026-10-16T12:00:00Z  # 该数据的实际更新时间（ISO 8601）
X-Data-Deprecation:          # 可选，字段级弃用提示
  "legacy_field: sunset 2026-12-31; replacement: new_field"
```

### 2.2 JSON 内嵌版本（文件 self-describe）

所有对外 JSON 数据文件必须包含：

```json
{
  "meta": {
    "schema_version": "1.0",
    "updated": "2026-10-16T12:00:00Z",
    "total_entities": 868
  },
  ...
}
```

## 3. 版本策略表

| 数据文件 | 当前版本 | 契约文件 | 变更日志 |
|---|---|---|---|
| `api/entities.json` | 1.0 | `schemas/entities.schema.json` | §4.1 |
| `api/data.json` | 1.0（弃用中，见 D1） | 复用 entities schema | §4.1 |
| `api/compatibility.json` | 1.0 | 未定义（TODO P2） | §4.2 |
| `api/co_mount.json` | 1.0 | 未定义 | §4.2 |
| `api/research_progress.json` | 1.0 | 未定义 | §4.2 |
| `api/evidence_ledger.json` | 1.0 | 未定义 | §4.2 |
| 其他 `api/*.json` | 1.0 | 未定义（按优先级补） | §4.2 |

## 4. 变更日志

### 4.1 entities.json

- **v1.0 (2026-10-16)**：
  - 时间戳收敛为 `meta.updated`（顶层 `updated` / `last_updated` 作向后兼容别名，值必须相等）
  - 新增 `meta.schema_version` 字段
  - `confidence_tier` 五档枚举化：`verified / observed / derived / inferred / unverified`（原为无约束浮点）
  - `quarantine=true` 时 `data_quality` 必须以 `quarantined_` 开头（D5 铁律）
  - 无 `source` 且无 `sources` 的实体必须 `quarantine=true`

### 4.2 其他数据文件

（待补：每个文件建 schema 后在此登记）

## 5. 弃用流程

1. 在 schema 的 `description` 字段加 `[DEPRECATED since vX.Y, sunset vA.B]`
2. 在 HTTP 响应头打 `X-Data-Deprecation: "field_name: sunset vA.B"`
3. 在响应头里 `X-Data-Version` 保持当前版本（不主动升 MAJOR，直到 sunset）
4. 到期后：删字段 → 升 MAJOR → 本文件记变更 → 通知下游

**当前弃用清单**：
- `api/data.json`：D1 定性为"继续维护但同步一致"，不主动弃用；长期建议收敛到 `entities.json`
- `entities.json.updated` / `entities.json.last_updated`：顶层字段（元数据在 `meta.updated`）；1 个 MAJOR 版本后删除

## 6. Agent 集成指南

给下游 Agent 的建议：

1. **首次消费**：检查 `X-Data-Version`，若高于自己的 `supported_version`，做兼容降级
2. **缓存策略**：以 `X-Data-Version` + `X-Data-Updated-At` 作缓存 key，不要只用 URL
3. **降级路径**：
   - `confidence_tier=verified` → 高可信判定
   - `confidence_tier=derived/inferred` → 需要交叉验证
   - `confidence_tier=unverified` → 不参与默认判定
4. **弃用响应**：检测到 `X-Data-Deprecation` 时记录日志，不阻塞业务

## 7. 一致性闸门

`scripts/ci_gate.py` 中的以下 gate 强制契约落地：

- `gate_d1_datajson_consistency`：`data.json` 与 `entities.json` 数字一致
- `gate_d2a_timestamp_consistency`：`entities.json` 三个时间戳镜像
- `gate_d5_no_source_policy`：无 `source` 实体必须 `quarantine`
- `产物新鲜度检查`：上游 mtime 早于产物 ⇒ FAIL

**TODO P2**：加 `gate_api_version_header` 断言所有对外 JSON 都有 `meta.schema_version` 且匹配 `schemas/*.schema.json` 的 `$id`。
