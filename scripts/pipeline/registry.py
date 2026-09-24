#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline.registry — 算子注册表（DAG 骨架的原子单元）。

设计取舍
--------
- 纯函数：每个算子输入 → 输出，无副作用（不读文件、不写文件、不发网络）。
  文件 IO 由 stage 内的显式算子负责（如 gap.load_entities）。
- 装饰器注册：`@operator(name, stage, description)` 把函数挂到全局表，
  避免运行时反射；重复注册即报错（fail-fast）。
- 零依赖：只用 stdlib。DataFlow 那种重型框架不适合我们——部署在 CF Pages，
  脚本本地跑，不需要 LLM 推理能力。我们只借它的**算子+DAG 建模思路**，
  不搬代码。

命名约定
--------
- name 全仓唯一，格式 `<stage>.<verb>`（如 `gap.load_entities`）。
- stage 是分组标签（如 `gap`、`morphology`、`compose`），便于按领域筛算子。
- description 面向人读，进 trace 便于审计。

引用解析
--------
DAG 步骤的 inputs 值可以是：
- 字面量：原样传递
- 字符串 `"prev_op.key"`：从上下文（此前步骤的返回 dict）按点号路径取值
- 字符串 `"prev_op"`（无点号）：直接取该步骤的整个返回值

详见 dag.py::resolve_input。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, Set


@dataclass(frozen=True)
class Operator:
    """一个已注册算子的元数据 + 可调用对象。"""
    name: str
    stage: str
    description: str
    fn: Callable


# 全局注册表：name -> Operator
OPERATOR_REGISTRY: Dict[str, Operator] = {}


def operator(name: str, stage: str, description: str = ""):
    """装饰器：把纯函数注册为算子。

    用法::

        @operator("gap.load_entities", "gap", "读 api/entities.json")
        def load_entities(path: str) -> dict:
            ...
    """
    if not name or "." not in name:
        raise ValueError(f"算子名必须为 '<stage>.<verb>' 形式，收到 {name!r}")
    if name in OPERATOR_REGISTRY:
        raise ValueError(f"算子重名: {name}（先反注册或换名）")

    def deco(fn: Callable) -> Callable:
        OPERATOR_REGISTRY[name] = Operator(
            name=name, stage=stage, description=description, fn=fn)
        return fn

    return deco


def get(name: str) -> Operator:
    """按名取算子。未注册即 KeyError（fail-fast，不静默降级）。"""
    try:
        return OPERATOR_REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"未注册的算子: {name}（已知 {len(OPERATOR_REGISTRY)} 个）") from None


def names() -> FrozenSet[str]:
    return frozenset(OPERATOR_REGISTRY.keys())


def by_stage(stage: str) -> Set[str]:
    return {n for n, op in OPERATOR_REGISTRY.items() if op.stage == stage}


def reset() -> None:
    """清空注册表——仅供测试用（生产路径不调用）。"""
    OPERATOR_REGISTRY.clear()


def __all__() -> list:
    return ["operator", "get", "names", "by_stage", "reset", "Operator"]
