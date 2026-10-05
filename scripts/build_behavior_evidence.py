#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_behavior_evidence — 行为层证据（policy→behavior 链的缺失段）。

    → api/behavior_evidence.json

── 背景：provenance 的 4 个连接条件里，L4（policy→behavior）恒为 false ──
判据原文：「存在行为/运行日志数据」，实测 `blocked_by = 本仓无任何运行日志文件`。

**本项目自己造不出来**：锚点 §3 硬性负向边界明列
    ❌ 造仿真器 / 训练栈 | 对接 Isaac/MuJoCo/LeRobot，不另起炉灶
自己跑 rollout = 造仿真器 + 训练栈 = 直接违反锚点。

**但「行为证据」不等于「自己产生的日志」。** 论文与官方报告的
benchmark 成功率是**真实存在、公开可溯源**的行为度量：
  · GR00T N1.5 真机 GR-1 语言跟随 **93.3%**（NVIDIA GEAR 研究页）
  · 对照 GR00T N1 同任务 **46.6%** ⇒ 该数字有对照，不是孤证
这类记录满足链判据要回答的问题——「这个策略在真机上表现如何」，
且出处是一手页面而非本仓自造。

── 三条纪律 ──────────────────────────────────────────────────────
1. **只收录有对照的数字**。孤证的单点数字不登记——
   单点可能是 cherry-pick。对照组存在才说明该数字有意义。
2. **区分 sim / real**。仿真成绩不能当真机行为证据。
   `trial_kind` 字段强制登记，实机为 `real`。
3. **不推算缺失指标**。模型没报的指标不填，
   `null` 表示「官方未报告」——与 unknown 同源纪律。
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: 行为证据表。**每条必须有 sim/real 标注 + 对照组 + 一手出处**。
BEHAVIOR = {
    "LLM-028": {
        "model": "NVIDIA Isaac GR00T N1.5",
        "records": [
            {
                "metric": "language_following_rate",
                "trial_kind": "real",          # ★ 真机，非仿真
                "embodiment": "Fourier GR-1",   # 库内实体 XPLT-007
                "embodiment_ref": "XPLT-007",
                "task": "two fruits on a table, place the named one onto a plate"
                        "（目标水果以 50% 概率采样至左手或右手）",
                "value": 0.933,
                "unit": "success_rate",
                "n_trials": None,               # 官方未报告样本量
                "control_value": 0.466,         # GR00T N1 同任务 46.6%
                "control_model": "GR00T N1",
                "has_control": True,            # ★ 有对照组 ⇒ 不是孤证
                "source_url": "https://research.nvidia.com/labs/gear/gr00t-n1_5/",
                "source_scope": "first_party",
                "note": "NVIDIA GEAR 研究页『Real GR-1 language following』段："
                        "GR00T N1.5 达 93.3%，GR00T N1 为 46.6%。"
                        "同页另列 0-shot 15% 拾放新物体成功率（N1 为 0%）作为第二组对照。",
            },
            {
                "metric": "novel_object_pick_place_rate",
                "trial_kind": "real",
                "embodiment": "Fourier GR-1",
                "embodiment_ref": "XPLT-007",
                "task": "拾放训练中未见过的新物体（无演示）",
                "value": 0.15,
                "unit": "success_rate",
                "n_trials": None,
                "control_value": 0.0,
                "control_model": "GR00T N1",
                "has_control": True,
                "source_url": "https://research.nvidia.com/labs/gear/gr00t-n1_5/",
                "source_scope": "first_party",
                "note": "同页『15% success rate in picking and placing novel objects "
                        "without any prior demonstrations, whereas GR00T N1 scored 0%』。"
                        "**这是弱对照组（0%），故该记录只作补充，不作主证据。**",
            },
            {
                "metric": "robocasa_30_demo_success",
                "trial_kind": "sim",            # ★ 仿真，单列不与实机混用
                "embodiment": "sim_robocasa",
                "embodiment_ref": None,
                "task": "RoboCasa，30 demos/task",
                "value": 0.475,
                "unit": "success_rate",
                "n_trials": None,
                "control_value": 0.174,
                "control_model": "GR00T N1",
                "has_control": True,
                "source_url": "https://research.nvidia.com/labs/gear/gr00t-n1_5/",
                "source_scope": "first_party",
                "note": "仿真基准。**单独标注 sim=true**，"
                        "不得与真机数字混算或互相替代。",
            },
        ],
    },
    "LLM-029": {
        "model": "SmolVLA",
        "records": [
            {
                "metric": "real_world_pick_place",
                "trial_kind": "real",
                "embodiment": "SO-100/SO-101",
                "embodiment_ref": None,        # ★ 本体不在库内 ⇒ 不可引用
                "task": "拾放立方体计数（含异步推理变体）",
                "value": None,                  # ★ 官方以图示为主，未给单一数值
                "unit": "success_rate",
                "n_trials": None,
                "control_value": None,
                "control_model": "ACT",
                "has_control": True,
                "source_url": "https://huggingface.co/blog/smolvla",
                "source_scope": "first_party",
                "note": "**刻意 value=null**：HF 官方博客以图示与定性描述为主"
                        "（『outperforms ... ACT on real-world tasks (SO100, SO101)』），"
                        "未给出可引用的单一成功率。"
                        "**把定性描述折算成数字是编造** ⇒ 留 null。"
                        "本条只证明「真机评测发生过」，不提供数值。",
            },
        ],
    },
}

