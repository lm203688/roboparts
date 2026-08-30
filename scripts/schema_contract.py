"""RoboParts 实体 schema 契约（mHarmony 式带类型校验）。

借鉴 Perceptron Isaac 0.5 开源的 mHarmony：把异构经验校验为一致的带类型格式，
在「摄取 → 归一化 → 富集 → 生成 manifest」全链路强制同一份 schema。
本模块是 RoboParts 实体层的最小契约：任何实体缺核心字段或 status 枚举越界，
都在回归闸门里判红（而非像历史 PROTO-010 / XFA-017 那样被静默丢弃）。

- SCHEMA_VERSION 进入发布指纹，schema 演进可追踪。
- CORE_REQUIRED 经 api/entities.json 全量核验 100% 存在，不会误报。
- MI_STATUS_ENUM 与 onboarding_block.facts() 白名单一致。
"""

SCHEMA_VERSION = "1.0.0"

# 全量核验 100% 存在的核心身份字段（id/rp_id/entity_kind/name/category）
CORE_REQUIRED = ["id", "rp_id", "entity_kind", "name", "category"]

# mechanical_interface.status 合法枚举（与 facts() 白名单一致）
MI_STATUS_ENUM = {"declared", "partial", "not_declared", "n_a"}


def validate(entities):
    """返回违规字符串列表；空列表表示契约满足。"""
    violations = []
    for i, e in enumerate(entities):
        eid = e.get("rp_id") or e.get("id") or f"#{i}"
        for k in CORE_REQUIRED:
            if not e.get(k):
                violations.append(f"{eid}: 缺核心字段 {k}")
        mi = e.get("mechanical_interface")
        if isinstance(mi, dict):
            st = mi.get("status")
            if st not in MI_STATUS_ENUM:
                violations.append(f"{eid}: mechanical_interface.status 越界 {st!r}")
        elif mi is not None:
            violations.append(f"{eid}: mechanical_interface 非 dict")
    return violations


def main():
    import json
    import os
    import sys

    p = os.path.join(os.path.dirname(__file__), "..", "api", "entities.json")
    d = json.load(open(p, encoding="utf-8"))
    ents = d.get("entities", [])
    v = validate(ents)
    print(f"schema_contract v{SCHEMA_VERSION}: 校验 {len(ents)} 实体")
    if v:
        print(f"❌ {len(v)} 条契约违规：")
        for x in v[:20]:
            print("  -", x)
        sys.exit(1)
    print("✅ 全部满足实体契约")
    sys.exit(0)


if __name__ == "__main__":
    main()
