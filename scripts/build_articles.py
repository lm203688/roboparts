# -*- coding: utf-8 -*-
"""
build_articles.py —— 把 content/*.md 渲染为可被搜索引擎与 AI Agent 索引的静态文章页。

【为什么需要这个脚本 · 20260805-17 事故背景】
  content/ 下有 14 篇共约 244KB 的原创中文长文，frontmatter 里的 canonical 早已
  声明为 https://roboparts.cc/articles/{slug}，但仓库中**从未存在过任何 /articles 页面**。
  实测线上 /articles/任意路径 都返回 200 且内容是首页 HTML（Cloudflare Pages 在缺少
  404.html 时的 SPA 回落行为）。后果有三：
    1. sitemap.xml 里宣称的 3 条 /articles/* 全是重复内容 → 搜索引擎判定 sitemap 不可信，
       会连带削弱整站抓取预算；
    2. 14 篇文章一篇都没有对外入口 → 已投入的内容成本 100% 沉没；
    3. AI 检索（GEO）拿不到任何可引用的文章正文，只能看到 JSON 数据。

【设计原则】
  - 零依赖：不引入 markdown / jinja 等第三方库（项目零成本约束），内置够用的渲染器。
  - 幂等：可重复执行，输出仅由 content/ 决定。
  - 不臆造：frontmatter 缺失的字段留空或按规则派生，绝不编造日期/作者。
  - GEO 优先：每页注入 TechArticle + BreadcrumbList JSON-LD、canonical、OG，
    并显式给出数据集引用入口，便于 AI 检索时归因到 roboparts.cc。

用法： python scripts/build_articles.py
输出： articles/{slug}.html × N、articles/index.html、404.html
"""
import glob
import html
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(ROOT, 'content')
OUT_DIR = os.path.join(ROOT, 'articles')
BASE = 'https://roboparts.cc'
SITE_NAME = 'RoboParts'


def site_facts():
    """全站数字的唯一真相源。放在这里是因为本文件会整份重写 404.html，
    任何写死在模板里的数字都会被「每次构建重新种回来」，手改产物无效。"""
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    from onboarding_block import facts
    return facts()


# ------------------------------------------------------------------- 数字占位符
# 【为什么需要 · 20260808-18 事故背景】
#   14 篇正文里把数据集规模**写死成字面量**，结果集体过期且互相矛盾：
#   article-01/02 写「427 个实体」，article-06/08/12/14 写「493 个实体」，
#   真值早已是 706；执行器写 155（真 217）、芯片写 95 或 103（真 108）、
#   传感器写 62（真 90）、机器人AI模型写 17 或 21（真 44）。
#   即对外**低报 30%~60% 且自相矛盾**，等于主动告诉搜索引擎和 AI 检索
#   「这站比实际小、且口径不可信」——与当初 ros-discourse-post.md 的事故同类。
#   根因不是"数字写错了"，而是**数字有第二个来源**。故正文一律只写占位符，
#   构建时从 onboarding_block.facts() 现取；未知占位符直接抛错中断构建，
#   绝不允许静默漏渲染成 "{{RP:...}}" 泄漏到线上。
_TOKEN_RE = re.compile(r'\{\{RP:([A-Z_]+)(?::([a-z_0-9]+))?\}\}')


def render_tokens(text, facts_obj, src=''):
    cats = facts_obj.get('category_counts') or {}

    def _sub(m):
        key, arg = m.group(1), m.group(2)
        if key == 'TOTAL':
            return str(facts_obj['total_entities'])
        if key == 'CATEGORIES':
            return str(len(cats))
        if key == 'OSS_TOTAL':
            return str(facts_obj['oss_total'])
        if key == 'CAT':
            if arg not in cats:
                raise KeyError('%s: 未知品类占位符 {{RP:CAT:%s}}，真相源仅有 %s'
                               % (src, arg, '/'.join(sorted(cats))))
            return str(cats[arg])
        raise KeyError('%s: 未知占位符 {{RP:%s}}' % (src, key))

    out = _TOKEN_RE.sub(_sub, text)
    if '{{RP' in out:
        bad = re.findall(r'\{\{RP[^}]{0,40}\}?\}?', out)[:3]
        raise ValueError('%s: 占位符书写有误未被渲染（大小写/格式），残留 %s' % (src, bad))
    return out


# ---------------------------------------------------------------- frontmatter
def parse_frontmatter(text):
    """解析 YAML frontmatter 的常用子集：标量、双引号标量、行内数组。"""
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.S)
    if not m:
        return {}, text
    raw, body = m.group(1), text[m.end():]
    meta = {}
    for line in raw.split('\n'):
        line = line.rstrip()
        if not line or line.lstrip().startswith('#'):
            continue
        km = re.match(r'^([A-Za-z_][\w-]*):\s*(.*)$', line)
        if not km:
            continue
        key, val = km.group(1), km.group(2).strip()
        if val.startswith('[') and val.endswith(']'):
            inner = val[1:-1].strip()
            items = []
            if inner:
                for part in re.findall(r'"([^"]*)"|\'([^\']*)\'|([^,]+)', inner):
                    s = (part[0] or part[1] or part[2]).strip().strip('"\'')
                    if s:
                        items.append(s)
            meta[key] = items
        else:
            meta[key] = val.strip().strip('"\'')
    return meta, body


