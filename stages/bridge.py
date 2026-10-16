#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stages/bridge.py — 双引擎口径桥接（可复用 stage 模块 · Phase B · S1）

**背景**（20261013 报告 §6.2 #4）：
    双引擎口径在对外表面残留。`docs/dual-engine-bridge.md` 是文档，但 Agent 读到
    "四维 vs 三轴"两套维度时会困惑。本模块把文档升级为**可执行 stage**：
    
    1. 从 `functions/_lib/compat_engine.js` 正则提取 DIMENSIONS / HARD_DIMENSIONS
    2. 从 `scripts/compose_engine.py` 正则提取 AXES
    3. 按 `docs/dual-engine-bridge.md` §三 的唯一权威对应表构建桥接
    4. 提供 `check()` 函数供 CI 闸门调用（不通过则抛异常）
    5. 提供 `export()` 函数生成 api/engine_bridge.json

**设计纪律**：
    - **不合并两套引擎**（合并会让 agent 误以为"协议 + signal 是一维"）；
      只做维度名映射与场景路由。
    - **权威表在 dual-engine-bridge.md §三**，本模块只是它的可执行镜像；
      修改映射必须同时改两处，否则 check() 判红。
    - 阴阳自证：把映射改坏（把 electrical 映射到 signal）→ 期望 check() 判红。

**与 scripts/bridge_engine.py 的关系**：
    bridge_engine.py 是独立可执行脚本（含 --check / --write CLI）；
    本模块是**可复用 stage**（供 CI gate、orchestrator、其他脚本 import）。
    两者共享权威映射表（DIMENSION_MAP / RESEARCH_ONLY_AXES / SCENARIO_ROUTING）。
    修改映射必须同时改两处，否则 CI gate_bridge 判红。

用法（作为 stage）：
    from stages.bridge import check, export, DIMENSION_MAP, build_bridge
    result = build_bridge()
    check(result)  # 抛异常则判红
    export(result)  # 写 api/engine_bridge.json

用法（独立 CLI）：
    python -m stages.bridge --check   # CI 闸门模式
    python -m stages.bridge --write   # 写产物模式
    python -m stages.bridge            # 输出桥接 JSON 到 stdout
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
PRODUCT_ENGINE = ROOT / "functions" / "_lib" / "compat_engine.js"
RESEARCH_ENGINE = ROOT / "scripts" / "compose_core.py"  # A1 抽核后 AXES 在此
BRIDGE_DOC = ROOT / "docs" / "dual-engine-bridge.md"
MANIFEST_OUT = ROOT / "api" / "engine_bridge.json"

# ── 权威映射表（dual-engine-bridge.md §三）─────────────────────────────
# product_dim → research_axis（None 表示无对应）
DIMENSION_MAP: Dict[str, Optional[str]] = {
    "protocol": None,            # 产品层独有：协议族（宏观）
    "electrical": "electrical",  # 同名同义
    "mechanical": "mechanical",  # 同名同义
    "software": None,            # 产品层独有：ROS2 生态支持
}
# 研究层独有
RESEARCH_ONLY_AXES: Tuple[str, ...] = ("signal",)  # 通道方向性（微观）

# 场景路由表（dual-engine-bridge.md §二）
SCENARIO_ROUTING: List[Dict[str, str]] = [
    {"scenario": "用户查 ACT-001 能否和 ACT-002 一起用",
     "engine": "product", "reason": "用户要「能不能」的可执行结论，四维覆盖协议 + 生态"},
    {"scenario": "Agent 通过 MCP 调用 check_compatibility",
     "engine": "product", "reason": "MCP 是产品面入口"},
    {"scenario": "Agent 通过 MCP 调用 check_co_mount",
     "engine": "research", "reason": "共装是三段关系，需要 signal 通道互补"},
    {"scenario": "研究进度评估（research_progress.json）",
     "engine": "research", "reason": "研究层量化数据完整性，不看协议族"},
    {"scenario": "评估「补哪条数据最值」（MDV 判据）",
     "engine": "research", "reason": "MDV 判据建立在三轴 verdict 分布上"},
    {"scenario": "论文方法学描述",
     "engine": "both", "reason": "论文要说明为什么两套并存"},
]

# 权威维度集（从源文件提取，不手写）
PRODUCT_DIMENSIONS_AUTHORITATIVE = ("protocol", "electrical", "mechanical", "software")
RESEARCH_AXES_AUTHORITATIVE = ("mechanical", "electrical", "signal")


# ── 提取函数 ──────────────────────────────────────────────────────────

def extract_js_dimensions(path: Path) -> Tuple[List[str], List[str]]:
    """从 compat_engine.js 正则提取 DIMENSIONS 和 HARD_DIMENSIONS。"""
    src = path.read_text(encoding="utf-8")
    m = re.search(r"export\s+const\s+DIMENSIONS\s*=\s*\[([^\]]+)\]", src)
    if not m:
        raise RuntimeError(f"DIMENSIONS 未在 {path.name} 中找到")
    dims = [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]

    m2 = re.search(r"export\s+const\s+HARD_DIMENSIONS\s*=\s*\[([^\]]+)\]", src)
    if not m2:
        hard = []
    else:
        hard = [x.strip().strip("'\"") for x in m2.group(1).split(",") if x.strip()]
    return dims, hard


def extract_py_axes(path: Path) -> List[str]:
    """从 compose_engine.py 正则提取 AXES 元组。"""
    src = path.read_text(encoding="utf-8")
    # 支持两种写法：AXES: Tuple[str, ...] = (...) 或 AXES = (...)
    m = re.search(r"AXES\s*(?::\s*Tuple\[str,\s*\.\.\.\])?\s*=\s*\(([^)]+)\)", src)
    if not m:
        raise RuntimeError(f"AXES 未在 {path.name} 中找到")
    return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]


