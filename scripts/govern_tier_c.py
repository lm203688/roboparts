# -*- coding: utf-8 -*-
"""Schema 治理：为无溯源实体显式补齐 source_tier / confidence / quarantine / data_quality。

规则（保守、不编造来源）：
  source 为空  ->  source_tier="C", confidence=0.30,
                   confidence_basis="unsourced_legacy_import",
                   needs_provenance=True
  已有 tier 的实体不改动。
  quarantine / data_quality 缺失时补默认值（False / "ok"）。
同时重算 meta.provenance_coverage，并同步 api/*.json 与 data.js 中的同 id 记录。
"""
import json, sys, os, io, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIMARY = os.path.join(ROOT, "api", "entities.json")

PATCH = {
    "source_tier": "C",
    "confidence": 0.30,
    "confidence_basis": "unsourced_legacy_import",
    "needs_provenance": True,
}


def norm(e):
    """返回 (是否修改)"""
    changed = False
    if "quarantine" not in e:
        e["quarantine"] = False
        changed = True
    if not e.get("data_quality"):
        e["data_quality"] = "ok"
        changed = True
    if not e.get("source_tier"):
        for k, v in PATCH.items():
            e[k] = v
        changed = True
    return changed


def recompute_meta(d):
    ents = d["entities"]
    n = len(ents)
    tiers = {"A": 0, "B": 0, "C": 0}
    for e in ents:
        tiers[e.get("source_tier", "C")] = tiers.get(e.get("source_tier", "C"), 0) + 1
    src = sum(1 for e in ents if e.get("source"))
    conf = sum(1 for e in ents if isinstance(e.get("confidence"), (int, float)))
    lv = sum(1 for e in ents if e.get("last_verified"))
    ver = sum(1 for e in ents if e.get("verified"))
    clean = [e for e in ents if not e.get("quarantine")]
    cn = max(len(clean), 1)
    pc = d["meta"].setdefault("provenance_coverage", {})
    pc.update({
        "source_pct": round(src / n * 100, 2),
        "traceable_pct": round(tiers["A"] / n * 100, 2),
        "confidence_pct": round(conf / n * 100, 2),
        "last_verified_pct": round(lv / n * 100, 2),
        "tier_a_traceable": tiers["A"],
        "tier_b_attributable": tiers["B"],
        "tier_c_none": tiers["C"],
        "tier_labeled_pct": round(sum(tiers.values()) / n * 100, 2),
        "needs_provenance": sum(1 for e in ents if e.get("needs_provenance")),
        "verified_true": ver,
        "verified_false": n - ver,
        "verify_threshold": pc.get("verify_threshold", 0.6),
        "clean_set": {
            "total": len(clean),
            "source_pct": round(sum(1 for e in clean if e.get("source")) / cn * 100, 2),
            "traceable_pct": round(sum(1 for e in clean if e.get("source_tier") == "A") / cn * 100, 2),
            "confidence_pct": round(sum(1 for e in clean if isinstance(e.get("confidence"), (int, float))) / cn * 100, 2),
            "last_verified_pct": round(sum(1 for e in clean if e.get("last_verified")) / cn * 100, 2),
        },
        "tier_definition": {
            "A": "可点开复核的一手来源（官方规格书/标准文本/带链接厂商文档）",
            "B": "弱归因（厂商目录声明值、官网首页，无原始链接）",
            "C": "无溯源（历史导入，待补来源，confidence 上限 0.30）",
        },
        "note": "主指标看 traceable_pct（Tier A 可点开复核）；source_pct 含 Tier B 弱归因，仅作过程指标；Tier C 已显式标注，供 Agent 侧过滤",
    })
    d["meta"]["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    with io.open(PRIMARY, encoding="utf-8") as f:
        d = json.load(f)
    patched_ids = {}
    n_changed = 0
    for e in d["entities"]:
        if norm(e):
            n_changed += 1
        patched_ids[e["id"]] = {k: e[k] for k in
                                ("source_tier", "confidence", "confidence_basis",
                                 "quarantine", "data_quality") if k in e}
        if e.get("needs_provenance"):
            patched_ids[e["id"]]["needs_provenance"] = True
    recompute_meta(d)
    with io.open(PRIMARY, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print("entities.json  changed=%d  total=%d" % (n_changed, len(d["entities"])))
    print(json.dumps(d["meta"]["provenance_coverage"], ensure_ascii=False, indent=2))

    # 同步其它 api/*.json 中的同 id 记录
    api_dir = os.path.join(ROOT, "api")
    for fn in sorted(os.listdir(api_dir)):
        if not fn.endswith(".json") or fn == "entities.json":
            continue
        p = os.path.join(api_dir, fn)
        try:
            with io.open(p, encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue
        hits = [0]

        def walk(o):
            if isinstance(o, dict):
                i = o.get("id")
                if isinstance(i, str) and i in patched_ids and ("name" in o or "category" in o):
                    for k, v in patched_ids[i].items():
                        if o.get(k) != v:
                            o[k] = v
                            hits[0] += 1
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(obj)
        if hits[0]:
            with io.open(p, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            print("  synced %-28s fields=%d" % (fn, hits[0]))


if __name__ == "__main__":
    main()
