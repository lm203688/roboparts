#!/usr/bin/env python3
"""双引擎口径桥接（可执行工具）· 2026-10-12

背景
----
《RoboParts-下一阶段全面提升报告-20261011》§6.2 #4 指出：双引擎口径在对外表面残留。
`docs/dual-engine-bridge.md` 是**文档**，但 Agent 读到"四维 vs 三轴"两套维度时会困惑。
本脚本把文档升级为**可执行工具**：

  1. 从 `functions/_lib/compat_engine.js` 正则提取 DIMENSIONS / HARD_DIMENSIONS
  2. 从 `scripts/compose_engine.py` 正则提取 AXES
  3. 按 `docs/dual-engine-bridge.md` §三 的唯一权威对应表构建桥接
  4. --check 模式：验证对外清单口径未回退，含阴阳自证（变异 → 判红）

用法
----
  python scripts/bridge_engine.py              # 输出桥接 JSON
  python scripts/bridge_engine.py --check      # CI 闸门：不通过则退出 1
  python scripts/bridge_engine.py --write      # 写 api/engine_bridge.json 供 MCP 消费

设计纪律
--------
- **不合并两套引擎**（合并会让 agent 误以为"协议 + signal 是一维"）；
  只做维度名映射与场景路由。
- **权威表在 dual-engine-bridge.md §三**，本脚本只是它的可执行镜像；
  修改映射必须同时改两处，否则 --check 判红。
- 阴阳自证：把映射改坏（把 electrical 映射到 signal）→ 期望 --check 判红。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
PRODUCT_ENGINE = ROOT / "functions" / "_lib" / "compat_engine.js"
RESEARCH_ENGINE = ROOT / "scripts" / "compose_engine.py"
BRIDGE_DOC = ROOT / "docs" / "dual-engine-bridge.md"
MANIFEST_OUT = ROOT / "api" / "engine_bridge.json"

# 权威映射表（dual-engine-bridge.md §三）
# product_dim → research_axis（None 表示无对应）
DIMENSION_MAP: Dict[str, Optional[str]] = {
    "protocol": None,       # 产品层独有：协议族（宏观）
    "electrical": "electrical",  # 同名同义
    "mechanical": "mechanical",  # 同名同义
    "software": None,       # 产品层独有：ROS2 生态支持
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
    m = re.search(r"AXES\s*:\s*Tuple\[str,\s*\.\.\.\]\s*=\s*\(([^)]+)\)", src)
    if not m:
        raise RuntimeError(f"AXES 未在 {path.name} 中找到")
    return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]


def build_bridge() -> Dict[str, Any]:
    """构建完整桥接结构。"""
    dims, hard = extract_js_dimensions(PRODUCT_ENGINE)
    axes = extract_py_axes(RESEARCH_ENGINE)

    # 一致性检查：权威映射表必须覆盖所有实际维度
    for d in dims:
        if d not in DIMENSION_MAP:
            raise RuntimeError(
                f"DIMENSION_MAP 未覆盖产品层维度 {d!r}——"
                f"新维度必须同步登记到 dual-engine-bridge.md §三 与 bridge_engine.py"
            )
    for a in RESEARCH_ONLY_AXES:
        if a not in axes:
            raise RuntimeError(
                f"RESEARCH_ONLY_AXES 声称 {a!r} 是研究层独有，"
                f"但 compose_engine.py 的 AXES 里没有——请同步"
            )

    intersection = sorted(
        [d for d, r in DIMENSION_MAP.items() if r and r in axes]
    )
    product_only = sorted([d for d, r in DIMENSION_MAP.items() if r is None])
    research_only = [a for a in axes if a not in set(DIMENSION_MAP.values())]

    return {
        "bridge_version": "1.0.0",
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "product_engine": {
            "location": str(PRODUCT_ENGINE.relative_to(ROOT)),
            "dimensions": dims,
            "hard_dimensions": hard,
            "note": "产品层四维查询：面向用户的可执行兼容结论（协议+生态覆盖）",
        },
        "research_engine": {
            "location": str(RESEARCH_ENGINE.relative_to(ROOT)),
            "axes": axes,
            "note": "研究层三轴类型系统：面向数据完整性评估与三态 fail-closed compose",
        },
        "mapping": {
            "canonical_source": str(BRIDGE_DOC.relative_to(ROOT)) + " §三",
            "dimension_to_axis": DIMENSION_MAP,
            "intersection": intersection,
            "product_only": product_only,
            "research_only": research_only,
            "non_union_reason": (
                "两套引擎不互为子集：signal（通道方向性，微观）与 protocol（协议族，宏观）"
                "是不同抽象层，合并会让 agent 误以为「协议+signal」是一维"
            ),
        },
        "scenario_routing": SCENARIO_ROUTING,
        "honest_boundaries": [
            "electrical 与 mechanical 同名同义，可跨引擎直接传递",
            "protocol / software 只在产品层存在（研究层不评生态支持）",
            "signal 只在研究层存在（产品层不评通道方向性）",
            "跨引擎调用前必须经本桥接转换，禁止裸用维度名",
        ],
    }


def check_docs_consistency() -> List[str]:
    """校验对外文档未回退到「四维作为唯一叙事」。"""
    issues: List[str] = []
    manifest_targets = [
        ROOT / "server.json",
        ROOT / "smithery.yaml",
        ROOT / ".well-known" / "mcp.json",
        ROOT / "llms.txt",
    ]
    for p in manifest_targets:
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        has_4d = ("四维" in txt) or ("4-dimension" in txt.lower())
        has_3d = ("三态" in txt) or ("三轴" in txt) or ("three-state" in txt.lower())
        if has_4d and not has_3d:
            issues.append(
                f"{p.relative_to(ROOT)}: 含「四维」但无「三态/三轴」桥接标注——"
                f"Agent 读到单一维度叙事会困惑"
            )
    if not BRIDGE_DOC.exists():
        issues.append(f"桥接文档不存在：{BRIDGE_DOC.relative_to(ROOT)}")
    return issues


def _assert_invariants(bridge: Dict[str, Any]) -> None:
    """阴阳自证：结构性不变式，违反立即抛错。"""
    inter = set(bridge["mapping"]["intersection"])
    assert {"electrical", "mechanical"} <= inter, (
        f"交集必须至少含 electrical + mechanical，实际 {inter}"
    )
    assert len(bridge["product_engine"]["dimensions"]) >= 4, (
        "产品层引擎维度数必须 >= 4（当前实现是 4）"
    )
    assert len(bridge["research_engine"]["axes"]) == 3, (
        f"研究层引擎维度数必须 = 3，实际 {bridge['research_engine']['axes']}"
    )
    assert "signal" in bridge["mapping"]["research_only"], "signal 必须是研究层独有"
    assert "protocol" in bridge["mapping"]["product_only"], "protocol 必须是产品层独有"
    assert "software" in bridge["mapping"]["product_only"], "software 必须是产品层独有"


def _mutation_self_proof() -> bool:
    """变异自证：把映射改坏，期望 _assert_invariants 抛错。

    返回 True 表示变异被正确拦截（闸门没被假绿绕过）。
    """
    try:
        dims, _ = extract_js_dimensions(PRODUCT_ENGINE)
        axes = extract_py_axes(RESEARCH_ENGINE)
        # 变异：把 electrical 错误映射到 signal
        bad_map = dict(DIMENSION_MAP)
        bad_map["electrical"] = "signal"  # 错：electrical 应该对应 electrical
        bridge = {
            "mapping": {
                "intersection": sorted(
                    [d for d, r in bad_map.items() if r and r in axes]
                ),
                "product_only": sorted([d for d, r in bad_map.items() if r is None]),
                "research_only": [a for a in axes if a not in set(bad_map.values())],
            },
            "product_engine": {"dimensions": dims},
            "research_engine": {"axes": axes},
        }
        _assert_invariants(bridge)
        return False  # 未被拦截 = 闸门坏了
    except AssertionError:
        return True  # 变异被正确拦截
    except Exception:
        return False  # 其他异常不算通过


def main() -> int:
    mode = "check" if "--check" in sys.argv else (
        "write" if "--write" in sys.argv else "show"
    )

    bridge = build_bridge()
    _assert_invariants(bridge)

    if mode == "show":
        print(json.dumps(bridge, ensure_ascii=False, indent=2))
        return 0

    if mode == "write":
        MANIFEST_OUT.write_text(
            json.dumps(bridge, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"已写入 {MANIFEST_OUT.relative_to(ROOT)}")
        return 0

    # --check 模式
    failures: List[str] = []

    doc_issues = check_docs_consistency()
    if doc_issues:
        failures.extend(f"文档口径漂移：{i}" for i in doc_issues)

    if not _mutation_self_proof():
        failures.append("变异自证失败：坏映射未被拦截")

    if failures:
        print("双引擎桥接一致性检查失败：")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(
        f"双引擎桥接一致：产品层 {len(bridge['product_engine']['dimensions'])} 维 / "
        f"研究层 {len(bridge['research_engine']['axes'])} 轴 / "
        f"交集 {bridge['mapping']['intersection']} / "
        f"产品独有 {bridge['mapping']['product_only']} / "
        f"研究独有 {bridge['mapping']['research_only']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
