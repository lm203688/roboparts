#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compose_ir — RoboParts 组合判定中间表示（Composition IR v1）。

P2-5（OpenUSD/AAS 导出试验）的载体。

**为什么需要 IR**：compose_engine.compose() 的输出是「一次判定」的完整展开
（含 pairs_evaluated 全量、provenance 细节），而 OpenUSD/AAS 导出需要一个
**稳定、可逆、跨格式一致**的中间表示。本模块定义 IR v1 并给出：

1. `build_ir(graph, pair_ids)` —— 从真实判定现算 IR（不手写期望值，判据由本地源给出）；
2. `key_semantics(ir)` —— **关键语义指纹**（裁决 + 阻断维 + 节点身份 + 端口），
   这是「导出并回读、关键语义不丢失」的验收对象；
3. 版本常量 + schema 元信息。

**纪律**（对应 MEMORY §六）：
- IR 由判据现算，不是产物自我声明；
- 关键语义只收「可校验事实」（verdict/blocking_dims/ports），不收叙事性 reason
  的精确文本（但要求 reason 非空保持非空）；
- 不手写期望值：verify 脚本从 IR 本身现算，而非抄一份期望 JSON。

Schema 版本：`compose_ir/v1`（2026-10-27 首立）。
"""
from __future__ import annotations

import copy
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Sequence

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from compose_engine import AXES, compose  # noqa: E402

IR_VERSION = "compose_ir/v1"
SCHEMA = "https://roboparts.cc/schemas/composition_ir.schema.json"


# ---------------------------------------------------------------------------
# IR 构建
# ---------------------------------------------------------------------------
def _port_identity(port: Dict[str, Any]) -> Dict[str, Any]:
    """端口身份 = type + status（可校验事实；caveat/prov 是叙事，不列入）。"""
    return {"type": port.get("type"), "status": port.get("status")}


def build_ir(
    graph: Dict[str, Any],
    pair_ids: Sequence[Sequence[str]],
    composition_id: str = "comp-demo",
) -> Dict[str, Any]:
    """从真实判定现算 IR。

    Args:
        graph: api/morphology_graph.json
        pair_ids: [(a_id, b_id), ...] —— 参与判定的节点对
        composition_id: 组合标识

    Returns:
        IR v1 dict。节点只收「本组合实际参与」的节点（判例闭包，不是全图）。
    """
    nodes_by_id: Dict[str, Dict[str, Any]] = {n["id"]: n for n in graph.get("nodes", [])}

    # 参与闭包：pair 两端
    involved: List[str] = []
    seen = set()
    for a, b in pair_ids:
        for node_id in (a, b):
            if node_id not in seen and node_id in nodes_by_id:
                seen.add(node_id)
                involved.append(node_id)

    nodes = []
    for node_id in involved:
        n = nodes_by_id[node_id]
        nodes.append(
            {
                "id": n["id"],
                "label": n.get("label"),
                "category": n.get("category"),
                "manufacturer": n.get("manufacturer"),
                "ports": [_port_identity(p) for p in n.get("ports", [])],
            }
        )

    pairs = []
    for a, b in pair_ids:
        if a not in nodes_by_id or b not in nodes_by_id:
            continue
        r = compose(nodes_by_id[a], nodes_by_id[b], graph)
        axes = {}
        for axis in AXES:
            ax = r["axes"][axis]
            axes[axis] = {
                "verdict": ax.get("verdict"),
                "blocking_dims": sorted(ax.get("best_pair", {}).get("blocking_dims", []) or []),
                "reason": ax.get("best_pair", {}).get("reason")
                or ax.get("reason")
                or ax.get("best_pair", {}).get("pair_verdict")
                or "",
            }
        pairs.append(
            {
                "a": a,
                "b": b,
                "overall": r.get("overall"),
                "axes": axes,
            }
        )

    return {
        "ir_version": IR_VERSION,
        "schema": SCHEMA,
        "composition": {
            "id": composition_id,
            "engine": "compose_engine/v1",
            "nodes": nodes,
            "pairs": pairs,
        },
    }


# ---------------------------------------------------------------------------
# 关键语义指纹（验收对象）
# ---------------------------------------------------------------------------
def key_semantics(ir: Dict[str, Any]) -> Dict[str, Any]:
    """IR 的关键语义投影。

    只保留「可校验事实」，丢叙事 reason 的精确文本（保留 reason 非空性）。
    排序确保指纹稳定可比较。
    """
    comp = ir.get("composition", {})
    nodes = []
    for n in sorted(comp.get("nodes", []), key=lambda x: x.get("id") or ""):
        nodes.append(
            {
                "id": n.get("id"),
                "label": n.get("label"),
                "category": n.get("category"),
                "manufacturer": n.get("manufacturer"),
                "ports": sorted(
                    [_port_identity(p) for p in n.get("ports", [])],
                    key=lambda p: (p.get("type") or "", p.get("status") or ""),
                ),
            }
        )
    pairs = []
    for p in sorted(comp.get("pairs", []), key=lambda x: (x.get("a") or "", x.get("b") or "")):
        axes = {}
        for axis in AXES:
            ax = (p.get("axes") or {}).get(axis, {})
            axes[axis] = {
                "verdict": ax.get("verdict"),
                "blocking_dims": sorted(ax.get("blocking_dims", []) or []),
                "reason_nonempty": bool(ax.get("reason")),
            }
        pairs.append(
            {
                "a": p.get("a"),
                "b": p.get("b"),
                "overall": p.get("overall"),
                "axes": axes,
            }
        )
    return {
        "ir_version": ir.get("ir_version"),
        "composition": {
            "id": comp.get("id"),
            "nodes": nodes,
            "pairs": pairs,
        },
    }


def canonical_json(obj: Any) -> str:
    """稳定可复现的 JSON 序列化（排序键），用于指纹比较。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def semantics_equal(ir_a: Dict[str, Any], ir_b: Dict[str, Any]) -> bool:
    """关键语义指纹是否一致（回读后语义不丢失 ⇔ 指纹相等）。"""
    return canonical_json(key_semantics(ir_a)) == canonical_json(key_semantics(ir_b))


