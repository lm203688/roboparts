#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pipeline.run — CLI 入口：python -m scripts.pipeline.run <pipeline_name> [--trace]

用法::

    # 列出所有已注册 pipeline
    python -m scripts.pipeline.run --list

    # 列出所有已注册算子
    python -m scripts.pipeline.run --ops

    # 跑一个 pipeline（当前只有 gap_classification）
    python -m scripts.pipeline.run gap_classification --trace

    # 打印 pipeline 定义（不执行）
    python -m scripts.pipeline.run gap_classification --dry-run

Pipeline 定义通过 PIPELINES 字典注册。目前只有 gap_classification——
后续每接一个 build_*.py 重构，就加一条到这里。
"""
from __future__ import annotations

import argparse
import json
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def _ensure_stages_loaded() -> None:
    """显式导入 stages/*，触发 @operator 装饰器注册。

    为什么不用 importlib 扫描？——importlib 是"运行时反射"，我们的算子
    是**静态声明**，导入顺序可控，直接用 import 语句更清晰可审计。
    以后加 stage 就在这里加一行，一目了然。
    """
    import scripts.pipeline.stages.gap  # noqa: F401


def _build_gap_classification_pipeline():
    """声明 gap_classification 的 DAG。

    与 build_gap_classification.py 原脚本对照——本 DAG 是它的**分解重放**，
    不是新逻辑。每一步的输入输出与原子函数一一对应，方便逐字段比对产物。
    """
    from .dag import Pipeline, Step

    return Pipeline("gap_classification", [
        Step(op="gap.load_entities", inputs={
            "path": "api/entities.json",
        }),
        Step(op="gap.derive_proprietary", inputs={
            "items": "gap.load_entities.items",
        }),
        Step(op="gap.classify_all", inputs={
            "items": "gap.load_entities.items",
            "proprietary_mfrs": "gap.derive_proprietary",
        }),
        Step(op="gap.crosscheck", inputs={
            "buckets": "gap.classify_all.buckets",
            "facts": "gap.load_entities.facts",
        }),
        Step(op="gap.signal_axis_stats", inputs={
            "path": "api/morphology_graph.json",
        }),
        Step(op="gap.gap_leverage", inputs={
            "items": "gap.load_entities.items",
            "buckets": "gap.classify_all.buckets",
        }),
        Step(op="gap.assemble", inputs={
            "items": "gap.load_entities.items",
            "buckets": "gap.classify_all.buckets",
            "per_category": "gap.classify_all.per_category",
            "examples": "gap.classify_all.examples",
            "physical_open_gap": "gap.classify_all.physical_open_gap",
            "proprietary_mfrs": "gap.derive_proprietary",
            "signal_axis": "gap.signal_axis_stats",
            "gap_leverage": "gap.gap_leverage",
            "facts": "gap.load_entities.facts",
        }),
    ])


# 全部已注册 pipeline 名 -> 构造函数
PIPELINES = {
    "gap_classification": _build_gap_classification_pipeline,
}


def _cmd_list(args):
    print("已注册 pipeline:")
    for name in sorted(PIPELINES.keys()):
        print(f"  - {name}")


def _cmd_ops(args):
    from .registry import OPERATOR_REGISTRY
    print(f"已注册算子（{len(OPERATOR_REGISTRY)} 个）:")
    by_stage: dict = {}
    for name, op in sorted(OPERATOR_REGISTRY.items()):
        by_stage.setdefault(op.stage, []).append(op)
    for stage in sorted(by_stage.keys()):
        print(f"  [{stage}]")
        for op in by_stage[stage]:
            desc = f" — {op.description}" if op.description else ""
            print(f"    - {op.name}{desc}")


def _cmd_run(args):
    name = args.name
    if name not in PIPELINES:
        sys.exit(f"未知 pipeline: {name}（已知：{sorted(PIPELINES)}）")

    if args.dry_run:
        pipe = PIPELINES[name]()
        print(f"Pipeline: {pipe.name}")
        print(f"Steps ({len(pipe.steps)}):")
        for i, s in enumerate(pipe.steps, 1):
            inputs = ", ".join(f"{k}={v!r}" for k, v in s.inputs.items())
            print(f"  {i}. {s.op}({inputs})")
        return

    pipe = PIPELINES[name]()
    ctx = pipe.run()

    if args.trace:
        print(json.dumps(pipe.to_trace(), ensure_ascii=False, indent=2))
        print("---")

    # 把最后一步的输出作为 pipeline 结果
    final_step = pipe.steps[-1]
    result = ctx[final_step.op]
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[written] {args.out}", file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(description="RoboParts pipeline CLI")
    sub = p.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="列出已注册 pipeline")
    p_list.set_defaults(func=_cmd_list)

    p_ops = sub.add_parser("ops", help="列出已注册算子")
    p_ops.set_defaults(func=_cmd_ops)

    p_run = sub.add_parser("run", help="执行 pipeline")
    p_run.add_argument("name", help="pipeline 名")
    p_run.add_argument("--trace", action="store_true", help="打印执行 trace")
    p_run.add_argument("--dry-run", action="store_true", help="只打印 DAG 定义不执行")
    p_run.add_argument("--out", help="把最终结果写入文件（覆盖）")
    p_run.set_defaults(func=_cmd_run)

    args = p.parse_args(argv)
    if not getattr(args, "cmd", None):
        p.print_help()
        sys.exit(1)
    _ensure_stages_loaded()
    args.func(args)


if __name__ == "__main__":
    main()
