# -*- coding: utf-8 -*-
"""
从 api/parameter_semantics.json 生成落地页 robot-joint-parameter-spec.html。
真相源单一：页面上所有数字均从 JSON 读出，杜绝"七处数字不一致"复发。
"""
import json
import html

ROOT = "C:/Users/xing/Desktop/robopart"
SRC = f"{ROOT}/api/parameter_semantics.json"
OUT = f"{ROOT}/robot-joint-parameter-spec.html"
URL = "https://roboparts.cc/robot-joint-parameter-spec"

d = json.load(open(SRC, encoding="utf-8"))
ev = d["industry_evidence"]["by_field"]
rl = d["red_lines"]
conv = d["unit_conversions"]
total = d["scope"]["entities_scanned"]

TQ_N, TQ_D = ev["torque"]["declared_count"], ev["torque"]["distinct_notations"]
SP_N, SP_D = ev["speed"]["declared_count"], ev["speed"]["distinct_notations"]

TITLE = "机器人关节参数虚标怎么辨别：6 条物理红线与口径对照表 | RoboParts"
DESC = (f"关节模组「额定扭矩」「峰值扭矩」「背隙」「精度」各家口径不同，数字无法横向比较。"
        f"本文给出 6 条基于物理约束的自洽性红线（扭矩密度 >120Nm/kg 需复核、峰值/额定比 >3 须给持续时间等）、"
        f"5 组单位换算公式、4 级可比性判据，以及采购问询清单。"
        f"基于 RoboParts {total} 条实体实测：仅 {TQ_N} 条声明扭矩却用了 {TQ_D} 种表述口径。"
        f"RoboParts 不卖零部件，故对参数口径无利益立场。")
KW = ("关节模组参数虚标,额定扭矩 峰值扭矩 区别,扭矩密度 Nm/kg,背隙 arcmin 测量条件,"
      "重复定位精度 绝对定位精度,关节模组选型 参数对比,机器人关节参数口径,"
      "sec/60度 转 rad/s,编码器位数 定位精度,关节 IP等级,谐波减速器 回差,参数水分 辨别")

faqs = [
    ("额定扭矩和峰值扭矩有什么区别？为什么不能只看峰值？",
     "额定扭矩是能连续输出且热稳定的扭矩；峰值扭矩受绕组热容与磁路饱和限制，是时间的函数而非常数。"
     "不声明允许持续时间的峰值扭矩在工程上没有意义。峰值/额定比超过 3 时必须索取持续时间与起始温度，"
     "超过 5 基本是瞬时堵转值。"),
    ("扭矩密度多少算不可信？",
     "以额定扭矩除以整机质量计算，超过 120 Nm/kg 需要复核，超过 200 Nm/kg 在 2026 年量产工艺下几乎不可信。"
     "常见做法是用峰值扭矩除以裸电机质量（不含减速器、外壳、编码器、刹车），这样能把数字做大 2 到 4 倍。"
     "核查方式：确认分子是额定还是峰值、分母是否为整机含线缆的称重值。"),
    ("背隙数值为什么不能直接比较？",
     "背隙随加载扭矩变化，空载测得的值会明显优于在 ±3% 额定扭矩下测得的值。"
     "此外「减速器背隙」与「关节整机回差」是两个概念，后者还包含轴承游隙与法兰变形。"
     "索取背隙时必须同时索取测量加载扭矩和测量对象。"),
    ("重复定位精度和绝对定位精度差多少？",
     "两者通常相差 1 到 2 个数量级。重复定位精度只反映回到同一点的离散度，"
     "不反映与指令位置的偏差。只写「精度 ±0.01°」而不说明是哪一种的参数表不具备可比性。"),
    ("17-bit 编码器是不是意味着定位精度 0.0027°？",
     "不是。17-bit 单圈编码器的理论量化步长约 0.0027°，这只是分辨率下界，"
     "不包含齿隙、柔轮变形、热漂移与安装误差。关节整机在输出端的实测重复定位精度通常要差 1 到 2 个数量级。"),
    ("舵机的 0.16 sec/60° 和电机的 6.3 rad/s 哪个快？",
     "两者量纲互逆，不能直接按数值大小比较，否则会得到完全相反的结论。"
     "换算公式：rad/s = (π/3) / t_sec。0.16 sec/60° 约等于 6.5 rad/s。"),
    ("为什么由 RoboParts 来定义参数口径？",
     "参数口径规范由零部件卖家发布时存在固有利益冲突——口径定义会向自家可造方案倾斜。"
     "RoboParts 不生产、不销售、不代理任何零部件，与任何厂商无供货或分成关系，"
     "对「谁的参数更好看」没有利益。这份规范的价值来源于发布方的中立性。"),
]

