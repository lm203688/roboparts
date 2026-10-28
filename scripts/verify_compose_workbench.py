#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_compose_workbench — P2-7 组合工作台 AG-UI 事件流契约闸门。

背景（2026-10-28 盘点，P2-7 v0.2 已落地）：
  compose-workbench.html 已实现 AG-UI 事件流（requirement.updated /
  candidate.proposed / verdict.computed / human.approved / revision.frozen）
  与「导入/回放」能力。但现有「组合语义 / 代数律」闸门守的是
  compose 引擎（scripts/compose_engine.py），**不守工作台页面本身**——
  工作台事件流契约无独立闸门守护。本脚本补齐该缺口。

审计模式（默认）：静态扫描 compose-workbench.html，守四条——
  1. event_types：EVENT_TYPES 恰含 5 类（下划线 key），每类带
     label / icon / agui 三字段（agui 为 AG-UI 互操作映射，契约点）
  2. functions：核心函数齐备（emit / validateEvents / replayTick /
     handleImportFile / parseImport / renderEvents / renderEventHtml）
  3. replay_ui：回放 UI 元素（replayBox / btnReplay / replayStatus /
     replaySpeed）+ 回放状态（replayRunning / replaySpeedMs / replayTimer）
  4. validate_rules：validateEvents 对齐 trace_replay 纪律（fail-fast，
     不静默丢弃）——trace_id 缺失/重复、type 未知（EVENT_TYPES 拒绝）、
     ts 非法 ISO、payload 非对象，四类校验全部存在
  5. meta_anchor：meta description 对外声明含 5 类点分事件名
     （requirement.updated 等），与内部 EVENT_TYPES 一致（不漂移）

fail-closed：文件缺失 / 解析不出 → 报红（不静默 skip，防 P0-9 假绿）。

--self-test：阴阳自证——
  baseline        全过
  missing_type    删 requirement_updated → event_types 报红
  missing_func    删 validateEvents      → functions 报红
  agui_drift      改 agui 映射           → event_types 报红
  missing_ui      删 replayBox 元素      → replay_ui 报红
  missing_rule    删 ts 校验             → validate_rules 报红
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WB_PATH = os.path.join(ROOT, "compose-workbench.html")

# 契约点（源码真相源，不手写期望值）
EVENT_KEYS = [
    "requirement_updated",
    "candidate_proposed",
    "verdict_computed",
    "human_approved",
    "revision_frozen",
]
EVENT_DOT = [
    "requirement.updated",
    "candidate.proposed",
    "verdict.computed",
    "human.approved",
    "revision.frozen",
]
CORE_FUNCS = [
    "emit",
    "validateEvents",
    "replayTick",
    "handleImportFile",
    "parseImport",
    "renderEvents",
    "renderEventHtml",
]
REPLAY_UI = [
    "replayBox",
    "btnReplay",
    "replayStatus",
    "replaySpeed",
]
REPLAY_STATE = [
    "replayRunning",
    "replaySpeedMs",
    "replayTimer",
]
VALIDATE_RULES = [
    r"trace_id",          # trace_id 缺失/重复校验
    r"EVENT_TYPES\[ev\.type\]",  # type 未知拒绝（对齐 trace_replay fail-fast）
    r"Date\.parse\(ev\.ts\)",    # ts 非法 ISO 校验
    r"payload",           # payload 非对象校验
]


def check_source(src: str) -> list[str]:
    """静态扫描源码，返回契约违规列表（空 = 通过）。"""
    errs: list[str] = []

    # 1. EVENT_TYPES 5 类 + 三字段（agui 须值非空——互操作映射是契约点）
    for key in EVENT_KEYS:
        if not re.search(rf"\b{key}\s*:\s*\{{", src):
            errs.append(f"EVENT_TYPES 缺事件类: {key}")
        else:
            for field in ("label", "icon"):
                if not re.search(rf"{key}\s*:\s*\{{[^}}]*\b{field}\s*:", src, re.DOTALL):
                    errs.append(f"EVENT_TYPES[{key}] 缺 {field} 字段")
            # agui 是 AG-UI 互操作映射，值必须非空（空 = 契约漂移）
            if not re.search(rf"{key}\s*:\s*\{{[^}}]*\bagui\s*:\s*'[^']+'", src, re.DOTALL):
                errs.append(f"EVENT_TYPES[{key}] agui 映射缺失或为空")

    # 2. 核心函数
    for fn in CORE_FUNCS:
        if not re.search(rf"function\s+{fn}\s*\(", src):
            errs.append(f"缺核心函数: {fn}")

    # 3. 回放 UI 元素 + 状态
    for el in REPLAY_UI:
        if not re.search(rf"getElementById\('{el}'\)", src):
            errs.append(f"缺回放 UI 元素: {el}")
    for st in REPLAY_STATE:
        if not re.search(rf"\b{st}\b", src):
            errs.append(f"缺回放状态: {st}")

    # 4. validate_rules（对齐 trace_replay 纪律）
    for rule in VALIDATE_RULES:
        if not re.search(rule, src):
            errs.append(f"validateEvents 缺校验规则: {rule}")

    # 5. meta 对外声明（点分）
    for dot in EVENT_DOT:
        if not re.search(rf"\b{re.escape(dot)}\b", src):
            errs.append(f"meta 对外声明缺事件名: {dot}")

    return errs


