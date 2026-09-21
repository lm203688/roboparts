# -*- coding: utf-8 -*-
"""
check_adapter_geometry.py —— 法兰转接件「三方几何一致性」闸门
================================================================

为什么需要（20260921 发现）
--------------------------
同一个 ISO 9409-1 法兰参数，在**三处**各写了一份，且**没有任何机器在守**：

    ① adapter-generator.html —— three.js 预览分支（浏览器里看到的 3D）
    ② adapter-generator.html —— OpenSCAD 导出模板（用户下载去打印的）
    ③ adapters/gen_adapter.py —— CLI/服务端（CadQuery，出真 BREP STEP）

历史上这里真出过事：① 曾把 `pinPCD` 当**半径**用（`s.pinPCD*Math.cos(a)`），
而 ②③ 按**直径**用 ⇒ 用户看到的预览与拿到手的 STL 是两套几何。
A100 预设 pinPCD=50 恰好等于其螺栓节圆半径 50，两个销孔会正好压在 0°/180°
的螺栓孔上，打印出来的板子装不上。

更要紧的是**它是怎么被发现的**：靠人读完三处代码比对出来的，而 ③ 的注释
在修复后还挂着"预览分支不一致"的过期警告一周（会误导下一个人"修"回去）。
也就是说 —— 这条一致性完全靠人的记忆维持，而人的记忆没有闸门。

元教训（本项目第 N 次同型）：**同一个口径的第二份来源，就是漂移的起点。**
本闸门不追求把三处合并成一份（浏览器端与 CLI 的技术栈不同，合并成本高于收益），
而是把「三处必须一致」这件事变成可机械判定的，让分叉当轮就红。

本闸门查什么
------------
A) 预设表的**自洽性**：label 里的标号（`A{n}` / `-{孔数}-M{螺纹}`）必须与
   同一行的 pcd / holes / thread 字段一致。标号写 4 孔、字段写 6 孔 = 用户
   按标号选型却拿到 6 孔的板。
B) **口径统一**：预览分支必须按直径解释 pinPCD（存在 `/2`），OpenSCAD 模板的
   `pins()` 模块必须按直径解释（`translate([pcd/2,...])`）。
C) **跨实现一致**：`adapter-generator.html` 的预设与 `adapters/gen_adapter.py`
   的预设，对同名 label 必须给出相同的 (pcd, holes, thread)。
D) 阴阳自证：喂四种真实会发生的分叉（半径口径回退、label 与字段不符、
   清空预设、删掉校验），闸门必须逐一判红 —— 否则它只是装饰。

用法：
    python scripts/check_adapter_geometry.py            # 判红则退出码非零
    python scripts/check_adapter_geometry.py --self-test  # 只跑阴阳自证
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, 'adapter-generator.html')
CLI = os.path.join(ROOT, 'adapters', 'gen_adapter.py')

FAILED: list[str] = []


def fail(msg: str) -> None:
    FAILED.append(msg)


def check(ok: bool, msg: str) -> None:
    if not ok:
        fail(msg)


# --------------------------------------------------------------------------
# 解析
# --------------------------------------------------------------------------

#: HTML 预设行形如：
#:   'A50':  {label:'ISO9409-1-A50-4-M6',  pcd:50,  holes:4, thread:'M6',  clr:6.5, pins:2, ...}
_HTML_PRESET_RE = re.compile(
    r"'([A0-9.]+)'\s*:\s*\{[^}]*?label\s*:\s*'([^']*)'[^}]*?"
    r"pcd\s*:\s*([0-9.]+)[^}]*?holes\s*:\s*(\d+)[^}]*?thread\s*:\s*'?M?(\d+)'?",
    re.S)

#: CLI 预设形如：
#:   "A50": dict(label="ISO9409-1-A50-4-M6", pcd=50.0, holes=4, thread="M6", ...)
_CLI_PRESET_RE = re.compile(
    r'"([A0-9.]+)"\s*:\s*dict\(label\s*=\s*"([^"]*)"\s*,\s*'
    r'pcd\s*=\s*([0-9.]+)\s*,\s*holes\s*=\s*(\d+)\s*,\s*thread\s*=\s*"M?(\d+)"',
    re.S)


def parse_html_presets(src: str) -> dict:
    out = {}
    for key, label, pcd, holes, thread in _HTML_PRESET_RE.findall(src):
        out[key] = {'label': label, 'pcd': float(pcd),
                    'holes': int(holes), 'thread': 'M' + thread}
    return out


def parse_cli_presets(src: str) -> dict:
    out = {}
    for key, label, pcd, holes, thread in _CLI_PRESET_RE.findall(src):
        out[key] = {'label': label, 'pcd': float(pcd),
                    'holes': int(holes), 'thread': 'M' + thread}
    return out


# --------------------------------------------------------------------------
# A) 预设表自洽：label 的标号必须与字段一致
# --------------------------------------------------------------------------
_LABEL_RE = re.compile(r'A([0-9.]+)(?:-(\d+)-M(\d+))?')


def label_conflicts(presets: dict) -> list[str]:
    """label 中出现的 A{n} / -{孔数}-M{螺纹} 必须与同行字段一致。"""
    bad = []
    for key, p in presets.items():
        m = _LABEL_RE.search(p['label'])
        if not m:
            continue
        tag_pcd, tag_holes, tag_thread = m.group(1), m.group(2), m.group(3)
        try:
            if tag_pcd is not None and abs(float(tag_pcd) - p['pcd']) > 1e-9:
                bad.append('%s: label 写 A%s 但 pcd=%.1f' % (key, tag_pcd, p['pcd']))
        except ValueError:
            bad.append('%s: label 中 PCD 片段不可解析（%r）' % (key, tag_pcd))
        if tag_holes is not None and int(tag_holes) != p['holes']:
            bad.append('%s: label 写 %s 孔但 holes=%d' % (key, tag_holes, p['holes']))
        if tag_thread is not None and ('M' + tag_thread) != p['thread']:
            bad.append('%s: label 写 M%s 但 thread=%s' % (key, tag_thread, p['thread']))
    return bad


# --------------------------------------------------------------------------
# B) 口径统一：pinPCD 一律按**直径**解释
# --------------------------------------------------------------------------
def preview_uses_diameter(html_src: str) -> bool:
    """three.js 预览分支必须对 **x 与 y 两个销孔坐标** 都做 /2（半径 = 直径 / 2）。

    【20260921 为什么必须限定两个坐标 + `s.` 前缀】
    第一版只扫全文件的 `pinPCD\\s*/\\s*2\\s*\\*`，结果自证的阴性①假绿：预览分支
    有 `Math.cos` 与 `Math.sin` 两处，只把 cos 那处改回半径口径时，sin 那处仍留着
    `/2` ⇒ 闸门照常通过。一个"只坏了一半"的几何分叉被放行，正是本闸门要防的事。
    `s.` 前缀把预览（选中规格 s）与导出分支（a./b. 两侧）区分开：
        L288  预览:   s.pinPCD/2*Math.cos(a)  /  s.pinPCD/2*Math.sin(a)
        L371  导出:   pins(${a.pinPCD...})    ← 不该被此处计分
    """
    cos_ok = bool(re.search(r'\bs\.pinPCD\s*/\s*2\s*\*\s*Math\.cos', html_src))
    sin_ok = bool(re.search(r'\bs\.pinPCD\s*/\s*2\s*\*\s*Math\.sin', html_src))
    return cos_ok and sin_ok


def scad_pins_uses_diameter(html_src: str) -> bool:
    """OpenSCAD 模板的 pins() 模块内部必须做 pcd/2 位移。"""
    m = re.search(r'module\s+pins\s*\([^)]*\)\s*\{(.*?)\}', html_src, re.S)
    if not m:
        return False
    return bool(re.search(r'translate\s*\(\s*\[\s*pcd\s*/\s*2', m.group(1)))


def cli_uses_diameter(cli_src: str) -> bool:
    """CLI 建孔时必须以 pin_pcd / 2 作为半径。"""
    return bool(re.search(r'pin_pcd\s*/\s*2', cli_src)
                or re.search(r'pinPCD\s*/\s*2', cli_src))


# --------------------------------------------------------------------------
# C) 跨实现一致
# --------------------------------------------------------------------------
def cross_impl_conflicts(html_p: dict, cli_p: dict) -> list[str]:
    bad = []
    common = sorted(set(html_p) & set(cli_p))
    if len(common) < 5:
        bad.append('两实现共有预设数过少（%d < 5），解析可能失效' % len(common))
    for k in common:
        a, b = html_p[k], cli_p[k]
        for f in ('pcd', 'holes', 'thread'):
            if a[f] != b[f]:
                bad.append('%s: %s 处 %s=%r，CLI 处 %r' % (k, 'HTML', f, a[f], b[f]))
    only_html = sorted(set(html_p) - set(cli_p))
    only_cli = sorted(set(cli_p) - set(html_p))
    if only_html:
        bad.append('仅 HTML 有的预设: %s' % ' '.join(only_html))
    if only_cli:
        bad.append('仅 CLI 有的预设: %s' % ' '.join(only_cli))
    return bad


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def audit(html_src: str, cli_src: str) -> list[str]:
    """纯函数：返回问题清单。阴阳自证直接复用它，保证测的是真东西。"""
    bad: list[str] = []
    hp = parse_html_presets(html_src)
    cp = parse_cli_presets(cli_src)

    if len(hp) < 5:
        bad.append('adapter-generator.html 预设解析到 %d 条（<5），闸门失效' % len(hp))
    if len(cp) < 5:
        bad.append('adapters/gen_adapter.py 预设解析到 %d 条（<5），闸门失效' % len(cp))

    bad += ['label 自洽: ' + x for x in label_conflicts(hp)]
    bad += ['label 自洽(CLI): ' + x for x in label_conflicts(cp)]

    if not preview_uses_diameter(html_src):
        bad.append('口径: 预览分支未见 pinPCD/2（疑似回退成半径解释 ⇒ 预览与产物两套几何）')
    if not scad_pins_uses_diameter(html_src):
        bad.append('口径: OpenSCAD pins() 模块未见 translate([pcd/2,...])')
    if not cli_uses_diameter(cli_src):
        bad.append('口径: CLI 未见 pin_pcd/2')

    bad += ['跨实现: ' + x for x in cross_impl_conflicts(hp, cp)]
    return bad


def self_test() -> int:
    """阴阳自证：四种真实会发生的分叉，闸门必须逐一判红。"""
    html = open(HTML, encoding='utf-8').read()
    cli = open(CLI, encoding='utf-8').read()
    cases = []

    # 阳性：生产源码必须干净（否则闸门恒红，等于没装）
    cases.append(('阳性(不该红): 生产源码通过全部判据', audit(html, cli), False))

    # 阴性 ①：预览回退成半径口径（历史真事故）。
    # 【20260921 本自证自身出过一次假绿】第一版只替换 cos 那处，sin 那处仍留 `/2`，
    # 闸门照常通过 ⇒ 阴性① 假绿。故这里**两处都替换**，模拟完整的历史回退形态；
    # 同时预览判据已改为 cos 与 sin 都必须带 /2（见 preview_uses_diameter）。
    mutated = (html.replace('s.pinPCD/2*Math.cos', 's.pinPCD*Math.cos')
                   .replace('s.pinPCD/2*Math.sin', 's.pinPCD*Math.sin'))
    assert mutated != html, '变异 ① 未生效：预览分支写法已改，请同步本自证'
    # 半坏形态（只坏 cos）也必须判红 —— 这是第一版漏掉的假绿路径
    half = html.replace('s.pinPCD/2*Math.cos', 's.pinPCD*Math.cos')
    assert half != html, '变异 ①b 未生效'
    cases.append(('阴性: 预览分支回退成半径解释（cos+sin 全回退）', audit(mutated, cli), True))
    cases.append(('阴性: 预览分支只坏一半（仅 cos 回退，sin 仍对）', audit(half, cli), True))

    # 阴性 ②：label 与字段不符（标号写 4 孔、字段写 6 孔）
    mutated = html.replace("'A50'", "'A50'")  # 保持解析面不变
    mutated = re.sub(r"(label:'ISO9409-1-A50-4-M6',\s*pcd:50,\s*holes:)\d+", r"\g<1>6", mutated, count=1)
    assert mutated != html, '变异 ② 未生效：A50 预设写法已改'
    cases.append(('阴性: label 写 4 孔而字段写 6 孔', audit(mutated, cli), True))

    # 阴性 ③：跨实现分叉（CLI 侧 A80 改成 4×M6）
    mutated = re.sub(r'("A80":\s*dict\(label="[^"]*",\s*pcd=80\.0,\s*holes=)\d+',
                     r'\g<1>4', cli, count=1)
    assert mutated != cli, '变异 ③ 未生效：CLI A80 预设写法已改'
    cases.append(('阴性: CLI 与 HTML 对 A80 给出不同孔数', audit(html, mutated), True))

    # 阴性 ④：OpenSCAD pins() 被改成半径口径
    mutated = re.sub(r'(module\s+pins\s*\([^)]*\)\s*\{[^}]*?)pcd\s*/\s*2',
                     r'\g<1>pcd', html, count=1, flags=re.S)
    assert mutated != html, '变异 ④ 未生效：pins() 模块写法已改'
    cases.append(('阴性: OpenSCAD pins() 改成半径口径', audit(mutated, cli), True))

    # 阴性 ⑤：清空预设表（防"解析到 0 条"被当成通过）
    cases.append(('阴性: 预设表被清空', audit('const FLANGE_PRESETS = {};', cli), True))

    nfail = 0
    for name, problems, want_red in cases:
        is_red = bool(problems)
        ok = (is_red == want_red)
        if not ok:
            nfail += 1
        print('  %s %s%s' % ('✅' if ok else '❌', name,
                             '' if ok else ' → %s' % (problems[:2])))
    print('\n阴阳自证：%d 例，%s' % (len(cases), 'PASS' if nfail == 0 else 'FAIL(%d)' % nfail))
    return 1 if nfail else 0


def main() -> int:
    if '--self-test' in sys.argv:
        return self_test()
    html = open(HTML, encoding='utf-8').read()
    cli = open(CLI, encoding='utf-8').read()
    problems = audit(html, cli)
    hp, cp = parse_html_presets(html), parse_cli_presets(cli)
    print('=== 转接件三方几何一致性 ===')
    print('  HTML 预设 %d 条 · CLI 预设 %d 条 · 共有 %d 条'
          % (len(hp), len(cp), len(set(hp) & set(cp))))
    if problems:
        print('❌ 判红 %d 项：' % len(problems))
        for p in problems:
            print('   - ' + p)
        return 1
    print('✅ 通过：label 自洽 · pinPCD 一律直径口径 · 跨实现 (pcd,holes,thread) 一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