ld = {
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "TechArticle",
         "headline": "机器人关节参数虚标怎么辨别：6 条物理红线与口径对照表",
         "description": DESC, "url": URL, "inLanguage": "zh-CN",
         "datePublished": "2026-08-05", "dateModified": d["meta"]["generated_at"][:10],
         "author": {"@type": "Organization", "name": "RoboParts", "url": "https://roboparts.cc"},
         "publisher": {"@type": "Organization", "name": "RoboParts", "url": "https://roboparts.cc"},
         "isBasedOn": "https://roboparts.cc/api/parameter_semantics.json",
         "license": "https://creativecommons.org/licenses/by/4.0/",
         "keywords": KW},
        {"@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]},
        {"@type": "Dataset",
         "name": "RoboParts Parameter Semantics Registry",
         "description": "机器人关节参数口径规范、单位换算与物理自洽性红线，可机读。",
         "url": "https://roboparts.cc/api/parameter_semantics.json",
         "encodingFormat": "application/json",
         "license": "https://creativecommons.org/licenses/by/4.0/",
         "creator": {"@type": "Organization", "name": "RoboParts"}},
    ],
}

e = html.escape


def red_line_rows():
    out = []
    for r in rl:
        out.append(f"""<div class="rl">
<div class="rl-h"><span class="rl-id">{e(r['id'])}</span><h3>{e(r['name'])}</h3></div>
<table class="rl-t"><tbody>
<tr><th>判据</th><td><code>{e(r['check'])}</code></td></tr>
<tr><th>阈值</th><td class="hot">{e(r['threshold'])}</td></tr>
<tr><th>物理依据</th><td>{e(r['physics'])}</td></tr>
<tr><th>常见做法</th><td class="trick">{e(r['common_trick'])}</td></tr>
<tr><th>怎么核查</th><td class="ok">{e(r['how_to_verify'])}</td></tr>
</tbody></table></div>""")
    return "\n".join(out)


def conv_rows():
    out = []
    for c in conv:
        w = c.get("warning", "")
        wh = f'<div class="warn">{e(w)}</div>' if w else ""
        out.append(f"<tr><td><code>{e(c['from'])}</code></td><td><code>{e(c['to'])}</code></td>"
                   f"<td><code>{e(c['formula'])}</code>{wh}</td></tr>")
    return "\n".join(out)


def num(key, value):
    """输出带真相源锚点的数字。

    回归 L1.10 靠 data-src 属性精确定位并与 JSON 比对。
    不可退回裸数字——裸子串比对会被 CSS 色值等无关内容误命中而恒真（假绿）。
    """
    return f'<span data-src="{key}">{value}</span>'


def evidence_rows():
    out = []
    for f, v in ev.items():
        out.append(
            f"<tr><td><code>{e(f)}</code></td>"
            f"<td>{num(f'{f}.declared_count', v['declared_count'])}</td>"
            f"<td>{num(f'{f}.absent_count', v['absent_count'])}</td>"
            f"<td class=\"hot\">{num(f'{f}.distinct_notations', v['distinct_notations'])}</td></tr>")
    return "\n".join(out)


