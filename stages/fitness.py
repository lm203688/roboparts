#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stages/fitness.py — 多目标适应度评估（可复用 stage 模块 · Phase B · 90 天 #3）

**背景**（20261013 报告 §6.4）：
    自进化停在半路。本项目有 MDV/cohort 的取证判据，但只衡量**声明**的边际价值。
    本模块把 MDV 推广到**工作流/代码层**，实现多目标适应度评估：

    fitness(变更 c) = Σ_axis Δ可判定对(c, axis) × 溯源可信度(c) − 闸门成本(c)

    - Δ可判定对：已有（compose_semantics + type_compat 可现算）
    - 溯源可信度：已有（Tier A/B/C）
    - 闸门成本：新增（变更带来的新断言数量 × 维护负担）——这是别人没有的保守项

**设计纪律**（§6.4.6 自进化红线）：
    1. **不得用单一标量做长期适应度**——指标污染前科
    2. **不得让自动变更修改 PROJECT_DIRECTIONS_V2.md 的判据**——锚点是宪法
    3. **不得为提升 fitness 而放宽闸门**——自毁壁垒
    4. **一切自动变更须可回滚到前一 hash**

**与 evidence_valuation.py 的关系**：
    evidence_valuation.py 衡量「补哪条声明最值」（MDV 定向）；
    本模块衡量「哪个变更最值」（多目标 fitness）。
    两者共享溯源可信度分层（Tier A/B/C）。

用法（作为 stage）：
    from stages.fitness import fitness, FitnessTarget, evaluate_change
    target = FitnessTarget(
        delta_pairs=15,   # 解锁 15 个可判定对
        provenance_tier="B",  # Tier B 溯源
        new_assertions=3,  # 新增 3 个断言
    )
    score = fitness(target)
    evaluate_change("add_electrical_type_compat", score)

用法（独立 CLI）：
    python -m stages.fitness --evaluate   # 评估当前待办变更的 fitness
    python -m stages.fitness --rank       # 排序候选变更（fitness 降序）
    python -m stages.fitness --self-test  # 自证（变异 + 守恒）
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent

# ── 溯源可信度分层（与 evidence_valuation.py 对齐）─────────────────────
PROVENANCE_WEIGHT: Dict[str, float] = {
    "A": 1.0,   # Tier A: 一手出处（厂商 datasheet / ISO 查表）
    "B": 0.7,   # Tier B: 可复验但非一手（用户提交带出处）
    "C": 0.4,   # Tier C: 无一手出处（上游开源仓 ingestion）
    "D": 0.2,   # Tier D: 无可复验路径（仅声明，不采信）
}

# ── 闸门成本系数（§6.4.4 保守项）─────────────────────────────────────
ASSERTION_COST = 0.5  # 每个新断言的成本（维护负担）
# 理由：断言越多，未来变更的回归面越大；这是「别人没有的保守项」
# 防止系统为了刷分而堆脆弱断言

# ── 目标权重（多目标，不合并成单一标量）───────────────────────────────
OBJECTIVE_WEIGHTS: Dict[str, float] = {
    "decidability": 0.5,   # 可判定对提升（核心目标）
    "provenance": 0.3,     # 溯源可信度（质量目标）
    "cost_efficiency": 0.2,  # 成本效率（维护目标）
}


@dataclass
class FitnessTarget:
    """单个变更的 fitness 目标参数。"""
    name: str
    delta_pairs: int = 0        # 解锁的可判定对数
    delta_axes: List[str] = field(default_factory=list)  # 涉及的轴
    provenance_tier: str = "B"  # 溯源可信度等级
    new_assertions: int = 0     # 新增断言数
    is_reversible: bool = True  # 是否可回滚
    evidence_source: str = ""   # 证据来源描述

    def validate(self) -> List[str]:
        """校验目标参数。返回错误列表。"""
        errors = []
        if not self.name:
            errors.append("name 为空")
        if self.delta_pairs < 0:
            errors.append(f"delta_pairs 不能为负：{self.delta_pairs}")
        if self.provenance_tier not in PROVENANCE_WEIGHT:
            errors.append(f"provenance_tier 非法：{self.provenance_tier}")
        if self.new_assertions < 0:
            errors.append(f"new_assertions 不能为负：{self.new_assertions}")
        return errors


