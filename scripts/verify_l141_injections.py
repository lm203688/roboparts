#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1.41 反向注入验证：把「未知参数静默吞掉」重新造出来，确认闸门真的会红。

最要紧的是 ①：它**逐字重现本轮修掉的原缺陷** —— 删掉未知参数校验，
`{"query":"harmonic reducer"}` 立刻退回"返回全库 685 条"的行为。
闸门若拦不住 ①，等于这条闸门从来没存在过。

其余各条针对的是"看起来修了、其实没修"的各种半吊子写法：
  ② 只警告不拦截（记了个 invalid_params 就继续跑）—— 调用方照样收到全库结果
  ③ 白名单改成硬编码数组 —— 与 schema 分家，加参数时必然漂移
  ④ 去掉 did_you_mean —— 只告诉对方"错了"却不说该用什么，等于把人挡在门外
  ⑤ 拒绝时顺带把数据一起返回 —— 报错与数据并存，调用方多半只看数据

用法：python scripts/verify_l141_injections.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, 'scripts', 'regression.py')
MCP = os.path.join(ROOT, 'functions', 'mcp.js')

# 本轮加入的整段校验（用于 ① 整体摘除）
BLOCK_HEAD = '        const allowed = Object.keys(toolSpec.inputSchema?.properties || {});'


def run_gate():
    r = subprocess.run([sys.executable, REG], cwd=ROOT, capture_output=True,
                       text=True, encoding='utf-8', errors='replace')
    out = r.stdout or ''
    seg, on = [], False
    for line in out.splitlines():
        if '[L1.41]' in line:
            on = True
        elif on and re.match(r'^\[L[\d.]+\]|^\[L\d\]', line):
            break
        if on:
            seg.append(line)
    body = '\n'.join(seg)
    return ('❌' not in body), body


def failed_lines(body):
    return [l.strip() for l in body.splitlines() if '❌' in l]


def drop_block(src):
    """① 整段摘除未知参数校验 —— 精确回到修复前的行为。"""
    i = src.find(BLOCK_HEAD)
    if i == -1:
        raise SystemExit('注入① 定位失败：未找到校验块起始行，脚本需随代码更新')
    j = src.find('\n      }\n\n      let payload;', i)
    if j == -1:
        raise SystemExit('注入① 定位失败：未找到校验块结束位置')
    return src[:i] + src[j + 1:]


class Patch:
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
    ('① 摘除整段校验（精确重现原缺陷：query 被吞、返回全库）', MCP, drop_block),
    ('② 只警告不拦截（记 invalid_params 后继续执行）', MCP,
     lambda s: s.replace(
         '          return rpcError(id, -32602, `未知参数: ${unknownArgs.join(\', \')}（工具 ${name}）`, {',
         '          const _ignored = ({')),
    ('③ 白名单改为硬编码数组（与 schema 分家）', MCP,
     lambda s: s.replace(
         'Object.keys(toolSpec.inputSchema?.properties || {})',
         "['category', 'keyword', 'limit', 'include_market_intelligence']")),
    ('④ 去掉 did_you_mean（只说错了，不说该用什么）', MCP,
     lambda s: s.replace('did_you_mean:', 'unused_hint_field:')),
    ('⑤ 拒绝时顺带返回全库数据', MCP,
     lambda s: s.replace(
         '            accepted_parameters: allowed,',
         '            accepted_parameters: allowed,\n'
         '            total_matched: 685,\n'
         '            leaked_first_id: \'ACT-001\',')),
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
