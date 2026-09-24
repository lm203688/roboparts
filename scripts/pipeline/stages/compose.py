#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline.stages.compose — compose_semantics 拆成 6 个纯函数算子。

对应关系（build_compose_semantics.py → 算子）
------------------------------------------------
  open(GRAPH_PATH) + json.load      → compose.load_graph
  eval_all_pairs(...)                → compose.evaluate_pairs
  _pick_examples(...)                → compose.pick_examples
  crosscheck（build 里的 fail-fast）→ compose.crosscheck
  roles 现算（build 内联）          → compose.compute_roles
  build() 的 output 组装             → compose.assemble

等价性约束
----------
compose.assemble 的输出必须与 build_compose_semantics.build() 产出
**除 meta.generated_at / meta.generated_by 外完全一致**。verify_pipeline.py
用 json 结构相等断言这条约束（不是字符串相等，允许 indent 差异）。

若本文件任何算子改动导致 assemble 输出变化，就是**破坏等价性**——要么改
回，要么同步改 build_compose_semantics.py 让两条路径保持等价。这是防止
"pipeline 与旧脚本悄悄分叉"的唯一闸门。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from ..registry import operator

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 复用引擎常量与函数——单一真相源，禁止复制。
# 这里用 sys.path 导入避免相对导入失败。
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from compose_engine import (  # noqa: E402
    ENGINE_VERSION,
    ROLES,
    RULE_TABLE,
    AXES,
    OVERALL_VERDICTS,
    compose,
    eval_all_pairs,
)
# EXAMPLES_PER_CLASS 定义在 build_compose_semantics.py——单一真相源，直接复用。
from build_compose_semantics import EXAMPLES_PER_CLASS  # noqa: E402


def _read_json(path: str) -> Dict[str, Any]:
    """相对仓库根读取 JSON。fail-fast：任何 IO/JSON 错误原样抛出。"""
    full = os.path.join(ROOT, path)
    with open(full, encoding="utf-8") as f:
        return json.load(f)


@operator("compose.load_graph", "compose",
          "读 api/morphology_graph.json——compose_semantics 的单一真相源")
def load_graph(path: str) -> Dict[str, Any]:
    """读形态图。fail-fast：缺 nodes 键视为不可判定。"""
    if not path:
        raise ValueError("load_graph: path 不能为空")
    graph = _read_json(path)
    if not isinstance(graph, dict):
        raise TypeError(f"load_graph: 形态图应为 dict，收到 {type(graph).__name__}")
    if "nodes" not in graph:
        raise ValueError("load_graph: 形态图缺 'nodes' 键，无法继续")
    return graph


@operator("compose.evaluate_pairs", "compose",
          "全对评测——593² 对，产出 overall_counts / axis_marginals / gap_distance / d1_bottleneck")
def evaluate_pairs(
    graph: Dict[str, Any],
    examples_per_class: int = EXAMPLES_PER_CLASS,
) -> Dict[str, Any]:
    """等价于 build_compose_semantics.build 中调用 eval_all_pairs 的一步。"""
    if not isinstance(graph, dict):
        raise TypeError(
            f"evaluate_pairs: graph 应为 dict，收到 {type(graph).__name__}")
    if not isinstance(examples_per_class, int) or examples_per_class < 0:
        raise ValueError(
            f"evaluate_pairs: examples_per_class 应为非负 int，收到 {examples_per_class!r}")
    return eval_all_pairs(graph, examples_per_class=examples_per_class)


@operator("compose.pick_examples", "compose",
          "对聚合计数里出现的每个总裁决类别，取前 N 对判例并算完整引擎证据")