@dataclass
class FitnessResult:
    """单个变更的 fitness 评估结果。"""
    name: str
    objectives: Dict[str, float]  # 多目标得分（不合并）
    composite_score: float        # 加权合并（仅用于排序，不做长期适应度）
    cost: float                   # 闸门成本
    net_gain: float               # 净收益 = composite_score - cost
    is_recommended: bool          # 是否推荐执行
    rank: int = 0                 # 排序位置（1=最高）
    rationale: str = ""           # 推荐/拒绝理由

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def fitness(target: FitnessTarget) -> FitnessResult:
    """计算单个变更的 fitness（多目标）。
    
    返回三个独立目标 + 加权合并分（仅用于排序）。
    红线：长期适应度必须多目标呈现，不得只用 composite_score。
    """
    errors = target.validate()
    if errors:
        return FitnessResult(
            name=target.name,
            objectives={},
            composite_score=0.0,
            cost=0.0,
            net_gain=0.0,
            is_recommended=False,
            rationale=f"参数非法：{'; '.join(errors)}",
        )

    # 目标 1: 可判定性提升
    decidability_score = target.delta_pairs * PROVENANCE_WEIGHT[target.provenance_tier]

    # 目标 2: 溯源质量
    provenance_score = PROVENANCE_WEIGHT[target.provenance_tier]

    # 目标 3: 成本效率（断言越少越好）
    cost = target.new_assertions * ASSERTION_COST
    cost_efficiency_score = max(0.0, 1.0 - cost) if cost > 0 else 1.0

    objectives = {
        "decidability": round(decidability_score, 4),
        "provenance": round(provenance_score, 4),
        "cost_efficiency": round(cost_efficiency_score, 4),
    }

    # 加权合并（仅用于排序）
    composite = sum(objectives[k] * OBJECTIVE_WEIGHTS[k] for k in OBJECTIVE_WEIGHTS)
    net_gain = composite - cost

    # 推荐判据：净收益 > 0 且可回滚
    is_recommended = net_gain > 0 and target.is_reversible

    # 理由生成
    if is_recommended:
        rationale = (
            f"净收益 {net_gain:.2f} > 0，可回滚。"
            f"解锁 {target.delta_pairs} 对，Tier {target.provenance_tier} 溯源，"
            f"新增 {target.new_assertions} 断言。"
        )
    else:
        reasons = []
        if net_gain <= 0:
            reasons.append(f"净收益 {net_gain:.2f} ≤ 0")
        if not target.is_reversible:
            reasons.append("不可回滚（红线：一切自动变更须可回滚）")
        if target.delta_pairs == 0:
            reasons.append("零可判定对提升（T2 定理：单声明零收益）")
        rationale = "拒绝：" + "；".join(reasons)

    return FitnessResult(
        name=target.name,
        objectives=objectives,
        composite_score=round(composite, 4),
        cost=round(cost, 4),
        net_gain=round(net_gain, 4),
        is_recommended=is_recommended,
        rationale=rationale,
    )


def evaluate_change(name: str, target: FitnessTarget) -> FitnessResult:
    """评估单个变更（便捷封装）。"""
    target.name = name
    return fitness(target)


def rank_changes(targets: List[FitnessTarget]) -> List[FitnessResult]:
    """排序候选变更（fitness 降序）。"""
    results = [fitness(t) for t in targets]
    # 按 net_gain 降序，推荐优先
    results.sort(key=lambda r: (r.is_recommended, r.net_gain), reverse=True)
    for i, r in enumerate(results, 1):
        r.rank = i
    return results


def export_ranking(results: List[FitnessResult]) -> Dict[str, Any]:
    """导出排序结果。"""
    return {
        "meta": {
            "version": "fitness/v1",
            "objectives": list(OBJECTIVE_WEIGHTS.keys()),
            "weights": OBJECTIVE_WEIGHTS,
            "assertion_cost": ASSERTION_COST,
            "red_lines": [
                "不得用单一标量做长期适应度",
                "不得让自动变更修改 PROJECT_DIRECTIONS_V2.md 的判据",
                "不得为提升 fitness 而放宽闸门",
                "一切自动变更须可回滚到前一 hash",
            ],
        },
        "total_changes": len(results),
        "recommended": sum(1 for r in results if r.is_recommended),
        "ranking": [r.to_dict() for r in results],
    }


# ── 自证 ──────────────────────────────────────────────────────────────

