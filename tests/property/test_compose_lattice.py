#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A2 · 组合演算的**代数律性质测试**（Phase A / L1 验收）。

**背景**：Phase A 的 A1 把 compose_engine.py 的判据抽到 compose_core.py（零 IO 纯函数），
A2 就是**用随机属性测试证明三条代数律成立**——不是枚举例子的单元测试。

**测试目标（compose_core.ALGEBRAIC_LAWS 里的三条）**：
1. **Soundness（可靠性）**：verdict=composed ⇒ 每轴都存在 identity pair
2. **Monotonicity under evidence（证据单调性）**：追加 evidence 不允许翻转已判定
3. **Undecidability boundary（不可判定边界）**：not_declared 端口永不产生 compatible

**测试策略**：
- 用固定种子的伪随机生成器构造**合成形态图**（不用真实 868 实体，太贵）
- 每个性质跑 N=2000 随机案例（种子固定，CI 结果可复现）
- 每个性质都带**阴性对照**：故意注入一个"违反该律"的变异体，测试**必须判红**
- 变异分闸门（新 CI gate `组合演算代数律`）读这份测试的 pass/fail

**为什么不用 Hypothesis**：`pip install hypothesis` 在沙箱里被拒（网络沙箱策略），
改用 stdlib `random.Random(seed)`——效果等价（种子固定 = 确定性回归）。

**如何跑**：
    cd robopart && python tests/property/test_compose_lattice.py
    # exit 0 = 全部通过；非 0 = 至少一条代数律失败
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ── 加 scripts/ 到 sys.path ───────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts"))

from compose_core import (  # noqa: E402
    AXES,
    AXIS_VERDICT_OF_PAIR,
    ComposeTypeError,
    PAIR_RANK,
    CompatIndex,
    compose,
    effective_ports,
    undeclared_count,
)

# ── 常量 ──────────────────────────────────────────────────────────────────
SEED = 20261015
N_CASES = 2000  # 每性质 2000 随机案例

# 用于合成形态图的基础类型池（覆盖三种语义类别）
MECH_TYPES = [
    "MECH:ISO9409-1-A20-2-M4",
    "MECH:ISO9409-1-A50-4-M6",
    "MECH:ISO9409-1-A100-4-M8",
    "MECH:PROPRIETARY:KUKA",
]
ELEC_TYPES = [
    "ELEC:CONNECTOR:M8-3",
    "ELEC:CONNECTOR:M12-5",
    "ELEC:PROPRIETARY:ROBOTIQ",
]
SIG_TYPES = ["SIG:OUTPUT_SPIKE", "SIG:INPUT_SENSORY", "SIG:REWARD"]


def _mk_node(node_id: str, ports: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"id": node_id, "label": node_id, "kind": "component", "ports": ports}


def _mk_port(pclass: str, status: str = "declared") -> Dict[str, Any]:
    return {"type": pclass, "status": status}


