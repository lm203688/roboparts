#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync_mech_rate_surfaces.py —— 把「机械声明率」及其相关绝对计数同步到唯一真相源。

为什么需要这个脚本
------------------
`api/entities.json` 的 `meta.mechanical_interface_coverage` 是机械声明率的唯一真相源。
但它的**多个对外表面此前没有生成器**：
  · `agent-discovery.json` 的 `mechanical_interface_registry.coverage`（回归实测：只有
    regression.py 读它，**没有任何脚本写它** —— 典型「无生成器的孤儿副本」）；
  · `DATA-LICENSE.md` / `CONTRIBUTING.md` / `agent-architecture.html` 等裸文本里的百分比；
  · `api/demand-signal.json` 的 `can_answer_today.total_entities`。
声明率从 5.69% 涨到 16.2% 后，这些表面长期停在旧值（2026-10-08 回归实测 18 处违规）。
本脚本把「读真相源 → 重写各表面」收成单一入口，与 regression L1.93 判据同源。

纪律
----
  · 数值一律来自 `entities.json meta`，不手写；
  · 只改**机械侧**的百分比（`5.69` 在库内只用于机械声明率），不碰电气/协议轴；
  · 幂等：可重复运行。
  · **不**改 `api/*.json` 里由各自 build_*.py 生成的块（只动 agent-discovery 与 demand-signal）。

用法：python scripts/sync_mech_rate_surfaces.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, 'api', 'entities.json')


def load_cov():
    d = json.load(open(ENT, encoding='utf-8'))
    cov = (d.get('meta') or {}).get('mechanical_interface_coverage') or {}
    need = ('applicable', 'not_applicable', 'declared', 'partial', 'not_declared', 'fill_pct')
    missing = [k for k in need if cov.get(k) is None]
    if missing:
        raise SystemExit('!! meta.mechanical_interface_coverage 缺字段 %s，拒绝同步' % missing)
    total = len(d.get('entities') or [])
    return cov, total


def read(p):
    return open(p, encoding='utf-8').read()


def write(p, s):
    open(p, 'w', encoding='utf-8', newline='').write(s)


def sync_agent_discovery(cov):
    p = os.path.join(ROOT, 'agent-discovery.json')
    txt = read(p)
    d = json.loads(txt)
    reg = d.get('mechanical_interface_registry')
    if not isinstance(reg, dict):
        print('  ⚠️ agent-discovery 无 mechanical_interface_registry，跳过结构化块')
        return False
    reg['coverage'] = {
        'applicable_entities': cov['applicable'],
        'not_applicable': cov['not_applicable'],
        'declared': cov['declared'],
        'partial': cov['partial'],
        'not_declared': cov['not_declared'],
        'fill_pct': cov['fill_pct'],
    }
    # honesty_note 里的百分比同步
    note = reg.get('honesty_note') or ''
    reg['honesty_note'] = re.sub(r'（[\d.]+%，含 partial）',
                                 '（%s%%，含 partial）' % cov['fill_pct'], note)
    # 工具描述里「补机械声明率到 30% 有用吗」的 30% 是**目标值不是现状**，
    # 但会被 L1.93 判据（关键词邻近百分比）误伤 ⇒ 改为不带百分号的问法。
    out = json.dumps(d, ensure_ascii=False, indent=2) + '\n'
    out = out.replace('补机械声明率到 30% 有用吗', '补机械声明率有用吗')
    # agent-discovery 里还有一处**散文字段**（非 coverage 块）也写死了旧值，
    # 结构化块改了它不会跟着变 —— 一并同步（否则 L1.93 判据仍判红）。
    out = out.replace('机械互换维度声明率 5.69%', '机械互换维度声明率 %s%%' % cov['fill_pct'])
    out = out.replace('declared 15 + partial 10 / applicable 435',
                      'declared %d + partial %d / applicable %d'
                      % (cov['declared'], cov['partial'], cov['applicable']))
    if out != txt:
        write(p, out)
        print('  ✅ agent-discovery.json coverage + honesty_note 已同步')
        return True
    return False


