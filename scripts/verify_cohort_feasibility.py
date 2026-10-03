#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_cohort_feasibility — 最小可行同质集层的阴阳自证（挂 ci_gate）。

为什么这层的自证比 MDV 层更严
----------------------------
MDV 层输出了「16 个单条正收益目标」，看起来像个可执行清单，
但探针 7 端到端验证发现：**单独补这 16 个，电气可判定对数 1→1 持平，预测未兑现**。
根因是 MDV 把「联合上界」误标成「单条边际值」。

这类错误的特征是：**产物自身完全自洽，只是语义标签错了**。
所以算术守卫抓不住它——必须靠**端到端行为验证**：

  ① 正样本：合成图里造一个「K=2 可行」的最小结构，层必须报出该对；
  ② 负样本：合成图里造一个「K=2 不可行」的结构，层**必须不报**；
     ——只测正样本的闸门是装饰（项目 §四纪律）。
  ③ K=1 不可能性：必须能在产物里找到该论证，且逻辑上无法被绕过。
  ④ 同质 ⊆ 全集：计数守恒。
  ⑤ MDV 对账：MDV 的单条目标必须全部落在可行集内（跨层不变量）。
     若 MDV 与本层分叉，说明至少一层已失效。
  ⑥ 变异检测：注入 5 种变异，必须逐一判红。
