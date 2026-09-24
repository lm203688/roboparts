#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_pipeline — pipeline 框架自证（正 / 负 / 变异 / 生命周期）。

设计原则
--------
1. **正**：跑通真实 pipeline，产出等价于原脚本
2. **负**：坏引用 / 缺参 / 类型不匹配 / 重复注册 → 必须抛明确异常
3. **变异**：篡改产物 → 下游算子（crosscheck）必须抓出
4. **生命周期**：registry reset / by_stage / names 等辅助 API 行为正确
5. **可独立运行**：不依赖 ci_gate.py；exit code 就是判定（0 = 通过）

调用方式
--------
  python scripts/verify_pipeline.py              # 全跑，打印摘要
  python scripts/verify_pipeline.py --quiet      # 只打印失败项
  python scripts/verify_pipeline.py --verbose    # 打印每项结果
  python scripts/verify_pipeline.py --self-test  # 显式跑（等价于默认）

失败即 exit(1)——供 ci_gate 挂闸。
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import traceback
from typing import Any, Callable, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from scripts.pipeline.registry import (  # noqa: E402
    OPERATOR_REGISTRY, by_stage, get, names, operator, reset,
)
from scripts.pipeline.dag import (  # noqa: E402
    Pipeline, PipelineError, Step, build as build_pipeline, resolve_input,
)
from scripts.pipeline.stages import gap  # noqa: F401  触发 @operator 注册


# ---------- 结果收集 ----------

Results: List[Tuple[str, bool, str]] = []


def check(name: str, fn: Callable[[], Any]) -> None:
    """执行一项断言；捕获所有异常，记录 (name, ok, msg)。"""
    try:
        fn()
        Results.append((name, True, ""))
    except Exception as e:
        Results.append((name, False, f"{type(e).__name__}: {e}"))


def expect(cond: bool, msg: str = "") -> None:
    """断言 True，否则抛 AssertionError（携带 msg）。"""
    if not cond:
        raise AssertionError(msg or "断言失败")


def expect_raises(exc: type, fn: Callable[[], Any], msg: str = "") -> None:
    """断言 fn 抛 exc 类型异常。"""
    try:
        fn()
    except exc:
        return
    except Exception as e:
        raise AssertionError(
            f"期望 {exc.__name__}，实际 {type(e).__name__}: {e}。{msg}".strip())
    raise AssertionError(f"期望 {exc.__name__}，但未抛出。{msg}".strip())


# ============================================================
# 1. 正路径：算子注册 + DAG 跑通
# ============================================================

def test_registry_has_7_gap_operators():
    """阶段一：7 个 gap.* 算子已注册。"""
    gap_ops = by_stage("gap")
    expect(len(gap_ops) == 7, f"gap 阶段应有 7 个算子，实际 {len(gap_ops)}: {sorted(gap_ops)}")
    expected = {
        "gap.load_entities", "gap.derive_proprietary", "gap.classify_all",
        "gap.crosscheck", "gap.signal_axis_stats", "gap.gap_leverage",
        "gap.assemble",
    }
    expect(gap_ops == expected, f"gap 算子名不符：差 {gap_ops ^ expected}")


def test_get_and_names():
    """阶段二：get / names 辅助 API 行为正确。"""
    op = get("gap.load_entities")
    expect(op.name == "gap.load_entities")
    expect(op.stage == "gap")
    expect(callable(op.fn))
    expect(len(names()) >= 7)


def test_get_unknown_raises():
    """阶段三：未注册的算子名 → KeyError。"""
    expect_raises(KeyError, lambda: get("gap.nonexistent"))


# ============================================================
# 2. 正路径：DAG 跑通并等价原脚本
# ============================================================

