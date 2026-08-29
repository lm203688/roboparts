#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1.44 反向注入验证：把「404 只有总数、查不出伤口」重新造回去，确认闸门会红。

闸门只有在"缺陷回来时会红"的前提下才算数。这里逐条造回三类退化：

① **精确重现原缺陷**：把 404 埋点改回只写 `status:404`。
   这就是 20260807-16 之前的真实代码形态 —— 42 次 404 无一可定位。
② **假修复之一：全归 other**。分类器还在、键也还在写，看着像修了，
   但所有路径都被聚合，定位能力为零。闸门若只查"有没有写 404path 键"就会假绿。
③ **假修复之二：不设界**。直接把原始 pathname 当键，定位是有了，
   扫描器一来 KV 键空间就爆、写额度打满，真实死链反被淹掉。
④ **自污染**：摘掉自检分支的 404 隔离 —— deploy.mjs 每轮探私有路径拿 404，
   下一轮就会把飞轮自己的探针读成"站点有断链"（L1.42 同型坑）。
⑤ **写了没人读**：把 read_metrics.py 的 404 归因段删掉。
   埋点进 KV 却无人读取，等于没埋（mcp:* 段已经踩过一次这个坑）。
⑥ **判据放水**：把真跑验证脚本换成永远退出 0 的空壳。

用法：python scripts/verify_l144_injections.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEED = [
    ('functions', '_middleware.js'),
    ('scripts', 'regression.py'),
    ('scripts', 'read_metrics.py'),
    ('scripts', 'verify_404_attribution.mjs'),
    ('scripts', 'verify_l144_injections.py'),
]


def run_gate(root):
    """只跑 L1.44 段，返回 (是否全绿, 该段输出)。"""
    r = subprocess.run([sys.executable, os.path.join(root, 'scripts', 'regression.py')],
                       cwd=root, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=900)
    out = r.stdout or ''
    seg = ''
    if '[L1.44]' in out:
        seg = out.split('[L1.44]', 1)[1].split('\n[L', 1)[0]
    return ('❌' not in seg and '[L1.44]' in out), seg


def sandbox():
    """复制一份工作副本，避免污染真仓库。"""
    tmp = tempfile.mkdtemp(prefix='l144_')
    # 【20260807-17】漏了 .well-known 会让基线直接红（L1.44 段内就查 agent.json /
    # glama.json）—— 沙箱与真仓库不一致时，反向注入的结论一概不可信。
    for d in ('functions', 'scripts', 'api', 'content', 'articles', 'adapters',
              'skills', 'mcp-server', '.well-known'):
        src = os.path.join(ROOT, d)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(tmp, d), dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('node_modules', '__pycache__'))
    for f in os.listdir(ROOT):
        p = os.path.join(ROOT, f)
        if os.path.isfile(p):
            try:
                shutil.copy2(p, os.path.join(tmp, f))
            except Exception:
                pass
    return tmp


def patch(root, rel, fn):
    p = os.path.join(root, *rel)
    s = open(p, encoding='utf-8').read()
    s2 = fn(s)
    assert s2 != s, f'注入未生效（目标文本未匹配）: {"/".join(rel)}'
    open(p, 'w', encoding='utf-8').write(s2)


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case('① 原缺陷：404 只写总数，不写路径/调用方归因')
def _c1(root):
    patch(root, ('functions', '_middleware.js'), lambda s: re.sub(
        r"if \(status === 404\) \{.*?\n    \}",
        "if (status === 404) bump('status:404');", s, flags=re.S))


@case('② 假修复：分类器全归 other（键还在写，定位能力为零）')
def _c2(root):
    patch(root, ('functions', '_middleware.js'), lambda s: s.replace(
        "function classify404(p) {",
        "function classify404(p) {\n  return 'other';"))


@case('③ 假修复：直接用原始 pathname 当键（能定位但键空间无界）')
def _c3(root):
    patch(root, ('functions', '_middleware.js'), lambda s: s.replace(
        "function classify404(p) {",
        "function classify404(p) {\n  return String(p || '/');"))


@case('④ 自污染：摘掉自检分支的 404 隔离（把自家探针读成站点断链）')
def _c4(root):
    patch(root, ('functions', '_middleware.js'), lambda s: s.replace(
        "      if (status === 404) bump('selftest:status:404');\n", ''))


@case('⑤ 写了没人读：删掉 read_metrics.py 的 404 归因段')
def _c5(root):
    patch(root, ('scripts', 'read_metrics.py'), lambda s: re.sub(
        r"        paths = sorted.*?优先查 llms\.txt / sitemap\.xml / 文章互链'\)\n",
        '', s, flags=re.S))


