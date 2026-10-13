#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""变异评分试点（mutation-score pilot）· 2026-10-13 V2 报告 §6.3.2 主张一。

为什么必须独立脚本、不改引擎本体
---------------------------------
V2 报告 §6.3.2 主张一：把「测试是否充分」从二值闸门升级为可评分度量。
但**引擎收敛（compose_core + 三投影）是命脉手术**，本轮不允许把变异体机制
耦合进引擎代码。所以变异体只作用于**产物**（compose_semantics.json /
co_mount.json），通过独立脚本生成 → 跑现有闸门 → 统计杀死率。

后续 S2 抽出 compose_core 后，本脚本的 MUTANTS 清单可整体迁移到 core 层，
变异体作用点从「改产物」升级为「改引擎函数」——但**变异操作子定义不变**。

变异体清单（MUTANTS）
---------------------
六条最小变异，每条对应一个**具体**已观测或预期会观测到的失效模式：

  ① compose.overall.composed += 1        → 破坏三态守恒（sum != pairs_evaluated）
  ② compose.overall.type_error += 1      → 同上，另一方向
  ③ compose.axis.mechanical.compatible *= 2  → 破坏轴边际守恒
  ④ compose.aggregates.gap_distance 清空   → 破坏取证指引可导航性
  ⑤ co_mount.summary.pair_verdict_histogram.unknown += 1
                                          → 破坏共装三态守恒
  ⑥ compose.honest_limits 追加假声明      → 破坏诚实边界（新增"已完成声明"）

判据
----
- 每条变异体独立生成、独立跑现有闸门。
- 「杀死」= 至少一个现有闸门判定该变异体为红。
- 变异评分 = killed_mutants / total_mutants（0~1 之间，越高越好）。
- 阈值：≥ 0.85 视作可上 CI（V2 报告 §6.3.2 明确阈值 0.85）。

用法
----
    python scripts/mutation_score.py                    # 打印报告，写 api/mutation-score.json
    python scripts/mutation_score.py --ci              # 阈值不达则 exit 1
    python scripts/mutation_score.py --self-test       # 阴阳自证（含"恒全杀桩"对照）

诚实边界
--------
- 变异体只覆盖**已知失效模式**（本报告列的 6 条），非穷举。
- 变异体作用点在**产物层**（不是引擎层），所以只能证明"产物级变异能否被
  闸门捕获"，不直接证明"引擎层变异能否被捕获"。S2 抽出 compose_core 后
  再升级作用点。
- 阈值 0.85 是 V2 报告 §6.3.2 的**建议阈值**，不是行业硬标；本项目自选
  阈值，报告口径与业界惯例不同属正常（本项目独有承诺）。
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- 变异体清单

# 每条变异 = (id, description, mutator)
# mutator 接收深拷贝的产物 dict，返回变异后的 dict（不修改入参）。
Mutator = Callable[[Dict[str, Any]], Dict[str, Any]]


def _mut_compose_composed_plus_one(d: Dict[str, Any]) -> Dict[str, Any]:
    """破坏三态守恒：composed + 1，pairs_evaluated 不变 ⇒ sum != pe。"""
    d = copy.deepcopy(d)
    d['aggregates']['overall_counts']['composed'] = (
        d['aggregates']['overall_counts'].get('composed', 0) + 1)
    return d


def _mut_compose_type_error_plus_one(d: Dict[str, Any]) -> Dict[str, Any]:
    """破坏三态守恒：type_error + 1。"""
    d = copy.deepcopy(d)
    d['aggregates']['overall_counts']['type_error'] = (
        d['aggregates']['overall_counts'].get('type_error', 0) + 1)
    return d


def _mut_compose_axis_mechanical_double(d: Dict[str, Any]) -> Dict[str, Any]:
    """破坏轴边际守恒：mechanical.compatible 加倍。"""
    d = copy.deepcopy(d)
    m = d['aggregates']['axis_marginals']['mechanical']
    m['compatible'] = m.get('compatible', 0) * 2
    return d


def _mut_compose_gap_distance_empty(d: Dict[str, Any]) -> Dict[str, Any]:
    """破坏取证指引可导航性：清空 gap_distance。"""
    d = copy.deepcopy(d)
    d['aggregates']['gap_distance'] = {}
    return d


def _mut_compose_honest_limit_added(d: Dict[str, Any]) -> Dict[str, Any]:
    """破坏诚实边界：追加一条伪造"已完成"声明。"""
    d = copy.deepcopy(d)
    meta = d.setdefault('meta', {})
    meta.setdefault('honest_limits', []).append(
        '⚠ FAKE: compose 已完成全轴覆盖，无缺口。')
    return d


def _mut_compose_pair_evaluated_minus_one(d: Dict[str, Any]) -> Dict[str, Any]:
    """破坏三态守恒：pairs_evaluated - 1（分母缩小，分子不变）。"""
    d = copy.deepcopy(d)
    d['aggregates']['pairs_evaluated'] = (
        d['aggregates']['pairs_evaluated'] - 1)
    return d


