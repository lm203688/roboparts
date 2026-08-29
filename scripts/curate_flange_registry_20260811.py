# -*- coding: utf-8 -*-
"""
机械接口登记表采编（20260811 批次）—— 让 registry_ref 这条链第一次真的能 join。

本批次不动实体库，只修 api/mechanical_interfaces.json，动因是本轮核查发现的三个硬缺陷：

【缺陷一：registry_ref 是一条断链】
  实体侧 mechanical_interface.standard 写的是 "ISO 9409-1-50-4-M6"（无 A），
  登记表 flange_designations[].id 写的是 "ISO9409-1-A50-4-M6"（有 A、无空格）。
  全库 707 处 registry_ref 指向本表，但**没有任何一个 standard 字符串能等值命中任何一行**。
  也就是说这条"实体→规范参考层"的链路一直是装饰性的：人看得懂，程序 join 不上。
  处置：每行补 aliases（收录实际在用的各种写法），并在 grammar 里写明归一化规则。

【缺陷二：命名语法的出处比它描述的对象更弱】
  grammar 声称格式为 "ISO 9409-1-A{d1}-{n}-{thread}"，出处是 abbpj.weisizhineng.com
  （ABB 集成商/经销站点，非 abb.com）。而两份**一手 OEM 手册**都写作无 A 形式：
    · Universal Robots《e-Series User Manual UR5e》图 4.2 图注：
      "The tool output flange (ISO 9409-1-50-4-M6) is where the tool is mounted at the tip of the robot."
    · Robotiq《FT 300-S / 2F-85 Instruction Manual》耦合件清单："Coupling for ISO 9409-1-50-4-M6"
  两种写法都真实存在于产业界，谁"正确"要看 ISO 9409-1:2004 原文（我方未持有）。
  处置：**不判谁对**，把两种形式都登记为可 join 的别名，并如实标注：带 A 形式目前
  只有第三方汇编出处，无 A 形式有两家 OEM 一手出处。

【缺陷三：source_tier 把第三方汇编标成了 A】
  四行法兰全部出自同一个非 OEM 域名，却标 source_tier=A（本项目 A 级=一手厂商官方）。
  处置：降为 B 并写明 basis。降级不删数据 —— 数据大概率是对的，但"大概率对"和
  "一手证实"是两件事，本项目吃过太多次把口径当事实的亏。

【本批次新增的一手证据】
  ISO9409-1-A50-4-M6 的 known_hosts 增补 "Universal Robots UR5e"，出处为 UR 官方
  用户手册 PDF（实测 HTTP 200，10.4 MB）与 universal-robots.com 官方技术单页（实测 200）。
  这是本表第一条非 ABB、且出自 OEM 自有域名的宿主记录。

【显式缺口：designations_in_use】
  新增该区块，从 entities.json 现算"实体库正在使用哪些编码、各自有没有规范行"。
  实测结果：31.5-4-M5 与 40-4-M6 在用但**登记表无对应行**。
  不补造行 —— 按 L1.77 纪律，没读到 ISO 9409-1:2004 原文就不替标准发明条目；
  但把缺口做成机读字段，让 agent 与后续批次能看见它，而不是让它继续隐身。

幂等：内容无变化时不改 generated_at，重复运行输出 unchanged。
"""
import io
import json
import os
import re
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, 'api', 'mechanical_interfaces.json')
ENT = os.path.join(ROOT, 'api', 'entities.json')

UR_MANUAL = 'https://s3-eu-west-1.amazonaws.com/ur-support-site/50557/UR5e_User_Manual_en_Global.pdf'
UR_TECHSHEET = ('https://www.universal-robots.com/manuals/EN/TechSheets/'
                'UR5e_techsheet_pdf_online/UR5e_techsheet_en.pdf')
ROBOTIQ_MANUAL = ('https://assets.robotiq.com/website-assets/support_documents/document/'
                  'FT300-S_Sensor_Manual_OMRON_TM_PDF_20210301.pdf')
ABB_COMPILATION = 'abbpj.weisizhineng.com（ABB 集成商汇编页，非 abb.com 官方域）'

