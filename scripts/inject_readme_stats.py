# -*- coding: utf-8 -*-
"""
inject_readme_stats.py —— 把 README 顶部的「数据量 / 最后更新」两行
从 onboarding_block.facts() 现算注入，杜绝手改漂移。

背景（_MARKET_POSITIONING-20260918.md · P0-2）：
    README 顶部长期写死「688 实体 / 最后更新 2026-08-05」，而真值早已是
    798 实体、2026-09-17 仍在更新。GitHub 访客第一印象就是「这项目 6 周没维护」。
    与 onboarding_block 同一纪律：数字唯一真相源 = facts()，README 不写第二份。

用法：
    python scripts/inject_readme_stats.py
幂等：marker 包裹，重复运行只刷新中间内容。
"""
import os
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import onboarding_block as ob  # noqa: E402

MARK_START = '<!-- RP-STATS:START 由 scripts/inject_readme_stats.py 生成，勿手改 -->'
MARK_END = '<!-- RP-STATS:END -->'


def last_updated():
    """最后更新取最近一次提交日期（fallback 当天）。"""
    try:
        out = subprocess.run(
            ['git', 'log', '-1', '--date=short', '--format=%cd'],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return date.today().isoformat()


def block(f, day):
    return (
        f'- **数据量**：{f["total_entities"]} 实体'
        f'（{f["component_entities"]} 实物零部件 / {f["specification_entities"]} 接口规范 / '
        f'{f["software_entities"]} AI 模型软件 / {f["organization_entities"]} 企业主体 / '
        f'{f["market_intelligence_entities"]} 市场情报）；'
        f'机械接口声明率 {f["mech_pct"]}%（{f["mech_declared"]}/{f["mech_applicable"]}）；'
        f'开源组件 {f["oss_total"]}\n'
        f'- **最后更新**：{day}'
    )


def inject():
    f = ob.facts()
    day = last_updated()
    body = block(f, day)
    seg = f'{MARK_START}\n{body}\n{MARK_END}'

    readme = os.path.join(ROOT, 'README.md')
    with open(readme, encoding='utf-8') as fh:
        text = fh.read()

    if MARK_START in text and MARK_END in text:
        head = text[:text.index(MARK_START)]
        tail = text[text.index(MARK_END) + len(MARK_END):]
        text = head + seg + tail
    else:
        # 首次注入：插到标题行之后
        text = text.replace(
            '# RoboParts — 仿生机器人生态平台\n',
            '# RoboParts — 仿生机器人生态平台\n\n' + seg + '\n', 1)
    with open(readme, 'w', encoding='utf-8') as fh:
        fh.write(text)
    print(f'✅ README 计数已注入（{f["total_entities"]} 实体 / 最后更新 {day}）')


if __name__ == '__main__':
    inject()
