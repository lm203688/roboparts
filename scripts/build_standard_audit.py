#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2 标准自校验 —— 标准登记表 ↔ 实体声明 自动比对
================================================

把「标准登记表」（mechanical_interfaces.json 机械接口规范 + hb 行标备案库台账）
与「实体库」（api/entities.json）的声明做交叉核对，自动标出**数据质量冲突**：

  1. 机械接口声明核查：实体 mechanical_interface.standard 引用的编码，
     是否落在 mechanical_interfaces.json 的已知指定（designations_in_use /
     flange_designations）里。落不在 → `unverified_mechanical_claim`
     （诚实：我们无法核实这个编码确实存在，可能是笔误或真实但未登记的规范）。
  2. 总线/协议标准核查：实体 protocol/interface 声明的总线，是否属公认互操作标准。
     不属 → `unrecognized_bus_claim`。
  3. 登记表缺口：designations_in_use 里 `registry_row=null` 的项
     （"实体在引用、但本表未登记规范行"）→ `registry_gap`。
  4. 行标覆盖：hb 台账作用域内 4 条 JB/T 标准的存在性与证据等级，
     以及当前有多少实体落在其作用域（机器人∩接口）内——只报告，不臆造"已符合"。

诚实边界（与全站纪律同源）：
  - 本审计**不裁决兼容性**，只校验"声明是否可核实"。
  - "声称符合某标但无可核实出处"是数据质量冲突，不是"不兼容"；
    绝不用它去扣分或伪造兼容结论。
  - 当前机械接口声明仅 2 条（ACT-028 / SENS-31，均 ISO 9409-1），
    故机械核查样本很小——这正是 P0 飞轮要解决的稀缺问题；
    本审计随飞轮引入更多带机械声明的 BOM 而自动变厚。