def test_pipeline_runs_all_7_steps_ok():
    """阶段四：跑通 gap_classification DAG，7 步全 ok。"""
    from scripts.pipeline.run import _build_gap_classification_pipeline
    pipe = _build_gap_classification_pipeline()
    ctx = pipe.run()
    trace = pipe.to_trace()
    expect(trace["steps_total"] == 7, f"应跑 7 步，实际 {trace['steps_total']}")
    expect(trace["steps_ok"] == 7, f"7 步应全 ok，实际 {trace['steps_ok']}")
    expect(trace["steps_failed"] == 0)
    expect(trace["total_duration_ms"] > 0)


def test_pipeline_output_equivalence_with_original():
    """阶段五：**关键** —— pipeline 产出与原 build_gap_classification.build()
    逐字段等价（除 meta.generated_at / meta.generated_at 两个必然不同的字段）。

    这条是整个"重构而非重写"的证据链——只要它红了，pipeline 就与旧脚本分叉，
    必须立刻修回。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "b_gc", os.path.join(ROOT, "scripts", "build_gap_classification.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # 加载原脚本

    orig = mod.build()

    from scripts.pipeline.run import _build_gap_classification_pipeline
    pipe = _build_gap_classification_pipeline()
    ctx = pipe.run()
    new = ctx["gap.assemble"]

    SKIP = {"meta.generated_at", "meta.generated_by"}

    def walk(x, y, path=""):
        diffs = []
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                p = f"{path}.{k}" if path else k
                if p in SKIP:
                    continue
                if k not in x or k not in y:
                    diffs.append(f"{p}: 一方缺")
                    continue
                diffs.extend(walk(x[k], y[k], p))
        elif isinstance(x, list) and isinstance(y, list):
            if len(x) != len(y):
                diffs.append(f"{path}: 长度 {len(x)} vs {len(y)}")
            else:
                for i, (xi, yi) in enumerate(zip(x, y)):
                    diffs.extend(walk(xi, yi, f"{path}[{i}]"))
        else:
            if x != y:
                diffs.append(f"{path}: {repr(x)[:60]} vs {repr(y)[:60]}")
        return diffs

    diffs = walk(orig, new)
    expect(not diffs, f"pipeline 与原脚本不等价，共 {len(diffs)} 处：{diffs[:5]}")


# ============================================================
# 3. 负路径：引用解析错误
# ============================================================

def test_resolve_input_unknown_step_raises():
    """阶段六：引用未产出的步骤 → PipelineError。"""
    # 注意：resolve_input 会把未匹配到 context key 的字符串当字面量返回。
    # 所以"未产出步骤"测试要通过"某处已注册了名字但被引用"来触发。
    ctx = {"gap.load_entities": {"items": [1, 2, 3]}}
    # 直接引用一个不存在的 key 但用已知步骤名开头 → 应 raise
    expect_raises(
        PipelineError,
        lambda: resolve_input("gap.load_entities.nonexistent_key", ctx),
    )


def test_resolve_input_out_of_range_list_raises():
    """阶段七：引用越界列表索引 → PipelineError。"""
    ctx = {"gap.load_entities": {"items": [1, 2, 3]}}
    expect_raises(
        PipelineError,
        lambda: resolve_input("gap.load_entities.items.99", ctx),
        "列表长度 3，索引 99 应越界"
    )


def test_resolve_input_literal_passthrough():
    """阶段八：字面量（无匹配步骤名前缀）原样返回。"""
    ctx = {"gap.load_entities": {"items": [1, 2, 3]}}
    # "api/entities.json" — "api" 不是 context 里的步骤名 → 字面量
    expect(resolve_input("api/entities.json", ctx) == "api/entities.json")
    # 简单字符串
    expect(resolve_input("hello", ctx) == "hello")
    # 非字符串
    expect(resolve_input(42, ctx) == 42)
    expect(resolve_input(None, ctx) is None)
    expect(resolve_input([1, 2], ctx) == [1, 2])


# ============================================================
# 4. 负路径：算子注册错误
# ============================================================

def test_duplicate_operator_name_raises():
    """阶段九：算子重名 → ValueError（fail-fast）。"""
    def _fn():  # noqa
        pass
    expect_raises(
        ValueError,
        lambda: operator("gap.load_entities", "gap", "重名")(_fn),
        "gap.load_entities 已注册，重名应报错"
    )


def test_operator_name_format_enforced():
    """阶段十：算子名必须为 `<stage>.<verb>` 形式。"""
    def _fn():  # noqa
        pass
    expect_raises(ValueError, lambda: operator("nodots", "gap", "格式错")(_fn))
    expect_raises(ValueError, lambda: operator("", "gap", "空名")(_fn))


# ============================================================
# 5. 变异：篡改下游算子返回 → 上游交叉校验必须抓出
# ============================================================

def test_crosscheck_catches_solved_mismatch():
    """阶段十一：buckets.solved 与 facts.mech_declared 不一致 → SystemExit。"""
    from scripts.pipeline.stages.gap import crosscheck as _cc
    buckets = {"solved": 26, "na": 363, "proprietary_suspect": 5,
               "unpublished_suspect": 350, "ambiguous": 59}
    facts = {"mech_declared": 25, "total_entities": 802}
    expect_raises(SystemExit, lambda: _cc(buckets, facts))


def test_crosscheck_catches_total_mismatch():
    """阶段十二：sum(buckets.values()) != facts.total_entities → SystemExit。"""
    from scripts.pipeline.stages.gap import crosscheck as _cc
    buckets = {"solved": 25, "na": 363, "proprietary_suspect": 5,
               "unpublished_suspect": 350, "ambiguous": 58}  # 59→58，故意缺 1
    facts = {"mech_declared": 25, "total_entities": 802}
    expect_raises(SystemExit, lambda: _cc(buckets, facts))


def test_crosscheck_passes_when_consistent():
    """阶段十三：crosscheck 通过时返回 ok=True（正向对照）。"""
    from scripts.pipeline.stages.gap import crosscheck as _cc
    buckets = {"solved": 25, "na": 363, "proprietary_suspect": 5,
               "unpublished_suspect": 350, "ambiguous": 59}
    facts = {"mech_declared": 25, "total_entities": 802}
    result = _cc(buckets, facts)
    expect(result["ok"] is True)
    expect(result["solved"] == 25)


def test_pipeline_error_wraps_operator_exception():
    """阶段十四：算子内部异常被 PipelineError 包装并含步骤名。"""
    @operator("gap._mutated_boom", "gap", "测试用：抛异常")
    def _boom(x):
        raise RuntimeError("boom!")

    pipe = build_pipeline("mutated", [
        Step(op="gap._mutated_boom", inputs={"x": 42}),
    ])
    try:
        pipe.run()
        raise AssertionError("应抛 PipelineError")
    except PipelineError as e:
        expect("gap._mutated_boom" in str(e), f"错误消息应含步骤名：{e}")
        expect("boom" in str(e), f"错误消息应含原始异常文本：{e}")
    finally:
        OPERATOR_REGISTRY.pop("gap._mutated_boom", None)


# ============================================================
# 6. 生命周期：registry reset / trace 结构
# ============================================================

def test_registry_reset_clears_all():
    """阶段十五：registry.reset 清空所有算子，importlib.reload 可复原。

    注意：单纯 `import ... as _g` 第二次导入是 no-op（Python 缓存模块），
    必须用 importlib.reload 才能真正重跑模块顶层的 @operator 装饰器。
    """
    import importlib

    before = len(OPERATOR_REGISTRY)
    expect(before >= 7, f"应有 ≥7 个算子，实际 {before}")

    reset()
    expect(len(OPERATOR_REGISTRY) == 0, f"reset 后应为空，实际 {len(OPERATOR_REGISTRY)}")

    # reload 触发 @operator 装饰器重跑
    import scripts.pipeline.stages.gap as _g
    importlib.reload(_g)

    after = len(OPERATOR_REGISTRY)
    expect(after >= 7, f"reload 后应恢复 ≥7 个，实际 {after}")


def test_trace_contains_expected_keys():
    """阶段十六：trace 结构完整。"""
    from scripts.pipeline.run import _build_gap_classification_pipeline
    pipe = _build_gap_classification_pipeline()
    pipe.run()
    trace = pipe.to_trace()
    for k in ("pipeline", "steps_total", "steps_ok", "steps_failed",
              "total_duration_ms", "traces"):
        expect(k in trace, f"trace 缺键 {k}")
    expect(len(trace["traces"]) == 7)
    for t in trace["traces"]:
        for k in ("op", "ok", "duration_ms", "error", "output_summary"):
            expect(k in t, f"trace.traces[] 缺键 {k}：{t}")
        expect(t["ok"] is True)
        expect(t["error"] is None)
        expect(t["duration_ms"] >= 0)


def test_step_result_has_all_fields():
    """阶段十七：StepResult 结构完整。"""
    from scripts.pipeline.dag import StepResult
    sr = StepResult(op="test", ok=True, duration_ms=1.0, error=None, output_summary=None)
    expect(sr.op == "test" and sr.ok is True and sr.duration_ms == 1.0)
    sr_bad = StepResult(op="bad", ok=False, duration_ms=1.0, error="err", output_summary=None)
    expect(sr_bad.ok is False and sr_bad.error == "err")


# ============================================================
# 主入口
# ============================================================

def run_all_tests():
    global Results
    Results = []

    check("01 registry 已注册 7 个 gap 算子", test_registry_has_7_gap_operators)
    check("02 get/names 辅助 API 正常", test_get_and_names)
    check("03 未注册算子 → KeyError", test_get_unknown_raises)
    check("04 DAG 跑通 7 步全 ok", test_pipeline_runs_all_7_steps_ok)
    check("05 pipeline 产出与原脚本逐字段等价", test_pipeline_output_equivalence_with_original)
    check("06 引用未存在键 → PipelineError", test_resolve_input_unknown_step_raises)
    check("07 引用越界列表 → PipelineError", test_resolve_input_out_of_range_list_raises)
    check("08 字面量原样返回", test_resolve_input_literal_passthrough)
    check("09 算子重名 → ValueError", test_duplicate_operator_name_raises)
    check("10 算子名格式校验", test_operator_name_format_enforced)
    check("11 crosscheck 抓出 solved 不一致", test_crosscheck_catches_solved_mismatch)
    check("12 crosscheck 抓出 total 不一致", test_crosscheck_catches_total_mismatch)
    check("13 crosscheck 正向对照通过", test_crosscheck_passes_when_consistent)
    check("14 算子异常被 PipelineError 包装", test_pipeline_error_wraps_operator_exception)
    check("15 registry.reset 清空并复原", test_registry_reset_clears_all)
    check("16 trace 结构完整", test_trace_contains_expected_keys)
    check("17 StepResult 结构完整", test_step_result_has_all_fields)

    return Results


def main(argv=None):
    p = argparse.ArgumentParser(description="RoboParts pipeline 框架自证")
    p.add_argument("--quiet", action="store_true", help="只打印失败项")
    p.add_argument("--verbose", action="store_true", help="打印每项结果")
    p.add_argument("--self-test", action="store_true", help="（默认行为，别名）")
    args = p.parse_args(argv)

    Results = run_all_tests()

    passed = sum(1 for _, ok, _ in Results if ok)
    failed = sum(1 for _, ok, _ in Results if not ok)

    if args.verbose or failed > 0 or not args.quiet:
        print(f"pipeline 自证：{len(Results)} 项，{passed} 通过 / {failed} 失败")
        for name, ok, msg in Results:
            if ok and not args.verbose:
                continue
            mark = "✅" if ok else "❌"
            line = f"  {mark} {name}"
            if not ok:
                line += f" — {msg}"
            print(line)

    if failed:
        print(f"\n❌ 共 {failed} 项失败，请修复后重跑。", file=sys.stderr)
        return 1
    print(f"✅ pipeline 自证全绿（{passed} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