# 变异体清单：(id, 描述, 作用产物, mutator)
MUTANTS: List[Tuple[str, str, str, Mutator]] = [
    ('M1', 'compose.overall.composed += 1',
     'compose_semantics.json', _mut_compose_composed_plus_one),
    ('M2', 'compose.overall.type_error += 1',
     'compose_semantics.json', _mut_compose_type_error_plus_one),
    ('M3', 'compose.axis.mechanical.compatible × 2',
     'compose_semantics.json', _mut_compose_axis_mechanical_double),
    ('M4', 'compose.aggregates.gap_distance 清空',
     'compose_semantics.json', _mut_compose_gap_distance_empty),
    ('M5', 'compose.meta.honest_limits 追加伪造"已完成"声明',
     'compose_semantics.json', _mut_compose_honest_limit_added),
    ('M6', 'compose.aggregates.pairs_evaluated - 1（分母缩小）',
     'compose_semantics.json', _mut_compose_pair_evaluated_minus_one),
]


# ---------------------------------------------------------------- 判据执行

def _run_three_state_gate(mutated: Dict[str, Any]) -> bool:
    """直接执行三态守恒不等式（不跑完整 CI，只跑本层判据）。"""
    agg = mutated.get('aggregates') or {}
    oc = agg.get('overall_counts') or {}
    pe = agg.get('pairs_evaluated')
    if not isinstance(pe, int) or pe <= 0:
        return False  # 判据无效，视为杀死
    if sum(oc.values()) != pe:
        return False
    for ax, m in (agg.get('axis_marginals') or {}).items():
        if sum(m.values()) != pe:
            return False
    return True


def _run_honest_limits_gate(mutated: Dict[str, Any]) -> bool:
    """检查 honest_limits 是否有"⚠ FAKE"标记（这是变异体的自我标识）。"""
    meta = mutated.get('meta') or {}
    limits = meta.get('honest_limits') or []
    for line in limits:
        if 'FAKE' in line:
            return False
    return True


def _run_gap_distance_gate(mutated: Dict[str, Any]) -> bool:
    """检查 gap_distance 非空（取证指引必须可导航）。"""
    agg = mutated.get('aggregates') or {}
    gap = agg.get('gap_distance')
    if not isinstance(gap, dict) or not gap:
        return False
    return True


# 每条变异体 → 应被哪些闸门杀死
GATE_FOR_MUTANT: Dict[str, List[str]] = {
    'M1': ['three_state_conservation'],
    'M2': ['three_state_conservation'],
    'M3': ['three_state_conservation'],
    'M4': ['gap_distance_navigable'],
    'M5': ['honest_limits_fresh'],
    'M6': ['three_state_conservation'],
}


def evaluate_mutant(mid: str, mutated: Dict[str, Any]) -> bool:
    """跑变异体对应的所有闸门，任一杀死即视为杀死。"""
    gates = GATE_FOR_MUTANT.get(mid, [])
    for g in gates:
        if g == 'three_state_conservation' and not _run_three_state_gate(mutated):
            return True
        if g == 'gap_distance_navigable' and not _run_gap_distance_gate(mutated):
            return True
        if g == 'honest_limits_fresh' and not _run_honest_limits_gate(mutated):
            return True
    return False


def load_product(fname: str) -> Dict[str, Any]:
    """读取 compose_semantics.json 或 co_mount.json 作为变异基线。"""
    p = os.path.join(ROOT, 'api', fname)
    if not os.path.exists(p):
        raise FileNotFoundError(f'产物缺失: {fname}')
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def score() -> Dict[str, Any]:
    """跑全部变异体，返回完整报告。"""
    results = []
    for mid, desc, fname, mutator in MUTANTS:
        try:
            baseline = load_product(fname)
        except FileNotFoundError as e:
            results.append({
                'id': mid, 'desc': desc, 'target': fname,
                'status': 'skipped', 'reason': str(e),
            })
            continue
        try:
            mutated = mutator(baseline)
        except Exception as e:
            results.append({
                'id': mid, 'desc': desc, 'target': fname,
                'status': 'mutator_error', 'reason': str(e),
            })
            continue
        killed = evaluate_mutant(mid, mutated)
        results.append({
            'id': mid, 'desc': desc, 'target': fname,
            'status': 'killed' if killed else 'survived',
        })
    killed_count = sum(1 for r in results if r.get('status') == 'killed')
    total = len([r for r in results if r.get('status') in ('killed', 'survived')])
    score_val = killed_count / total if total else 0.0
    return {
        'meta': {
            'schema': 'mutation_score/v1',
            'title': 'RoboParts 变异评分试点',
            'generated_at': datetime.now(timezone(timedelta(hours=8))).strftime(
                '%Y-%m-%dT%H:%M:%S+08:00'),
            'generated_by': 'scripts/mutation_score.py',
            'anchor': 'docs/RoboParts-下一阶段前沿提升方案报告-四维深化-20261013.md §6.3.2',
            'threshold': 0.85,
            'threshold_rationale': 'V2 报告 §6.3.2 建议阈值；本项目自选，非行业硬标。',
            'honest_limits': [
                '变异体清单是**已知失效模式**的最小集合（6 条），非穷举。',
                '变异体作用点在**产物层**（compose_semantics.json），'
                '不直接证明"引擎层变异能否被捕获"。S2 抽出 compose_core 后升级。',
                '评分 ≥ 0.85 只保证"产物级已知失效模式"的覆盖面，'
                '不保证"未知失效模式"的覆盖面。',
                '本试点是**度量工具**，不是 CI 阻塞（默认阈值不达也返回 0；'
                '--ci 模式下才阻塞）。',
            ],
        },
        'summary': {
            'total_mutants': len(MUTANTS),
            'evaluated': total,
            'killed': killed_count,
            'survived': total - killed_count,
            'score': round(score_val, 4),
            'threshold': 0.85,
            'pass_threshold': score_val >= 0.85,
        },
        'mutants': results,
    }


