# -*- coding: utf-8 -*-
"""verify_live_numbers.py —— 线上对外数字核验（飞轮每轮必跑）。

为什么必须有这个文件（2026-08-08 19:58 事故 ·「口径 ≠ 事实」第 10 次）：
  第 46 次运行把 14 篇长文里过期又互相矛盾的规模数字占位符化，
  回归全绿（含新增 L1.61）、探活 19/19、推 GitHub 且 tree SHA 自校验一致，
  报告"本次修复"写得理直气壮。**但线上一个字都没变。**
  实测线上仍在对外展示 `493个实体 / 155款执行器 / 103款芯片 / 62条传感器`（真值 706）。
  根因：Cloudflare Pages 并未接 GitHub 自动构建，本机又无 CLOUDFLARE_API_TOKEN，
  `deploy.mjs` 跑不了 —— 「推了 GitHub」被当成了「会自动上线」，是个从未被验证的假设。

  真正的缺口是：**没有任何东西在看"线上正文究竟写了什么"**。
    · regression.py 只读本地文件 —— 本地对了就绿；
    · probe.mjs 只看 HTTP 状态码 —— 页面返回 200 就绿，哪怕正文全是错数字。
  两道"绿灯"合起来仍然放过了"对外低报三到六成"。本脚本补的就是这一格。

判定语义（写脚本时当场纠的一个设计错误，记下来免得再犯）：
  最初直接拿 L1.61 的 `l161_violations` 判线上，自测立刻打脸 ——
  L1.61 管的是**源文件禁字面量**（content/*.md 只准写 `{{RP:...}}`），
  而线上是**渲染后的产物**，占位符本就该变成 `706 个实体` 这样的字面量。
  照搬会把"渲染正确"的页面全判红，闸门天天假红＝等于没有。
  线上要问的不是"有没有数字"，而是 **"这个数字等不等于真相源现算值"**。
  所以：用 L1.61 的正则**定位**哪些数字属于我方口径（复用，不另造口径定义），
  再拿 `onboarding_block.facts()` 现算值**比对数值**。定位与真相源都只有一份。

纪律（三条，都是拿血换的）：
  1. "什么算我方口径"**复用** regression 的 L1.61 正则，绝不另写一套。
     本项目反复栽的坑就是"同一个口径有第二个来源"；再造一个线上专用判定，
     等于亲手制造下一次"本地判绿、线上判红"的对不上。
  2. 带 `X-RoboParts-Selftest` 隔离头，不污染真实遥测（与 probe.mjs 同一纪律）。
  3. 传输层失败（拿不到任何 HTTP 状态）**不判红**，只记 UNKNOWN。
     "本机没网" ≠ "线上失真"（这是 20260808-04 已经踩过的第 8 次口径事故）。

用法：
  python scripts/verify_live_numbers.py            # 核验线上（默认全部长文 + llms.txt）
  python scripts/verify_live_numbers.py --json     # 机读
  python scripts/verify_live_numbers.py --self-test  # 阴阳对照自测（不联网）
"""
import glob
import html as _html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from onboarding_block import facts, stale_count_claims  # 数字的唯一真相源  # noqa: E402
from regression import (  # 口径定义唯一来源  # noqa: E402
    _KIND_ALT, _KIND_NOUNS, _L161_BULLET, _L161_COUNT, _L161_MARKER)

# 口径名词 → 真相源里的键。'TOTAL' 表示实体总数，'CATEGORIES' 表示品类数。
# 这张表是本脚本唯一的"自有知识"，且只做名词到键的翻译，不含任何数值。
#
# 种类档（零部件/规范/软件/企业主体/市场情报）**不在这里手抄**，直接并入
# regression._KIND_NOUNS —— 那张表同时喂给 L1.61 源头闸，两边只能有一份。
# 手抄两份的下场见 L1.69：新增五档口径后这里少了名词，取到数字走
# `key is None → continue` 静默放行，线上播着「694 条零部件」而三道闸门全绿。
_NOUN2KEY = {
    '实体': 'TOTAL', '条目': 'TOTAL',
    '执行器': 'actuators', '芯片': 'chips', '传感器': 'sensors',
    '通信协议': 'protocols', '协议': 'protocols',
    '机器人AI模型': 'robot_ai_models', 'robot_ai_models': 'robot_ai_models',
}
_NOUN2KEY.update(_KIND_NOUNS)
# 与 _L161_COUNT 同构，但**带捕获组**以取出数值与名词（口径边界仍以 _L161_COUNT 为准）
_PAIR = re.compile(
    r'(?<![\d{])(\d{2,4})\s*(?:款|条|个)\s*'
    r'(实体|条目|执行器|芯片|传感器|通信协议|协议|机器人AI模型|robot_ai_models)'
    # 种类口径可以是个位数（企业主体 9 条），且长名词优先（否则「实物零部件」被截半）
    r'|(?<![\d{])(\d{1,4})\s*(?:款|条|个)\s*(' + _KIND_ALT + r')')
