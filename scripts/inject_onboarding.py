# -*- coding: utf-8 -*-
"""
inject_onboarding.py —— 把可执行接入入口下沉到 AI 实际抓取的页面
=================================================================

为什么需要这一步：
    遥测（scripts/read_metrics.py）显示 AI 爬虫抓取分布为
        /articles/*   30%
        /robots.txt   33%
        /llms.txt      3.3%
    而此前接入入口只写在 llms.txt 与 agent-discovery.json。
    爬虫抓走最多的那批页面里，没有任何可执行的下一步 —— 曝光到此为止。

本脚本幂等地把 onboarding_block 注入到：
    index.html / articles/*.html / iso-9409-flange.html / robot-joint-parameter-spec.html

幂等实现：以 RP-ONBOARDING:START / END 注释包裹，重复运行为替换而非追加。
构建脚本（build_articles.py 等）重跑会覆盖页面，届时重跑本脚本即可；
regression L1.13 会在缺失时阻断部署，不依赖人记得跑。
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from onboarding_block import html_block, ld_action, facts, MARK_START, MARK_END  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LD_START = '<!-- RP-ONBOARDING-LD:START -->'
LD_END = '<!-- RP-ONBOARDING-LD:END -->'

STYLE = """<style>
/* RP-ONBOARDING scoped styles */
.rp-onboard{max-width:880px;margin:48px auto 0;padding:28px 24px;border:1px solid rgba(128,128,128,.28);
border-radius:12px;background:rgba(128,128,128,.05);font-size:15px;line-height:1.75}
.rp-onboard h2{margin:0 0 10px;font-size:20px}
.rp-onboard h3{margin:22px 0 8px;font-size:15px;opacity:.9}
.rp-onboard .rp-lead{margin:0 0 4px;opacity:.9}
.rp-onboard pre.rp-code{margin:8px 0;padding:14px 16px;overflow-x:auto;border-radius:8px;
background:rgba(0,0,0,.06);border:1px solid rgba(128,128,128,.22);font-size:13px;line-height:1.6}
.rp-onboard code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.rp-onboard ul{margin:8px 0;padding-left:22px}
.rp-onboard li{margin:5px 0}
.rp-onboard .rp-neutral{margin-top:20px;padding-top:16px;border-top:1px dashed rgba(128,128,128,.32)}
@media (prefers-color-scheme:dark){.rp-onboard pre.rp-code{background:rgba(255,255,255,.06)}}
</style>"""

# STYLE 早期版本未被 MARK_START/END 包裹，strip_marked 剥不掉它 ——
# 于是每跑一次就往 </body> 前多塞一份，17 个页面累计出 107 份死重复 CSS。
# 这里按「签名」剥离所有历史副本（含无标记的legacy），使注入器自愈且真正幂等。
# 前后空白一起吃：注入时会补一个 \n，剥离若不对称就会每轮多留一个换行（仍是不幂等）。
STYLE_SIG_RE = re.compile(
    r'\n*[ \t]*<style>\s*/\* RP-ONBOARDING scoped styles \*/.*?</style>[ \t]*\n*',
    re.S,
)

TARGETS = ['index.html', 'iso-9409-flange.html', 'robot-joint-parameter-spec.html']


def targets():
    out = [os.path.join(ROOT, t) for t in TARGETS]
    out += sorted(glob.glob(os.path.join(ROOT, 'articles', '*.html')))
    return [p for p in out if os.path.isfile(p)]


def refresh_targets():
    """只保鲜数字、不注入区块的范围 = 全站 HTML（根目录 + articles/）。"""
    out = sorted(glob.glob(os.path.join(ROOT, '*.html')))
    out += sorted(glob.glob(os.path.join(ROOT, 'articles', '*.html')))
    return [p for p in out if os.path.isfile(p)]


def strip_marked(text, start, end):
    # 连同前后空行一起吃掉：否则每剥一次就在 </head> 前留一个空行，逐轮堆积
    return re.sub(
        r'\n*[ \t]*' + re.escape(start) + r'.*?' + re.escape(end) + r'[ \t]*\n*',
        '', text, flags=re.S,
    )


# --------------------------------------------------------- 全页数字锚点刷新
# 【20260809-15】此前 data-rp 锚点只存在于 onboarding 区块内，而区块每轮由
# facts() 整体重生成，所以"页面数字自动跟真值"这件事**只在区块里成立**。
# 区块之外的正文（首页 hero、三步说明…）想引用总数，只能手写死数字——
# 15:30 那次首页改版就在正文里写下了「700+ 实体、300+ 开源组件」，
# 它不在任何锚点内，L1.62 线上核验按锚点解析，抓不到它，于是这行会
# 一路陈旧下去：库涨到 800 它仍写 700+，属于本项目反复栽的"低报"家族。
# 这里把锚点刷新扩成**全页生效**：任何位置的 <span data-rp="KEY">…</span>，
# 只要 KEY（去掉尾部序号）在真相源里有对应整数值，就按真值重写。
# 于是正文引用总数变成机械保鲜的，而不是"记得手改"。幂等：值相同即无改动。
ANCHOR_KEYS = (
    'credits', 'rate_limit', 'total_entities', 'component_entities',
    'specification_entities', 'software_entities', 'organization_entities',
    'market_intelligence_entities', 'oss_total', 'mech_declared',
    'mech_applicable', 'comparable_grade_a',
    'caee060_relevant',            # 子集口径，供 SUBSET_RULES 用
)
ANCHOR_RE = re.compile(r'(<span data-rp="([a-z_]+?)(\d*)"\s*>)([^<]*)(</span>)')


# ------------------------------------------------------------ 子集口径保鲜
# 【20260809-15】总数有 L2「七处一致」盯着，**子集数字没有任何人盯**。
# llms.txt 里「451 条实体落在其作用域内（caee060_relevant: true）」写死了三周，
# 真值早已是 469。这类数字比总数更危险：它不参与任何一致性比对，
# 而且外部 AI 抓 llms.txt 的比例最高。这里按「限定语 + 真相源键」逐条现算重写。
SUBSET_RULES = (
    # (文件, 正则(必须恰有一个 (\d+) 捕获组), 真相源键)
    ('llms.txt',
     re.compile(r'(?<![\d.])(\d{2,5})(?=\s*条实体落在其作用域内)'),
     'caee060_relevant'),
)


def refresh_subsets(fact_map, write=True):
    """子集口径按真相源现算重写。返回 [(文件, 旧值, 新值)]（无改动则不列）。"""
    changed = []
    for rel, pat, key in SUBSET_RULES:
        if key not in fact_map:
            continue
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as f:
            src = f.read()
        hits = [int(m.group(1)) for m in pat.finditer(src)]
        if not hits:
            # 限定语被改写 → 规则失效而无人知晓。宁可吵，也不要静默失管。
            raise SystemExit('!! 子集保鲜规则在 %s 中零命中（键 %s）：'
                             '限定语被改过？规则失效等于这条数字重新无人维护' % (rel, key))
        out = pat.sub(str(fact_map[key]), src)
        if out != src:
            changed.append((rel, hits, fact_map[key]))
            if write:
                with open(path, 'w', encoding='utf-8', newline='') as f:
                    f.write(out)
    return changed


def refresh_anchors(src, fact_map):
    """把全页 data-rp 整数锚点刷成真值。非整数锚点（mech_pct / mcp_endpoint 等）
    与未知 KEY 一律原样放过——宁可不管，也不要猜着改。"""
    def _sub(m):
        key = m.group(2)
        if key not in fact_map:
            return m.group(0)
        return '%s%d%s' % (m.group(1), fact_map[key], m.group(5))
    return ANCHOR_RE.sub(_sub, src)


# ------------------------------------------------ 区块外「裸文本」数量断言保鲜
# 【20260809-15】锚点方案有个够不着的地方：<meta name="description">、og:/twitter:
# 描述、页面级 JSON-LD 里的数字是**属性值**，塞不进 <span>。于是这些位置的总数
# 只能手写，然后一路陈旧。本轮全站实扫的结果：
#     data-hub.html      「9 大品类 435+ 实体」   真值 708 —— 低报 39%
#     articles/index.html「基于 688 个实体」×5    （meta/og/twitter/JSON-LD/正文）
#     mcp-guide.html     「688 实体 / 325 开源组件」
# 而 L1.62 线上核验当轮报「17 页 0 项未核验」——因为它按 data-rp 锚点解析，
# 这些裸文本它压根不看。**核验器的覆盖面被当成了全站覆盖**，是本项目
# "口径≠事实"家族的又一次现形。这里把区块外的裸文本数量断言也纳入机械保鲜。
BARE_TOTAL_RE = re.compile(r'(?<!\d)(\d{2,5})\s*\+?\s*(个|条)?\s*(机器人零部件实体|零部件实体|实体)')
BARE_OSS_RE = re.compile(r'(?<!\d)(\d{2,5})\s*\+?\s*(个|条)?\s*开源(项目)?组件')
# 锚点内的数字归 refresh_anchors 管，裸文本 pass 必须看不见它们。
# 曾用 (?<![\d>]) 排除「紧跟 > 的数字」来躲开 </span>——但那把 <td>688 实体、
# <strong>688 个…实体</strong> 这类**紧跟任意标签**的真陈旧数字一并放过了
# （promotion.html / articles/index.html 底部 CTA 就这样漏网）。
# 改成先把锚点整体挖成占位符，再跑裸文本 pass，最后填回：范围精确，不靠猜。
_MASK = '\x00RPANCHOR%d\x00'


def refresh_bare_counts(src, total, oss):
    """把区块外的「N 个/条 实体」「N 个开源组件」重写为真值（并去掉约数的 +）。
    量词原样保留，只换数字，不改写文案语气。"""
    kept = []

    def _mask(m):
        kept.append(m.group(0))
        return _MASK % (len(kept) - 1)
    src = ANCHOR_RE.sub(_mask, src)

    src = BARE_TOTAL_RE.sub(lambda m: '%d %s%s' % (total, m.group(2) or '', m.group(3)), src)
    src = BARE_OSS_RE.sub(lambda m: '%d %s开源%s组件'
                          % (oss, m.group(2) or '', m.group(3) or ''), src)

    for i, raw in enumerate(kept):
        src = src.replace(_MASK % i, raw)
    return src


MANAGED_RE = re.compile(
    r'(%s.*?%s|%s.*?%s)' % (re.escape(LD_START), re.escape(LD_END),
                            re.escape(MARK_START), re.escape(MARK_END)),
    re.S,
)


def apply_refresh(src, fact_map):
    """全页保鲜：区块内（LD / MARK）本就由 facts() 整体重生成，原样保留；
    区块外的裸文本数量断言与 data-rp 锚点按真值重写。幂等：值相同即无改动。"""
    if not fact_map:
        return src
    total = fact_map.get('total_entities')
    oss = fact_map.get('oss_total')

    parts = MANAGED_RE.split(src)
    out = []
    for seg in parts:
        if seg.startswith(LD_START) or seg.startswith(MARK_START):
            out.append(seg)          # 生成物，不二次加工
        elif total is not None and oss is not None:
            out.append(refresh_bare_counts(seg, total, oss))
        else:
            out.append(seg)
    return refresh_anchors(''.join(out), fact_map)


def refresh_only(path, fact_map):
    """对非注入目标页（pricing / data-hub / mcp-guide / 404 …）只做数字保鲜，
    不注入接入区块——它们的版式不适合塞长区块，但数字同样不许陈旧。"""
    with open(path, encoding='utf-8') as f:
        src = f.read()
    new = apply_refresh(src, fact_map)
    if new == src:
        return 'unchanged'
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new)
    return 'ok'


def inject(path, block, ld_tag, fact_map=None):
    with open(path, encoding='utf-8') as f:
        src = f.read()
    orig = src

    # 先剥离旧块，保证重复运行是替换而非叠加
    src = strip_marked(src, MARK_START, MARK_END)
    src = strip_marked(src, LD_START, LD_END)
    src = STYLE_SIG_RE.sub('', src)  # 剥掉全部历史 style 副本（含无标记的 legacy）

    if '</body>' not in src or '</head>' not in src:
        return 'skip(结构不符)'

    payload = '\n' + STYLE + '\n' + block + '\n'
    src = src.replace('</body>', payload + '</body>', 1)
    src = src.replace('</head>', '\n' + ld_tag + '\n</head>', 1)

    src = apply_refresh(src, fact_map)

    if src == orig:
        return 'unchanged'
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(src)
    return 'ok'


def build_ld_tag():
    """抽出来是为了让回归的行为对照能用到与生产**同一条**字符串，
    而不是在测试里另写一份（那样测的就不是真东西了）。"""
    return ('%s<script type="application/ld+json">%s</script>%s'
            % (LD_START,
               json.dumps(ld_action(), ensure_ascii=False, separators=(',', ':')),
               LD_END))


def fact_map():
    """真相源里可直接写进锚点的整数项。缺一项即视为该 KEY 不受管，不猜不补。"""
    f = facts()
    return {k: f[k] for k in ANCHOR_KEYS if isinstance(f.get(k), int)}


def main():
    block = html_block()
    ld_tag = build_ld_tag()
    fm = fact_map()

    files = targets()
    if not files:
        print('!! 未找到任何目标页面')
        return 1

    stats = {}
    for p in files:
        r = inject(p, block, ld_tag, fm)
        stats[r] = stats.get(r, 0) + 1
    print('接入区块注入完成：%d 个页面 %s'
          % (len(files), ' '.join('%s=%d' % kv for kv in sorted(stats.items()))))
    print('   覆盖：index / 2 落地页 / %d 篇文章'
          % len([p for p in files if os.sep + 'articles' + os.sep in p]))

    # 数字保鲜扩到全站 HTML：注入目标之外的页面（data-hub / mcp-guide / 404 …）
    # 同样会写总数，且此前无任何机制维护它们。
    done = set(files)
    extra = [p for p in refresh_targets() if p not in done]
    stats2 = {}
    for p in extra:
        r = refresh_only(p, fm)          # 只调一次：这是写文件的副作用函数
        stats2[r] = stats2.get(r, 0) + 1
    print('数字保鲜（非注入目标）：%d 个页面 %s'
          % (len(extra), ' '.join('%s=%d' % kv for kv in sorted(stats2.items()))))

    sub = refresh_subsets(fm)
    print('子集口径保鲜：%d 条规则 %s'
          % (len(SUBSET_RULES),
             'unchanged' if not sub
             else ' '.join('%s %s→%d' % (r, o, n) for r, o, n in sub)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