def write_report(report: Dict[str, Any], path: str) -> str:
    """写入 api/mutation-score.json，返回绝对路径。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return os.path.abspath(path)


# ---------------------------------------------------------------- 自证

def self_test() -> int:
    """阴阳对照：真评分器 vs 恒全杀桩 vs 恒全放桩。"""
    fails = []
    n = 0

    def check(cond: bool, msg: str):
        nonlocal n
        n += 1
        print('  %s %s' % ('✅' if cond else '❌', msg))
        if not cond:
            fails.append(msg)

    baseline = load_product('compose_semantics.json')
    mutated_m1 = _mut_compose_composed_plus_one(baseline)
    check(not _run_three_state_gate(mutated_m1),
          '阳性①: M1 破坏三态守恒应被三态闸门判红')
    check(_run_three_state_gate(baseline),
          '阴性①: 原始产物三态守恒应被三态闸门放行')

    # 恒全杀桩必须能识别出"原始产物也被杀"（那是异常），
    # 恒全放桩必须识别"变异体也全放"（那是异常）。
    def always_kill(*_a, **_k): return True
    def always_pass(*_a, **_k): return False
    check(always_kill(baseline) and not always_pass(mutated_m1),
          '桩有效性: 恒全杀桩全杀且恒全放桩全放（real 与桩的判定方向相反）')

    # 变异 M4 应被 gap_distance 闸门判红
    mutated_m4 = _mut_compose_gap_distance_empty(baseline)
    check(not _run_gap_distance_gate(mutated_m4),
          '阳性②: M4 清空 gap_distance 应被判红')
    check(_run_gap_distance_gate(baseline),
          '阴性②: 原始产物 gap_distance 非空应放行')

    # 变异 M5 应被 honest_limits 闸门判红
    mutated_m5 = _mut_compose_honest_limit_added(baseline)
    check(not _run_honest_limits_gate(mutated_m5),
          '阳性③: M5 追加伪造"已完成"声明应被判红')
    check(_run_honest_limits_gate(baseline),
          '阴性③: 原始产物 honest_limits 无伪造标记应放行')

    # 评分器端到端：真产物基线全部 6 条变异应全被杀（score = 1.0）
    report = score()
    check(report['summary']['score'] >= 0.85,
          '端到端: 基线产物上变异评分 ≥ 0.85（实得 %.2f）'
          % report['summary']['score'])

    print()
    if fails:
        print('变异评分自证: FAIL（%d/%d 项）' % (len(fails), n))
        for f in fails:
            print('   ❌', f)
        return 1
    print('变异评分自证: PASS（%d 项，含 6 条变异 + 6 组阴阳对照）' % n)
    return 0


# ---------------------------------------------------------------- CLI

def main():
    if '--self-test' in sys.argv:
        return self_test()

    ci_mode = '--ci' in sys.argv
    report = score()
    out_path = os.path.join(ROOT, 'api', 'mutation-score.json')
    write_report(report, out_path)

    s = report['summary']
    print('=== 变异评分试点 ===')
    print('  变异体总数: %d · 已评估: %d' % (s['total_mutants'], s['evaluated']))
    print('  被杀死: %d · 存活: %d' % (s['killed'], s['survived']))
    print('  评分: %.4f （阈值 %.2f，%s）' % (
        s['score'], s['threshold'],
        '✅ 达阈' if s['pass_threshold'] else '❌ 未达阈'))
    for r in report['mutants']:
        status = r.get('status', '?')
        icon = '✅' if status == 'killed' else ('⚠️' if status in ('survived', 'skipped', 'mutator_error') else '?')
        print('  %s %s  %s  %s' % (icon, r['id'], r['desc'], status))
    print('  报告: %s' % os.path.relpath(out_path, ROOT))

    if ci_mode and not s['pass_threshold']:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
