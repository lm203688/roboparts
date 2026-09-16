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
  - 机械核查样本随飞轮引入更多带机械声明的 BOM 而自动变厚
    （2026-09-16 实测 28 条实体×标号声明，不再是早期文档写的"仅 2 条"）。

generated_at 语义（2026-09-16 起）：
  锚定**源内容最后变更时刻**（三个输入文件的 mtime 最大值），而非脚本运行时刻。
  理由：本脚本挂入部署链后每次部署都会跑，若用运行时刻，同一内容也会每次
  改写字节 → 每小时一份"纯时间戳" git 噪声，正是本项目反复根治的那类病。
  改锚源 mtime 后：内容不变则输出字节不变（幂等），内容一变则时间戳必变。
  精确内容锚定另见 source_digest（源文件 sha256 前 16 位）。

用法：python scripts/build_standard_audit.py
输出：api/standard-audit.json
"""
from __future__ import annotations
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SOURCES = ['api/entities.json', 'api/mechanical_interfaces.json',
           'ops/intel/hb-standards-ledger.json']


def load(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return json.load(f)


def norm_mech(s: str) -> str:
    """与 mechanical_interfaces.json 的 join_rule 完全一致：去空格、大写、去 A 前缀。"""
    s = str(s).upper().replace(' ', '')
    s = re.sub(r'ISO9409-1-A', 'ISO9409-1-', s)
    return s


def source_anchor() -> dict:
    """返回 {generated_at, source_digest}，均锚定源**内容**而非脚本运行时刻/文件 mtime。

    取各源内已有的时间戳字段（meta.updated / meta.generated_at …）的最大值。
    选内容锚而非 mtime：部署链会刷派生产物时间戳，mtime 每次部署都变，
    会重新制造本项目反复根治的「纯时间戳 git 噪声」。
    字节级精确锚定见 source_digest（各源 sha256 前 16 位串联）。
    """
    best, digest = None, []
    for rel in SOURCES:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        with open(p, 'rb') as f:
            digest.append(hashlib.sha256(f.read()).hexdigest()[:16])
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        m = d.get('meta') if isinstance(d, dict) else None
        for scope in (m, d):
            if not isinstance(scope, dict):
                continue
            for k, v in scope.items():
                if isinstance(v, str) and re.match(r'^\d{4}-\d{2}-\d{2}[T ]', v):
                    if best is None or v > best:
                        best = v
    return {
        'generated_at': best or 'unknown',
        'generated_at_semantics': (
            '锚定三个输入源**内容内**时间戳字段的最大值，非脚本运行时刻、非文件 mtime；'
            '源内容不变则本字段不变（幂等）。字节级精确锚定见 source_digest。'
        ),
        'source_digest': '/'.join(digest),
    }


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
            # aliases 必须一并入表：实体库用的是无 A 形式，登记表 id 是带 A 形式，
            # 只靠 norm_mech(id) 恰好也能命中，但一旦某行只有 alias 形态就会假红。
            for a in (f.get('aliases') or []):
                known.add(norm_mech(a))
    du = mi.get('designations_in_use', {}) or {}

    # 【20260916 死角修复】原写法遍历 du.items() 的**顶层键**（description /
    # total_tokens_in_use / unregistered_count / unregistered_policy / entries …），
    # 而真正带 registry_row 的 entries 是一个**列表**，永远读不到。结果：
    #   - registry_gaps 恒为 []（缺口检测是死代码，从未生效过）
    #   - known 被塞进 "3" / "2" / "ENTRIES" 这类垃圾串
    # 2026-09-16 实测：api/standard-audit.json（8/17 快照）一直对外报 4 条
    # unverified_mechanical_claim，声称 31.5-4-M5 与 40-4-M6 不在已知指定集中——
    # 两行自 commit 11af550 起就已登记。冻结快照 + 死检测叠加的假报。
    entries = du.get('entries') if isinstance(du.get('entries'), list) else []
    for ent in entries:
        if isinstance(ent, dict):
            tok = ent.get('token_as_written') or ent.get('normalized')
            if tok:
                known.add(norm_mech(tok))
        elif isinstance(ent, str):
            known.add(norm_mech(ent))

    # ── 登记表缺口：在用但未登记规范行 ──────────────────────────────
    registry_gaps = []
    for ent in entries:
        # 只认 status=unregistered_gap：registry_row=null 还有第二种情形
        # （unparseable_bare_standard，厂商只给了标准号没给几何），
        # 那不是可补的缺口，不能混报成缺口。
        if isinstance(ent, dict) and ent.get('status') == 'unregistered_gap':
            registry_gaps.append({
                'designation': norm_mech(ent.get('token_as_written') or ''),
                'entity_count': ent.get('entity_count'),
                'used_by_entity_ids': ent.get('used_by_entity_ids') or [],
                'note': '实体库在引用该编码，但 mechanical_interfaces.json 无对应规范行'
                        '（registry_row=null 且 status=unregistered_gap）',
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
    mech_unresolvable = []
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
                # entity_kind 必须带出：审计记录引用的是**真实实体**（id+name），
                # 回归的 entity_kind 全量对账会把它当派生实体看待——丢掉 kind 即漂移。
                rec = {'id': eid, 'name': e.get('name'),
                       'entity_kind': e.get('entity_kind'), 'declared': s}
                # 裸标准号（只有 ISO 9409-1、没给 PCD/孔数/螺纹）不构成可核实声明：
                # 它在 designations_in_use 里出现会命中 known，若直接算 verified
                # 就是把「厂商没说清」记成「已核实」，属过度计数。
                if ns in known and not re.fullmatch(r'ISO9409-1', ns):
                    mech_verified.append(rec)
                elif ns in known:
                    rec['note'] = ('声明只到标准号本身，未给出 (PCD, 孔数, 螺纹)，'
                                    '无可核实内容；这不是笔误，是厂商未声明到可判定粒度')
                    mech_unresolvable.append(rec)
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
                rec = {'id': eid, 'name': e.get('name'),
                       'entity_kind': e.get('entity_kind'),
                       'field': field, 'declared': t}
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

    anchor = source_anchor()
    out = {
        'generated_at': anchor['generated_at'],
        'generated_at_semantics': anchor['generated_at_semantics'],
        'source_digest': anchor['source_digest'],
        'purpose': '标准登记表 ↔ 实体声明 自动交叉校验（数据质量自检，非兼容性裁决）',
        'registry': {
            'known_mechanical_designations': len(known),
            'recognized_bus_standards': sorted(BUS_STD),
            'hb_in_scope_count': len(hb_coverage),
        },
        'mechanical_claims': {
            'total_declared': len(mech_verified) + len(mech_unverified) + len(mech_unresolvable),
            'verified': mech_verified,
            'unverified': mech_unverified,
            'unresolvable_granularity': mech_unresolvable,
            'note': ('verified = 编码落在已知指定集且给出可判定的 (PCD, 孔数, 螺纹)；'
                     'unverified = 不在已知指定集（可能未登记）；'
                     'unresolvable_granularity = 只给到标准号本身、无可核实内容。'
                     '后两者不属"错误"，但都不能算已核实。'),
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
    # 保留部署链 0c（inject_api_access.py）注入的 meta.access：本脚本整份重写产物，
    # 若不自带 access 就会每次部署「抹掉→再注入」来回抖动（多一次无意义 git diff）。
    if out.get('meta') is None and os.path.exists(out_path):
        try:
            with open(out_path, encoding='utf-8') as f:
                old = json.load(f)
            acc = (old.get('meta') or {}).get('access')
            if acc:
                out['meta'] = {'access': acc}
        except (OSError, ValueError):
            pass

    # 幂等闸门：内容不变就不写盘，避免每次部署都产生纯时间戳 diff
    new_bytes = (json.dumps(out, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if os.path.exists(out_path):
        with open(out_path, 'rb') as f:
            if f.read() == new_bytes:
                print(f"✅ 标准自校验无需更新（内容未变）: 机械声明 {out['mechanical_claims']['total_declared']}"
                      f"（核实 {len(mech_verified)} / 未核实 {len(mech_unverified)} / "
                      f"粒度不足 {len(mech_unresolvable)}），"
                      f"登记表缺口 {len(registry_gaps)}，冲突 {len(conflicts)} → api/standard-audit.json")
                return
    with open(out_path, 'wb') as f:
        f.write(new_bytes)

    print(f"✅ 标准自校验已生成: 机械声明 {out['mechanical_claims']['total_declared']}"
          f"（核实 {len(mech_verified)} / 未核实 {len(mech_unverified)} / "
          f"粒度不足 {len(mech_unresolvable)}），"
          f"总线声明 {out['bus_claims']['total_declared']}"
          f"（公认数字总线 {out['bus_claims']['recognized_standard_bus']} / 非标准接口 {out['bus_claims']['non_standard_interface']['proprietary_or_generic'] + out['bus_claims']['non_standard_interface']['signal_level'] + out['bus_claims']['non_standard_interface']['unknown_token']}），"
          f"登记表缺口 {len(registry_gaps)}，行标覆盖 {len(hb_coverage)} → api/standard-audit.json")
    if conflicts:
        print(f"   ⚠️ 共 {len(conflicts)} 条可核实性冲突（机械未核实 + 登记表缺口，诚实标记，待补全出处）")


if __name__ == '__main__':
    main()
