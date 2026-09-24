#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_compose_semantics — 生成 api/compose_semantics.json（B1/B2 语义导出）。

内容全部现算，禁手写数字：
- rule_table / roles：引擎常量导出（与 compose_engine.py 同源）
- aggregates：593² 全对评测聚合（eval_all_pairs）
- examples：每个出现的总裁决类别取 2 个确定性判例（sorted 取首），附完整引擎证据

单一真相源：api/morphology_graph.json（其真值源链见其 meta.truth_sources）。
meta.access 由注入器受管，本构建器不产出。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from compose_engine import (  # noqa: E402
    ENGINE_VERSION,
    ROLES,
    RULE_TABLE,
    AXES,
    OVERALL_VERDICTS,
    compose,
    eval_all_pairs,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_PATH = os.path.join(ROOT, "api", "morphology_graph.json")
OUT_PATH = os.path.join(ROOT, "api", "compose_semantics.json")

EXAMPLES_PER_CLASS = 2


def _now_cn() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def _pick_examples(graph, aggregates):
    """对聚合计数里出现的每个总裁决类别，取确定性判例并算完整引擎证据。"""
    nodes = {n["id"]: n for n in graph["nodes"] if n.get("composable", True)}
    examples = []
    for cls, id_pairs in aggregates.get("example_ids", {}).items():
        for a, b in id_pairs[:EXAMPLES_PER_CLASS]:
            examples.append(compose(nodes[a], nodes[b], graph))
    return examples


def build(with_timestamp: bool = True, graph: dict | None = None):
    if graph is None:
        with open(GRAPH_PATH, encoding="utf-8") as f:
            graph = json.load(f)

    aggregates = eval_all_pairs(graph, examples_per_class=EXAMPLES_PER_CLASS)
    examples = _pick_examples(graph, aggregates)

    # 算术守卫（fail-fast）：聚合计数必须自洽
    total = aggregates["pairs_evaluated"]
    if sum(aggregates["overall_counts"].values()) != total:
        raise SystemExit("fail-fast: overall_counts 之和不等于 pairs_evaluated")
    for ax in AXES:
        if sum(aggregates["axis_marginals"][ax].values()) != total:
            raise SystemExit(f"fail-fast: axis_marginals[{ax}] 之和不等于 pairs_evaluated")

    # 角色标注：现算每类节点数，不手写
    cat_counts = {}
    for n in graph["nodes"]:
        c = n.get("category")
        if c:
            cat_counts[c] = cat_counts.get(c, 0) + 1
    roles = {}
    for role, spec in ROLES.items():
        roles[role] = {
            "categories": spec["categories"],
            "node_count": sum(cat_counts.get(c, 0) for c in spec["categories"]),
            "note": spec["note"],
        }

    meta = {
        "schema": "compose_semantics/v1",
        "title": "RoboParts 组合语义（Compose Semantics）——三轴效应系统原型",
        "description": (
            "把「两个零件能不能组成一个具身系统」从散文变成可判定函数："
            "compose(a, b) 在机械/电气/信号三轴上做类型裁决，"
            "总裁决三态（composed / type_error / unknown），fail-closed——"
            "无证据的轴恒为 unknown，绝不按标号字面猜测。"
            "这是方向锚点 Phase B1/B2 的形式化底座原型（轻量 effect system，非 Lean）。"
        ),
        "anchor": "docs/PROJECT_DIRECTIONS_V2.md §1（方向锚点 v2.2）",
        "roadmap": "docs/direction-evolution-roadmap-20260923.md Phase B1/B2",
        "engine_version": ENGINE_VERSION,
        "generated_by": "scripts/build_compose_semantics.py",
        "truth_sources": ["api/morphology_graph.json", "scripts/compose_engine.py"],
        "honest_limits": [
            "composed 的归因**必须现读 aggregates**，不要复述历史口径。此前记作"
            "「SIG 全 not_declared 导致 composed=0」——那是 2026-09-23 之前的状态。"
            "信号轴改为按品类定向声明角色后，真实瓶颈已由 gap_distance 指出："
            "d1_bottleneck 显示只差一轴即可判定的配对中，电气轴占比 "
            "%d%%。补哪一轴的声明，看 d1_bottleneck 而非记忆。"
            % (100 * aggregates.get("d1_bottleneck", {}).get("electrical", 0)
               / max(1, aggregates.get("gap_distance", {}).get("1", 0))),
            "compatible_via_adapter 表示需转接盘（H3 硬骨头：转接件几何可打印可信尚未做），"
            "不等于开箱即装。",
            "全对评测含自配对与脑体对称展开；35 万对逐对结果不落盘，只落聚合与判例。",
            "gap_distance[d] = 恰有 d 轴判 unknown 的配对数（仅统计 overall=unknown；"
            "type_error 是类型冲突而非证据缺口，不计入）。d=1 即「补一轴声明即可判定」，"
            "是数据补录的最高优先级目标；gap_distance['0'] 恒为 0（无缺口就不可能是 unknown）。",
            "reflexivity 公理（同型必配）只对**几何规格型**类型成立（同标号法兰必然可装）；"
            "对**方向性角色型**类型（OUTPUT_SPIKE~OUTPUT_SPIKE）不成立——两个输出端不是"
            "必然可装，而是互为不互补。type_compat 里显式登记的自配对裁决优先于该公理。",
        ],
    }
    if not with_timestamp:
        meta.pop("generated_at", None)
    else:
        meta["generated_at"] = _now_cn()

    doc = {
        "meta": meta,
        "rule_table": RULE_TABLE,
        "verdicts": {
            "axis": list(("compatible", "compatible_via_adapter", "incompatible", "unknown")),
            "overall": list(OVERALL_VERDICTS),
            "precedence": "incompatible ⇒ type_error；否则 unknown ⇒ unknown；否则 composed",
        },
        "roles": roles,
        "aggregates": aggregates,
        "examples": examples,
    }
    return doc


def main():
    doc = build()
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    agg = doc["aggregates"]["overall_counts"]
    print(f"compose_semantics: pairs={doc['aggregates']['pairs_evaluated']} "
          f"composed={agg['composed']} type_error={agg['type_error']} "
          f"unknown={agg['unknown']} examples={len(doc['examples'])}")
    print(f"written: {os.path.relpath(OUT_PATH, ROOT)}")


if __name__ == "__main__":
    main()
