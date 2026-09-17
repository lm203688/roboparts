#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_neurorobotics.py — 神经控制前沿登记生成器

单一真相源： neurorobotics/source.json
产出：         api/neurorobotics.json

纪律（沿用 RoboParts 派生数据约定）：
- api/neurorobotics.json 由本脚本生成，禁止手改；
- 所有条目来自公开来源，零臆造；逐条带 source_tier / confidence / last_verified；
- signal_contracts 必须经过 neurorobotics/signal_interface.schema.json 的结构校验
  （本脚本内置轻量校验，无外部依赖）。

运行： python scripts/build_neurorobotics.py
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "neurorobotics", "source.json")
SCHEMA = os.path.join(ROOT, "neurorobotics", "signal_interface.schema.json")
OUT = os.path.join(ROOT, "api", "neurorobotics.json")

# ── 轻量 schema 校验（只覆盖本域用到的关键约束，避免引入 jsonschema 依赖） ──
_ENCODINGS = {"rate", "temporal", "event", "membrane-potential"}
_ACT_TYPES = {"discrete", "continuous", "pwm", "spike-train"}
_BODY_KINDS = {"virtual-game", "sim-body", "physical-robot", "hybrid"}
_NEURON_MODELS = {"leaky-integrate-and-fire", "rate-based", "izhikevich",
                  "hodgkin-huxley", "custom"}
_STATUSES = {"spec-example", "validated", "proposed", "deprecated"}
_POLARITY = {"aversive", "appetitive", "neutral"}


def _err(msg):
    print("  ❌", msg)
    sys.exit(1)


def validate_signal_contracts(contracts):
    for c in contracts:
        if not isinstance(c.get("id"), str) or not c["id"].startswith("SIGC-"):
            _err("signal_contract.id 必须以 SIGC- 开头: %r" % c.get("id"))
        if c.get("status") not in _STATUSES:
            _err("%s.status 非法: %r" % (c.get("id"), c.get("status")))
        ctrl = c.get("controller") or {}
        if ctrl.get("neuron_model") not in _NEURON_MODELS:
            _err("%s.controller.neuron_model 非法" % c.get("id"))
        for p in (ctrl.get("output_populations") or []) + (ctrl.get("input_populations") or []):
            if p.get("encoding") not in _ENCODINGS:
                _err("%s 群体 encoding 非法: %r" % (c.get("id"), p.get("encoding")))
        body = c.get("body") or {}
        if body.get("kind") not in _BODY_KINDS:
            _err("%s.body.kind 非法" % c.get("id"))
        for a in body.get("actuators") or []:
            if a.get("type") not in _ACT_TYPES:
                _err("%s 执行器 type 非法: %r" % (c.get("id"), a.get("type")))
        mp = c.get("mappings") or {}
        for m in mp.get("output") or []:
            if not (m.get("controller_population") and m.get("body_actuator") and m.get("rule")):
                _err("%s mappings.output 缺必需字段" % c.get("id"))
        for m in mp.get("input") or []:
            if not (m.get("body_sensor") and m.get("controller_population") and m.get("rule")):
                _err("%s mappings.input 缺必需字段" % c.get("id"))
        for m in mp.get("reward") or []:
            if m.get("polarity") not in _POLARITY:
                _err("%s mappings.reward.polarity 非法" % c.get("id"))


def validate_reference_robots(robots):
    """校验 reference_robots 条目——GAP-G1 参考实现必须诚实标注独立性铁律。"""
    for r in robots:
        rid = r.get("id")
        if not (isinstance(rid, str) and rid.startswith("ROBOT-")):
            _err("reference_robots[].id 必须以 ROBOT- 开头: %r" % rid)
        indep = r.get("independence") or {}
        for k in ("no_weights_downloaded", "no_source_shared", "no_reverse_dependency"):
            if indep.get(k) is not True:
                _err("%s.independence.%s 必须为 true（独立铁律）" % (rid, k))
        if not r.get("source"):
            _err("%s.source 必填（诚实出处）" % rid)
        if not r.get("last_verified"):
            _err("%s.last_verified 必填" % rid)
        for wm in (r.get("world_models") or []):
            if not wm.get("license"):
                _err("%s world_models[] license 必填" % rid)


def main():
    if not os.path.exists(SRC):
        _err("找不到单一真相源: %s" % SRC)
    src = json.load(open(SRC, encoding="utf-8"))
    meta = src["meta"]

    # 结构校验
    validate_signal_contracts(src.get("signal_contracts") or [])
    validate_reference_robots(src.get("reference_robots") or [])

    # 计数
    counts = {
        "connectomes": len(src.get("connectomes") or []),
        "neuromorphic_chips": len(src.get("neuromorphic_chips") or []),
        "labs": len(src.get("labs") or []),
        "reference_robots": len(src.get("reference_robots") or []),
        "research_gaps": len(src.get("research_gaps") or []),
        "signal_contracts": len(src.get("signal_contracts") or []),
        "references": len(src.get("references") or []),
    }
    gap_sev = {}
    for g in src.get("research_gaps") or []:
        gap_sev[g.get("severity", "unknown")] = gap_sev.get(g.get("severity", "unknown"), 0) + 1

    out = {
        "meta": {
            **meta,
            "generated_at": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "counts": counts,
            "gap_severity": gap_sev,
        },
        "connectomes": src["connectomes"],
        "neuromorphic_chips": src["neuromorphic_chips"],
        "labs": src["labs"],
        "reference_robots": src.get("reference_robots") or [],
        "research_gaps": src["research_gaps"],
        "signal_contracts": src["signal_contracts"],
        "references": src["references"],
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("  ✅ 已生成 api/neurorobotics.json")
    print("     连接组 %d · 神经形态芯片 %d · 实验室 %d · 参考机器人 %d · 研究空白 %d (高优先级 %d) · 信号契约 %d · 引用 %d"
          % (counts["connectomes"], counts["neuromorphic_chips"], counts["labs"],
             counts["reference_robots"],
             counts["research_gaps"], gap_sev.get("high", 0),
             counts["signal_contracts"], counts["references"]))


if __name__ == "__main__":
    main()