# ------------------------------------------------------------------- markdown
def inline(s):
    """行内元素渲染。顺序要紧：先保护行内代码，避免其中的 * _ 被误处理。"""
    codes = []

    def _keep(m):
        codes.append(m.group(1))
        return '\x00%d\x00' % (len(codes) - 1)

    s = re.sub(r'`([^`]+)`', _keep, s)
    s = html.escape(s, quote=False)
    # 链接 [text](url)
    s = re.sub(
        r'\[([^\]]+)\]\(([^)\s]+)\)',
        lambda m: '<a href="%s"%s>%s</a>' % (
            html.escape(m.group(2), quote=True),
            '' if m.group(2).startswith(('/', '#', BASE)) else ' target="_blank" rel="noopener"',
            m.group(1),
        ),
        s,
    )
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![\w*])\*([^*\n]+)\*(?![\w*])', r'<em>\1</em>', s)
    for i, c in enumerate(codes):
        s = s.replace('\x00%d\x00' % i, '<code>%s</code>' % html.escape(c, quote=False))
    return s


def slugify_anchor(text):
    t = re.sub(r'<[^>]+>', '', text)
    t = re.sub(r'[^\w\u4e00-\u9fff]+', '-', t).strip('-').lower()
    return t or 'section'


def render_markdown(md):
    """逐行状态机渲染。支持：h1-h4 / 表格 / 围栏代码 / 引用 / 有序无序列表 / 分隔线 / 段落。
    返回 (html, toc)；toc 为 [(level, text, anchor)]，仅收 h2/h3。"""
    lines = md.split('\n')
    out, toc = [], []
    i, n = 0, len(lines)
    list_stack = []  # 'ul' / 'ol'

    def close_lists():
        while list_stack:
            out.append('</%s>' % list_stack.pop())

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # 围栏代码块
        if stripped.startswith('```'):
            close_lists()
            lang = stripped[3:].strip()
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith('```'):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append(
                '<pre class="code"%s><code>%s</code></pre>'
                % (' data-lang="%s"' % html.escape(lang, True) if lang else '',
                   html.escape('\n'.join(buf), quote=False))
            )
            continue

        # 空行
        if not stripped:
            close_lists()
            i += 1
            continue

        # 表格：当前行含 | 且下一行是分隔行
        if '|' in stripped and i + 1 < n and re.match(r'^\s*\|?[\s:|-]+\|[\s:|-]*$', lines[i + 1]):
            close_lists()
            def cells(row):
                r = row.strip()
                if r.startswith('|'):
                    r = r[1:]
                if r.endswith('|'):
                    r = r[:-1]
                return [c.strip() for c in r.split('|')]

            head = cells(stripped)
            i += 2
            body = []
            while i < n and '|' in lines[i] and lines[i].strip():
                body.append(cells(lines[i]))
                i += 1
            t = ['<div class="tablebox"><table><thead><tr>']
            t += ['<th>%s</th>' % inline(c) for c in head]
            t.append('</tr></thead><tbody>')
            for row in body:
                row = (row + [''] * len(head))[:len(head)]
                t.append('<tr>' + ''.join('<td>%s</td>' % inline(c) for c in row) + '</tr>')
            t.append('</tbody></table></div>')
            out.append(''.join(t))
            continue

        # 标题
        hm = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if hm:
            close_lists()
            lvl = len(hm.group(1))
            txt = inline(hm.group(2).strip())
            if lvl == 1:
                # 正文 h1 交由页面标题承担，降级为 h2 以保证全页只有一个 h1
                lvl = 2
            anchor = slugify_anchor(txt)
            if lvl in (2, 3):
                toc.append((lvl, re.sub(r'<[^>]+>', '', txt), anchor))
            out.append('<h%d id="%s">%s</h%d>' % (lvl, anchor, txt, lvl))
            i += 1
            continue

        # 分隔线
        if re.match(r'^(\*{3,}|-{3,}|_{3,})$', stripped):
            close_lists()
            out.append('<hr>')
            i += 1
            continue

        # 引用块
        if stripped.startswith('>'):
            close_lists()
            buf = []
            while i < n and lines[i].strip().startswith('>'):
                buf.append(re.sub(r'^\s*>\s?', '', lines[i]))
                i += 1
            out.append('<blockquote>%s</blockquote>'
                       % ''.join('<p>%s</p>' % inline(b) for b in buf if b.strip()))
            continue

        # 列表
        lm = re.match(r'^(\s*)([-*]|\d+\.)\s+(.*)$', line)
        if lm:
            kind = 'ul' if lm.group(2) in ('-', '*') else 'ol'
            if not list_stack:
                list_stack.append(kind)
                out.append('<%s>' % kind)
            elif list_stack[-1] != kind:
                out.append('</%s>' % list_stack.pop())
                list_stack.append(kind)
                out.append('<%s>' % kind)
            out.append('<li>%s</li>' % inline(lm.group(3)))
            i += 1
            continue

        # 段落（合并后续连续非空、非块级起始行）
        close_lists()
        buf = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(('#', '>', '```', '|'))
                    or re.match(r'^(\s*)([-*]|\d+\.)\s+', lines[i])
                    or re.match(r'^(\*{3,}|-{3,}|_{3,})$', nxt)):
                break
            buf.append(nxt)
            i += 1
        out.append('<p>%s</p>' % inline(' '.join(buf)))

    close_lists()
    return '\n'.join(out), toc


