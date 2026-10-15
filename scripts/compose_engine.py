#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compose_engine — RoboParts 组合判定的 **IO 层 + 向后兼容入口**。

⚠️ **重要（Phase A · A1）**：
从 2026-10-15 起，本模块的所有**判据、常量、纯函数**已迁移到
`scripts/compose_core.py`（零 IO / 零全局状态 / 零副作用的纯函数内核）。

本文件保留的目的：
1. **向后兼容**：现有 20+ 处 `from compose_engine import X` 不改动；
2. **IO 层**：读 `api/morphology_graph.json`、写 `api/compose_semantics.json` 的文件
   系统逻辑；
3. **CLI 入口**：`python scripts/compose_engine.py` 仍可跑一次全对评测的 smoke test。

**任何新的判据测试（A2 性质测试、A3 assemble 原语、CI 闸门）都必须直接 import
`compose_core`，不允许再绕过本模块**。这样 mutation-score.json 的 honest_limits 建议
「S2 抽出 compose_core 后可升级到引擎层」的诉求才真正落地。

判据单一真相源（Phase A 硬约束）：
- 常量、轴、pair 排序、reflexivity 公理：`compose_core`
- 类型语义（type_compat 构建）：`api/morphology_graph.json`
- 规则表 R0–R5：`compose_core.RULE_TABLE`
- 代数律（A2 测试目标）：`compose_core.ALGEBRAIC_LAWS`
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

# ── 把 scripts/ 加到 sys.path，让相对导入稳 ──────────────────────────────
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# ── 单一判据源：一切从 compose_core 导出 ────────────────────────────────
from compose_core import (  # noqa: F401,E402
    CORE_VERSION,
    ENGINE_VERSION,
    AXES,
    PAIR_RANK,
    AXIS_VERDICT_OF_PAIR,
    PAIR_VERDICTS,
    AXIS_VERDICTS,
    OVERALL_VERDICTS,
    EFFECTIVE_STATUS,
    SIG_OUTPUT,
    SIG_INPUT,
    SIG_REWARD,
    ComposeTypeError,
    axis_of,
    effective_ports,
    undeclared_count,
    CompatIndex,
    compose,
    eval_all_pairs,
    RULE_TABLE,
    ROLES,
    ALGEBRAIC_LAWS,
)


__all__ = [
    # 兼容 re-export
    "CORE_VERSION", "ENGINE_VERSION", "AXES", "PAIR_RANK",
    "AXIS_VERDICT_OF_PAIR", "PAIR_VERDICTS", "AXIS_VERDICTS", "OVERALL_VERDICTS",
    "EFFECTIVE_STATUS", "SIG_OUTPUT", "SIG_INPUT", "SIG_REWARD",
    "ComposeTypeError", "axis_of", "effective_ports", "undeclared_count",
    "CompatIndex", "compose", "eval_all_pairs", "RULE_TABLE", "ROLES",
    "ALGEBRAIC_LAWS",
    # IO 层
    "load_graph", "save_result", "ROOT", "GRAPH_PATH",
]


# ── IO 层（本文件独占）───────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
GRAPH_PATH = ROOT / "api" / "morphology_graph.json"


def load_graph(path: "Path | None" = None) -> Dict[str, Any]:
    """读 morphology_graph.json。纯 IO，不含任何判定逻辑。"""
    import json
    p = Path(path) if path else GRAPH_PATH
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_result(result: Dict[str, Any], path: "Path | None" = None) -> None:
    """写 compose_semantics 类产物。纯 IO。"""
    import json
    p = Path(path) if path else ROOT / "api" / "compose_semantics.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ── CLI smoke test ──────────────────────────────────────────────────────
def _cli() -> int:
    """`python scripts/compose_engine.py` — 一次性全对评测，验证迁移后仍一致。"""
    import json
    graph = load_graph()
    result = eval_all_pairs(graph, examples_per_class=3)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