_PAIR_CATS = re.compile(r'(?<![\d{])(\d{1,3})\s*大(?:分类|品类)')
_PAIR_BULLET = re.compile(
    r'^\s*-\s*(?:\*\*)?(执行器|传感器|芯片|通信协议|协议|机器人AI模型|robot_ai_models|'
    r'实体|条目|协议库|芯片库|执行器库|传感器库)(?:\*\*)?\s*[:：]\s*(\d{2,4})\s*(?:款|条|个)')
_BULLET_ALIAS = {'协议库': '协议', '芯片库': '芯片', '执行器库': '执行器', '传感器库': '传感器'}


def expected_values(facts_obj):
    """真相源 → {键: 期望值}。纯翻译，不含任何写死的数字。"""
    cats = facts_obj.get('category_counts') or {}
    exp = {'TOTAL': facts_obj['total_entities'], 'CATEGORIES': len(cats)}
    exp.update(cats)
    if facts_obj.get('oss_total') is not None:      # OSS 层总数（供接口核验用）
        exp['OSS_TOTAL'] = facts_obj['oss_total']
    # 种类档：键名与 facts() 一致，靠 _KIND_NOUNS 反查，不在此写死档数
    for key in set(_KIND_NOUNS.values()):
        if facts_obj.get(key) is not None:
            exp[key] = facts_obj[key]
    return exp


def number_mismatches(lines, expected):
    """纯函数：返回 [(行号, 原文, 名词, 实际值, 期望值)] —— 只报**对不上真相源**的。

    只在 L1.61 认定"这一行是我方口径"的行上比对：口径边界不由本函数发明。
    名词无法映射到真相源键时**放行**（宁可漏报也不假红；漏的那类由 L1.61 在源头管）。
    """
    out = []
    for i, line in enumerate(lines, 1):
        is_bullet = bool(_L161_BULLET.search(line))
        if not is_bullet and not (_L161_MARKER.search(line) and _L161_COUNT.search(line)):
            continue
        # _PAIR 有两条分支各带 (数值, 名词) 捕获组 → findall 给出 4 元组，
        # 未命中的那条分支为空串。只取命中的那一对。
        found = []
        for v1, n1, v2, n2 in _PAIR.findall(line):
            if n1:
                found.append((n1, int(v1)))
            elif n2:
                found.append((n2, int(v2)))
        found += [('CATEGORIES', int(v)) for v in _PAIR_CATS.findall(line)]
        m = _PAIR_BULLET.match(line)
        if m:
            noun = _BULLET_ALIAS.get(m.group(1), m.group(1))
            found.append((noun, int(m.group(2))))
        for noun, val in found:
            key = 'CATEGORIES' if noun == 'CATEGORIES' else _NOUN2KEY.get(noun)
            if key is None or key not in expected:
                continue
            if val != expected[key]:
                out.append((i, line.strip(), noun, val, expected[key]))
    return out

TARGET = os.environ.get('PROBE_TARGET', 'https://roboparts.cc')
SELFTEST_HEADERS = {'X-RoboParts-Selftest': '1', 'User-Agent': 'RoboParts-LiveCheck/1.0'}

# 块级标签才断行；行内标签（strong/em/a/code/span）直接抹掉，
# 否则 `<strong>155 款执行器</strong>` 会被拆成孤立片段，
# 使 R1 所需的「自我指称 + 数字」不再同行 —— 检测器会集体假绿。
_BLOCK = re.compile(
    r'</?(?:p|div|li|ul|ol|br|h[1-6]|tr|td|th|section|article|header|footer|nav|table|blockquote|pre)\b[^>]*>',
    re.I)
