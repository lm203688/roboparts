#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_assembly_typecheck — 产出 api/assembly_typecheck.json（Phase A · A3）。

对若干代表性候选集（形态图前 N 节点、按品类切片、随机样本）跑 assemble()，
落一份产物给前端 / MCP 工具 / CI 闸门读。

产物结构：
{
  "meta": {"version":..., "generated_at":..., "source":"api/morphology_graph.json"},
  "cases": [
    {"goal":..., "candidate_set":[...], "result":..., "witness"/"minimal_core":...},
    ...
  ],
  "summary": {
    "total_cases": N, "well_typed": X, "ill_typed": Y, "unknown": Z,
    "sample_size": K
  }
}

**与 MDV 对账**：对每条 ill_typed，检查 minimal_core 里节点在 evidence_valuation.json
里的 MDV 是否 ≥ 1。若发现某条 MDV=0，说明 core 里混了零价值节点——应判红。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from assembly_typecheck import assemble  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _load_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))


def _load_mdv_index() -> Dict[str, int]:
    """MDV 索引：entity_id::axis -> 边际可判定价值。"""
    ev = _load_json(ROOT / "api" / "evidence_valuation.json")
    return ev.get("entity_mdv_index") or {}


def _crosscheck_core_with_mdv(minimal_core: Dict[str, Any], mdv: Dict[str, int]) -> Dict[str, Any]:
    """核对 minimal core 里每个节点的 MDV（跨轴总和）。"""
    axis = minimal_core.get("bottleneck_axis", "")
    nodes = minimal_core.get("minimal_core") or []
    details = []
    all_positive = True
    total_mdv = 0
    for nid in nodes:
        key = f"{nid}::{axis}"
        v = mdv.get(key, 0)
        details.append({"node": nid, "axis": axis, "mdv": v})
        total_mdv += v
        if v < 1:
            all_positive = False
    return {
        "bottleneck_axis": axis,
        "core_size": len(nodes),
        "core_total_mdv": total_mdv,
        "all_positive": all_positive,
        "details": details,
    }


def _build_cases(graph: Dict[str, Any], sample_size: int = 6) -> List[Dict[str, Any]]:
    """构造代表性候选集。"""
    nodes = [n for n in graph.get("nodes", []) if n.get("composable", True)]
    nodes_by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for n in nodes:
        c = n.get("category") or "unknown"
        nodes_by_cat.setdefault(c, []).append(n)

    cases: List[Dict[str, Any]] = []
    # 1) 全形态图前 20 节点
    cases.append({
        "goal": "general multi-axis assembly",
        "candidate_set": [n["id"] for n in nodes[:20]],
        "description": "形态图前 20 节点（含 EOAT/actuator/sensor 混合）",
    })
    # 2) 单一品类切片
    for cat in ("grippers", "actuators", "sensors"):
        cat_nodes = nodes_by_cat.get(cat, [])
        if len(cat_nodes) >= 4:
            cases.append({
                "goal": f"assembly within {cat}",
                "candidate_set": [n["id"] for n in cat_nodes[:10]],
                "description": f"{cat} 品类前 10 节点",
            })
    # 3) 按角色搭配
    mixed = []
    for cat in ("actuators", "grippers", "sensors", "controllers"):
        mixed.extend([n["id"] for n in (nodes_by_cat.get(cat, [])[:3])])
    cases.append({
        "goal": "role-balanced robot arm",
        "candidate_set": mixed,
        "description": "actuator+gripper+sensor+controller 各取 3 个",
    })
    # 4) 随机样本
    import random
    rng = random.Random(20261015)
    pool = [n["id"] for n in nodes]
    sampled = rng.sample(pool, k=min(12, len(pool)))
    cases.append({
        "goal": "random candidate set",
        "candidate_set": sampled,
        "description": "形态图随机 12 节点（seed=20261015）",
    })

    return cases[:sample_size]


def main() -> int:
    graph = _load_json(ROOT / "api" / "morphology_graph.json")
    mdv_index = _load_mdv_index()

    cases = _build_cases(graph, sample_size=6)
    results = []
    for case in cases:
        result = assemble(case["goal"], case["candidate_set"], graph=graph)
        entry = {
            "goal": case["goal"],
            "description": case["description"],
            "candidate_count": len(case["candidate_set"]),
            "result": result["result"],
        }
        if result["result"] == "ill_typed" and "minimal_core" in result:
            entry["minimal_core"] = result["minimal_core"]
            entry["mdv_crosscheck"] = _crosscheck_core_with_mdv(
                result["minimal_core"], mdv_index
            )
        elif result["result"] == "well_typed":
            entry["witness"] = result.get("witness")
        elif result["result"] == "unknown":
            entry["reason"] = result.get("reason")
        results.append(entry)

    summary = {
        "total_cases": len(results),
        "well_typed": sum(1 for r in results if r["result"] == "well_typed"),
        "ill_typed": sum(1 for r in results if r["result"] == "ill_typed"),
        "unknown": sum(1 for r in results if r["result"] == "unknown"),
        "mdv_crosscheck_all_positive": all(
            r.get("mdv_crosscheck", {}).get("all_positive", True)
            for r in results if r["result"] == "ill_typed"
        ),
    }

    out = {
        "meta": {
            "version": "assembly_typecheck/v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "api/morphology_graph.json + scripts/assembly_typecheck.py",
            "engine": "compose_core/v1 + assembly_typecheck/v1",
        },
        "cases": results,
        "summary": summary,
        "note": (
            "装配级类型检查产物。well_typed = 存在良类型子装配；"
            "ill_typed = 无良类型子装配，minimal_core 给出最小缺失接口集；"
            "unknown = 证据不足。所有 ill_typed 的 core 都与 MDV 对账（B1 出口判据）。"
        ),
    }

    p = ROOT / "api" / "assembly_typecheck.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] wrote {p}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
