"""RoboParts 实体 schema 契约（mHarmony 式带类型校验）。

借鉴 Perceptron Isaac 0.5 开源的 mHarmony：把异构经验校验为一致的带类型格式，
在「摄取 → 归一化 → 富集 → 生成 manifest」全链路强制同一份 schema。
本模块是 RoboParts 实体层的最小契约：任何实体缺核心字段或 status 枚举越界，
都在回归闸门里判红（而非像历史 PROTO-010 / XFA-017 那样被静默丢弃）。

- SCHEMA_VERSION 进入发布指纹，schema 演进可追踪。
- CORE_REQUIRED 经 api/entities.json 全量核验 100% 存在，不会误报。
- MI_STATUS_ENUM 与 onboarding_block.facts() 白名单一致。
- mount_type 枚举**不在本文件硬编码**：从 api/mechanical_interfaces.json 的
  mount_type_enum 节点现读（单一真相源），避免出现第二份会失修的副本。
  该节点由 scripts/govern_mount_type.py 从权威 mounting_taxonomy 派生生成。
  历史缺陷（20260831 治理）：全库曾有 12 种 mount_type 写法，其中
  'flange_mount'(3 条，含全部 2 条 declared) / 'N/A'(2) / 'research_prototype'(1)
  越出权威枚举，根因即「无单一源 + 无闸门」，各写入脚本各写各的。
"""

SCHEMA_VERSION = "1.1.0"

# 全量核验 100% 存在的核心身份字段（id/rp_id/entity_kind/name/category）
CORE_REQUIRED = ["id", "rp_id", "entity_kind", "name", "category"]

# mechanical_interface.status 合法枚举（与 facts() 白名单一致）
MI_STATUS_ENUM = {"declared", "partial", "not_declared", "n_a"}


def load_mount_type_keys(registry_path=None):
    """从 registry 现读 mount_type 合法枚举。

    返回 (keys:set, err:str|None)。registry 缺节点时返回 err，由调用方判红 ——
    不静默放行（静默放行等于闸门形同虚设）。
    """
    import json
    import os

    if registry_path is None:
        registry_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "api", "mechanical_interfaces.json")
    try:
        with open(registry_path, encoding="utf-8") as f:
            reg = json.load(f)
    except Exception as exc:  # noqa: BLE001
        return set(), f"读取 mechanical_interfaces.json 失败：{exc}"
    node = reg.get("mount_type_enum")
    if not isinstance(node, dict):
        return set(), ("api/mechanical_interfaces.json 缺 mount_type_enum 节点"
                       "（补：python scripts/govern_mount_type.py）")
    keys = set()
    for group in ("standard_derived", "roboparts_extension"):
        for v in node.get(group, {}).get("values", []) or []:
            if v.get("key"):
                keys.add(v["key"])
    if not keys:
        return set(), "mount_type_enum 节点为空，无合法取值"
    return keys, None


def validate(entities, mount_type_keys=None):
    """返回违规字符串列表；空列表表示契约满足。

    mount_type_keys 为 None 时自动从 registry 现读。
    """
    violations = []
    mt_err = None
    if mount_type_keys is None:
        mount_type_keys, mt_err = load_mount_type_keys()
    if mt_err:
        violations.append(f"<registry>: {mt_err}")

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
            mt = mi.get("mount_type")
            # null 合法（未采集/不适用，语义由 status 承载）；字符串必须在枚举内
            if mt is not None and mount_type_keys and mt not in mount_type_keys:
                violations.append(
                    f"{eid}: mechanical_interface.mount_type 越界 {mt!r}"
                    f"（合法值见 api/mechanical_interfaces.json#mount_type_enum）")
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
    keys, err = load_mount_type_keys()
    v = validate(ents)
    print(f"schema_contract v{SCHEMA_VERSION}: 校验 {len(ents)} 实体"
          f"｜mount_type 合法枚举 {len(keys)} 个"
          f"{'（registry 异常：' + err + '）' if err else '（源：registry#mount_type_enum）'}")
    if v:
        print(f"❌ {len(v)} 条契约违规：")
        for x in v[:20]:
            print("  -", x)
        sys.exit(1)
    print("✅ 全部满足实体契约")
    sys.exit(0)


if __name__ == "__main__":
    main()
