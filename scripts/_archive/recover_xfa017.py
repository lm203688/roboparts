#!/usr/bin/env python3
"""
recover_xfa017.py — 把 XFA-017（UNIST Magnetic Composite Artificial Muscle）恢复到
api/entities.json 真相源。

来源：git 11af550:api/flexible_actuators.json（历史 23 条实体中的 XFA-017，24 字段）。
对齐当前 flexible_actuator 兄弟 schema（27 字段）：补齐 rp_id / entity_kind_basis /
source_tier_prev / tier_cap_reason。

幂等：若 entities.json 已含 XFA-017 则跳过。只改工作区，不 commit / 不 push。
写完真相源后须跑 `python scripts/normalize_categories.py` 重生成派生文件。
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT = os.path.join(ROOT, 'api', 'entities.json')


def git_show(path):
    return subprocess.check_output(['git', 'show', '11af550:' + path], cwd=ROOT, text=True)


def main():
    raw = git_show('api/flexible_actuators.json')
    d = json.loads(raw)
    arr = d.get('data') or d.get('entities') or d
    xfa = [e for e in arr if str(e.get('id', '')).upper() == 'XFA-017']
    if not xfa:
        print('!! 在 git 11af550 中未找到 XFA-017')
        sys.exit(1)
    e = dict(xfa[0])

    # 对齐当前 flexible_actuator 兄弟 schema（XFA-001..016 均为 27 字段）
    if 'rp_id' not in e:
        e['rp_id'] = 'RP-FLE-0022'
    if 'entity_kind_basis' not in e:
        e['entity_kind_basis'] = '默认归类'
    if 'source_tier_prev' not in e:
        e['source_tier_prev'] = e.get('source_tier', 'B')
    if 'tier_cap_reason' not in e:
        e['tier_cap_reason'] = (
            '来源为同行评审期刊（Advanced Functional Materials）报道的 UNIST 研究原型，'
            '非厂商量产规格页；按 source_tier_basis=peer_reviewed_journal 归 B。'
            '研究原型阶段无标准化机械接口，mechanical_interface 保持 not_declared。'
        )

    with open(ENT, encoding='utf-8') as f:
        doc = json.load(f)
    ents = doc['entities']
    if any(str(x.get('id', '')).upper() == 'XFA-017' for x in ents):
        print('entities.json 已含 XFA-017，跳过')
        return

    ents.append(e)
    with open(ENT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('✔ XFA-017 已追加到 entities.json (rp_id=%s, total=%d)' % (e['rp_id'], len(ents)))


if __name__ == '__main__':
    main()
