#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_aas — Composition IR v1 ⇄ Asset Administration Shell（IEC 63278）双向映射。

P2-5（OpenUSD/AAS 导出试验）。AAS 是工业 4.0「资产管理壳」，标准格式为 AAS JSON
（IDTA 规范，字段名驼峰，submodelElements 承载数据）。本模块把 IR 映射到 AAS
JSON 并回读，验证**关键语义不丢失**。

**映射（IR → AAS）**：
- composition → 一个 AssetAdministrationShell（globalAssetId 指向组合 id）
- 每个 node → 一个 SubmodelElementCollection（idShort = Node_<id>）：
  - 子 Property：entityId/label/category/manufacturer
  - 端口子集合：Ports（每个端口一个 SubmodelElementCollection）
- 每个 pair → 一个 SubmodelElementCollection（idShort = Pair_<a>__<b>）：
  - 子 Property：a / b / overall
  - 每轴一个 SubmodelElementCollection（Mechanical/Electrical/Signal）：
    verdict / blockingDims（逗号串）/ reason

**回读（AAS → IR）**：逐 element 还原，不信任声明。

**纪律**：AAS 是 JSON 载体，字段值必须显式 string 化（AAS 的 value 是字符串），
阻断维用逗号分隔（AAS 无原生数组 Property，用 MultiLanguageProperty 或逗号串；
这里选逗号串保持可逆，key_semantics 只认 blocking_dims 集合）。
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List

# AAS JSON 是纯 dict，无需外部库
_AVAILABLE = True


def aas_available() -> bool:
    return _AVAILABLE


def _prop(id_short: str, value: str) -> Dict[str, Any]:
    return {
        "idShort": id_short,
        "modelType": "Property",
        "valueType": "xs:string",
        "value": value,
    }


def _coll(id_short: str, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "idShort": id_short,
        "modelType": "SubmodelElementCollection",
        "value": elements,
    }


# ---------------------------------------------------------------------------
# IR → AAS JSON
# ---------------------------------------------------------------------------
def export_aas(ir: Dict[str, Any]) -> Dict[str, Any]:
    """IR → AAS JSON（dict，可 json.dumps）。"""
    comp = ir.get("composition", {})
    comp_id = comp.get("id") or "composition"

    aas_id = f"https://roboparts.cc/aas/{comp_id}"
    submodel_id = f"{aas_id}/submodels/Composition"

    # 每个 node 一个 SubmodelElementCollection
    node_elements = []
    for node in comp.get("nodes", []):
        nid = node.get("id") or ""
        ports = []
        for i, port in enumerate(node.get("ports", [])):
            ports.append(
                _coll(
                    f"Port_{i}",
                    [
                        _prop("type", port.get("type") or ""),
                        _prop("status", port.get("status") or ""),
                    ],
                )
            )
        node_elements.append(
            _coll(
                f"Node_{nid}",
                [
                    _prop("entityId", nid),
                    _prop("label", node.get("label") or ""),
                    _prop("category", node.get("category") or ""),
                    _prop("manufacturer", node.get("manufacturer") or ""),
                    _coll("Ports", ports),
                ],
            )
        )

    # 每个 pair 一个 SubmodelElementCollection
    pair_elements = []
    for pair in comp.get("pairs", []):
        axes = pair.get("axes") or {}
        axis_colls = []
        for axis in ("mechanical", "electrical", "signal"):
            ax = axes.get(axis) or {}
            axis_colls.append(
                _coll(
                    axis.capitalize(),
                    [
                        _prop("verdict", ax.get("verdict") or ""),
                        _prop("blockingDims", ",".join(str(x) for x in (ax.get("blocking_dims") or []))),
                        _prop("reason", ax.get("reason") or ""),
                    ],
                )
            )
        pair_elements.append(
            _coll(
                f"Pair_{pair.get('a')}__{pair.get('b')}",
                [
                    _prop("a", pair.get("a") or ""),
                    _prop("b", pair.get("b") or ""),
                    _prop("overall", pair.get("overall") or ""),
                    _coll("Axes", axis_colls),
                ],
            )
        )

    return {
        "assetAdministrationShells": [
            {
                "idShort": "RoboPartsComposition",
                "id": aas_id,
                "assetInformation": {
                    "assetKind": "Instance",
                    "globalAssetId": aas_id,
                },
                "submodels": [
                    {"type": "ExternalReference", "keys": [{"type": "Submodel", "value": submodel_id}]}
                ],
            }
        ],
        "submodels": [
            {
                "idShort": "Composition",
                "id": submodel_id,
                "kind": "Instance",
                "submodelElements": [
                    _prop("irVersion", ir.get("ir_version") or ""),
                    _prop("engine", comp.get("engine") or ""),
                    _prop("compId", comp_id),
                    _coll("Nodes", node_elements),
                    _coll("Pairs", pair_elements),
                ],
            }
        ],
        "conceptDescriptions": [],
    }


