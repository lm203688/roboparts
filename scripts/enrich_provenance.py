#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboParts 溯源三字段治理脚本（N10 Schema 治理 · 覆盖率提升管线）

职责（严格只做「已有证据的回填」，绝不凭空编造 source / 日期）：
1. confidence 类型修复：历史上写成字符串（official / specsheet / community），
   转换为 0~1 数值，原始取值保留到 confidence_basis
2. source 回填：从实体已有的 sources[] / source_url 中提取可读来源串
3. last_verified 回填：从 sources[].collected_at 或 last_updated 中提取日期（YYYY-MM-DD）
4. confidence 派生：对「有 source 但无 confidence」的实体，按来源可信度规则表打分
5. verified 标记：verified = 有 source 且 confidence >= 0.6；
   否则 verified=false（不删除实体，供前端降权展示）

【N10 20260805 周三升级 · 分级溯源】
  上周把「有没有 source 字段」当成唯一指标，导致一个危险倾向：
  只要往 source 里塞点什么，覆盖率就好看。本次改为三级口径，杜绝指标注水：
    Tier A 可追溯 traceable —— 有 URL / 具名文档，可点开复核
    Tier B 可归因 attributable —— 只知道来源「类别」（厂商目录 / 具名标准），无法点开
    Tier C 无溯源 none
  Tier B 的 confidence 一律 < 0.6，因此 verified 恒为 false，前端照常降权。
  对外报的主指标是 traceable_pct（Tier A），source_pct 仅作过程指标。
  另：已被 audit_data_quality.py 隔离（quarantine=true）的条目**不做任何归因**，
  避免给无法溯源的合成数据"洗白"。

