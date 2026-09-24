#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compose_engine — RoboParts 轻量效应系统原型（B1）+ 三轴类型语义（B2）。

    compose(a, b, graph) -> CompositionResult
    overall verdict ∈ {composed, type_error, unknown}   （三态诚实）

方向锚点：docs/PROJECT_DIRECTIONS_V2.md §1/§2（具身系统「组合」的形式化底座）。
路线图：docs/direction-evolution-roadmap-20260923.md Phase B1/B2
（「compose(brain, body) -> Result | TypeError」；先轻量 effect system，不上 Lean）。

设计要点（全部可判定、全部 fail-closed）：

1. 对称组合。引擎不预设谁是脑谁是体——形态图 593 节点全为 component，
   「脑侧/体侧」是类别角色标注（见 roles），不是引擎的前提。这是对数据的诚实：
   强行给 46 个 AI 模型造端口才是捏造。

2. 三轴类型语义（B2）：
   - mechanical  能不能拧上去（ISO 9409-1 标号 / 专有安装体）
   - electrical  能不能接上电（连接器标号 + pins/pitch）
   - signal      接上后能否正确收发脉冲（通道互补：OUTPUT_SPIKE → INPUT_SENSORY）

3. 判定只认 evidence：
   - effective 端口 = status ∈ {declared, partial}。not_declared 端口不参与判定，
     只进 evidence 计数。ELEC:UNKNOWN / MECH:UNKNOWN 枢纽端口构建时即为
     not_declared，天然被排除——缺口永远不可能伪装成兼容。

4. 类型序（pair verdict，来自形态图 type_compat + 一条公理）：
   - reflexivity 公理：ta == tb ⇒ identity。同型接口必然可配（自反性是类型
     系统的逻辑后承，不是猜测；ISO 标号在图里已显式登记 identity，专有类型
     依赖此公理补全）。
   - 其余查 type_compat（双向）：identity / adapter_required / incompatible /
     unknown。缺键 = unknown（fail-closed，绝不按标号字面猜）。

5. 轴内 best-pair 语义：多端口零件有多个安装面/连接器，组合只需一对可配。
   轴 verdict 取所有端口对的最优证据：
   identity > adapter_required > unknown > incompatible。
   全部 incompatible 才判 incompatible；存在 unknown 候选对时保守判 unknown
   （那个 unknown 对可能是可配的——我们不知道，就承认不知道）。

6. 总裁决优先级：任一轴 incompatible ⇒ type_error；
   否则任一轴 unknown ⇒ unknown；否则 composed。
   （数据现状：SIG 通道全部 not_declared ⇒ signal 恒 unknown ⇒
   composed 恒为 0。这是事实，不是缺陷——与溯源层「连接条件满足 0/4」一致。）
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

ENGINE_VERSION = "compose_engine/v1"

AXES: Tuple[str, ...] = ("mechanical", "electrical", "signal")

_PREFIX_AXIS = {"MECH": "mechanical", "ELEC": "electrical", "SIG": "signal"}

EFFECTIVE_STATUS = frozenset(("declared", "partial"))

# 轴内 pair 证据排序：数值大者胜（best-pair）
PAIR_RANK = {"identity": 3, "adapter_required": 2, "unknown": 1, "incompatible": 0}

# pair verdict → 轴 verdict 映射
AXIS_VERDICT_OF_PAIR = {
    "identity": "compatible",
    "adapter_required": "compatible_via_adapter",
    "unknown": "unknown",
    "incompatible": "incompatible",
}

AXIS_VERDICTS = ("compatible", "compatible_via_adapter", "incompatible", "unknown")
OVERALL_VERDICTS = ("composed", "type_error", "unknown")

SIG_OUTPUT = "SIG:OUTPUT_SPIKE"
SIG_INPUT = "SIG:INPUT_SENSORY"
SIG_REWARD = "SIG:REWARD"


class ComposeTypeError(ValueError):
    """输入不构成可判定对象（结构性错误，非三态裁决）。"""


def axis_of(port_type: str) -> Optional[str]:
    return _PREFIX_AXIS.get(port_type.split(":", 1)[0])