DESIGNATION_FORMS = {
    'note': ('同一法兰在产业界存在两种书写形式，二者指向同一孔位；本表 id 沿用带 A 形式，'
             '但实体库 mechanical_interface.standard 使用无 A 形式，故每行以 aliases 收录'
             '全部在用写法，join 时按 normalize_rule 归一化后比对。'),
    'form_with_A': {
        'pattern': 'ISO 9409-1-A{d1}-{n}-{thread}',
        'example': 'ISO 9409-1-A50-4-M6',
        'evidence_strength': 'weak',
        'evidence_note': '目前仅见于第三方汇编（%s），未取得 OEM 一手出处或 ISO 原文。' % ABB_COMPILATION,
    },
    'form_without_A': {
        'pattern': 'ISO 9409-1-{d1}-{n}-{thread}',
        'example': 'ISO 9409-1-50-4-M6',
        'evidence_strength': 'strong',
        'evidence_note': ('两家 OEM 一手手册均采用此形式：Universal Robots《e-Series User Manual UR5e》'
                          '图 4.2 图注 "The tool output flange (ISO 9409-1-50-4-M6) is where the tool '
                          'is mounted at the tip of the robot."（%s）；Robotiq 官方手册耦合件清单 '
                          '"Coupling for ISO 9409-1-50-4-M6"（%s）。' % (UR_MANUAL, ROBOTIQ_MANUAL)),
    },
    'normalize_rule': ("去空格、大写、并删除尺寸段前的 'A' 前缀，即 "
                       "re.sub(r'ISO9409-1-A', 'ISO9409-1-', s.upper().replace(' ', ''))"),
    'unresolved': ('哪种形式与 ISO 9409-1:2004 原文一致尚未核实（我方未持有标准原文）。'
                   '本表不裁决，两种形式均可 join，避免因写法差异产生假阴。'),
    # 【20260811-09】把归一化规则的**作用域**写死。
    # 上一轮补 aliases 是为了让 707 处 registry_ref 能查到规范行；但"能查到同一行"
    # 极易被下游读成"这两种写法所指的法兰可以互相安装"——那是一句我方无从证实的
    # 等价断言（带 A 是同义写法还是型式区分，须看 ISO 原文）。查表与裁决是两件事，
    # 必须显式分开，否则一个便利措施会在下游变成孔位级的结论。
    'join_scope': ('本 normalize_rule 的作用域仅限**查表**：把实体侧在用写法映射到本表规范行。'
                   '它不构成"两种写法所指法兰可互相安装"的等价断言。'
                   '兼容性判定另有口径：functions/_lib/compat_engine.js 在"尺寸段一致、'
                   '字母前缀不同"时输出 compatible=null / relation=undecided_designation_form，'
                   '既不判不兼容（假红）也不判兼容（假绿）；纯词法差异（空白/大小写/'
                   'Unicode 连字符）才做归一。回归闸门 L1.89 锁死两层口径不得互相打架。'),
}

# 已核实采用 ISO 9409-1-50-4-M6 的宿主 —— 逐条挂出处，不再是一串裸字符串
HOSTS_EVIDENCE_50 = [
    {
        'host': 'Universal Robots UR5e',
        'host_kind': 'cobot_arm_tool_flange',
        'quote': ('Figure 4.2: The tool output flange (ISO 9409-1-50-4-M6) is where the tool '
                  'is mounted at the tip of the robot.'),
        'source': 'Universal Robots《e-Series User Manual UR5e》第 4 章 图 4.2 图注',
        'source_url': UR_MANUAL,
        'corroboration_url': UR_TECHSHEET,
        'source_tier': 'A',
        'source_tier_basis': 'oem_official_user_manual',
        'confidence': 0.95,
        'verified_at': '2026-08-11',
        'verification_note': ('2026-08-11 实测：手册 PDF HTTP 200（10,429,493 B）、'
                              'universal-robots.com 技术单页 HTTP 200（2,031,500 B），'
                              '后者「Tool flange for UR5e」工程图标注 Ø50±0.1 / 4×M6-6H / Ø6 H7 定位孔，'
                              '与图 4.2 一致。'),
    },
    {
        'host': 'ABB IRB1100 / IRB1200 / IRB120 / CRB1100 / IRB920 / IRB920T',
        'host_kind': 'industrial_arm_tool_flange',
        'quote': None,
        'source': 'ABB 机型法兰规格对照（第三方汇编）',
        'source_url': None,
        'source_tier': 'B',
        'source_tier_basis': 'third_party_compilation_not_oem_domain',
        'confidence': 0.9,
        'gap': ('出处为 %s，未取得 abb.com 官方手册逐机型确认；'
                '数据大概率正确，但未达本项目 A 级（一手 OEM 出处）标准。' % ABB_COMPILATION),
    },
]