用法：python scripts/enrich_provenance.py [--dry-run]
幂等：可重复运行，结果与单次运行一致。
前置：先跑 scripts/audit_data_quality.py（提供 quarantine 标记）
后置：再跑 scripts/normalize_categories.py 把字段传播到三副本。
"""
import json
import os
import re
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES_PATH = os.path.join(ROOT, 'api', 'entities.json')

# 字符串 confidence -> 数值
TIER_SCORE = {
    'official': 0.90,
    'specsheet': 0.85,
    'vendor': 0.85,
    'community': 0.55,
    'unknown': 0.40,
}

# sources[].source_credibility -> 数值
CRED_SCORE = {'A': 0.72, 'B': 0.62, 'C': 0.45}

# 有 source 但无 confidence 时的规则表（按顺序命中，先严后宽）
SOURCE_RULES = [
    (r'官网|Official|patent filings|Robotics 20', 0.85, 'official_source'),
    (r'[Cc]ommunity|Aggregation|聚合', 0.55, 'community_source'),
    (r'Specification|specsheet|datasheet|规格书', 0.75, 'spec_source'),
    (r'web_search|Web Research|网络检索', 0.60, 'web_search'),
    (r'研报|报告|分析|analysis|eefocus|东方财富|雪球', 0.60, 'industry_report'),
]
DEFAULT_SCORE, DEFAULT_BASIS = 0.55, 'unclassified_source'

VERIFY_THRESHOLD = 0.6

# ---- Tier B 归因规则 ----------------------------------------------------
# B1 具名标准：IEC 61158 / CiA 301 / IEEE 802.1AS / ISO 13849 / GB 5226 / RFC 8032 …
#    标准号是公开可查的锚点，比"某厂商说的"强，但库里没存条文出处，仍算 Tier B。
# 【2026-08-10 收唯一源】判据不再在本文件另抄一份，一律引用 govern_source_tier
#    （同一事实存两处的账见 L1.69）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from govern_source_tier import (  # noqa: E402
    NAMED_STANDARD, JUNK_STANDARDS, derive_tier,
)
VAGUE_VENDORS = {'未指定', '未明确', 'N/A', 'Unknown', ''}

STANDARD_SCORE = 0.55   # < 0.6，verified 仍为 false
VENDOR_SCORE = 0.50     # < 0.6，verified 仍为 false


BASELINE_PATH = os.path.join(ROOT, 'scripts', 'quality-baseline.json')


def _criterion_break():
    """取「口径断点」那条基线历史（带 criterion 的最新一条）。

    对外 note 里的历史值只能从这里读，不许在文案里手打 —— 手打的数字
    第二天就会和现算值打架（2026-08-10 note 写「真值 9.46%」而字段是
    12.85%，两个数字并排上线，消费方无从分辨哪个是真的）。见 L1.83。
    """
    try:
        with open(BASELINE_PATH, encoding='utf-8') as f:
            hist = json.load(f).get('_traceable_history') or []
    except Exception:
        return {}
    marked = [h for h in hist if h.get('criterion')]
    return marked[-1] if marked else {}


def build_provenance_note(current_traceable_pct):
    """渲染对外 note：数字全部现算/现读，文案里不出现任何手打百分比。"""
    brk = _criterion_break()
    sup = brk.get('superseded_value')
    base = ('主指标看 traceable_pct（Tier A 可点开复核）；source_pct 含 Tier B 弱归因，仅作过程指标；'
            'Tier C 已显式标注，供 Agent 侧过滤。')
    if sup is None:
        return base
    return base + (
        '【%s 更正】此前实现为「source 字段非空即判 A」，traceable_pct 曾虚报为 %s%%，'
        '已按证据重算为 %s%%，原值留在实体的 source_tier_prev 字段供审计。'
        % (brk.get('date', ''), sup, current_traceable_pct)
    )


def tier_of(e):
    """判定溯源等级：A 可追溯 / B 可归因 / C 无。

    【2026-08-10 第 70 次运行 · 修「定义与实现分家」】
    原实现是 `有 source 就返回 A`，与本文件开头写死的定义
    「Tier A —— 有 URL / 具名文档，可点开复核」直接矛盾，且那段改动的注释
    还声称「杜绝指标注水」。实测后果：336 条 A 里只有 48 条真有深链，
    对外 traceable_pct 报 47.32%，按证据重算后真值 12.85%（91/708）。
    （9.46% 是重算过程中尚未合并 L1.70「项目自有主页可 A」例外时的中间值，
     曾被当作终值手打进对外 note 并上线，见 L1.83。）
    现改为引用唯一判据源，tier 只由证据形态推导，不看已有字段、不默认给分。
    """
    return derive_tier(e)[0]


def coverage(entities):
    n = len(entities)
    out = {}
    for k in ('source', 'confidence', 'last_verified'):
        c = sum(1 for e in entities if e.get(k) not in (None, '', [], {}))
        out[k] = (c, round(c * 100.0 / n, 2))
    numeric = sum(1 for e in entities if isinstance(e.get('confidence'), (int, float)))
    out['confidence_numeric'] = (numeric, round(numeric * 100.0 / n, 2))
    trace = sum(1 for e in entities if tier_of(e) == 'A')
    out['traceable'] = (trace, round(trace * 100.0 / n, 2))
    return out


def domain(url):
    m = re.match(r'https?://([^/]+)', str(url))
    return m.group(1).replace('www.', '') if m else str(url)[:60]


def derive_from_sources(e):
    """从 sources[] / source_url 提取 (source_str, last_verified, cred_score, basis)"""
    src = lv = basis = None
    score = None
    arr = e.get('sources') or []
    if isinstance(arr, list):
        for x in arr:
            if isinstance(x, dict):
                st = x.get('source_type') or 'web'
                cred = x.get('source_credibility')
                src = f'{st} aggregation (credibility {cred})' if cred else f'{st} aggregation'
                score = CRED_SCORE.get(cred)
                basis = f'sources[].credibility={cred}'
                col = x.get('collected_at')
                if col:
                    lv = str(col)[:10]
                break
            if isinstance(x, str) and x.startswith('http'):
                src = f'{domain(x)} (URL 引用)'
                score, basis = 0.60, 'sources[].url'
                break
    if not src and e.get('source_url'):
        src = f'{domain(e["source_url"])} (URL 引用)'
        score, basis = 0.60, 'source_url'
    return src, lv, score, basis


def score_from_source_text(text):
    for pat, sc, basis in SOURCE_RULES:
        if re.search(pat, str(text)):
            return sc, basis
    return DEFAULT_SCORE, DEFAULT_BASIS


def main():
    dry = '--dry-run' in sys.argv
    doc = json.load(open(ENTITIES_PATH, encoding='utf-8'))
    entities = doc['entities']
    before = coverage(entities)

    # 「已被证据背书的厂商」：该厂商在库中至少有一条 **Tier A 可追溯** 实体。
    # 用数据本身推导白名单，而不是手写一份主观清单。
    #
    # 【2026-08-05 第 3 轮修复 · 哑火 bug】
    # 原判据是「有 source 且 source_tier 缺失」。但下方步骤 0 会给所有存量
    # 有 source 的条目补盖 source_tier='A'，于是从第二次运行起该集合恒为空，
    # Tier B 厂商归因规则静默失效 —— 表面正常跑完，实际一条都不会命中。
    # 改为直接认 Tier A：厂商要被「背书」，前提是它至少有一条能点开复核的来源。
    endorsed_vendors = set()
    for e in entities:
        if e.get('source') and e.get('source_tier', 'A') == 'A':
            v = str(e.get('manufacturer') or e.get('developer') or '').strip()
            if v and v not in VAGUE_VENDORS:
                endorsed_vendors.add(v)

    stat = collections.Counter()
    for e in entities:
        # 0) 溯源等级：由 govern_source_tier.derive_tier 按证据形态推导。
        #    原逻辑「有 source 就盖 A」已删除 —— 那是本轮 313 条错标的根因。
        _t, _b = derive_tier(e)
        if e.get('source_tier') != _t:
            stat['tier_recomputed'] += 1
        e['source_tier'], e['source_tier_basis'] = _t, _b

        # 1) confidence 字符串 -> 数值
        conf = e.get('confidence')
        if isinstance(conf, str):
            tier = conf.strip().lower()
            e['confidence'] = TIER_SCORE.get(tier, TIER_SCORE['unknown'])
            e['confidence_basis'] = f'tier:{tier}'
            stat['confidence_str2num'] += 1
            conf = e['confidence']

        # 2/3) source & last_verified 回填
        d_src, d_lv, d_score, d_basis = derive_from_sources(e)
        if not e.get('source') and d_src:
            e['source'] = d_src
            stat['source_backfilled'] += 1
        if not e.get('last_verified'):
            lv = d_lv or (str(e['last_updated'])[:10] if e.get('last_updated') else None)
            if lv and re.match(r'^\d{4}-\d{2}-\d{2}$', lv):
                e['last_verified'] = lv
                stat['last_verified_backfilled'] += 1

        # 4) confidence 派生（仅对有 source 的实体）
        if e.get('source') and not isinstance(e.get('confidence'), (int, float)):
            if d_score is not None:
                e['confidence'] = d_score
                e['confidence_basis'] = d_basis
            else:
                sc, basis = score_from_source_text(e['source'])
                e['confidence'] = sc
                e['confidence_basis'] = basis
            stat['confidence_derived'] += 1

        # 4.5) Tier B 归因 —— 仅对「非隔离、仍无 source」的实体
        #      隔离条目（合成厂商/占位ID/非实体）一律不归因，避免洗白
        if not e.get('source') and not e.get('quarantine'):
            std = str(e.get('standard') or '').strip()
            vendor = str(e.get('manufacturer') or e.get('developer') or '').strip()
            if std and std not in JUNK_STANDARDS and NAMED_STANDARD.search(std):
                e['source'] = f'具名标准：{std}（未逐条核验原文）'
                e['source_tier'] = 'B'
                e['confidence'] = STANDARD_SCORE
                e['confidence_basis'] = 'named_standard'
                stat['tierB_standard'] += 1
            elif vendor and vendor not in VAGUE_VENDORS and vendor in endorsed_vendors:
                e['source'] = f'厂商目录声明值：{vendor}（无原始链接，未核验）'
                e['source_tier'] = 'B'
                e['confidence'] = VENDOR_SCORE
                e['confidence_basis'] = 'endorsed_vendor_catalog'
                stat['tierB_vendor'] += 1

        # 5) verified 标记
        c = e.get('confidence')
        ok = bool(e.get('source')) and isinstance(c, (int, float)) and c >= VERIFY_THRESHOLD
        if e.get('verified') != ok:
            stat['verified_true' if ok else 'verified_false'] += 1
        e['verified'] = ok

    after = coverage(entities)

    # 干净集（排除隔离条目）口径 —— 这才是真正可运营的分母
    clean = [e for e in entities if not e.get('quarantine')]
    clean_cov = coverage(clean) if clean else {}
    tiers = collections.Counter(tier_of(e) for e in entities)

    if not dry:
        doc.setdefault('meta', {})
        doc['meta']['provenance_coverage'] = {
            'source_pct': after['source'][1],
            'traceable_pct': after['traceable'][1],
            'confidence_pct': after['confidence'][1],
            'last_verified_pct': after['last_verified'][1],
            'tier_a_traceable': tiers.get('A', 0),
            'tier_b_attributable': tiers.get('B', 0),
            'tier_c_none': tiers.get('C', 0),
            'verified_true': sum(1 for e in entities if e.get('verified')),
            'verified_false': sum(1 for e in entities if not e.get('verified')),
            'verify_threshold': VERIFY_THRESHOLD,
            'clean_set': {
                'total': len(clean),
                'source_pct': clean_cov.get('source', (0, 0))[1],
                'traceable_pct': clean_cov.get('traceable', (0, 0))[1],
                'confidence_pct': clean_cov.get('confidence', (0, 0))[1],
                'last_verified_pct': clean_cov.get('last_verified', (0, 0))[1],
            },
            # 【L1.55 型复发防护】tier_definition 是 L1.70 闸门的判据依据，
            # 本处是整份重写 provenance_coverage，漏写一次就会被静默抹掉
            # （20260810-21 本轮真实踩过一次）。必须在生成器里显式带上。
            'tier_definition': {
                'A': '可点开复核的一手来源（官方规格书/标准文本/带链接厂商文档）',
                'B': '弱归因（厂商目录声明值、官网首页，无原始链接）',
                'C': '无溯源（历史导入，待补来源，confidence 上限 0.30）',
            },
            'tier_rule': (
                'source_tier 由证据形态推导，不由录入者自封：'
                'A=有深链可点开复核；B=仅根域名/具名标准号/具名厂商目录（知道去哪找，点不开）；'
                'C=无来源/无身份聚合/有话无锚点。判据唯一源 scripts/govern_source_tier.py'
            ),
            # 【L1.83】note 里的百分比一律渲染，不许手打：手打的数字不会随
            # 重算更新，会和它旁边的机读字段公开打架。
            'note': build_provenance_note(after['traceable'][1]),
        }
        with open(ENTITIES_PATH, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write('\n')

    print('=== 溯源覆盖率治理 ===', '(dry-run)' if dry else '')
    print(f'--- 全量口径 (n={len(entities)}) ---')
    for k in ('source', 'traceable', 'confidence', 'last_verified', 'confidence_numeric'):
        b, a = before[k], after[k]
        print(f'  {k:20s} {b[0]:>4} ({b[1]:>5.2f}%)  ->  {a[0]:>4} ({a[1]:>5.2f}%)  {a[1]-b[1]:+.2f}pp')
    print(f'  溯源分级： A可追溯 {tiers.get("A",0)} / B可归因 {tiers.get("B",0)} / C无溯源 {tiers.get("C",0)}')
    print(f'--- 干净集口径 (n={len(clean)}，已排除 {len(entities)-len(clean)} 条隔离) ---')
    for k in ('source', 'traceable', 'confidence', 'last_verified'):
        a = clean_cov[k]
        print(f'  {k:20s} {a[0]:>4} ({a[1]:>5.2f}%)')
    print('  变更明细：', dict(stat))
    print(f'  verified=true  {sum(1 for e in entities if e.get("verified"))} 条')
    print(f'  verified=false {sum(1 for e in entities if not e.get("verified"))} 条（前端降权，不删除）')


if __name__ == '__main__':
    main()