def self_test() -> Dict[str, Any]:
    """阴阳自证 + 变异测试。"""
    results = []

    # 阳性：有可判定对提升 + 可回滚 → 应推荐
    t1 = FitnessTarget(
        name="add_electrical_type_compat",
        delta_pairs=15,
        provenance_tier="B",
        new_assertions=3,
        is_reversible=True,
    )
    r1 = fitness(t1)
    results.append({
        "test": "positive: 15 pairs, Tier B, 3 assertions",
        "expected": "recommended",
        "actual": "recommended" if r1.is_recommended else "rejected",
        "pass": r1.is_recommended and r1.net_gain > 0,
    })

    # 阴性：零可判定对提升 → 应拒绝（T2 定理）
    t2 = FitnessTarget(
        name="add_single_declare",
        delta_pairs=0,
        provenance_tier="A",
        new_assertions=1,
        is_reversible=True,
    )
    r2 = fitness(t2)
    results.append({
        "test": "negative: 0 pairs (T2 theorem)",
        "expected": "rejected",
        "actual": "rejected" if not r2.is_recommended else "recommended",
        "pass": not r2.is_recommended,
    })

    # 阴性：不可回滚 → 应拒绝（红线）
    t3 = FitnessTarget(
        name="unreversible_change",
        delta_pairs=10,
        provenance_tier="A",
        new_assertions=2,
        is_reversible=False,
    )
    r3 = fitness(t3)
    results.append({
        "test": "negative: irreversible (red line)",
        "expected": "rejected",
        "actual": "rejected" if not r3.is_recommended else "recommended",
        "pass": not r3.is_recommended,
    })

    # 变异：大量断言 → 成本过高 → 净收益 ≤ 0
    t4 = FitnessTarget(
        name="bloat_assertions",
        delta_pairs=10,
        provenance_tier="B",
        new_assertions=20,
        is_reversible=True,
    )
    r4 = fitness(t4)
    results.append({
        "test": "mutation: 20 assertions (cost > gain)",
        "expected": "net_gain <= 0",
        "actual": f"net_gain={r4.net_gain:.2f}",
        "pass": r4.net_gain <= 0,
    })

    # 多目标守恒：三个目标必须独立计算
    t5 = FitnessTarget(name="multi_objective_check", delta_pairs=5, provenance_tier="A", new_assertions=1)
    r5 = fitness(t5)
    results.append({
        "test": "conservation: 3 objectives computed independently",
        "expected": "3 objectives",
        "actual": f"{len(r5.objectives)} objectives",
        "pass": len(r5.objectives) == 3,
    })

    return {
        "total_tests": len(results),
        "passed": sum(1 for r in results if r["pass"]),
        "failed": sum(1 for r in results if not r["pass"]),
        "tests": results,
        "overall": "PASS" if all(r["pass"] for r in results) else "FAIL",
    }


# ── 预设候选变更（Phase B 待办）───────────────────────────────────────

def build_pending_changes() -> List[FitnessTarget]:
    """构建 Phase B 待办变更的 fitness 目标。"""
    return [
        FitnessTarget(
            name="S1: 桥接映射代码化（stages/bridge.py）",
            delta_pairs=0,  # 桥接不直接解锁对，是口径收敛
            provenance_tier="A",  # 权威表在 dual-engine-bridge.md
            new_assertions=2,  # check() + mutation_self_test()
            is_reversible=True,
        ),
        FitnessTarget(
            name="S2: orchestrator DAG 迁移（stages/dag.py）",
            delta_pairs=0,  # DAG 不直接解锁对，是工作流升级
            provenance_tier="A",
            new_assertions=3,  # validate + topological_sort + cycle detection
            is_reversible=True,
        ),
        FitnessTarget(
            name="S3: 多目标 fitness v0（stages/fitness.py）",
            delta_pairs=0,  # fitness 是度量层，不直接解锁对
            provenance_tier="A",
            new_assertions=4,  # fitness + rank + export + self_test
            is_reversible=True,
        ),
        FitnessTarget(
            name="电气取证同质集（16 节点）",
            delta_pairs=15,  # 预计解锁 15 对
            provenance_tier="B",
            new_assertions=8,  # 16 节点 × 0.5 断言/节点
            is_reversible=True,
        ),
        FitnessTarget(
            name="单条机械声明（ACT-028 法兰）",
            delta_pairs=0,  # T2 定理：单声明零收益
            provenance_tier="B",
            new_assertions=1,
            is_reversible=True,
        ),
        FitnessTarget(
            name="全库声明补全（批量 50 条）",
            delta_pairs=15,  # 批量才有边际收益
            provenance_tier="C",
            new_assertions=50,
            is_reversible=True,
        ),
    ]


# ── CLI ──────────────────────────────────────────────────────────────

def _cli() -> int:
    if "--self-test" in sys.argv:
        result = self_test()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["overall"] == "PASS" else 1
    elif "--evaluate" in sys.argv:
        targets = build_pending_changes()
        results = rank_changes(targets)
        print(json.dumps(export_ranking(results), ensure_ascii=False, indent=2))
        return 0
    elif "--rank" in sys.argv:
        targets = build_pending_changes()
        results = rank_changes(targets)
        for r in results:
            status = "✅" if r.is_recommended else "❌"
            print(f"  {status} #{r.rank} {r.name}")
            print(f"     net_gain={r.net_gain:.2f}  cost={r.cost:.2f}  pairs={r.objectives.get('decidability', 0):.1f}")
            print(f"     {r.rationale}")
        return 0
    else:
        print(__doc__)
        return 0


if __name__ == "__main__":
    sys.exit(_cli())