TIER_FIX_NOTE = ('原标 source_tier=A，但出处为 %s，不满足本项目 A 级定义（一手厂商官方出处），'
                 '20260811 降为 B 并保留数据。' % ABB_COMPILATION)


def normalize(s):
    return re.sub(r'ISO9409-1-A', 'ISO9409-1-', str(s).upper().replace(' ', ''))


def aliases_for(row_id):
    base = normalize(row_id)                      # ISO9409-1-50-4-M6
    spaced = base.replace('ISO9409-1-', 'ISO 9409-1-')
    with_a = base.replace('ISO9409-1-', 'ISO9409-1-A')
    spaced_a = with_a.replace('ISO9409-1-A', 'ISO 9409-1-A')
    return sorted({row_id, base, spaced, with_a, spaced_a})


def main():
    with io.open(REG, encoding='utf-8') as f:
        reg = json.load(f)
    with io.open(ENT, encoding='utf-8') as f:
        ents = json.load(f)

    before = json.dumps(reg, ensure_ascii=False, sort_keys=True)
    changes = []

    # ---- 1. grammar：登记两种书写形式 + 归一化规则 ----------------------------
    g = reg['designation_grammar']
    if g.get('designation_forms') != DESIGNATION_FORMS:
        g['designation_forms'] = DESIGNATION_FORMS
        changes.append('grammar.designation_forms')
    if g.get('source_tier') != 'B':
        g['source_tier'] = 'B'
        g['source_tier_basis'] = 'third_party_compilation_not_oem_domain'
        g['source_tier_note'] = TIER_FIX_NOTE
        changes.append('grammar.source_tier A→B')

    # ---- 2. 每行补 aliases（修断链）+ 出处分级订正 ----------------------------
    for row in reg['flange_designations']:
        al = aliases_for(row['id'])
        if row.get('aliases') != al:
            row['aliases'] = al
            changes.append('%s.aliases' % row['id'])
        if row.get('source_tier') == 'A' and 'weisizhineng' in str(row.get('source', '')):
            row['source_tier'] = 'B'
            row['source_tier_basis'] = 'third_party_compilation_not_oem_domain'
            row['source_tier_note'] = TIER_FIX_NOTE
            changes.append('%s.source_tier A→B' % row['id'])

    # ---- 3. 50-4-M6 增补 UR5e 宿主（本表首条 OEM 自有域出处）------------------
    row50 = next(r for r in reg['flange_designations'] if r['id'] == 'ISO9409-1-A50-4-M6')
    hosts = list(row50.get('known_hosts') or [])
    if 'Universal Robots UR5e' not in hosts:
        hosts.insert(0, 'Universal Robots UR5e')
        row50['known_hosts'] = hosts
        changes.append('ISO9409-1-A50-4-M6.known_hosts += UR5e')
    if row50.get('known_hosts_evidence') != HOSTS_EVIDENCE_50:
        row50['known_hosts_evidence'] = HOSTS_EVIDENCE_50
        changes.append('ISO9409-1-A50-4-M6.known_hosts_evidence')

    # ---- 4. designations_in_use：把"在用但无规范行"的缺口做成机读字段 ----------
    reg_index = {}
    for row in reg['flange_designations']:
        for a in row['aliases']:
            reg_index[normalize(a)] = row['id']

    used = {}
    for e in ents['entities']:
        mi = e.get('mechanical_interface') or {}
        for key in ('standard', 'flange', 'tool_side', 'tool_side_flange'):
            v = mi.get(key)
            if not v:
                continue
            for tok in (v if isinstance(v, list) else [v]):
                tok = str(tok).strip()
                if not tok.upper().startswith('ISO'):
                    continue
                slot = used.setdefault(tok, {'entity_ids': set(), 'sides': set()})
                slot['entity_ids'].add(e['id'])
                slot['sides'].add('tool' if key.startswith('tool_side') else 'robot')

    in_use = []
    for tok in sorted(used):
        norm = normalize(tok)
        hit = reg_index.get(norm)
        m = re.match(r'^ISO9409-1-(\d+(?:\.\d+)?)-(\d+)-M(\d+)$', norm)
        in_use.append({
            'token_as_written': tok,
            'normalized': norm,
            'parsed': ({'d1_mm': float(m.group(1)), 'bolt_count': int(m.group(2)),
                        'thread': 'M' + m.group(3)} if m else None),
            'registry_row': hit,
            'status': 'registered' if hit else 'unregistered_gap',
            'declared_sides': sorted(used[tok]['sides']),
            'used_by_entity_ids': sorted(used[tok]['entity_ids']),
        })

    unregistered = [x['token_as_written'] for x in in_use if x['status'] == 'unregistered_gap']
    block = {
        'description': ('从 api/entities.json 现算：实体库正在引用的 ISO 9409-1 编码，'
                        '以及每个编码在本表是否有规范行。registry_row=null 即"在用但未登记"。'),
        'computed_from': '/api/entities.json → mechanical_interface.{standard,flange,tool_side,tool_side_flange}',
        'join_rule': DESIGNATION_FORMS['normalize_rule'],
        'total_tokens_in_use': len(in_use),
        'unregistered_count': len(unregistered),
        'unregistered_policy': ('不为消除缺口而凭空补行。按本项目纪律（L1.77），未读到 '
                                'ISO 9409-1:2004 原文即不替标准发明条目；缺口在此显式列出，'
                                '待取得标准原文或 OEM 一手尺寸图后再补规范行。'),
        'entries': in_use,
    }
    if reg.get('designations_in_use') != block:
        reg['designations_in_use'] = block
        changes.append('designations_in_use（%d 个在用编码，%d 个无规范行）'
                       % (len(in_use), len(unregistered)))

    # ---- 5. honest_limits 的覆盖率不再手抄，改从实体库现算 --------------------
    cov = (ents.get('meta') or {}).get('mechanical_interface_coverage') or {}
    fill = cov.get('fill_pct')
    hl = reg['meta']['access']['honest_limits']
    if fill is not None and hl.get('mechanical_interface_declared_pct') != fill:
        hl['mechanical_interface_declared_pct'] = fill
        changes.append('honest_limits.fill_pct → %s（改为从 entities.json 现算）' % fill)
    src_note = 'entities.json:meta.mechanical_interface_coverage.fill_pct（唯一真相源，勿手改）'
    if hl.get('mechanical_interface_declared_pct_source') != src_note:
        hl['mechanical_interface_declared_pct_source'] = src_note
        changes.append('honest_limits 标注真相源')

    if not changes:
        print('登记表采编（20260811 批次）：unchanged（幂等）')
        return

    reg['meta']['generated_at'] = datetime.now(
        timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    reg['meta']['version'] = '1.1.0'

    # ---- 自检：阳性 + 阴性对照（防"join 规则写了但没生效"）--------------------
    idx = {}
    for row in reg['flange_designations']:
        for a in row['aliases']:
            idx[normalize(a)] = row['id']
    pos = idx.get(normalize('ISO 9409-1-50-4-M6'))
    neg = idx.get(normalize('ISO 9409-1-999-4-M6'))
    if pos != 'ISO9409-1-A50-4-M6':
        raise SystemExit('阳性对照失败：实体库在用写法 "ISO 9409-1-50-4-M6" 仍 join 不上登记表')
    if neg is not None:
        raise SystemExit('阴性对照失败：不存在的编码 "ISO 9409-1-999-4-M6" 竟命中 %s，'
                         '归一化规则过宽' % neg)
    if len(reg['designations_in_use']['entries']) == 0:
        raise SystemExit('designations_in_use 为空 —— 实体库明明有 declared 条目，'
                         '取数路径必然写错（空输入下平凡成立的自检等于没自检，见 L1.88）')

    with io.open(REG, 'w', encoding='utf-8') as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
        f.write('\n')

    assert json.dumps(reg, ensure_ascii=False, sort_keys=True) != before
    print('登记表采编（20260811 批次）：changed=%d' % len(changes))
    for c in changes:
        print('  ✏️ ', c)
    print('  ✅ 阳性对照：ISO 9409-1-50-4-M6 → %s' % pos)
    print('  ✅ 阴性对照：ISO 9409-1-999-4-M6 → 未命中')
    print('  📊 在用编码 %d 个，其中无规范行 %d 个：%s'
          % (len(in_use), len(unregistered), '、'.join(unregistered) or '—'))


if __name__ == '__main__':
    main()