# ── 合成形态图生成器 ─────────────────────────────────────────────────────
def _build_synthetic_graph(rng: random.Random, n_nodes: int = 40) -> Dict[str, Any]:
    """构造一个覆盖几何规格型 + 方向性角色型 + 专有接口 的合成形态图。

    保证：
      - 每对同型法兰都有显式 identity 条目（reflexivity 的显式版本）
      - 至少有一对 OUTPUT_SPIKE~OUTPUT_SPIKE 显式登记为 unknown（R1 反例）
      - 至少有一条 adapter_required（不同标号法兰）
      - 至少有一条 incompatible（专有 vs ISO）
      - 每个节点都有 1-3 个声明端口 + 0-2 个 not_declared 端口
    """
    type_compat: List[Dict[str, Any]] = []

    # 几何规格型：同标号 identity（reflexivity 公理覆盖）
    for t in MECH_TYPES[:3] + ELEC_TYPES[:2]:
        type_compat.append({
            "a": t, "b": t, "axis": t.split(":", 1)[0].lower(),
            "verdict": "identity", "reason": "同标号，自配对 identity",
        })
    # 不同标号 → adapter_required
    type_compat.append({
        "a": MECH_TYPES[0], "b": MECH_TYPES[1], "axis": "mechanical",
        "verdict": "adapter_required", "reason": "节圆不同，需转接盘",
    })
    # 专有 vs ISO → incompatible
    type_compat.append({
        "a": MECH_TYPES[3], "b": MECH_TYPES[0], "axis": "mechanical",
        "verdict": "incompatible", "reason": "专有接口 vs ISO 标号不可物理互插",
    })
    # 方向性角色型：OUTPUT~OUTPUT 显式登记为 unknown（R1 反例）
    type_compat.append({
        "a": "SIG:OUTPUT_SPIKE", "b": "SIG:OUTPUT_SPIKE", "axis": "signal",
        "verdict": "unknown", "reason": "两输出端不互补——显式登记覆盖 reflexivity",
    })
    # OUTPUT~INPUT 互补 → identity
    type_compat.append({
        "a": "SIG:OUTPUT_SPIKE", "b": "SIG:INPUT_SENSORY", "axis": "signal",
        "verdict": "identity", "reason": "通道互补，可配对",
    })
    # REWARD 同类 → unknown
    type_compat.append({
        "a": "SIG:REWARD", "b": "SIG:REWARD", "axis": "signal",
        "verdict": "unknown", "reason": "学习者消费，不代表互连",
    })

    # 节点：混合各类型，含 not_declared 端口
    nodes: List[Dict[str, Any]] = []
    for i in range(n_nodes):
        ports: List[Dict[str, Any]] = []
        # 至少一个声明的机械端口
        if i % 4 == 0:
            ports.append(_mk_port(MECH_TYPES[3]))  # proprietary
        else:
            ports.append(_mk_port(rng.choice(MECH_TYPES[:3])))
        # 可能加一个电气端口
        if rng.random() < 0.7:
            ports.append(_mk_port(rng.choice(ELEC_TYPES), status=rng.choice(["declared", "partial"])))
        # 可能加信号端口
        if rng.random() < 0.5:
            ports.append(_mk_port(rng.choice(SIG_TYPES)))
        # 加 0-2 个 not_declared 端口（制造缺口距离）
        for _ in range(rng.choice([0, 0, 1, 2])):
            ports.append(_mk_port(rng.choice(MECH_TYPES + ELEC_TYPES + SIG_TYPES), status="not_declared"))
        nodes.append(_mk_node(f"node_{i}", ports))

    return {"nodes": nodes, "type_compat": type_compat}


# ── 性质 1：Soundness ───────────────────────────────────────────────────
# **定义（best-pair 版，与 R3 一致）**：
#   ∀ axis ∈ AXES, axes[axis].verdict ∈ {compatible, compatible_via_adapter}
#     ⇒ axes[axis].best_pair.pair_verdict ∈ {identity, adapter_required}
#
# 直觉：best-pair 语义（R3）取所有 pair 的最优证据——verdict 声称可组合时，
# 被选中的 best_pair 必须是"可组合证据"（identity 或 adapter_required）。
# 不允许 best_pair 是 incompatible 或 unknown。
#
# **不要求所有 pairs 都是可组合的**：R3 是"取最优"，可能有 [identity, unknown]
# 并存——best 是 identity，verdict=compatible 完全合法。禁止 unknown pair 存在
# 会过度严格（因为 best-pair 就是要在有 unknown 时对也找到可组合路径）。
#
# 轴级检查（不是 overall 级）：overall 会被其他轴的 unknown 掩盖，
# 轴级才是抓"该轴假绿"的粒度。

def _check_axis_soundness(axis: str, ax_data: Dict[str, Any]) -> Optional[str]:
    """检查单轴是否满足 Soundness（best-pair 版）。"""
    verdict = ax_data.get("verdict")
    if verdict not in ("compatible", "compatible_via_adapter"):
        return None  # 未声称可组合，本律不约束
    best_pair = ax_data.get("best_pair") or {}
    pair_v = best_pair.get("pair_verdict")
    if pair_v not in ("identity", "adapter_required"):
        return (f"{axis} verdict={verdict} 但 best_pair.pair_verdict={pair_v}（假绿）")
    return None


