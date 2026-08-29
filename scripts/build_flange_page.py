# -*- coding: utf-8 -*-
"""
build_flange_page.py —— 由 api/mechanical_interfaces.json 生成 ISO 9409-1 法兰速查落地页。

【为什么做这一页 · GEO 获客切入点】
  "ISO 9409-1"、"A50-4-M6"、"机器人末端法兰尺寸"、"法兰能不能互换" 这类查询在中文互联网
  几乎没有结构化答案 —— 现有结果多为厂商 PDF 手册截图或论坛零散回帖，AI 检索时无可引用源。
  本页把 api/mechanical_interfaces.json 的登记表渲染成人可读 + 机可读双形态，并注入
  FAQPage / Dataset / TechArticle JSON-LD，目标是成为该问题簇的**被引用源**。

  内容全部来自登记表，本脚本不新增任何未经登记的数据 —— 页面与 API 永远同源，
  改数据只需改 JSON 并重跑，不会出现「页面说 A、API 说 B」的漂移。

用法： python scripts/build_flange_page.py
输出： iso-9409-flange.html
"""
import html
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from build_articles import page, BASE  # noqa: E402  复用同一套模板与样式

SLUG = 'iso-9409-flange'
CANON = '%s/%s' % (BASE, SLUG)


def esc(x):
    return html.escape(str(x), quote=False)