@case('⑦ 同族缺陷：某个 GET 路由漏掉 onRequestHead（目录站探活判定我们下线）')
def _c7(root):
    """真实形态就是"新加路由时忘了加"——本轮全站 17 个 GET 路由一个都没有。
    只要漏一个，那条对外 URL 在探活工具眼里就是死的。"""
    patch(root, ('functions', 'api', 'oss.js'), lambda s: re.sub(
        r"\n// HEAD 探活.*?\n\}\n", '\n', s, flags=re.S))


@case('⑩ 补了但补错：HEAD 写死 200（把故障端点报成健康，比 404 更坏）')
def _c10(root):
    patch(root, ('functions', 'mcp.js'), lambda s: s.replace(
        'return new Response(null, { status: r.status, headers: r.headers });',
        'return new Response(null, { status: 200 });'))


@case('⑪ 校验放水：deploy 探活 HEAD 404 时回退 GET（本轮掩盖假修复两轮的元凶）')
def _c11(root):
    """2026-08-07 真实教训：探活拿到 HEAD 404 后回退 GET，只要 GET 通就报绿。
    于是线上 HEAD 一直 404、目录站一直判我们下线，而部署校验轮轮全绿。
    校验方式必须与真实探活方式一致，否则校验只是在自我安慰。"""
    patch(root, ('scripts', 'deploy.mjs'), lambda s: s.replace(
        "      const r = await fetch(TARGET + ep, { method: 'HEAD', headers: SELFTEST_HEADERS });",
        "      let r = await fetch(TARGET + ep, { method: 'HEAD', headers: SELFTEST_HEADERS });\n"
        "      if (r.status === 404) r = await fetch(TARGET + ep, { headers: SELFTEST_HEADERS });"))


@case('⑧ 同族缺陷：GET /api/register 退回 404（对外入口装作不存在）')
def _c8(root):
    patch(root, ('functions', 'api', 'register.js'), lambda s: s.replace(
        'export async function onRequestGet()', 'async function _disabledGet()'))


@case('⑨ 只静态检查不在线验证：删掉 deploy.mjs 的 HEAD 探活')
def _c9(root):
    patch(root, ('scripts', 'deploy.mjs'), lambda s: re.sub(
        r"  for \(const ep of \['/mcp'.*?\n  \}\n", '', s, flags=re.S))


@case('⑥ 判据放水：真跑脚本换成永远通过的空壳')
def _c6(root):
    p = os.path.join(root, 'scripts', 'verify_404_attribution.mjs')
    open(p, 'w', encoding='utf-8').write(
        "console.log('✅ ok');\nprocess.exit(0);\n")
    # 空壳本身退出 0，闸门若只看 returncode 就会假绿；
    # 真正的判据是分类器行为，所以同时把分类器也退化掉
    patch(root, ('functions', '_middleware.js'), lambda s: s.replace(
        "function classify404(p) {",
        "function classify404(p) {\n  return 'other';"))


def main():
    missing = [os.path.join(*r) for r in NEED
               if not os.path.isfile(os.path.join(ROOT, *r))]
    if missing:
        print('❌ 缺少依赖文件: ' + ', '.join(missing))
        return 1

    base = sandbox()
    green, seg = run_gate(base)
    if not green:
        print('❌ 基线未通过（未注入缺陷时闸门就是红的，无法判定注入是否有效）')
        print(seg[:800])
        shutil.rmtree(base, ignore_errors=True)
        return 1
    print('✅ 基线：未注入时 L1.44 全绿')
    shutil.rmtree(base, ignore_errors=True)

    bad = 0
    for name, fn in CASES:
        root = sandbox()
        try:
            fn(root)
            g, s = run_gate(root)
            if g:
                bad += 1
                print(f'❌ {name} —— 注入后闸门仍绿（闸门形同虚设）')
            else:
                first = next((ln.strip() for ln in s.splitlines()
                              if ln.strip().startswith('❌')), '')
                print(f'✅ {name} —— 闸门变红：{first[:110]}')
        except AssertionError as e:
            bad += 1
            print(f'❌ {name} —— {e}')
        finally:
            shutil.rmtree(root, ignore_errors=True)

    if bad:
        print(f'\n❌ {bad}/{len(CASES)} 条注入未被拦截')
        return 1
    print(f'\n✅ 全部 {len(CASES)} 条注入均被 L1.44 拦截')
    return 0


if __name__ == '__main__':
    sys.exit(main())
