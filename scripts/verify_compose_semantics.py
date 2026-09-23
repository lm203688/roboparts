#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_compose_semantics — 组合语义产物闸门。

审计模式（默认）：结构 + 不变量 + 与「graph 现算」逐键对账 + 判例复验。
--self-test：合成图上的阳性/阴性/变异/守卫自证（只测绿路径的闸门等于没闸门）。

判据源：scripts/compose_engine.py（引擎常量与判定过程）。
产物：api/compose_semantics.json。
"""
from __future__ import annotations

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import compose_engine as eng  # noqa: E402
from compose_engine import (  # noqa: E402
    AXES,
    ENGINE_VERSION,
    OVERALL_VERDICTS,
    ROLES,
    RULE_TABLE,
    compose,
    eval_all_pairs,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_PATH = os.path.join(ROOT, "api", "morphology_graph.json")
DOC_PATH = os.path.join(ROOT, "api", "compose_semantics.json")

# 与 build_compose_semantics.EXAMPLES_PER_CLASS 保持一致（builder 侧已有算术守卫）
EXAMPLES_PER_CLASS = 2

# 注入器受管区 / 时间戳：比对时剥离
VOLATILE_META_KEYS = ("generated_at", "access")


def strip_volatile(doc):
    d = copy.deepcopy(doc)
    meta = d.get("meta") or {}
    for k in VOLATILE_META_KEYS:
        meta.pop(k, None)
    return d


def check_doc(doc, graph) -> list:
    """返回错误列表；空列表 = 通过。"""
    errs = []
    meta = doc.get("meta") or {}

    # ---- 结构 ----
    if meta.get("schema") != "compose_semantics/v1":
        errs.append(f"meta.schema={meta.get('schema')!r} != compose_semantics/v1")
    if meta.get("engine_version") != ENGINE_VERSION:
        errs.append(f"meta.engine_version={meta.get('engine_version')!r} != {ENGINE_VERSION}")
    if meta.get("truth_sources") != ["api/morphology_graph.json", "scripts/compose_engine.py"]:
        errs.append("meta.truth_sources 与判据源不符")
    if not meta.get("honest_limits"):
        errs.append("meta.honest_limits 缺失（诚实边界必须显式声明）")

    # ---- 规则表 / 词表与引擎同源 ----
    if doc.get("rule_table") != RULE_TABLE:
        errs.append("rule_table 与 compose_engine.RULE_TABLE 不一致")
    v = doc.get("verdicts") or {}
    if v.get("overall") != list(OVERALL_VERDICTS):
        errs.append("verdicts.overall 与引擎常量不一致")
    if "precedence" not in v:
        errs.append("verdicts.precedence 缺失")
    if v.get("axis") != sorted(eng.AXIS_VERDICTS):
        errs.append("verdicts.axis 与引擎常量不一致")

    # ---- roles node_count 现算 ----
    roles = doc.get("roles") or {}
    cat_counts = {}
    for n in graph.get("nodes") or []:
        c = n.get("category")
        if c:
            cat_counts[c] = cat_counts.get(c, 0) + 1
    if set(roles) != set(ROLES):
        errs.append(f"roles 键集 {sorted(roles)} != 引擎 {sorted(ROLES)}")
    for role, spec in ROLES.items():
        r = roles.get(role) or {}
        if r.get("categories") != spec["categories"]:
            errs.append(f"roles.{role}.categories 与引擎不一致")
        expect = sum(cat_counts.get(c, 0) for c in spec["categories"])
        if r.get("node_count") != expect:
            errs.append(f"roles.{role}.node_count={r.get('node_count')} != 现算 {expect}")

    # ---- 聚合：与 graph 现算逐键对账（判例 id 口径与 builder 同参数）----
    agg = doc.get("aggregates") or {}
    fresh = eval_all_pairs(graph, examples_per_class=EXAMPLES_PER_CLASS)
    for key in ("pairs_evaluated", "overall_counts", "axis_marginals",
                "mech_elec_cross", "example_ids"):
        if agg.get(key) != fresh.get(key):
            errs.append(f"aggregates.{key} 与现算不符")

    total = agg.get("pairs_evaluated", 0)
    if sum((agg.get("overall_counts") or {}).values()) != total:
        errs.append("overall_counts 之和不等于 pairs_evaluated")
    for ax in AXES:
        if sum((agg.get("axis_marginals") or {}).get(ax, {}).values()) != total:
            errs.append(f"axis_marginals[{ax}] 之和不等于 pairs_evaluated")

    # ---- fail-closed 不变量：无 effective SIG 端口 ⇒ composed 必为 0 ----
    has_sig = any(
        p["type"] == eng.SIG_OUTPUT or p["type"] == eng.SIG_INPUT
        for n in graph.get("nodes") or []
        for p in (n.get("ports") or [])
        if p.get("status") in eng.EFFECTIVE_STATUS
    )
    composed = (agg.get("overall_counts") or {}).get("composed", 0)
    if not has_sig and composed != 0:
        errs.append(f"不变量违背：全库无已声明 SIG 通道但 composed={composed} != 0")

    # ---- 判例复验：引擎重算逐键全等 + 前缀对账 ----
    nodes = {n["id"]: n for n in graph.get("nodes") or []}
    examples = doc.get("examples") or []
    seen = {v: 0 for v in OVERALL_VERDICTS}
    for ex in examples:
        a, b = ex.get("node_a"), ex.get("node_b")
        if a not in nodes or b not in nodes:
            errs.append(f"判例引用未知节点 {a}×{b}")
            continue
        fresh_ex = compose(nodes[a], nodes[b], graph)
        if strip_volatile(ex) != strip_volatile(fresh_ex):
            errs.append(f"判例 {a}×{b} 与引擎重算不符")
        if ex.get("overall") in seen:
            seen[ex["overall"]] += 1
    # example_ids 与判例一一对应（前 N）
    for cls, id_pairs in (fresh.get("example_ids") or {}).items():
        want = [(a, b) for a, b in id_pairs[:2]]
        got = [(ex.get("node_a"), ex.get("node_b")) for ex in examples
               if ex.get("overall") == cls]
        if got != want:
            errs.append(f"判例类 {cls} 与 example_ids 前缀不一致: {got} != {want}")
    # 每个非零类别至少 1 判例
    for cls, cnt in (agg.get("overall_counts") or {}).items():
        if cnt > 0 and seen.get(cls, 0) < 1:
            errs.append(f"类别 {cls} 计数 {cnt} > 0 但无判例")
    return errs


# ---------------------------------------------------------------------------
# 自证（合成图：阳性 / 阴性 / 变异 / 守卫）
# ---------------------------------------------------------------------------

def _synth_graph():
    """三类型合成图：ISO_A / ISO_B（incompatible 登记）+ PROP_X（专有，靠 reflexivity）。"""
    tc = [
        {"a": "MECH:ISO_A", "b": "MECH:ISO_A", "axis": "mechanical",
         "verdict": "identity", "reason": "同标号"},
        {"a": "MECH:ISO_A", "b": "MECH:ISO_B", "axis": "mechanical",
         "verdict": "incompatible", "reason": "孔数不同"},
        {"a": "ELEC:CONN1", "b": "ELEC:CONN1", "axis": "electrical",
         "verdict": "identity", "reason": "同连接器"},
    ]
    def node(nid, ports):
        return {"id": nid, "kind": "component", "entity_kind": "component",
                "category": "actuators", "composable": True, "ports": ports}
    return {
        "nodes": [
            node("NA_FULL", [
                {"type": "MECH:ISO_A", "status": "declared"},
                {"type": "ELEC:CONN1", "status": "declared"},
                {"type": "SIG:OUTPUT_SPIKE", "status": "declared"},
            ]),
            node("NB_FULL", [
                {"type": "MECH:ISO_A", "status": "declared"},
                {"type": "ELEC:CONN1", "status": "declared"},
                {"type": "SIG:INPUT_SENSORY", "status": "declared"},
            ]),
            node("NC_INCOMPAT", [
                {"type": "MECH:ISO_B", "status": "declared"},
                {"type": "ELEC:CONN1", "status": "declared"},
            ]),
            node("ND_PROP", [
                {"type": "MECH:PROP_X", "status": "partial"},
                {"type": "ELEC:CONN1", "status": "declared"},
            ]),
            node("NE_UNKNOWN", [
                {"type": "MECH:UNKNOWN", "status": "not_declared"},
                {"type": "ELEC:UNKNOWN", "status": "not_declared"},
            ]),
        ],
        "type_compat": tc,
    }


def self_test() -> int:
    failures = []
    g = _synth_graph()
    nodes = {n["id"]: n for n in g["nodes"]}

    def expect(name, cond, detail=""):
        if cond:
            print(f"  ✅ {name}")
        else:
            failures.append(name)
            print(f"  ❌ {name} {detail}")

    # ---- 引擎级：阳性 ----
    r = compose(nodes["NA_FULL"], nodes["NB_FULL"], g)
    expect("阳性·全声明三轴 ⇒ composed", r["overall"] == "composed", str(r["overall"]))
    expect("阳性·信号轴 sensory_link",
           r["axes"]["signal"]["verdict"] == "compatible"
           and "a_output_to_b_input" in r["axes"]["signal"]["sensory_links"])

    # 轴级 adapter（overall 仍 composed，因其余轴 compatible）——补 adapter 登记图
    g2 = copy.deepcopy(g)
    g2["type_compat"].append(
        {"a": "MECH:ISO_A", "b": "MECH:ISO_B", "axis": "mechanical",
         "verdict": "adapter_required", "reason": "转接盘"})
    r2 = compose(nodes["NA_FULL"], nodes["NC_INCOMPAT"], g2)
    expect("阳性·adapter_required ⇒ compatible_via_adapter",
           r2["axes"]["mechanical"]["verdict"] == "compatible_via_adapter",
           str(r2["axes"]["mechanical"]["verdict"]))

    # reflexivity：同专有型 ⇒ identity
    r3 = compose(nodes["ND_PROP"], nodes["ND_PROP"], g)
    expect("公理·reflexivity 同专有型 ⇒ identity",
           r3["axes"]["mechanical"]["verdict"] == "compatible"
           and r3["axes"]["mechanical"]["best_pair"]["pair_verdict"] == "identity")

    # best-pair：identity 压过 incompatible
    r4 = compose(nodes["NA_FULL"], nodes["NA_FULL"], g)
    expect("best-pair·自配对 identity", r4["axes"]["mechanical"]["verdict"] == "compatible")

    # ---- 引擎级：阴性 / fail-closed ----
    r5 = compose(nodes["NA_FULL"], nodes["NC_INCOMPAT"], g)
    expect("阴性·incompatible ⇒ type_error", r5["overall"] == "type_error")
    r6 = compose(nodes["NA_FULL"], nodes["NE_UNKNOWN"], g)
    expect("fail-closed·UNKNOWN 枢纽 ⇒ unknown 非 composed",
           r6["overall"] == "unknown"
           and r6["axes"]["mechanical"]["verdict"] == "unknown")
    r7 = compose(nodes["NE_UNKNOWN"], nodes["NE_UNKNOWN"], g)
    expect("fail-closed·双侧 UNKNOWN 仍 unknown", r7["overall"] == "unknown")
    # 缺键：ISO_B × PROP_X 未登记 ⇒ unknown
    r8 = compose(nodes["NC_INCOMPAT"], nodes["ND_PROP"], g)
    expect("fail-closed·缺键不猜 ⇒ unknown",
           r8["axes"]["mechanical"]["verdict"] == "unknown")
    # 混合 unknown+incompatible 候选对 ⇒ 保守 unknown（best-pair 取最优非零证据）
    g3 = copy.deepcopy(g)
    nf_mix = {"id": "NF_MIX", "kind": "component", "entity_kind": "component",
              "category": "actuators", "composable": True, "ports": [
                  {"type": "MECH:ISO_B", "status": "declared"},
                  {"type": "MECH:PROP_X", "status": "partial"}]}
    g3["nodes"].append(nf_mix)
    r9 = compose(nodes["NA_FULL"], nf_mix, g3)
    expect("best-pair·unknown 候选压过 incompatible ⇒ unknown",
           r9["axes"]["mechanical"]["verdict"] == "unknown",
           str(r9["axes"]["mechanical"]["verdict"]))
    # REWARD 不参与正向（注意：节点对象须取自 g4，g4 是 deepcopy）
    g4 = copy.deepcopy(g)
    for n in g4["nodes"][:2]:
        n["ports"] = [p for p in n["ports"] if not p["type"].startswith("SIG")]
        n["ports"].append({"type": "SIG:REWARD", "status": "declared"})
    g4_nodes = {n["id"]: n for n in g4["nodes"]}
    r10 = compose(g4_nodes["NA_FULL"], g4_nodes["NB_FULL"], g4)
    expect("阴性·仅 REWARD 不构成链路 ⇒ unknown",
           r10["axes"]["signal"]["verdict"] == "unknown")

    # ---- 产物级：绿路径 ----
    doc = None
    try:
        import build_compose_semantics as bcs
        doc = bcs.build(with_timestamp=False, graph=g)
    except Exception as e:  # pragma: no cover
        expect("产物级·build(合成图) 可运行", False, repr(e))
    if doc is not None:
        expect("产物级·check_doc 绿路径", check_doc(doc, g) == [],
               str(check_doc(doc, g)[:3]))

        # ---- 变异（各判红）----
        m = copy.deepcopy(doc)
        m["aggregates"]["overall_counts"]["unknown"] += 1
        expect("变异·篡改 overall_counts ⇒ 红", check_doc(m, g) != [])

        m = copy.deepcopy(doc)
        if m["examples"]:
            m["examples"][0]["overall"] = "type_error"  # 异值篡改，必与引擎重算不符
        expect("变异·篡改判例 verdict ⇒ 红", check_doc(m, g) != [])

        m = copy.deepcopy(doc)
        m["meta"]["engine_version"] = "compose_engine/v0"
        expect("变异·篡改 engine_version ⇒ 红", check_doc(m, g) != [])

        m = copy.deepcopy(doc)
        m.pop("rule_table")
        expect("变异·删 rule_table ⇒ 红", check_doc(m, g) != [])

        m = copy.deepcopy(doc)
        m["roles"]["brain_side_candidates"]["node_count"] += 100
        expect("变异·篡改 roles.node_count ⇒ 红", check_doc(m, g) != [])

        m = copy.deepcopy(doc)
        m["meta"].pop("honest_limits")
        expect("变异·删 honest_limits ⇒ 红", check_doc(m, g) != [])

        # fail-closed 守卫：无声明 SIG 却报 composed
        m = copy.deepcopy(doc)
        m["aggregates"]["overall_counts"]["composed"] = 5
        m["aggregates"]["overall_counts"]["unknown"] -= 5
        # 合成图有 declared SIG，此变异只触发「判例缺失」……构造真无 SIG 图：
        g_nosig = copy.deepcopy(g)
        for n in g_nosig["nodes"]:
            n["ports"] = [p for p in n["ports"] if not p["type"].startswith("SIG")]
        doc2 = bcs.build(with_timestamp=False, graph=g_nosig)
        expect("守卫·无 SIG 图 composed=0",
               doc2["aggregates"]["overall_counts"]["composed"] == 0)
        m2 = copy.deepcopy(doc2)
        m2["aggregates"]["overall_counts"]["composed"] = 3
        m2["aggregates"]["overall_counts"]["unknown"] -= 3
        expect("守卫·无 SIG 图硬塞 composed ⇒ 红", check_doc(m2, g_nosig) != [])

        # 往返确定性：再 build 一次与首份逐键相等（剥离易变键）
        doc3 = bcs.build(with_timestamp=False, graph=g)
        expect("确定性·两次 build 逐键相等", strip_volatile(doc3) == strip_volatile(doc))

    print()
    if failures:
        print(f"自证失败 {len(failures)} 项: {failures}")
        return 1
    print("自证全部通过（阳性/阴性/公理/fail-closed/变异/守卫/确定性）")
    return 0


def main() -> int:
    args = sys.argv[1:]
    quiet = "--quiet" in args
    if "--self-test" in args:
        rc = self_test()
        return rc if not quiet else (0 if rc == 0 else 1)
    with open(GRAPH_PATH, encoding="utf-8") as f:
        graph = json.load(f)
    with open(DOC_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    errs = check_doc(doc, graph)
    if errs:
        for e in errs:
            print(f"❌ {e}")
        print(f"compose_semantics 审计失败：{len(errs)} 处")
        return 1
    if not quiet:
        agg = doc["aggregates"]["overall_counts"]
        print(f"✅ compose_semantics 审计通过：pairs={doc['aggregates']['pairs_evaluated']} "
              f"composed={agg['composed']} type_error={agg['type_error']} "
              f"unknown={agg['unknown']} examples={len(doc['examples'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
