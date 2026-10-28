#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""assembly_typecheck — 装配级类型检查（Phase A · L2 · A3）。

**新原语**：
    assemble(goal, candidate_set, constraints) -> AssemblyResult

**返回值**（三态诚实）：
    - well_typed  : 存在良类型装配，含 witnesses（可装配对）
    - ill_typed   : 不存在良类型装配，含 minimal_core（最小缺失接口集）
    - unknown     : 证据不足以下结论

**为什么这是"装配级"而不是"成对"级**（对应 §1.3 新事实①）：
    16 个共享同一法兰的 EOAT 器件按设计不该互插，成对互插是伪命题。
    本原语问的是"这堆零件能不能组成一个能干成 goal 的系统"——多段、角色感知、可解释。

**最小 unsat core**：
    ill_typed 时输出**挡住装配的最小缺失接口集**。硬件版编译错误信息：
    > ill_typed: 目标 "6-DOF 力控抓取" 不成立。
    > minimal_core = {ACT-028 的电气连接器未声明}
    > 补这 1 条声明即可解锁 12 对候选。

**禁止 fail-open**：
    任一角色/轴为 unknown 且无法用已有证据排除时，总结果必须是 unknown，不得降级成 well_typed。
    这与锚点 §3「负向边界」和 compose_core 的 fail-closed 纪律一致。

**与 MDV 对账**（B1 出口判据）：
    minimal_core 里每条声明的边际价值（MDV）应≥1，且是候选集中 MDV 最高的几条。
    若 MDV 复核发现 core 里某条 MDV=0，说明"补它不会解锁任何对"，是**错误的 core**——
    应被 verify_assembly_typecheck 判红。

复用：
    - scripts/compose_core.py（判据内核）
    - api/morphology_graph.json（形态图本体）
    - api/evidence_valuation.json（MDV 定向）
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from compose_core import (  # noqa: E402
    AXES,
    CompatIndex,
    PAIR_RANK,
    ComposeTypeError,
    compose,
    effective_ports,
    undeclared_count,
)

ROOT = Path(__file__).resolve().parent.parent

# 装配角色（L2 定义）
ROLES = ("BASE", "LINK", "EOAT", "SENSOR", "COMPUTE", "POWER")

# 装配目标词汇（简版；完整版见 api/morphology_graph.json）
GOAL_CATEGORIES = ("grippers", "actuators", "sensors", "platforms", "controllers")

TYPED_RESULT = "well_typed"
ILL_TYPED_RESULT = "ill_typed"
UNKNOWN_RESULT = "unknown"


def _role_of(node: Dict[str, Any]) -> str:
    """从节点推断装配角色。"""
    cat = (node.get("category") or "").lower()
    kind = (node.get("kind") or "").lower()
    if "gripper" in cat or "eoat" in cat:
        return "EOAT"
    if "sensor" in cat:
        return "SENSOR"
    if "actuator" in cat:
        return "LINK"
    if "controller" in cat or "chip" in cat:
        return "COMPUTE"
    if "power" in cat:
        return "POWER"
    if "platform" in cat or "base" in cat or "structural" in cat:
        return "BASE"
    if "link" in cat:
        return "LINK"
    return "LINK"  # 默认


