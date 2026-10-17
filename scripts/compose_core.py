#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compose_core — RoboParts 组合演算的**纯函数内核**（Phase A · L1）。

**本模块的设计契约**（Phase A / A1 硬约束）：
1. **零 IO**：本文件不 import json / open / os / pathlib / sys.exit，也不做网络。
   判定层的所有函数只吃 dict / list，只返回 dict / tuple / enum。**唯一入口是 dict**。
2. **零全局状态**：除本文件顶部定义的常量与 ROLES 外，不写任何可变全局。
3. **零副作用**：所有函数（除类型构造）都是纯函数——同输入必同输出、无外部观测。
4. **单一判据源**：所有 pair verdict 一律走 CompatIndex.pair_verdict，
   禁止在本内核里另写"互补规则"（R4 教训：曾经分叉过）。

**为什么要抽出这个模块**：
- 旧的 compose_engine.py 把「判据 + IO（读 morphology_graph、写 compose_semantics.json）」混在一起，
  导致 A2 的**性质测试**（Property-based testing）只能靠 monkey-patch 注入证据，
  而且 mutation-score.json 的 honest_limits 已明确点名：
  「S2 抽出 compose_core 后可升级到引擎层」。
- 抽出后：
  - tests/property/test_compose_lattice.py 直接对 compose_core.compose() 做随机属性测试；
  - 变异闸门可以在 compose_core 上打点（比打在生产入口 compose_engine 上更精准）；
  - A3 的 assemble() 原语直接复用本内核的判定，不再需要重写 pair 逻辑。

**代数律（A2 要证明的三条，本模块必须满足）**：
- **Soundness**：compose(a,b)=composed ⇒ 每轴至少存在一个 identity pair。
- **Monotonicity under evidence**：给同一 (a,b) 追加任何 evidence，
  verdict 只能沿 lattice {composed ≤ compatible_via_adapter ≤ unknown ≤ type_error} 的「信息增量」方向移动，
  禁止 decided 翻转。
- **Undecidability boundary**：not_declared 端口不参与判定，
  故"可判但缺字段"（evidence gap）与"本质不可判"（proprietary）在本内核里语义可分。

**版本**：compose_core/v1（与 compose_engine/v1 同源；本文件是它的纯函数提取）。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

# ── 元信息 ────────────────────────────────────────────────────────────────
CORE_VERSION = "compose_core/v1"
ENGINE_VERSION = "compose_engine/v1"  # 保持向后兼容的 engine_version 字段值

# ── 三轴（B2 类型语义）───────────────────────────────────────────────────
AXES: Tuple[str, ...] = ("mechanical", "electrical", "signal")

_PREFIX_AXIS = {"MECH": "mechanical", "ELEC": "electrical", "SIG": "signal"}

# ── R0：只认 status ∈ {declared, partial} 的端口 ─────────────────────────
EFFECTIVE_STATUS = frozenset(("declared", "partial"))

# ── R3：best-pair 语义（数值大者胜）──────────────────────────────────────
PAIR_RANK: Dict[str, int] = {
    "identity": 3,
    "adapter_required": 2,
    "unknown": 1,
    "incompatible": 0,
}

# ── pair verdict → 轴 verdict ────────────────────────────────────────────
AXIS_VERDICT_OF_PAIR: Dict[str, str] = {
    "identity": "compatible",
    "adapter_required": "compatible_via_adapter",
    "unknown": "unknown",
    "incompatible": "incompatible",
}

# ── verdict 集合（用于 lattice 测试与三态守恒闸门）───────────────────────
PAIR_VERDICTS = ("identity", "adapter_required", "unknown", "incompatible")
AXIS_VERDICTS = ("compatible", "compatible_via_adapter", "incompatible", "unknown")
OVERALL_VERDICTS = ("composed", "type_error", "unknown")

# ── 信号端口的规范符号（角色互补的锚点，判据源仍是 type_compat）───────────
SIG_OUTPUT = "SIG:OUTPUT_SPIKE"
SIG_INPUT = "SIG:INPUT_SENSORY"
SIG_REWARD = "SIG:REWARD"


class ComposeTypeError(ValueError):
    """输入不构成可判定对象（结构性错误，非三态裁决）。

    与「unknown」严格区分：
    - ComposeTypeError = 节点缺 id / 类型错误 → 引擎拒收，raise
    - unknown         = 三态裁决之一 → 引擎接收，返回 verdict="unknown"
    """


# ── 基本访问器 ────────────────────────────────────────────────────────────
def axis_of(port_type: str) -> Optional[str]:
    """端口类型前缀 → 轴名。无前缀返回 None。"""
    if ":" not in port_type:
        return None
    return _PREFIX_AXIS.get(port_type.split(":", 1)[0])


