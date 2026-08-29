#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboParts 数据质量审计脚本（N10 Schema 治理 · 可信度隔离层）

背景（20260805 周三治理发现）：
  溯源覆盖率长期卡在 47% 上不去，根因不是「回填规则不够」，而是库里混入了
  一批**根本无法溯源**的条目。它们由早期新闻抓取 / 批量扩充留下，特征极其明确：
    1. 键盘序列占位 ID（ACTUATOR-A1B2C3 / LLM-a1b2c3 / PROTOCOL-abc123 …）
    2. 合成厂商名（FluidForce Inc / OmniMotors / Synthetic Motion Systems …），
       经检索确认无对应机器人执行器厂商及产品
    3. 根本不是实体（"IP55" / "48V-300VDC" / "消费电子" / "通讯协议全覆盖"）
  对一个「零部件兼容性」SaaS 来说，这类条目一旦被选型引擎命中就是硬伤。

补充（20260808-02）：
    4. 同物异 ID 重复 —— 同名同厂商登记了两遍，两条都在清洁集里。
       详见 scripts/lib/dedupe_rule.py 的模块注释。

本脚本职责（**非破坏性**，只加标记不删数据，符合治理约定）：
  为命中条目写入 data_quality / quarantine 两个字段，供前端与 API 过滤降权。
  quarantine=true 的条目建议：默认不进选型结果，仅在「显示未核验数据」时展示。