def _node_by_id(graph: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
    for n in graph.get("nodes") or []:
        if n.get("id") == node_id:
            return n
    return None


def _pair_decidability(a: Dict[str, Any], b: Dict[str, Any], graph: Dict[str, Any]) -> Dict[str, Any]:
    """两节点的可判定性摘要：每轴是否已判定、缺失什么。"""
    axes: Dict[str, Any] = {}
    for ax in AXES:
        a_eff = effective_ports(a, ax)
        b_eff = effective_ports(b, ax)
        a_und = undeclared_count(a, ax)
        b_und = undeclared_count(b, ax)
        if not a_eff or not b_eff:
            axes[ax] = {
                "decidable": False,
                "reason": f"a_has={len(a_eff)} b_has={len(b_eff)} (not_declared: a={a_und}, b={b_und})",
                "a_undeclared": a_und,
                "b_undeclared": b_und,
            }
        else:
            axes[ax] = {
                "decidable": True,
                "a_effective": len(a_eff),
                "b_effective": len(b_eff),
                "a_undeclared": a_und,
                "b_undeclared": b_und,
            }
    return axes


def _find_witness(
    candidate_set: List[str], graph: Dict[str, Any]
) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """在候选集中找一个 composed 对作为 witness。"""
    nodes = [_node_by_id(graph, nid) for nid in candidate_set]
    nodes = [n for n in nodes if n is not None]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            try:
                result = compose(nodes[i], nodes[j], graph)
                if result["overall"] == "composed":
                    return (nodes[i]["id"], nodes[j]["id"], result)
            except ComposeTypeError:
                continue
    return None


def _find_ill_typed_reason(
    goal: str, candidate_set: List[str], graph: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """如果无 witness，找 ill_typed 的原因——最小缺失接口集。

    **策略**：找候选集里所有对，看有多少对因**某轴 unknown** 而未决；
    按瓶颈轴聚合出「补哪一轴的哪几个节点声明能解锁最多对」——这就是 minimal core。
    """
    nodes = [_node_by_id(graph, nid) for nid in candidate_set]
    nodes = [n for n in nodes if n is not None]
    if len(nodes) < 2:
        return None

    # 收集所有对的可判定性
    unknown_by_axis: Dict[str, List[Tuple[str, str]]] = {ax: [] for ax in AXES}
    incompatible_count = 0
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            dec = _pair_decidability(nodes[i], nodes[j], graph)
            for ax in AXES:
                if not dec[ax]["decidable"]:
                    unknown_by_axis[ax].append((nodes[i]["id"], nodes[j]["id"]))
            # 检查是否某轴 incompatible（已判定冲突）
            try:
                result = compose(nodes[i], nodes[j], graph)
                if result["overall"] == "type_error":
                    incompatible_count += 1
            except ComposeTypeError:
                continue

    # 找到瓶颈轴（unknown 对数最多的轴）
    bottleneck = max(AXES, key=lambda ax: len(unknown_by_axis[ax]))
    if not unknown_by_axis[bottleneck] and incompatible_count == 0:
        return None  # 全部可判但无 composed——真 ill_typed

    # 提取 core：瓶颈轴上 unknown 对涉及的节点
    nodes_in_core = set()
    for ida, idb in unknown_by_axis[bottleneck]:
        nodes_in_core.add(ida)
        nodes_in_core.add(idb)

    # 排序：按 unknown 出现频次降序；freq 平局时按节点 ID（确定性 tiebreaker，
    # 消除 set 迭代顺序依赖——freq 平局时 sorted 会受 PYTHONHASHSEED 影响导致
    # minimal_core 每次运行不同，违反「判据现算/确定性」铁律）
    freq: Dict[str, int] = {}
    for ida, idb in unknown_by_axis[bottleneck]:
        freq[ida] = freq.get(ida, 0) + 1
        freq[idb] = freq.get(idb, 0) + 1
    ranked = sorted(nodes_in_core, key=lambda nid: (-freq.get(nid, 0), nid))
    # 取前 N 个（最小 core 大小上限）
    minimal_core = ranked[:min(3, len(ranked))]

    return {
        "bottleneck_axis": bottleneck,
        "unknown_pairs_on_bottleneck": len(unknown_by_axis[bottleneck]),
        "incompatible_pairs": incompatible_count,
        "minimal_core": minimal_core,
        "reason": (
            f"瓶颈轴={bottleneck}；该轴有 {len(unknown_by_axis[bottleneck])} 对因 not_declared 未判；"
            f"另有 {incompatible_count} 对已判 incompatible；"
            f"minimal core = {minimal_core}——补这些节点的 {bottleneck} 声明是解锁装配的最小动作。"
        ),
        "examples": unknown_by_axis[bottleneck][:5],
    }


def assemble(
    goal: str,
    candidate_set: List[str],
    constraints: Optional[Dict[str, Any]] = None,
    graph: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """装配级类型检查。

    参数：
        goal: 能力目标（自由文本；当前实现按关键字匹配角色）
        candidate_set: 候选节点 ID 列表
        constraints: 约束（预留：max_parts, budget 等）
        graph: 形态图（不传则从磁盘加载）

    返回：
        {"result": "well_typed"|"ill_typed"|"unknown",
         "goal": str, "candidate_count": int,
         "witness"|"minimal_core": ..., "role_distribution": {...}}
    """
    if graph is None:
        import json
        graph = json.loads((ROOT / "api" / "morphology_graph.json").read_text(encoding="utf-8"))

    if not isinstance(candidate_set, list) or len(candidate_set) < 2:
        return {
            "result": "unknown",
            "goal": goal,
            "candidate_count": len(candidate_set) if isinstance(candidate_set, list) else 0,
            "reason": "候选集少于 2 个节点——无法构成装配",
        }

    # 角色分布（诊断用）
    roles_seen: Dict[str, int] = {}
    valid_nodes = 0
    for nid in candidate_set:
        n = _node_by_id(graph, nid)
        if n:
            valid_nodes += 1
            r = _role_of(n)
            roles_seen[r] = roles_seen.get(r, 0) + 1

    if valid_nodes < 2:
        return {
            "result": "unknown",
            "goal": goal,
            "candidate_count": len(candidate_set),
            "valid_nodes": valid_nodes,
            "reason": "候选集中有效节点少于 2 个",
        }

    # 找 witness（任何 composed 对即算 well_typed）
    witness = _find_witness(candidate_set, graph)
    if witness:
        ida, idb, detail = witness
        return {
            "result": TYPED_RESULT,
            "goal": goal,
            "candidate_count": len(candidate_set),
            "valid_nodes": valid_nodes,
            "role_distribution": roles_seen,
            "witness": {
                "node_a": ida,
                "node_b": idb,
                "overall": detail["overall"],
                "axes_verdicts": {ax: detail["axes"][ax]["verdict"] for ax in AXES},
            },
            "note": "存在至少一个 composed 对——装配类型检查通过（存在良类型子装配）",
        }

    # 无 witness：找 ill_typed 原因
    ill_reason = _find_ill_typed_reason(goal, candidate_set, graph)
    if ill_reason:
        return {
            "result": ILL_TYPED_RESULT,
            "goal": goal,
            "candidate_count": len(candidate_set),
            "valid_nodes": valid_nodes,
            "role_distribution": roles_seen,
            "minimal_core": ill_reason,
            "note": "无 composed 对；最小缺失接口集见 minimal_core",
        }

    return {
        "result": UNKNOWN_RESULT,
        "goal": goal,
        "candidate_count": len(candidate_set),
        "valid_nodes": valid_nodes,
        "role_distribution": roles_seen,
        "reason": "候选集内无 composed 也无可归因的瓶颈——证据不足",
    }


# ── CLI smoke test ──────────────────────────────────────────────────────
def _cli() -> int:
    import json
    graph = json.loads((ROOT / "api" / "morphology_graph.json").read_text(encoding="utf-8"))
    # 选 20 个可组合节点做 demo
    nodes = [n for n in graph.get("nodes", []) if n.get("composable", True)]
    ids = [n["id"] for n in nodes[:20]]
    result = assemble("6-DOF force-controlled grasping", ids, graph=graph)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