# ----------------------------------------------------------------- 页面模板
CSS = """
:root{--bg:#0b1020;--card:#141b30;--acc:#37e0a6;--acc2:#5b9dff;--txt:#e7ecf5;--mut:#8a96b0;--line:#243352}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--txt);line-height:1.8}
a{color:var(--acc2);text-decoration:none}a:hover{text-decoration:underline}
.nav{border-bottom:1px solid var(--line);background:#0e1530}
.nav .in{max-width:960px;margin:0 auto;padding:12px 20px;display:flex;gap:16px;flex-wrap:wrap;align-items:center;font-size:14px}
.nav .brand{font-weight:800;color:var(--acc);font-size:16px}
.nav a{color:var(--mut)}.nav a:hover{color:var(--txt)}
.wrap{max-width:960px;margin:0 auto;padding:28px 20px 72px}
.crumb{font-size:13px;color:var(--mut);margin-bottom:14px}
h1{font-size:30px;line-height:1.4;margin:0 0 14px}
h2{font-size:22px;margin:34px 0 12px;padding-top:8px;border-top:1px solid var(--line)}
h3{font-size:18px;margin:24px 0 10px;color:var(--acc)}
h4{font-size:16px;margin:18px 0 8px}
.meta{color:var(--mut);font-size:13px;margin-bottom:18px}
.lede{background:var(--card);border-left:3px solid var(--acc);border-radius:0 10px 10px 0;padding:14px 16px;color:#c8d2e6;margin:18px 0 24px;font-size:15px}
.tags{margin:10px 0 0}
.badge{display:inline-block;background:#0e1530;border:1px solid var(--line);border-radius:999px;padding:2px 10px;font-size:12px;color:var(--mut);margin:2px 4px 2px 0}
.tablebox{overflow-x:auto;margin:16px 0;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:520px}
th,td{border-bottom:1px solid var(--line);padding:8px 12px;text-align:left;vertical-align:top}
th{background:#0e1530;color:var(--acc);font-weight:700;white-space:nowrap}
tbody tr:hover{background:#111a33}
blockquote{margin:16px 0;padding:10px 16px;background:#101830;border-left:3px solid var(--acc2);border-radius:0 8px 8px 0;color:#c2cde3}
blockquote p{margin:6px 0}
pre.code{background:#0a1128;border:1px solid var(--line);border-radius:10px;padding:14px;overflow-x:auto;font-size:13px;line-height:1.6}
code{background:#0e1530;border:1px solid var(--line);border-radius:5px;padding:1px 5px;font-size:13px;color:var(--acc)}
pre.code code{background:0;border:0;padding:0;color:#cfe3ff}
ul,ol{padding-left:22px}li{margin:6px 0}
hr{border:0;border-top:1px solid var(--line);margin:26px 0}
.toc{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin:22px 0}
.toc b{color:var(--acc);font-size:14px}
.toc ol{margin:8px 0 0;padding-left:20px;font-size:14px}
.toc li{margin:4px 0}.toc a{color:#b9c6de}
.cta{background:linear-gradient(135deg,#13233f,#152b3a);border:1px solid #2b6;border-radius:14px;padding:18px 20px;margin:30px 0 10px}
.cta h3{margin:0 0 8px;color:var(--acc);border:0;padding:0}
.cta p{margin:6px 0;font-size:14.5px;color:#c8d2e6}
.btn{display:inline-block;background:linear-gradient(135deg,var(--acc),var(--acc2));color:#04210f;font-weight:800;border-radius:9px;padding:9px 18px;margin:10px 8px 0 0;font-size:14px}
.btn:hover{text-decoration:none;opacity:.9}
.btn.ghost{background:transparent;color:var(--acc);border:1px solid var(--acc)}
.rel{margin-top:34px;border-top:1px solid var(--line);padding-top:18px}
.rel h3{border:0;padding:0;margin:0 0 10px}
.rel li{margin:8px 0;font-size:14.5px}
.foot{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);color:var(--mut);font-size:13px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-top:20px}
.acard{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;display:flex;flex-direction:column}
.acard h2{font-size:17px;margin:0 0 8px;border:0;padding:0;line-height:1.5}
.acard p{color:var(--mut);font-size:13.5px;margin:0 0 10px;flex:1}
@media(max-width:640px){h1{font-size:24px}.wrap{padding:20px 16px 56px}}
"""