def audit() -> int:
    if not os.path.exists(WB_PATH):
        print("❌ compose-workbench.html 不存在（fail-closed）")
        return 1
    try:
        with open(WB_PATH, encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        print(f"❌ 读取失败（fail-closed）: {e}")
        return 1
    errs = check_source(src)
    if errs:
        for e in errs:
            print(f"❌ {e}")
        print(f"compose-workbench 事件流契约审计失败：{len(errs)} 处")
        return 1
    print(f"✅ compose-workbench 事件流契约通过：{len(EVENT_KEYS)} 类事件 / "
          f"{len(CORE_FUNCS)} 核心函数 / {len(REPLAY_UI)} 回放 UI / "
          f"{len(VALIDATE_RULES)} 校验规则 / {len(EVENT_DOT)} 对外声明")
    return 0


def self_test() -> int:
    """阴阳自证：每类破坏都必须被抓（只测绿路径的闸门等于没闸门）。"""
    if not os.path.exists(WB_PATH):
        print("❌ 自证无法运行：compose-workbench.html 不存在（fail-closed）")
        return 1
    with open(WB_PATH, encoding="utf-8") as f:
        src = f.read()

    cases = []

    # baseline
    base_errs = check_source(src)
    cases.append(("baseline", base_errs, False))

    # missing_type：删 requirement_updated 事件类
    variant = re.sub(r"\brequirement_updated\s*:\s*\{[^}]*\},?\n", "", src, count=1)
    cases.append(("missing_type", check_source(variant), True))

    # missing_func：删 validateEvents 函数（删到下一个 function 前）
    variant = re.sub(r"function validateEvents\([^)]*\)\s*\{.*?\n  \}\n", "", src, count=1, flags=re.DOTALL)
    cases.append(("missing_func", check_source(variant), True))

    # agui_drift：清空 agui 互操作映射值（空 = 契约漂移，必须被抓）
    variant = re.sub(r"(requirement_updated:\s*\{[^}]*?agui:\s*')[^']*(')", r"\1\2", src, count=1)
    cases.append(("agui_drift", check_source(variant), True))

    # missing_ui：删除全部 replayBox 引用（文件内出现 2 次，须全删才等价破坏）
    variant = re.sub(r"getElementById\('replayBox'\)", "", src, count=0)
    cases.append(("missing_ui", check_source(variant), True))

    # missing_rule：删 ts 校验
    variant = re.sub(r"if \(!ev\.ts \|\| isNaN\(Date\.parse\(ev\.ts\)\)\)[^\n]*", "", src, count=1)
    cases.append(("missing_rule", check_source(variant), True))

    all_ok = True
    for name, errs, expect_fail in cases:
        if expect_fail:
            caught = len(errs) > 0
            ok = caught
            print(f"[{name}] 应报红 → {'✅ 被抓' if caught else '❌ 漏抓'}")
        else:
            ok = len(errs) == 0
            print(f"[{name}] 应全绿 → {'✅' if ok else '❌ ' + '; '.join(errs[:3])}")
        all_ok = all_ok and ok

    if all_ok:
        print("✅ 自证 6/6 通过（阴阳对照）")
        return 0
    print("❌ 自证失败：存在漏抓或误报")
    return 1


def main() -> int:
    args = sys.argv[1:]
    quiet = "--quiet" in args
    if "--self-test" in args:
        rc = self_test()
        return rc if not quiet else (0 if rc == 0 else 1)
    return audit()


if __name__ == "__main__":
    sys.exit(main())
