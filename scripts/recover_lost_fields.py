#!/usr/bin/env python3
"""
恢复「写错层」造成的派生层与真相源分叉（真相源缺失或落后）

背景
----
20260826-06 那轮「竞品借鉴点落地」把 PROTO-010 (OPC UA) 的改动只写进了派生文件
`api/protocols.json`，而 `scripts/normalize_categories.py` 是
`entities.json`（单一真相源）→ 重生成 `api/<category>.json` 的**单向覆盖**。

本轮实测（非推测）
------------------
- `git grep -l robot_brand_support HEAD --` 命中 0 ⇒ 当前 HEAD 全树无该字段。
- `git log --all -S"robot_brand_support"` 命中 515e6b2 / 5bcd7c7，但那些 commit 的
  `api/entities.json` 里 PROTO-010 依然没有该字段 ⇒ 确证"写错层"，不是"没做过"。
- 本轮为恢复 XFA-017 执行过 `git checkout -- api/` + 归一化，派生层被真相源重生成
  ⇒ 这两处改动在**工作区**已消失，只剩 git 历史这一份拷贝。

两类分叉、两种处置（不混为一谈）
--------------------------------
1. `robot_brand_support`：**真相源从来没有**。属字段级永久丢失，从 git 逐字回填。
2. `applications`：真相源有旧值（3 项），派生层是它的**超集**（6 项）。
   真相源领先派生层是正常演进；派生层反过来领先真相源，说明那次扩写从未回流。
   仅当"真相源是派生层的真子集"时才把超集回流——否则视为**真实分叉**，只告警不覆盖。

不做的事
--------
- 不改 `normalize_categories.py` 的单向语义（单向覆盖是刻意设计）。
- 不回填任何推测内容：字段值一律逐字取自 git 历史，不改写、不扩写。
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES = os.path.join(ROOT, 'api', 'entities.json')

# 换 commit 前须先核对：该 commit 的 entities.json 里 PROTO-010 的这两处字段
# 确实缺失/落后（否则等于用旧值覆盖新值）。
SRC_COMMIT = '5bcd7c7'
TARGET_ID = 'PROTO-010'
FIELDS = ('robot_brand_support', 'applications')


def git_show(path):
    raw = subprocess.run(
        ['git', '-C', ROOT, 'show', path],
        capture_output=True, text=True, encoding='utf-8', errors='replace')
    if raw.returncode != 0:
        raise SystemExit('!! 无法读取 %s（%s）' % (path, raw.stderr.strip()))
    return raw.stdout


def read_derived(commit, category):
    """读指定 commit 的派生文件实体列表（兼容 data/entities/items 三种键）。"""
    doc = json.loads(git_show('%s:api/%s.json' % (commit, category)))
    return doc.get('data') or doc.get('entities') or doc.get('items') or []


def main():
    ents_doc = json.load(open(ENTITIES, encoding='utf-8'))
    ents = ents_doc['entities']

    src = {e['id']: e for e in read_derived(SRC_COMMIT, 'protocols') if e.get('id')}
    tgt_list = [e for e in ents if e.get('id') == TARGET_ID]
    if not tgt_list:
        raise SystemExit('!! 真相源缺 %s，无法回填' % TARGET_ID)
    if TARGET_ID not in src:
        raise SystemExit('!! %s 的派生层也缺 %s，恢复前提不成立' % (SRC_COMMIT, TARGET_ID))

    # 分叉前提核对：该 commit 的真相源必须确实缺失或落后
    truth_at_src = json.loads(git_show('%s:api/entities.json' % SRC_COMMIT))
    truth_ent = [e for e in truth_at_src['entities'] if e.get('id') == TARGET_ID][0]
    for f in FIELDS:
        if f in truth_ent and truth_ent[f] == src[TARGET_ID].get(f):
            raise SystemExit('!! %s 的 entities.json 中 %s 已与派生层一致，'
                             '本脚本前提不成立，停止' % (SRC_COMMIT, f))

    src_ent, tgt_ent = src[TARGET_ID], tgt_list[0]
    recovered, adopted, skipped = [], [], []

    for f in FIELDS:
        cur = tgt_ent.get(f)
        nxt = src_ent.get(f)
        if nxt is None:
            print('  跳过 %s：%s 里也没有' % (f, SRC_COMMIT))
            skipped.append(f)
            continue
        if cur == nxt:
            print('  %s 已一致，跳过' % f)
            continue
        if cur is None:
            tgt_ent[f] = nxt
            recovered.append(f)
            print('  回填 %s ← %s:api/protocols.json（真相源原先缺失）' % (f, SRC_COMMIT))
        elif isinstance(cur, list) and isinstance(nxt, list) and all(x in nxt for x in cur):
            tgt_ent[f] = nxt
            adopted.append(f)
            print('  超集回流 %s：%s 项 → %s 项（真相源为真子集）'
                  % (f, len(cur), len(nxt)))
        else:
            print('  ⚠️ 跳过 %s：真相源与派生层真实分叉，不覆盖（真相源=%s）'
                  % (f, json.dumps(cur, ensure_ascii=False)[:120]))
            skipped.append(f)

    if recovered or adopted:
        meta = ents_doc['meta']
        meta['lost_layer_recoveries'] = meta.get('lost_layer_recoveries', [])
        meta['lost_layer_recoveries'].append({
            'id': TARGET_ID,
            'fields_absent_in_truth': recovered,
            'fields_superset_adopted': adopted,
            'source_commit': SRC_COMMIT,
            'source_path': 'api/protocols.json',
            'recovered_at': '2026-08-29',
            'note': ('字段原先只写在派生层、真相源从未获得或已落后；'
                     '本轮从 git 历史逐字回填至真相源，未改写任何取值')
        })
        for e in ents:
            if e.get('id') == TARGET_ID:
                e['lost_layer_recovery'] = {
                    'fields': recovered + adopted,
                    'source_commit': SRC_COMMIT,
                    'source_path': 'api/protocols.json'
                }
        with open(ENTITIES, 'w', encoding='utf-8') as fp:
            json.dump(ents_doc, fp, ensure_ascii=False, indent=2)
            fp.write('\n')
        print('\n[OK] 真相源已回填 %s / 超集回流 %s' % (recovered or '无', adopted or '无'))
        print('     下一步：python scripts/normalize_categories.py（广播到派生层）')
    else:
        print('\n[OK] 无需改动（字段已在真相源中，幂等）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