NAV = """<div class="nav"><div class="in">
<a class="brand" href="/">RoboParts</a>
<a href="/articles">技术文库</a>
<a href="/oss">开源数据层</a>
<a href="/bom-checker">BOM 兼容检查</a>
<a href="/selection">智能选型</a>
<a href="/data-hub">数据中心</a>
<a href="/pricing">定价</a>
</div></div>"""

CTA = """<div class="cta">
<h3>把这篇文章的结论直接跑一遍</h3>
<p>RoboParts 收录 <strong>688 个机器人零部件实体</strong>与 <strong>325 个开源项目组件</strong>，支持电气 / 机械 / 协议 / 软件四维兼容判定。文中提到的型号大多可直接检索。</p>
<a class="btn" href="/bom-checker">免费校验我的 BOM</a>
<a class="btn ghost" href="/oss">浏览开源组件库</a>
<a class="btn ghost" href="/api/data.json">下载结构化数据 (JSON)</a>
</div>"""


def page(title, desc, keywords, canonical, body, extra_ld=None, og_type='article'):
    ld = '\n'.join('<script type="application/ld+json">%s</script>'
                   % json.dumps(x, ensure_ascii=False, separators=(',', ':'))
                   for x in (extra_ld or []))
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%(title)s</title>

<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#0b1020">
<meta name="description" content="%(desc)s">
<meta name="keywords" content="%(kw)s">
<link rel="canonical" href="%(canon)s">
<meta property="og:type" content="%(ogt)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(canon)s">
<meta property="og:site_name" content="RoboParts">
<meta property="og:locale" content="zh_CN">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="%(title)s">
<meta name="twitter:description" content="%(desc)s">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
%(ld)s
<style>%(css)s</style>
</head>
<body>
%(nav)s
<div class="wrap">
%(body)s
<div class="foot">
© 2026 RoboParts · 开源机器人零部件兼容性平台 ·
<a href="/llms.txt">llms.txt</a> ·
<a href="/api/openapi.json">OpenAPI</a> ·
<a href="/agent-discovery.json">Agent 发现清单</a>
<br>本文数据引用自 RoboParts 公开数据集，转载请注明来源并保留原文链接。
</div>
</div>
</body>
</html>""" % dict(
        title=html.escape(title, True), desc=html.escape(desc, True),
        kw=html.escape(keywords, True), canon=canonical, ogt=og_type,
        ld=ld, css=CSS, nav=NAV, body=body,
    )


# --------------------------------------------------------------------- 构建
def build():
    files = sorted(glob.glob(os.path.join(CONTENT_DIR, 'article-*.md')))
    if not files:
        print('!! content/ 下没有 article-*.md')
        return 1
    os.makedirs(OUT_DIR, exist_ok=True)

    arts = []
    _facts = site_facts()
    for f in files:
        text = render_tokens(io.open(f, encoding='utf-8').read(), _facts, src=f)
        meta, body_md = parse_frontmatter(text)
        slug = (meta.get('slug') or '').strip()
        if not slug:
            print('!! 缺少 slug，跳过：', f)
            continue
        title = meta.get('title') or slug
        desc = meta.get('description') or ''
        kws = meta.get('keywords') or []
        if isinstance(kws, str):
            kws = [kws]
        tags = meta.get('tags') or []
        if isinstance(tags, str):
            tags = [tags]
        date = (meta.get('date') or '').strip()
        author = meta.get('author') or 'RoboParts Research'
        arts.append(dict(src=f, slug=slug, title=title, desc=desc, keywords=kws,
                         tags=tags, date=date, author=author, md=body_md,
                         words=len(re.sub(r'\s', '', body_md))))

    # 有日期的按日期倒序在前，无日期的按文件名顺序在后
    arts.sort(key=lambda a: (a['date'] == '', a['date'] and (0,) or (1,), a['date']), reverse=False)
    dated = sorted([a for a in arts if a['date']], key=lambda a: a['date'], reverse=True)
    undated = [a for a in arts if not a['date']]
    ordered = dated + undated

    for a in ordered:
        body_html, toc = render_markdown(a['md'])
        canon = '%s/articles/%s' % (BASE, a['slug'])

        # 相关文章：标签重合度最高的 3 篇
        rel = sorted(
            [b for b in ordered if b['slug'] != a['slug']],
            key=lambda b: len(set(b['tags']) & set(a['tags'])), reverse=True,
        )[:3]
        rel_html = ''
        if rel:
            rel_html = '<div class="rel"><h3>相关阅读</h3><ul>%s</ul></div>' % ''.join(
                '<li><a href="/articles/%s">%s</a></li>' % (r['slug'], html.escape(r['title']))
                for r in rel
            )

        toc_html = ''
        h2s = [t for t in toc if t[0] == 2]
        if len(h2s) >= 3:
            toc_html = '<div class="toc"><b>本文目录</b><ol>%s</ol></div>' % ''.join(
                '<li><a href="#%s">%s</a></li>' % (t[2], html.escape(t[1])) for t in h2s
            )

        crumb = ('<div class="crumb"><a href="/">首页</a> › '
                 '<a href="/articles">技术文库</a> › %s</div>' % html.escape(a['title'][:28]))
        meta_line = '<div class="meta">%s%s · 约 %d 字 · RoboParts 开源机器人兼容性平台</div>' % (
            (a['date'] + ' · ') if a['date'] else '', html.escape(a['author']), a['words'])
        tags_html = ('<div class="tags">%s</div>' % ''.join(
            '<span class="badge">%s</span>' % html.escape(t) for t in a['tags'])) if a['tags'] else ''
        lede = ('<div class="lede">%s</div>' % html.escape(a['desc'])) if a['desc'] else ''

        body = (crumb + '<h1>%s</h1>' % html.escape(a['title']) + meta_line + tags_html
                + lede + toc_html + '<article>' + body_html + '</article>' + CTA + rel_html)

        article_ld = {
            '@context': 'https://schema.org',
            '@type': 'TechArticle',
            'headline': a['title'][:110],
            'description': a['desc'],
            'keywords': ', '.join(a['keywords']),
            'inLanguage': 'zh-CN',
            'url': canon,
            'mainEntityOfPage': {'@type': 'WebPage', '@id': canon},
            'author': {'@type': 'Organization', 'name': a['author'], 'url': BASE},
            'publisher': {'@type': 'Organization', 'name': SITE_NAME, 'url': BASE},
            'isAccessibleForFree': True,
            'citation': {
                '@type': 'Dataset',
                'name': 'RoboParts 机器人零部件兼容性数据集',
                'url': BASE + '/api/data.json',
            },
        }
        if a['date']:
            article_ld['datePublished'] = a['date']
            article_ld['dateModified'] = a['date']

        crumb_ld = {
            '@context': 'https://schema.org',
            '@type': 'BreadcrumbList',
            'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': '首页', 'item': BASE},
                {'@type': 'ListItem', 'position': 2, 'name': '技术文库', 'item': BASE + '/articles'},
                {'@type': 'ListItem', 'position': 3, 'name': a['title'], 'item': canon},
            ],
        }

        out = page(a['title'] + ' | RoboParts', a['desc'] or a['title'],
                   ', '.join(a['keywords']), canon, body, [article_ld, crumb_ld])
        with io.open(os.path.join(OUT_DIR, a['slug'] + '.html'), 'w', encoding='utf-8') as fp:
            fp.write(out)

    # ---------------- 索引页 ----------------
    cards = ''.join(
        '<div class="acard"><h2><a href="/articles/%s">%s</a></h2><p>%s</p>'
        '<div>%s</div><div class="meta" style="margin:8px 0 0">%s约 %d 字</div></div>' % (
            a['slug'], html.escape(a['title']),
            html.escape((a['desc'] or '')[:130] + ('…' if len(a['desc'] or '') > 130 else '')),
            ''.join('<span class="badge">%s</span>' % html.escape(t) for t in a['tags'][:4]),
            (a['date'] + ' · ') if a['date'] else '', a['words'])
        for a in ordered
    )
    idx_desc = ('RoboParts 技术文库：%d 篇开源机器人零部件选型与兼容性深度长文，'
                '覆盖执行器选型、VLA 模型部署、边缘芯片、CAN FD/EtherCAT 协议、'
                '触觉传感器、国产替代与供应链分析，全部基于 688 个实体的公开数据集撰写。'
                % len(ordered))
    idx_body = (
        '<div class="crumb"><a href="/">首页</a> › 技术文库</div>'
        '<h1>RoboParts 技术文库</h1>'
        '<div class="meta">%d 篇原创长文 · 共约 %d 字 · 全部免费阅读，无需注册</div>'
        '<div class="lede">%s</div>'
        '<div class="cards">%s</div>' % (
            len(ordered), sum(a['words'] for a in ordered), html.escape(idx_desc), cards)
    ) + CTA

    idx_ld = [{
        '@context': 'https://schema.org', '@type': 'CollectionPage',
        'name': 'RoboParts 技术文库', 'description': idx_desc,
        'url': BASE + '/articles/', 'inLanguage': 'zh-CN',
        'isPartOf': {'@type': 'WebSite', 'name': SITE_NAME, 'url': BASE},
        'mainEntity': {
            '@type': 'ItemList', 'numberOfItems': len(ordered),
            'itemListElement': [
                {'@type': 'ListItem', 'position': i + 1, 'name': a['title'],
                 'url': '%s/articles/%s' % (BASE, a['slug'])}
                for i, a in enumerate(ordered)
            ],
        },
    }, {
        '@context': 'https://schema.org', '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': '首页', 'item': BASE},
            {'@type': 'ListItem', 'position': 2, 'name': '技术文库', 'item': BASE + '/articles'},
        ],
    }]
    with io.open(os.path.join(OUT_DIR, 'index.html'), 'w', encoding='utf-8') as fp:
        fp.write(page('技术文库 · 开源机器人零部件选型与兼容性长文 | RoboParts',
                      idx_desc, '开源机器人,零部件选型,兼容性,技术文章,人形机器人,执行器,VLA模型',
                      BASE + '/articles/', idx_body, idx_ld, og_type='website'))

    # ---------------- 404 页（消除软 404 根因） ----------------
    # 20260808-13：下面两条曾写死 325 / 688（真值 706），且本函数每次构建都会把旧数字
    # 重新种回 404.html —— 生成器里的硬编码数字是「越修越回来」的，手改产物没有意义。
    # 改为从唯一真相源 onboarding_block.facts() 现算，取数失败即构建失败（不回落旧值）。
    _f = site_facts()
    nf_body = (
        '<h1>404 · 页面不存在</h1>'
        '<div class="lede">你访问的路径在 RoboParts 上不存在。'
        '此前本站缺少该页面，导致任意未知路径都会回落首页并返回 200，'
        '已于 2026-08-05 修复为标准 404。</div>'
        '<p>可能你在找：</p>'
        '<ul>'
        '<li><a href="/articles">技术文库</a> —— 开源机器人选型与兼容性长文</li>'
        '<li><a href="/bom-checker">BOM 兼容性检查</a> —— 免费校验物料清单</li>'
        '<li><a href="/oss">开源组件数据层</a> —— %d 个开源项目组件</li>'
        % _f['oss_total'] +
        '<li><a href="/api/data.json">结构化数据 API</a> —— %d 个实体，可直接机读</li>'
        % _f['total_entities'] +
        '<li><a href="/llms.txt">llms.txt</a> —— 面向 AI Agent 的站点说明</li>'
        '</ul>'
    )
    with io.open(os.path.join(ROOT, '404.html'), 'w', encoding='utf-8') as fp:
        fp.write(page('404 · 页面不存在 | RoboParts', '页面不存在。返回 RoboParts 技术文库或数据 API。',
                      '404', BASE + '/404', nf_body, og_type='website'))

    print('✅ 生成文章页 %d 篇 → articles/' % len(ordered))
    for a in ordered:
        print('   /articles/%-48s %s %6d 字' % (a['slug'], a['date'] or '        ', a['words']))
    print('✅ 生成 articles/index.html（索引页）')
    print('✅ 生成 404.html（消除 SPA 软 404 回落）')

    sync_sitemap(ordered)
    sync_llms(ordered)
    sync_agent_discovery(ordered)
    return 0


def sync_agent_discovery(ordered):
    """把文章清单同步进 agent-discovery.json。

    20260808-13：`content_library.count/articles` 此前**没有任何生成者**，纯靠手工
    维护，只有 regression 事后判红。上一轮新增第 15 篇文章后它仍停在 14 —— 手工维护
    就是漂移源，正确做法是让唯一的文章生成者顺手把它写对（与 sitemap/llms 同源）。
    只重写 count 与 articles，其余字段（topic_landing_pages 等）原样保留。
    """
    p = os.path.join(ROOT, 'agent-discovery.json')
    if not os.path.exists(p):
        print('!! 未找到 agent-discovery.json，跳过同步')
        return
    doc = json.loads(io.open(p, encoding='utf-8').read())
    cl = doc.get('content_library')
    if not isinstance(cl, dict):
        print('!! agent-discovery.json 无 content_library 段，跳过同步')
        return
    cl['count'] = len(ordered)
    cl['articles'] = [{'title': a['title'],
                       'url': '%s/articles/%s' % (BASE, a['slug']),
                       'date': a['date'] or None} for a in ordered]
    io.open(p, 'w', encoding='utf-8').write(
        json.dumps(doc, ensure_ascii=False, indent=2) + '\n')
    print('✅ agent-discovery.json content_library 已同步（%d 篇）' % len(ordered))


def sync_llms(ordered):
    """在 llms.txt 中维护「技术文库」章节。

    llms.txt 是 AI Agent 读取本站的第一入口。此前它完全没有提到 content/ 里的 14 篇长文，
    等于 10 万字原创内容对 AI 检索不可见。本函数以标记块包裹，可重复覆盖。
    """
    p = os.path.join(ROOT, 'llms.txt')
    if not os.path.exists(p):
        print('!! 未找到 llms.txt，跳过同步')
        return
    txt = io.open(p, encoding='utf-8').read()
    begin, end = '<!-- ARTICLES:BEGIN -->', '<!-- ARTICLES:END -->'

    lines = [begin,
             '## 技术文库（原创长文，允许引用，请注明来源链接）',
             '索引页：https://roboparts.cc/articles',
             '共 %d 篇，约 %d 字。全部基于本站公开数据集撰写，免费无需注册。'
             % (len(ordered), sum(a['words'] for a in ordered)),
             '']
    for a in ordered:
        lines.append('- [%s](%s/articles/%s)%s — %s'
                     % (a['title'], BASE, a['slug'],
                        ('（%s）' % a['date']) if a['date'] else '',
                        (a['desc'] or '')[:110]))
    # 20260808-13 修复：本函数整块覆盖 ARTICLES:BEGIN..END，而「专题速查页」清单
    # 曾是**硬编码的 1 条**。其余 9 个工具页（转接件生成器 / 3D 预览库 / 推广中心 /
    # 海报 / GEO 仪表盘 / Copilot / Agent 架构 / Build Planner / Skills 清单）是历史上
    # 手工写进块内的 —— 于是每跑一次本脚本就被静默抹掉 9 条，llms.txt 又恰是 AI Agent
    # 读本站的第一入口，等于把 9 个工具页对 AI 隐身。这与 sitemap 在 20260805-21
    # 修过的「整段覆盖吞掉别人注册的条目」是同一个病，只是 llms.txt 这侧一直没修。
    # 改为与 sitemap 同构的保留式合并：先回收旧块速查页段里的全部条目，再并入已知项。
    keep_ref = []
    if begin in txt and end in txt:
        old_block = txt[txt.index(begin):txt.index(end)]
        seg = old_block.split('### 专题速查页', 1)
        if len(seg) == 2:
            for ln in seg[1].splitlines():
                ln = ln.rstrip()
                # 只回收条目行；文章段由本函数按 content/ 真值重建，不参与回收
                if ln.startswith('- [') and '/articles/' not in ln:
                    keep_ref.append(ln)

    known_ref = [
        '- [ISO 9409-1 机器人法兰速查](%s/iso-9409-flange) — designation 语法与解析正则、'
        'A50-4-M6/A80-4-M8/A100-6-M10/A160-8-M12 四大尺寸族对照、6 条装配红线、'
        '人形 3DOF 球肩三级负载参数。机读版：%s/api/mechanical_interfaces.json'
        % (BASE, BASE),
    ]

    def _url_of(line):
        m = re.search(r'\]\((https?://[^)]+)\)', line)
        return m.group(1) if m else line

    merged, seen_url = [], set()
    for ln in keep_ref + known_ref:
        u = _url_of(ln)
        if u in seen_url:
            continue
        seen_url.add(u)
        merged.append(ln)

    lines += ['', '### 专题速查页'] + merged + [end, '']
    block = '\n'.join(lines)

    if begin in txt and end in txt:
        txt = txt[:txt.index(begin)] + block + txt[txt.index(end) + len(end) + 1:]
    else:
        txt = txt.replace('## API', block + '\n## API', 1)
    io.open(p, 'w', encoding='utf-8').write(txt)
    print('✅ llms.txt 已同步技术文库章节（%d 篇 + 速查页 %d 条，其中回收 %d 条）'
          % (len(ordered), len(merged), len(keep_ref)))


def sync_sitemap(ordered):
    """把文章段整体重写进 sitemap.xml。

    此前 sitemap 里手工维护了 6 条 /articles/*，既漏了 8 篇，又因为页面根本不存在
    而全部指向软 404 —— 手工维护是漂移的根源。改为由本脚本按 content/ 真值重写，
    以 <!-- SEO Articles --> 为锚点，锚点之后到 </urlset> 之间的内容整体替换。
    """
    sm_path = os.path.join(ROOT, 'sitemap.xml')
    if not os.path.exists(sm_path):
        print('!! 未找到 sitemap.xml，跳过同步')
        return
    xml = io.open(sm_path, encoding='utf-8').read()
    marker = '<!-- SEO Articles -->'
    # 这不是"今天"，是**新条目从未出现过时的回退日期**。原来的变量名叫 today 却是
    # 写死常量，读代码的人（包括我）会以为它跟着当天走 —— 变量名撒谎比数字过期更坏。
    FALLBACK_DATE = '2026-08-05'

    # 20260808-13 修复：下面的"保留式合并"此前**只回收 path，丢掉了 lastmod/
    # changefreq/priority**，回收后统一按 `/api/ ? daily,0.6 : weekly,0.9` 重新赋值、
    # lastmod 一律写成 FALLBACK_DATE。后果：geo-dashboard 从 daily 被降成 weekly、
    # promotion/海报 0.7 与 skills 0.6 被一律抬成 0.9（priority 全站拉平＝等于没有信号）、
    # 且 8-06/8-07 更新过的页 lastmod **倒退**回 8-05（对搜索引擎是负信号且与事实不符）。
    # 改为连属性一起回收，只有从未见过的新条目才使用默认值。
    prev = {}
    if marker in xml:
        for m in re.finditer(
                r'<url>\s*<loc>([^<]+)</loc>\s*<lastmod>([^<]*)</lastmod>\s*'
                r'<changefreq>([^<]*)</changefreq>\s*<priority>([^<]*)</priority>',
                xml[xml.index(marker):]):
            loc = m.group(1)
            path = loc[len(BASE):] if loc.startswith(BASE) else loc
            prev[path] = {'lastmod': m.group(2), 'changefreq': m.group(3),
                          'priority': m.group(4)}

    def _attr(path, key, default):
        v = (prev.get(path) or {}).get(key)
        return v if v else default

    entries = ['  <url><loc>%s/articles/</loc><lastmod>%s</lastmod>'
               '<changefreq>weekly</changefreq><priority>0.9</priority></url>'
               % (BASE, _attr('/articles/', 'lastmod', FALLBACK_DATE))]
    for a in ordered:
        path = '/articles/%s' % a['slug']
        entries.append(
            '  <url><loc>%s%s</loc><lastmod>%s</lastmod>'
            '<changefreq>monthly</changefreq><priority>0.8</priority></url>'
            % (BASE, path, a['date'] or _attr(path, 'lastmod', FALLBACK_DATE)))
    entries.append('')
    entries.append('  <!-- GEO 长尾落地页 -->')

    # 20260805-21 修复：本函数把「锚点 → </urlset>」整段覆盖重写，而长尾 URL 曾是
    # 硬编码的 2 条。结果 19:00 那轮新增的 /robot-joint-parameter-spec 与
    # /api/parameter_semantics.json 被下一次构建静默抹掉（本轮由 L1.10 拦下）。
    # 根因不是漏写了两行，而是「整段覆盖」会吞掉其他写者注册的 URL，
    # 且要求新增落地页的人记得回来改这里 —— 依赖记忆的机制迟早失效。
    # 改为保留式合并：先回收旧区段中所有非文章 URL，再并入本轮已知落地页。
    keep = []
    if marker in xml:
        for loc in re.findall(r'<loc>([^<]+)</loc>', xml[xml.index(marker):]):
            path = loc[len(BASE):] if loc.startswith(BASE) else loc
            if path.startswith('/articles'):
                continue          # 文章段由本函数按 content/ 真值重建
            keep.append(path)

    # 已知长尾落地页：每一条都必须有明确的生成者，不允许只靠手工往 sitemap 里塞。
    # /robot-joint-parameter-spec 与 /api/parameter_semantics.json 此前正是手工添加、
    # 无人认领，才会在下一次构建时被无声吞掉。
    known = [
        '/iso-9409-flange',                    # scripts/build_flange_page.py
        '/api/mechanical_interfaces.json',     # scripts/add_mechanical_interface.py
        '/robot-joint-parameter-spec',         # scripts/build_param_page.py
        '/api/parameter_semantics.json',       # scripts/build_parameter_semantics.py
    ]
    seen, extra = set(), []
    for path in keep + known:
        if path in seen:
            continue
        seen.add(path)
        extra.append(path)

    for path in extra:
        daily = path.startswith('/api/')
        entries.append(
            '  <url><loc>%s%s</loc><lastmod>%s</lastmod>'
            '<changefreq>%s</changefreq><priority>%s</priority></url>'
            % (BASE, path,
               _attr(path, 'lastmod', FALLBACK_DATE),
               _attr(path, 'changefreq', 'daily' if daily else 'weekly'),
               _attr(path, 'priority', '0.6' if daily else '0.9')))
    block = marker + '\n' + '\n'.join(entries) + '\n</urlset>\n'

    if marker in xml:
        xml = xml[:xml.index(marker)] + block
    else:
        xml = xml.replace('</urlset>', '  ' + block)
    io.open(sm_path, 'w', encoding='utf-8').write(xml)
    total = xml.count('<url>')
    print('✅ sitemap.xml 已同步：文章 %d 条 + 索引 1 条 + 长尾 %d 条（含回收 %d 条），'
          '全站共 %d 条 URL' % (len(ordered), len(extra), len(keep), total))


# --- RP-ONBOARDING 自动重注入（构建覆盖页面后必须补回接入入口）---
def _reinject_onboarding():
    import subprocess, sys as _s, os as _o
    _r = _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    # check=False 会把注入器崩溃吞掉，构建照样打印成功 → 文章上线却没有接入区块。
    # "调了注入器" ≠ "注入器跑成了"，必须校验 returncode。
    p = subprocess.run([_s.executable, _o.path.join(_r, 'scripts', 'inject_onboarding.py')],
                       check=False)
    if p.returncode != 0:
        print('!! inject_onboarding.py 退出码 %d —— 接入区块未注入，构建判失败' % p.returncode)
    return p.returncode


if __name__ == '__main__':
    _rc = build()
    _rc2 = _reinject_onboarding()
    sys.exit(_rc or _rc2)