# ---------------------------------------------------------------------------
# AAS JSON → IR
# ---------------------------------------------------------------------------
def import_aas(aas: Dict[str, Any]) -> Dict[str, Any]:
    """AAS JSON → IR（逐字段还原）。"""
    submodel = (aas.get("submodels") or [{}])[0]
    elements = submodel.get("submodelElements") or []

    ir_version = ""
    engine = ""
    comp_id = ""
    nodes: List[Dict[str, Any]] = []
    pairs: List[Dict[str, Any]] = []

    for el in elements:
        id_short = el.get("idShort", "")
        if id_short == "irVersion":
            ir_version = el.get("value") or ""
        elif id_short == "engine":
            engine = el.get("value") or ""
        elif id_short == "compId":
            comp_id = el.get("value") or ""
        elif id_short == "Nodes":
            nodes = _read_nodes(el.get("value") or [])
        elif id_short == "Pairs":
            pairs = _read_pairs(el.get("value") or [])

    return {
        "ir_version": ir_version or "compose_ir/v1",
        "schema": "https://roboparts.cc/schemas/composition_ir.schema.json",
        "composition": {
            "id": comp_id,
            "engine": engine or "compose_engine/v1",
            "nodes": nodes,
            "pairs": pairs,
        },
    }


def _read_nodes(colls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    nodes = []
    for coll in colls:
        if coll.get("modelType") != "SubmodelElementCollection":
            continue
        kv = _kv(coll)
        ports = []
        for sub in coll.get("value") or []:
            if sub.get("idShort") == "Ports" and sub.get("modelType") == "SubmodelElementCollection":
                for i, pc in enumerate(sub.get("value") or []):
                    pv = _kv(pc)
                    ports.append({"type": pv.get("type", ""), "status": pv.get("status", "")})
        nodes.append(
            {
                "id": kv.get("entityId", ""),
                "label": kv.get("label", ""),
                "category": kv.get("category", ""),
                "manufacturer": kv.get("manufacturer", ""),
                "ports": ports,
            }
        )
    return nodes


def _read_pairs(colls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pairs = []
    for coll in colls:
        if coll.get("modelType") != "SubmodelElementCollection":
            continue
        kv = _kv(coll)
        axes = {}
        for sub in coll.get("value") or []:
            if sub.get("idShort") == "Axes" and sub.get("modelType") == "SubmodelElementCollection":
                for ac in sub.get("value") or []:
                    axis_name = (ac.get("idShort") or "").lower()
                    av = _kv(ac)
                    bd = av.get("blockingDims", "")
                    axes[axis_name] = {
                        "verdict": av.get("verdict", ""),
                        "blocking_dims": [x for x in bd.split(",") if x != ""],
                        "reason": av.get("reason", ""),
                    }
        pairs.append(
            {
                "a": kv.get("a", ""),
                "b": kv.get("b", ""),
                "overall": kv.get("overall", ""),
                "axes": axes,
            }
        )
    return pairs


def _kv(coll: Dict[str, Any]) -> Dict[str, str]:
    """collection 里所有 Property 子元素 → {idShort: value}。"""
    out = {}
    for el in coll.get("value") or []:
        if el.get("modelType") == "Property":
            out[el.get("idShort", "")] = str(el.get("value") or "")
    return out
