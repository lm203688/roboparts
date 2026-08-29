#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""聚合读取边缘遥测指标（GEO 曝光 / 访问信号）。

配套 functions/_middleware.js 的埋点。指标按天分 16 片写入 KV，
本脚本把分片合并成人类可读的日报口径。

用法：
    python scripts/read_metrics.py              # 今天
    python scripts/read_metrics.py 2026-08-06   # 指定日期
    python scripts/read_metrics.py --no-probe   # 不回探线上（离线时用）

为什么不开 HTTP 端点：运营数据一旦公开就是新的攻击面/情报泄露面，
读取走 wrangler 本地凭据即可，无需对外暴露。
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NS = 'f01526d743c24e1a91b2586a865f4864'  # USER_CREDITS
SHARDS = 16
SITE = 'https://roboparts.cc'


def probe_404(path, timeout=10):
    """回探一条被记为 404 的路径，判断它**现在**是否仍是死链。

    【20260807-19】为什么必须回探：404 计数是"当天累计"，一条中午修好的死链
    会在剩下的一整天里继续喊"需修"。今天就有 5/6 条属于此类（agent.json、
    glama.json、/mcp、/api/register、/api/validate 均已在 17-18 点修复）。
    代价不是多看几行 —— 而是真正新增的死链会被埋在一堆已修条目里，
    读的人很快学会跳过 ⛔ 那一行。告警一旦长期为真却无需动作，就等于没有告警。

    返回 'broken' | 'fixed' | 'unknown'：
    - HEAD 与 GET **任一** 仍返回 404 即判 broken（今日教训：HEAD 404 / GET 200
      对目录站与链接检查器而言就是下线，不能因为 GET 通了就算修好）。
    - 网络异常返回 unknown，调用方按"仍需处理"对待：
      绝不允许一次连不上网就把告警清成绿的。
    """
    if not path.startswith('/'):
        return 'unknown'                      # scan/other 是聚合桶，不是真实路径
    seen = []
    for method in ('HEAD', 'GET'):
        try:
            req = urllib.request.Request(
                SITE + path, method=method,
                headers={'User-Agent': 'roboparts-flywheel/404-recheck'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                seen.append(r.status)
        except urllib.error.HTTPError as e:
            seen.append(e.code)               # 400/405 等自述响应 = 路由活着
        except Exception:
            return 'unknown'
    return 'broken' if 404 in seen else 'fixed'


# 我方对外公布路径的地方。仍在死的路径若出现在这里 = 我们承诺过却敲不开（P0）；
# 没出现 = 外部瞎猜或我方临时误敲（P1），不该和前者抢同一条待办。
ADVERTISED_IN = ('llms.txt', 'sitemap.xml', 'agent-discovery.json',
                 'api/openapi.json', '.well-known/agent.json', 'README.md',
                 'robots.txt')

# 浏览器 / 搜索引擎 / 平台按约定主动请求的路径。即便这些路径没有显式出现在任何
# 清单里，它们的缺失仍然是站点缺陷，必须归为 P0 承诺违约（例如 favicon.ico、
# apple-touch-icon.png）。否则就像把"别人敲门你没答应"算成"别人敲错了"。
CONVENTIONAL_ADVERTISED_PREFIXES = (
    '/favicon.ico',
    '/favicon.svg',
    '/apple-touch-icon',
    '/robots.txt',
    '/sitemap.xml',
)

# /.well-known/ 是**命名空间**，不是单个约定路径。里面既有我方确实提供的发现文件
# （agent.json / mcp.json / glama.json…），也有各家目录站、扫描器按自家私有协议
# 乱探的路径（mcp-verify-claim.txt、security.txt、apple-app-site-association…）。
# 把整个前缀视为"我方已承诺"会让任何一次陌生探测都变成 P0，告警很快失去意义
# —— 这与 favicon 那次是同一个病根的反面：口径必须贴着事实，宁精勿宽。
# 正确口径：该 well-known 路径我方**确实打算提供**（仓库里有这个文件），
# 或被我方清单显式公布，才算承诺；否则是外部探测，不占 P0 名额。
WELLKNOWN_PREFIX = '/.well-known/'


def is_advertised(path, root='.'):
    """该路径是否被外部视为"这个站点应该提供的"。

    判定口径：
      1. 出现在我方主动公开清单（llms.txt / sitemap.xml / README.md 等）→ 已公布；
      2. 属于浏览器/搜索引擎约定必请求的路径（favicon / apple-touch-icon /
         robots.txt / sitemap.xml）→ 也视为已公布，缺了就是真缺陷；
      3. /.well-known/ 下的路径：仓库里存在同名文件（= 我方打算提供）才算承诺，
         否则视为外部探测，不计入 P0；
      4. 读不到文件按"未宣传"处理。
    """
    path_lower = path.lower()
    if any(path_lower.startswith(pre.lower()) for pre in CONVENTIONAL_ADVERTISED_PREFIXES):
        return True

    if path_lower.startswith(WELLKNOWN_PREFIX):
        # 只认"我方仓库里真有这个文件"——线上 404 才是部署掉件的真缺陷
        rel_local = path.lstrip('/').replace('/', os.sep)
        if os.path.isfile(os.path.join(root, rel_local)):
            return True
        # 未命中则继续走下面的"是否被我方清单公布"判定，不在此处直接放行

    for rel in ADVERTISED_IN:
        p = os.path.join(root, rel)
        try:
            with open(p, encoding='utf-8') as f:
                if _mentions_path(f.read(), path):
                    return True
        except Exception:
            continue
    return False


# 路径续接字符：命中处后面紧跟这些字符，说明匹配到的是**更长路径的前缀**，
# 不能算"这条路径被公布过"。
_PATH_TAIL = r'[A-Za-z0-9._~%\-/]'


def _mentions_path(text, path):
    """清单文本里是否**公布了这条路径本身**（而不是它的某个更长同前缀兄弟）。

    【20260811-19】修一处假红：原实现是 `if path in f.read()` 纯子串匹配。
    llms.txt 公布的是 `/.well-known/mcp.json`，于是探测流量里的
    `/.well-known/mcp`（无 .json，我方从未承诺）被判成
    「P0 我方死链：已对外公布却敲不开」。回探实证：
      /.well-known/mcp.json → 200（我方真正公布的那条，好的）
      /.well-known/mcp      → 404（外部猜测，本不该出现在 P0）
    假红比漏报更致命：它会催人去"修"一条本不存在的承诺，
    甚至为了消红新建一个我方从未打算提供的文件。

    口径：命中处必须落在路径**词元边界**上 —— 后面不能紧跟路径续接字符；
    允许一个可选的收尾 `/`（清单里常写 `/oss/` 这种带尾斜杠的形式）。
    """
    if not text or not path:
        return False
    return re.search(re.escape(path) + r'/?(?!' + _PATH_TAIL + r')', text) is not None


def _selftest_advertised():
    """阴阳对照 + 鉴别力自证（对冻结的旧实现实跑，两版结论必须相反）。"""
    bad = 0
    manifest = (
        '- 清单文件：`/.well-known/mcp.json` · `/server.json` · `/smithery.yaml`\n'
        '- 数据接口：`/api/data.json`\n'
        '- 页面：https://roboparts.cc/oss/ 与 https://roboparts.cc/pricing\n'
        '- MCP 端点：https://roboparts.cc/mcp\n'
    )
    cases = [
        # 阳性：清单里确实公布了这条路径本身
        ('/.well-known/mcp.json', True),
        ('/api/data.json', True),
        ('/oss', True),        # 清单写成带尾斜杠，仍算公布
        ('/pricing', True),
        ('/mcp', True),
        # 阴性：只是某条已公布路径的**前缀**，我方从未承诺
        ('/.well-known/mcp', False),          # ← 本轮真实假红
        ('/api/data', False),
        ('/serv', False),
        ('/mcp/.well-known/owners.json', False),
        ('/smithery', False),
    ]
    for path, want in cases:
        got = _mentions_path(manifest, path)
        if got != want:
            print(f'  ❌ 清单口径失配: {path} 期望={want} 实得={got}')
            bad += 1
    # 空输入不得平凡成立（L1.88）
    if _mentions_path('', '/mcp') or _mentions_path(manifest, ''):
        print('  ❌ 空输入下不得判「已公布」')
        bad += 1
    # 鉴别力自证：冻结旧实现（纯子串）在同一输入上必须给出相反答案
    old = '/.well-known/mcp' in manifest          # 旧实现 = True（假红来源）
    new = _mentions_path(manifest, '/.well-known/mcp')   # 新实现 = False
    if old is True and new is False:
        print('  ✅ 鉴别力自证：/.well-known/mcp 上 旧实现=已公布(假红) / '
              '新实现=未公布（结论相反，非空转）')
    else:
        print(f'  ❌ 鉴别力自证失败：旧={old} 新={new}（两版未相反 ⇒ 新口径可能空转）')
        bad += 1
    print('  ✅ 阴阳对照通过（阳 5 / 阴 5 / 空输入 2 / 鉴别力 1）' if bad == 0
          else f'  ❌ 阴阳对照失败 {bad} 项')
    return bad == 0


def kv_get(key):
    """读单个 KV 键；不存在返回 None。"""
    try:
        r = subprocess.run(
            ['npx', 'wrangler', 'kv', 'key', 'get', key,
             f'--namespace-id={NS}', '--remote'],
            capture_output=True, text=True, timeout=90, shell=True,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return json.loads(r.stdout.strip())
    except Exception:
        return None


# 第三方探针 / 目录站爬虫的自报名特征。它们的调用**不是**市场需求信号。
# 上一轮把这些读成"真实 Agent 接入"，是"自检探针污染"这个坑的第三种形态：
# 第一种是自己的探针，第二种是自己的乐观，第三种是别人的探针。
PROBE_RE = re.compile(
    r'probe|verifymcp|enricher|scanner|health[-_]?check|monitor|inspector'
    r'|uptime|crawler|registry|smoke|benchmark|[-_]discovery$|^test',
    re.I)
# 只有这些被调用，才说明有人真的在用 RoboParts 解决兼容性问题。
# 必须与 functions/mcp.js 的 TOOLS 数组逐个对齐，由 L1.19 断言交叉核对：
# 漏一个，该工具的真实调用就会被统计成 0 —— 又一次「把未知读成零」。
BUSINESS_TOOLS = ('search_components', 'get_component_detail',
                  'check_compatibility', 'recommend_for_application',
                  'get_parameter_semantics', 'bom_compatibility_check',
                  'semantic_search', 'get_standard_audit')


def mcp_report(total, n):
    """MCP 段分账：握手 / 业务调用 / 探针 client，三者不可混计。

    判据：tools_list、initialize、discovery_get 只是"看一眼目录"，
    任何爬虫都会做；只有 BUSINESS_TOOLS 被调用才是真实使用。
    """
    items = {k[len('mcp:'):]: v for k, v in total.items()
             if k.startswith('mcp:')}
    if not items:
        return
    print('\n[MCP 端点]  ← 唯一可归因的 Agent 接入通道')

    handshake = {k: v for k, v in items.items()
                 if k in ('initialize', 'tools_list', 'discovery_get')}
    tools = {k[len('tool:'):]: v for k, v in items.items()
             if k.startswith('tool:')}
    clients = {k[len('client:'):]: v for k, v in items.items()
               if k.startswith('client:')}
    # toolsrc:<kind>:<tool> —— 调用现场写下的归因线（functions/mcp.js）。
    # 只有它能回答"这次业务调用是谁打的"；client:* 来自 initialize，
    # 与 tool:* 分属两个无状态请求，**永远不可相减**。
    srcs = {}
    for k, v in items.items():
        if k.startswith('toolsrc:'):
            rest = k[len('toolsrc:'):]
            kind, _, tool = rest.partition(':')
            srcs.setdefault(tool, {})[kind] = srcs.setdefault(tool, {}).get(kind, 0) + v
    other = {k: v for k, v in items.items()
             if k not in handshake
             and not k.startswith(('tool:', 'client:', 'toolsrc:'))}

    probe_c = {k: v for k, v in clients.items() if PROBE_RE.search(k)}
    real_c = {k: v for k, v in clients.items() if k not in probe_c}
    biz = {k: v for k, v in tools.items() if k in BUSINESS_TOOLS}
    probe_t = {k: v for k, v in tools.items()
               if k not in biz and PROBE_RE.search(k)}
    unknown_t = {k: v for k, v in tools.items()
                 if k not in biz and k not in probe_t}

    def blk(title, d, mark=''):
        if not d:
            return
        print(f'  {title}{mark}')
        for k, v in sorted(d.items(), key=lambda x: -x[1]):
            pct = f'{v / n * 100:5.1f}%' if n else '    -'
            print(f'    {v:6d}  {pct}  {k}')

    blk('· 协议握手（任何爬虫都会做，不代表使用）', handshake)
    blk('· 业务工具调用', biz, '  ★ 需求信号候选（归因见下）')
    blk('· 未知工具调用', unknown_t)
    blk('· 探针工具（已识别，不计入需求）', probe_t)
    blk('· 探针 / 目录站 client（已识别）', probe_c)
    blk('· 未识别 client（仅握手，无法据此推断谁在调工具）', real_c)
    blk('· 其他 MCP 指标', other)

    # ── 业务调用归因分账 ──────────────────────────────────────────────
    biz_total = sum(biz.values())
    attributed = {}
    for tool, kinds in srcs.items():
        if tool in BUSINESS_TOOLS:
            for kind, v in kinds.items():
                attributed[kind] = attributed.get(kind, 0) + v
    covered = sum(attributed.values())
    if biz_total:
        print('  · 业务调用归因（toolsrc 现场埋点）')
        if covered:
            for kind, v in sorted(attributed.items(), key=lambda x: -x[1]):
                tag = '  ← 探针，不算需求' if kind == 'probe' else ''
                print(f'    {v:6d}         {kind}{tag}')
        gap = biz_total - covered
        if gap > 0:
            print(f'    {gap:6d}         不可归因（埋点上线前的历史数据）'
                  f'  ← 既不能算真实需求，也不能算探针')
    return biz_total, covered, attributed


def main():
    if '--selftest' in sys.argv:
        print('=== read_metrics 判据自测（404 归因口径）===')
        sys.exit(0 if _selftest_advertised() else 3)
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    no_probe = '--no-probe' in sys.argv
    day = args[0] if args else \
        datetime.now(timezone.utc).strftime('%Y-%m-%d')
    total = {}
    found = 0
    for s in range(SHARDS):
        d = kv_get(f'metrics:{day}:s{s}')
        if not d:
            continue
        found += 1
        for k, v in d.items():
            if k.startswith('_'):
                continue
            total[k] = total.get(k, 0) + v

    print(f'=== RoboParts 边缘遥测 · {day} （合并 {found}/{SHARDS} 分片）===')
    print('※ 以下计数均为**下界**，不是精确值。')
    print('  写侧 flushMcp 对 KV 做读-改-写：isolate 内已于 20260806-15 串行化修复，')
    print('  但两个 isolate 若随机取到同一分片并同时写，仍会互相覆盖（尚未消除）。')
    print('  故「实际发生次数 ≥ 此处读数」：可用来证明「至少有」，')
    print('  不能用来证明「只有这么多」或「没有」。')
    print('※ 历史口径警告：**2026-08-08 01:45 之前**，飞轮每轮巡检用裸 curl 打关键路径，')
    print('  未带 x-roboparts-selftest，其请求被记进下方「真实请求数」与「404 归因」。')
    print('  当日阳性对照已实证（哨兵路径裸打 → 进真实 404；带头打 → 只进 selftest）。')
    print('  现已统一走 `node scripts/probe.mjs` + 回归闸门 L1.50 锁死；解读 8/8 之前的')
    print('  「真实流量」与「站点有断链」结论时，须扣除飞轮自造的那部分。')
    if not total:
        print('无数据（当日尚无请求，或埋点未生效）')
        return

    # 自检探针与真实流量严格分账：飞轮自己发的伪造爬虫探针如果混进 GEO 曝光，
    # 会导致下一轮把自己的动作读成市场反馈（同 14:00 测试订单污染事故）。
    selftest = {k[len('selftest:'):]: v for k, v in total.items()
                if k.startswith('selftest:')}
    total = {k: v for k, v in total.items() if not k.startswith('selftest:')}

    n = total.get('total', 0)
    print(f'\n[总量] 真实请求数 {n}'
          + (f'（另有自检探针 {selftest.get("total", 0)} 次，已隔离不计）'
             if selftest else ''))

    def section(title, prefix, note=''):
        items = sorted(((k[len(prefix):], v) for k, v in total.items()
                        if k.startswith(prefix)), key=lambda x: -x[1])
        if not items:
            return
        print(f'\n[{title}]{note}')
        for k, v in items:
            pct = f'{v / n * 100:5.1f}%' if n else '    -'
            print(f'  {v:6d}  {pct}  {k}')

    section('UA 分类', 'ua:')
    section('AI / 搜索爬虫命中', 'bot:', '  ← GEO 曝光核心指标')
    section('页面', 'path:')
    section('外部来源', 'ref:', '  ← 自然流量证据')
    # MCP 端点：functions/mcp.js 写 mcp:<event>（自检写 selftest:mcp:<event>）。
    # 这一段此前缺失 —— 埋点确实写进了 KV，却因为没有对应 section 被静默丢弃，
    # 导致连续三轮"读 metrics:mcp:*"读了个寂寞。埋点与读取端必须成对存在。
    mcp_report(total, n)
    if 'status:404' in total:
        print(f'\n[异常] 404 次数 {total["status:404"]}')
        # 【20260807-16】只有总数是查不出伤口的。必须把两类性质相反的 404 拆开：
        # 我方死链要修（每一次都是 GEO 抓取 / Agent 接入的直接损失），
        # 扫描器噪声不必理会。scan / other 是有界聚合桶，不是具体路径。
        paths = sorted(((k[len('404path:'):], v) for k, v in total.items()
                        if k.startswith('404path:')), key=lambda x: -x[1])
        ours = [(k, v) for k, v in paths if k not in ('scan', 'other')]
        # 回探：把"当天累计计数"里已经修好的历史条目剔出待办，否则告警会
        # 长期为真而无需动作（详见 probe_404 的注释）。离线时全部保守为需修。
        state = {k: ('unknown' if no_probe else probe_404(k)) for k, _ in ours}
        broken = [(k, v) for k, v in ours if state.get(k) != 'fixed']
        if paths:
            print('  · 路径归因')
            for k, v in paths:
                if k == 'scan':
                    tag = '  ← 扫描器噪声，忽略'
                elif k == 'other':
                    tag = '  ← 超界/异形，已聚合'
                elif state.get(k) == 'fixed':
                    tag = '  ← 已修复（当日历史计数，回探非 404）'
                elif state.get(k) == 'unknown':
                    tag = '  ← 需修（未能回探，保守计入）'
                elif is_advertised(k, ROOT):
                    tag = '  ← P0 我方死链：已对外公布却敲不开（回探仍 404）'
                else:
                    tag = '  ← P1 未对外公布的 404（外部猜测/我方误敲，非承诺违约）'
                print(f'     {v:6d}  {k}{tag}')
            fixed_n = sum(1 for s in state.values() if s == 'fixed')
            if fixed_n:
                print(f'  ✅ 其中 {fixed_n} 条已在当日修复，不再计入待办')
        else:
            print('  ⚠️ 无路径归因数据：埋点为 20260807-16 新增，'
                  '此前的 404 无法回溯定位（不等于没有死链）')
        ua = sorted(((k[len('404ua:'):], v) for k, v in total.items()
                     if k.startswith('404ua:')), key=lambda x: -x[1])
        if ua:
            hurt = any(k in ('ai', 'search') for k, _ in ua)
            print('  · 撞 404 的是谁：' + '、'.join(f'{k} {v}' for k, v in ua)
                  + ('  ⚠️ 含 ai/search，正在实伤 GEO' if hurt else ''))
        p0 = [k for k, _ in broken
              if state.get(k) == 'unknown' or is_advertised(k, ROOT)]
        if p0:
            print(f'  ⛔ 需处理：{len(p0)} 条已对外公布却敲不开的路径，'
                  '优先查 llms.txt / sitemap.xml / 文章互链')
        elif broken:
            print(f'  · 无 P0：仅 {len(broken)} 条未对外公布的 404，无需动作')

    # 未归类兜底：任何新埋点若忘了加 section，在这里现形而不是被吞掉。
    # 宁可打印难看，也不要观测盲点 —— 看不见的指标等于没埋。
    known = ('ua:', 'bot:', 'path:', 'ref:', 'mcp:', 'status:', 'total',
             '404path:', '404ua:')
    rest = sorted(((k, v) for k, v in total.items()
                   if not k.startswith(known)), key=lambda x: -x[1])
    if rest:
        print('\n[未归类指标]  ← 已写入 KV 但读取端无对应分段，请补 section')
        for k, v in rest:
            print(f'  {v:6d}         {k}')

    if selftest:
        print('\n[自检探针·已隔离]  ← 飞轮自身产生，不代表任何市场信号')
        for k, v in sorted(selftest.items(), key=lambda x: -x[1]):
            print(f'  {v:6d}         {k}')

    ai = sum(v for k, v in total.items() if k.startswith('bot:'))
    human = total.get('ua:human', 0)
    biz = sum(v for k, v in total.items()
              if k.startswith('mcp:tool:') and k[len('mcp:tool:'):] in BUSINESS_TOOLS)
    # 业务调用的归因只能来自调用现场的 toolsrc:*。
    # 【20260806-11 修正】此处曾打印"（探针 client N 次已剔除）"，而 biz 从未被减过：
    # client:* 记于 initialize，tool:* 记于 tools/call，无状态 HTTP 下分属两个请求，
    # 两条计数线不可相减。那句话把「无法归因」说成了「已归因并剔除」，
    # 使最影响商业判断的指标凭空获得可信度 —— 与 L1.22~L1.25 同族的假绿。
    # 【20260807-08 修正·观测层假绿第 6 例】
    # 此前只把 toolsrc:probe:* 当探针，其余 kind 一律计入"真实需求"。
    # 但 functions/mcp.js 的 callerKind() 对 curl/wget/python-requests 返回 'script' ——
    # **飞轮自己每轮的线上验证 curl 正是 script**。于是本工具把自己的脚印读成了市场需求
    # （本轮实测 7 次 search_components 全部 toolsrc:script，恰好等于我方 curl 次数）。
    # 危害与 L1.26 同族：最影响资源投向的数字（"MCP 有没有人真在用"）凭空获得可信度。
    # 判据改为三分账：明确探针 / **不可归因**（script、空 UA、unknown、bot：既可能是
    # 飞轮自己，也可能是目录扫描，也可能是真集成方，无法区分）/ 可识别的真实调用方。
    # 只有第三类才准计入需求下界。宁可下界为 0，也不许把自检读成需求。
    PROBE_KINDS = {'probe'}
    AMBIGUOUS_KINDS = {'script', 'empty-ua', 'unknown', 'bot'}

    def _kind_of(key):
        # mcp:toolsrc:<kind>:<tool>
        parts = key.split(':')
        return parts[2] if len(parts) >= 4 else 'unknown'

    src_keys = [(k, v) for k, v in total.items()
                if k.startswith('mcp:toolsrc:')
                and k.rsplit(':', 1)[-1] in BUSINESS_TOOLS]
    src_probe = sum(v for k, v in src_keys if _kind_of(k) in PROBE_KINDS)
    src_ambig = sum(v for k, v in src_keys if _kind_of(k) in AMBIGUOUS_KINDS)
    src_all = sum(v for _, v in src_keys)
    src_named = max(src_all - src_probe - src_ambig, 0)   # 可识别的真实调用方
    unattr = max(biz - src_all, 0)                        # 埋点上线前的历史数据
    real_lo = src_named                                   # 需求下界：只认可识别的
    real_hi = real_lo + src_ambig + unattr                # 上界：把说不清的全算上
    print(f'\n[判读] 真实爬虫命中 {ai} 次 / 疑似真人 {human} 次 '
          f'/ MCP 业务调用 {biz} 次')
    if biz:
        print(f'  分账：探针 {src_probe} / 不可归因 {src_ambig + unattr} '
              f'（其中 script 等模糊 UA {src_ambig}、埋点前历史 {unattr}）'
              f'/ 可识别真实调用方 {src_named}')
        print(f'  真实需求区间 [{real_lo}, {real_hi}]'
              + ('' if real_lo else ' —— 下界为 0：目前没有任何一次调用可被证明来自外部真实用户'))
        if src_ambig:
            print(f'  ⚠️ script/空UA 类调用**包含飞轮自身的线上验证 curl**，'
                  f'不得作为"有人在用"的证据')
    if biz == 0:
        print('  ⚠️ MCP 端点被索引但零业务调用 —— 被收录 ≠ 被使用，'
              '瓶颈在"目录里被点开并接上"，不在曝光')
    if ai == 0:
        print('  ⚠️ 尚无任何 AI/搜索爬虫抓取 —— 内容未进入检索侧，GEO 曝光为 0')
    if human == 0:
        print('  ⚠️ 尚无真人访问 —— 漏斗在入口即断，瓶颈确认在获客')


if __name__ == '__main__':
    main()