用法：python scripts/audit_data_quality.py [--dry-run]
幂等：可重复运行，结果与单次运行一致。
运行后需再跑 scripts/normalize_categories.py 把字段传播到三副本。
"""
import json
import os
import re
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES_PATH = os.path.join(ROOT, 'api', 'entities.json')

sys.path.insert(0, os.path.join(ROOT, 'scripts', 'lib'))
from dedupe_rule import mark_duplicates  # noqa: E402

# ---------------------------------------------------------------------------
# 规则 1：键盘序列占位 ID
# 早期批量写入时 ID 用了 a1b2c3 / abc123 这类顺手敲的假哈希，
# 是「本条目未经过正规入库流程」的强信号。
# ---------------------------------------------------------------------------
PLACEHOLDER_ID = re.compile(
    r'(a1b2c|d4e5f|g7h8i|j0k1l|m3n4o|p6q7r|s9t0u|v2w3x|y5z6a|b8c9d'
    r'|a3b7c|d4e8f|g5h1j|k6m4n|p7q8r|s2t3u|v5w6x|y8z9a|b2c3d|e5f6g)'
    r'|-(abc|def|ghi|jkl|mno|pqr|stu|vwx|yza|bcd|efg)\d*$',
    re.I,
)

# ---------------------------------------------------------------------------
# 规则 2：无法溯源的合成厂商名单（ACT-118~147 区块）
# 判定依据：① 无 source ② 无 last_updated ③ 产品名为通用臆造词
#          ④ 公开检索无对应机器人零部件厂商
# 注意：RoboDrive/Kollmorgen（ACT-024）是真实存在的德国无框电机厂商，
#      已被 Kollmorgen 收购，ILM 70 为真实型号 —— **不在**本名单内。
# ---------------------------------------------------------------------------
UNVERIFIABLE_VENDORS = {
    'RoboDrive Dynamics', 'RoboDrive Systems', 'Synthetic Motion Systems',
    'FluidForce Inc', 'FluidPower Solutions', 'CompressTech Solutions',
    'Smart Materials Co', 'Smart Materials Co.', 'Precision Piezo Ceramics',
    'Precision Micro Devices', 'HeavyBot Components', 'HeavyMotive Inc.',
    'AirLogic Dynamics', 'OmniMotors', 'Microbotics LLC',
}

# ---------------------------------------------------------------------------
# 规则 3：根本不是「零部件实体」的条目
# 这些是从新闻/产品页里抓下来的规格值、认证名、营销短语、话题标签。
# ---------------------------------------------------------------------------
NON_ENTITY_NAMES = {
    'IP55', 'IP55防护协议', '48V-300VDC', 'CE机械安全认证', 'TC591',
    '通讯协议全覆盖', '系列化标准协议',
    'AI芯片', '人形机器人', '机器人新技术', '辅助驾驶', 'AR眼镜', '消费电子',
}
# 纯规格值形态：IP68 / 24V / 48V-300VDC / M12 等
NON_ENTITY_PATTERN = re.compile(r'^(IP\d{2}|[\d.]+V(-[\d.]+V(DC|AC)?)?|M\d{1,2})$', re.I)

# 无意义的 standard 取值（不能作为溯源锚点）
JUNK_STANDARDS = {
    'Proprietary', 'Industry Standard', 'Exhibition Standard',
    'Regional Policy Standard', '未指定', '未明确',
}

VAGUE_VENDORS = {'未指定', '未明确', 'N/A', 'Unknown', ''}


def audit(e):
    """返回 (data_quality 标签, 是否隔离, 判定理由)"""
    name = str(e.get('name', '')).strip()
    vendor = str(e.get('manufacturer') or e.get('developer') or '').strip()

    if name in NON_ENTITY_NAMES or NON_ENTITY_PATTERN.match(name):
        return 'non_entity', True, '名称为规格值/认证名/话题标签，非零部件实体'

    if vendor in UNVERIFIABLE_VENDORS:
        return 'unverifiable_vendor', True, f'厂商「{vendor}」公开渠道无法溯源，疑似批量合成'

    if PLACEHOLDER_ID.search(str(e.get('id', ''))):
        return 'placeholder_id', True, '键盘序列占位 ID，未经正规入库流程'

    return 'ok', False, ''


QUARANTINE_REASON = {
    'non_entity': '名称为规格值/认证名/话题标签，非零部件实体',
    'unverifiable_vendor': '厂商公开渠道无法溯源，疑似批量合成',
    'placeholder_id': '键盘序列占位 ID，未经正规入库流程',
    'duplicate': '与库内另一条目为同一实物（同名同厂商），保留规范条目',
}


def main():
    dry = '--dry-run' in sys.argv
    doc = json.load(open(ENTITIES_PATH, encoding='utf-8'))
    entities = doc['entities']

    bycat = collections.defaultdict(collections.Counter)
    detail = []

    # --- 第一轮：规则 1~3（逐条独立判定） ---
    tags = {}
    for e in entities:
        tag, _quar, _why = audit(e)
        tags[e['id']] = tag
        # 幂等：先清掉上一轮可能写下的 duplicate_of，由第二轮重新决定
        e.pop('duplicate_of', None)

    # --- 第二轮：规则 4（需要全库视野，只在清洁集内部去重） ---
    dups = mark_duplicates(entities, tags)

    # --- 落标记 ---
    stat = collections.Counter()
    for e in entities:
        tag = tags[e['id']]
        quar = tag != 'ok'
        stat[tag] += 1
        if quar:
            bycat[e.get('category')][tag] += 1
            detail.append((e['id'], e.get('category'), tag, e.get('name'),
                           QUARANTINE_REASON.get(tag, '')))
        e['data_quality'] = tag
        e['quarantine'] = quar

    quar_n = sum(1 for e in entities if e.get('quarantine'))
    clean_n = len(entities) - quar_n

    if not dry:
        doc.setdefault('meta', {})
        doc['meta']['data_quality'] = {
            'audited_at': __import__('datetime').datetime.now(
                __import__('datetime').timezone.utc).strftime('%Y-%m-%d'),
            'total': len(entities),
            'clean': clean_n,
            'quarantined': quar_n,
            'quarantine_pct': round(quar_n * 100.0 / len(entities), 2),
            'breakdown': dict(stat),
            'policy': 'quarantine=true 的条目不删除，前端默认不进选型结果，仅在"显示未核验数据"时展示',
            'duplicate_policy': (
                '同名同厂商的重复登记只保留一条规范条目，其余标 data_quality=duplicate '
                '+ duplicate_of=<规范 id> 并隔离。清洁集内不再存在同物异 ID，'
                '故 clean 可作为「不重复可信条目数」使用。'
            ),
            'duplicates_resolved': [
                {'duplicate': d, 'canonical': c, 'name': k[0], 'manufacturer': k[1]}
                for d, c, k in dups
            ],
        }
        with open(ENTITIES_PATH, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write('\n')

    print('=== 数据质量审计 ===', '(dry-run)' if dry else '')
    print(f'  总实体      {len(entities)}')
    print(f'  干净        {clean_n} ({clean_n*100.0/len(entities):.2f}%)')
    print(f'  隔离        {quar_n} ({quar_n*100.0/len(entities):.2f}%)')
    for k, v in stat.most_common():
        if k != 'ok':
            print(f'    - {k:22s} {v}')
    print('  隔离条目按类目：')
    for c, cc in sorted(bycat.items(), key=lambda x: -sum(x[1].values())):
        print(f'    {c:20s} {sum(cc.values()):3d}  {dict(cc)}')
    if dups:
        print('  去重（保留规范条目，其余隔离）：')
        for d, c, k in dups:
            print(f'    {d:22s} -> {c:12s}  {k[0]} / {k[1]}')
    return detail


if __name__ == '__main__':
    main()