# ---------------------------------------------------------------------------
# 便捷：从真实 graph 取典型判例闭包
# ---------------------------------------------------------------------------
def demo_pair_ids(graph: Dict[str, Any], limit: int = 9) -> List[Sequence[str]]:
    """从 graph 现算一小组「覆盖各类可得裁决」的判例闭包。

    不硬编码期望值：跨节点扫描，按 overall 归类采样，保证 IR 里同时存在
    实际可得的各类裁决（真实图 composed=0，故通常只含 type_error/unknown；
    composed 不可得是**数据事实**，采样器如实返回可得类，verify 只要求
    「采样到的类在回读后不丢失」，不要求 composed 必现）。

    采样是确定性的：固定扫描顺序，不引入随机。
    """
    ids = [n["id"] for n in graph.get("nodes", [])]
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}

    # 目标类：优先真实可得的「可判定」类，再补 unknown
    targets = ["composed", "type_error", "unknown"]
    pairs: List[Sequence[str]] = []
    seen = set()
    have = set()

    # 第一遍：跨行采样（修正：不再在首个 a 处 break，要覆盖不同行）
    for a in ids[:120]:
        if all(t in have for t in targets):
            break
        for b in ids[:120]:
            if len(pairs) >= limit:
                break
            if a == b or (a, b) in seen:
                continue
            try:
                r = compose(nodes_by_id[a], nodes_by_id[b], graph)
            except Exception:
                continue
            overall = r.get("overall")
            # 只收「已判」或「两端有声明」的 unknown（unknown 无任何声明 → 无导出区分度）
            if overall == "unknown" and not _has_any_declared(nodes_by_id[a], nodes_by_id[b]):
                continue
            if overall in targets:
                seen.add((a, b))
                pairs.append((a, b))
                have.add(overall)
        # 每行至多收 limit 个，避免单行垄断
        if sum(1 for p in pairs if p[0] == a) >= limit:
            break

    if not pairs:
        # 兜底：至少前两对（保证非空，回读测试有对象）
        pairs = [(ids[0], ids[1])]
    return pairs


def _has_any_declared(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return any(p.get("status") in ("declared", "partial") for p in a.get("ports", [])) and any(
        p.get("status") in ("declared", "partial") for p in b.get("ports", [])
    )
