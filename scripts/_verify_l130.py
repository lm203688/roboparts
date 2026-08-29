#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1.30 反向注入验证：把缺陷逐个改回去，确认闸门确实变红（而不是摆设）。

每个注入 -> 跑一次 regression -> 断言 L1.30 出现 ❌ -> 还原。
任一注入未被拦下即视为闸门无效。
"""
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
FILES = ['scripts/ingest_oss.mjs', 'api/oss_components.json',
         'oss.html', 'bom-checker.html']


def backup():
    for f in FILES:
        shutil.copy2(os.path.join(ROOT, f), os.path.join(ROOT, f + '.l130bak'))


def restore():
    for f in FILES:
        b = os.path.join(ROOT, f + '.l130bak')
        if os.path.isfile(b):
            shutil.move(b, os.path.join(ROOT, f))


def run_gate():
    """返回 L1.30 段落里 ❌ 的条数。"""
    r = subprocess.run([PY, os.path.join(ROOT, 'scripts', 'regression.py')],
                       capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
    out = (r.stdout or '')
    seg = out.split('[L1.30]')
    if len(seg) < 2:
        return -1
    body = seg[1].split('\n[L')[0]
    return body.count('❌')


def edit(rel, old, new):
    p = os.path.join(ROOT, rel)
    with open(p, encoding='utf-8') as f:
        t = f.read()
    assert old in t, f'注入锚点未找到: {rel} :: {old[:50]}'
    with open(p, 'w', encoding='utf-8') as f:
        f.write(t.replace(old, new, 1))


INJECTIONS = []


def inj(name):
    def deco(fn):
        INJECTIONS.append((name, fn))
        return fn
    return deco


@inj('源码-1: extractUrdf 改回硬编码 ros_support: true')
def _i1():
    edit('scripts/ingest_oss.mjs',
         'ros_support: undefined,\n      ros_ecosystem_origin: true,',
         'ros_support: true,\n      ros_ecosystem_origin: true,')


@inj('源码-2: extractBomMd 改回硬编码 ros_support: false')
def _i2():
    edit('scripts/ingest_oss.mjs',
         "ros_support: undefined, compatibility: [], standard: partNo || '',",
         "ros_support: false, compatibility: [], standard: partNo || '',")


@inj('源码-3: extractReadme 改回按名字猜 /ros/i.test(name)')
def _i3():
    edit('scripts/ingest_oss.mjs',
         "ros_support: undefined, compatibility: [], standard: '',",
         "ros_support: /ros/i.test(name), compatibility: [], standard: '',")


@inj('源码-4: makeEntity 改回 === true 压平')
def _i4():
    edit('scripts/ingest_oss.mjs',
         "ros_support: typeof base.ros_support === 'boolean' ? base.ros_support : undefined,",
         'ros_support: base.ros_support === true,')


@inj('数据-5: 把 urdf 125 条重新写回全 true（与抽取器共变）')
def _i5():
    p = os.path.join(ROOT, 'api', 'oss_components.json')
    d = json.load(open(p, encoding='utf-8'))
    for e in d['data']:
        if e.get('extractor') == 'urdf':
            e['ros_support'] = True
    json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


@inj('数据-6: 把字段整个删光冒充合规（应被防假绿断言拦下）')
def _i6():
    p = os.path.join(ROOT, 'api', 'oss_components.json')
    d = json.load(open(p, encoding='utf-8'))
    for e in d['data']:
        e.pop('ros_support', None)
    json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


@inj('消费端-7: oss.html 改回 truthy 折叠')
def _i7():
    edit('oss.html', '<td>${rosCell(e)}</td>',
         "<td>${e.ros_support?'\u2713':'\u2013'}</td>")


@inj('消费端-8: bom-checker.html 改回 !! 压平')
def _i8():
    edit('bom-checker.html',
         "...(r.ros==='yes' ? {ros_support:true} : r.ros==='no' ? {ros_support:false} : {})",
         'ros_support:!!r.ros')


def main():
    base = run_gate()
    print(f'基线（未注入）L1.30 失败数 = {base}')
    if base != 0:
        print('基线就不是绿的，无法验证'); sys.exit(1)

    all_ok = True
    for name, fn in INJECTIONS:
        backup()
        try:
            fn()
            n = run_gate()
            caught = n > 0
            print(f'  [{"拦下" if caught else "漏过"}] {name}  -> ❌{n} 项')
            if not caught:
                all_ok = False
        finally:
            restore()

    after = run_gate()
    print(f'还原后 L1.30 失败数 = {after}')
    if after != 0:
        print('还原不干净！'); sys.exit(1)
    print('\n结论：' + ('全部注入均被拦下，闸门有效' if all_ok else '存在漏过项，闸门无效'))
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
