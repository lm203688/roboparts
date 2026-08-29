# -*- coding: utf-8 -*-
"""L1.37 反向注入验证：把缺陷重新种回去，闸门必须变红。

闸门写出来是绿的不算数——绿也可能是"根本没在看"。这里逐个把已修的缺陷
注入回 list.js，跑一遍 L1.37，要求每一项都被抓出来；跑完自动还原文件。
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, 'functions', 'api', 'suppliers', 'list.js')
PY = sys.executable

# (名称, 替换前, 替换后, 期望红的断言关键词)
CASES = [
    ('①退回 pending 也公开（原缺陷精确重现）',
     "if (supplier.review_status === 'approved') {",
     "if (supplier.review_status !== 'rejected') {",
     'approved 白名单'),
    ('②白名单口径被改成子串可蒙混的形式',
     "supplier.review_status === 'approved'",
     "supplier.review_status === 'approved_or_pending'",
     'approved 白名单'),
    ('③公开投影里泄露联系邮箱',
     '        has_contact:',
     '        contact_email: s.contact_email || \'\',\n        has_contact:',
     '联系方式'),
]


def run_gate():
    p = subprocess.run([PY, os.path.join(ROOT, 'scripts', 'regression.py')],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = p.stdout or ''
    seg = out[out.find('[L1.37]'):]
    seg = seg[:seg.find('[L2]')] if '[L2]' in seg else seg
    return seg


def main():
    backup = TARGET + '.l137bak'
    shutil.copy2(TARGET, backup)
    orig = open(TARGET, encoding='utf-8').read()
    ok = True
    try:
        base = run_gate()
        if '❌' in base:
            print('基线就不干净，先修基线：\n' + base)
            return 1
        print('基线：L1.37 全绿 ✅\n')

        for name, old, new, kw in CASES:
            if old not in orig:
                print('%s -> ⚠️ 注入锚点未命中，用例失效（锚点: %r）' % (name, old[:40]))
                ok = False
                continue
            open(TARGET, 'w', encoding='utf-8').write(orig.replace(old, new, 1))
            seg = run_gate()
            caught = any('❌' in ln and kw in ln for ln in seg.splitlines())
            print('%s -> %s' % (name, '✅ 被拦下' if caught else '❌ 漏过（闸门失效）'))
            if not caught:
                ok = False
                print(seg)
            open(TARGET, 'w', encoding='utf-8').write(orig)
    finally:
        shutil.copy2(backup, TARGET)
        os.remove(backup)

    print('\n还原后复验：', '干净 ✅' if '❌' not in run_gate() else '仍有红 ❌')
    print('\n结论：', '3/3 全部拦下，闸门有效' if ok else '存在漏过，闸门需加强')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
