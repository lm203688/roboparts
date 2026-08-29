#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1.42 反向注入验证：把「飞轮把自己的 curl 读成市场需求」重新造出来，确认闸门会红。

① 精确重现本轮修掉的原缺陷：real_lo 退回 `src_all - src_probe`。
   那一步就是全部问题所在 —— toolsrc:script（飞轮自身验证 curl）不是 probe，
   于是被当成真实需求，打印出"真实需求 7 次"。
② 把 'script' 从 AMBIGUOUS_KINDS 里摘掉 —— 集合还在、判据形似，但漏掉的正是自己。
③ 把 'empty-ua' 摘掉 —— 无 UA 同样不构成真实用户证据，漏一个就留一条后门。
④ 退回"已全部归因"措辞 —— L1.26 记过一次的错：把不可归因说成已归因。
⑤ 删掉读数旁边的警告语 —— 数字对了但不利事实被搬走，下游只会看到区间上界。
⑥ src_named 只扣 probe 不扣 ambiguous —— 等价于 ①，但改在另一处，防单点判据。

用法：python scripts/verify_l142_injections.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, 'scripts', 'regression.py')
RM = os.path.join(ROOT, 'scripts', 'read_metrics.py')


def run_gate():
    r = subprocess.run([sys.executable, REG], cwd=ROOT, capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    out = r.stdout or ''
    seg, on = [], False
    for line in out.splitlines():
        if '[L1.42]' in line:
            on = True
        elif on and re.match(r'^\[L[\d.]+\]|^\[L\d\]', line):
            break
        if on:
            seg.append(line)
    return ('❌' not in '\n'.join(seg)), '\n'.join(seg)


def failed_lines(body):
    return [l.strip() for l in body.splitlines() if '❌' in l]


class Patch:
    def __init__(self, path, fn):
        self.path, self.fn = path, fn

    def __enter__(self):
        self.bak = tempfile.mktemp(suffix='.bak')
        shutil.copy2(self.path, self.bak)
        with open(self.path, encoding='utf-8') as f:
            src = f.read()
        new = self.fn(src)
        if new == src:
            shutil.copy2(self.bak, self.path)
            os.remove(self.bak)
            raise SystemExit(f'注入定位失败（源码未变化）：{self.path}，脚本需随代码更新')
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write(new)
        return self

    def __exit__(self, *a):
        shutil.copy2(self.bak, self.path)
        os.remove(self.bak)
        return False


CASES = [
    ('① 精确重现原缺陷：real_lo 退回 src_all - src_probe', RM,
     lambda s: s.replace('    real_lo = src_named',
                         '    real_lo = max(src_all - src_probe, 0)')),
    ("② 把 'script' 从 AMBIGUOUS_KINDS 摘掉（漏掉的正是飞轮自己）", RM,
     lambda s: s.replace("AMBIGUOUS_KINDS = {'script', 'empty-ua', 'unknown', 'bot'}",
                         "AMBIGUOUS_KINDS = {'empty-ua', 'unknown', 'bot'}")),
    ("③ 把 'empty-ua' 摘掉（无 UA 也不构成真实用户证据）", RM,
     lambda s: s.replace("AMBIGUOUS_KINDS = {'script', 'empty-ua', 'unknown', 'bot'}",
                         "AMBIGUOUS_KINDS = {'script', 'unknown', 'bot'}")),
    ('④ 退回"已全部归因"措辞（L1.26 记过的同一个错）', RM,
     lambda s: s.replace("        print(f'  真实需求区间 [{real_lo}, {real_hi}]'",
                         "        print(f'  已全部归因 [{real_lo}, {real_hi}]'")),
    ('⑤ 删掉读数旁边的自检警告（数字对了但不利事实被搬走）', RM,
     lambda s: s.replace('script/空UA 类调用**包含飞轮自身的线上验证 curl**，',
                         'script 类调用来源多样，')),
    ('⑥ src_named 只扣 probe 不扣 ambiguous（改在另一处的等价缺陷）', RM,
     lambda s: s.replace('src_named = max(src_all - src_probe - src_ambig, 0)',
                         'src_named = max(src_all - src_probe, 0)')),
]


def main():
    ok, body = run_gate()
    print('=== 基线（未注入）===')
    if not ok:
        print('⚠️ 基线本身就红：')
        for l in failed_lines(body):
            print('   ' + l)
        return 1
    print('✅ 基线全绿\n')

    caught = 0
    for name, path, fn in CASES:
        with Patch(path, fn):
            ok_i, body_i = run_gate()
        if ok_i:
            print(f'❌ {name} —— 闸门**没拦住**')
        else:
            caught += 1
            hit = failed_lines(body_i)
            print(f'✅ {name} —— 拦下：{hit[0][:110] if hit else "(未取到具体行)"}')

    ok_after, body_after = run_gate()
    print()
    print(f'拦截 {caught}/{len(CASES)}；还原后基线：'
          + ('✅ 干净' if ok_after else '❌ 未还原干净！\n' + body_after))
    return 0 if (caught == len(CASES) and ok_after) else 1


if __name__ == '__main__':
    sys.exit(main())
