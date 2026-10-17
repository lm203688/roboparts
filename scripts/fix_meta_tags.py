#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboParts meta tags 批量补齐（G-15/G-16 · 2026-10-17）

审计实测：11 页缺 meta description，32 页缺 og:title。
分享到微信/Twitter/Slack 时无摘要，SEO 也受影响。

本脚本：
  1. 从 <title> 提取页面标题
  2. 自动生成 meta description（基于标题 + 页面功能描述）
  3. 自动生成 og:title（复用 <title>）
  4. 插入到 <head> 中 <title> 之后

幂等：已有 description 或 og:title 的不重复插入。

用法：
    python scripts/fix_meta_tags.py [--dry-run]
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 页面功能描述映射（用于生成 meta description）
PAGE_DESCRIPTIONS = {
    'api-pricing': 'RoboParts API 定价方案 — 按调用量计费，免费层 1000 次/月',
    'bom-checker': 'BOM 兼容性检查器 — 上传 BOM 文件，自动检查零件间机械/电气/协议兼容性',
    'bom-import': '导入 BOM 文件 — 支持 CSV/Excel，自动匹配零件并生成兼容性报告',
    'compatibility-viz': '兼容性可视化 — 交互式查看零件间的机械、电气、协议兼容性关系图',
    'designer': 'RoboParts 模块化设计画布 — 拖拽式机器人组件设计与兼容性实时校验',
    'funnel': '激活漏斗 — 追踪从访客到付费用户的转化路径与关键指标',
    'order': '订单管理 — 查看和管理 RoboParts 订阅与积分订单',
    'oss': 'RoboParts 开源项目 — CC BY 4.0 许可的机器人零件兼容性数据层',
    'reference-builds': '开源机器人参考构型 — 预置 Unitree/A1/Go2 等主流机型兼容性配置',
    'scoreboard': '验证计分板 — 需求信号、资本信号、生态信号的融合验证视图',
    'standard-audit': '标准自校验 — ISO 9409/ISO 22166 等机器人接口标准合规性检查',
}

SITE_URL = 'https://roboparts.cc'
SITE_NAME = 'RoboParts'


def extract_title(html):
    """从 HTML 提取 <title>"""
    m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    return m.group(1).strip() if m else None


def has_meta_description(html):
    """检查是否已有 meta description"""
    return bool(re.search(r'<meta\s+name=["\']description["\']', html, re.I))


def has_og_title(html):
    """检查是否已有 og:title"""
    return bool(re.search(r'property=["\']og:title["\']', html, re.I))


def generate_description(page_name, title):
    """生成 meta description"""
    if page_name in PAGE_DESCRIPTIONS:
        return PAGE_DESCRIPTIONS[page_name]
    # 基于标题生成通用描述
    clean_title = re.sub(r'\s*[\|\-—].*RoboParts.*$', '', title or page_name).strip()
    if clean_title:
        return f'{clean_title} — RoboParts 机器人零件兼容性判定层'
    return f'{SITE_NAME} — 机器人零件兼容性判定层，868+ 零件数据，机械/电气/协议三轴兼容性验证'


def generate_og_title(title, page_name):
    """生成 og:title（优先用 <title>）"""
    if title:
        return title
    return f'{page_name} | {SITE_NAME}'


def fix_page(filepath, dry_run):
    """修复单个页面的 meta tags"""
    with open(filepath, encoding='utf-8', errors='replace') as f:
        html = f.read()

    page_name = os.path.splitext(os.path.basename(filepath))[0]
    title = extract_title(html)
    changed = False

    # 补 meta description
    if not has_meta_description(html):
        desc = generate_description(page_name, title)
        # 插入到 <title> 之后
        tag = f'  <meta name="description" content="{desc}">\n'
        title_pattern = r'(<title[^>]*>.*?</title>\n)'
        html, n = re.subn(title_pattern, r'\1' + tag, html, count=1, flags=re.I | re.DOTALL)
        if n == 0:
            # 如果没找到 <title>，插入到 <head> 之后
            head_pattern = r'(<head[^>]*>\n)'
            html, n = re.subn(head_pattern, r'\1' + tag, html, count=1, flags=re.I)
        if n > 0:
            changed = True
            print(f'  + description: {os.path.basename(filepath)}')

    # 补 og:title
    if not has_og_title(html):
        og_title = generate_og_title(title, page_name)
        tag = f'  <meta property="og:title" content="{og_title}">\n'
        # 插入到 description 之后（或 <title> 之后）
        if has_meta_description(html):
            desc_pattern = r'(<meta\s+name=["\']description["\'][^>]*>\n)'
            html, n = re.subn(desc_pattern, r'\1' + tag, html, count=1, flags=re.I)
        else:
            title_pattern = r'(<title[^>]*>.*?</title>\n)'
            html, n = re.subn(title_pattern, r'\1' + tag, html, count=1, flags=re.I | re.DOTALL)
        if n == 0:
            head_pattern = r'(<head[^>]*>\n)'
            html, n = re.subn(head_pattern, r'\1' + tag, html, count=1, flags=re.I)
        if n > 0:
            changed = True
            print(f'  + og:title: {os.path.basename(filepath)}')

    if changed and not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
    return changed


def main():
    dry = '--dry-run' in sys.argv
    html_files = glob.glob(os.path.join(ROOT, '*.html'))

    desc_added = 0
    og_added = 0

    print('=== meta tags 批量补齐 ===', '(dry-run)' if dry else '')
    for f in sorted(html_files):
        with open(f, encoding='utf-8', errors='replace') as fp:
            html = fp.read()
        page_name = os.path.splitext(os.path.basename(f))[0]
        needs_desc = not has_meta_description(html)
        needs_og = not has_og_title(html)

        if needs_desc or needs_og:
            if fix_page(f, dry):
                if needs_desc:
                    desc_added += 1
                if needs_og:
                    og_added += 1

    print(f'\n完成：+{desc_added} description, +{og_added} og:title')


if __name__ == '__main__':
    main()