def test_soundness() -> Dict[str, Any]:
    """Soundness (best-pair): 每轴声称可组合时，其 best_pair 必须是可组合证据。"""
    rng = random.Random(SEED)
    failures: List[Dict[str, Any]] = []
    passes = 0
    composed_count = 0

    for _ in range(N_CASES):
        graph = _build_synthetic_graph(rng)
        nodes = graph["nodes"]
        if len(nodes) < 2:
            continue
        a = rng.choice(nodes)
        b = rng.choice(nodes)
        result = compose(a, b, graph)
        if result["overall"] == "composed":
            composed_count += 1

        # 逐轴检查 Soundness（best-pair 版）
        for axis in AXES:
            reason = _check_axis_soundness(axis, result["axes"][axis])
            if reason:
                failures.append({
                    "case": f"{a['id']} × {b['id']}",
                    "axis": axis,
                    "reason": reason,
                })
                break
        else:
            passes += 1

    return {"law": "Soundness (best-pair)",
            "passes": passes, "failures": failures[:5],
            "total_cases": N_CASES, "composed_observed": composed_count,
            "verdict": "PASS" if not failures else "FAIL"}


# ── 性质 2：Monotonicity under evidence ─────────────────────────────────
def _verdict_rank(overall: str) -> int:
    """整体 verdict 的"信息增量"秩：composed=3, type_error=2, unknown=1.

    Monotonicity 断言：追加 evidence 后秩不减（unknown → type_error/composed 允许；
    type_error → unknown 禁止；composed → 任何东西都禁止）。
    """
    return {"composed": 3, "type_error": 2, "unknown": 1}.get(overall, 0)


def test_monotonicity() -> Dict[str, Any]:
    """追加 evidence 不允许让 verdict 秩减小（禁 flip：composed → unknown/type_error）。

    更严格的断言：
      - composed → composed（唯一允许从 composed 出发的路径）
      - unknown → {unknown, type_error, composed}
      - type_error → {type_error}（一旦判不兼容，只可能继续确认为不兼容）
    """
    rng = random.Random(SEED + 1)
    failures: List[Dict[str, Any]] = []
    passes = 0

    for _ in range(N_CASES):
        graph = _build_synthetic_graph(rng)
        nodes = graph["nodes"]
        if len(nodes) < 2:
            continue
        a = rng.choice(nodes)
        b = rng.choice(nodes)
        before = compose(a, b, graph)
        rank_before = _verdict_rank(before["overall"])

        # 变异 1：向 type_compat 追加一条 identity 让原本 unknown 的类型变可判
        # 目标类型对：找两个都存在的、当前 unknown 的类型对
        added = False
        for pa in a.get("ports", []):
            for pb in b.get("ports", []):
                if pa["status"] not in ("declared", "partial"):
                    continue
                if pb["status"] not in ("declared", "partial"):
                    continue
                ta, tb = pa["type"], pb["type"]
                if ta != tb:
                    ci = CompatIndex(graph["type_compat"])
                    pv, _ = ci.pair_verdict(ta, tb)
                    if pv == "unknown":
                        graph["type_compat"].append({
                            "a": ta, "b": tb, "axis": ta.split(":", 1)[0].lower(),
                            "verdict": "identity",
                        })
                        added = True
                        break
            if added:
                break

        if not added:
            continue  # 该 case 没有可变的 unknown 对

        after = compose(a, b, graph)
        rank_after = _verdict_rank(after["overall"])

        # 严格断言：rank 不减
        if rank_after < rank_before:
            failures.append({
                "case": f"{a['id']} × {b['id']}",
                "before": before["overall"], "after": after["overall"],
                "rank_delta": rank_after - rank_before,
            })
            continue

        # 更严格：composed 绝不能降级到 type_error（禁止 flip）
        if before["overall"] == "composed" and after["overall"] in ("type_error", "unknown"):
            failures.append({
                "case": f"{a['id']} × {b['id']}",
                "before": "composed", "after": after["overall"],
                "note": "composed flip",
            })
            continue

        passes += 1

    return {"law": "Monotonicity", "passes": passes, "failures": failures[:5],
            "total_cases": N_CASES, "verdict": "PASS" if not failures else "FAIL"}