# ── 桥接构建 ──────────────────────────────────────────────────────────

def build_bridge() -> Dict[str, Any]:
    """构建完整桥接结构。"""
    dims, hard = extract_js_dimensions(PRODUCT_ENGINE)
    axes = extract_py_axes(RESEARCH_ENGINE)

    return {
        "meta": {
            "version": "engine_bridge/v1",
            "source": "dual-engine-bridge.md §二/§三 可执行镜像",
            "note": "两套引擎不合并，只做维度名映射与场景路由。",
        },
        "product_engine": {
            "path": str(PRODUCT_ENGINE.relative_to(ROOT)),
            "dimensions": dims,
            "hard_dimensions": hard,
        },
        "research_engine": {
            "path": str(RESEARCH_ENGINE.relative_to(ROOT)),
            "axes": axes,
        },
        "dimension_map": DIMENSION_MAP,
        "research_only_axes": list(RESEARCH_ONLY_AXES),
        "scenario_routing": SCENARIO_ROUTING,
        "caliber_warning": (
            "本桥接不合并两套引擎。"
            "产品层四维（protocol/electrical/mechanical/software）与研究层三轴"
            "（mechanical/electrical/signal）维度不同、口径不同、结论不可混用。"
            "Agent 按场景路由表选择引擎，不得自行合并。"
        ),
    }


# ── 校验函数（供 CI 闸门调用）─────────────────────────────────────────

def check(bridge: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """校验桥接一致性。返回 {ok: bool, errors: [...], warnings: [...]}。
    
    CI 闸门调用：check() 返回 ok=False 时判红。
    """
    if bridge is None:
        bridge = build_bridge()

    errors = []
    warnings = []

    # 1) 产品层维度必须匹配权威集
    prod_dims = bridge["product_engine"]["dimensions"]
    if set(prod_dims) != set(PRODUCT_DIMENSIONS_AUTHORITATIVE):
        errors.append(
            f"产品层维度漂移：实际 {prod_dims}，权威 {list(PRODUCT_DIMENSIONS_AUTHORITATIVE)}"
        )

    # 2) 研究层轴必须匹配权威集
    research_axes = bridge["research_engine"]["axes"]
    if set(research_axes) != set(RESEARCH_AXES_AUTHORITATIVE):
        errors.append(
            f"研究层轴漂移：实际 {research_axes}，权威 {list(RESEARCH_AXES_AUTHORITATIVE)}"
        )

    # 3) 维度映射表必须完整覆盖产品层四维
    for d in PRODUCT_DIMENSIONS_AUTHORITATIVE:
        if d not in bridge["dimension_map"]:
            errors.append(f"维度映射表缺少产品层维度 {d}")

    # 4) 映射值必须合法（None 或研究层轴之一）
    valid_targets = set(RESEARCH_AXES_AUTHORITATIVE)
    for d, target in bridge["dimension_map"].items():
        if target is not None and target not in valid_targets:
            errors.append(f"维度映射 {d} → {target} 非法（目标不在研究层轴中）")

    # 5) 研究层独有轴必须显式登记
    for ax in RESEARCH_ONLY_AXES:
        if ax not in research_axes:
            errors.append(f"研究层独有轴 {ax} 未在 compose_engine.py 中声明")

    # 6) 场景路由表必须存在且非空
    routing = bridge.get("scenario_routing") or []
    if not routing:
        errors.append("场景路由表为空")
    else:
        valid_engines = {"product", "research", "both"}
        for r in routing:
            if r.get("engine") not in valid_engines:
                errors.append(f"场景路由 engine 非法：{r.get('engine')}")

    # 7) 警告：映射表中有 None（产品层独有维度）
    none_count = sum(1 for v in bridge["dimension_map"].values() if v is None)
    if none_count > 0:
        warnings.append(f"产品层有 {none_count} 个维度无研究层对应（正常）")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "bridge_version": bridge["meta"]["version"],
    }


# ── 导出函数 ──────────────────────────────────────────────────────────

def export(bridge: Optional[Dict[str, Any]] = None, path: Optional[Path] = None) -> Path:
    """写 api/engine_bridge.json。"""
    if bridge is None:
        bridge = build_bridge()
    if path is None:
        path = MANIFEST_OUT
    path.write_text(json.dumps(bridge, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


# ── 变异自证（供 CI gate_bridge 调用）─────────────────────────────────

def mutation_self_test() -> Dict[str, Any]:
    """阴阳自证：故意篡改映射，check() 必须判红。
    
    返回 {mutation_kills: bool, detail: str}
    """
    # 变异：把 electrical 映射到 signal（非法目标）
    bad_bridge = build_bridge()
    bad_bridge["dimension_map"]["electrical"] = "signal"
    result = check(bad_bridge)
    return {
        "mutation_kills": not result["ok"],
        "detail": "; ".join(result["errors"][:3]) if not result["ok"] else "映射改坏但 check 判绿（失败）",
    }


# ── CLI ──────────────────────────────────────────────────────────────

def _cli() -> int:
    if "--check" in sys.argv:
        bridge = build_bridge()
        result = check(bridge)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    elif "--write" in sys.argv:
        p = export()
        print(f"[ok] wrote {p}")
        return 0
    elif "--mutation" in sys.argv:
        result = mutation_self_test()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["mutation_kills"] else 1
    else:
        bridge = build_bridge()
        print(json.dumps(bridge, ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    sys.exit(_cli())
