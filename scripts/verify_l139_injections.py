#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1.39 反向注入验证：破坏「证据成分可见」，确认闸门真的会红。

闸门全绿本身不证明任何事 —— 一条永远返回 True 的断言也是全绿。
所以每加一条闸门，都要反过来把它该防的东西真造出来，看它是不是真拦得住。

本文件测两侧：
  A. **代码侧**（①–⑤）：把 oss.js 的成分输出拆掉／折叠回去。
  B. **数据侧**（⑥）：把 06:00 轮那个摄取器的真实产物灌进 oss_components.json，
     确认闸门会因「类目 unknown」和「可判定率跌破 70%」而红。
     ⑥ 才是这条闸门的存在理由 —— 前五条只保证仪表盘还在，
     ⑥ 保证仪表盘真的会在稀释发生时报警。

用法：python scripts/verify_l139_injections.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OSS_JS = os.path.join(ROOT, 'functions', 'api', 'oss.js')
OSS_JSON = os.path.join(ROOT, 'api', 'oss_components.json')
REG = os.path.join(ROOT, 'scripts', 'regression.py')


def run_gate():
    """只跑 L1.39，返回 (是否全绿, 输出片段)。"""
    r = subprocess.run([sys.executable, REG], cwd=ROOT,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = r.stdout or ''
    seg, on = [], False
    for line in out.splitlines():
        if '[L1.39]' in line:
            on = True
        elif on and re.match(r'^\[L[\d.]+\]|^\[L\d\]', line):
            break
        if on:
            seg.append(line)
    body = '\n'.join(seg)
    return ('❌' not in body), body


def failed_lines(body):
    return [l.strip() for l in body.splitlines() if '❌' in l]


def main():
    ok, body = run_gate()
    if not ok:
        print('基线就不是全绿，先修好再跑注入：')
        print(body)
        return 1
    print('基线：L1.39 全绿 ✅\n')

    orig_js = open(OSS_JS, encoding='utf-8').read()
    orig_json = open(OSS_JSON, encoding='utf-8').read()
    passed = 0
    total = 0

    # ---------------- A. 代码侧 ----------------
    code_cases = [
        ('①删掉 by_confidence（成分不再可见，回到只给一个总数）',
         lambda s: s.replace('by_confidence: byConfidence,', '')),
        ('②删掉 decidable_entities（不再回答「多少行能用来判断」）',
         lambda s: s.replace('decidable_entities: decidable,', '')),
        ("③把未评级折叠成 high（「没评过级」被说成「评过是高」）",
         lambda s: s.replace("e.confidence || 'unrated'", "e.confidence || 'high'")),
        ('④decidable 直接等于总行数（指标退化成恒等式，永远好看）',
         lambda s: re.sub(r'if \(Array\.isArray\(e\.compatibility\)[^\n]*decidable\+\+;',
                          'decidable++;', s)),
        ('⑤只在注释里提及成分，代码里全拆掉（防判据被注释喂饱）',
         lambda s: s.replace('by_source_tier: byTier,', '')
                    .replace('by_confidence: byConfidence,', '')
                    .replace('decidable_entities: decidable,', '')
                    + '\n// by_confidence by_source_tier decidable_entities\n'),
    ]

    for name, mutate in code_cases:
        total += 1
        mutated = mutate(orig_js)
        if mutated == orig_js:
            print(f'{name} -> ⚠️ 注入没改到任何东西（用例本身失效，需修正）')
            open(OSS_JS, 'w', encoding='utf-8').write(orig_js)
            continue
        open(OSS_JS, 'w', encoding='utf-8').write(mutated)
        try:
            ok2, body2 = run_gate()
        finally:
            open(OSS_JS, 'w', encoding='utf-8').write(orig_js)
        if ok2:
            print(f'{name} -> ❌ 未被拦下（闸门是摆设）')
        else:
            passed += 1
            print(f'{name} -> ✅ 被拦下')

    # ---------------- B. 数据侧（这条才是重点） ----------------
    total += 1
    print('\n⑥ 数据侧：把 URDF <link> 摄取器的真实产物灌进目录')
    tmpdir = tempfile.mkdtemp(prefix='rp-l139-')
    try:
        # 用摄取器**自己**的 dry-run 产物，而不是我手捏的假数据 ——
        # 手捏数据只能证明「如果脏数据长这样就会红」，
        # 用真产物才能证明「那个脚本现在真的跑就会红」。
        r = subprocess.run(
            ['node', os.path.join('scripts', 'ingest_oss_bom.mjs'), '--dry-run', '--source', 'sample'],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace')
        sample_ok = '示例条目' in (r.stdout or '')
        if not sample_ok:
            print('   ⚠️ 摄取器 dry-run 未产出示例，跳过数据侧注入')
        else:
            doc = json.loads(orig_json)
            # 复制真实形态：category=unknown、compatibility 空、规格全 N/A。
            stub = {
                'id': 'OSS-BOM-INJECT-%04d', 'name': 'INJECT 连杆', 'category': 'unknown',
                'manufacturer': 'x', 'type': 'urdf_link', 'protocol': 'N/A',
                'interface': 'N/A', 'voltage': 'N/A', 'compatibility': [],
                'extractor': 'urdf_link', 'source_tier': 'C', 'confidence': 'low',
                'declared': False,
            }
            for i in range(98):
                row = dict(stub)
                row['id'] = stub['id'] % i
                doc['data'].append(row)
            doc['meta']['total_entities'] = len(doc['data'])
            open(OSS_JSON, 'w', encoding='utf-8').write(json.dumps(doc, ensure_ascii=False, indent=2))
            ok3, body3 = run_gate()
            if ok3:
                print('   -> ❌ 未被拦下：98 行无兼容维度的线索行灌进目录，闸门竟然全绿')
            else:
                fl = failed_lines(body3)
                print('   -> ✅ 被拦下，红的是：')
                for l in fl:
                    print('      ' + l)
                # 必须是**这两条**红，而不是碰巧因别的原因红。
                hit_unknown = any('unknown' in l for l in fl)
                hit_ratio = any('可判定率' in l for l in fl)
                if hit_unknown and hit_ratio:
                    passed += 1
                else:
                    print('   ⚠️ 红的原因不对：期望「类目 unknown」+「可判定率」两条同时红')
    finally:
        open(OSS_JSON, 'w', encoding='utf-8').write(orig_json)
        shutil.rmtree(tmpdir, ignore_errors=True)

    # 还原后复验，确认没把仓库改脏。
    ok4, _ = run_gate()
    print('\n还原后复验：', '干净 ✅' if ok4 else '❌ 仓库被改脏了，请检查')
    print(f'\n结论：{passed}/{total} 全部拦下' if passed == total
          else f'\n结论：{passed}/{total} 被拦下，存在漏网')
    return 0 if (passed == total and ok4) else 1


if __name__ == '__main__':
    sys.exit(main())