"""
from __future__ import annotations

import copy
import json
import os
import sys
from itertools import combinations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_cohort_feasibility as bcf  # noqa: E402
from compose_engine import CompatIndex  # noqa: E402

FAILED: list = []
_MUTFAIL: list = []


def fail(msg: str) -> None:
    FAILED.append(msg)
    print(f"  [FAIL] {msg}")


def _mutfail(msg: str) -> None:
    _MUTFAIL.append(msg)


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


def _synth(kind: str):
    """构造合成图。kind='viable' → 必须报出可行对；kind='infeasible' → 必须不报。

    可行结构：两节点同缺 mechanical，各自补齐后 MECH 侧同型可配，
    且 ELEC/SIG 现状已可判定 ⇒ K=2 可行。
    不可行结构：两节点**缺不同轴组**（一方缺 MECH，另一方缺 ELEC），
    补齐后仍有一轴无端口 ⇒ K=2 不可行。
    """
    def P(t):
        return {"type": t, "status": "declared"}

    def N(t):
        return {"type": t, "status": "not_declared"}

    M = "MECH:ISO9409-1-A50-4-M6"
    E = "ELEC:CONNECTOR:JST-EHR-03"
    S = "SIG:OUTPUT_SPIKE"
    SI = "SIG:INPUT_SENSORY"
    MU = "MECH:UNKNOWN"
    EU = "ELEC:UNKNOWN"

    def node(nid, ports, cat="actuators"):
        return {"id": nid, "label": nid, "composable": True, "category": cat,
                "manufacturer": "SYNTH", "kind": "component", "ports": ports}

    if kind == "viable":
        # A、B 同缺 MECH；ELEC 与 SIG 现状即可判定
        nodes = [
            node("V-A", [N(M), P(E), P(S)]),
            node("V-B", [N(M), P(E), P(SI)]),
        ]
    else:
        # A 缺 MECH，B 缺 ELEC ⇒ 异质组
        nodes = [
            node("I-A", [N(M), P(E), P(S)]),
            node("I-B", [P(M), N(E), P(SI)]),
        ]

    tc = []
    for a in (M, MU):
        for b in (M, MU):
            tc.append({"a": a, "b": b, "verdict": "identity", "reason": "syn"})
    for a in (E, EU):
        for b in (E, EU):
            tc.append({"a": a, "b": b, "verdict": "identity", "reason": "syn"})
    tc.append({"a": S, "b": S, "verdict": "unknown", "reason": "syn"})
    tc.append({"a": SI, "b": SI, "verdict": "unknown", "reason": "syn"})
    tc.append({"a": S, "b": SI, "verdict": "identity", "reason": "syn"})
    tc.append({"a": SI, "b": S, "verdict": "identity", "reason": "syn"})
    return {"nodes": nodes, "type_compat": tc}


def _run_synth(graph, missing):
    """对合成图跑本层核心逻辑（复用 build 内部函数，避免重复实现）。"""
    nodes = [n for n in graph["nodes"] if n.get("composable", True)]
    compat = CompatIndex(graph.get("type_compat") or [])
    pool = bcf._pool(nodes)
    eff = {n["id"]: bcf._effective(n) for n in nodes}
    ids = [n["id"] for n in nodes]
    homog = []
    for a, b in combinations(ids, 2):
        if missing(a, eff) != missing(b, eff):
            continue
        okpair = True
        for ax in bcf.AXES:
            pre = bcf.PREFIX[ax]
            pa = eff[a].get(pre) or pool[pre]
            pb = eff[b].get(pre) or pool[pre]
            if not bcf._axis_ok(pa, pb, compat):
                okpair = False
                break
        if okpair:
            homog.append((a, b))
    return homog


def check_synthetic() -> None:
    print("\n[1/4] 阴阳对照（合成图：正样本必报 / 负样本必不报）")

    def miss(nid, eff):
        return tuple(a for a in bcf.AXES if not eff[nid].get(bcf.PREFIX[a]))

    h_pos = _run_synth(_synth("viable"), miss)
    if not h_pos:
        fail("正样本失守：同缺 MECH 的两节点应构成 K=2 可行对，层却报 0")
    else:
        ok(f"正样本成立：{h_pos} 构成可行对")

    h_neg = _run_synth(_synth("infeasible"), miss)
    if h_neg:
        fail(f"负样本失守：异质缺轴组应不可行，层却报 {h_neg} —— 同质过滤有洞")
    else:
        ok("负样本成立：异质缺轴组不产生可行对（同质过滤正确）")


def check_k1_impossible(out) -> None:
    print("\n[2/4] K=1 不可能性论证")
    m = out.get("method") or {}
    if "k1_impossible" not in m:
        fail("method.k1_impossible 缺失 —— K=1 不可能性是本层的前提，缺它整层无意义")
    else:
        ok("K=1 不可能性论证在位")
    s = out.get("summary") or {}
    if s.get("min_viable_k") != 2:
        fail(f"min_viable_k 应为 2，收到 {s.get('min_viable_k')!r}")
    else:
        ok("min_viable_k = 2")
    # 逻辑守卫：K=1 恒不可判定是**定义性**的（单条只能补一侧），
    # 产物里不应出现任何 K=1 的可行对记录
    if s.get("k1_status", "").startswith("possible"):
        fail("k1_status 声称 K=1 可行 —— 与 method.k1_impossible 矛盾")
    else:
        ok(f"k1_status = {s.get('k1_status')!r}")


def check_conservation(out) -> None:
    print("\n[3/4] 计数守恒 + MDV 跨层对账")
    s = out.get("summary") or {}
    n = s.get("nodes_evaluated", 0)
    total = n * (n - 1) // 2
    v, h = s.get("viable_pairs_k2", 0), s.get("homogeneous_viable_pairs", 0)
    if h > v:
        fail(f"同质集 {h} > 可行集 {v}，过滤逻辑反了")
    elif v > total:
        fail(f"可行对 {v} > C(n,2) {total}")
    else:
        ok(f"同质 {h:,} ⊆ 可行 {v:,} ⊆ 全对 {total:,}")

    # 缺口画像加总必须回到同质可行对总数
    prof_sum = sum(p["viable_pairs"] for p in out.get("gap_profiles") or [])
    if prof_sum != h:
        fail(f"缺口画像加总 {prof_sum:,} != 同质可行对 {h:,}")
    else:
        ok(f"缺口画像加总 {prof_sum:,} == 同质可行对")

    # 每个 profile 的 nodes_involved 不得超过总节点数
    for p in out.get("gap_profiles") or []:
        if p["nodes_involved"] > n:
            fail(f"profile {p['missing_axes']} 节点数 {p['nodes_involved']} > 全库 {n}")
    ok("各 profile 节点数在界内")

    # 跨层：MDV 的单条目标必须全部落在可行集内
    rc = out.get("mdv_reconciliation")
    if rc is None:
        print("  [skip] MDV 产物不存在，跳过跨层对账")
        return
    t = rc.get("mdv_single_declaration_targets", 0)
    landed = rc.get("landed_in_viable_cohort", 0)
    if t and landed != t:
        fail(f"MDV 对账不一致：{landed}/{t} 落在可行集 —— 两层判定分叉")
    else:
        ok(f"MDV 对账一致：{landed}/{t} 落在可行集")


def _mut_homog_gt_viable(out, label):
    m = copy.deepcopy(out)
    m["summary"]["homogeneous_viable_pairs"] = \
        m["summary"]["viable_pairs_k2"] + 1
    return m


def _mut_profile_sum(out, label):
    m = copy.deepcopy(out)
    if m.get("gap_profiles"):
        m["gap_profiles"][0]["viable_pairs"] += 1
    return m


def _mut_k1_ok(out, label):
    m = copy.deepcopy(out)
    m["summary"]["min_viable_k"] = 1
    m["summary"]["k1_status"] = "possible"
    return m


def _mut_nodes_overflow(out, label):
    m = copy.deepcopy(out)
    if m.get("gap_profiles"):
        m["gap_profiles"][0]["nodes_involved"] = 10 ** 9
    return m


def _mut_pairs_overflow(out, label):
    m = copy.deepcopy(out)
    m["summary"]["viable_pairs_k2"] = 10 ** 9
    return m


def _mut_method_stripped(out, label):
    m = copy.deepcopy(out)
    m.get("method", {}).pop("k1_impossible", None)
    return m


MUTATIONS = [
    ("同质集 > 可行集", _mut_homog_gt_viable),
    ("缺口画像加总 != 同质可行对", _mut_profile_sum),
    ("min_viable_k 被改成 1", _mut_k1_ok),
    ("profile 节点数溢出", _mut_nodes_overflow),
    ("可行对数溢出 C(n,2)", _mut_pairs_overflow),
    ("K=1 不可能性论证被删", _mut_method_stripped),
]


def _assert_all(out, sink):
    s = out.get("summary") or {}
    n = s.get("nodes_evaluated", 0)
    total = n * (n - 1) // 2
    v, h = s.get("viable_pairs_k2", 0), s.get("homogeneous_viable_pairs", 0)
    if h > v:
        sink("同质集大于可行集")
    if v > total:
        sink("可行对数超过 C(n,2)")
    if sum(p["viable_pairs"] for p in out.get("gap_profiles") or []) != h:
        sink("缺口画像加总不守恒")
    if s.get("min_viable_k") != 2:
        sink("min_viable_k != 2")
    if (s.get("k1_status") or "").startswith("possible"):
        sink("k1_status 声称 K=1 可行")
    if "k1_impossible" not in (out.get("method") or {}):
        sink("K=1 不可能性论证缺失")
    for p in out.get("gap_profiles") or []:
        if p.get("nodes_involved", 0) > n:
            sink("profile 节点数溢出")
    rc = out.get("mdv_reconciliation")
    if rc and rc.get("mdv_single_declaration_targets"):
        if rc.get("landed_in_viable_cohort") != rc["mdv_single_declaration_targets"]:
            sink("MDV 跨层对账不一致")


def check_mutations(out) -> None:
    print("\n[4/4] 变异检测（每个变异必须判红）")
    for label, fn in MUTATIONS:
        before = len(_MUTFAIL)
        _assert_all(fn(out, label), _mutfail)
        if len(_MUTFAIL) == before:
            fail(f"变异未被捕获：{label}（闸门对该变异不敏感）")
        else:
            print(f"  [ok]   变异已捕获：{label}（触发 {len(_MUTFAIL)-before} 条断言）")


def main() -> int:
    print("=" * 70)
    print("verify_cohort_feasibility — 最小可行同质集层阴阳自证")
    print("=" * 70)
    out = bcf.build()

    check_synthetic()
    check_k1_impossible(out)
    check_conservation(out)

    before = len(FAILED)
    _assert_all(out, fail)
    if len(FAILED) > before:
        print("\n真实产物未通过守恒，后续变异检测无意义。")
        return 1
    ok("baseline 干净（阴性对照成立）")

    check_mutations(out)

    print("\n" + "=" * 70)
    if FAILED:
        print(f"FAIL：{len(FAILED)} 项未通过")
        for m in FAILED:
            print(f"  - {m}")
        return 1
    print("PASS：全部自证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
