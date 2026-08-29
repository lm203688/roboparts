#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1.43 反向注入验证：把「对外机读契约手抄漂移」重新造出来，确认闸门会红。

一个闸门只有在"缺陷回来时会红"的前提下才有意义。这里逐条把 20260807-11
那份手写 manifest 的每种错法单独造回去：

① **精确重现原缺陷**：把 roboparts-search 的 keyword 改回 query。
   这正是 08:00 那轮刚在 mcp.js 里判定为"生态最常见误名"的那个参数。
② 声明一个端点不存在的工具（dataset_discovery）—— 原清单 6 项里有 2 项是这种。
③ 把 check_compatibility 的两个必填参数换成 components 数组
   —— 结构性错误，即使不看未知参数校验也会缺必填。
④ 只改 agent-discovery.json 的 skills.items（不动 manifest）
   —— 验证"三处同源"不是只盯着 manifest 一处。
⑤ 只改 skills/README.md 的表格 —— 人读的那份漂了同样要红。
⑥ 把 functions/mcp.js 的 `export { TOOLS }` 摘掉
   —— 真相源不再对外可读，生成器就只能回去手抄，等于地基没了。
⑦ 把生成器改成硬编码工具名（形似同源、实为把手抄挪个地方）。
⑧ 让 verify 脚本只做"存在性"判断不真跑
   —— 假修复的典型形态：判据变松，一切照绿。

用法：python scripts/verify_l143_injections.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, 'scripts', 'regression.py')


def run_gate(root):
    """只跑 L1.43 段，返回 (是否全绿, 该段输出)。"""
    r = subprocess.run([sys.executable, os.path.join(root, 'scripts', 'regression.py')],
                       cwd=root, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=600)
    out = r.stdout or ''
    seg = ''
    if '[L1.43]' in out:
        seg = out.split('[L1.43]', 1)[1].split('\n[L', 1)[0]
    return ('❌' not in seg and '[L1.43]' in out), seg


def sandbox():
    """复制一份最小工作副本（只带闸门需要的文件），避免污染真仓库。"""
    tmp = tempfile.mkdtemp(prefix='l143_')
    for rel in ['scripts', 'skills', 'functions']:
        shutil.copytree(os.path.join(ROOT, rel), os.path.join(tmp, rel),
                        ignore=shutil.ignore_patterns('__pycache__', 'node_modules'))
    for rel in ['agent-discovery.json']:
        shutil.copy2(os.path.join(ROOT, rel), os.path.join(tmp, rel))
    return tmp


def patch(root, rel, fn):
    p = os.path.join(root, rel)
    with open(p, 'r', encoding='utf-8') as f:
        s = f.read()
    s2 = fn(s)
    assert s2 != s, f'注入未生效（{rel} 内容没变，说明锚点已过时，判据可能已失效）'
    with open(p, 'w', encoding='utf-8') as f:
        f.write(s2)


def json_patch(root, rel, fn):
    p = os.path.join(root, rel)
    with open(p, 'r', encoding='utf-8') as f:
        d = json.load(f)
    fn(d)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write('\n')


# ── 注入用例 ──────────────────────────────────────────────────────────────
def inj_query(root):
    """① 精确重现：keyword 改回 query"""
    def f(d):
        for s in d['skills']:
            for p in s.get('params', []):
                if p['name'] == 'keyword':
                    p['name'] = 'query'
    json_patch(root, 'skills/manifest.json', f)


def inj_ghost_tool(root):
    """② 声明不存在的工具"""
    def f(d):
        d['skills'].append({
            'name': 'roboparts-dataset-discovery', 'title': '数据集发现',
            'type': 'mcp_tool', 'tool': 'dataset_discovery',
            'description': '发现公开数据集', 'when_to_use': '想下载原始数据时',
            'params': [],
        })
    json_patch(root, 'skills/manifest.json', f)


def inj_array_params(root):
    """③ check_compatibility 换成 components 数组"""
    def f(d):
        for s in d['skills']:
            if s.get('tool') == 'check_compatibility':
                s['params'] = [{'name': 'components', 'type': 'array',
                                'required': True, 'desc': '零部件 ID 数组'}]
    json_patch(root, 'skills/manifest.json', f)


def inj_agent_discovery(root):
    """④ 只改 agent-discovery.json"""
    def f(d):
        for it in d['skills']['items']:
            if it.get('tool') == 'get_parameter_semantics':
                it['tool'] = 'parameter_semantics'
    json_patch(root, 'agent-discovery.json', f)


def inj_readme(root):
    """⑤ 只改 README 表格"""
    patch(root, 'skills/README.md',
          lambda s: s.replace('`search_components`', '`search_parts`', 1))


def inj_unexport(root):
    """⑥ 摘掉 export { TOOLS }"""
    patch(root, 'functions/mcp.js',
          lambda s: s.replace('export { TOOLS };', '// export { TOOLS };', 1))


def inj_hardcode(root):
    """⑦ 生成器改成硬编码工具名"""
    patch(root, 'scripts/gen_skills_manifest.mjs',
          lambda s: s.replace("const BY_NAME = new Map(TOOLS.map((t) => [t.name, t]));",
                              "const BY_NAME = new Map(TOOLS.map((t) => [t.name, t]));\n"
                              "const _LEGACY = ['search_components', 'check_compatibility'];", 1))


def inj_toothless_verify(root):
    """⑧ verify 脚本退化成只做存在性判断（假修复）"""
    p = os.path.join(root, 'scripts', 'verify_skills_manifest.mjs')
    with open(p, 'w', encoding='utf-8') as f:
        f.write("import fs from 'node:fs';\n"
                "// 假修复：只确认文件在，不真跑 —— 判据一松，什么错都能绿\n"
                "console.log('✅ manifest 存在');\nprocess.exit(0);\n")
    # 同时把 manifest 改错，若闸门只信这个脚本就会漏掉
    inj_query(root)


CASES = [
    ('① keyword 改回 query（精确重现原缺陷）', inj_query),
    ('② 声明端点不存在的工具 dataset_discovery', inj_ghost_tool),
    ('③ check_compatibility 换成 components 数组（缺必填）', inj_array_params),
    ('④ 只改 agent-discovery.json 的 skills.items', inj_agent_discovery),
    ('⑤ 只改 skills/README.md 表格', inj_readme),
    ('⑥ 摘掉 functions/mcp.js 的 export { TOOLS }', inj_unexport),
    ('⑦ 生成器硬编码工具名（把手抄挪个地方）', inj_hardcode),
    ('⑧ verify 退化为只判存在性（假修复）', inj_toothless_verify),
]


def main():
    print('=== L1.43 反向注入 ===\n')

    ok, seg = run_gate(ROOT)
    print(f'{"✅" if ok else "❌"} 基线：真仓库 L1.43 全绿')
    if not ok:
        print(seg)
        return 1

    passed = 0
    for title, inject in CASES:
        tmp = sandbox()
        try:
            inject(tmp)
            caught, seg = run_gate(tmp)
            caught = not caught
            print(f'{"✅" if caught else "❌"} {title} —— {"被拦下" if caught else "**漏网**"}')
            if not caught:
                print('   闸门输出：' + re.sub(r'\s+', ' ', seg)[:300])
            passed += 1 if caught else 0
        except AssertionError as e:
            print(f'❌ {title} —— 注入失败: {e}')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print(f'\n{passed}/{len(CASES)} 处注入被拦下')
    return 0 if passed == len(CASES) else 1


if __name__ == '__main__':
    sys.exit(main())