def pick_examples(
    graph: Dict[str, Any],
    aggregates: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """等价于 build_compose_semantics._pick_examples。

    判例选取是确定性的：`id_pairs[:EXAMPLES_PER_CLASS]`，排序由 eval_all_pairs
    负责。同输入必同输出——这是等价性测试能通过的必要前提。
    """
    if not isinstance(graph, dict):
        raise TypeError(f"pick_examples: graph 应为 dict")
    if not isinstance(aggregates, dict):
        raise TypeError(f"pick_examples: aggregates 应为 dict")

    nodes = {n["id"]: n for n in graph.get("nodes", []) if n.get("composable", True)}
    examples: List[Dict[str, Any]] = []
    for _cls, id_pairs in aggregates.get("example_ids", {}).items():
        for a, b in id_pairs[:EXAMPLES_PER_CLASS]:
            examples.append(compose(nodes[a], nodes[b], graph))
    return examples


@operator("compose.crosscheck", "compose",
          "算术守卫：overall_counts 之和与 axis_marginals 每轴之和都必须 == pairs_evaluated")
def crosscheck(aggregates: Dict[str, Any]) -> Dict[str, Any]:
    """两条硬约束（与 build_compose_semantics.build 里 fail-fast 逻辑一致）：
    1. sum(overall_counts.values()) == pairs_evaluated
    2. 对每个 axis：sum(axis_marginals[axis].values()) == pairs_evaluated

    任一违反即 SystemExit——宁可构建失败也不发布自相矛盾的聚合。
    """
    if not isinstance(aggregates, dict):
        raise TypeError(f"crosscheck: aggregates 应为 dict")

    total = aggregates.get("pairs_evaluated")
    if total is None:
        raise ValueError("crosscheck: aggregates 缺 pairs_evaluated")

    oc = aggregates.get("overall_counts")
    if not isinstance(oc, dict) or not oc:
        raise ValueError("crosscheck: overall_counts 缺失或为空")
    if sum(oc.values()) != total:
        raise SystemExit(
            "!! crosscheck: overall_counts 之和不等于 pairs_evaluated")

    for ax in AXES:
        m = (aggregates.get("axis_marginals") or {}).get(ax)
        if not isinstance(m, dict):
            raise SystemExit(
                f"!! crosscheck: axis_marginals[{ax}] 缺失")
        if sum(m.values()) != total:
            raise SystemExit(
                f"!! crosscheck: axis_marginals[{ax}] 之和不等于 pairs_evaluated")

    return {"pairs_evaluated": total, "ok": True}


@operator("compose.compute_roles", "compose",
          "现算每个角色的类别映射与节点数——禁止手写")
def compute_roles(graph: Dict[str, Any]) -> Dict[str, Any]:
    """等价于 build_compose_semantics.build 里的 roles 计算。

    ROLES 常量里的 categories 是引擎定义，node_count 从 graph["nodes"] 现算
    （按 category 分组计数再按 ROLES 汇总），不手写、不缓存。
    """
    if not isinstance(graph, dict):
        raise TypeError(f"compute_roles: graph 应为 dict")

    cat_counts: Dict[str, int] = {}
    for n in graph.get("nodes", []):
        c = n.get("category")
        if c:
            cat_counts[c] = cat_counts.get(c, 0) + 1

    roles: Dict[str, Any] = {}
    for role, spec in ROLES.items():
        roles[role] = {
            "categories": spec["categories"],
            "node_count": sum(cat_counts.get(c, 0) for c in spec["categories"]),
            "note": spec["note"],
        }
    return roles


@operator("compose.assemble", "compose",
          "把前面所有步骤的产物组装为最终 compose_semantics 文档")
def assemble(
    graph: Dict[str, Any],
    aggregates: Dict[str, Any],
    examples: List[Dict[str, Any]],
    roles: Dict[str, Any],
) -> Dict[str, Any]:
    """等价于 build_compose_semantics.build() 的 output 组装。

    输出结构与 build_compose_semantics.py 完全一致——verify_pipeline.py 会
    逐字段比对。任何键名/嵌套变化都会被等价性断言抓住。
    """
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
        "generated_by": "scripts/pipeline/stages/compose.py (assemble)",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%dT%H:%M:%S+08:00"),
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
