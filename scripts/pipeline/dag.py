#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline.dag — 声明式 DAG 执行器 + trace。

核心设计
--------
1. **顺序执行 + 显式依赖**：不做拓扑排序，用户按列表顺序写步骤，
   前置步骤的返回 dict 挂到上下文里，后一步按 `"prev_op.key"` 引用取值。
   拓扑排序在多阶段并行时才有意义，目前我们所有 pipeline 都是串行，
   强行排序反而让错误信息变差（哪一步依赖了哪一步需要靠图搜索）。
2. **每一步留下 trace**：算子名、耗时、是否成功、错误摘要、输出摘要。
   trace 里**不塞完整返回值**（避免几十 KB 的 JSON 挤爆日志），只塞摘要。
3. **失败即停**：任一步骤异常立刻抛 PipelineError，不做"跳过坏步骤继续跑"。
   组合系统里静默跳过是最坏的选择——下游会拿到 None 然后一路假绿。
4. **失败也留痕**：抛异常之前先把失败步骤写进 traces，事后能查是哪里炸的。

为什么不引入 pyyaml
-------------------
YAML 声明式配置是 DataFlow 的亮点，但对我们是过度工程：
- 引入一个第三方依赖，就要走 pyproject/pip install 流程；
- 我们的 pipeline 都是本地跑，声明写代码里跟写在文件里差别不大；
- 出错时"配置文件语法错"比"代码错"更难定位。

所以 DAG 声明是 **Python dict**，直接在代码里声明。想复用/共享时再抽成 JSON
文件也不迟，那时再决定要不要 yaml。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .registry import get as get_operator, Operator


class PipelineError(Exception):
    """DAG 执行失败。message 含步骤名与真实异常文本。"""


@dataclass
class Step:
    """一个 DAG 步骤：算子名 + 输入绑定。

    inputs 值支持两种：
    - 字面量：原样传给算子
    - 字符串 `"prev_op"` 或 `"prev_op.key"`：从上下文取值（前置步骤的返回 dict）
    """
    op: str
    inputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """一步的执行结果（成功或失败都留）。"""
    op: str
    ok: bool
    duration_ms: float
    error: Optional[str] = None
    output_summary: Any = None


def resolve_input(value: Any, context: Dict[str, Any]) -> Any:
    """把 inputs 值解析为真实参数值。

    **关键设计**：算子名本身含点号（`gap.load_entities`），
    不能按 `.` 分段做 head/middle。改成**匹配 context 里已有的步骤名**作为 head：

    1. 非字符串 → 原样返回
    2. 字符串 → 尝试匹配 context 里某个步骤名作为前缀（取最长匹配）
       - `"gap.load_entities.items"` + context 里有 `"gap.load_entities"` → 引用
       - `"api/entities.json"` + context 无 `"api"` → 字面量
       - `"gap"` + context 里有 `"gap"` → 引用（整个步骤返回值）
    3. 未匹配到任何步骤名前缀 → 视为字面量
    4. 引用剩余部分按点号分层深入 dict/list；任一层不存在 → PipelineError

    最长匹配是关键：`"gap.load_entities.items"` 既能匹配到 `"gap"` 又能匹配到
    `"gap.load_entities"`，我们取后者。这样即便 stage 名跟某步骤名撞了，
    也不会歧义。
    """
    if not isinstance(value, str):
        return value

    # 找出 context 里作为 value 前缀的最长 key
    # value == key（无 .）或 value 以 key + "." 开头
    sorted_keys = sorted(context.keys(), key=len, reverse=True)
    matched_key = None
    for key in sorted_keys:
        if value == key or value.startswith(key + "."):
            matched_key = key
            break

    if matched_key is None:
        return value  # 字面量

    if value == matched_key:
        return context[matched_key]

    remainder = value[len(matched_key) + 1:]  # 剥掉 "matched_key."
    target = context[matched_key]
    for key_part in remainder.split("."):
        if isinstance(target, dict) and key_part in target:
            target = target[key_part]
        elif isinstance(target, list) and key_part.isdigit():
            i = int(key_part)
            if i < len(target):
                target = target[i]
            else:
                raise PipelineError(
                    f"引用越界: {value}（列表长度 {len(target)}）")
        else:
            raise PipelineError(
                f"引用解析失败: {value}（在 {type(target).__name__} 上无键 {key_part!r}）")
    return target


def _summarize(v: Any) -> Any:
    """轻量摘要：避免 trace 里塞完整返回值（大 JSON 会让 trace 挤爆）。

    dict → 键名列表；list/set → 长度；其他 → repr 截断。
    """
    if v is None:
        return None
    if isinstance(v, dict):
        return {k: f"<{type(v[k]).__name__}>" for k in list(v.keys())[:10]}
    if isinstance(v, (list, tuple)):
        return f"{type(v).__name__}[{len(v)}]"
    if isinstance(v, set):
        return f"set[{len(v)}]"
    if isinstance(v, str):
        return v[:120]
    return repr(v)[:120]


class Pipeline:
    """声明式 DAG。构造 → run → 拿到 (final_context, traces)。"""

    def __init__(self, name: str, steps: List[Step]):
        if not name:
            raise ValueError("Pipeline name 不能为空")
        if not steps:
            raise ValueError(f"Pipeline {name!r} 至少需要一个步骤")
        self.name = name
        self.steps = steps
        self.traces: List[StepResult] = []

    def run(self, initial_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行 DAG，返回最终上下文（每个步骤的返回都挂在这里，按 op 名索引）。"""
        ctx: Dict[str, Any] = dict(initial_context or {})
        self.traces = []

        for step in self.steps:
            # 预解析 inputs（早失败：引用错就在此步抛，不算 op 执行错）
            resolved: Dict[str, Any] = {}
            try:
                for k, v in step.inputs.items():
                    resolved[k] = resolve_input(v, ctx)
            except PipelineError:
                raise

            t0 = time.perf_counter()
            try:
                op = get_operator(step.op)
                result = op.fn(**resolved)
                dur = (time.perf_counter() - t0) * 1000.0
                ctx[step.op] = result
                self.traces.append(StepResult(
                    op=step.op, ok=True, duration_ms=dur,
                    error=None, output_summary=_summarize(result),
                ))
            except Exception as e:
                dur = (time.perf_counter() - t0) * 1000.0
                self.traces.append(StepResult(
                    op=step.op, ok=False, duration_ms=dur,
                    error=f"{type(e).__name__}: {e}", output_summary=None,
                ))
                # 失败即停——不做"跳过继续跑"（会让下游拿 None 一路假绿）
                raise PipelineError(
                    f"[{self.name}] 步骤 {step.op} 失败: {type(e).__name__}: {e}"
                ) from e

        return ctx

    def to_trace(self) -> Dict[str, Any]:
        """导出可 JSON 序列化的 trace 摘要（用于日志/审计）。"""
        return {
            "pipeline": self.name,
            "steps_total": len(self.steps),
            "steps_ok": sum(1 for t in self.traces if t.ok),
            "steps_failed": sum(1 for t in self.traces if not t.ok),
            "total_duration_ms": round(sum(t.duration_ms for t in self.traces), 3),
            "traces": [
                {
                    "op": t.op,
                    "ok": t.ok,
                    "duration_ms": round(t.duration_ms, 3),
                    "error": t.error,
                    "output_summary": t.output_summary,
                }
                for t in self.traces
            ],
        }


def build(name: str, steps: List[Step]) -> Pipeline:
    """便捷构造器。"""
    return Pipeline(name, steps)
