# -*- coding: utf-8 -*-
"""L1.36 反向注入验证：把闸门本该拦下的四类缺陷逐个种回去，确认每一处都变红。

闸门只有被真正打破过，才知道它拦的是不是它声称拦的东西。
基线全绿 + 注入全红 + 还原全绿，三者缺一不可。
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIDE = os.path.join(ROOT, 'mcp-guide.html')
README = os.path.join(ROOT, 'mcp-server', 'README.md')
REG = os.path.join(ROOT, 'scripts', 'regression.py')

# 断言名 → 关键片段（用于从输出里定位那一条的红绿）
ASSERTS = {
    'exist': '阳性：对外接入文档均存在',
    'path': '对外接入文档给的路径均可走通',
    'fneg': '功能性·阴：可执行配置里的未发布包名',
    'fpos': '功能性·阳：警示语中提及未发布包名',
}


def run_gate():
    """只跑 L1.36，返回 {断言名: True(绿)/False(红)}"""
    r = subprocess.run(
        [sys.executable, '-c',
         'import sys; sys.argv=["regression.py"];'
         'exec(open(r"%s",encoding="utf-8").read().replace('
         '"\\n    main()","\\n    pass"))' % REG.replace('\\', '\\\\')],
        cwd=ROOT, capture_output=True, text=True, timeout=180)
    out = r.stdout + r.stderr
    return out


def gate_state():
    """直接 import 方式跑 layer1_36，精确取每条断言状态。"""
    code = (
        'import io,sys,os\n'
        'sys.path.insert(0, r"%s")\n'
        'import importlib.util\n'
        'spec=importlib.util.spec_from_file_location("reg", r"%s")\n'
        'm=importlib.util.module_from_spec(spec)\n'
        'spec.loader.exec_module(m)\n'
        'm.failures.clear()\n'
        'buf=io.StringIO(); old=sys.stdout; sys.stdout=buf\n'
        'try:\n'
        '    m.layer1_36()\n'
        'finally:\n'
        '    sys.stdout=old\n'
        'print(buf.getvalue())\n'
    ) % (os.path.join(ROOT, 'scripts').replace('\\', '\\\\'),
         REG.replace('\\', '\\\\'))
    r = subprocess.run([sys.executable, '-c', code], cwd=ROOT,
                       capture_output=True, text=True, timeout=180)
    out = r.stdout + r.stderr
    state = {}
    for key, frag in ASSERTS.items():
        green = ('✅ ' + frag) in out or any(
            l.strip().startswith('✅') and frag in l for l in out.splitlines())
        red = any(l.strip().startswith('❌') and frag in l
                  for l in out.splitlines())
        state[key] = True if green and not red else False
    return state, out


def fmt(st):
    return ' '.join('%s=%s' % (k, '绿' if v else '红') for k, v in st.items())


def main():
    bak = {}
    for p in (GUIDE, README):
        bak[p] = p + '.l136bak'
        shutil.copy2(p, bak[p])

    def restore():
        for p, b in bak.items():
            shutil.copy2(b, p)
            os.remove(b)

    try:
        base, out = gate_state()
        print('[基线]', fmt(base))
        if not all(base.values()):
            print('基线未全绿，终止。\n', out)
            restore()
            return 1

        results = []

        # ① 移除远程直连 URL（回到"唯一能用的路径没人告诉"的原缺陷）
        t = open(GUIDE, encoding='utf-8').read()
        open(GUIDE, 'w', encoding='utf-8').write(
            t.replace('https://roboparts.cc/mcp', 'https://example.invalid/mcp'))
        st, _ = gate_state()
        results.append(('①指南移除远程直连URL（原缺陷）', not st['path']))
        shutil.copy2(bak[GUIDE], GUIDE)

        # ② 恢复"教用户装未发布包"的可执行配置
        t = open(README, encoding='utf-8').read()
        t2 = t.replace('"args": ["-y", "mcp-remote", "https://roboparts.cc/mcp"]',
                       '"args": ["-y", "roboparts-mcp-server"]')
        assert t2 != t, '注入②未生效：目标片段未命中'
        open(README, 'w', encoding='utf-8').write(t2)
        st, _ = gate_state()
        results.append(('②README 教装未发布包 roboparts-mcp-server', not st['path']))
        shutil.copy2(bak[README], README)

        # ③ 删掉 git clone 但保留本地路径占位（给了拿不到的文件路径）
        t = open(GUIDE, encoding='utf-8').read()
        t2 = t.replace('git clone', 'GIT-CLONE-REMOVED')
        assert t2 != t, '注入③未生效'
        open(GUIDE, 'w', encoding='utf-8').write(t2)
        st, _ = gate_state()
        results.append(('③有本地路径占位却无 git clone 指引', not st['path']))
        shutil.copy2(bak[GUIDE], GUIDE)

        # ④ 文档整体缺失（闸门空转，阳性下界必须报）
        os.rename(GUIDE, GUIDE + '.hidden')
        st, _ = gate_state()
        os.rename(GUIDE + '.hidden', GUIDE)
        results.append(('④接入文档缺失（闸门空转）', not st['exist']))

        for name, ok in results:
            print('%s %s' % ('✅' if ok else '❌ 未拦下', name))

        fin, _ = gate_state()
        print('[还原]', '✅ 全绿' if all(fin.values()) else '❌ ' + fmt(fin))
        passed = sum(1 for _, ok in results if ok)
        print('\n结论：%d/%d 处注入被对应断言拦下' % (passed, len(results)))
        return 0 if passed == len(results) and all(fin.values()) else 1
    finally:
        restore()


if __name__ == '__main__':
    sys.exit(main())