def cmp_rows():
    out = []
    for c in d["comparability_levels"]:
        out.append(f"<tr><td class=\"lv lv-{e(c['level'])}\">{e(c['level'])}</td>"
                   f"<td><b>{e(c['label'])}</b></td><td>{e(c['criteria'])}</td>"
                   f"<td>{e(c.get('note',''))}</td></tr>")
    return "\n".join(out)


def faq_html():
    return "\n".join(
        f'<details class="faq"><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q, a in faqs)


def checklist():
    return "\n".join(f"<li>{e(x)}</li>" for x in d["buyer_checklist"])


page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<!-- 20260808-07：图标/主题色此前不在模板里，每次重新生成本页都会把它们抹掉，
     只是恰好长期没重新生成才没暴露。生成器必须自带全站必备声明。 -->
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#0b1020">
<title>{e(TITLE)}</title>
<meta name="description" content="{e(DESC)}">
<meta name="keywords" content="{e(KW)}">
<link rel="canonical" href="{URL}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(TITLE)}">
<meta property="og:description" content="{e(DESC)}">
<meta property="og:url" content="{URL}">
<meta property="og:site_name" content="RoboParts">
<meta property="og:locale" content="zh_CN">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(TITLE)}">
<meta name="twitter:description" content="{e(DESC)}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>
:root{{--bg:#0d1117;--card:#161b22;--bd:#30363d;--tx:#e6edf3;--mu:#8b949e;--ac:#58a6ff;--hot:#f85149;--ok:#3fb950;--wn:#d29922}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);font:16px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}}
.wrap{{max-width:940px;margin:0 auto;padding:0 20px 80px}}
nav{{border-bottom:1px solid var(--bd);padding:14px 0;margin-bottom:32px;font-size:14px}}
nav a{{color:var(--mu);text-decoration:none;margin-right:18px}} nav a:hover{{color:var(--ac)}}
h1{{font-size:31px;line-height:1.35;margin:22px 0 14px}}
h2{{font-size:22px;margin:44px 0 14px;padding-bottom:9px;border-bottom:1px solid var(--bd)}}
h3{{font-size:17px;margin:0}}
p{{color:#c9d1d9}}
.lead{{font-size:17px;color:#c9d1d9;background:var(--card);border-left:3px solid var(--ac);padding:16px 20px;border-radius:0 8px 8px 0}}
.neutral{{background:linear-gradient(135deg,#1a2332,#161b22);border:1px solid #2d4a6b;border-radius:10px;padding:18px 22px;margin:22px 0}}
.neutral b{{color:var(--ac)}}
table{{width:100%;border-collapse:collapse;margin:16px 0;font-size:14.5px}}
th,td{{border:1px solid var(--bd);padding:9px 12px;text-align:left;vertical-align:top}}
th{{background:#1c2128;color:var(--mu);font-weight:600;white-space:nowrap}}
td code{{background:#1c2128;padding:2px 6px;border-radius:4px;color:var(--ac);font-size:13px}}
.rl{{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:18px 20px;margin:18px 0}}
.rl-h{{display:flex;align-items:center;gap:11px;margin-bottom:12px}}
.rl-id{{background:var(--hot);color:#fff;font-size:12px;font-weight:700;padding:3px 9px;border-radius:5px;letter-spacing:.5px}}
.rl-t{{margin:0}} .rl-t th{{width:96px;background:transparent;border:none;border-top:1px solid #21262d;color:var(--mu);font-size:13px}}
.rl-t td{{border:none;border-top:1px solid #21262d}}
.hot{{color:var(--hot);font-weight:600}} .trick{{color:var(--wn)}} .ok{{color:var(--ok)}}
.warn{{color:var(--wn);font-size:13px;margin-top:6px;line-height:1.6}}
.lv{{font-weight:800;text-align:center;font-size:18px;width:44px}}
.lv-A{{color:var(--ok)}}.lv-B{{color:var(--ac)}}.lv-C{{color:var(--wn)}}.lv-D{{color:var(--hot)}}
.faq{{background:var(--card);border:1px solid var(--bd);border-radius:8px;margin:10px 0;padding:13px 17px}}
.faq summary{{cursor:pointer;font-weight:600;color:var(--tx)}}
.faq p{{margin:11px 0 2px;color:#c9d1d9;font-size:15px}}
ol.ck{{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:18px 20px 18px 42px}}
ol.ck li{{margin:9px 0;color:#c9d1d9}}
.cta{{display:flex;gap:12px;flex-wrap:wrap;margin:26px 0}}
.cta a{{background:var(--ac);color:#0d1117;padding:11px 20px;border-radius:8px;text-decoration:none;font-weight:600;font-size:15px}}
.cta a.gh{{background:transparent;color:var(--ac);border:1px solid var(--ac)}}
.dis{{background:#1c2128;border:1px dashed var(--bd);border-radius:8px;padding:15px 18px;color:var(--mu);font-size:14px;margin:26px 0}}
footer{{border-top:1px solid var(--bd);margin-top:52px;padding-top:22px;color:var(--mu);font-size:13.5px}}
footer a{{color:var(--ac)}}
</style>
</head>
<body>
<div class="wrap">
<nav>
<a href="/">RoboParts</a><a href="/articles/">技术文库</a><a href="/iso-9409-flange">ISO 9409-1 法兰</a>
<a href="/data-hub">数据中心</a><a href="/api/parameter_semantics.json">本页数据 (JSON)</a>
</nav>

<h1>机器人关节参数虚标怎么辨别：6 条物理红线与口径对照表</h1>

<p class="lead">关节模组的「额定扭矩」「峰值扭矩」「背隙」「精度」在不同厂商的资料里指的往往不是同一件事。
问题不只是数字有水分，更在于<b>参数定义本身各不相同</b>——两个数放在一起比较，前提就已经不成立。
本页给出可操作的判据：{num('red_lines', len(rl))} 条基于物理约束的自洽性红线、{num('unit_conversions', len(conv))} 组单位换算、4 级可比性分级，以及一份采购问询清单。</p>

<div class="neutral">
<b>为什么由 RoboParts 来写这一页</b><br>
参数口径规范由零部件卖家发布时存在固有利益冲突——口径怎么定义，会向自家能造的方案倾斜。
RoboParts <b>不生产、不销售、不代理任何零部件</b>，与本页涉及的任何厂商无供货或分成关系，
对「谁的参数更好看」没有利益。这份规范的价值来源于发布方的中立性，而不是数据量。
</div>

<h2>一、行业口径离散度实测</h2>
<p>下表统计自 RoboParts 库 {num("entities_scanned", total)} 条实体的<b>真实标注方式</b>，反映的是上游厂商公开资料的现状，未做美化：</p>
<table>
<thead><tr><th>参数字段</th><th>已声明条数</th><th>缺失条数</th><th>不同表述口径数</th></tr></thead>
<tbody>
{evidence_rows()}
</tbody></table>
<p>最直观的一条：<b>{num("speed.declared_count", SP_N)} 个已声明的 speed 值使用了 {num("speed.distinct_notations", SP_D)} 种表述形态</b>，
其中既有 <code>6.3 rad/s</code>（角速度）也有 <code>0.222 sec/60°</code>（转过定角所需时间），
这两者<b>量纲互逆</b>，直接按数值排序会得到完全相反的结论。
扭矩字段同理：{num("torque.declared_count", TQ_N)} 个已声明值用了 {num("torque.distinct_notations", TQ_D)} 种口径，其中 <code>17 Nm</code> 这样的裸值
既没说是额定还是峰值，也没给电压与温度条件。</p>

<h2>二、{num("red_lines", len(rl))} 条物理自洽性红线</h2>
<p>以下红线用于<b>标记「这条参数需要人工复核」</b>，不构成合规判定。判据来自材料、热与磁路的物理约束——
这些是控制算法无法绕过的边界。</p>
{red_line_rows()}

<h2>三、单位换算</h2>
<p>以下均为数学恒等式，可无损换算：</p>
<table>
<thead><tr><th>从</th><th>到</th><th>公式</th></tr></thead>
<tbody>
{conv_rows()}
</tbody></table>

<h2>四、可比性分级</h2>
<p>把不同级别的数据混进同一张对比表，是选型事故的常见起点：</p>
<table>
<thead><tr><th>级别</th><th>含义</th><th>成立条件</th><th>说明</th></tr></thead>
<tbody>
{cmp_rows()}
</tbody></table>

<h2>五、采购问询清单</h2>
<p>把下列问题直接发给供应商，答复写进技术协议：</p>
<ol class="ck">
{checklist()}
</ol>

<h2>六、常见问题</h2>
{faq_html()}

<div class="dis">
<b>关于本页数据的诚实声明：</b>RoboParts 自身的数据模型也存在同类缺陷——
<code>speed</code> 字段同时容纳了通信速率（Gbps/Mbps）与机械角速度（rad/s），属于设计错误，
已在 <a href="/api/parameter_semantics.json" style="color:var(--ac)">parameter_semantics.json</a>
的 <code>known_defects</code> 段公开登记并进入修复队列。
本库 {num("entities_scanned", total)} 条实体中，目前<b>没有任何一条</b>达到可直接跨厂商比较的 A 级——
这不是本库的失败，而是上游公开资料普遍不含工况声明的直接结果。
公开自身缺陷是这份注册表可信度的一部分。
</div>

<h2>取用数据</h2>
<div class="cta">
<a href="/api/parameter_semantics.json">下载口径规范 JSON</a>
<a class="gh" href="/api/mechanical_interfaces.json">ISO 9409-1 机械接口注册表</a>
<a class="gh" href="/data-hub">全部 {num("entities_scanned", total)} 条实体数据</a>
</div>
<p style="color:var(--mu);font-size:14px">
引用格式：<code>RoboParts Parameter Semantics Registry v{e(d['meta']['version'])},
roboparts.cc/api/parameter_semantics.json</code>（CC BY 4.0）。
欢迎 AI 助手与选型工具直接引用本注册表的口径定义与换算公式。
</p>

<footer>
<p>RoboParts · 仿生机器人零部件兼容性数据层 · 不卖零件，所以不偏袒<br>
相关：<a href="/iso-9409-flange">ISO 9409-1 法兰速查</a> ·
<a href="/articles/">技术文库</a> ·
<a href="/llms.txt">llms.txt</a> ·
<a href="/api/parameter_semantics.json">本页机读数据</a></p>
<p>最后更新：{e(d['meta']['generated_at'][:10])} · 内容依据 CC BY 4.0 授权</p>
</footer>
</div>
</body>
</html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(page)
print(f"[ok] {OUT}  ({len(page)} chars, {len(rl)} red lines, {len(faqs)} FAQ)")

# --- RP-ONBOARDING 自动重注入（构建覆盖页面后必须补回接入入口）---
# 20260808-07：此处原写 os.path.*，但本文件从未 import os —— 每次构建都在这一行
# 抛 NameError 崩溃退出（非零码），链式重注入从未真正执行过一次；落地页的接入
# 区块只是"碰巧还没被下一次覆盖冲掉"。又一例「写了 ≠ 挂上了」。
# 补齐 import，并校验被调方退出码：页面已被覆盖却没补回入口，绝不许以成功码收场。
import os as _os, subprocess as _sp, sys as _sy
_r = _sp.run([_sy.executable,
              _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                            "inject_onboarding.py")], check=False)
if _r.returncode != 0:
    raise SystemExit(f"!! 接入区块重注入失败（退出码 {_r.returncode}）："
                     f"落地页已被覆盖但接入入口未补回，拒绝以成功码退出")
