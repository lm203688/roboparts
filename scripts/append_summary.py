#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全追加一行飞轮摘要到 ops/results/_SUMMARY.md。

为什么需要一个脚本来干「追加一行」这么简单的事：
20260806-06 发现 00:00 与 02:00 两条摘要粘连成同一行 —— 上一条写入时没有以
换行结尾，下一条直接接在了它尾巴上。粘连后该记录不在行首，**任何按行解析的
下游（含日报汇总）都会静默丢掉它**，而文件看上去毫无异样。

手工 `>>` 追加无法保证前导换行，所以把这件事收敛到唯一入口，并在写入后
自校验「行首记录数 == 全文记录数」，不满足就报错退出（不留下半损文件）。

用法：
  python scripts/append_summary.py "- 2026-08-06 06:00 | 修复:… | 提升:… | 待办:…"
  python scripts/append_summary.py --file line.txt     # 长行从文件读，避免 shell 转义
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'ops', 'results', '_SUMMARY.md')
REC = r'-\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s*\|'


def main():
    args = sys.argv[1:]
    if not args:
        print('用法: append_summary.py "<摘要行>" | --file <路径>')
        return 2
    if args[0] == '--file':
        with open(args[1], encoding='utf-8') as f:
            line = f.read()
    else:
        line = args[0]

    line = ' '.join(line.split())          # 折叠换行/多空格，保证单行
    if not line.startswith('-'):
        line = '- ' + line
    if not re.match(r'^' + REC, line):
        print('❌ 格式不符，应为: - YYYY-MM-DD HH:MM | 修复:… | 提升:… | 待办:…')
        return 1

    old = ''
    if os.path.isfile(PATH):
        with open(PATH, encoding='utf-8') as f:
            old = f.read()

    sep = '' if (not old or old.endswith('\n')) else '\n'
    new = old + sep + line + '\n'

    total = len(re.findall(REC, new))
    heads = len([ln for ln in new.splitlines() if re.match(r'^\s*' + REC, ln)])
    if total != heads:
        print('❌ 自校验失败：记录 %d / 行首 %d，存在粘连，未写入' % (total, heads))
        return 1

    with open(PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new)
    print('✅ 已追加，当前 %d 条摘要，全部独占一行' % heads)
    return 0


if __name__ == '__main__':
    sys.exit(main())
