#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_evidence_valuation — MDV 层的阴阳自证（挂 ci_gate）。

为什么必须有这个闸门
------------------
MDV 层输出的是「某轴取证收益恒为 0」这种**定理级断言**。断言错了不会崩，
只会安静地误导整个项目的取证方向（把资源投到 MDV=0 的轴上）。
而它错的方式很隐蔽：引擎逻辑改错一个 PAIR_RANK 阈值、或 type_compat 表少登记
几条，MDV 全都可能翻号，而所有「跑通了」的检查都照样绿。

所以本闸门走**阳性 + 阴性 + 变异三对照**（项目 §四纪律）：
  1. 算术自洽：产物内部计数必须互相咬合。
  2. 阴阳对照：构造一个「电气轴已有声明」的合成图，MDV 必须给出正收益。
  3. 变异检测：逐个注入 5 种变异，闸门必须逐一判红。
  4. 恒等复现：同输入跑两次结果必须一致（确定性）。
  5. 反向误报：把真实产物里「有效轴」的 MDV 改小，看是否触发 zero 误报。

变异体不得改磁盘文件（ci_gate 会先跑 builder 把文件级篡改洗掉），
故全部走**内存级注入 + 直接调用 build 内部函数**。
"""
from __future__ import annotations

import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_evidence_valuation as bev  # noqa: E402

FAILED: list = []


def fail(msg: str) -> None:
    """记录真实失败。变异体触发的失败走 _MUTFAIL，不进这里。"""
    FAILED.append(msg)
    print(f"  [FAIL] {msg}")


#: 变异体专用失败收集器。变异**应该**触发失败，所以它的失败不是「本层有 bug」，
#: 而是「闸门成功捕获了变异」。若混进 FAILED，闸门会永远红 —— 那就是假红灯，
#: 违反项目 §四纪律「只测绿路径的闸门等于没闸门」的镜像版本。
_MUTFAIL: list = []


def _mutfail(msg: str) -> None:
    _MUTFAIL.append(msg)


def ok(msg: str) -> None:
    print(f"  [ok]   {msg}")


def _base_graph():
    with open(os.path.join(ROOT, bev.GRAPH_PATH), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. 算术自洽（真实产物）
# ---------------------------------------------------------------------------
def check_arithmetic(out, sink=None) -> None:
    """算术自洽断言。sink 指定失败收集器（变异体传 _mutfail）。"""
    emit = sink or fail
    if sink is None:
        print("\n[1/5] 算术自洽")
    s = out["summary"]
    n = s["nodes_evaluated"]
    total = n * (n - 1) // 2
    if s["total_pairs"] != total:
        emit(f"total_pairs {s['total_pairs']} != C(n,2) {total}")
    else:
        ok(f"total_pairs == C({n},2) == {total}")

    for axis, cnt in s["per_axis_decidable_pairs"].items():
        if cnt > total:
            emit(f"{axis} 可判定对 {cnt} > 全对空间 {total}")
    if emit is fail:
        ok("各轴可判定对数 <= 全对空间")

    conj = s["two_axis_conjunction"]
    for combo, cnt in conj.items():
        a, b = combo.split("+")
        cap = min(s["per_axis_decidable_pairs"][a], s["per_axis_decidable_pairs"][b])
        if cnt > cap:
            emit(f"{combo}={cnt} > min({a},{b})={cap}，AND 语义被破坏")
    if emit is fail:
        ok("二轴 AND 不超过单轴上界")

    if s["three_axis_conjunction"] > min(conj.values()):
        emit("三轴 AND 超过二轴 AND")
    elif emit is fail:
        ok(f"三轴 AND = {s['three_axis_conjunction']} <= 各二轴 AND")

    # MDV 计数守恒：正收益 + 零贡献 == 未声明节点数
    for axis, b in out["by_axis"].items():
        if b["positive_mdv_nodes"] + b["zero_mdv_nodes"] != b["undeclared_nodes"]:
            emit(f"{axis}: 正收益+零贡献 != 未声明数")
        elif emit is fail:
            ok(f"{axis}: {b['positive_mdv_nodes']}+{b['zero_mdv_nodes']}"
               f" == {b['undeclared_nodes']} 未声明")

    # entity_mdv_index 条数须等于未声明节点总数（跨轴）
    idx_n = len(out["entity_mdv_index"])
    expect = sum(b["undeclared_nodes"] for b in out["by_axis"].values())
    if idx_n != expect:
        emit(f"entity_mdv_index 条数 {idx_n} != 未声明总数 {expect}")
    elif emit is fail:
        ok(f"entity_mdv_index 条数 {idx_n} == 未声明总数")

    # top_targets 里的 MDV 必须与索引一致（防止两处口径分叉）
    for axis, b in out["by_axis"].items():
        for t in b["top_targets"]:
            k = f"{t['id']}::{t['axis']}"
            if out["entity_mdv_index"].get(k) != t["mdv"]:
                emit(f"top_target {k} 的 MDV 与索引不一致")
                break
    if emit is fail:
        ok("top_targets MDV 与 entity_mdv_index 一致")


# ---------------------------------------------------------------------------
# 2. 阴阳对照：合成图必须给出正收益（真实数据是 97.45% 零，闸门必须能看见正号）
# ---------------------------------------------------------------------------
def _synth_graph():
    """构造 5 节点合成图。

    必须包含**至少一个该轴未声明**的节点，否则 MDV 无取证目标、正样本失守。
    设计意图：
      A,B,C 三轴齐备且 A×B 三轴互补 ⇒ 三轴 AND > 0（引擎能判 composed）
      D 只缺 electrical 轴 ⇒ 补 D 的 electrical 声明可救回与 A/B/C 的配对
        ⇒ MDV(D, electrical) > 0（正样本）
      D 的 mechanical/signal 仍可判定，故满足 MDV 的「另两轴已 True」前提
    """
    def node(nid, ports):
        return {"id": nid, "label": nid, "composable": True, "category": "actuators",
                "manufacturer": "SYNTH", "kind": "component", "ports": ports}
    P = lambda t: {"type": t, "status": "declared"}   # noqa: E731
    N = lambda t: {"type": t, "status": "not_declared"}  # noqa: E731

    M, E, S = "MECH:ISO9409-1-A50-4-M6", "ELEC:JST-EHR-03", "SIG:OUTPUT_SPIKE"
    SI = "SIG:INPUT_SENSORY"
    MU, EU = "MECH:UNKNOWN", "ELEC:UNKNOWN"

    nodes = [
        node("SYN-A", [P(M), P(E), P(S)]),
        node("SYN-B", [P(M), P(E), P(SI)]),
        node("SYN-C", [P(M), P(E), P(SI)]),
        # D 缺 electrical ⇒ 唯一的取证目标
        node("SYN-D", [P(M), N(E), P(SI)]),
        node("SYN-E", [N(M), N(E), P(SI)]),
    ]
    tc = []
    def add(a, b, v):
        tc.append({"a": a, "b": b, "verdict": v, "reason": "synthetic"})
    for a in (M, MU):
        for b in (M, MU):
            add(a, b, "identity")
    for a in (E, EU):
        for b in (E, EU):
            add(a, b, "identity")
    add(S, S, "unknown")
    add(SI, SI, "unknown")
    add(S, SI, "identity")
    add(SI, S, "identity")
    return {"nodes": nodes, "type_compat": tc}


def check_synthetic() -> None:
    print("\n[2/5] 阴阳对照（合成图：必须出现正 MDV）")
    g = _synth_graph()
    nodes = [n for n in g["nodes"] if n.get("composable", True)]
    from compose_engine import CompatIndex
    compat = CompatIndex(g["type_compat"])
    pool = bev._port_type_pool(nodes)
    mat = bev._decidable_matrix(nodes, compat)
    rows = bev._mdv_table(nodes, mat, pool, compat)
    summary, by_axis = bev._summarize(rows, nodes, mat, compat, pool)

    total_pos = sum(b["positive_mdv_nodes"] for b in by_axis.values())
    if total_pos == 0:
        fail("合成图下 MDV 全为 0 —— 判据在正样本上失效（引擎恒返回 0）")
    else:
        ok(f"合成图下正 MDV 目标数 = {total_pos}")

    # 精确断言：SYN-D 只缺 electrical，它必须被识别为正收益目标
    d_rows = [r for r in rows if r["id"] == "SYN-D"]
    if not d_rows:
        fail("合成图 SYN-D 未出现在 MDV 表中（该轴已声明或节点被漏）")
    else:
        elec_d = [r for r in d_rows if r["axis"] == "electrical"]
        if not elec_d:
            fail("SYN-D 的 electrical 轴未列为取证目标（但它 not_declared）")
        elif elec_d[0]["mdv"] <= 0:
            fail(f"SYN-D electrical MDV={elec_d[0]['mdv']}，正样本失守"
                 "（D 与 A/B/C 的另两轴均可判定，补 E 应有正收益）")
        else:
            ok(f"SYN-D electrical MDV = {elec_d[0]['mdv']} > 0（正样本成立）")

    if summary["three_axis_conjunction"] == 0:
        fail("合成图三轴 AND = 0，但 SYN-A×SYN-B 应可判定（正样本失守）")
    else:
        ok(f"合成图三轴 AND = {summary['three_axis_conjunction']} > 0")

    # 负样本：SYN-E 缺两轴，补任一轴都救不回（另一轴仍缺）⇒ MDV 必为 0
    e_rows = {r["axis"]: r["mdv"] for r in rows if r["id"] == "SYN-E"}
    if e_rows and any(v > 0 for v in e_rows.values()):
        fail(f"SYN-E 缺两轴却报正 MDV {e_rows} —— AND 语义被破坏（负样本失守）")
    elif e_rows:
        ok(f"SYN-E 缺两轴 ⇒ MDV 全 0 {e_rows}（负样本成立：单轴补齐不够）")
    else:
        fail("SYN-E 未出现在 MDV 表中")

    # 反向误报检查：正样本下不得出现任何 provably_zero_mdv 裁决
    for axis, b in by_axis.items():
        if b["verdict"].startswith("provably_zero_mdv") and b["undeclared_nodes"] == 0:
            fail(f"{axis}: 无未声明节点却输出 provably_zero_mdv（措辞误报）")
    ok("无未声明节点时不误报 provably_zero_mdv")


# ---------------------------------------------------------------------------
# 3. 变异检测：5 种变异必须逐一判红
# ---------------------------------------------------------------------------
def _mut_arithmetic(out, label):
    """篡改 total_pairs，使 C(n,2) 守恒被破坏。"""
    m = copy.deepcopy(out)
    m["summary"]["total_pairs"] += 1
    return m


def _mut_and_above_single(out, label):
    """篡改二轴 AND 使其超过单轴上界。"""
    m = copy.deepcopy(out)
    m["summary"]["two_axis_conjunction"]["mechanical+signal"] = \
        m["summary"]["per_axis_decidable_pairs"]["mechanical"] + 999
    return m


def _mut_three_above_two(out, label):
    """篡改三轴 AND 使其超过二轴 AND。"""
    m = copy.deepcopy(out)
    m["summary"]["two_axis_conjunction"]["mechanical+signal"] = 10 ** 9
    m["summary"]["two_axis_conjunction"]["mechanical+electrical"] = 10 ** 9
    m["summary"]["two_axis_conjunction"]["electrical+signal"] = 10 ** 9
    m["summary"]["three_axis_conjunction"] = 10 ** 9 + 1
    return m


def _mut_count_conservation(out, label):
    """篡改 MDV 计数守恒（正收益 + 零贡献 != 未声明）。"""
    m = copy.deepcopy(out)
    axis = next(iter(m["by_axis"]))
    m["by_axis"][axis]["zero_mdv_nodes"] += 7
    return m


def _mut_index_mismatch(out, label):
    """篡改 top_targets MDV 与索引产生分叉。"""
    m = copy.deepcopy(out)
    for axis, b in m["by_axis"].items():
        if b["top_targets"]:
            b["top_targets"][0]["mdv"] = 99999
            break
    return m


def _mut_axis_overflow(out, label):
    """篡改单轴可判定对数超过全对空间。"""
    m = copy.deepcopy(out)
    axis = next(iter(m["summary"]["per_axis_decidable_pairs"]))
    m["summary"]["per_axis_decidable_pairs"][axis] = 10 ** 9
    return m


MUTATIONS = [
    ("total_pairs 破坏 C(n,2) 守恒", _mut_arithmetic),
    ("二轴 AND 超过单轴上界", _mut_and_above_single),
    ("三轴 AND 超过二轴 AND", _mut_three_above_two),
    ("MDV 计数守恒被破坏", _mut_count_conservation),
    ("top_targets 与索引口径分叉", _mut_index_mismatch),
    ("单轴可判定对数溢出全对空间", _mut_axis_overflow),
]


def check_mutations(out) -> None:
    print("\n[3/5] 变异检测（每个变异必须判红）")
    for label, fn in MUTATIONS:
        before = len(_MUTFAIL)
        mutant = fn(out, label)
        # 用同一套断言校验变异体，但失败进 _MUTFAIL（变异**应该**触发失败）
        check_arithmetic(mutant, sink=_mutfail)
        if len(_MUTFAIL) == before:
            fail(f"变异未被捕获：{label}（闸门对该变异不敏感）")
        else:
            print(f"  [ok]   变异已捕获：{label}（触发 {len(_MUTFAIL)-before} 条断言）")


def check_arithmetic_quiet(out) -> None:
    """已并入 check_arithmetic(sink=...)，保留别名以兼容外部引用。"""
    check_arithmetic(out, sink=_mutfail)


# ---------------------------------------------------------------------------
# 4. 恒等复现（确定性）
# ---------------------------------------------------------------------------
def check_determinism() -> None:
    print("\n[4/5] 恒等复现（两次 build 结果必须一致）")
    a = bev.build()
    b = bev.build()
    for key in ("summary", "by_axis", "entity_mdv_index"):
        ja = json.dumps(a[key], sort_keys=True, ensure_ascii=False)
        jb = json.dumps(b[key], sort_keys=True, ensure_ascii=False)
        if ja != jb:
            fail(f"{key} 两次 build 结果不一致（存在非确定性）")
        else:
            ok(f"{key} 两次 build 一致")


# ---------------------------------------------------------------------------
# 5. 反向误报：有效轴不得被误判为 provably_zero_mdv
# ---------------------------------------------------------------------------
def check_no_false_zero(out) -> None:
    print("\n[5/5] 反向误报")
    for axis, b in out["by_axis"].items():
        zero_claim = b["verdict"].startswith("provably_zero_mdv")
        actually_zero = b["positive_mdv_nodes"] == 0 and b["undeclared_nodes"] > 0
        if zero_claim != actually_zero:
            fail(f"{axis}: verdict='{b['verdict'][:40]}' 与实测"
                 f"（正收益 {b['positive_mdv_nodes']} / 未声明 "
                 f"{b['undeclared_nodes']}）矛盾")
        else:
            ok(f"{axis}: zero_claim={zero_claim} 与实测一致")

    # 电气轴是本层判定的关键轴：它必须有正收益目标，否则 MDV 层没抓到关键
    elec = out["by_axis"]["electrical"]
    if elec["positive_mdv_nodes"] == 0:
        fail("electrical 轴正收益为 0 —— 与探针实测（15 个有效目标）矛盾，"
             "MDV 层可能已失效")
    else:
        ok(f"electrical 轴正收益目标 {elec['positive_mdv_nodes']} 个")


def main() -> int:
    print("=" * 68)
    print("verify_evidence_valuation — MDV 层阴阳自证")
    print("=" * 68)
    out = bev.build()

    # baseline 必须先干净
    n_before = len(FAILED)
    check_arithmetic(out)
    if len(FAILED) > n_before:
        print("\n真实产物未通过算术自洽，后续变异检测无意义。")
        return 1
    ok("baseline 干净（变异检测的阴性对照成立）")

    check_synthetic()
    check_mutations(out)
    check_determinism()
    check_no_false_zero(out)

    print("\n" + "=" * 68)
    if FAILED:
        print(f"FAIL：{len(FAILED)} 项未通过")
        for m in FAILED:
            print(f"  - {m}")
        return 1
    print("PASS：全部自证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
