# -*- coding: utf-8 -*-
"""L1.34 反向注入验证（20260806-22）

背景：L1.34 由 20260806-21 那轮写入，但**该轮在部署后中断，从未做过反向注入**。
一个从没被证伪过的闸门，和一句没被检验的断言没有区别 —— 它可能因为正则写错、
判据绑死单个文件名而恒绿。本脚本对 L1.34 的每一条断言各造一次真缺陷，
要求**对应那条**必须变红；同时要求注入前全绿、注入后能恢复原状。

用法： python scripts/verify_l134_injections.py
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, 'scripts', 'regression.py')


def read(p):
    with open(p, encoding='utf-8', errors='ignore') as f:
        return f.read()


def write(p, s):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


LAYERS = ('L1.34', 'L1.35')


def sections():
    """跑一遍回归，返回 {层名: (失败断言列表, 断言总数)}。"""
    r = subprocess.run([sys.executable, REG], cwd=ROOT,
                       capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = r.stdout or ''
    res = {}
    for lyr in LAYERS:
        m = re.search(r'\[' + re.escape(lyr) + r'\].*?(?=\n\[|\Z)', out, re.S)
        if not m:
            res[lyr] = (None, 0)
            continue
        block = m.group(0)
        fails = [ln.strip() for ln in block.splitlines() if '\u274c' in ln]
        total = len([ln for ln in block.splitlines()
                     if '\u2705' in ln or '\u274c' in ln])
        res[lyr] = (fails, total)
    return res


# 每项: (名称, [(相对路径, 原文, 替换, 是否全量替换)], 期望变红的断言关键字)
INJECTIONS = [
    ('死锚点：单处 /#api-access 改回 /#api',
     [('credits.html', '"/#api-access"', '"/#api"', False)],
     '无死锚点'),
    ('关键锚点被改名：index.html 的 id="api-access"',
     [('index.html', 'id="api-access"', 'id="api-access-renamed"', False)],
     '保留 #api-access'),
    ('批量改回死锚点（模拟一次性 sed 回退）',
     [('credits.html', '"/#api-access"', '"/#api"', True),
      ('pricing.html', '"/#api-access"', '"/#api"', True),
      ('data-hub.html', '"/#api-access"', '"/#api"', True),
      ('credits-history.html', '"/#api-access"', '"/#api"', True),
      ('selection.html', '"/#api-access"', '"/#api"', True),
      ('suppliers.html', '"/#api-access"', '"/#api"', True),
      ('bom-manager.html', '"/#api-access"', '"/#api"', True)],
     '\u9633\u6027\uff1a\u7ad9\u5185\u4ecd\u6709'),
    ('串站跳转：收钱页回到兄弟站域名',
     [('pricing.html', '</body>',
       '<a href="https://genetech.tools/api-key">Main Site</a></body>', False)],
     '\u65e0\u5144\u5f1f\u7ad9\u8df3\u8f6c'),
    ('示例代码留 pages.dev 预览域',
     [('api-pricing.html', 'https://roboparts.cc',
       'https://roboparts.pages.dev', False)],
     'api-pricing.html \u793a\u4f8b\u4ee3\u7801\u65e0 pages.dev'),
    # 注意：此项最初写成「替换 llms.txt 里第一个 roboparts.cc」，结果落在第 51 行的
    # 端点上而非第 163 行的「线上」声明行，注入没打中靶子 —— 反倒暴露出 L1.34
    # 这条断言只守一行、守不住其余 22 处引用。该缺口已由 L1.35 覆盖，此处改为精确打靶。
    ('llms.txt 线上条目指回预览域',
     [('llms.txt', '- 线上（正式域名，请始终引用此域）：https://roboparts.cc',
       '- 线上（正式域名，请始终引用此域）：https://robotparts-924.pages.dev',
       False)],
     'llms.txt\u300c\u7ebf\u4e0a\u300d'),
    ('【新】站内链接指向不存在的页面',
     [('pricing.html', '</body>',
       '<a href="/ghost-page">\u4ef7\u683c\u8be6\u60c5</a></body>', False)],
     '\u65e0\u6307\u5411\u4e0d\u5b58\u5728\u9875\u9762'),
    ('假绿防护：锚点扫描正则改成永不匹配',
     [('scripts/regression.py',
       r'''href="(#[^"]+|/#[^"]+|/[a-z0-9\-/]+#[^"]+)"''',
       r'''href="(#ZZNOMATCH[^"]+)"''', False)],
     '\u9633\u6027\uff1a\u951a\u70b9\u626b\u63cf'),
    ('【新】假绿防护：普通链接扫描正则改成永不匹配',
     [('scripts/regression.py', r'''href="(/[^"#?]*)"''',
       r'''href="(/ZZNOMATCH[^"#?]*)"''', False)],
     '\u9633\u6027\uff1a\u666e\u901a\u7ad9\u5185\u94fe\u63a5\u626b\u63cf'),
]

# L1.35 正式域权威性
INJECTIONS_35 = [
    ('主力收钱页丢失 canonical',
     [('pricing.html', '<link rel="canonical" href="https://roboparts.cc/pricing">',
       '', False)],
     '\u5747\u6709 canonical'),
    ('canonical 路由写错（认领了别的页面）',
     [('data-hub.html', '<link rel="canonical" href="https://roboparts.cc/data-hub">',
       '<link rel="canonical" href="https://roboparts.cc/selection">', False)],
     '\u8def\u7531\u81ea\u6d3d'),
    ('canonical 指向预览域（主动让出权重）',
     [('index.html', '<link rel="canonical" href="https://roboparts.cc/">',
       '<link rel="canonical" href="https://robotparts-924.pages.dev/">', False)],
     '\u65e0 canonical \u6307\u5411\u9884\u89c8\u57df'),
    ('README「线上地址」改回预览域（本轮真实缺陷重放）',
     [('README.md', '- **线上地址**: https://roboparts.cc',
       '- **线上地址**: https://robotparts-924.pages.dev', False)],
     'README\u300c\u7ebf\u4e0a\u5730\u5740\u300d'),
    ('llms.txt 预览域去掉「非正式」标注（变成裸引用）',
     [('llms.txt', '- 预览（Cloudflare Pages 默认域，非正式入口）：',
       '- 备用入口：', False)],
     '\u5747\u5df2\u6807\u6ce8\u4e3a\u975e\u6b63\u5f0f\u5165\u53e3'),
    ('假绿防护：sitemap 解析正则改成永不匹配',
     [('scripts/regression.py',
       r'''<loc>https://roboparts\.cc/([a-z0-9\-]*)</loc>''',
       r'''<loc>https://ZZNOMATCH\.cc/([a-z0-9\-]*)</loc>''', False)],
     '\u9633\u6027\uff1asitemap \u89e3\u6790'),
    ('假绿防护：预览域扫描常量被改空',
     [('scripts/regression.py', "PREVIEW = 'robotparts-924.pages.dev'",
       "PREVIEW = 'zz-nomatch-preview.invalid'", False)],
     '\u9633\u6027\uff1a\u9884\u89c8\u57df\u626b\u63cf'),
]


def main():
    print('=' * 62)
    print('L1.34 / L1.35 反向注入验证')
    print('=' * 62)

    base = sections()
    for lyr in LAYERS:
        fails, total = base[lyr]
        if fails is None:
            print('❌ 取不到 [%s] 段，闸门可能未被调用' % lyr)
            return 1
        print('[基线] %s 共 %d 条断言，失败 %d 条' % (lyr, total, len(fails)))
        for f in fails:
            print('   ', f)
        if fails:
            print('❌ 基线未全绿，先修好再做注入验证')
            return 1
    print('✅ 两层基线均全绿')

    plan = [('L1.34', INJECTIONS), ('L1.35', INJECTIONS_35)]
    total_inj = sum(len(v) for _, v in plan)
    passed = 0
    for layer, items in plan:
      print('\n' + '-' * 62)
      print('注入 %s' % layer)
      print('-' * 62)
      for name, edits, expect in items:
        backups = {}
        ok = True
        try:
            for rel, old, new, allrep in edits:
                p = os.path.join(ROOT, rel)
                src = read(p)
                if rel not in backups:
                    backups[rel] = src
                if old not in src:
                    print('\n⚠️  [%s] 注入锚文本未命中 %s，跳过' % (name, rel))
                    ok = False
                    break
                src = src.replace(old, new) if allrep else src.replace(old, new, 1)
                write(p, src)
            if not ok:
                continue
            fails, _ = sections()[layer]
            hit = [f for f in (fails or []) if expect in f]
            if hit:
                print('\n✅ [%s]' % name)
                print('    → 已拦下: %s' % hit[0][:96])
                passed += 1
            else:
                print('\n❌ [%s]' % name)
                print('    → 期望含「%s」的断言变红，实际失败项: %s'
                      % (expect, [f[:60] for f in (fails or [])] or '无（闸门漏过）'))
        finally:
            for rel, src in backups.items():
                write(os.path.join(ROOT, rel), src)

    after = sections()
    dirty = [l for l in LAYERS if after[l][0]]
    print('\n' + '=' * 62)
    print('注入 %d 项，拦下 %d 项' % (total_inj, passed))
    print('还原后基线: %s'
          % ('✅ 全绿' if not dirty
             else '❌ 未还原干净 %s' % {l: after[l][0] for l in dirty}))
    print('=' * 62)
    return 0 if passed == total_inj and not dirty else 1


if __name__ == '__main__':
    sys.exit(main())