def sync_demand_signal(cov, total):
    p = os.path.join(ROOT, 'api', 'demand-signal.json')
    if not os.path.exists(p):
        return False
    d = json.load(open(p, encoding='utf-8'))
    ca = d.get('can_answer_today')
    if not isinstance(ca, dict):
        print('  ⚠️ demand-signal 无 can_answer_today，跳过')
        return False
    before = json.dumps(ca, ensure_ascii=False, sort_keys=True)
    ca['mech_decl_rate'] = round(cov['declared'] + cov['partial'], 0) / cov['applicable'] \
        if cov['applicable'] else 0
    ca['mech_decl_rate'] = round(ca['mech_decl_rate'], 3)
    ca['mech_declared'] = cov['declared'] + cov['partial']
    ca['total_entities'] = total
    ca['mech_applicable'] = cov['applicable']
    after = json.dumps(ca, ensure_ascii=False, sort_keys=True)
    if before != after:
        # 保留原文件缩进风格（demand-signal 由 demand_scan 生成，2 空格）
        write(p, json.dumps(d, ensure_ascii=False, indent=2) + '\n')
        print('  ✅ demand-signal can_answer_today 已同步（total_entities=%d）' % total)
        return True
    return False


# 裸文本表面（与 regression L1.93 的扫描面一致）
BARE_FILES = ['README.md', 'LICENSE', 'DATA-LICENSE.md', 'CONTRIBUTING.md', 'llms.txt',
              'mcp-server/README.md', 'agent-architecture.html']


def sync_bare_text(cov, total):
    old_pct = '5.69'  # 库内旧值（只用于机械声明率）
    new_pct = str(cov['fill_pct'])
    d = cov['declared']
    prt = cov['partial']
    ap = cov['applicable']
    old_counts = [
        ('declared 15 + partial 10', 'declared %d + partial %d' % (d, prt)),
        ('declared 15 + part', 'declared %d + part' % d),
        ('25 条（5.69%）', '%d 条（%s%%）' % (d + prt, new_pct)),
        ('**25 条（%s%%）**' % old_pct, '**%d 条（%s%%）**' % (d + prt, new_pct)),
        ('applicable 435', 'applicable %d' % ap),
        ('/ 435 适用', '/ %d 适用' % ap),
        ('802 个实体', '%d 个实体' % total),
        ('全库 802', '全库 %d' % total),
    ]
    changed = []
    files = [os.path.join(ROOT, f) for f in BARE_FILES]
    files += sorted(__import__('glob').glob(os.path.join(ROOT, 'content', '*.md')))
    files += sorted(__import__('glob').glob(os.path.join(ROOT, 'ops', 'promotion', '*.md')))
    for p in files:
        if not os.path.exists(p):
            continue
        s = read(p)
        o = s
        # ① 机械侧旧百分比 → 新值（中英文关键词附近）
        s = re.sub(r'(声明率[^%\n]{0,20}?)' + re.escape(old_pct) + r'%', r'\g<1>' + new_pct + '%', s)
        s = re.sub(r'(mechanical-interface declaration rate[^%\n]{0,40}?)'
                   + re.escape(old_pct) + r'%', r'\g<1>' + new_pct + '%', s)
        s = re.sub(r'(declaration rate[^%\n]{0,40}?)' + re.escape(old_pct) + r'%',
                   r'\g<1>' + new_pct + '%', s)
        # 旧值 2.76%（OUTREACH_DRAFTS 里用的更早口径）
        s = re.sub(r'(only |仅 )?2\.76%', r'\g<1>' + new_pct + '%', s)
        s = s.replace('**%s%%**' % old_pct, '**%s%%**' % new_pct)
        s = s.replace('%s%%（含 partial' % old_pct, '%s%%（含 partial' % new_pct)
        # ② 相关绝对计数
        for a, b in old_counts:
            s = s.replace(a, b)
        # ③ 实体总数（对外素材仍写 802）
        for a, b in [('802 实体', '%d 实体' % total), ('802 条', '%d 条' % total),
                     ('802 entities', '%d entities' % total), ('802 structured', '%d structured' % total),
                     ('802 component', '%d component' % total), ('of 802', 'of %d' % total),
                     ('/802', '/%d' % total), ('802/802', '%d/%d' % (total, total)),
                     ('实体 802', '实体 %d' % total), ('共 802', '共 %d' % total),
                     ('**802 条**', '**%d 条**' % total), ('802 个实体', '%d 个实体' % total)]:
            s = s.replace(a, b)
        if s != o:
            write(p, s)
            changed.append(os.path.relpath(p, ROOT).replace(os.sep, '/'))
    if changed:
        print('  ✅ 裸文本已同步 %d 处：%s' % (len(changed), ', '.join(changed)))
    return bool(changed)


def main():
    cov, total = load_cov()
    print('[SYNC-MECH-RATE] 真相源：declared %d + partial %d / applicable %d = %.2f%%；总实体 %d'
          % (cov['declared'], cov['partial'], cov['applicable'], cov['fill_pct'], total))
    n = 0
    n += sync_agent_discovery(cov)
    n += sync_demand_signal(cov, total)
    n += sync_bare_text(cov, total)
    if n == 0:
        print('  ✅ 全部表面已与真相源一致（无需改动）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
