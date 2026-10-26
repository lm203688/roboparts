#!/usr/bin/env python3
"""将 RoboParts 统一 Shell 注入到所有根 HTML 页面（幂等）。

四件套（顺序严格）：
  HEAD: <link rel="stylesheet" href="/_shell.css">
  HEAD: <link rel="stylesheet" href="/_project-badge.css">
  BODY-TAIL: <script src="/rp-project.js"></script>   # 必须先加载（_shell.js 依赖）
  BODY-TAIL: <script src="/_shell.js"></script>

关键教训（2026-10-24 修复）：
  用 \s* 匹配标签会导致贪婪吞行 bug。改用行级精确匹配 re.MULTILINE。
"""
import os, sys, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_DIR = ROOT

SHELL_CSS = '<link rel="stylesheet" href="/_shell.css">'
BADGE_CSS = '<link rel="stylesheet" href="/_project-badge.css">'
PROJ_JS = '<script src="/rp-project.js"></script>'
SHELL_JS = '<script src="/_shell.js"></script>'

SKIP_FILES = set()


def inject_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    orig = html

    # 1. 移除所有 4 个标签（行级精确匹配，避免 \s* 贪婪吞行）
    for tag in [SHELL_CSS, BADGE_CSS, PROJ_JS, SHELL_JS]:
        html = re.sub(r'^.*' + re.escape(tag) + r'.*$', '', html, flags=re.MULTILINE)
    html = re.sub(r'\n{3,}', '\n\n', html)

    # 2. 插 CSS 到 <head> 之后
    m = re.search(r'(<head[^>]*>)', html, re.IGNORECASE)
    if m:
        pos = m.end()
        html = html[:pos] + '\n' + SHELL_CSS + '\n' + BADGE_CSS + html[pos:]

    # 3. 插 JS 到 </body> 之前
    m = re.search(r'</body>', html)
    if m:
        pos = m.start()
        html = html[:pos] + '\n' + PROJ_JS + '\n' + SHELL_JS + html[pos:]

    if html != orig:
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(html)
        return 'changed'
    return 'unchanged'


def verify(path: str) -> bool:
    with open(path, 'r', encoding='utf-8') as f:
        t = f.read()
    if SHELL_CSS not in t or BADGE_CSS not in t:
        return False
    if PROJ_JS not in t or SHELL_JS not in t:
        return False
    # 顺序：proj < shell < body
    i_proj = t.find(PROJ_JS)
    i_shell = t.find(SHELL_JS)
    i_body = t.rfind('</body>')
    return 0 <= i_proj < i_shell < i_body


def main():
    html_files = sorted([
        f for f in os.listdir(HTML_DIR)
        if f.endswith('.html') and f not in SKIP_FILES
    ])
    print(f'Found {len(html_files)} HTML pages')
    changed = unchanged = fail = 0
    for name in html_files:
        path = os.path.join(HTML_DIR, name)
        try:
            status = inject_file(path)
            if status == 'changed':
                changed += 1
            else:
                unchanged += 1
                print(f'  · {name:40s} unchanged')
        except Exception as e:
            fail += 1
            print(f'  ✗ {name:40s} ERROR: {e}')

    # 验证
    ok = 0
    for f in html_files:
        if verify(os.path.join(HTML_DIR, f)):
            ok += 1
    print(f'\nInject: {changed} changed, {unchanged} unchanged, {fail} failed')
    print(f'Verify: {ok}/{len(html_files)} 页 4 件齐全且顺序正确')
    return 0 if fail == 0 and ok == len(html_files) else 1


if __name__ == '__main__':
    sys.exit(main())
