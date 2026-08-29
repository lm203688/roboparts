# -*- coding: utf-8 -*-
"""L1.32 反向注入验证：把缺陷造回去，确认闸门确实变红（而非恒绿假绿）。

本仓已栽过 3 次假绿（括号深度判顶层 / 裸子串比数字 / 两个子串各自都在），
所以任何新断言都必须证明它能红。
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(ROOT, 'scripts', 'deploy.mjs')
RES = os.path.join(ROOT, 'ops', 'results')
PY = sys.executable


def run_l132():
    """只跑 L1.32，返回 (通过数, 失败数, 文本)。"""
    code = (
        "import sys; sys.argv=['x'];"
        "sys.path.insert(0,r'%s');"
        "import regression as R;"
        "R.layer1_32();"
        "print('FAILURES=%%d' %% len(R.failures))"
    ) % os.path.join(ROOT, 'scripts')
    r = subprocess.run([PY, '-c', code], cwd=ROOT, capture_output=True,
                       encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    m = re.search(r'FAILURES=(\d+)', out)
    return (int(m.group(1)) if m else -1), out


def case(name, mutate, restore):
    mutate()
    try:
        n, out = run_l132()
    finally:
        restore()
    ok = n > 0
    print(('  [OK] ' if ok else '  [BAD] ') + name + ('  -> 变红 %d 项' % n if ok else '  -> 仍然全绿（假绿！）'))
    return ok


def main():
    base_n, _ = run_l132()
    print('基线（未注入）失败数: %d %s' % (base_n, '✅' if base_n == 0 else '❌ 基线就不绿，先修基线'))
    if base_n != 0:
        sys.exit(1)

    src = open(DEPLOY, encoding='utf-8').read()
    results = []

    # 注入 1：摘掉调用，只留定义（最可能的"顺手删掉"退化路径）
    results.append(case(
        '注入1 摘掉 ensureRunTrace() 调用（仅保留函数定义）',
        lambda: open(DEPLOY, 'w', encoding='utf-8').write(
            src.replace('\nensureRunTrace();', '\n// ensureRunTrace();')),
        lambda: open(DEPLOY, 'w', encoding='utf-8').write(src)))

    # 注入 2：把调用挪到部署命令之后（形似还在，实际已失效 —— 典型假绿形态）
    moved = src.replace('\nensureRunTrace();', '\n')
    moved = moved.rstrip('\n') + '\nensureRunTrace();\n'
    results.append(case(
        '注入2 把调用挪到 pages deploy 之后（顺序失效）',
        lambda: open(DEPLOY, 'w', encoding='utf-8').write(moved),
        lambda: open(DEPLOY, 'w', encoding='utf-8').write(src)))

    # 注入 3：去掉 AUTO-STUB 标记（占位与真报告同形 → 闸门再也分不出来）
    results.append(case(
        '注入3 去掉 AUTO-STUB 标记（占位伪装成真报告）',
        lambda: open(DEPLOY, 'w', encoding='utf-8').write(
            src.replace('AUTO-STUB', 'PLACEHOLDER')),
        lambda: open(DEPLOY, 'w', encoding='utf-8').write(src)))

    # 注入 4：去掉 _SUMMARY 换行保护（L1.21 粘连根因复发）
    results.append(case(
        '注入4 去掉 _SUMMARY 换行结尾保护',
        lambda: open(DEPLOY, 'w', encoding='utf-8').write(
            src.replace("if (!cur.endsWith('\\n')) cur += '\\n';", '')),
        lambda: open(DEPLOY, 'w', encoding='utf-8').write(src)))

    # 注入 5：真实场景 —— 过去某小时留下没人填写的占位
    stub = os.path.join(RES, 'roboparts-20260801-03.md')

    def mk():
        open(stub, 'w', encoding='utf-8').write(
            '# stub\n<!-- AUTO-STUB: 部署了但没人来填 -->\n')

    def rm():
        if os.path.exists(stub):
            os.remove(stub)

    results.append(case('注入5 过去小时遗留未填写的 AUTO-STUB 占位', mk, rm))

    # 收尾复核：文件确实已还原
    assert open(DEPLOY, encoding='utf-8').read() == src, '❌ deploy.mjs 未还原！'
    n, _ = run_l132()
    print('还原后失败数: %d %s' % (n, '✅' if n == 0 else '❌'))

    ok = all(results) and n == 0
    print('\n' + ('✅ L1.32 反向注入 %d/%d 全部确认可阻断' % (len(results), len(results))
                  if ok else '❌ 存在假绿断言，必须修'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
