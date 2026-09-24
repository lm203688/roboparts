#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RoboParts pipeline — 最小 operator+DAG 骨架。

用法::

    # 定义算子
    from scripts.pipeline.registry import operator

    @operator("gap.load_entities", "gap", "读 api/entities.json")
    def load_entities(path: str) -> dict:
        ...

    # 声明并执行 pipeline
    from scripts.pipeline import build, Step

    pipe = build("gap_classification", [
        Step(op="gap.load_entities", inputs={"path": "api/entities.json"}),
        Step(op="gap.derive_proprietary", inputs={"items": "gap.load_entities.items"}),
        ...
    ])
    ctx = pipe.run()
    trace = pipe.to_trace()

设计要点：零依赖 stdlib，纯函数算子，失败即停。详见各模块 docstring。
"""
from .registry import (  # noqa: F401
    operator, get, names, by_stage, reset, OPERATOR_REGISTRY, Operator,
)
from .dag import (  # noqa: F401
    Pipeline, Step, StepResult, PipelineError, build, resolve_input,
)

__all__ = [
    "operator", "get", "names", "by_stage", "reset", "OPERATOR_REGISTRY", "Operator",
    "Pipeline", "Step", "StepResult", "PipelineError", "build", "resolve_input",
]