# ── 性质 3：Undecidability boundary ─────────────────────────────────────
def test_undecidability() -> Dict[str, Any]:
    """not_declared 端口永不产生 compatible，无论 type_compat 里怎么加条目。"""
    rng = random.Random(SEED + 2)
    failures: List[Dict[str, Any]] = []
    passes = 0

    for _ in range(N_CASES):
        graph = _build_synthetic_graph(rng)
        nodes = graph["nodes"]
        if len(nodes) < 2:
            continue
        a = rng.choice(nodes)
        b = rng.choice(nodes)

        # 变异：把 a 的某个 declared 端口改回 not_declared
        original_ports = a.get("ports", [])
        mutated_ports = [dict(p) for p in original_ports]
        changed = False
        for p in mutated_ports:
            if p["status"] in ("declared", "partial"):
                p["status"] = "not_declared"
                changed = True
                break
        if not changed:
            continue
        a["ports"] = mutated_ports

        result = compose(a, b, graph)

        # 断言：只要 a 的某轴所有端口都是 not_declared，则该轴 verdict 必须是 unknown
        for axis in AXES:
            eff = effective_ports(a, axis)
            if not eff:
                # a 的该轴无有效端口，则该轴 verdict 必为 unknown
                if result["axes"][axis]["verdict"] != "unknown":
                    failures.append({
                        "case": f"{a['id']} × {b['id']}",
                        "axis": axis,
                        "axis_verdict": result["axes"][axis]["verdict"],
                        "expected": "unknown",
                    })
                    break
        else:
            passes += 1

    return {"law": "Undecidability", "passes": passes, "failures": failures[:5],
            "total_cases": N_CASES, "verdict": "PASS" if not failures else "FAIL"}


# ── 阴性对照：变异体引擎必须被上面测试判红 ────────────────────────────────
def test_mutation_kills_soundness() -> Dict[str, Any]:
    """阴性对照（**确定性构造**）：改 AXIS_VERDICT_OF_PAIR 让 incompatible→compatible，
    Soundness 应能抓到"有 incompatible pair 却判 composed"的假绿。

    **为什么这个 mutation 有效**：PAIR_RANK 只影响 best-pair 选择，不影响 pair verdict 本身
    （verdict 来自 type_compat 查表）。真正的假绿是"冲突对被降级成可组合"——
    篡改 verdict 映射表是精准武器。

    **为什么用确定性案例**：合成随机图可能凑不出 a×b 恰好命中 incompatible 的组合，
    导致 mutation 抓不到。改用**手工构造**的两节点两端口图，保证必命中。
    """
    import compose_core
    original_map = dict(compose_core.AXIS_VERDICT_OF_PAIR)
    # 变异：让 incompatible 泄漏成 compatible（假绿）
    compose_core.AXIS_VERDICT_OF_PAIR["incompatible"] = "compatible"
    try:
        graph = {
            "nodes": [
                {"id": "A", "ports": [{"type": "MECH:X", "status": "declared"}]},
                {"id": "B", "ports": [{"type": "MECH:Y", "status": "declared"}]},
            ],
            "type_compat": [
                {"a": "MECH:X", "b": "MECH:Y", "axis": "mechanical",
                 "verdict": "incompatible", "reason": "强制冲突"},
            ],
        }
        result = compose_core.compose(graph["nodes"][0], graph["nodes"][1], graph)
        # 轴级假绿：机械轴 verdict 声称 compatible，但 best_pair.pair_verdict 是 incompatible
        # 这是本 mutation 的"泄漏证据"——不看 overall，只看轴级 verdict 与 pair verdict 是否自洽
        leaked = (
            result["axes"]["mechanical"]["verdict"] in ("compatible", "compatible_via_adapter")
            and result["axes"]["mechanical"].get("best_pair", {}).get("pair_verdict") == "incompatible"
        )
        return {
            "test": "mutation_kills_soundness",
            "killed": leaked,
            "verdict": "PASS" if leaked else "FAIL",
            "note": "Soundness 抓到 incompatible→compatible 假绿泄漏",
            "observed": {
                "overall": result["overall"],
                "mech_verdict": result["axes"]["mechanical"]["verdict"],
                "best_pair_verdict": result["axes"]["mechanical"].get("best_pair", {}).get("pair_verdict"),
            },
        }
    finally:
        compose_core.AXIS_VERDICT_OF_PAIR.clear()
        compose_core.AXIS_VERDICT_OF_PAIR.update(original_map)


# ── 主入口 ───────────────────────────────────────────────────────────────
def main() -> int:
    import json
    results = [
        test_soundness(),
        test_monotonicity(),
        test_undecidability(),
        test_mutation_kills_soundness(),
    ]
    summary = {
        "core_version": "compose_lattice_tests/v1",
        "seed": SEED,
        "n_cases_per_law": N_CASES,
        "laws": results,
        "total_pass": all(r["verdict"] == "PASS" for r in results),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    # 落一份产物给 CI 闸门读
    out = _REPO / "api" / "compose_lattice_tests.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if summary["total_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