def _ports_of(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    return node.get("ports") or []


def effective_ports(node: Dict[str, Any], axis: str) -> List[Dict[str, Any]]:
    """该轴上带声明证据的端口。not_declared 端口不参与判定。"""
    return [
        p
        for p in _ports_of(node)
        if axis_of(p.get("type", "")) == axis and p.get("status") in EFFECTIVE_STATUS
    ]


def undeclared_count(node: Dict[str, Any], axis: str) -> int:
    """该轴上未声明端口数——用于缺口距离 / d1_bottleneck。"""
    return sum(
        1
        for p in _ports_of(node)
        if axis_of(p.get("type", "")) == axis and p.get("status") not in EFFECTIVE_STATUS
    )


# ── CompatIndex：type_compat 双向索引 + reflexivity 公理 ───────────────────
class CompatIndex:
    """type_compat 双向索引 + reflexivity 公理。缺键一律 unknown。

    **公理 R1（reflexivity）**：ta == tb 且未显式登记 ⇒ identity。
    适用范围严格区分：
    - **几何规格型**类型（A50-4-M6 法兰）：成立——同标号必然可装。
    - **方向性角色型**类型（OUTPUT_SPIKE）：**不成立**——两输出端不互补，
      必须由 type_compat 显式登记为 unknown。
    本类尊重显式登记：**显式登记的自配对裁决优先于 reflexivity 公理**。
    历史上无条件返回 identity 会静默覆盖显式登记，登记了等于没登记。
    """

    __slots__ = ("_index",)

    def __init__(self, type_compat: Iterable[Dict[str, Any]]):
        self._index: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for entry in type_compat or []:
            if not isinstance(entry, dict) or "a" not in entry or "b" not in entry:
                continue
            key = (entry["a"], entry["b"])
            # 后写的优先——同一 (a,b) 若有多条，最后一条生效。
            # 这是有意的（便于 CI 里注入变异体做自证），不是巧合。
            self._index[key] = entry

    def __len__(self) -> int:
        return len(self._index)

    def has(self, ta: str, tb: str) -> bool:
        """判断双向索引是否有 (ta,tb) 或 (tb,ta) 记录。"""
        return (ta, tb) in self._index or (tb, ta) in self._index

    def pair_verdict(self, ta: str, tb: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """返回 (pair_verdict, entry|None)。entry 仅索引命中时非空。"""
        if ta == tb:
            entry = self._index.get((ta, tb))
            if entry is not None:
                return (entry.get("verdict", "unknown"), entry)
            return ("identity", None)  # 未登记 ⇒ reflexivity 公理
        entry = self._index.get((ta, tb)) or self._index.get((tb, ta))
        if entry is None:
            return ("unknown", None)
        return (entry.get("verdict", "unknown"), entry)


# ── 轴内判定 ──────────────────────────────────────────────────────────────
def _mech_elec_axis(
    a_eff: List[Dict[str, Any]],
    b_eff: List[Dict[str, Any]],
    compat: CompatIndex,
) -> Dict[str, Any]:
    """R3 best-pair 语义：多端口零件组合只需一对可配。

    轴 verdict = 所有端口对的最优证据：identity > adapter_required > unknown > incompatible。
    全部 incompatible 才判 incompatible；存在 unknown 候选对时保守判 unknown。
    """
    pairs_eval: List[Dict[str, Any]] = []
    best_rank = -1
    best: Optional[Dict[str, Any]] = None
    for pa in a_eff:
        for pb in b_eff:
            verdict, entry = compat.pair_verdict(pa["type"], pb["type"])
            rec: Dict[str, Any] = {
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

    本函数只负责两件事：
      1. 产出**结构化通道证据**（sensory_links / reward）
      2. 把「哪一轴可组合」的判据交给 CompatIndex

    **R4 教训**：历史上把 OUTPUT~INPUT 互补逻辑硬编码在两处（本函数与 eval_all_pairs），
    两处语义一旦分叉，产物与引擎就会悄悄不一致。所有 pair verdict 走 CompatIndex。

    **REWARD 端口**：是"学习者消费奖励"，双方各有 REWARD 不代表互连，
    只记 evidence，不参与正向判定（fail-closed）。
    """
    a_ports = effective_ports(a_node, "signal")
    b_ports = effective_ports(b_node, "signal")
    a_ids = sorted({p["type"] for p in a_ports})
    b_ids = sorted({p["type"] for p in b_ports})
    links: List[str] = []
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
    best_rec: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    for ta in a_ids:
        for tb in b_ids:
            pv, entry = compat.pair_verdict(ta, tb)
            if PAIR_RANK[pv] > best_rank:
                best_rank = PAIR_RANK[pv]
                best_pv = pv
                best_rec = {"a_type": ta, "b_type": tb, "pair_verdict": pv}
                if entry:
                    best_rec["reason"] = entry.get("reason")
                reason = entry.get("reason") if entry else None
    out = dict(base, verdict=AXIS_VERDICT_OF_PAIR[best_pv])
    if best_rec is not None:
        out["best_pair"] = best_rec
    if reason:
        out["reason"] = reason
    return out


# ── 主入口：compose ──────────────────────────────────────────────────────
def compose(a: Dict[str, Any], b: Dict[str, Any], graph: Dict[str, Any]) -> Dict[str, Any]:
    """对称组合裁决。graph 为 morphology_graph.json 反序列化对象。

    **fail-closed**：结构性错误（节点缺 id）抛 ComposeTypeError；
    三态裁决（composed / type_error / unknown）永远不抛异常。

    **R5 优先级**：任一轴 incompatible ⇒ type_error；否则任一轴 unknown ⇒ unknown；否则 composed。
    """
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
        "core_version": CORE_VERSION,
        "engine_version": ENGINE_VERSION,
        "node_a": a["id"],
        "node_b": b["id"],
        "overall": overall,
        "axes": axes,
    }


# ── 全对评测：eval_all_pairs ─────────────────────────────────────────────
def eval_all_pairs(
    graph: Dict[str, Any], examples_per_class: int = 0
) -> Dict[str, Any]:
    """全对评测（含自配对）：聚合计数 + 交叉表。确定性，无随机。

    只回聚合，不回逐对结果（35 万对逐对落盘既无必要也不可审计）。
    examples_per_class > 0 时，按遍历序为每个总裁决类别收集前 N 个 (node_a, node_b)。
    """
    nodes = [n for n in graph.get("nodes") or [] if n.get("composable", True)]
    compat = CompatIndex(graph.get("type_compat") or [])

    # 预取每节点每轴的 effective 类型集合
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
    example_ids: Dict[str, List[List[str]]] = {v: [] for v in OVERALL_VERDICTS}
    gap_dist_counts: Dict[int, int] = {i: 0 for i in range(len(AXES) + 1)}
    d1_bottleneck: Dict[str, int] = {ax: 0 for ax in AXES}
    d1_examples: List[List[str]] = []
    n_d1_cap = max(8, examples_per_class * 4)

    n_ids = [n["id"] for n in nodes]
    for ida in n_ids:
        for idb in n_ids:
            a_eff = eff[ida]
            b_eff = eff[idb]
            axis_v: Dict[str, str] = {}
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
                example_ids[ov].append([ida, idb])
            for ax in AXES:
                axis_marginals[ax][axis_v[ax]] += 1
            key = f"{axis_v['mechanical']}|{axis_v['electrical']}"
            cross[key] = cross.get(key, 0) + 1
            if ov == "unknown":
                nd = sum(1 for v in vals if v == "unknown")
                gap_dist_counts[nd] += 1
                if nd == 1:
                    bottleneck = next(ax for ax in AXES if axis_v[ax] == "unknown")
                    d1_bottleneck[bottleneck] += 1
                    if len(d1_examples) < n_d1_cap:
                        d1_examples.append([ida, idb, bottleneck])

    return {
        "core_version": CORE_VERSION,
        "pairs_evaluated": len(n_ids) * len(n_ids),
        "overall_counts": overall_counts,
        "axis_marginals": axis_marginals,
        "mech_elec_cross": dict(sorted(cross.items())),
        "gap_distance": {str(k): v for k, v in sorted(gap_dist_counts.items())},
        "d1_bottleneck": d1_bottleneck,
        "d1_examples": d1_examples,
        "example_ids": {k: v for k, v in example_ids.items() if v},
    }


# ── 规则表（R0–R5，A2 性质测试的规范文本）────────────────────────────────
RULE_TABLE: List[Dict[str, str]] = [
    {
        "rule": "R0 evidence",
        "statement": "判定只认 status ∈ {declared, partial} 的端口；not_declared 只计 evidence。",
        "fail_mode": "not_declared 永不产生 compatible。",
    },
    {
        "rule": "R1 reflexivity",
        "statement": "ta == tb 且 type_compat 未显式登记 ⇒ identity（同型必配）。显式登记的自配对裁决优先于本公理。",
        "fail_mode": (
            "对本公理的适用范围要分清：几何规格型（同标号法兰）成立；"
            "方向性角色型（OUTPUT_SPIKE~OUTPUT_SPIKE）不成立——两个输出端不是「必然可装」"
            "而是「不互补」，必须由 type_compat 显式登记为 unknown。"
            "旧实现无条件返回 identity，会让显式登记被静默覆盖（登记了等于没登记）。"
        ),
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
        "statement": (
            "signal 轴与机械/电气同构：一律走 type_compat 查表，"
            "由 morphology_graph 的 build_type_compat 单一定义角色语义"
            "（OUTPUT_SPIKE~INPUT_SENSORY = identity；同类端 = unknown；含 REWARD = unknown）。"
        ),
        "fail_mode": (
            "本规则的唯一判据源是 type_compat。引擎内不得另写互补逻辑——"
            "历史上 signal 判定曾在 _signal_axis 与 eval_all_pairs 各写一份，"
            "两处语义一旦分叉，产物与引擎就悄悄不一致。REWARD 不参与正向判定。"
        ),
    },
    {
        "rule": "R5 precedence",
        "statement": "任一轴 incompatible ⇒ type_error；否则任一轴 unknown ⇒ unknown；否则 composed。",
        "fail_mode": "composed 不可能在有 unknown 轴时出现。",
    },
]


# ── 角色标注（不是引擎前提，仅供下游选型参考）──────────────────────────────
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


# ── 三条代数律的形式化描述（A2 测试的对照文本）───────────────────────────
ALGEBRAIC_LAWS: List[Dict[str, str]] = [
    {
        "name": "Soundness（可靠性）",
        "statement": (
            "compose(a,b) = composed ⇒ 每一轴都至少存在一个 pair verdict = identity。"
            "等价于：在已声明公理下，每个可组合的轴都有物理装配的可能（同型或显式判定可配）。"
        ),
        "test_strategy": "遍历所有 verdict=composed 的对，验证每轴 pairs_evaluated 中存在 identity。",
        "counterexample_source": "若某轴 verdict=compatible_via_adapter 也算 compatible，"
                                 "则该对不算 composed；若 identity 存在但 verdict 未反映，测试应判红。",
    },
    {
        "name": "Monotonicity under evidence（证据单调性）",
        "statement": (
            "给定同一对节点 (a,b)，向 type_compat 追加任何一条 evidence：\n"
            "  - 允许：unknown → compatible / compatible_via_adapter / type_error（从『不知道』变『知道』）\n"
            "  - 禁止：compatible → incompatible / unknown（已判定的翻转）\n"
            "  - 禁止：composed → type_error / unknown（一旦能装，新证据不允许证明不能装）"
        ),
        "test_strategy": (
            "对每个随机 (a,b) 生成初始 verdict，然后对每个未知类型对注入一条 identity evidence，"
            "重新计算 verdict；断言整体 verdict 只能从 {unknown, type_error} → {composed, type_error} "
            "或保持不动，绝不允许 composed → unknown/type_error。"
        ),
        "counterexample_source": "变体引擎里让 adapter_required 也算 identity 的降级路径 → 必须判红。",
    },
    {
        "name": "Undecidability boundary（不可判定边界）",
        "statement": (
            "not_declared 端口不参与判定，因此：\n"
            "  - 「可判但缺字段」（evidence gap）：某轴全为 not_declared，可补一条 → 从 unknown 变 decided\n"
            "  - 「本质不可判」（proprietary）：接口未标准化，即使补全也无法从标号查表 → 仍 unknown\n"
            "本内核通过 undeclared_count() 与 effective_ports() 把两者显式区分开。"
        ),
        "test_strategy": (
            "构造一个专有接口（PROPRIETARY:XX），无论 type_compat 里怎么加条目，"
            "只要端口类型不匹配就仍 unknown。"
        ),
        "counterexample_source": "若实现里给所有 not_declared 端口偷偷补 default 端口 → 测试应判红。",
    },
]


__all__ = [
    "CORE_VERSION", "ENGINE_VERSION",
    "AXES", "PAIR_RANK", "AXIS_VERDICT_OF_PAIR",
    "PAIR_VERDICTS", "AXIS_VERDICTS", "OVERALL_VERDICTS",
    "EFFECTIVE_STATUS",
    "SIG_OUTPUT", "SIG_INPUT", "SIG_REWARD",
    "ComposeTypeError",
    "axis_of", "effective_ports", "undeclared_count",
    "CompatIndex",
    "compose", "eval_all_pairs",
    "RULE_TABLE", "ROLES", "ALGEBRAIC_LAWS",
]
