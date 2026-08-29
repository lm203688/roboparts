# -*- coding: utf-8 -*-
"""为全站 HTML 注入真实 favicon 链接与主题色，并清理旧的 emoji data-URI favicon。"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_BLOCK = (
    '<link rel="icon" href="/favicon.ico" sizes="any">\n'
    '<link rel="icon" type="image/svg+xml" href="/favicon.svg">\n'
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png">\n'
    '<meta name="theme-color" content="#0b1020">\n'
)
ICON_RE = re.compile(
    r'<link[^>]*rel\s*=\s*["\'](?:shortcut icon|icon)["\'][^>]*>\s*\n?',
    re.I)
THEME_RE = re.compile(r'<meta[^>]*name\s*=\s*["\']theme-color["\'][^>]*>\s*\n?', re.I)
TITLE_RE = re.compile(r'(</title>\n?)', re.I)


def fix(path):
    text = open(path, encoding='utf-8').read()
    text = ICON_RE.sub('', text)
    text = THEME_RE.sub('', text)
    m = TITLE_RE.search(text)
    if not m:
        return False, '未找到 </title>'
    pos = m.end()
    text = text[:pos] + '\n' + ICON_BLOCK + text[pos:]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return True, None


def targets():
    """全部对外 HTML。

    20260808-13：此前只扫根目录，`articles/` 下 16 个页面**从建站起就没有 favicon
    与 theme-color** —— 而文章页占 AI 爬虫抓取量约 30%，是搜索结果里露出最多的一批页，
    等于 SERP 一直显示默认地球图标。扫描面比修复逻辑更容易出错：逻辑写对了，
    只扫了一半目录，效果仍是零。
    """
    out = [os.path.join(ROOT, p) for p in sorted(os.listdir(ROOT))
           if p.endswith('.html') and os.path.isfile(os.path.join(ROOT, p))]
    art = os.path.join(ROOT, 'articles')
    if os.path.isdir(art):
        out += [os.path.join(art, p) for p in sorted(os.listdir(art))
                if p.endswith('.html')]
    return out


def main():
    htmls = [os.path.relpath(p, ROOT) for p in targets()]
    fixed = 0
    for name in htmls:
        ok, err = fix(os.path.join(ROOT, name))
        if ok:
            fixed += 1
            print(f'  ✅ {name}')
        else:
            print(f'  ⚠️ {name}: {err}')
    print(f'\n共处理 {fixed} 个 HTML 文件')


if __name__ == '__main__':
    main()