用法：python scripts/build_standard_audit.py
输出：api/standard_audit.json
"""
from __future__ import annotations
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return json.load(f)


def norm_mech(s: str) -> str:
    """与 mechanical_interfaces.json 的 join_rule 完全一致：去空格、大写、去 A 前缀。"""
    s = str(s).upper().replace(' ', '')
    s = re.sub(r'ISO9409-1-A', 'ISO9409-1-', s)
    return s


# 公认互操作总线/协议标准（大写，做子串/等值匹配）
BUS_STD = {
    'ETHERCAT', 'CANOPEN', 'CAN', 'MODBUS', 'RS485', 'RS232', 'UART', 'SPI', 'I2C',
    'PROFINET', 'POWERLINK', 'SERCOS', 'USB', 'TCP', 'TCP/IP', 'MQTT', 'ROS2', 'ROS',
    'BLE', 'BLUETOOTH', 'WIFI', 'ETHERNET', 'LIN', 'FLEXRAY', 'GMSL', 'MIPI', 'I2S',
}


def main():
    entities = load('api/entities.json')['entities']
    mi = load('api/mechanical_interfaces.json')
    hb = load('ops/intel/hb-standards-ledger.json')

    # ── 已知机械指定集 ───────────────────────────────────────────────
    known = set()
    for f in mi.get('flange_designations', []):
        if isinstance(f, dict) and f.get('id'):
            known.add(norm_mech(f['id']))
    du = mi.get('designations_in_use', {})
    if isinstance(du, dict):
        for k, v in du.items():
            if k in ('description', 'computed_from', 'join_rule'):
                continue
            des = k
            if isinstance(v, dict):
                des = v.get('designation') or v.get('id') or k
            known.add(norm_mech(str(des)))

    # ── 登记表缺口：在用但未登记规范行 ──────────────────────────────
    registry_gaps = []
    if isinstance(du, dict):
        for k, v in du.items():
            if k in ('description', 'computed_from', 'join_rule'):
                continue
            if isinstance(v, dict) and v.get('registry_row') is None:
                registry_gaps.append({
                    'designation': norm_mech(k),
                    'note': '实体库在引用该编码，但 mechanical_interfaces.json 无对应规范行（registry_row=null）',
                })

    # 非标准/信号级接口归类（这些不是"错误"，只是不属于公认数字总线标准，
    # 故只作信息统计，不计入冲突——避免把 proprietary/analog/PWM 误判成数据质量问题）。
    PROPRIETARY_OR_GENERIC = {
        'PROPRIETARY', 'CUSTOM', 'BUS', 'PROTOCOL', 'CONTROL', 'CONTROLLER',
        'DRIVE', 'AI', 'HELIX', 'ESCON', 'AKD', 'VESC', 'TESLA', 'GENERIC', 'OTHER',
    }
    SIGNAL_LEVEL = {
        'PWM', 'TTL', 'ANALOG', 'ANALOGUE', 'DIGITAL', 'STEP', 'STEP/DIR', 'STEPDIR',
        'PULSE', 'RC', 'PPM', 'CV', '0-10V', '4-20MA',
    }

    # ── 逐实体声明核查 ──────────────────────────────────────────────
    mech_verified, mech_unverified = [], []
    bus_recognized = []
    bus_other = {'proprietary_or_generic': [], 'signal_level': [], 'unknown_token': []}
    for e in entities:
        eid = e.get('id')
        mi_e = e.get('mechanical_interface')
        if isinstance(mi_e, dict):
            std = mi_e.get('standard')
            stds = std if isinstance(std, list) else ([std] if isinstance(std, str) else [])
            for s in stds:
                if not s or s in ('n_a', 'not_declared', ''):
                    continue
                ns = norm_mech(s)
                rec = {'id': eid, 'name': e.get('name'), 'declared': s}
                if ns in known:
                    mech_verified.append(rec)
                else:
                    rec['note'] = '声明的机械编码不在已知指定集中，无法核实（可能为本表未登记的真实规范）'
                    mech_unverified.append(rec)

        for field in ('protocol', 'interface'):
            val = e.get(field)
            if not val:
                continue
            toks = re.split(r'[,;/、|+\s]+', str(val))
            for t in toks:
                t = t.strip().upper()
                if not t:
                    continue
                rec = {'id': eid, 'name': e.get('name'), 'field': field, 'declared': t}
                if any(b in t for b in BUS_STD):
                    bus_recognized.append(rec)
                elif t in PROPRIETARY_OR_GENERIC:
                    bus_other['proprietary_or_generic'].append(rec)
                elif t in SIGNAL_LEVEL:
                    bus_other['signal_level'].append(rec)
                else:
                    bus_other['unknown_token'].append(rec)

    # ── 行标覆盖（hb 台账作用域内）─────────────────────────────────
    hb_coverage = []
    for code, info in (hb.get('in_scope_latest') or {}).items():
        hb_coverage.append({
            'code': code,
            'name': info.get('name'),
            'status': info.get('status'),
            'evidence': info.get('evidence'),
            'evidence_tier': info.get('evidence_tier'),
            'note': '作用域（机器人∩接口）已确认；实体级"是否符合"需其声明该标准，'
                    '当前库无此链接字段，故仅报告标准存在性与证据等级，不臆造符合判定。',
        })

    conflicts = []
    conflicts += [{'type': 'unverified_mechanical_claim', **r} for r in mech_unverified]
    conflicts += [{'type': 'registry_gap', **r} for r in registry_gaps]

    out = {
        'generated_at': __import__('datetime').datetime.now().isoformat(),
        'purpose': '标准登记表 ↔ 实体声明 自动交叉校验（数据质量自检，非兼容性裁决）',
        'registry': {
            'known_mechanical_designations': len(known),
            'recognized_bus_standards': sorted(BUS_STD),
            'hb_in_scope_count': len(hb_coverage),
        },
        'mechanical_claims': {
            'total_declared': len(mech_verified) + len(mech_unverified),
            'verified': mech_verified,
            'unverified': mech_unverified,
        },
        'bus_claims': {
            'total_declared': len(bus_recognized)
            + sum(len(v) for v in bus_other.values()),
            'recognized_standard_bus': len(bus_recognized),
            'non_standard_interface': {
                'proprietary_or_generic': len(bus_other['proprietary_or_generic']),
                'signal_level': len(bus_other['signal_level']),
                'unknown_token': len(bus_other['unknown_token']),
            },
            'note': 'proprietary/analog/PWM/TTL 等非标准或信号级接口属正常品类，'
                    '不作冲突报告，仅作分布统计。',
        },
        'registry_gaps': registry_gaps,
        'hb_standard_coverage': hb_coverage,
        'conflicts': conflicts,
        'conflict_count': len(conflicts),
        'disclaimer': '本审计仅校验"声明是否可核实"，不构成兼容性结论；'
                      'unverified/registry_gap 属数据质量缺口，需用可溯源出处补全，而非直接判定不兼容。',
    }

    out_path = os.path.join(ROOT, 'api/standard-audit.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"✅ 标准自校验已生成: 机械声明 {out['mechanical_claims']['total_declared']}"
          f"（核实 {len(mech_verified)} / 未核实 {len(mech_unverified)}），"
          f"总线声明 {out['bus_claims']['total_declared']}"
          f"（公认数字总线 {out['bus_claims']['recognized_standard_bus']} / 非标准接口 {out['bus_claims']['non_standard_interface']['proprietary_or_generic'] + out['bus_claims']['non_standard_interface']['signal_level'] + out['bus_claims']['non_standard_interface']['unknown_token']}），"
          f"登记表缺口 {len(registry_gaps)}，行标覆盖 {len(hb_coverage)} → api/standard-audit.json")
    if conflicts:
        print(f"   ⚠️ 共 {len(conflicts)} 条可核实性冲突（机械未核实 + 登记表缺口，诚实标记，待补全出处）")


if __name__ == '__main__':
    main()