# 结构化数据（JSON-LD）必须**留下来**参与核验。
#
# 原先 _DROP 把 <script> 一律剜掉，理由是"里面的数字是代码不是正文"——
# 对可执行 JS 成立，对 `application/ld+json` **恰恰相反**：那不是代码，
# 是这一页对外主张的机读副本，而且是 AI 抓取 / GEO 回答实际读的那一份。
# 2026-08-09：线上 Schema.org 里挂着「694 条零部件、3 条市场情报」
# （真相源 507 / 17），页面核验器却因为先剜掉 script 而全程看不见它，
# 于是"专门用来发现线上播错数字"的闸门，漏掉了最机读的那一格。
_LDJSON = re.compile(
    r'<script\b[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S)
_DROP = re.compile(r'<(script|style|template)\b[^>]*>.*?</\1>', re.I | re.S)
_TAG = re.compile(r'<[^>]+>')
# meta description / og:description / twitter:description 也必须参与核验：
# 它们的文字**在标签属性里**，`_TAG.sub('')` 一刀切会连内容一起抹掉 ——
# 于是"搜索结果和社交卡片上展示给人看的那句话"成了核验器唯一看不见的正文。
# 2026-08-09 实测：articles/index.html 的 description/og/twitter 三处都写着 688
# （真值 708），页面核验器全程零告警。
_META = re.compile(
    r'<meta\b[^>]*?(?:name|property)\s*=\s*["\'](?:description|og:description|'
    r'twitter:description|og:title|twitter:title)["\'][^>]*?'
    r'content\s*=\s*["\']([^"\']*)["\']', re.I)
_META_REV = re.compile(  # content 在前、name 在后的写法同样要抓
    r'<meta\b[^>]*?content\s*=\s*["\']([^"\']*)["\'][^>]*?'
    r'(?:name|property)\s*=\s*["\'](?:description|og:description|'
    r'twitter:description|og:title|twitter:title)["\']', re.I)


def html_to_lines(text):
    """纯函数：HTML → 供检测器逐行判定的文本行。

    只做三件事，且顺序不能换：先剜掉 script/style（里面的数字是代码不是正文），
    再把块级标签换成换行（保住"一句话一行"），最后抹掉行内标签（保住同行上下文）。
    不读文件、不取环境值。
    """
    if not text:
        return []
    # 先把 JSON-LD 正文抽出来另存为行（剜 script 之前），它是机读口径不是代码
    ld_lines = [m.strip() for m in _LDJSON.findall(text) if m.strip()]
    # meta 描述文字在属性里，抹标签之前先抽出来（否则永远看不见）
    meta_lines = [_html.unescape(m).strip()
                  for m in _META.findall(text) + _META_REV.findall(text) if m.strip()]
    t = _DROP.sub('\n', text)
    t = _BLOCK.sub('\n', t)
    t = _TAG.sub('', t)
    t = _html.unescape(t)
    return [ln.strip() for ln in t.split('\n')] + ld_lines + meta_lines


def claim_mismatches(lines, expected):
    """纯函数：裸文本数量断言（"收录 688 个机器人零部件实体"）的失配。

    为什么必须有这一趟：`number_mismatches` 只在 L1.61 认定的「我方口径行」上比对，
    而线上真正误导读者的多数是 CTA / meta / JSON-LD 里的裸句——它们没有口径标记，
    上一趟**看都不看**。2026-08-09 第 62 次运行实测：本地全站 22 处陈旧数字
    （data-hub 435+、credits 577、16 篇文章 CTA 688…），L1.62 却报「17 页全绿、
    0 项未核验」。绿的是"锚点"，不是"页面"。
    识别器与静态闸 L1.76 共用 onboarding_block.stale_count_claims，只有一份定义。
    """
    total = expected.get('TOTAL')
    oss = expected.get('OSS_TOTAL')
    if total is None:
        return []
    out = []
    for i, line in enumerate(lines, 1):
        for frag, got, want in stale_count_claims(line, total, oss):
            if want is None:
                continue
            out.append((i, line.strip(), frag, got, want))
    return out


def live_violations(pages, expected):
    """纯函数：pages = [(名称, 原文)] → {名称: [失配...]}，只留对不上真相源的页面。"""
    out = {}
    for name, text in pages:
        lines = html_to_lines(text) if '<' in (text or '') else (text or '').split('\n')
        v = number_mismatches(lines, expected)
        seen = {(a, d) for a, _b, _c, d, _e in v}
        v += [x for x in claim_mismatches(lines, expected)
              if (x[0], x[3]) not in seen]
        if v:
            out[name] = v
    return out


# ---------------------------------------------------------------------------
# 对外 JSON 接口的总数核验（2026-08-08 23:40 第 50 次运行补的盲区）
#
# 为什么单独加这一节：上面那套只看**页面正文**里的中文口径句，覆盖 17 页；
# 但机器读者（Agent / MCP 客户端）拿到的数字来自 JSON 接口，而：
#   · regression.py 只读本地 api/*.json —— 本地对了就绿；
#   · probe.mjs 只看 HTTP 状态码 —— /api/oss?stats=1 返回 200 就绿，哪怕里面是旧总数；
#   · 本脚本原有的页面核验 **完全够不着 OSS 这一轴**：
#     `_NOUN2KEY` 里没有任何 OSS 名词，`live_paths()` 里也没有 /oss、/api/oss。
# 于是「本地 ingest_oss 跑过、部署没生效」这一类失真，三道绿灯一个都拦不住 ——
# 这正是 8/8 那次「线上低报三到六成」的同一族故障，只是换到了 OSS 轴上。
# 此前每轮飞轮靠临时 heredoc 手抓一次，属于「同一口径的第二个来源」，
# 迟早对不上；收进本脚本后，线上核验只有这一个入口。
#
# 判定语义与页面部分保持一致：拿不到响应 = UNKNOWN（不判红）；
# 拿到 200 但数值对不上真相源 = RED（确定性事实）。
#
# 2026-08-09 00:52 第 51 次运行：补第三轴 —— GET /mcp 的机读 dataset。
# 前两条覆盖 REST 接口（人写的集成会读），但 **agent 读者的入口不是它们**：
# 目录站（MCP 官方 Registry / Glama / mcp.so）与 MCP 客户端抓的是 `GET /mcp`
# 自描述卡片里的 `dataset.total_entities`。这一格此前**没有任何东西核验过**：
#   · regression.py 只读本地 api/*.json；
#   · probe.mjs 对 /mcp 只发 POST 且只看状态码 —— 200 就绿；
#   · 本脚本页面段够不着（live_paths() 里没有 /mcp），接口段也没列它。
# 而它恰恰最不该失真：mcp.js 注释已记录过写死 688（真值 706）被 Registry
# 抓走二次分发的旧账。现改为 tryFacts() 运行时现算 —— 但"机制上不会错"是口径，
# 不是事实（这条已连咬 9 次）。两种静默失真仍完全可能：
#   ① tryFacts() 在生产取数失败 → 回落 `total_entities: null`，HTTP 仍 200，
#      三道绿灯全过，目录站记下"数据集大小未知"，而我们永远不会知道；
#   ② 部署没生效（"推 GitHub ≠ 上线"），旧版写死值原地复活。
# 判定沿用同一语义：拿不到响应 = UNKNOWN；200 但 null / 缺字段 / 值不符 = RED。
# 注：GET /mcp 会走 recordMcp 打点，但已按 x-roboparts-selftest 分流到
# `selftest:mcp` 命名空间（functions/mcp.js:171），每小时自检不污染真实遥测。
_API_TOTALS = [
    ('/api/data.json',    ('meta', 'total_entities'), 'TOTAL'),
    ('/api/oss?stats=1',  ('meta', 'total_entities'), 'OSS_TOTAL'),
    ('/mcp',              ('dataset', 'total_entities'), 'TOTAL'),
]


_MISSING = object()


def _dig(obj, path):
    """按键路径取值；任一层缺失返回 _MISSING（区别于"值就是 None"）。"""
    cur = obj
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return _MISSING
        cur = cur[k]
    return cur


def api_total_mismatches(payloads, expected):
    """纯函数：payloads = [(路径, 键路径, 期望键, 已解析对象或 None)] → [(路径, 说明)]。

    只报**确定性失真**，三种：
      ① 200 但不是 JSON（obj is None）—— 对外接口契约已坏；
      ② 键路径缺失 —— 我们承诺过的字段没了，机器读者会读到 undefined；
      ③ 数值 ≠ 真相源。
    数字型字符串（"706"）按数值比对后放行：值是对的，宁漏勿假红。
    期望值由调用方注入，本函数不读真相源、不读环境。
    """
    out = []
    for path, keypath, exp_key, obj in payloads:
        if exp_key not in expected:      # 真相源没有这个口径 → 无从比对，跳过
            continue
        want = expected[exp_key]
        if obj is None:
            out.append((path, '返回 200 但不是合法 JSON（对外接口契约已坏）'))
            continue
        got = _dig(obj, keypath)
        if got is _MISSING:
            out.append((path, '缺少字段 %s（机器读者会读到 undefined）' % '.'.join(keypath)))
            continue
        try:
            got_num = int(str(got).strip())
        except (TypeError, ValueError):
            out.append((path, '%s = %r 不是数字' % ('.'.join(keypath), got)))
            continue
        if got_num != want:
            out.append((path, '%s 线上 %d ≠ 真相源 %d' % ('.'.join(keypath), got_num, want)))
    return out


def _fetch(path, retries=3):
    """取线上内容。返回 (status, text)；连续拿不到响应时 status=0。

    传输层失败要退避重试（与 probe.mjs 同纪律）：部署后紧接着连打十几个请求，
    很容易被 CDN 限流打出一串瞬时失败 —— 本轮就真撞上了 16/17 页抓不到。
    拿到 HTTP 状态（含 4xx/5xx）是确定性事实，不重试。
    """
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(TARGET + path, headers=SELFTEST_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.getcode(), r.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            return e.code, ''
        except Exception:
            if attempt < retries:
                time.sleep(attempt * 1.5)
    return 0, ''


def verdict(checked, unknown, bad):
    """纯函数：(已核验页数, 未核验页数, 失配页数) → (退出码, 结论)。

    为什么单独抽出来测（本轮当场自伤）：第一版在 16/17 页压根没抓到的情况下
    照样打印「✅ 线上数字均与真相源一致」—— 只因唯一抓到的那页恰好没问题。
    **会撒谎的闸门比没有闸门更危险**：它给的绿灯会被下一轮的我当成"线上已验证"。
    所以"没核验"必须是独立的第三态，绝不许坍缩成绿。
    """
    if bad:
        return 1, 'RED'
    if unknown:
        return 2, 'UNKNOWN'
    if checked == 0:
        return 2, 'UNKNOWN'
    return 0, 'GREEN'


def live_paths():
    """线上待核验路径：全部长文（用本地文件名反推 slug）+ llms.txt + 首页。"""
    paths = ['/llms.txt', '/']
    for f in sorted(glob.glob(os.path.join(ROOT, 'articles', '*.html'))):
        slug = os.path.basename(f)[:-5]
        if slug != 'index':
            paths.append('/articles/' + slug)
    return paths


def self_test():
    """阴阳对照：判定逻辑不联网也能测，基准由用例注入、**不向环境取值**。

    L1.58/L1.59 各自因为"判定函数偷偷向环境取基准"假红过一次，这里钉死：
    期望值写在用例里（TOTAL=706 等只是**用例基准**，不是脚本里的硬编码真值）。
    """
    fails = []
    EXP = {'TOTAL': 706, 'CATEGORIES': 10, 'actuators': 217, 'chips': 108,
           'sensors': 90, 'protocols': 64, 'robot_ai_models': 44}

    def check(ok, msg):
        print('  %s %s' % ('✅' if ok else '❌', msg))
        if not ok:
            fails.append(msg)

    # 阳性：全部取自 2026-08-08 线上**实际抓到**的页面片段（不是我编的）
    pos = [
        ('行内标签包裹的过期数字',
         '<p>本文基于 RoboParts 数据集收录的 <strong>155 款执行器</strong>实测参数。</p>'),
        ('整句多个数字全过期',
         '<div>RoboParts数据集覆盖10大分类、493个实体条目，含155款执行器、103款芯片。</div>'),
        ('品类清单项', '<li>- <strong>执行器</strong>：155条，含产线级旋转/线性执行器</li>'),
        ('纯文本 llms.txt 同样能判', 'RoboParts 数据集收录 155 款执行器'),
        ('总数低报', '<p>RoboParts 平台已收录 493 个实体、覆盖 10 大品类</p>'),
    ]
    for why, src in pos:
        check(bool(live_violations([('t', src)], EXP)), '阳性: 判红（%s）' % why)

    # 阴性：这些**必须放行**，否则闸门天天假红、红到没人信
    neg = [
        ('渲染正确的真值不判红', '<p>RoboParts 数据集收录 <strong>706 个实体</strong>。</p>'),
        ('正确的品类数不判红', '<p>RoboParts 数据集含 217 款执行器、108 款芯片。</p>'),
        ('别人的机器人关节数', '<p>单台机器人配备28-45个关节模组，仅此一项成本1万元以上</p>'),
        ('行业统计不是我方口径', '<p>国内人形机器人整机企业已超过140家，发布产品超过330款。</p>'),
        ('script 里的数字是代码不是正文',
         '<script>var stats={entities:493,actuators:155};</script><p>RoboParts 数据集正文无数字。</p>'),
        ('无数字不判红', '<p>RoboParts 数据集以 CC BY 4.0 许可开放，欢迎引用。</p>'),
        ('未知名词放行（宁漏勿假红）', '<p>RoboParts 数据集收录 999 条法规</p>'),
    ]
    for why, src in neg:
        check(not live_violations([('t', src)], EXP), '阴性: 放行（%s）' % why)

    # --- 裸文本断言这一趟（2026-08-09 第 62 次运行补的盲区）----------------
    # 下面五条**全部**是当天在本仓真实存在、且被 L1.62 判成"17 页全绿"的写法。
    # 它们没有 L1.61 口径标记，上一趟看都不看；这一趟必须命中，否则等于没补。
    EXP_OSS = dict(EXP, OSS_TOTAL=325)
    blind = [
        ('文章 CTA：无口径标记的裸句',
         '<p>本文数据来自 RoboParts，收录 <strong>688 个机器人零部件实体</strong>。</p>'),
        ('meta description（抓下来就是正文行）',
         '<meta name="description" content="覆盖 688 个零部件实体的兼容性数据库">'),
        ('JSON-LD 里的机读副本',
         '<script type="application/ld+json">{"description":"收录 688 条零部件实体"}</script>'),
        ('约数写法 435+（今天对不等于明天对）',
         '<div><span>435+</span> 实体，覆盖主流机器人品类</div>'),
        ('开源组件轴同样受管', '<p>已索引 300 个开源组件</p>'),
    ]
    for why, src in blind:
        check(bool(live_violations([('t', src)], EXP_OSS)),
              '阳性(裸文本): 判红（%s）' % why)
    check(not live_violations([('t', '<p>收录 706 个机器人零部件实体、325 开源组件</p>')],
                              EXP_OSS),
          '阴性(裸文本): 等于真值放行（否则天天假红）')
    check(not live_violations([('t', '<p>已索引 300 个开源组件</p>')], EXP),
          '未注入 OSS_TOTAL 时不猜：开源轴放行（宁漏勿假红）')
    check(live_violations([('t', '<p>收录 688 个实体</p>')], EXP)['t'].__len__() == 1,
          '两趟不重复计数：同一句同一数字只报一次')

    # 本脚本唯一的自有逻辑：HTML→行。断错了会让检测器整体假绿，必须单独测。
    two = html_to_lines('<p>甲</p><p>乙</p>')
    check('甲' in two and '乙' in two and not any('甲' in x and '乙' in x for x in two),
          '块级标签断行：两段不粘连（粘连会造出不存在的"同行上下文"）')
    check(any('收录 155 款执行器' in x for x in html_to_lines('<p>收录 <b>155</b> 款执行器</p>')),
          '行内标签抹除后同行上下文保留（否则漏判）')
    check(not any('493' in x for x in html_to_lines('<script>var a=493;</script><p>正文</p>')),
          'script 内容整体剜除')

    probe = [('t', '<p>RoboParts 数据集收录 155 款执行器</p>')]
    check(live_violations(probe, EXP) == live_violations(list(probe), dict(EXP)),
          '隔离性: 同输入同结论（不向环境取值）')
    check(not live_violations([('t', '<p>RoboParts 数据集收录 155 款执行器</p>')],
                              {'actuators': 155}),
          '基准由调用方注入：期望值改成 155 则同一句放行（证明没偷读真相源）')

    # 三态结论：本轮真的自伤过一次 —— 16/17 页压根没抓到，却打印了「✅ 一致」
    check(verdict(1, 16, 0)[1] == 'UNKNOWN', '三态: 抓到1页/漏16页 → UNKNOWN，不许坍缩成绿')
    check(verdict(17, 0, 0) == (0, 'GREEN'), '三态: 全抓到且无失配 → GREEN')
    check(verdict(17, 0, 3)[1] == 'RED', '三态: 有失配 → RED')
    check(verdict(3, 5, 2)[1] == 'RED', '三态: 红优先于未核验（别被"没抓全"洗白）')
    check(verdict(0, 0, 0)[1] == 'UNKNOWN', '三态: 一页没抓到 → UNKNOWN（空集不算通过）')
    check(verdict(1, 16, 0)[0] != 0, '三态: UNKNOWN 退出码非 0（调用方不会误读为成功）')

    # ---- 对外 JSON 接口总数核验（新增段）：阳性 / 阴性 / 隔离性 / 精确盲区 ----
    EXP2 = dict(EXP, OSS_TOTAL=325)
    ok_oss = {'meta': {'total_entities': 325, 'robots': 6}}
    ok_ent = {'meta': {'total_entities': 706}}

    apos = [
        ('OSS 总数落后（本地 ingest 过、线上没生效）',
         [('/api/oss?stats=1', ('meta', 'total_entities'), 'OSS_TOTAL',
           {'meta': {'total_entities': 136}})]),
        ('实体总数落后（部署没生效的经典形态）',
         [('/api/data.json', ('meta', 'total_entities'), 'TOTAL',
           {'meta': {'total_entities': 493}})]),
        ('字段被删（机器读者读到 undefined）',
         [('/api/data.json', ('meta', 'total_entities'), 'TOTAL', {'meta': {}})]),
        ('整段 meta 消失',
         [('/api/data.json', ('meta', 'total_entities'), 'TOTAL', {'data': []})]),
        ('200 但不是 JSON（CDN 错误页顶替了接口）',
         [('/api/data.json', ('meta', 'total_entities'), 'TOTAL', None)]),
        ('值不是数字',
         [('/api/oss?stats=1', ('meta', 'total_entities'), 'OSS_TOTAL',
           {'meta': {'total_entities': 'many'}})]),
    ]
    for why, pl in apos:
        check(bool(api_total_mismatches(pl, EXP2)), '阳性: 接口判红（%s）' % why)

    aneg = [
        ('真值一致放行',
         [('/api/oss?stats=1', ('meta', 'total_entities'), 'OSS_TOTAL', ok_oss),
          ('/api/data.json', ('meta', 'total_entities'), 'TOTAL', ok_ent)]),
        ('数字型字符串按数值比对（值是对的，宁漏勿假红）',
         [('/api/data.json', ('meta', 'total_entities'), 'TOTAL',
           {'meta': {'total_entities': '706'}})]),
        ('多出无关字段不影响判定',
         [('/api/data.json', ('meta', 'total_entities'), 'TOTAL',
           {'meta': {'total_entities': 706, 'updated': 'x'}, 'data': [1, 2]})]),
        ('真相源没有该口径时跳过（不拿不存在的基准假红）',
         [('/api/oss?stats=1', ('meta', 'total_entities'), 'OSS_TOTAL', ok_oss)]),
    ]
    check(not api_total_mismatches(aneg[0][1], EXP2), '阴性: 放行（%s）' % aneg[0][0])
    check(not api_total_mismatches(aneg[1][1], EXP2), '阴性: 放行（%s）' % aneg[1][0])
    check(not api_total_mismatches(aneg[2][1], EXP2), '阴性: 放行（%s）' % aneg[2][0])
    check(not api_total_mismatches(aneg[3][1], {k: v for k, v in EXP2.items()
                                                if k != 'OSS_TOTAL'}),
          '阴性: 放行（%s）' % aneg[3][0])

    p2 = [('/api/oss?stats=1', ('meta', 'total_entities'), 'OSS_TOTAL',
           {'meta': {'total_entities': 136}})]
    check(api_total_mismatches(p2, EXP2) == api_total_mismatches(list(p2), dict(EXP2)),
          '隔离性: 同输入同结论（不向环境取值）')
    check(not api_total_mismatches(p2, dict(EXP2, OSS_TOTAL=136)),
          '基准由调用方注入：期望值改成 136 则同一份 payload 放行（没偷读真相源）')

    # 精确盲区隔离：证明这一段补的不是"别处已经能抓的红"。
    # 把 OSS 落后的接口响应原样喂给**页面正文检测器**，它一声不吭（口径里根本没有 OSS 名词）。
    stale_oss_body = json.dumps({'meta': {'total_entities': 136}}, ensure_ascii=False)
    check(not live_violations([('/api/oss?stats=1', stale_oss_body)], EXP2),
          '精确盲区: 页面正文检测器对"OSS 总数落后"完全放行 ← 只有接口段能抓')
    check(bool(api_total_mismatches(
        [('/api/oss?stats=1', ('meta', 'total_entities'), 'OSS_TOTAL',
          json.loads(stale_oss_body))], EXP2)),
          '精确盲区: 同一份响应，接口段判红（新增段非空转）')
    check(not any('oss' in p.lower() for p in live_paths()),
          '精确盲区: live_paths() 里确实没有任何 OSS 路径（盲区是真的，不是我编的）')

    # ---- GET /mcp 机读 dataset（第三轴，2026-08-09 补）：阳性 / 阴性 / 精确盲区 ----
    MCPK = ('dataset', 'total_entities')
    # ① 取数失败回落 null —— 本轴最独特的失真形态：HTTP 200、结构完整、只是数字没了。
    #    "值不符"型检查若不把 null 当红，目录站会永久记下"数据集大小未知"。
    null_card = {'dataset': {'total_entities': None, 'categories': 10,
                             'note': '本次实体统计取数失败，故不提供条数。'}}
    check(bool(api_total_mismatches([('/mcp', MCPK, 'TOTAL', null_card)], EXP2)),
          '阳性: /mcp dataset.total_entities=null（tryFacts 生产取数失败）判红')
    # ② 部署没生效，旧版写死值复活 —— mcp.js 注释里记录过的真实旧账。
    check(bool(api_total_mismatches(
        [('/mcp', MCPK, 'TOTAL', {'dataset': {'total_entities': 688}})], EXP2)),
        '阳性: /mcp 回到写死的 688（真值 706）判红 ← 正是被 Registry 抓走过的那个错值')
    check(bool(api_total_mismatches(
        [('/mcp', MCPK, 'TOTAL', {'dataset': {'categories': 10}})], EXP2)),
        '阳性: /mcp dataset 整个缺 total_entities 字段判红')
    check(not api_total_mismatches(
        [('/mcp', MCPK, 'TOTAL', {'dataset': {'total_entities': 706,
                                              'selectable': 703}})], EXP2),
        '阴性: /mcp 真值一致放行（不核 selectable —— 真相源无此口径，不自造第二基准）')
    # 精确盲区：同一份"null 卡片"喂给页面正文检测器，它一声不吭；
    # 且 live_paths() 里根本没有 /mcp —— 证明这一格只有本段够得着。
    null_body = json.dumps(null_card, ensure_ascii=False)
    check(not live_violations([('/mcp', null_body)], EXP2),
          '精确盲区: 页面正文检测器对"/mcp 数字丢失"完全放行')
    check(not any(p == '/mcp' or p.startswith('/mcp') for p in live_paths()),
          '精确盲区: live_paths() 里确实没有 /mcp（盲区是真的）')

    print('\n%s' % ('❌ 自测失败 %d 项' % len(fails) if fails else '✅ 自测全绿'))
    return 1 if fails else 0


def main():
    if '--self-test' in sys.argv:
        print('=== verify_live_numbers 阴阳对照自测（不联网）===')
        sys.exit(self_test())

    as_json = '--json' in sys.argv
    expected = expected_values(facts())
    pages, unknown = [], []
    for p in live_paths():
        status, text = _fetch(p)
        if status == 0:
            unknown.append(p)          # 传输层没响应：不判红
        elif status >= 400:
            unknown.append('%s(HTTP %d)' % (p, status))
        else:
            pages.append((p, text))

    bad = live_violations(pages, expected)

    # 对外 JSON 接口总数（页面正文核验够不着的那一轴）
    api_payloads, api_unknown = [], []
    for path, keypath, exp_key in _API_TOTALS:
        status, text = _fetch(path)
        if status == 0:
            api_unknown.append(path)                       # 传输层没响应：不判红
        elif status >= 400:
            api_unknown.append('%s(HTTP %d)' % (path, status))
        else:
            try:
                obj = json.loads(text)
            except Exception:
                obj = None                                 # 200 但非 JSON → 交给判定函数判红
            api_payloads.append((path, keypath, exp_key, obj))
    api_bad = api_total_mismatches(api_payloads, expected)

    code, state = verdict(len(pages) + len(api_payloads),
                          len(unknown) + len(api_unknown),
                          len(bad) + len(api_bad))

    if as_json:
        print(json.dumps({
            'target': TARGET, 'state': state, 'checked': len(pages), 'unknown': unknown,
            'expected': expected, 'violating_pages': len(bad),
            'violations': {k: ['%s: 线上%s ≠ 真相源%s' % (n, a, e) for _, _, n, a, e in v[:4]]
                           for k, v in bad.items()},
            'api_checked': [p for p, _, _, _ in api_payloads],
            'api_unknown': api_unknown,
            'api_violations': ['%s: %s' % (p, m) for p, m in api_bad],
        }, ensure_ascii=False, indent=2))
    else:
        print('=== 线上对外数字核验 · %s · 隔离头已带 ===' % TARGET)
        print('真相源现算: 实体 %s / 品类 %s / OSS %s'
              % (expected['TOTAL'], expected['CATEGORIES'], expected.get('OSS_TOTAL', 'n/a')))
        print('已核验 %d 页；未核验 %d 页 %s' % (len(pages), len(unknown), unknown[:6] or ''))
        print('已核验 %d 个对外接口；未核验 %d 个 %s'
              % (len(api_payloads), len(api_unknown), api_unknown[:4] or ''))
        for name, v in bad.items():
            pairs = sorted({'%s 线上%s≠真值%s' % (n, a, e) for _, _, n, a, e in v})
            print('❌ %-58s %s' % (name, '；'.join(pairs[:4])))
        for path, msg in api_bad:
            print('❌ %-58s %s' % (path, msg))
        if state == 'RED':
            print('\n❌ 页面失配 %d/%d；对外接口失配 %d/%d。'
                  % (len(bad), len(pages), len(api_bad), len(api_payloads)))
            print('   注意：本地回归绿 + 探活 200 都**不能**排除这个红 ——'
                  '它恰恰说明线上跑的不是当前代码，多半是没部署成功。')
        elif state == 'UNKNOWN':
            print('\n⚠️  未核验 %d 项 —— 这**不是**绿灯，只是没看到。'
                  % (len(unknown) + len(api_unknown)))
            print('   先确认本机出网/是否被限流，再重跑；别把"没看到"当成"没问题"。')
        else:
            print('\n✅ 线上 %d 页 + %d 个对外接口的数字均与真相源一致（0 项未核验）'
                  % (len(pages), len(api_payloads)))

    sys.exit(code)


if __name__ == '__main__':
    main()