#: 明确不做的事（如实登记，避免被当成遗漏）
NOT_MODELLED = [
    "**不自建 rollout 日志**。锚点 §3：❌ 造仿真器/训练栈"
    "（对接 Isaac/MuJoCo/LeRobot，不另起炉灶）⇒ 自己跑仿真 = 违反锚点。",
    "**不收录无对照的孤证数字**。单点成功率可能是 cherry-pick，"
    "登记它等于给读者一个不可靠的横向比较依据。",
    "**不推算官方未报告的指标**。value=null 表示「官方未报告」，"
    "与 unknown 同源——缺数据必须显式可见。",
    "**仿真（sim）与真机（real）严格分列**，不合并统计。"
    "仿真成绩不能当真机行为证据。",
]


def _load(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _validate(ents):
    """fail-fast：embodiment_ref 指向的实体必须真实存在。"""
    errs = []
    for mid, rec in BEHAVIOR.items():
        for r in rec["records"]:
            ref = r.get("embodiment_ref")
            if ref and ref not in ents:
                errs.append("%s 的 embodiment_ref=%s 不在 entities.json"
                            " —— 行为证据引用不存在的实体是凭空断言" % (mid, ref))
            if r.get("trial_kind") not in ("real", "sim"):
                errs.append("%s 的 trial_kind=%r 非法（只允许 real/sim）"
                            % (mid, r.get("trial_kind")))
            if not r.get("source_url"):
                errs.append("%s 的记录缺 source_url" % mid)
            # ★ 有数值的记录必须有对照组（纪律 1）
            if r.get("value") is not None and not r.get("has_control"):
                errs.append("%s 的 %s 有数值但无对照组 —— "
                            "孤证数字不登记（可能是 cherry-pick）"
                            % (mid, r.get("metric")))
    if errs:
        raise SystemExit("build_behavior_evidence 校验失败:\n  - "
                         + "\n  - ".join(errs))


def main() -> int:
    ents = {e["id"] for e in ((_load("api/entities.json") or {}).get("entities") or [])}
    _validate(ents)
    rm = _load("api/robot_ai_models.json") or {}
    models = {m["id"]: m for m in (rm.get("models") or rm.get("data") or [])}

    total = real = sim = nulled = 0
    per_model = {}
    for mid, rec in BEHAVIOR.items():
        m = models.get(mid)
        if not m:
            print("  跳过 %s（不在 robot_ai_models）" % mid)
            continue
        rv = [r for r in rec["records"] if r["trial_kind"] == "real"
              and r.get("value") is not None]
        rnull = [r for r in rec["records"] if r.get("value") is None]
        sm = [r for r in rec["records"] if r["trial_kind"] == "sim"]
        total += len(rec["records"])
        real += len(rv)
        sim += len(sm)
        nulled += len(rnull)
        per_model[mid] = {
            "model": rec["model"],
            "records": len(rec["records"]),
            "real_with_value": len(rv),
            "sim": len(sm),
            "null_value": len(rnull),
            "real_success_rates": [
                {"metric": r["metric"], "value": r["value"],
                 "embodiment": r["embodiment"],
                 "control_model": r.get("control_model"),
                 "control_value": r.get("control_value")}
                for r in rv],
        }
        # 回写行为证据指针到模型条目（便于下游溯源，不复制数据）
        m["behavior_evidence"] = {
            "records": len(rec["records"]),
            "real_with_value": len(rv),
            "source": "api/behavior_evidence.json",
        }

    p = os.path.join(ROOT, "api", "robot_ai_models.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(rm, f, ensure_ascii=False, indent=1)
        f.write("\n")

    out = {
        "meta": {
            "title": "行为证据层（policy→behavior 链）",
            "caliber": "论文/官方报告的 benchmark 行为度量，**非本仓自造日志**。"
                       "sim 与 real 严格分列；value=null 表示官方未报告。",
            "why_not_own_logs": (
                "锚点 §3 硬性负向边界：❌ 造仿真器 / 训练栈"
                "（对接 Isaac/MuJoCo/LeRobot，不另起炉灶）"
                "⇒ 本项目自己跑 rollout 就是造仿真器，**直接违反锚点**。"),
            "why_these_count": (
                "「行为证据」不等于「自己产生的日志」。"
                "官方报告的真机 benchmark 成功率是**真实、公开、可溯源**的行为度量，"
                "且 GR00T N1.5 的数字带**同任务对照组**（93.3% vs N1 46.6%）"
                "⇒ 不是孤证。这恰好回答链判据要问的问题："
                "「这个策略在真机上表现如何」。"),
        },
        "summary": {
            "models": len(per_model),
            "records": total,
            "real_with_value": real,
            "sim_records": sim,
            "null_value_records": nulled,
        },
        "per_model": per_model,
        "records": {mid: rec["records"] for mid, rec in BEHAVIOR.items()},
        "not_modelled": NOT_MODELLED,
        "honest_limits": [
            "**样本量官方均未报告**（n_trials=null）⇒ 成功率无法算置信区间，"
            "不可用于统计比较，只可作定性参照。",
            "**只覆盖 2 个开源 VLA**。46 个模型中闭源模型"
            "（RT-2 / π0 等）无公开真机数字 ⇒ 不登记，"
            "**不给闭源模型编造行为数据**。",
            "**仿真记录仅作参考**，不得替代真机证据，"
            "也不得与真机数字合并统计。",
            "**行为证据不等于本仓可复现**。我们引用官方数字，"
            "不声称能自己重跑——重跑需 Isaac/MuJoCo/LeRobot 栈（锚点不做）。",
        ],
    }
    op = os.path.join(ROOT, "api", "behavior_evidence.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")

    s = out["summary"]
    print("build_behavior_evidence: 模型 %d｜记录 %d"
          % (s["models"], s["records"]))
    print("  真机有数值 %d｜仿真 %d｜刻意留 null %d"
          % (s["real_with_value"], s["sim_records"], s["null_value_records"]))
    for mid, v in per_model.items():
        print("  %s (%s): 真机有值 %d，null %d"
              % (mid, v["model"], v["real_with_value"], v["null_value"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
