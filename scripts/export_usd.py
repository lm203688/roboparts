#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_usd — Composition IR v1 ⇄ OpenUSD (.usda) 双向映射。

P2-5（OpenUSD/AAS 导出试验）。用**真实 OpenUSD**（pxr.Usd/Sdf）构建 stage、
写 .usda、再打开回读——验证的是真 USD 序列化语义，不是自制文本字符串。

**映射（IR → USD）**：
- composition → 根 prim（defaultPrim = 组合 id 的 Xform）
- 每个 node → `def Xform "Node_<sanitized>"`，rp:id/label/category/manufacturer 为
  custom attributes（rp = RoboParts 命名空间）
- 每个 port → 子 prim `Port_<i>`，rp:type / rp:status
- 每个 pair → 子 prim `Pair_<a>__<b>`，rp:a / rp:b / rp:overall，
  每轴 rp:mechanical/electrical/signal = verdict，rp:<axis>_blocking = 逗号串

**回读（USD → IR）**：逐 prim 还原。key_semantics 只认可校验事实，
叙事 reason 不在 USD 里（回读后 reason 置空——这是**有意裁剪**，key_semantics
只保留 reason_nonempty，因此 reason 精确文本不参与验收）。

**纪律**：判据由 IR 现算；回读不信任 .usda 的自我声明，逐字段还原后与
key_semantics 比对。
"""
from __future__ import annotations

import re
import sys
from typing import Any, Dict, List

# pxr 是可选依赖：导入失败时给出可诊断的错误（verify 脚本负责 fail-closed）
try:
    from pxr import Sdf, Usd, UsdGeom  # noqa: F401
    _PXR_AVAILABLE = True
except ImportError as _e:  # pragma: no cover
    _PXR_AVAILABLE = False
    _PXR_IMPORT_ERROR = str(_e)


def pxr_available() -> bool:
    return _PXR_AVAILABLE


def pxr_import_error() -> str:
    return _PXR_IMPORT_ERROR if not _PXR_AVAILABLE else ""


def _san(name: str) -> str:
    """USD prim 名要求 [A-Za-z_][A-Za-z0-9_]*；连字符/冒号需清洗。"""
    s = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not s or not s[0].isalpha():
        s = "N_" + s
    return s


# ---------------------------------------------------------------------------
# IR → .usda
# ---------------------------------------------------------------------------
def export_usda(ir: Dict[str, Any]) -> str:
    """IR → .usda 文本（通过真实 USD stage 导出）。"""
    if not _PXR_AVAILABLE:
        raise RuntimeError("pxr 不可用：" + _PXR_IMPORT_ERROR)

    comp = ir.get("composition", {})
    comp_id = comp.get("id") or "composition"
    root_name = _san(comp_id)

    stage = Usd.Stage.CreateInMemory()
    stage.SetDefaultPrim(stage.DefinePrim("/" + root_name, "Xform"))

    root = stage.GetPrimAtPath("/" + root_name)
    # 版本信息存为根 prim 自定义属性（USD 不允许未注册的 stage metadata 键）
    root.CreateAttribute("rp:ir_version", Sdf.ValueTypeNames.String).Set(ir.get("ir_version") or "")
    root.CreateAttribute("rp:engine", Sdf.ValueTypeNames.String).Set(comp.get("engine") or "")
    # 原始组合 id 可能含连字符（非合法 prim 名），单独存原值
    root.CreateAttribute("rp:comp_id", Sdf.ValueTypeNames.String).Set(comp_id)

    # 节点
    for node in comp.get("nodes", []):
        nid = node.get("id") or ""
        prim = UsdGeom.Xform.Define(stage, f"/{root_name}/Node_{_san(nid)}")
        p = prim.GetPrim()
        p.CreateAttribute("rp:id", Sdf.ValueTypeNames.String).Set(nid)
        p.CreateAttribute("rp:label", Sdf.ValueTypeNames.String).Set(node.get("label") or "")
        p.CreateAttribute("rp:category", Sdf.ValueTypeNames.String).Set(node.get("category") or "")
        p.CreateAttribute("rp:manufacturer", Sdf.ValueTypeNames.String).Set(
            node.get("manufacturer") or ""
        )
        for i, port in enumerate(node.get("ports", [])):
            pp = UsdGeom.Xform.Define(stage, f"/{root_name}/Node_{_san(nid)}/Port_{i}")
            pp.GetPrim().CreateAttribute("rp:type", Sdf.ValueTypeNames.String).Set(
                port.get("type") or ""
            )
            pp.GetPrim().CreateAttribute("rp:status", Sdf.ValueTypeNames.String).Set(
                port.get("status") or ""
            )

    # 判例
    for pair in comp.get("pairs", []):
        a = pair.get("a") or ""
        b = pair.get("b") or ""
        pair_name = f"Pair_{_san(a)}__{_san(b)}"
        prim = UsdGeom.Xform.Define(stage, f"/{root_name}/{pair_name}")
        p = prim.GetPrim()
        p.CreateAttribute("rp:a", Sdf.ValueTypeNames.String).Set(a)
        p.CreateAttribute("rp:b", Sdf.ValueTypeNames.String).Set(b)
        p.CreateAttribute("rp:overall", Sdf.ValueTypeNames.String).Set(pair.get("overall") or "")
        axes = pair.get("axes") or {}
        for axis in ("mechanical", "electrical", "signal"):
            ax = axes.get(axis) or {}
            p.CreateAttribute(f"rp:{axis}", Sdf.ValueTypeNames.String).Set(ax.get("verdict") or "")
            bd = ax.get("blocking_dims") or []
            p.CreateAttribute(f"rp:{axis}_blocking", Sdf.ValueTypeNames.String).Set(
                ",".join(str(x) for x in bd)
            )
            # 叙事 reason 也进 USD（下游可读；key_semantics 只认 reason_nonempty）
            p.CreateAttribute(f"rp:{axis}_reason", Sdf.ValueTypeNames.String).Set(
                ax.get("reason") or ""
            )

    return stage.ExportToString()


# ---------------------------------------------------------------------------
# .usda → IR
# ---------------------------------------------------------------------------
def import_usda(usda_text: str) -> Dict[str, Any]:
    """.usda → IR（逐字段还原，不信任声明）。"""
    if not _PXR_AVAILABLE:
        raise RuntimeError("pxr 不可用：" + _PXR_IMPORT_ERROR)

    # 用匿名 Sdf 层载入 .usda 文本 → 真实 USD stage 打开回读
    layer = Sdf.Layer.CreateAnonymous(".usda")
    layer.ImportFromString(usda_text)
    stage = Usd.Stage.Open(layer)
    if not stage:
        raise RuntimeError(".usda 无法被 OpenUSD 打开")

    root = stage.GetDefaultPrim()
    if not root:
        raise RuntimeError(".usda 无 defaultPrim")

    ir_version = _attr(root, "rp:ir_version") or "compose_ir/v1"

    nodes: List[Dict[str, Any]] = []
    pairs: List[Dict[str, Any]] = []

    for prim in root.GetChildren():
        name = prim.GetName()
        if name.startswith("Node_"):
            nid = _attr(prim, "rp:id")
            ports = []
            for child in prim.GetChildren():
                if child.GetName().startswith("Port_"):
                    ports.append(
                        {
                            "type": _attr(child, "rp:type"),
                            "status": _attr(child, "rp:status"),
                        }
                    )
            nodes.append(
                {
                    "id": nid,
                    "label": _attr(prim, "rp:label"),
                    "category": _attr(prim, "rp:category"),
                    "manufacturer": _attr(prim, "rp:manufacturer"),
                    "ports": ports,
                }
            )
        elif name.startswith("Pair_"):
            axes = {}
            for axis in ("mechanical", "electrical", "signal"):
                bd = _attr(prim, f"rp:{axis}_blocking") or ""
                axes[axis] = {
                    "verdict": _attr(prim, f"rp:{axis}") or "",
                    "blocking_dims": [x for x in bd.split(",") if x != ""],
                    "reason": _attr(prim, f"rp:{axis}_reason"),
                }
            pairs.append(
                {
                    "a": _attr(prim, "rp:a"),
                    "b": _attr(prim, "rp:b"),
                    "overall": _attr(prim, "rp:overall"),
                    "axes": axes,
                }
            )

    return {
        "ir_version": ir_version,
        "schema": "https://roboparts.cc/schemas/composition_ir.schema.json",
        "composition": {
            "id": _attr(root, "rp:comp_id") or root.GetName(),
            "engine": _attr(root, "rp:engine") or "compose_engine/v1",
            "nodes": nodes,
            "pairs": pairs,
        },
    }


def _attr(prim, name: str) -> str:
    attr = prim.GetAttribute(name)
    if attr:
        v = attr.Get()
        if v is not None:
            return str(v)
    return ""