def build():
    src = os.path.join(ROOT, 'api', 'mechanical_interfaces.json')
    d = json.load(io.open(src, encoding='utf-8'))
    g = d['designation_grammar']
    flanges = d['flange_designations']
    shoulder = d['humanoid_shoulder_3dof_2026']
    gb = d['gb_modular_humanoid']
    taxo = d['mounting_taxonomy']
    pitfalls = d['pitfalls']
    eco = d['ecosystem_watch']

    title = 'ISO 9409-1 机器人法兰速查：designation 语法、标准尺寸族与互换红线'
    desc = ('ISO 9409-1:2004 圆形法兰（型式A）完整速查：designation 命名语法 '
            'ISO 9409-1-A{节圆}-{孔数}-M{螺纹} 的读法与正则、A50-4-M6 / A80-6-M8 / '
            'A100-6-M10 / A160-8-M16 标准尺寸族（含厂商偏离）对照、6 条会导致减速器漏油或螺栓咬死的'
            '装配红线，以及人形机器人 3DOF 球肩适配规范三级负载参数。数据可机读下载。')
    kws = ('ISO 9409-1,机器人法兰,机械接口,法兰标准,A50-4-M6,A80-6-M8,A100-6-M10,'
           '螺栓节圆直径,末端执行器安装,法兰互换,机器人手腕法兰,定位销 H7,'
           '人形机器人 3DOF 球肩,一体化关节,法兰尺寸对照表')

    # ---------------- 正文 ----------------
    P = []
    P.append('<div class="crumb"><a href="/">首页</a> › <a href="/articles">技术文库</a> › ISO 9409-1 法兰速查</div>')
    P.append('<h1>%s</h1>' % esc(title))
    P.append('<div class="meta">最后核验 %s · 数据源等级 %s · 可机读版本：'
             '<a href="/api/mechanical_interfaces.json">/api/mechanical_interfaces.json</a></div>'
             % (esc(g.get('last_verified', '')), esc(g.get('source_tier', ''))))
    P.append('<div class="lede">一句话结论：<strong>节圆直径、螺栓数量、螺纹规格三者全等，'
             '只是法兰互换的<u>必要条件</u>，不是充分条件。</strong>'
             '同一个 A80 designation 在不同机型上，螺纹有效旋入深度、法兰总厚度、中心通孔直径都可能不同 —— '
             '按 designation 选型只能得到「候选」，装机前必须查原厂规格手册确认这三项。</div>')

    P.append('<div class="toc"><b>本文目录</b><ol>'
             '<li><a href="#grammar">designation 怎么读（含解析正则）</a></li>'
             '<li><a href="#sizes">标准尺寸族（含厂商偏离）对照表</a></li>'
             '<li><a href="#rule">互换判定流程</a></li>'
             '<li><a href="#pitfalls">6 条装配红线</a></li>'
             '<li><a href="#humanoid">人形机器人 3DOF 球肩适配规范（2026）</a></li>'
             '<li><a href="#gb">《人形机器人模块化通用技术要求》进展</a></li>'
             '<li><a href="#mount">关节电机安装方式分类</a></li>'
             '<li><a href="#eco">2026 年标准化竞争态势</a></li>'
             '<li><a href="#faq">常见问题</a></li>'
             '</ol></div>')

    # 1 语法
    P.append('<h2 id="grammar">designation 怎么读</h2>')
    P.append('<p><strong>%s</strong> —— %s。现行有效版本为 2004 版，%s</p>'
             % (esc(g['standard']), esc(g['title']), esc(g.get('note', ''))))
    P.append('<pre class="code"><code>%s\n\n%s</code></pre>' % (esc(g['format']), esc(g['example'])))
    P.append('<div class="tablebox"><table><thead><tr><th>字段</th><th>含义</th></tr></thead><tbody>'
             + ''.join('<tr><td><code>%s</code></td><td>%s</td></tr>' % (esc(k), esc(v))
                       for k, v in g['fields'].items())
             + '</tbody></table></div>')
    P.append('<p>若你要在程序里解析这串标识，可直接用下面的具名捕获组正则：</p>')
    P.append('<pre class="code" data-lang="regex"><code>%s</code></pre>' % esc(g['parse_regex']))

    # 2 尺寸族
    P.append('<h2 id="sizes">标准尺寸族（含厂商偏离）对照表</h2>')
    P.append('<p>下表为 ISO 9409-1 型式 A 在工业机器人上标准梯级（含厂商偏离，同一 A 标号在不同厂商可能对应不同几何）。'
             '<em>known_hosts</em> 列为已核实采用该法兰的机型，不代表穷举。</p>')
    rows = ''
    for f in flanges:
        rows += ('<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td>'
                 '<td>%s</td><td>%s</td><td>%s</td></tr>' % (
                     esc(f['id']), esc(f['d1_mm']), esc(f['bolt_count']), esc(f['thread']),
                     esc(f.get('dowel_holes') or '—'), esc(f.get('typical_payload_class') or '—'),
                     esc('、'.join(f.get('known_hosts') or []) or '—')))
    P.append('<div class="tablebox"><table><thead><tr>'
             '<th>Designation</th><th>节圆 d1 (mm)</th><th>螺栓数</th><th>螺纹</th>'
             '<th>定位销孔</th><th>典型负载级</th><th>已核实机型</th>'
             '</tr></thead><tbody>%s</tbody></table></div>' % rows)
    P.append('<p class="meta">数据来源：%s（源等级 %s，置信度 %s）</p>'
             % (esc(flanges[0].get('source', '')), esc(flanges[0].get('source_tier', '')),
                esc(flanges[0].get('confidence', ''))))

    # 3 互换规则
    P.append('<h2 id="rule">互换判定流程</h2>')
    P.append('<blockquote><p>%s</p></blockquote>' % esc(g['interchange_rule']))
    P.append('<ol>'
             '<li><strong>第一步（必要条件）</strong>：比对 d1 / n / thread 三项。任一不等 → 直接判不兼容，无需继续。</li>'
             '<li><strong>第二步（排除致命项）</strong>：查两侧机型手册的<u>螺纹有效旋入深度</u>。'
             '这一步不过关会顶破油封，是唯一可能造成减速器报废的项。</li>'
             '<li><strong>第三步（几何干涉）</strong>：比对法兰总厚度、中心通孔直径、定位销孔配合等级。</li>'
             '<li><strong>第四步（紧固件）</strong>：确认螺栓强度等级与长度，按原厂扭矩表拧紧。</li>'
             '</ol>')
    P.append('<p>只有四步全过才是「确认兼容」。跳过第二至第四步而仅凭 designation 相同就装机，'
             '是这个领域最常见也最昂贵的错误。</p>')

    # 4 红线
    P.append('<h2 id="pitfalls">6 条装配红线</h2>')
    sev_label = {'critical': '致命', 'high': '高', 'medium': '中'}
    prow = ''
    for p in pitfalls:
        prow += ('<tr><td><strong>%s</strong></td><td>%s</td><td>%s%s</td></tr>' % (
            esc(p['title']), esc(sev_label.get(p['severity'], p['severity'])),
            esc(p['detail']),
            ('<br><em>对选型的含义：%s</em>' % esc(p['implication_for_matching']))
            if p.get('implication_for_matching') else ''))
    P.append('<div class="tablebox"><table><thead><tr>'
             '<th>红线</th><th>严重度</th><th>说明</th></tr></thead><tbody>%s</tbody></table></div>' % prow)

    # 5 人形球肩
    P.append('<h2 id="humanoid">人形机器人 3DOF 球肩适配规范（2026）</h2>')
    P.append('<p>%s，由%s。当前状态：<strong>%s</strong>。</p>'
             % (esc(shoulder['title']), esc(shoulder['issuer']), esc(shoulder['status'])))
    lrow = ''
    for c in shoulder['load_classes']:
        lrow += ('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            esc(c['class']), esc(c['rated_static_load_kg']), esc(c['flange_od_mm']),
            esc(c['bolt_pattern']), esc(c['bolt_circle_mm']), esc(c['dowel_holes'])))
    P.append('<div class="tablebox"><table><thead><tr>'
             '<th>等级</th><th>额定静负载 (kg)</th><th>法兰外径 (mm)</th>'
             '<th>螺栓图案</th><th>螺栓节圆 (mm)</th><th>定位销孔</th>'
             '</tr></thead><tbody>%s</tbody></table></div>' % lrow)
    P.append('<p><strong>几何公差要求：</strong>%s</p>' % esc('；'.join(
        '%s %s' % (k, v) for k, v in shoulder['geometric_tolerance'].items())))
    P.append('<p><strong>其他要求：</strong>%s</p>' % esc('；'.join(
        '%s %s' % (k, v) for k, v in shoulder['other_requirements'].items())))
    P.append('<blockquote><p>%s</p></blockquote>' % esc(shoulder['note']))

    # 6 国标
    P.append('<h2 id="gb">《人形机器人模块化通用技术要求》进展</h2>')
    P.append('<p>由%s。模块粒度定义：%s。机械接口条款覆盖：%s。</p>'
             % (esc(gb['issuer']), esc(gb['granularity']), esc(gb['mechanical_interface_clause'])))
    P.append('<div class="tablebox"><table><thead><tr><th>合规层级</th><th>要求</th></tr></thead><tbody>'
             + ''.join('<tr><td><strong>%s</strong></td><td>%s</td></tr>'
                       % (esc(k.replace('_', ' ')), esc('、'.join(v)))
                       for k, v in gb['compliance_tiers'].items())
             + '</tbody></table></div>')
    P.append('<p>与机械接口相邻的其他维度同样被纳入：%s</p>' % esc('；'.join(
        '%s —— %s' % (k, v) for k, v in gb['adjacent_interfaces'].items())))

    # 7 安装分类
    P.append('<h2 id="mount">关节电机安装方式分类</h2>')
    P.append('<p>%s。RoboParts 数据库中 <code>mechanical_interface.mount_type</code> 字段即取以下枚举值：</p>'
             % esc(taxo['description']))
    P.append('<div class="tablebox"><table><thead><tr><th>取值</th><th>名称</th><th>定义</th>'
             '</tr></thead><tbody>'
             + ''.join('<tr><td><code>%s</code></td><td>%s</td><td>%s</td></tr>'
                       % (esc(v['key']), esc(v['label']), esc(v['definition']))
                       for v in taxo['values'])
             + '</tbody></table></div>')

    # 8 生态
    P.append('<h2 id="eco">2026 年标准化竞争态势</h2>')
    P.append('<p>%s</p>' % esc(eco['note']))
    P.append('<ul>' + ''.join(
        '<li><strong>%s</strong>：%s%s</li>' % (
            esc(i['actor']), esc(i['event']),
            ('（已知采用方：%s）' % esc('、'.join(i['adopters']))) if i.get('adopters') else '')
        for i in eco['items']) + '</ul>')
    P.append('<p>值得注意的是，目前推动接口统一的主力是<strong>零部件厂商与整机厂商自身</strong>。'
             '厂商主导的标准天然带有立场 —— 它更倾向于让生态围绕自家产品系列收敛。'
             '在标准尚未收敛的窗口期，一份<strong>中立、可机读、标注了数据来源等级的索引</strong>'
             '对采购方与开源硬件开发者是有实际价值的。</p>')

    # FAQ
    faqs = [
        ('ISO 9409-1 是什么标准？',
         'ISO 9409-1:2004《工业操作机器人 机械接口 第1部分：圆形法兰》规定了机器人手腕末端'
         '用于安装末端执行器的圆形法兰（型式 A）的尺寸系列，包括螺栓节圆直径、螺栓数量、'
         '螺纹规格与定位销孔。1988 版已废止，现行有效版本为 2004 版。'),
        ('ISO 9409-1-A50-4-M6 是什么意思？',
         '按 designation 语法 ISO 9409-1-A{d1}-{n}-M{thread} 拆解：节圆直径 φ50mm、'
         '4 个螺栓孔、螺纹规格 M6，另配 2 个 φ6H7 定位销孔。常见于 ABB IRB1100、IRB1200、'
         'IRB120、CRB1100、IRB920 等小型/协作机型。'),
        ('两个法兰 designation 相同就能互换吗？',
         '不能直接互换。designation 相同只说明螺栓孔位一致，属于必要条件。'
         '相同 A80 在不同机型上，螺纹有效旋入深度、法兰总厚度、中心通孔直径都可能不同。'
         'designation 匹配只能作为「候选」，装机前必须核对这三项。'),
        ('法兰装配最容易出的致命错误是什么？',
         '螺栓过长。每个机型的法兰螺纹有效旋入深度是固定的，螺栓超长会顶破腕部内部油封，'
         '导致减速器漏油。设计转接法兰时必须查该机型规格手册标注的最大允许旋入深度。'),
        ('机器人法兰应该用什么等级的螺栓？',
         '以 ABB 为例，官方强制要求 12.9 级高强度螺栓，禁止使用 4.8 级、8.8 级及不锈钢螺栓 —— '
         '低等级螺栓易塑性变形而松动，不锈钢螺栓易咬死。具体等级以原厂手册为准。'),
        ('定位销要用什么配合？',
         '机器人法兰上的销孔通常为 H7。工装侧的定位销外径推荐 g6，构成过渡配合。'
         '严禁按过盈配合硬敲装配，会损伤法兰销孔精度。'),
        ('是不是所有工业机器人法兰都符合 ISO 9409？',
         '不是。部分老款机型采用厂商专用非标法兰，例如 ABB IRB140、IRB2400 的早期版本。'
         '这类机型不能直接使用标准转接板，必须按原厂图纸加工。'),
        ('人形机器人的关节法兰有标准吗？',
         '截至 2026 年 8 月尚无强制国标。目前有寰识科技牵头的《人形机器人3DOF球肩驱控传'
         '一体化通用适配规范(2026版)》（团体/联合规范，分轻载 5kg / 中载 15kg / 重载 30kg 三级）、'
         '泉智博《关节接口白皮书》，以及中国电子技术标准化研究院立项的《人形机器人一体化关节通用规范》'
         '并行推进，尚未收敛。'),
        ('这些数据能程序化调用吗？',
         '可以。完整登记表以 JSON 形式发布在 https://roboparts.cc/api/mechanical_interfaces.json，'
         '含 designation 解析正则、尺寸族、装配红线与数据源等级标注，免费无需鉴权。'),
    ]
    P.append('<h2 id="faq">常见问题</h2>')
    for q, a in faqs:
        P.append('<h3>%s</h3><p>%s</p>' % (esc(q), esc(a)))

    # 数据诚实声明
    mic = d['meta'].get('coverage_note') or ''
    P.append('<h2 id="honesty">关于本页数据覆盖度的说明</h2>')
    P.append('<p>RoboParts 数据库当前收录 688 个零部件实体，其中 350 个属于「机械接口适用」类别。'
             '但<strong>已声明具体法兰尺寸的条目极少</strong> —— 我们选择如实披露这一点，'
             '而不是用推测值填满字段。每条实体都带有显式的 <code>mechanical_interface.status</code>'
             '（declared / partial / not_declared / n_a），可直接查询缺口。'
             '<code>not_declared</code> 表示<u>厂商未公开或我们尚未采集</u>，'
             '不代表该部件没有机械接口。</p>')
    if mic:
        P.append('<blockquote><p>%s</p></blockquote>' % esc(mic))

    P.append('<div class="cta"><h3>把法兰参数接进你的选型流程</h3>'
             '<p>登记表已作为公开 API 发布，可直接在 BOM 校验、选型脚本或 AI Agent 中调用。</p>'
             '<a class="btn" href="/api/mechanical_interfaces.json">获取 JSON 登记表</a>'
             '<a class="btn ghost" href="/bom-checker">校验我的 BOM</a>'
             '<a class="btn ghost" href="/articles">更多技术长文</a></div>')

    body = ''.join(P)

    # ---------------- JSON-LD ----------------
    ld_faq = {
        '@context': 'https://schema.org', '@type': 'FAQPage',
        'mainEntity': [
            {'@type': 'Question', 'name': q,
             'acceptedAnswer': {'@type': 'Answer', 'text': a}}
            for q, a in faqs
        ],
    }
    ld_article = {
        '@context': 'https://schema.org', '@type': 'TechArticle',
        'headline': 'ISO 9409-1 机器人法兰速查：designation 语法、标准尺寸族与互换红线',
        'description': desc, 'keywords': kws, 'inLanguage': 'zh-CN', 'url': CANON,
        'mainEntityOfPage': {'@type': 'WebPage', '@id': CANON},
        'author': {'@type': 'Organization', 'name': 'RoboParts Research', 'url': BASE},
        'publisher': {'@type': 'Organization', 'name': 'RoboParts', 'url': BASE},
        'dateModified': g.get('last_verified', ''),
        'isAccessibleForFree': True,
        'about': [{'@type': 'Thing', 'name': 'ISO 9409-1:2004'},
                  {'@type': 'Thing', 'name': '机器人机械接口法兰'}],
    }
    ld_dataset = {
        '@context': 'https://schema.org', '@type': 'Dataset',
        'name': 'RoboParts 机械接口标准登记表 (ISO 9409-1)',
        'description': 'ISO 9409-1:2004 法兰 designation 语法、解析正则、标准尺寸族、'
                       '人形机器人 3DOF 球肩适配规范与装配红线的机读登记表。',
        'url': CANON,
        'distribution': [{'@type': 'DataDownload', 'encodingFormat': 'application/json',
                          'contentUrl': BASE + '/api/mechanical_interfaces.json'}],
        'license': 'https://roboparts.cc/llms.txt',
        'creator': {'@type': 'Organization', 'name': 'RoboParts', 'url': BASE},
        'isAccessibleForFree': True, 'inLanguage': 'zh-CN',
    }
    ld_crumb = {
        '@context': 'https://schema.org', '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': '首页', 'item': BASE},
            {'@type': 'ListItem', 'position': 2, 'name': '技术文库', 'item': BASE + '/articles'},
            {'@type': 'ListItem', 'position': 3, 'name': 'ISO 9409-1 法兰速查', 'item': CANON},
        ],
    }

    out = page(title + ' | RoboParts', desc, kws, CANON, body,
               [ld_article, ld_faq, ld_dataset, ld_crumb])
    dst = os.path.join(ROOT, SLUG + '.html')
    with io.open(dst, 'w', encoding='utf-8') as fp:
        fp.write(out)
    print('✅ 生成 %s.html（%d 字节，%d 条 FAQ，%d 个尺寸族，%d 条红线）'
          % (SLUG, len(out.encode('utf-8')), len(faqs), len(flanges), len(pitfalls)))
    return 0


# --- RP-ONBOARDING 自动重注入（构建覆盖页面后必须补回接入入口）---
def _reinject_onboarding():
    import subprocess, sys as _s, os as _o
    _r = _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
    subprocess.run([_s.executable, _o.path.join(_r, 'scripts', 'inject_onboarding.py')],
                   check=False)


if __name__ == '__main__':
    _rc = build()
    _reinject_onboarding()
    sys.exit(_rc)