def _ports_of(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    return node.get("ports") or []


def effective_ports(node: Dict[str, Any], axis: str) -> List[Dict[str, Any]]:
    """该轴上带声明证据的端口。not_declared 不参与判定。"""
    return [
        p
        for p in _ports_of(node)
        if axis_of(p["type"]) == axis and p.get("status") in EFFECTIVE_STATUS
    ]


def undeclared_count(node: Dict[str, Any], axis: str) -> int:
    return sum(
        1
        for p in _ports_of(node)
        if axis_of(p["type"]) == axis and p.get("status") not in EFFECTIVE_STATUS
    )


class CompatIndex:
    """type_compat 双向索引 + reflexivity 公理。缺键一律 unknown。"""

    def __init__(self, type_compat: List[Dict[str, Any]]):
        self._index: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for entry in type_compat or []:
            key = (entry["a"], entry["b"])
            self._index[key] = entry

    def pair_verdict(self, ta: str, tb: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """返回 (pair_verdict, entry|None)。entry 仅索引命中时非空。"""
        if ta == tb:
            entry = self._index.get((ta, tb))
            if entry is not None:
                # 显式登记的自配对裁决优先于 reflexivity 公理。
                # reflexivity（同型必配）对**几何规格型**类型成立：A50-4-M6 法兰
                # 配 A50-4-M6 法兰必然可装。但对**方向性角色型**类型不成立：
                # OUTPUT_SPIKE 配 OUTPUT_SPIKE 不是「必然可装」，而是「不互补」。
                # 旧实现无条件返回 identity，会让 type_compat 里显式登记的
                # 自配对 unknown/incompatible 被静默覆盖——登记了等于没登记。
                return (entry["verdict"], entry)
            return ("identity", None)  # 未登记 ⇒ reflexivity 公理
        entry = self._index.get((ta, tb)) or self._index.get((tb, ta))
        if entry is None:
            return ("unknown", None)
        return (entry["verdict"], entry)


def _mech_elec_axis(
    a_eff: List[Dict[str, Any]],
    b_eff: List[Dict[str, Any]],
    compat: CompatIndex,
) -> Dict[str, Any]:
    pairs_eval: List[Dict[str, Any]] = []
    best_rank = -1
    best: Optional[Dict[str, Any]] = None
    for pa in a_eff:
        for pb in b_eff:
            verdict, entry = compat.pair_verdict(pa["type"], pb["type"])
            rec = {
                "a_type": pa["type"],
                "b_type": pb["type"],
                "pair_verdict": verdict,
            }
            if entry:
                rec["reason"] = entry.get("reason")
                rec["blocking_dims"] = entry.get("blocking_dims") or []
            pairs_eval.append(rec)
            rank = PAIR_RANK[verdict]
            if rank > best_rank:
                best_rank = rank
                best = rec
    best_pair_verdict = best["pair_verdict"] if best else "unknown"
    return {
        "verdict": AXIS_VERDICT_OF_PAIR[best_pair_verdict],
        "best_pair": best,
        "pairs_evaluated": pairs_eval,
    }


def _signal_axis(
    a_node: Dict[str, Any], b_node: Dict[str, Any], compat: CompatIndex
) -> Dict[str, Any]:
    """信号轴判定。verdict 一律来自 type_compat 查表（单一判据源）。

    本函数只负责两件事：产出**结构化通道证据**（sensory_links / reward），
    以及把「哪一轴可组合」的判据交给 CompatIndex——不在这里另写互补规则。
    旧实现把 OUTPUT~INPUT 互补逻辑硬编码在两处（本函数与 eval_all_pairs），
    两处语义一旦分叉，产物与引擎就会悄悄不一致。

    REWARD 是「学习者消费奖励」，双方各有 REWARD 端口不代表互连，
    只记 evidence，不参与正向判定（fail-closed）。
    """
    a_ports = effective_ports(a_node, "signal")
    b_ports = effective_ports(b_node, "signal")
    a_ids = sorted({p["type"] for p in a_ports})
    b_ids = sorted({p["type"] for p in b_ports})
    links = []
    if SIG_OUTPUT in a_ids and SIG_INPUT in b_ids:
        links.append("a_output_to_b_input")
    if SIG_OUTPUT in b_ids and SIG_INPUT in a_ids:
        links.append("b_output_to_a_input")
    reward_note = {
        "a_declared": SIG_REWARD in a_ids,
        "b_declared": SIG_REWARD in b_ids,
    }
    base = {"sensory_links": links, "reward": reward_note}
    if not a_ids or not b_ids:
        return dict(
            base,
            verdict="unknown",
            reason="任一侧无已声明信号端口（not_declared）",
        )
    best_rank = -1
    best_pv = "unknown"
    reason = None
    for ta in a_ids:
        for tb in b_ids:
            pv, entry = compat.pair_verdict(ta, tb)
            if PAIR_RANK[pv] > best_rank:
                best_rank = PAIR_RANK[pv]
                best_pv = pv
                reason = entry.get("reason") if entry else None
    out = dict(base, verdict=AXIS_VERDICT_OF_PAIR[best_pv])
    if reason:
        out["reason"] = reason
    return out


def compose(a: Dict[str, Any], b: Dict[str, Any], graph: Dict[str, Any]) -> Dict[str, Any]:
    """对称组合裁决。graph 为 morphology_graph.json 反序列化对象。"""
    for name, node in (("a", a), ("b", b)):
        if not isinstance(node, dict) or "id" not in node:
            raise ComposeTypeError(f"节点 {name} 缺 id")
    compat = CompatIndex(graph.get("type_compat") or [])

    axes: Dict[str, Any] = {}
    for axis in ("mechanical", "electrical"):
        a_eff = effective_ports(a, axis)
        b_eff = effective_ports(b, axis)
        base = {
            "a_effective": len(a_eff),
            "b_effective": len(b_eff),
            "a_undeclared": undeclared_count(a, axis),
            "b_undeclared": undeclared_count(b, axis),
        }
        if not a_eff or not b_eff:
            base.update(
                verdict="unknown",
                reason="任一侧该轴无声明端口（not_declared）——证据缺口，不猜测",
            )
        else:
            base.update(_mech_elec_axis(a_eff, b_eff, compat))
        axes[axis] = base

    axes["signal"] = _signal_axis(a, b, compat)
    axes["signal"]["a_undeclared"] = undeclared_count(a, "signal")
    axes["signal"]["b_undeclared"] = undeclared_count(b, "signal")

    axis_verdicts = [axes[ax]["verdict"] for ax in AXES]
    if "incompatible" in axis_verdicts:
        overall = "type_error"
    elif "unknown" in axis_verdicts:
        overall = "unknown"
    else:
        overall = "composed"

    return {
        "engine_version": ENGINE_VERSION,
        "node_a": a["id"],
        "node_b": b["id"],
        "overall": overall,
        "axes": axes,
    }


def eval_all_pairs(graph: Dict[str, Any], examples_per_class: int = 0) -> Dict[str, Any]:
    """全对评测（含自配对）：聚合计数 + 交叉表。确定性，无随机。

    只回聚合，不回逐对结果（35 万对逐对落盘既无必要也不可审计）。
    examples_per_class > 0 时，按遍历序为每个总裁决类别收集前 N 个
    (node_a, node_b) 判例 id（完整证据由调用方对判例单独调 compose()）。
    """
    nodes = [n for n in graph.get("nodes") or [] if n.get("composable", True)]
    compat = CompatIndex(graph.get("type_compat") or [])

    # 预取每节点每轴的 effective 类型集合（判定只依赖类型，不依赖其余字段）
    eff: Dict[str, Dict[str, List[str]]] = {}
    undecl: Dict[str, Dict[str, int]] = {}
    for n in nodes:
        eff[n["id"]] = {
            ax: sorted(p["type"] for p in effective_ports(n, ax))
            for ax in ("mechanical", "electrical")
        }
        undecl[n["id"]] = {ax: undeclared_count(n, ax) for ax in AXES}
        sig = {p["type"] for p in effective_ports(n, "signal")}
        eff[n["id"]]["signal"] = sorted(sig)

    overall_counts = {v: 0 for v in OVERALL_VERDICTS}
    axis_marginals = {ax: {v: 0 for v in AXIS_VERDICTS} for ax in AXES}
    cross: Dict[str, int] = {}
    example_ids: Dict[str, List[Tuple[str, str]]] = {v: [] for v in OVERALL_VERDICTS}
    # 缺口距离 = unknown 轴数。overall 恒 unknown 不等于零信息：d=1 的配对只差
    # 一轴声明即可判定，是数据补录的最高优先级目标。把 unknown 变成可排序的
    # 资产，而不是一个笼统的零信号。d1_bottleneck 即「补全某轴可解锁多少对」
    # 的上界，是数据飞轮的排序依据。
    gap_dist_counts: Dict[int, int] = {i: 0 for i in range(len(AXES) + 1)}
    d1_bottleneck: Dict[str, int] = {ax: 0 for ax in AXES}
    d1_examples: List[List[str]] = []
    n_d1_cap = max(8, examples_per_class * 4)

    n_ids = [n["id"] for n in nodes]
    for ida in n_ids:
        for idb in n_ids:  # 有序对，含自配对（自配对有物理意义：同件自证 identity）
            a_eff = eff[ida]
            b_eff = eff[idb]
            axis_v: Dict[str, str] = {}
            # 三轴同构：全部走 type_compat 查表。旧实现在 signal 分支另写一套
            # 互补判定，与 morphology_graph 的 type_compat 两处定义会悄悄分叉。
            for axis in AXES:
                ta_list, tb_list = a_eff[axis], b_eff[axis]
                if not ta_list or not tb_list:
                    axis_v[axis] = "unknown"
                else:
                    best = "unknown"
                    best_rank = -1
                    for ta in ta_list:
                        for tb in tb_list:
                            pv, _ = compat.pair_verdict(ta, tb)
                            if PAIR_RANK[pv] > best_rank:
                                best_rank = PAIR_RANK[pv]
                                best = pv
                    axis_v[axis] = AXIS_VERDICT_OF_PAIR[best]

            vals = list(axis_v.values())
            if "incompatible" in vals:
                ov = "type_error"
            elif "unknown" in vals:
                ov = "unknown"
            else:
                ov = "composed"
            overall_counts[ov] += 1
            if len(example_ids[ov]) < max(0, examples_per_class):
                example_ids[ov].append([ida, idb])  # list 而非 tuple：JSON 往返后类型稳定
            for ax in AXES:
                axis_marginals[ax][axis_v[ax]] += 1
            key = f"{axis_v['mechanical']}|{axis_v['electrical']}"
            cross[key] = cross.get(key, 0) + 1
            # 缺口距离：只在 overall == unknown 时统计。type_error 是「类型冲突」
            # 而非「证据缺口」，混进来会让 d1_bottleneck 语义混乱。
            # d=0 恒为 0（无缺口就不可能是 unknown）——保留该键作为不变量。
            if ov == "unknown":
                nd = sum(1 for v in vals if v == "unknown")
                gap_dist_counts[nd] += 1
                if nd == 1:
                    bottleneck = next(ax for ax in AXES if axis_v[ax] == "unknown")
                    d1_bottleneck[bottleneck] += 1
                    if len(d1_examples) < n_d1_cap:
                        d1_examples.append([ida, idb, bottleneck])

    return {
        "pairs_evaluated": len(n_ids) * len(n_ids),
        "overall_counts": overall_counts,
        "axis_marginals": axis_marginals,
        "mech_elec_cross": dict(sorted(cross.items())),
        "gap_distance": {str(k): v for k, v in sorted(gap_dist_counts.items())},
        "d1_bottleneck": d1_bottleneck,
        "d1_examples": d1_examples,
        "example_ids": {k: v for k, v in example_ids.items() if v},
    }


RULE_TABLE: List[Dict[str, str]] = [
    {
        "rule": "R0 evidence",
        "statement": "判定只认 status ∈ {declared, partial} 的端口；not_declared 只计 evidence。",
        "fail_mode": "not_declared 永不产生 compatible。",
    },
    {
        "rule": "R1 reflexivity",
        "statement": "ta == tb 且 type_compat 未显式登记 ⇒ identity（同型必配，类型系统自反性）。"
                     "显式登记的自配对裁决优先于本公理。",
        "fail_mode": "对本公理的适用范围要分清：几何规格型（同标号法兰）成立；"
                     "方向性角色型（OUTPUT_SPIKE~OUTPUT_SPIKE）不成立——两个输出端不是"
                     "「必然可装」而是「不互补」，必须由 type_compat 显式登记为 unknown。"
                     "旧实现无条件返回 identity，会让显式登记被静默覆盖（登记了等于没登记）。",
    },
    {
        "rule": "R2 lookup",
        "statement": "ta ≠ tb 查 type_compat（双向）；缺键 = unknown。",
        "fail_mode": "绝不按标号字面猜（fail-closed）。",
    },
    {
        "rule": "R3 best-pair",
        "statement": "轴 verdict = 所有端口对的最优证据：identity > adapter_required > unknown > incompatible。",
        "fail_mode": "全部 incompatible 才判 incompatible；存在 unknown 候选对时保守 unknown。",
    },
    {
        "rule": "R4 signal lookup",
        "statement": "signal 轴与机械/电气同构：一律走 type_compat 查表，"
                     "由 morphology_graph 的 build_type_compat 单一定义角色语义"
                     "（OUTPUT_SPIKE~INPUT_SENSORY = identity；同类端 = unknown；含 REWARD = unknown）。",
        "fail_mode": "本规则的唯一判据源是 type_compat。引擎内不得另写互补逻辑——"
                     "历史上 signal 判定曾在 _signal_axis 与 eval_all_pairs 各写一份，"
                     "两处语义一旦分叉，产物与引擎就悄悄不一致。REWARD 不参与正向判定。",
    },
    {
        "rule": "R5 precedence",
        "statement": "任一轴 incompatible ⇒ type_error；否则任一轴 unknown ⇒ unknown；否则 composed。",
        "fail_mode": "composed 不可能在有 unknown 轴时出现。",
    },
]

ROLES: Dict[str, Dict[str, Any]] = {
    "brain_side_candidates": {
        "categories": ["controllers", "chips"],
        "note": "主控/计算侧——compose 对称，此标注仅供下游选型参考，不是引擎前提。",
    },
    "body_side_candidates": {
        "categories": [
            "actuators", "flexible_actuators", "grippers", "sensors",
            "platforms", "bionic_mechanisms", "reducers", "structural",
        ],
        "note": "物理执行/感知侧。",
    },
    "auxiliary": {
        "categories": ["cables", "connectors", "pcb", "power", "data_acquisition"],
        "note": "辅助件——组合语义上作为被动连接面参与。",
    },
}
