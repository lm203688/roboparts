#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1.40 反向注入验证：确认「补写留痕」不是一条免检通道。

L1.40 引入 RECONCILED 是为了解决一个真实缺陷：主线/人工部署会生成一份
**没有任何飞轮轮次可以填写**的占位，而闸门要求它被填，于是唯一的变绿方式
是伪造一份第一人称的运行报告。承认"补写"这种收尾方式解开了死结，
但同时开了一扇门 —— 如果补写的门槛比第一人称还低，那所有报告都会变成补写，
留痕体系就名存实亡。

所以本文件的每一条注入，都是在问同一个问题：
**"能不能贴个 RECONCILED 标签就蒙混过去？"**

  ① 自己补自己（by = 被补写时段本身）—— 追责链闭环成死环
  ② 用未来轮次背书（by 晚于当前小时）—— 拿一个还没发生的运行当担保
  ③ 去掉免责声明 —— 读者会把重建当成亲历
  ④ 只引用捏造的哈希 —— 无据重建，等于换个壳的伪造
  ⑤ 补写标记与占位标记并存 —— 标了补写却没真写
  ⑥ 判据退回裸子串 —— 散文里提一句 RECONCILED 就免检（L1.32 首版同型缺陷）
  ⑦ deploy.mjs 退回"该轮运行异常中断" —— 误导本身正是伪造的起点

用法：python scripts/verify_l140_injections.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, 'scripts', 'regression.py')
DEPLOY = os.path.join(ROOT, 'scripts', 'deploy.mjs')
RES = os.path.join(ROOT, 'ops', 'results')
# 被补写的样本：03 轮（真实存在的补写报告）
SAMPLE = os.path.join(RES, 'roboparts-20260807-03.md')


def run_gate():
    """只跑 L1.40 段，返回 (是否全绿, 输出片段)。"""
    r = subprocess.run([sys.executable, REG], cwd=ROOT, capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    out = r.stdout or ''
    seg, on = [], False
    for line in out.splitlines():
        if '[L1.40]' in line:
            on = True
        elif on and re.match(r'^\[L[\d.]+\]|^\[L\d\]', line):
            break
        if on:
            seg.append(line)
    body = '\n'.join(seg)
    return ('❌' not in body), body


def failed_lines(body):
    return [l.strip() for l in body.splitlines() if '❌' in l]


class Patch:
    """临时改文件，退出时无条件还原（异常也还原，防止把仓库改坏）。"""

    def __init__(self, path, fn):
        self.path, self.fn = path, fn

    def __enter__(self):
        self.bak = tempfile.mktemp(suffix='.bak')
        shutil.copy2(self.path, self.bak)
        with open(self.path, encoding='utf-8') as f:
            src = f.read()
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write(self.fn(src))
        return self

    def __exit__(self, *a):
        shutil.copy2(self.bak, self.path)
        os.remove(self.bak)
        return False


CASES = [
    ('① 自己补自己（by = 被补写时段）', SAMPLE,
     lambda s: s.replace('RECONCILED by=20260807-08', 'RECONCILED by=20260807-03')),
    ('② 用未来轮次背书（by=20261231-23）', SAMPLE,
     lambda s: s.replace('RECONCILED by=20260807-08', 'RECONCILED by=20261231-23')),
    ('③ 去掉免责声明「据 git 痕迹重建」', SAMPLE,
     lambda s: s.replace('据 git 痕迹重建', '经核实确认')),
    ('④ 只引用捏造的哈希', SAMPLE,
     lambda s: re.sub(r'`[0-9a-f]{7,40}`', '`deadbee`', s)),
    ('⑤ 补写标记与占位标记并存', SAMPLE,
     lambda s: s.replace('<!-- ROBOPARTS-RUN-TRACE:RECONCILED by=20260807-08 -->',
                         '<!-- ROBOPARTS-RUN-TRACE:RECONCILED by=20260807-08 -->\n'
                         '<!-- ROBOPARTS-RUN-TRACE:AUTO-STUB -->')),
    ('⑥ 判据退回裸子串匹配', REG,
     lambda s: s.replace(
         "    _mk = 'RECON' + 'CILED'",
         "    _mk = 'RECON' + 'CILED'\n"
         "    _demo = 'RECONCILED' in txt if False else None")),
    ('⑦ deploy.mjs 退回"该轮运行异常中断"', DEPLOY,
     lambda s: s.replace('若本占位停留在过去的小时',
                         '若本占位长期未被替换，说明该轮运行异常中断；停留在过去的小时')),
]


def main():
    ok, body = run_gate()
    print('=== 基线（未注入）===')
    if not ok:
        print('⚠️ 基线本身就红，先修基线再跑注入：')
        for l in failed_lines(body):
            print('   ' + l)
        return 1
    print('✅ 基线全绿\n')

    caught = 0
    for name, path, fn in CASES:
        with Patch(path, fn):
            ok_i, body_i = run_gate()
        if ok_i:
            print(f'❌ {name} —— 闸门**没拦住**（这条注入等于免检通道，闸门失效）')
        else:
            caught += 1
            hit = failed_lines(body_i)
            print(f'✅ {name} —— 拦下：{hit[0] if hit else "(未取到具体行)"}')

    ok_after, body_after = run_gate()
    print()
    print(f'拦截 {caught}/{len(CASES)}；还原后基线：'
          + ('✅ 干净' if ok_after else '❌ 未还原干净！\n' + body_after))
    return 0 if (caught == len(CASES) and ok_after) else 1


if __name__ == '__main__':
    sys.exit(main())
