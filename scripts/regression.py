#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')
"""
RoboParts 回归测试网关（对应报告 N02 四层测试）
用法：python scripts/regression.py [--url https://roboparts.cc]

层级：
  L1 Schema      : entities.json 元数据自洽 + category 在标准白名单 + 必填字段非空
  L1.5 数据质量闸门: 【N10 20260805 周三新增】棘轮机制 —— 隔离条目数/占位ID数不得
                    超过 scripts/quality-baseline.json 记录的基线。
                    存量债务不阻断发布（否则永远发不出去），但**任何新增劣化立即拦截**，
                    堵住"边治理边灌脏数据"的漏斗。基线只能降不能升，由治理流程下调。
  L2 一致性       : 七处数字（entities.meta / data.js stats / 分类JSON / README / llms.txt / agent-discovery
                    / api/data.json）必须相同，并对 api/data.json 做 ID+category 内容指纹交叉校验
                    【N03 20260805 加固】原六处口径不含 api/data.json，而它正是对外主接口
                    /api/data.json 的数据源，导致其长期漂移（493/65类）却始终"全绿"
  L3 API 冒烟     : 给定 --url 时，校验页面与关键端点（默认跳过）
  L4 业务校验     : 兼容矩阵维度定义完整、示意 pairs 已标记、真实 ID 引用必须存在

退出码：0 = 全部通过（放行发布） / 1 = 存在阻断项（禁止发布）
"""
import glob
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 【20260809-07】CANONICAL 曾在此处**重抄一份**，与 normalize_categories.py 的定义
# 并列存在。两份名单的危害不是"当时不一致"，而是新增类目时**只改一份不会失败**：
# 改了 normalize 而漏了这里 → 数据合法但回归判红；反过来 → 回归放行而生成器丢文件。
# 与 L1.69「名词表并入 regression._KIND_NOUNS 单一来源」同一处方：取消副本，只留一处。
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from normalize_categories import CANONICAL  # noqa: E402  单一真相源，禁止在此重定义
# 历史重写感知的哈希解析：唯一识别器，三道靠 git 取证的闸门共用（禁止各自另抄）。
from lib import hash_history as _hh  # noqa: E402

REQUIRED = ['id', 'name', 'category']

failures = []
warnings = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print('  ❌', msg)
    else:
        print('  ✅', msg)


def load_entities():
    return json.load(open(os.path.join(ROOT, 'api', 'entities.json'), encoding='utf-8'))


def layer_schema_contract():
    """D1(20260830): 实体 schema 契约闸门（mHarmony 式带类型校验）。
    缺核心字段或 status 枚举越界 → 判红，杜绝历史『写错层被静默丢弃』类缺陷
    （PROTO-010 / XFA-017）。契约定义见 scripts/schema_contract.py。"""
    from schema_contract import SCHEMA_VERSION, validate
    ents = load_entities().get('entities', [])
    v = validate(ents)
    check(len(v) == 0,
          f"实体 schema 契约 v{SCHEMA_VERSION}：{len(ents)} 实体全部满足核心字段+status 枚举（违规 {len(v)}）")


def _git_show_json(relpath, ref='HEAD'):
    """取 git 某版本的 JSON 文件内容；取不到返回 None（调用方须按"无法核验"处理，不得当绿灯）。"""
    try:
        out = subprocess.run(['git', 'show', f'{ref}:{relpath}'], cwd=ROOT,
                             capture_output=True, timeout=60)
        if out.returncode != 0:
            return None
        return json.loads(out.stdout.decode('utf-8'))
    except Exception:
        return None


# ---------- L1 Schema ----------
def layer1():
    print('\n[L1] Schema 校验')
    doc = load_entities()
    ents = doc['entities']
    meta = doc['meta']
    check(meta.get('total_entities') == len(ents), f"meta.total_entities({meta.get('total_entities')}) == 实体数组长度({len(ents)})")
    check(sum(meta.get('category_counts', {}).values()) == len(ents), 'category_counts 求和 == 实体总数')
    bad_cat = [e['id'] for e in ents if e.get('category') not in CANONICAL]
    check(len(bad_cat) == 0, f'所有 category 在标准白名单内（异常 {len(bad_cat)} 条）')
    missing = [e.get('id', '?') for e in ents if any(not e.get(k) for k in REQUIRED)]
    check(len(missing) == 0, f'必填字段(id/name/category)非空（缺失 {len(missing)} 条）')


# ---------- L1.5 数据质量棘轮闸门 ----------
BASELINE_PATH = os.path.join(ROOT, 'scripts', 'quality-baseline.json')


def layer1_5():
    print('\n[L1.5] 数据质量闸门（棘轮：只许变好，不许变坏）')
    doc = load_entities()
    ents = doc['entities']

    quarantined = sum(1 for e in ents if e.get('quarantine'))
    placeholder = sum(1 for e in ents if e.get('data_quality') == 'placeholder_id')
    unverif_vendor = sum(1 for e in ents if e.get('data_quality') == 'unverifiable_vendor')
    non_entity = sum(1 for e in ents if e.get('data_quality') == 'non_entity')
    duplicate = sum(1 for e in ents if e.get('data_quality') == 'duplicate')
    unaudited = sum(1 for e in ents if 'data_quality' not in e)

    # 脏度与去重分账（20260808-02）：
    #   max_quarantined 的原意是「无法溯源的脏数据不许再增加」，
    #   95 = 51 + 30 + 14 本就是脏度小计。duplicate 属治理动作（同物异 ID
    #   发现后主动隐藏一侧），数据本身可信，并进脏度会让"每治理一次就被
    #   自己的闸门拦一次"—— 即「回归假红拦部署」的复发形态。故各自设棘轮。
    dirty_quarantined = placeholder + unverif_vendor + non_entity
    # 防绕过：不许靠新造一种 data_quality 取值把条目挪出脏度统计。
    check(quarantined == dirty_quarantined + duplicate,
          f'隔离总数({quarantined}) == 脏度({dirty_quarantined}) + 去重({duplicate})'
          f' —— 出现未登记的隔离原因即视为绕过棘轮')

    check(unaudited == 0,
          f'全部实体已通过质量审计（未审计 {unaudited} 条 —— 请先跑 audit_data_quality.py）')

    if not os.path.exists(BASELINE_PATH):
        warnings.append('缺少质量基线文件，本次跳过棘轮比对')
        print(f'  ⚠️  未找到 {BASELINE_PATH}，跳过棘轮比对')
        return

    base = json.load(open(BASELINE_PATH, encoding='utf-8'))
    for key, cur, label in (
        ('max_quarantined', dirty_quarantined, '脏度隔离条目'),
        ('max_duplicate', duplicate, '去重隔离条目'),
        ('max_placeholder_id', placeholder, '占位ID条目'),
        ('max_unverifiable_vendor', unverif_vendor, '不可溯源厂商条目'),
        ('max_non_entity', non_entity, '非实体条目'),
    ):
        limit = base.get(key)
        if limit is None:
            continue
        check(cur <= limit, f'{label} {cur} ≤ 基线 {limit}'
              + ('' if cur <= limit else ' —— 新增劣化，禁止发布'))

    # 【20260809-09 · L1.71】真正要守的是「不许新灌脏数据」，不是「隔离计数不许涨」。
    #
    # 事故现场：本轮查出 2 条存量条目的 source_url 是**编造的 GitHub 仓库**（API 实证 404），
    # 如实标 quarantine 后，棘轮立刻报「脏度 97 ≤ 95 新增劣化，禁止发布」。
    # 可这一轮**一条新数据都没进库** —— 涨的是"已被发现的脏"，不是"脏本身"。
    # 棘轮分不清「我灌了脏」和「我发现了既有的脏」，于是它实际惩罚的是诚实：
    # 只要不去查，指标就永远好看；一查就判红、就发不出去。
    # 这与 20260808-02 给 duplicate 分账时写下的教训是同一个（「每治理一次就被自己的闸门拦一次」），
    # 当时只给 duplicate 开了口子，没有把语义本身修对。
    #
    # 修法：把「新增」定义成**新出现的实体 ID**（对照 git HEAD 版本的 entities.json），
    # 而不是「隔离计数变大」。新条目带脏 —— 一条都不许；存量条目被查出脏 —— 允许并要求留证。
    prev_doc = _git_show_json('api/entities.json')
    if prev_doc is None:
        warnings.append('取不到 git HEAD 版 entities.json，L1.71 新增脏度判定跳过')
        print('  ⚠️  取不到 git HEAD 版 entities.json，跳过新增脏度判定')
    else:
        prev_ids = {e.get('id') for e in prev_doc.get('entities', [])}
        new_ents = [e for e in ents if e.get('id') not in prev_ids]
        new_dirty = [e['id'] for e in new_ents if e.get('quarantine')]
        check(not new_dirty,
              f'本轮新增条目 {len(new_ents)} 条，其中带脏隔离 0 条'
              + ('' if not new_dirty else f' —— 新灌脏数据，禁止发布: {new_dirty[:5]}'))
        # 存量被查出脏必须留可审计的理由，否则"存量豁免"会变成免责通道
        prev_q = {e.get('id') for e in prev_doc.get('entities', []) if e.get('quarantine')}
        newly_q = [e for e in ents if e.get('quarantine') and e.get('id') in prev_ids
                   and e.get('id') not in prev_q]
        no_reason = [e['id'] for e in newly_q if not str(e.get('quarantine_reason') or '').strip()]
        check(not no_reason,
              f'本轮新隔离的存量条目 {len(newly_q)} 条均附 quarantine_reason'
              + ('' if not no_reason else f'（缺理由: {no_reason[:5]}）'))

    # 溯源覆盖率棘轮：Tier A 可追溯率不得下降
    cov = doc.get('meta', {}).get('provenance_coverage', {})
    cur_tr = cov.get('traceable_pct')
    min_tr = base.get('min_traceable_pct')
    if cur_tr is not None and min_tr is not None:
        check(cur_tr >= min_tr, f'Tier A 可追溯率 {cur_tr}% ≥ 基线 {min_tr}%')

    # 【20260809-09 · L1.72】基线本身必须被守住。
    #
    # L1.71 放开了"存量治理不算劣化"，但如果基线数字可以随手改，整套棘轮就是摆设 ——
    # 任何红灯都能靠把 max_* 调大 / min_* 调小变绿，而 baseline 文件开头那句
    # "这些上限只能调低，绝不能上调来迁就脏数据"只是**写给人看的注释，机器不读**。
    # 本轮我自己就有动机这么干（traceable_pct 47.32% 撞 55.2 下限）。
    # 故：基线朝松的方向变动时，必须在 `_adjustments` 留下**机器可复核**的记录，
    # 复核不过就判红 —— 让"改基线"这个动作本身也要过闸门。
    prev_base = _git_show_json('scripts/quality-baseline.json')
    if prev_base is None:
        warnings.append('取不到 git HEAD 版 quality-baseline.json，L1.72 基线松动核验跳过')
        print('  ⚠️  取不到 git HEAD 版基线文件，跳过基线松动核验')
        return
    adjustments = {(a.get('key'), a.get('to')): a for a in base.get('_adjustments', [])}
    loosened = []
    for k, v in base.items():
        if not isinstance(v, (int, float)) or k not in prev_base:
            continue
        old = prev_base[k]
        if k.startswith('max_') and v > old:
            loosened.append((k, old, v))
        elif k.startswith('min_') and v < old:
            loosened.append((k, old, v))
    if not loosened:
        print('  ✅ 基线未朝松的方向变动（无需自证）')
        return
    for k, old, new in loosened:
        rec = adjustments.get((k, new))
        if not rec:
            check(False, f'基线 {k} 由 {old} 松动到 {new}，但 _adjustments 无对应记录 —— 禁止无记录改基线')
            continue
        kind = rec.get('kind')
        if kind == 'legacy_discovery':
            ids = rec.get('ids') or []
            prev_doc2 = _git_show_json('api/entities.json') or {}
            prev_ids2 = {e.get('id') for e in prev_doc2.get('entities', [])}
            cur_by_id = {e.get('id'): e for e in ents}
            ok_delta = (new - old) == len(ids)
            all_legacy = all(i in prev_ids2 for i in ids)
            all_labeled = all(cur_by_id.get(i, {}).get('quarantine') is True
                              and str(cur_by_id.get(i, {}).get('quarantine_reason') or '').strip()
                              for i in ids)
            check(ok_delta and all_legacy and all_labeled,
                  f'基线 {k} {old}->{new} 自证通过：恰好 {len(ids)} 条**存量**条目被查出并附理由'
                  + ('' if (ok_delta and all_legacy and all_labeled)
                     else f'（差额匹配={ok_delta} 全为存量={all_legacy} 均有理由={all_labeled}）'))
        elif kind == 'recalibration':
            # 口径变更下调下限：必须证明**新判据更严**（在旧数据上确有命中），
            # 否则"口径变了"就是万能借口。
            #
            # 【20260810-21 通用化】原自证写死只认 source_scope.violations()，
            # 那是 L1.70 那一次口径变更的**专用**形态。于是下一次口径变更
            # （本轮：tier 由「source 非空即 A」改为按证据推导）自证恒为 0 ——
            # **专用自证等于没有自证**：真变严的改动过不了，反倒逼人去改闸门本身。
            # 改为通用判据：拿**当前判据**重算 git HEAD 版旧数据，数出多少条会被
            # 降级；降级数 > 0 即证明这次是收紧而非放水。
            proof = 0
            try:
                prev_doc2 = _git_show_json('api/entities.json') or {}
                prev_ents = prev_doc2.get('entities', [])
                import govern_source_tier as _gst
                _ORD = {'A': 0, 'B': 1, 'C': 2}
                proof = sum(
                    1 for e in prev_ents
                    if _ORD.get(_gst.derive_tier(e)[0], 9) > _ORD.get(e.get('source_tier'), 9)
                )
                if proof == 0:      # 兼容 L1.70 形态的旧口径变更
                    import source_scope as _ss
                    proof = len(_ss.violations(prev_ents))
            except Exception as exc:      # noqa: BLE001
                warnings.append(f'L1.72 recalibration 自证异常: {exc}')
            check(proof > 0,
                  f'基线 {k} {old}->{new} 自证通过：新判据在旧数据上命中 {proof} 条'
                  '（证明是口径变严，不是放水）')
        else:
            check(False, f'基线 {k} {old}->{new} 的 _adjustments 记录 kind={kind!r} 不是可自证类型')


# ---------- L1.6 边缘拦截不变式 ----------
def layer1_6():
    """【N03 20260805-r3 新增 · 守护 S-01 修复】

    S-01 事故：线上 /wrangler.toml 返回 200 并泄露明文 ADMIN_API_KEYS。
    根因不在 functions/_middleware.js（规则写得没错），而在 _routes.json 的
    include 是枚举式白名单 —— Pages Function 只在 include 命中的路径上运行，
    根级文件从未进入 include，中间件对它们根本没被调用。**规则有，入口没开。**

    这类失效最危险的地方在于它完全静默：没有报错、没有告警，回归全绿，
    而私有文件在线上大方地提供下载。故在此加断言把「入口是否打开」变成硬门禁。
    """
    print('\n[L1.6] 边缘拦截不变式（防 S-01 型静默失效）')
    try:
        with open(os.path.join(ROOT, '_routes.json'), encoding='utf-8') as f:
            routes = json.load(f)
    except Exception as e:
        check(False, f'_routes.json 可读取（{e}）')
        return

    include = routes.get('include') or []
    check('/*' in include,
          '_routes.json include 包含 "/*"'
          + ('' if '/*' in include else
             f' —— 当前为 {include}。改回枚举式白名单会让 _middleware.js 的'
             '全部拦截规则静默失效，与 S-01 事故同型，禁止发布'))

    try:
        mw = read_text('functions/_middleware.js')
    except Exception as e:
        check(False, f'functions/_middleware.js 可读取（{e}）')
        return

    # 拦截清单必须覆盖已知高危项；缺任意一项即阻断
    # 【20260805-15】新增 '/functions'：此前 /functions/** 回落首页并返回 200，
    # 构成软 404（源码本身未泄露，但对搜索引擎是大批重复内容页）。棘轮防回退。
    required = ['/wrangler.toml', '/.gitignore', '/integrity_report.txt',
                '/scripts', '/tasks', '/functions', '.docx']
    missing = [k for k in required if f"'{k}'" not in mw]
    check(not missing,
          '中间件私有清单覆盖已知高危项'
          + ('' if not missing else f' —— 缺失 {missing}，禁止发布'))


# ---------- L2 一致性 ----------
def read_text(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f:
        return f.read()


_DD_CACHE = []


def _load_dd():
    """加载 scripts/digest_due.py —— 留痕域**唯一源**（识别器/解析器都在那边）。

    20260810-19：本文件此前各闸门各持一份摘要行正则、运行时间正则、待办解析器，
    与 digest_due 的产出侧语义两张皮。run-67 手打的摘要行 `2026-08-10T18:17 | …`
    正是踩在两份语义之间：写的人以为写了，识别器一条都不认。
    收敛到一处后，"写出来的形状"与"查得出的形状"由同一份代码保证。
    """
    if not _DD_CACHE:
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location(
            'digest_due', os.path.join(ROOT, 'scripts', 'digest_due.py'))
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _DD_CACHE.append(mod)
    return _DD_CACHE[0]


def strip_js_comments(js):
    """剥掉 JS 注释，只留代码，供「断言必须认代码、不能被注释喂饱」的闸门使用。

    ⚠️ 别用 `re.sub(r'/\\*.*?\\*/')` + 逐行删 `//` 这套。真实翻车（20260807-05）：
    deploy_snapshot.mjs 有一行**行注释**写着「…的文件（如 mcp-server/*）不会丢」，
    其中的 `/*` 被块注释正则当成了**开注释**，于是从那里一路吞到下一个 `*/`
    （几十行之后的 `catch { /* 忽略 */ }`），把中间所有真代码连同
    GIT_INDEX_FILE、read-tree 全部抹掉 —— 闸门当场无中生有地恒红。
    反过来同样成立：`/* http://x */` 里的 `//` 也不该被当成行注释。
    两类注释会互相"污染"对方的定界符，正则解决不了，必须单趟状态机。

    字符串字面量也要跳过，否则代码里的 '//' 或 '/*' 同样会误开注释。
    """
    out = []
    i, n = 0, len(js)
    quote = None            # 当前所处的字符串引号（None 表示在代码里）
    while i < n:
        c = js[i]
        if quote:
            out.append(c)
            if c == '\\' and i + 1 < n:      # 转义：整体跳过下一个字符
                out.append(js[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
        elif c in '"\'`':
            quote = c
            out.append(c)
            i += 1
        elif js.startswith('//', i):
            while i < n and js[i] != '\n':
                i += 1
        elif js.startswith('/*', i):
            j = js.find('*/', i + 2)
            i = n if j == -1 else j + 2
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def layer2():
    print('\n[L2] 七处数字一致性 + 对外接口内容指纹')
    doc = load_entities()
    total = doc['meta']['total_entities']

    # data.js stats
    db_text = read_text('data.js')
    m = re.search(r'const DB = (\{.*?\});', db_text, re.S)
    db = json.loads(m.group(1)) if m else {}
    db_sum = sum(db.get('stats', {}).values())

    # 分类 JSON 求和
    cat_sum = 0
    for c in CANONICAL:
        p = os.path.join(ROOT, 'api', c + '.json')
        if os.path.exists(p):
            j = json.load(open(p, encoding='utf-8'))
            cat_sum += j.get('count', 0)

    readme = read_text('README.md')
    llms = read_text('llms.txt')
    ad = json.loads(read_text('agent-discovery.json'))

    # api/data.json —— 对外主接口 /api/data.json 的数据源
    pub_path = os.path.join(ROOT, 'api', 'data.json')
    pub = json.load(open(pub_path, encoding='utf-8')) if os.path.exists(pub_path) else {}
    pub_arr = pub.get('data') or pub.get('entities') or []

    sources = {
        'entities.json': total,
        'data.js(stats)': db_sum,
        '分类JSON求和': cat_sum,
        'README': int(re.search(r'(\d+)实体', readme).group(1)) if re.search(r'(\d+)实体', readme) else -1,
        'llms.txt': int(re.search(r'(\d+)实体', llms).group(1)) if re.search(r'(\d+)实体', llms) else -1,
        'agent-discovery': ad.get('total_entities', -1),
        'api/data.json': len(pub_arr),
    }
    vals = set(sources.values())
    check(len(vals) == 1, f'七处实体总数一致: {sources}')

    # 内容指纹交叉校验：仅比总数会漏报「总数不变、内容变更」的漂移
    src_fp = {(e.get('id'), e.get('category')) for e in doc['entities']}
    pub_fp = {(e.get('id'), e.get('category')) for e in pub_arr}
    only_src, only_pub = src_fp - pub_fp, pub_fp - src_fp
    check(
        not only_src and not only_pub,
        f'api/data.json 与真相源 ID+category 指纹一致（真相源独有 {len(only_src)} 条 / 接口独有 {len(only_pub)} 条）',
    )
    bad_pub_cat = sorted({e.get('category') for e in pub_arr if e.get('category') not in CANONICAL})
    check(len(bad_pub_cat) == 0, f'api/data.json 全部 category 已归一化（非标准值 {len(bad_pub_cat)} 种）')

    # 分类 JSON 各自 count 与实体库分类计数一致
    ents_by_cat = {}
    for e in doc['entities']:
        ents_by_cat[e['category']] = ents_by_cat.get(e['category'], 0) + 1
    mismatch = []
    for c in CANONICAL:
        p = os.path.join(ROOT, 'api', c + '.json')
        if os.path.exists(p):
            j = json.load(open(p, encoding='utf-8'))
            if j.get('count') != ents_by_cat.get(c, 0):
                mismatch.append(c)
    check(len(mismatch) == 0, f'每个分类JSON的count与实体库分类计数一致（不一致: {mismatch}）')

    # 【N13 20260805-16 加固】agent-discovery.json 是 Agent 直读的发现清单，
    # 其 categories 明细曾长期停留在旧快照（求和 577 ≠ 宣称 688）却因只校验
    # total_entities 而全绿 —— 与 api/data.json 漂移同型的静默失效。
    ad_cats = ad.get('categories', {})
    ad_sum = sum(ad_cats.values())
    check(ad_sum == total,
          f'agent-discovery.json categories 求和({ad_sum}) == 实体总数({total})')
    ad_cat_mismatch = sorted(
        c for c in set(list(ad_cats.keys()) + list(ents_by_cat.keys()))
        if ad_cats.get(c, 0) != ents_by_cat.get(c, 0)
    )
    check(len(ad_cat_mismatch) == 0,
          f'agent-discovery.json 各类目计数与实体库一致（不一致: {ad_cat_mismatch}）')

    # 对外端点不得指向已废弃的预览域名（应使用正式域 roboparts.cc）
    stale_ep = sorted(k for k, v in (ad.get('api_endpoints') or {}).items()
                      if isinstance(v, str) and 'pages.dev' in v)
    check(len(stale_ep) == 0,
          f'agent-discovery.json 端点无 pages.dev 残留（残留: {stale_ep}）')


# ---------- L1.7 机械互换维度不变式 ----------
def layer1_7():
    print('\n[L1.7] 机械互换维度（防「四维兼容」宣称落空）')
    doc = load_entities()
    ents = doc['entities']
    VALID = {'declared', 'partial', 'not_declared', 'n_a'}

    missing = [e['id'] for e in ents if 'mechanical_interface' not in e]
    check(len(missing) == 0,
          f'全部实体带 mechanical_interface 字段（缺失 {len(missing)} 条）')

    bad = [e['id'] for e in ents
           if (e.get('mechanical_interface') or {}).get('status') not in VALID]
    check(len(bad) == 0, f'mechanical_interface.status 取值合法（异常 {len(bad)} 条）')

    cov = doc['meta'].get('mechanical_interface_coverage', {})
    stat = {}
    for e in ents:
        s = e['mechanical_interface']['status']
        stat[s] = stat.get(s, 0) + 1
    consistent = (
        cov.get('not_applicable') == stat.get('n_a', 0)
        and cov.get('not_declared') == stat.get('not_declared', 0)
        and cov.get('partial') == stat.get('partial', 0)
        and cov.get('declared') == stat.get('declared', 0)
    )
    check(consistent, f'meta.mechanical_interface_coverage 与实体实际分布一致（实际 {stat}）')

    # 棘轮：已声明数只许增不许减
    BASELINE_FILLED = 2
    filled = stat.get('declared', 0) + stat.get('partial', 0)
    check(filled >= BASELINE_FILLED,
          f'机械接口已声明条目 {filled} ≥ 基线 {BASELINE_FILLED}')

    reg = os.path.join(ROOT, 'api', 'mechanical_interfaces.json')
    check(os.path.exists(reg), '机械接口标准登记表 api/mechanical_interfaces.json 存在')
    if os.path.exists(reg):
        r = json.load(open(reg, encoding='utf-8'))
        check(bool(r.get('designation_grammar', {}).get('parse_regex')),
              '登记表含可机读的法兰指定解析规则 (parse_regex)')


# ---------- L1.8 内容分发不变式 ----------
def layer1_8():
    """守护 20260805-17 修复的 SEO 事故。

    事故：content/ 有 14 篇原创长文，frontmatter 的 canonical 早已声明为
    /articles/{slug}，但仓库里从来没有 /articles 页面；且缺少 404.html，
    导致 Cloudflare Pages 把所有未知路径回落首页并返回 200。
    结果 sitemap 宣称的 6 条文章 URL 全是「200 的重复首页」——
    搜索引擎会据此判定 sitemap 不可信，连带压低整站抓取预算。

    不变式：sitemap 声明的每一个 /articles/* 都必须有真实页面文件；
    content/ 的每篇文章都必须已发布；404.html 必须存在。
    """
    import glob as _glob
    import re as _re
    print('\n[L1.8] 内容分发（防 sitemap 宣称不存在的页面 / 软 404 回落）')

    check(os.path.exists(os.path.join(ROOT, '404.html')),
          '404.html 存在（缺失会导致未知路径回落首页并返回 200，即软 404）')

    srcs = sorted(_glob.glob(os.path.join(ROOT, 'content', 'article-*.md')))
    slugs = []
    for f in srcs:
        t = read_text(f)
        m = _re.search(r'^slug:\s*(.+)$', t, _re.M)
        if m:
            slugs.append(m.group(1).strip().strip('"\''))
    check(len(slugs) == len(srcs),
          f'content/ 每篇文章都声明了 slug（{len(slugs)}/{len(srcs)}）')

    missing = [s for s in slugs
               if not os.path.exists(os.path.join(ROOT, 'articles', s + '.html'))]
    check(not missing, f'每篇 content/ 文章都已生成对外页面（缺失: {missing}）')

    check(os.path.exists(os.path.join(ROOT, 'articles', 'index.html')),
          'articles/index.html 索引页存在')

    # sitemap 宣称的文章 URL 必须都落地
    sm = read_text(os.path.join(ROOT, 'sitemap.xml'))
    declared = _re.findall(r'<loc>https://roboparts\.cc/articles/([^<]+)</loc>', sm)
    ghost = [s for s in declared
             if not os.path.exists(os.path.join(ROOT, 'articles', s + '.html'))]
    check(not ghost, f'sitemap 中每条 /articles/* 都有对应页面文件（幽灵URL: {ghost}）')
    check(len(declared) == len(slugs),
          f'sitemap 文章条目数与 content/ 一致（sitemap {len(declared)} vs 源 {len(slugs)}）')

    # 长尾落地页
    check(os.path.exists(os.path.join(ROOT, 'iso-9409-flange.html')),
          'ISO 9409-1 长尾落地页 iso-9409-flange.html 存在')
    check('<loc>https://roboparts.cc/iso-9409-flange</loc>' in sm,
          'sitemap 已收录 ISO 9409-1 落地页')

    # 页面质量：单 h1 + JSON-LD 可解析
    pages = sorted(_glob.glob(os.path.join(ROOT, 'articles', '*.html')))
    pages.append(os.path.join(ROOT, 'iso-9409-flange.html'))
    bad_h1, bad_ld, no_canon = [], [], []
    for f in pages:
        t = read_text(f)
        if t.count('<h1') != 1:
            bad_h1.append(os.path.basename(f))
        if '<link rel="canonical"' not in t:
            no_canon.append(os.path.basename(f))
        for blob in _re.findall(
                r'<script type="application/ld\+json">(.*?)</script>', t, _re.S):
            try:
                json.loads(blob)
            except Exception:
                bad_ld.append(os.path.basename(f))
                break
    check(not bad_h1, f'每个内容页有且仅有一个 h1（异常: {bad_h1}）')
    check(not bad_ld, f'每个内容页的 JSON-LD 均可解析（异常: {bad_ld}）')
    check(not no_canon, f'每个内容页都声明 canonical（缺失: {no_canon}）')

    # robots.txt 与 sitemap 不得互相矛盾
    # 事故：robots 曾 Disallow 20 个 /api/*.json，而 sitemap 同时把它们列为待抓 URL，
    # 且 llms.txt 还在邀请 AI 取用这些端点 —— 三个文件对同一批 URL 给出三种信号。
    robots = read_text(os.path.join(ROOT, 'robots.txt'))
    disallowed = [m.strip() for m in
                  _re.findall(r'^\s*Disallow:\s*(\S+)\s*$', robots, _re.M) if m.strip() != '/']
    conflict = [d for d in disallowed if ('<loc>https://roboparts.cc%s</loc>' % d) in sm]
    check(not conflict,
          f'sitemap 未收录被 robots.txt 禁止抓取的路径（冲突: {conflict}）')
    check('Sitemap: https://roboparts.cc/sitemap.xml' in robots,
          'robots.txt 已声明 sitemap 位置')
    for bot in ('GPTBot', 'ClaudeBot', 'PerplexityBot'):
        check(bot in robots, f'robots.txt 显式允许 AI 检索爬虫 {bot}（GEO 前提）')

    # IndexNow 密钥文件名必须等于密钥本身，否则提交会被静默拒绝
    kf = os.path.join(ROOT, 'roboparts2026indexnow.txt')
    check(os.path.exists(kf), 'IndexNow 密钥校验文件 {key}.txt 存在（文件名必须等于密钥）')
    if os.path.exists(kf):
        check(read_text(kf).strip() == 'roboparts2026indexnow',
              'IndexNow 密钥文件内容与密钥一致')

    # llms.txt 与 agent-discovery 同步
    llms = read_text(os.path.join(ROOT, 'llms.txt'))
    check('<!-- ARTICLES:BEGIN -->' in llms and '/articles' in llms,
          'llms.txt 已收录技术文库章节（AI Agent 的内容发现入口）')
    ad_p = os.path.join(ROOT, 'agent-discovery.json')
    if os.path.exists(ad_p):
        ad = json.load(open(ad_p, encoding='utf-8'))
        cl = ad.get('content_library') or {}
        check(cl.get('count') == len(slugs),
              f'agent-discovery.content_library.count 与实际文章数一致'
              f'（{cl.get("count")} vs {len(slugs)}）')


def layer1_9():
    """守护 20260805-18 新增的边缘遥测（GEO 曝光埋点）。

    背景：连续 4 轮判定瓶颈为「获客」，但站点无任何流量埋点，
    ops/funnel/ 只能测「可用性」与「KV 里的转化终点(0)」，
    导致永远只看得到 0，无法区分「没人来」与「来了没转化」。
    18:00 在 functions/_middleware.js 加了 isolate 级累加 + 分片落盘的零成本遥测。

    不变式（任一被破坏都会让遥测静默失效或炸掉免费额度）：
      1. 两条返回路径（私有 404 / 正常 next）都必须打点，否则样本有偏；
      2. 必须返回 context.next() 的结果，遥测不得吞掉响应；
      3. 落盘必须走 waitUntil 且全程 try/catch —— 遥测不得影响响应正确性；
      4. FLUSH_MS 不得低于 30s，且必须分片 —— 否则按请求写 KV 会击穿
         免费额度（1000 写/日）并产生跨 isolate 读改写竞争丢数；
      5. 必须设 expirationTtl，否则 KV 键无界增长；
      6. 不得新增未鉴权的公开 metrics 端点（避免把运营数据变成新攻击面）。
    """
    import re as _re
    print('\n[L1.9] 边缘遥测（GEO 曝光埋点，防静默失效 / 防击穿免费额度）')
    mw_p = os.path.join(ROOT, 'functions', '_middleware.js')
    mw = read_text(mw_p)
    check(bool(mw), 'functions/_middleware.js 存在')
    if not mw:
        return

    check('function record(' in mw, '遥测采集函数 record() 存在')
    # 精确匹配两个调用点本身，而非笼统计数（笼统计数会把函数定义算进去，
    # 删掉一个调用点仍能"通过"，等于断言失效）
    check(_re.search(r'\n\s*record\(context,\s*url,\s*404\)', mw) is not None,
          '私有 404 路径已打点（否则拦截量不可见，样本有偏）')
    check(_re.search(r'\n\s*record\(context,\s*url,\s*res\s*&&\s*res\.status\)', mw) is not None,
          '正常响应路径已打点（主样本来源）')
    check(_re.search(r'(?:const|let)\s+res\s*=[\s\S]{0,200}?await\s+context\.next\(', mw) is not None
          and _re.search(r'return\s+res;', mw) is not None,
          '遥测未吞掉响应（next() 结果被原样返回）')
    # 【20260807-16】本断言原写死 `const`。HEAD 补偿必须改写 res，故放开为 let ——
    # 但**放开写法不等于放开语义**：一旦用了 let，就必须证明"唯一的改写点是
    # HEAD 补偿"，否则 let 就成了"任何人都能悄悄改写响应"的后门，
    # 本断言也就退化成一句空话（判据变松、一切照绿，正是这仓库反复记过的假修复形态）。
    if _re.search(r'\blet\s+res\s*=', mw):
        assigns = _re.findall(r'^\s*res\s*=\s*', mw, _re.M)
        check(len(assigns) == 1
              and 'x-head-fallback' in mw
              and _re.search(r'res\s*=\s*new Response\(null,\s*\{\s*status:\s*res\.status',
                             mw) is not None,
              'res 的唯一改写点是 HEAD 补偿（实得改写点 %d 处；不得借 let 之名改写正常响应）'
              % len(assigns))
    # 注：「HEAD 补偿禁止二次 next()」的判据属 HEAD 正确性范畴，见 L1.44，本段不重复。
    check('context.waitUntil(' in mw, '落盘走 waitUntil（不阻塞响应）')
    check(mw.count('catch') >= 4, f'遥测全程 try/catch 兜底（catch 数 {mw.count("catch")}，需 ≥4）')

    m = _re.search(r'FLUSH_MS\s*=\s*([\d_]+)', mw)
    flush_ms = int(m.group(1).replace('_', '')) if m else 0
    check(flush_ms >= 30000,
          f'FLUSH_MS={flush_ms}ms ≥ 30000ms（防按请求写 KV 击穿免费额度）')
    m = _re.search(r'SHARDS\s*=\s*(\d+)', mw)
    shards = int(m.group(1)) if m else 0
    check(2 <= shards <= 32,
          f'分片数 SHARDS={shards} 在 2~32（防跨 isolate 竞争丢数 / 防键爆炸）')
    check('expirationTtl' in mw, 'KV 指标键设置了 expirationTtl（防无界增长）')

    # 零流量丢数守护：纯节流时缓冲要等"下一个请求"才落盘，低流量下等不到，
    # isolate 回收即丢。爬虫命中（GEO 曝光核心证据）必须立即落盘。
    check(_re.search(r'highValue\s*\|\|\s*now\s*-\s*_lastFlush\s*>=\s*FLUSH_MS', mw) is not None,
          '爬虫命中走立即落盘（零流量站点纯节流会永久丢数）')
    check(_re.search(r"const\s+highValue\s*=\s*\(kind\s*===\s*'ai'\s*\|\|\s*kind\s*===\s*'search'\)", mw)
          is not None, 'highValue 判定覆盖 ai + search 两类爬虫')
    m = _re.search(r'MAX_WRITES_PER_ISOLATE_DAY\s*=\s*(\d+)', mw)
    cap = int(m.group(1)) if m else 0
    check(0 < cap <= 200,
          f'单 isolate 每日写次数硬上限={cap}（0<cap≤200，防立即落盘被流量突增放大而击穿额度）')
    check('_writeDay' in mw and _re.search(r"day\s*!==\s*_writeDay", mw) is not None,
          '写次数额度按天重置（否则 isolate 长活后额度永久耗尽，遥测静默停摆）')
    mw_low = mw.lower()
    check('AI_BOTS' in mw and 'gptbot' in mw_low and 'claudebot' in mw_low
          and 'perplexitybot' in mw_low,
          'AI 爬虫识别表覆盖 GPTBot/ClaudeBot/PerplexityBot（GEO 曝光口径）')
    check("bump('total')" in mw, '总量计数存在（分母，否则无法算比率）')

    # 防自污染：飞轮验证埋点时会伪造爬虫 UA 发探针，若与真实流量混记，
    # 下一轮就会把自己的探针读成 GEO 曝光（同 14:00 测试订单污染事故）。
    check('SELFTEST_HEADER' in mw and 'x-roboparts-selftest' in mw_low,
          '自检探针隔离头已定义（防把自己的探针读成真实 GEO 曝光）')
    check(_re.search(r"if\s*\(req\.headers\.get\(SELFTEST_HEADER\)\)", mw) is not None
          and "bump('selftest:total')" in mw,
          '自检请求走 selftest: 隔离命名空间')
    # 隔离分支必须 return，否则会同时计入真实指标 —— 隔离形同虚设
    seg = mw.split('SELFTEST_HEADER)')[-1].split("bump('total')")[0] if 'SELFTEST_HEADER)' in mw else ''
    check('return;' in seg,
          '自检分支提前 return（否则探针同时计入真实指标，隔离失效）')

    # 遥测口径必须与 robots.txt 放行名单对齐，否则「放行了却没统计」= 曝光被低估
    robots = read_text(os.path.join(ROOT, 'robots.txt')).lower()
    missing = [b for b in ('gptbot', 'claudebot', 'perplexitybot', 'bytespider', 'petalbot')
               if b in robots and b not in mw_low]
    check(not missing, f'robots.txt 放行的 AI 爬虫均在遥测口径内（漏统计: {missing}）')

    # 不得出现未鉴权的公开指标端点
    api_dir = os.path.join(ROOT, 'functions', 'api')
    leaky = []
    if os.path.isdir(api_dir):
        for dirpath, _dirnames, filenames in os.walk(api_dir):
            for fn in filenames:
                if 'metric' in fn.lower():
                    src = read_text(os.path.join(dirpath, fn))
                    if 'ADMIN_API_KEYS' not in src and 'Authorization' not in src:
                        leaky.append(os.path.relpath(os.path.join(dirpath, fn), ROOT))
    check(not leaky, f'无未鉴权的公开指标端点（可疑: {leaky}）')

    check('USER_CREDITS' in read_text(os.path.join(ROOT, 'wrangler.toml')),
          '遥测所用 KV 绑定 USER_CREDITS 已在 wrangler.toml 声明')

    # 部署脚本每轮发 ~15 次校验请求，不隔离就会把运维动作记成真实流量
    dep = read_text(os.path.join(ROOT, 'scripts', 'deploy.mjs'))
    bare = _re.findall(r'fetch\(TARGET[^)]*\)(?!\s*,)', dep)
    bare = [b for b in bare if 'SELFTEST_HEADERS' not in b]
    check(not bare,
          f'deploy.mjs 全部校验请求带自检隔离头（裸请求会被记成真实流量）遗漏 {len(bare)} 处')
    check("'X-RoboParts-Selftest'" in dep,
          'deploy.mjs 已定义 SELFTEST_HEADERS')

    # ── 20260805-18 全站 404 事故守护 ──────────────────────────────────────
    # 事故：`const _shard = Math.floor(Math.random()*SHARDS)` 写在模块顶层。
    # Cloudflare Workers 禁止在顶层作用域生成随机数/做 I/O，worker 启动即抛错；
    # 又因 _routes.json include="/*"，**整站所有请求**（含 / 与 /api/*）全部 404。
    # 一行代码 = 全站不可用，且本地静态检查完全看不出来。
    # 判据说明：最初用「括号深度==0」判顶层，实测顶层行的 depth 恒为 1
    # （字符串/正则里的括号无法用计数法配平），条件永不成立 —— 断言恒绿、
    # 等于没检查（假绿比没有断言更危险）。改用**列锚定**：JS 里模块顶层
    # 语句一定顶格书写（零缩进），函数体内一定有缩进。判据简单且无歧义。
    BANNED_RE = _re.compile(
        r'^(?:const|let|var|export\s+(?:const|let|var))\s+[\w${}\[\],\s]+='
        r'[^\n]*?(?:Math\.random\(|Date\.now\(|crypto\.getRandomValues\(|crypto\.randomUUID\()'
    )
    offenders = []
    fn_dir = os.path.join(ROOT, 'functions')
    for dirpath, _d, filenames in os.walk(fn_dir):
        for fn in filenames:
            if not fn.endswith('.js'):
                continue
            fp = os.path.join(dirpath, fn)
            src = read_text(fp)
            # 剥离块注释（保持行号）：注释里描述事故的示例代码不算违规，
            # 否则本文件的事故说明会把自己判死。
            src = _re.sub(r'/\*.*?\*/',
                          lambda m: _re.sub(r'[^\n]', ' ', m.group(0)), src, flags=_re.S)
            for lineno, raw in enumerate(src.splitlines(), 1):
                line = _re.sub(r'//.*$', '', raw)
                if line[:1].strip() and BANNED_RE.match(line):  # 顶格 = 模块顶层
                    offenders.append(
                        f'{os.path.relpath(fp, ROOT)}:{lineno} {line.strip()[:60]}')
    check(not offenders,
          f'Functions 顶层作用域无 Math.random/Date.now 等运行时禁用调用'
          f'（会导致 worker 启动失败 → 全站 404）违规: {offenders}')


def layer1_10():
    """守护 20260805-19 新增的参数口径规范注册表（中立性资产）。

    背景：竞品英孚机器人（关节卖家）公开承认行业痛点是「参数存在水分、
    参数定义又存在区别」。但卖家定义口径必然向自家可造方案倾斜——
    这道题只有中立第三方有资格答。参数口径规范因此是 RoboParts
    唯一不可被卖家复制的定位性资产。

    本层守护「可信度」而非「功能」，破坏后果不是报错而是信誉塌方：
      1. 中立性声明被删 → 资产退化为又一份普通参数科普，丧失全部差异化；
      2. epistemic_status 被删 → 启发式红线会被读者当作标准判定，
         我方将对选型事故承担无法承受的隐含责任（合规风险）；
      3. known_defects 被删 → 一边指责行业口径混乱、一边隐藏自己
         speed 字段混装两个物理量的同类缺陷，双标，信誉一次性归零；
      4. 页面数字与 JSON 脱钩 → 复发「七处数字不一致」老问题；
      5. 未被 sitemap/llms.txt/agent-discovery 收录 → 内容孤岛，等于没做。
    """
    print('\n[L1.10] 参数口径规范注册表（中立性资产 + 认知诚实）')
    ps_path = os.path.join(ROOT, 'api', 'parameter_semantics.json')
    page_path = os.path.join(ROOT, 'robot-joint-parameter-spec.html')

    if not os.path.exists(ps_path):
        check(False, 'api/parameter_semantics.json 存在')
        return
    ps = json.load(open(ps_path, encoding='utf-8'))
    meta = ps.get('meta', {})

    for seg in ('red_lines', 'unit_conversions', 'comparability_levels',
                'known_defects', 'buyer_checklist', 'industry_evidence'):
        check(bool(ps.get(seg)), f'parameter_semantics.{seg} 非空')

    # --- 1. 中立性声明（差异化的全部来源）
    ns = meta.get('neutrality_statement', '')
    check(all(k in ns for k in ('不生产', '不销售', '利益')),
          '中立性声明完整（不生产/不销售/无利益立场）—— 本资产唯一不可被卖家复制之处')

    # --- 2. 认知边界声明（合规闸门）
    es = meta.get('epistemic_status', '')
    check(('启发式' in es or 'heuristic' in es.lower()) and '不构成' in es,
          'epistemic_status 声明红线为启发式筛查、不构成合规判定（防被当作标准援引）')

    # --- 3. 自身缺陷登记须与实际数据状态一致（防「假装修好」与双标）
    kd_ids = {k.get('id') for k in ps.get('known_defects', [])}
    speed_vals = [str(e.get('speed') or '') for e in load_entities().get('entities', [])]
    has_rate = any(re.search(r'\d\s*(Gbps|Mbps|kbps)', v, re.I) for v in speed_vals)
    has_ang = any(re.search(r'\d\s*(rad/s|rpm|sec\s*/\s*\d+)', v, re.I) for v in speed_vals)
    if has_rate and has_ang:
        check('KD-01' in kd_ids,
              'speed 仍混装通信速率与角速度 → known_defects 必须保留 KD-01（不得隐藏自身同类缺陷）')
    else:
        check('KD-01' not in kd_ids,
              'speed 已拆分 → KD-01 应撤销（缺陷登记不得长期滞后于实际状态）')

    # --- 4. 页面数字与 JSON 单一真相源一致
    if not os.path.exists(page_path):
        check(False, 'robot-joint-parameter-spec.html 存在')
    else:
        page = read_text(page_path)
        ev = ps['industry_evidence']['by_field']

        # 用 data-src 语义锚点精确比对，禁止退回裸子串包含判断。
        # 20260805-19 反向验证抓到：裸子串 '63' 会被 CSS 色值 #30363d 命中，
        # 导致断言恒真（假绿）。锚点法对每个数字定位到唯一出处。
        def truth(key):
            if key == 'red_lines':
                return len(ps['red_lines'])
            if key == 'unit_conversions':
                return len(ps['unit_conversions'])
            if key == 'entities_scanned':
                return ps['scope']['entities_scanned']
            if '.' in key:
                fld, attr = key.split('.', 1)
                return (ev.get(fld) or {}).get(attr)
            return None

        anchors = re.findall(r'data-src="([^"]+)">([^<]*)<', page)
        check(len(anchors) >= 20,
              f'落地页真相源锚点数量充足（实测 {len(anchors)} 个，<20 说明锚点被移除）')
        mism, unknown = [], []
        for key, shown in anchors:
            t = truth(key)
            if t is None:
                unknown.append(key)
            elif str(t) != shown.strip():
                mism.append(f'{key}: 页面={shown} JSON={t}')
        check(not mism, f'落地页锚点数字与 JSON 真相源逐项一致（脱钩: {mism[:4]}）')
        check(not unknown, f'落地页锚点均可在 JSON 中解析（未知键: {unknown[:4]}）')
        check('不销售' in page and '不偏袒' in page,
              '落地页正文承载中立立场（不只写在机读文件里）')
        check('known_defects' in page or '公开登记' in page,
              '落地页公开自身数据缺陷（与对外指摘行业口径混乱对称）')
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
        ok_ld = False
        if m:
            try:
                json.loads(m.group(1))
                ok_ld = True
            except Exception:
                ok_ld = False
        check(ok_ld, '落地页 JSON-LD 可解析（失效则 FAQ/Dataset 富结果全部丢失）')

    # --- 5. 发现层收录（防内容孤岛）
    for f, label in (('sitemap.xml', 'sitemap'), ('llms.txt', 'llms.txt'),
                     ('agent-discovery.json', 'agent-discovery'), ('index.html', '首页内链')):
        p = os.path.join(ROOT, f)
        txt = read_text(p) if os.path.exists(p) else ''
        check('robot-joint-parameter-spec' in txt,
              f'{label} 已收录参数口径页（未收录=AI 爬虫发现不到，等于没做）')
    check('parameter_semantics.json' in read_text(os.path.join(ROOT, 'sitemap.xml')),
          'sitemap 收录 parameter_semantics.json 机读端点')


def layer1_11():
    """守护「新鲜度判据」本身不静默失效。

    20260805-19 发现：运维飞轮按 oss_components.json 的 meta.last_updated
    判断是否需要重新摄取（阈值 7 天），但 ingest_oss.mjs 从来只写
    generated_at，导致 last_updated 恒为 null，时间比较永不成立 ——
    摄取新鲜度检查静默失效了不知多久。

    这与「假绿断言」是同一类故障：检查存在、永远不报警、因此永远不被发现。
    凡是「读某字段做时间/阈值判断」的运维逻辑，该字段的存在性必须被断言守护。
    """
    print('\n[L1.11] 运维判据字段存在性（防检查静默失效）')
    from datetime import datetime as _dt

    targets = [
        ('api/oss_components.json', 'last_updated', 'OSS 摄取新鲜度（飞轮 7 天阈值判据）'),
        ('api/parameter_semantics.json', 'generated_at', '参数口径注册表生成时间'),
        ('api/mechanical_interfaces.json', 'generated_at', '机械接口注册表生成时间'),
    ]
    for rel, field, why in targets:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            check(False, f'{rel} 存在')
            continue
        meta = (json.load(open(p, encoding='utf-8')) or {}).get('meta', {})
        v = meta.get(field)
        ok = isinstance(v, str) and v.strip() != ''
        if ok:
            try:
                _dt.fromisoformat(v.replace('Z', '+00:00'))
            except Exception:
                ok = False
        check(ok, f'{rel} meta.{field} 存在且可解析为时间 —— {why}（缺失=该检查恒不触发）')

    # 生成器与消费者必须对齐：写 meta 的脚本必须真的写了这个字段
    ing = read_text(os.path.join(ROOT, 'scripts', 'ingest_oss.mjs'))
    check('last_updated' in ing,
          'ingest_oss.mjs 确实写入 last_updated（否则下次摄取后字段又会消失，故障复发）')


def layer1_12():
    """守护「转化路径」：AI 能看见门、门是开的、承诺与实现一致、自测不污染。

    20260805-20 背景：遥测证明唯一走通的流量通道是 AI 爬虫（GPTBot /
    ClaudeBot / PerplexityBot / OAI-SearchBot 均已确认抓取，真人 0），
    但 llms.txt 与 agent-discovery.json 中 curl / api/register / Bearer
    出现次数为 0 —— 爬虫抓走的内容里没有任何可执行的下一步。

    曝光通道通了、转化出口却不存在，与 18:00「有站点无仪表」同型：
    动作能发生，但结构上不可能发生。本层锁死四条不变式：

      1. AI 可读入口必须含可直接执行的领 key 命令（门要可见）
      2. 自助注册不得引入人工审批（门要是开的）
      3. 文档承诺的免费额度必须等于代码实际发放（不许吹牛）
      4. 飞轮自测注册必须与真实转化分账（基线要可信）
    """
    print('\n[L1.12] 转化路径可达性与诚实性（AI 通道 → 真实注册）')
    import re as _re
    reg = read_text(os.path.join(ROOT, 'functions', 'api', 'register.js'))
    llms = read_text(os.path.join(ROOT, 'llms.txt'))
    ad_p = os.path.join(ROOT, 'agent-discovery.json')
    ad = json.load(open(ad_p, encoding='utf-8')) if os.path.exists(ad_p) else {}
    ob = ad.get('onboarding', {})

    # ---- 1. 门要可见：AI 抓走的内容里必须有可执行的下一步 ----
    # 反向验证教训（20260805-20，本轮第 3 次假绿）：最初写成
    #   '/api/register' in llms and 'curl' in llms
    # 把领 key 的 curl 换成"请联系客服"后断言仍然通过 —— 因为 curl 出现在
    # validate 示例里、/api/register 出现在端点列表里，两个裸子串各自都在。
    # 必须验证二者出现在**同一条命令**内，才等价于"AI 真的能照抄执行"。
    reg_cmd = _re.search(
        r'curl[^\n`]{0,400}?/api/register|/api/register[^\n`]{0,200}?\n[^`]{0,400}?curl',
        llms, _re.S)
    check(bool(_re.search(r'curl\s+(-[^\s]+\s+)*(-X\s+POST\s+)?\S*roboparts\.cc/api/register',
                          llms)) or bool(reg_cmd),
          'llms.txt 含**完整可照抄**的领 key curl 命令（curl 与 /api/register 须在同一条命令内，'
          '分散在文档两处不算——AI 无法拼出可执行指令）')
    check('-d' in llms and '"email"' in llms,
          'llms.txt 给出了注册请求体示例（缺 body 则命令不可直接执行）')
    check('Authorization: Bearer' in llms,
          'llms.txt 说明了鉴权用法（否则 AI 拿到 key 也不知道怎么用）')
    check(bool(ob.get('get_api_key', {}).get('curl')),
          'agent-discovery.json onboarding.get_api_key.curl 存在（机读转化路径）')
    check('register' in (ad.get('api_endpoints') or {}),
          'agent-discovery.json api_endpoints 暴露 register 端点')

    # ---- 2. 门要是开的：不得悄悄加回人工审批 ----
    check(ob.get('get_api_key', {}).get('approval_required') is False,
          '自助注册声明为无需审批（approval_required=false）')
    for word in ('pending_approval', 'awaiting_review', 'manual_approval'):
        check(word not in reg,
              f'register.js 未引入人工审批阻塞（无 {word}）—— 一旦需人工介入，AI 通道即断')

    # ---- 3. 不许吹牛：文档承诺必须等于代码实际发放 ----
    m_code = _re.search(r'credits:\s*(\d+)', reg)
    code_credits = int(m_code.group(1)) if m_code else None
    check(code_credits is not None, 'register.js 中免费额度可解析')
    doc_hits = _re.findall(r'(\d+)\s*次免费额度', llms)
    check(bool(doc_hits), 'llms.txt 明示了免费额度数量')
    if code_credits is not None and doc_hits:
        check(all(int(x) == code_credits for x in doc_hits),
              f'llms.txt 承诺的免费额度 {doc_hits} == register.js 实际发放 {code_credits}'
              f'（不一致=对 AI 与用户虚假承诺）')
    m_rl = _re.search(r'rate_limit:\s*(\d+)', reg)
    if m_rl:
        check(f"{m_rl.group(1)} 次/小时" in llms,
              f'llms.txt 限速表述与代码一致（{m_rl.group(1)} 次/小时）')

    # ---- 4. 基线要可信：自测注册必须分账 ----
    check("'selftest_'" in reg or '"selftest_"' in reg,
          'register.js 对自检注册使用隔离 key 前缀（飞轮探活不污染真实用户）')
    check('stat:selftest:registrations' in reg,
          '自检注册写入隔离统计键，不并入 stat:users:total')
    check('function attribute(' in reg,
          'register.js 具备来源归因函数（否则首个真实用户来自哪个渠道不可知）')
    check('stat:src:' in reg,
          '真实注册按来源分桶写入 stat:src:*（决定下一步资源投向）')
    check('stat:first_signup' in reg,
          '保留首个真实注册现场（只写一次，供复盘）')

    # ---- 5. 诚实边界不许为了好看被撤下（同 KD-01 机制）----
    limits = ob.get('honest_limits') or []
    check(len(limits) >= 3,
          'agent-discovery.json 保留 honest_limits 边界声明（≥3 条）')
    check(any('0 条' in x or '0.57' in x for x in limits),
          '边界声明仍如实包含"可比较 0 条 / 声明率 0.57%"等不利事实'
          '（撤下=用中立牌吸引流量却隐藏缺陷，自毁唯一壁垒）')
    check('不生产、不销售、不代理' in llms,
          'llms.txt 保留中立性声明（唯一不可被竞品复制的差异）')


def layer1_13():
    """守护「接入入口落在 AI 实际抓取的页面上」。

    20260805-21 背景：L1.12 把可执行入口补进了 llms.txt 与 agent-discovery.json，
    但遥测显示 AI 爬虫的真实抓取分布是
        /articles/*  30%  ·  /robots.txt 33%  ·  /llms.txt 仅 3.3%
    也就是说，入口补在了被抓最少的那个文件上。爬虫抓走的绝大部分内容里
    依然没有任何可执行的下一步 —— 与上一轮同型的结构性断点，只是换了位置。

    本层锁死五条不变式（全部走 data-rp 语义锚点逐项解析，
    不用裸子串比对 —— 裸子串已连续三轮造成假绿）：

      1. 覆盖：index / 落地页 / 每一篇文章都必须带接入区块，且恰好一份
      2. 可执行：领 key 命令中 curl 与 /api/register 必须在同一条命令内
      3. 一致：页面标注的额度 / 限速 / 实体数必须等于代码与数据的真值
      4. 诚实：不利事实（可比较 0 条、机械声明率 0.57%）不许为了好看撤下
      5. 机读：JSON-LD 必须含指向 /api/register 的 RegisterAction
    """
    print('\n[L1.13] 接入入口下沉到 AI 实际抓取的页面')
    import re as _re
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    try:
        from onboarding_block import facts as _facts
    except Exception as e:                                    # noqa: BLE001
        check(False, 'scripts/onboarding_block.py 可导入（接入区块真相源）: %s' % e)
        return
    f = _facts()

    pages = [os.path.join(ROOT, x) for x in
             ('index.html', 'iso-9409-flange.html', 'robot-joint-parameter-spec.html')]
    pages += sorted(glob.glob(os.path.join(ROOT, 'articles', '*.html')))
    pages = [p for p in pages if os.path.isfile(p)]
    check(len(pages) >= 18,
          '接入区块目标页面齐备（index+落地页+文章 共 %d 个，期望 ≥18）' % len(pages))

    missing, dup, bad_cmd, bad_ld = [], [], [], []
    mismatch = []          # 数字与真值不符
    lost_honest = []       # 撤下不利事实
    lost_neutral = []      # 撤下中立声明

    # 领 key 命令的严格判据：curl 与 register 端点必须在同一条命令内。
    # （L1.12 的假绿正是因为两者分处不同位置也算通过。）
    CMD = _re.compile(r'curl\s+(?:-[^\s]+\s+|"[^"]*"\s+)*'
                      r'(?:-X\s+POST\s+)?[^\s"\'<]*roboparts\.cc/api/register')

    def anchor(txt, key):
        m = _re.search(r'data-rp="%s"[^>]*>([^<]+)<' % _re.escape(key), txt)
        return m.group(1).strip() if m else None

    for p in pages:
        t = read_text(p)
        rel = os.path.relpath(p, ROOT).replace('\\', '/')
        n = t.count('RP-ONBOARDING:START')
        if n == 0:
            missing.append(rel)
            continue
        if n > 1:
            dup.append('%s×%d' % (rel, n))

        # 去掉 shell 续行与 HTML 实体的干扰后再匹配命令
        if not CMD.search(t.replace('\\\n', ' ').replace('&quot;', '"')):
            bad_cmd.append(rel)

        for key, truth in (('credits', f['credits']),
                           ('rate_limit', f['rate_limit']),
                           ('total_entities', f['total_entities']),
                           ('oss_total', f['oss_total'])):
            got = anchor(t, key)
            if got is None or got.replace(',', '') != str(truth):
                mismatch.append('%s:%s=%s≠%s' % (rel, key, got, truth))

        # 不利事实：可比较 A 级条数、机械声明率 —— 必须在页面上且等于真值
        cmp_a = anchor(t, 'comparable_grade_a')
        pct = anchor(t, 'mech_pct')
        if cmp_a != str(f['comparable_grade_a']) or pct != str(f['mech_pct']):
            lost_honest.append('%s(可比较=%s 声明率=%s)' % (rel, cmp_a, pct))

        if '不生产、不销售、不代理' not in t:
            lost_neutral.append(rel)

        if not _re.search(r'"@type"\s*:\s*"RegisterAction"', t) or \
           not _re.search(r'"urlTemplate"\s*:\s*"[^"]*?/api/register"', t):
            bad_ld.append(rel)

    check(not missing,
          '每个被抓页面都带接入区块（缺失: %s）' % (missing[:4] or '无'))
    check(not dup, '接入区块未重复叠加（重复: %s）' % (dup[:4] or '无'))
    check(not bad_cmd,
          '领 key 命令可直接照抄执行（curl 与 /api/register 同命令内）'
          '（不合格: %s）' % (bad_cmd[:4] or '无'))
    check(not mismatch,
          '页面标注额度/限速/数据量 == 代码与数据真值（不一致: %s）'
          % (mismatch[:4] or '无'))
    check(not lost_honest,
          '不利事实仍在页面上且未被粉饰（可比较 %d 条 / 声明率 %s%%）（异常: %s）'
          % (f['comparable_grade_a'], f['mech_pct'], lost_honest[:4] or '无'))
    check(not lost_neutral,
          '中立声明保留在每个页面（撤下=放弃唯一不可复制的壁垒）'
          '（缺失: %s）' % (lost_neutral[:4] or '无'))
    check(not bad_ld,
          'JSON-LD 含指向 /api/register 的 RegisterAction（AI 机读转化路径）'
          '（缺失: %s）' % (bad_ld[:4] or '无'))

    # 真相源本身不许被硬编码绕过：区块生成器必须仍从 register.js 解析额度
    ob_src = read_text(os.path.join(ROOT, 'scripts', 'onboarding_block.py'))
    check(bool(_re.search(r"re\.search\(r'credits:\\s\*\(\\d\+\)'", ob_src)),
          '接入区块的额度仍从 register.js 现场解析（硬编码=文档与代码可各自漂移）')


# ---------- L3 API 冒烟 ----------
def layer3(url):
    print('\n[L3] API 冒烟', '(跳过，未提供 --url)' if not url else f'(目标 {url})')
    if not url:
        print('  ⏭️  传入 --url 时执行：8 页面 + /api/stats + /api/compatibility')
        return
    endpoints = [url, url + '/api/stats', url + '/api/compatibility?a=ACT-001&b=SENS-001']
    for ep in endpoints:
        try:
            req = urllib.request.Request(ep, headers={'User-Agent': 'regression'})
            with urllib.request.urlopen(req, timeout=20) as r:
                ok = r.status == 200
                check(ok, f'{ep} -> {r.status}')
        except Exception as e:
            check(False, f'{ep} -> 异常 {e}')


# ---------- L4 业务校验 ----------
def layer4():
    print('\n[L4] 业务校验（兼容矩阵）')
    doc = load_entities()
    allids = set(e['id'] for e in doc['entities'])
    cm = json.load(open(os.path.join(ROOT, 'api', 'compatibility_matrix.json'), encoding='utf-8'))
    dims = cm.get('dimensions', [])
    defined_dims = set()
    if isinstance(dims, list):
        for d in dims:
            if isinstance(d, str):
                defined_dims.add(d)
            elif isinstance(d, dict) and d.get('name'):
                defined_dims.add(d.get('name'))
    elif isinstance(dims, dict):
        defined_dims = set(dims.keys())
    check('pairs_are_illustrative' in cm, 'compatibility_pairs 已显式声明为示意样例（不伪装成数据库链接）')

    pairs = cm.get('compatibility_pairs', [])
    bad_dim = []
    unreal_ref = []
    for p in pairs:
        if p.get('dimension') not in defined_dims:
            bad_dim.append(p.get('dimension'))
        for ref in (p.get('from'), p.get('to')):
            if isinstance(ref, str) and re.match(r'^(ACT|SEN|CHIP|PROTO|PLAT|INT|LLM|ROB|DAQ)-', ref) and ref not in allids:
                unreal_ref.append(ref)
    check(len(bad_dim) == 0, f'每个 pair 的 dimension 在 dimensions 中已定义（异常: {set(bad_dim)}）')
    check(len(unreal_ref) == 0, f'引用的真实实体ID均存在于实体库（异常: {set(unreal_ref)}）')


def layer1_14():
    """守护「AI 直接读 JSON 时也能拿到可执行入口」。

    20260805-22 背景：遥测显示真实爬虫 16% 的抓取直接打在 /api/*.json 上
    （ClaudeBot 18 次 / YandexBot 22 次，命中 27→42 持续上升），
    而前两轮把入口分别补进了 llms.txt（3.3% 抓取量）和 18 个 HTML 页面。
    JSON 这一路始终是裸数据：模型拿到 688 条实体，却拿不到「怎么领 key」，
    转述给用户时只能说「有这么个库」，给不出可执行的下一步。

    这是同型断点第三次出现 —— 每次都补对了内容、补错了位置。
    因此本层不再只验「入口存在」，而是验「入口存在于被抓取的每一种载体上」。

    六条不变式：
      1. 覆盖：每个对外 JSON 都带 meta.access（蜜罐与数组型按设计豁免）
      2. 可执行：command 内 curl 与 /api/register 必须同处一条命令
      3. 一致：额度 / 限速必须等于 register.js 现场真值（不许硬编码漂移）
      4. 诚实：honest_limits 必须在，且数值等于真实统计（不许只挑好听的说）
      5. 指令式：for_ai_assistants 必须是对模型的祈使句 —— 抓到 ≠ 会转述
      6. 蜜罐洁净：honeypot.json 绝不能被注入真实入口
    """
    print('\n[L1.14] AI 直读 JSON 的接入入口（16% 抓取量的盲区）')
    import re as _re
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    try:
        from onboarding_block import facts as _facts
    except Exception as e:                                    # noqa: BLE001
        check(False, 'onboarding_block 可导入: %s' % e)
        return
    f = _facts()

    EXEMPT = {'honeypot.json', 'geo-faqs.json'}
    CMD = _re.compile(r'curl\s+(?:-[^\s]+\s+|"[^"]*"\s+|\'[^\']*\'\s+)*'
                      r'(?:-X\s+POST\s+)?[^\s"\'<]*roboparts\.cc/api/register')

    no_access, bad_cmd, bad_num, no_honest, no_ai, bad_honest = [], [], [], [], [], []
    checked = 0

    for path in sorted(glob.glob(os.path.join(ROOT, 'api', '*.json'))):
        name = os.path.basename(path)
        if name in EXEMPT:
            continue
        try:
            doc = json.loads(read_text(path))
        except Exception:                                     # noqa: BLE001
            no_access.append(name + '(解析失败)')
            continue
        if not isinstance(doc, dict):
            continue

        if name == 'openapi.json':
            acc = doc.get('info', {}).get('x-roboparts-access')
        else:
            acc = doc.get('meta', {}).get('access')

        if not isinstance(acc, dict):
            no_access.append(name)
            continue
        checked += 1

        cmd = (acc.get('how_to_get_a_key') or {}).get('command', '')
        if not CMD.search(cmd or ''):
            bad_cmd.append(name)

        if acc.get('free_credits') != f['credits'] or \
           acc.get('rate_limit_per_hour') != f['rate_limit']:
            bad_num.append('%s(%s/%s≠%s/%s)' % (name, acc.get('free_credits'),
                                                acc.get('rate_limit_per_hour'),
                                                f['credits'], f['rate_limit']))

        hl = acc.get('honest_limits')
        if not isinstance(hl, dict):
            no_honest.append(name)
        elif hl.get('cross_vendor_comparable_grade_a') != f['comparable_grade_a'] or \
                abs(float(hl.get('mechanical_interface_declared_pct', -1)) - f['mech_pct']) > 1e-6:
            bad_honest.append(name)

        ai = acc.get('for_ai_assistants') or ''
        # 必须是「让 AI 把命令转述给用户」的祈使句，而不是泛泛的描述
        if not ('转述' in ai or '给用户' in ai) or 'how_to_get_a_key' not in ai:
            no_ai.append(name)

    check(checked >= 25,
          '对外 JSON 已带机读接入声明（%d 个，期望 ≥25）' % checked)
    check(not no_access, '无对外 JSON 遗漏 meta.access（遗漏: %s）' % (no_access or '无'))
    check(not bad_cmd,
          '领 key 命令可照抄执行（curl 与 /api/register 同处一条）（违规: %s）' % (bad_cmd or '无'))
    check(not bad_num,
          'JSON 内额度/限速 == register.js 真值（漂移: %s）' % (bad_num or '无'))
    check(not no_honest,
          'JSON 内保留诚实边界 honest_limits（缺失: %s）' % (no_honest or '无'))
    check(not bad_honest,
          '诚实边界数值 == 真实统计，未被粉饰（异常: %s）' % (bad_honest or '无'))
    check(not no_ai,
          'for_ai_assistants 为指令式且要求转述领 key 命令（异常: %s）' % (no_ai or '无'))

    hp = os.path.join(ROOT, 'api', 'honeypot.json')
    if os.path.isfile(hp):
        check('/api/register' not in read_text(hp),
              '蜜罐未被注入真实接入入口（注入即暴露其用途）')


def layer1_15():
    """【L1.15】MCP 分发包：装到用户机器上必须真的能用。

    为什么需要这一层：MCP 是我们在 AI Agent 侧唯一的「可安装物」，
    它不受站点部署闸门保护 —— 站点全绿不代表包能用。
    20260805-22 已抓到一次「装上即坏」（读仓库内 ../api，npm 包里根本没有）。
    20260805-23 又抓到两个同类问题：
      · 预载无重试，一次网络抖动即拒启（本机 3 次失败 1 次）；
      · 自检用固定 sleep(6s) 等就绪 —— 计时竞态，会把「慢」误判成「坏」，
        而一个随机误报的闸门比没有闸门更糟：它训练人忽略红灯。

    六条不变式：
      1. 远程拉取必须有重试（≥2 次），且重试过程可见（不许静默）
      2. 4xx 不重试（确定性错误，重试只会掩盖真因）
      3. 不得出现「catch 后返回空数组」的静默兜底（假绿温床）
      4. 自检不得用固定 sleep 充当就绪判据，必须等真实就绪信号
      5. index.js 的 PKG_VERSION == package.json version（UA 归因靠它）
      6. 包名不得写成被第三方占位的 roboparts-mcp
    """
    print('\n[L1.15] MCP 分发包（不受站点闸门保护的唯一可安装物）')
    import re as _re
    idx = os.path.join(ROOT, 'mcp-server', 'index.js')
    stf = os.path.join(ROOT, 'mcp-server', 'selftest.mjs')
    pkgf = os.path.join(ROOT, 'mcp-server', 'package.json')
    if not os.path.isfile(idx):
        check(False, 'mcp-server/index.js 存在')
        return
    src = read_text(idx)

    m = _re.search(r'FETCH_RETRIES\s*=\s*(\d+)', src)
    check(bool(m) and int(m.group(1)) >= 2,
          '远程拉取有重试 ≥2 次（现: %s）' % (m.group(1) if m else '无'))
    check('退避重试中' in src, '重试过程可见（非静默重试）')
    check(_re.search(r'status\s*>=\s*400\s*&&.*<\s*500', src) is not None,
          '4xx 不重试（确定性错误不掩盖真因）')

    silent = _re.search(
        r'catch\s*(\([^)]*\))?\s*\{\s*[a-zA-Z_$][\w$]*\s*=\s*\[\s*\]\s*;?\s*\}', src)
    check(silent is None, '无「catch 后静默返回空数组」的假绿兜底')

    if os.path.isfile(stf):
        s = read_text(stf)
        # 用语义锚点而非裸子串（裸子串判据已两次误判，见 L1.11 / 环境要点）。
        # 判据是「就绪等待这一步由 waitFor 承担」，不是「文件里出现过某串字符」。
        check(_re.search(r"waitFor\(\s*'预载数据'", s) is not None,
              '就绪等待由 waitFor(预载数据) 承担（非固定 sleep 计时）')
        check(_re.search(r'setTimeout\(\s*r\s*,\s*6000\s*\)', s) is None,
              '未退回固定 sleep(6000) 充当就绪判据')
        check(_re.search(r"waitFor\(\s*'tools/list", s) is not None
              and _re.search(r"waitFor\(\s*'tools/call", s) is not None,
              'RPC 响应亦为事件驱动等待（tools/list 与 tools/call）')
        check('exited' in s, '自检能感知子进程提前退出并快速失败')
    else:
        check(False, 'mcp-server/selftest.mjs 存在')

    if os.path.isfile(pkgf):
        pj = json.loads(read_text(pkgf))
        mv = _re.search(r"PKG_VERSION\s*=\s*'([^']+)'", src)
        check(bool(mv) and mv.group(1) == pj.get('version'),
              'PKG_VERSION == package.json version（UA 归因不漂移，%s vs %s）'
              % (mv.group(1) if mv else '无', pj.get('version')))
        check(pj.get('name') != 'roboparts-mcp',
              '包名未使用被第三方占位的 roboparts-mcp（现: %s）' % pj.get('name'))


def layer1_16():
    """【L1.16】Hosted MCP 端点 + 实体类型治理。

    20260806-00 背景：连续三轮补「接入入口位置」（llms.txt → HTML 页 → JSON），
    /api/* 抓取占比 16% → 36.6% → 71.1%，而 stat:src:agent 恒为 0。
    位置线已被三次实验证伪 —— 瓶颈不是"找不到入口"，是"入口要求的动作太重"。
    本轮改走 hosted 端点（粘一个 URL 即可用，无需领 key / 装包 / 起进程）。

    A. 端点侧
      1. functions/mcp.js 导出 POST/GET/OPTIONS 三个处理器
      2. 兼容性裁决**唯一实现**：mcp.js 与 api/compatibility.js 均 import _lib/compat_engine.js，
         且两者都不得自带 evalDimension 本地副本（三份实现 = 同一问题三个答案）
      3. 端点必须自带遥测：免鉴权端点在 KV 里没有 user 记录，
         不埋点就会重蹈"指标看不见 = 以为没人用"
      4. /mcp 已进中间件 tracked 路径，且未被私有前缀误伤
      5. 通知（无 id 的 JSON-RPC）返回 202
      6. 诚实边界必须写进 initialize 的 instructions（中立 / 非实测 / 未声明不折算）
      7. 零件检索与推荐默认剔除 market_intelligence

    B. 数据侧（本轮由新端点自己照出来的老问题）
      8-11. entity_kind 全覆盖 / kind_basis 齐备 / 计数自洽 / 派生文件不漂移
      12.   server.json 指向线上端点且版本与 SERVER_VERSION 一致
    """
    print('\n[L1.16] Hosted MCP 端点 + 实体类型治理')
    import re as _re

    mcpf = os.path.join(ROOT, 'functions', 'mcp.js')
    engf = os.path.join(ROOT, 'functions', '_lib', 'compat_engine.js')
    cmpf = os.path.join(ROOT, 'functions', 'api', 'compatibility.js')

    if not os.path.isfile(mcpf):
        check(False, 'functions/mcp.js 存在')
        return
    check(os.path.isfile(engf), 'functions/_lib/compat_engine.js 存在（裁决逻辑唯一实现）')
    src = read_text(mcpf)

    for h in ('onRequestPost', 'onRequestGet', 'onRequestOptions'):
        check(_re.search(r'export\s+async\s+function\s+' + h, src) is not None,
              f'/mcp 导出 {h}')

    check(_re.search(r"import\s*\{[^}]*judgePair[^}]*\}\s*from\s*'\./_lib/compat_engine\.js'", src) is not None,
          'mcp.js 从 _lib/compat_engine.js 引入 judgePair（不另写一套）')
    if os.path.isfile(cmpf):
        csrc = read_text(cmpf)
        check(_re.search(r"import\s*\{[^}]*judgePair[^}]*\}\s*from\s*'\.\./_lib/compat_engine\.js'", csrc) is not None,
              'api/compatibility.js 亦复用同一引擎')
        check(_re.search(r'function\s+evalDimension', csrc) is None,
              'api/compatibility.js 未保留 evalDimension 本地副本')
    check(_re.search(r'function\s+evalDimension', src) is None,
          'mcp.js 未自带 evalDimension 本地副本')

    check(_re.search(r'function\s+recordMcp', src) is not None,
          '/mcp 自带调用遥测 recordMcp（否则新通道等于没有仪表盘）')
    check(_re.search(r"recordMcp\(context,\s*[`']tool", src) is not None,
          '遥测记录到具体工具名（知道 AI 在问什么，而非只知道有人来过）')
    check('x-roboparts-selftest' in src,
          '/mcp 遥测隔离自检探针（飞轮自己的验证流量不混入真实信号）')

    mw = read_text(os.path.join(ROOT, 'functions', '_middleware.js'))
    tracked = _re.search(r'const tracked = \[(.*?)\];', mw, _re.S)
    check(tracked is not None and "'/mcp'" in tracked.group(1),
          "/mcp 已加入中间件 tracked 路径（否则调用全落 __other 被丢弃）")
    priv = _re.search(r'const PRIVATE_PREFIXES = \[(.*?)\];', mw, _re.S)
    if priv:
        items = _re.findall(r"'([^']+)'", priv.group(1))
        blocked = [p for p in items if p == '/mcp' or '/mcp'.startswith(p + '/')]
        check(not blocked, '/mcp 未被私有前缀拦截（现命中: %s）' % (blocked or '无'))

    check(_re.search(r'status:\s*202', src) is not None,
          'JSON-RPC 通知返回 202（Streamable HTTP 规范）')

    # 【20260808-10】常量已由 INSTRUCTIONS 拆为 INSTRUCTIONS_STATIC（静态边界声明）
    # + 运行时实况两段，见 L1.56。此处放宽为兼容两种命名，但边界三条仍逐条校验。
    instr = _re.search(r'const INSTRUCTIONS(?:_STATIC)? = \[(.*?)\]\.join', src, _re.S)
    check(instr is not None, 'initialize 带 instructions 自述')
    if instr:
        body = instr.group(1)
        check('既不生产也不转售' in body, '边界①：声明中立（既不生产也不转售）')
        check('不是实验室实测' in body or '非实测' in body, '边界②：声明兼容性结论非实测')
        check('无法判定' in body, '边界③：未声明维度显式标为无法判定，不折算成兼容')

    check("entity_kind !== 'market_intelligence'" in src,
          '零件检索/推荐默认剔除 market_intelligence 条目')

    d = load_entities()
    ents = d['entities']
    missing = [e['id'] for e in ents if not e.get('entity_kind')]
    check(not missing, 'entity_kind 全覆盖（缺失 %d 条）' % len(missing))

    mi = [e for e in ents if e.get('entity_kind') == 'market_intelligence']
    no_basis = [e['id'] for e in mi if not e.get('kind_basis')]
    check(not no_basis, 'market_intelligence 条目均带 kind_basis（缺失: %s）' % (no_basis or '无'))

    # 20260809-03：新增第三档 organization（企业主体）。不变式仍是"三类求和 == 总数"，
    # 只是类别从两档变三档 —— 若将来再加档而忘了改这里，本行会立刻转红。
    org = [e for e in ents if e.get('entity_kind') == 'organization']
    no_basis_org = [e['id'] for e in org if not e.get('kind_basis')]
    check(not no_basis_org, 'organization 条目均带 kind_basis（缺失: %s）' % (no_basis_org or '无'))

    # 20260809-05：本行原来写死"三类求和"，加第四、五档时如预期转红（说明它有效），
    # 但每加一档就要改一次断言本身，不是好设计。改成**种类无关**的求和不变式：
    # 无论有几档，各档计数求和必须等于总数，且每档都得在 meta 里透出。
    from collections import Counter as _C
    kind_count = _C(e.get('entity_kind') for e in ents)
    check(sum(kind_count.values()) == len(ents),
          '各 entity_kind 计数求和 == 总数（%s → %d vs %d）'
          % (dict(kind_count), sum(kind_count.values()), len(ents)))
    comp = kind_count.get('component', 0)
    ek = d['meta'].get('entity_kinds') or {}
    ek_mismatch = {k: (ek.get(k), v) for k, v in kind_count.items() if ek.get(k) != v}
    check(not ek_mismatch,
          'meta.entity_kinds 与实际计数一致（每档都得透出；不一致: %s）' % ek_mismatch)
    # 非 component 的每一档都必须带 kind_basis（判据可追溯，不许悄悄归类）
    nb = [e['id'] for e in ents
          if e.get('entity_kind') not in (None, 'component') and not e.get('kind_basis')]
    check(not nb, '所有非 component 条目均带 kind_basis（缺失: %s）' % (nb[:5] or '无'))

    truth = {e['id']: e.get('entity_kind') for e in ents}
    drift = []

    def walk(o, fn):
        if isinstance(o, dict):
            i = o.get('id')
            if isinstance(i, str) and i in truth and ('name' in o or 'category' in o):
                if o.get('entity_kind') != truth[i]:
                    drift.append(f'{fn}:{i}')
            for v in o.values():
                walk(v, fn)
        elif isinstance(o, list):
            for v in o:
                walk(v, fn)

    api_dir = os.path.join(ROOT, 'api')
    for fn in sorted(os.listdir(api_dir)):
        if not fn.endswith('.json') or fn == 'entities.json':
            continue
        try:
            walk(json.load(open(os.path.join(api_dir, fn), encoding='utf-8')), fn)
        except Exception:
            continue
    check(not drift, '派生 api/*.json 的 entity_kind 与真相源一致（漂移 %d 处）' % len(drift))

    sj = os.path.join(ROOT, 'server.json')
    if os.path.isfile(sj):
        s = json.loads(read_text(sj))
        remotes = s.get('remotes') or []
        check(any(r.get('url') == 'https://roboparts.cc/mcp'
                  and r.get('type') == 'streamable-http' for r in remotes),
              'server.json 的 remotes 指向线上 streamable-http 端点')
        mv = _re.search(r"SERVER_VERSION\s*=\s*'([^']+)'", src)
        check(bool(mv) and mv.group(1) == s.get('version'),
              'server.json version == mcp.js SERVER_VERSION（%s vs %s）'
              % (s.get('version'), mv.group(1) if mv else '无'))
    else:
        check(False, 'server.json 存在（官方 MCP Registry 提交物）')


def layer1_17():
    """【L1.17】官方 MCP Registry 域名验证 + 私钥卫生。

    20260806-02 背景：此前连续两轮把「进官方 Registry」记为「需人工鉴权」而挂起。
    该判断是错的 —— Registry 的 HTTP 域名验证只要求在自家域名上托管
    /.well-known/mcp-registry-auth，我方本来就能自动部署，零人工依赖。
    教训写进不变式：把能自动化的事误判为人工阻塞，成本等于把 P0 无限期挂起。

    本层锁死两件会让「已发布」悄悄退化成「发布不了/发布错东西」的事：

    A. 域名验证链（任一环断掉，下次改版就发不上去，且不会有人发现）
      1. .well-known/mcp-registry-auth 存在
      2. 内容严格是 v=MCPv1; k=ed25519; p=<32字节公钥base64>
      3. server.json 的命名空间必须 == websiteUrl 主机名的反向 DNS
         （cc.roboparts ← roboparts.cc）。不等则 Registry 一定拒签，
         而本地 validate 不会报 —— 这正是只能靠断言兜住的盲区。
      4. $schema 必须是当前版本，不许停在已弃用 schema
      5. description ≤ 100（Registry 硬上限，超一个字符直接 400）
      6. remotes[0].url 与 smithery.yaml 声明的 url 一致
         （两个目录各说各话 = 其中一处必然是谎）

    B. 私钥卫生（比发不出去严重得多：私钥进仓库 = 任何人可冒名改我方条目）
      7. 工作树内不得出现 PEM 私钥
      8. .well-known/ 下不得出现任何私钥材料（该目录会随站点公开）
      9. .gitignore 必须显式挡住 .secrets/ / .tools/ / *.pem
     10. .tools/ 不得被 git 跟踪
    """
    print('\n[L1.17] 官方 Registry 域名验证 + 私钥卫生')
    import re as _re

    authf = os.path.join(ROOT, '.well-known', 'mcp-registry-auth')
    ok_auth = os.path.isfile(authf)
    check(ok_auth, '.well-known/mcp-registry-auth 存在（HTTP 域名验证凭证）')
    if ok_auth:
        raw = read_text(authf).strip()
        m = _re.fullmatch(r'v=MCPv1; k=ed25519; p=([A-Za-z0-9+/]{43}=)', raw)
        check(m is not None,
              'mcp-registry-auth 格式为 v=MCPv1; k=ed25519; p=<32字节公钥base64>')
        # 公开文件里出现私钥材料 = 域名所有权当场失守
        check('PRIVATE KEY' not in raw and not _re.search(r'\b[0-9a-f]{64}\b', raw),
              'mcp-registry-auth 只含公钥，无私钥材料')

    sj = os.path.join(ROOT, 'server.json')
    if os.path.isfile(sj):
        s = json.load(open(sj, encoding='utf-8'))
        # 反向 DNS 一致性：域名验证能否通过的充要条件
        host = _re.sub(r'^https?://', '', s.get('websiteUrl', '')).strip('/').split('/')[0]
        expect_ns = '.'.join(reversed(host.split('.'))) if host else ''
        actual_ns = s.get('name', '').split('/')[0]
        check(expect_ns and expect_ns == actual_ns,
              'server.json 命名空间 == websiteUrl 反向DNS（期望 %s / 实际 %s）'
              % (expect_ns or '无', actual_ns or '无'))
        sch = s.get('$schema', '')
        check('/2025-09-29/' not in sch and _re.search(r'/schemas/\d{4}-\d{2}-\d{2}/server\.schema\.json$', sch) is not None,
              'server.json $schema 未停留在已弃用版本（当前 %s）' % (sch.split('/schemas/')[-1] if '/schemas/' in sch else '无'))
        dlen = len(s.get('description', ''))
        check(0 < dlen <= 100, 'server.json description 长度 %d ≤ 100（Registry 硬上限）' % dlen)

        smf = os.path.join(ROOT, 'smithery.yaml')
        if os.path.isfile(smf):
            sm = read_text(smf)
            sm_url = _re.search(r'^\s*url:\s*(\S+)\s*$', sm, _re.M)
            rurl = (s.get('remotes') or [{}])[0].get('url', '')
            check(bool(sm_url) and sm_url.group(1) == rurl,
                  'smithery.yaml url == server.json remotes[0].url（%s）' % rurl)

    # 私钥卫生：遍历工作树（跳过依赖与版本库自身）
    leaked = []
    skip_dirs = {'.git', 'node_modules', '__pycache__', '.wrangler'}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            if fn.endswith(('.pem', '.key')):
                leaked.append(os.path.relpath(os.path.join(dirpath, fn), ROOT))
    check(not leaked, '工作树内无 PEM/KEY 私钥文件（发现: %s）' % (leaked or '无'))

    gi = read_text(os.path.join(ROOT, '.gitignore')) if os.path.isfile(os.path.join(ROOT, '.gitignore')) else ''
    for pat in ('.secrets/', '.tools/', '*.pem'):
        check(_re.search(r'^\s*' + _re.escape(pat) + r'\s*$', gi, _re.M) is not None,
              '.gitignore 显式挡住 %s' % pat)

    tracked = subprocess.run(['git', 'ls-files', '.tools'], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
    check(tracked == '', '.tools/ 未被 git 跟踪（发布器二进制不入库）')

    # C. 已注册的端点必须在"AI 真正读得到的地方"出现
    #    20260806-02 发现：站点已有 hosted 端点且已进官方注册表，
    #    但 llms.txt 与 18 个被抓页面里一个字都没提 —— 资产存在≠可被发现。
    #    与 L1.13 同型的结构性断点，只是这次断在新资产上。
    if os.path.isfile(sj):
        s = json.load(open(sj, encoding='utf-8'))
        rurl = (s.get('remotes') or [{}])[0].get('url', '')
        rname = s.get('name', '')

        llms = read_text(os.path.join(ROOT, 'llms.txt')) if os.path.isfile(os.path.join(ROOT, 'llms.txt')) else ''
        check(rurl and rurl in llms, 'llms.txt 载明 MCP 端点 %s' % rurl)
        check(rname and rname in llms, 'llms.txt 载明官方注册表规范名 %s' % rname)

        pages = [os.path.join(ROOT, x) for x in
                 ('index.html', 'iso-9409-flange.html', 'robot-joint-parameter-spec.html')]
        pages += sorted(glob.glob(os.path.join(ROOT, 'articles', '*.html')))
        pages = [p for p in pages if os.path.isfile(p)]
        no_ep, wrong_ep, no_name = [], [], []
        for p in pages:
            h = read_text(p)
            m1 = _re.search(r'data-rp="mcp_endpoint">([^<]+)<', h)
            m2 = _re.search(r'data-rp="mcp_registry_name">([^<]+)<', h)
            if not m1:
                no_ep.append(os.path.basename(p))
            elif m1.group(1).strip() != rurl:
                wrong_ep.append('%s→%s' % (os.path.basename(p), m1.group(1).strip()))
            if not m2 or m2.group(1).strip() != rname:
                no_name.append(os.path.basename(p))
        check(not no_ep, '每个被抓页面都载明 MCP 端点（缺失 %d 个: %s）'
              % (len(no_ep), no_ep[:3] or '无'))
        check(not wrong_ep, '页面标注的端点与 server.json 一致（不一致: %s）' % (wrong_ep[:3] or '无'))
        check(not no_name, '每个被抓页面都载明规范名 %s（缺失/不符 %d 个: %s）'
              % (rname, len(no_name), no_name[:3] or '无'))


def layer1_18():
    """【L1.18】遥测可观测性：埋点与读取端必须成对存在。

    20260806-03 背景：functions/mcp.js 老老实实把每次真实 Agent 调用写成
    metrics 键 `mcp:<event>`，源码注释还写着「read_metrics.py 无需改造即可读到」。
    实际上读取端只按 ua:/bot:/path:/ref: 四个前缀分段打印，`mcp:*` 落在所有
    分段之外 —— 数据进了 KV，却一个字都不显示。

    后果不是「少看一张表」：连续三轮把「72h 后读 metrics:mcp:*」列为 P0 待办，
    每轮都"读"了，每轮都看到空，于是每轮都得出「还没有真实 Agent 接入」。
    修好后一看，首个外部 client 早就来了（含目录站收录爬虫）。
    **看不见的指标不是零，是未知；而把未知读成零会直接改变资源投向。**

    锁死三条：
      1. read_metrics.py 必须有 mcp: 分段（本轮修复不许被回退）
      2. read_metrics.py 必须有未归类兜底，任何新前缀漏配 section 时会自曝，
         而不是像 mcp:* 那样静默消失
      3. 交叉核对：mcp.js 里 bump() 实际用到的每个命名空间前缀，
         都必须能被 read_metrics.py 的某个已知前缀覆盖 —— 这条是真正的
         不变式，前两条只是它当前的实现形态。
    """
    print('\n[L1.18] 遥测可观测性（埋点↔读取端配对）')
    import re as _re

    rm = os.path.join(ROOT, 'scripts', 'read_metrics.py')
    ok_rm = os.path.isfile(rm)
    check(ok_rm, 'scripts/read_metrics.py 存在')
    if not ok_rm:
        return
    src = read_text(rm)

    # 1) 解析读取端声明了哪些前缀：section('...', '<prefix>') + known 元组
    sec_prefixes = set(_re.findall(r"section\(\s*'[^']*'\s*,\s*'([^']+)'", src))
    # 不变式是「mcp: 被读取端处理并展示」，而不是「必须用 section() 处理」。
    # 20260806-04：本轮把 mcp: 从通用 section 升级为专用分账函数 mcp_report()，
    # 原断言只认 section() 立刻误报 —— 断言若锁死实现形态，就会在正确的
    # 重构面前变成阻力（本文件自己的 docstring 早已写明这点，却仍这么写了）。
    mcp_handled = ('mcp:' in sec_prefixes) or ("startswith('mcp:')" in src)
    check(mcp_handled,
          "read_metrics.py 处理 mcp: 前缀（真实 Agent 调用可见，section 前缀: %s%s）"
          % (sorted(sec_prefixes) or '无',
             '，另有专用分账函数' if "startswith('mcp:')" in src else ''))

    m_known = _re.search(r"known\s*=\s*\(([^)]*)\)", src)
    known_prefixes = set(_re.findall(r"'([^']+)'", m_known.group(1))) if m_known else set()
    has_fallback = bool(m_known) and 'startswith(known)' in src
    check(has_fallback,
          '读取端有未归类兜底（新埋点漏配 section 会自曝，不会被静默吞掉）')

    # 2) 交叉核对：mcp.js 真正写出去的键前缀，读取端能否覆盖
    mcpjs = os.path.join(ROOT, 'functions', 'mcp.js')
    if os.path.isfile(mcpjs):
        js = read_text(mcpjs)
        # 形如：const ns = <cond> ? 'selftest:mcp' : 'mcp';  然后 bump(`${ns}:${event}`)
        # 逐行取 `ns =` 所在行的全部字符串字面量：三元表达式用单条正则捕两个分支
        # 很容易只捕到第一个，那会让断言以为「只有 selftest」而误判。
        ns_vals = set()
        for line in js.splitlines():
            if _re.search(r'\bns\s*=', line):
                ns_vals.update(_re.findall(r"'([A-Za-z0-9_:.-]+)'", line))
        # selftest: 由读取端单独剥离处理，只需校验真实侧命名空间
        real_ns = {n for n in ns_vals if not n.startswith('selftest:')}
        covered = {n for n in real_ns
                   if any((n + ':').startswith(p) or p == n + ':'
                          for p in (sec_prefixes | known_prefixes))}
        missing = sorted(real_ns - covered)
        check(real_ns, 'mcp.js 中能解析出遥测命名空间（解析到: %s）'
              % (sorted(real_ns) or '无 —— 埋点被删或写法已变，请复核'))
        check(not missing,
              '每个 mcp.js 埋点命名空间在读取端都有归属（无归属: %s）'
              % (missing or '无'))
        # 立即落盘：MCP 调用低频，等下一个请求触发 flush 等于永久丢失
        check('waitUntil(flushMcp' in js.replace(' ', ''),
              'MCP 埋点立即落盘（低频强信号不等下一个请求，否则零流量下必丢）')


def layer1_19():
    """【L1.19】遥测分账：探针流量不得计入真实需求信号。

    20260806-04 背景：L1.18 修好「mcp:* 看不见」之后，读取端把
    `mcp:tools_list 24 / initialize 15 / client:*` 一股脑放在
    「真实 Agent 接入的唯一可归因信号」标题下。实际这些全是目录站爬虫
    与健康探针（glimind-probe / verifymcp-probe / MCP-Marketplace-Enricher
    / *-discovery），业务工具调用是 0。

    这是「自检探针污染」的第三种形态：
      一是自己的探针（已由 selftest: 前缀隔离），
      二是自己的乐观（把"被收录"读成"被使用"），
      三是**别人的探针** —— 它不带 selftest: 前缀，长得就像真实 client。
    三者后果相同：把噪声读成需求，据此改变资源投向。

    锁死四条：
      1. 存在探针识别规则 PROBE_RE，且能命中已实际出现过的探针名
      2. 存在业务工具白名单 BUSINESS_TOOLS
      3. **交叉核对：mcp.js 的 TOOLS 数组与 BUSINESS_TOOLS 逐个一致** ——
         这是真正的不变式。新增业务工具却漏加白名单，该工具的真实调用
         会被静默算成 0（写这条断言时就当场抓到白名单写错 2 个）。
      4. 判读行必须区分业务调用与探针，不得只报握手次数
    """
    print('\n[L1.19] 遥测分账（探针 ≠ 真实需求）')
    import re as _re

    rm = os.path.join(ROOT, 'scripts', 'read_metrics.py')
    if not os.path.isfile(rm):
        check(False, 'scripts/read_metrics.py 存在')
        return
    src = read_text(rm)

    m_probe = _re.search(r"PROBE_RE\s*=\s*re\.compile\(\s*(.*?)\)\s*$",
                         src, _re.S | _re.M)
    check(bool(m_probe), '存在探针识别规则 PROBE_RE')
    if m_probe:
        try:
            pat = ''.join(_re.findall(r"r?'([^']*)'", m_probe.group(1)))
            rx = _re.compile(pat, _re.I)
            # 曾真实出现在 KV 里的探针名，必须全部能被识别出来
            seen = ['glimind-probe', 'verifymcp-probe', 'rokha-probe',
                    'viperclaw1-discovery', 'MCP-Marketplace-Enricher',
                    '__verifymcp_auth_probe_c99f6ee80']
            miss = [s for s in seen if not rx.search(s)]
            check(not miss, '已出现过的探针名全部可识别（漏判: %s）' % (miss or '无'))
            # 反向：真实业务工具名不能被误判成探针，否则真需求会被抹掉
            false_pos = [t for t in ('search_components', 'check_compatibility',
                                     'recommend_for_application')
                         if rx.search(t)]
            check(not false_pos,
                  '业务工具名不会被误判为探针（误判: %s）' % (false_pos or '无'))
        except _re.error as e:
            check(False, 'PROBE_RE 可编译（%s）' % e)

    m_biz = _re.search(r"BUSINESS_TOOLS\s*=\s*\(([^)]*)\)", src, _re.S)
    biz = set(_re.findall(r"'([^']+)'", m_biz.group(1))) if m_biz else set()
    check(bool(biz), '存在业务工具白名单 BUSINESS_TOOLS（%d 个）' % len(biz))

    # 核心不变式：白名单 == mcp.js 实际注册的工具集
    mcpjs = os.path.join(ROOT, 'functions', 'mcp.js')
    if os.path.isfile(mcpjs) and biz:
        js = read_text(mcpjs)
        m_tools = _re.search(r"const\s+TOOLS\s*=\s*\[(.*?)\n\];", js, _re.S)
        declared = set(_re.findall(r"name:\s*'([^']+)'", m_tools.group(1))) \
            if m_tools else set()
        check(bool(declared),
              'mcp.js 中能解析出 TOOLS 工具名（解析到 %d 个）' % len(declared))
        if declared:
            check(declared == biz,
                  'BUSINESS_TOOLS 与 mcp.js TOOLS 完全一致'
                  '（白名单缺: %s / 白名单多余: %s）'
                  % (sorted(declared - biz) or '无', sorted(biz - declared) or '无'))

    check('业务调用' in src and '探针' in src,
          '判读行区分业务调用与探针（不把握手次数当接入数）')


def layer1_20():
    """【L1.20】ops/ 隔离与版本保护：声明的保护必须真的生效。

    20260806-04 背景：.gitignore 第 51 行注释白纸黑字写着
    「Local agent memory / private ops — never deploy to public Pages」，
    54/55 行也确实写了 `ops/` 和 `ops/**`。但 **gitignore 对已跟踪文件无效** ——
    13 份运营日报/周报在加入 ignore 之前就已被 commit，于是一直随主仓库
    推送到 **公开** 仓库 lm203688/roboparts，raw.githubusercontent 可匿名读取
    （已实测 200，单份最大 34KB）。所幸内容不含任何凭据。

    两条不变式：
      1. ops/ 下不得有任何 git 已跟踪文件 —— 这是「保护声明」与
         「保护事实」之间唯一可自动核验的桥。写了 ignore 不等于被 ignore。
      2. ops/ 自有仓库不得配置远端 —— 它的存在是为了本地可回滚
         （20260806-03 曾因无版本历史永久丢失一份日报），
         一旦挂上远端，就把刚堵住的泄露口原样重开。
    """
    print('\n[L1.20] ops/ 隔离与版本保护')

    def git(args, cwd=ROOT):
        try:
            r = subprocess.run(['git'] + args, cwd=cwd, capture_output=True,
                               text=True, timeout=20)
            return r.stdout.strip() if r.returncode == 0 else ''
        except Exception:
            return ''

    tracked = [x for x in git(['ls-files', 'ops/']).splitlines() if x.strip()]
    check(not tracked,
          '主仓库未跟踪任何 ops/ 文件（gitignore 实际生效，已跟踪 %d 个: %s）'
          % (len(tracked), tracked[:3] or '无'))

    opsdir = os.path.join(ROOT, 'ops')
    if os.path.isdir(os.path.join(opsdir, '.git')):
        remotes = [x for x in git(['remote'], cwd=opsdir).splitlines() if x.strip()]
        check(not remotes,
              'ops/ 本地仓库无远端（不会把内部运营口径推上公网，现有: %s）'
              % (remotes or '无'))
        n = len([x for x in git(['ls-files'], cwd=opsdir).splitlines() if x.strip()])
        check(n > 0, 'ops/ 已纳入本地版本历史（%d 份文档可回滚）' % n)
    else:
        check(False, 'ops/ 已建立本地版本历史（缺失则覆盖操作不可回滚）')


def layer1_21():
    """【L1.21】上报链路完整性：运行必须能自证，而不只是工作能自证。

    20260806-06 背景：20260806-04 那次运行做完了实事（改 read_metrics.py 探针
    分账、改 regression.py、建 ops/ 本地版本库 116 份、并发现 13 份运营文档
    正随主仓推向**公开**仓库），却在走到「上报」之前中断 —— 上报是任务的
    最后一步，运行被截断就整段丢失。后果不是少一份报告：

      1. 下一轮读记忆，把两件**已完成**的事当待办 P0/P1，险些重做；
      2. 该运行 `git rm --cached` 暂存了泄露修复却没提交，**泄露口一直开着**，
         而没有任何报告提到它 —— 直到 06 轮实测 raw 仍 200 才发现。

    工作会留下痕迹（commit、文件 mtime），运行不会。所以要用「有痕迹的工作」
    反查「没留下报告的运行」。四条不变式：

      1. 每条摘要独占一行 —— 追加时缺前导换行会把两条记录粘成一行，
         下游解析（含日报汇总）静默丢记录。00:00 与 02:00 已粘连。
      2. _SUMMARY 必须以换行结尾 —— 这是粘连的**根因**，锁死它才治本。
      3. 每份小时报告都要有对应摘要行（按 日期+小时 匹配，容许分钟偏移）。
      4. 无孤儿运行：最近 48h 内有 git 活动的小时，必须有对应小时报告。
         排除当前小时（本轮报告尚未写，属正常在途，否则闸门自己误报）。
    """
    print('\n[L1.21] 上报链路完整性（运行可自证）')
    import datetime as _dt

    res_dir = os.path.join(ROOT, 'ops', 'results')
    sum_path = os.path.join(res_dir, '_SUMMARY.md')
    if not os.path.isdir(res_dir) or not os.path.isfile(sum_path):
        check(False, 'ops/results/_SUMMARY.md 存在（上报链路的落点）')
        return

    with open(sum_path, encoding='utf-8') as f:
        raw = f.read()

    # 识别器唯一源：与 digest_due.append_summary 的产出形状同一份代码（勿另抄）
    REC = _load_dd().SUMMARY_REC_RE
    all_rec = REC.findall(raw)
    head_rec = [m for m in (REC.match(ln.lstrip()) for ln in raw.splitlines()) if m]
    glued = len(all_rec) - len(head_rec)
    check(glued == 0,
          '_SUMMARY 每条摘要独占一行（记录 %d / 行首 %d，粘连 %d 条 —— '
          '粘连条目会被下游解析静默丢弃）' % (len(all_rec), len(head_rec), glued))

    check(raw.endswith('\n'),
          '_SUMMARY 以换行结尾（粘连的根因：不以换行结尾则下次追加必粘连）')

    covered = {(m.group(1) + m.group(2) + m.group(3), m.group(4)) for m in head_rec}

    reports = {}
    for p in glob.glob(os.path.join(res_dir, 'roboparts-*.md')):
        m = re.match(r'roboparts-(\d{8})-(\d{2})\.md$', os.path.basename(p))
        if m:
            reports[(m.group(1), m.group(2))] = p

    empty = [os.path.basename(p) for p in reports.values()
             if os.path.getsize(p) < 80]
    check(not empty, '小时报告均非空（<80B 视为写入中断: %s）' % (empty[:3] or '无'))

    uncovered = sorted(k for k in reports if k not in covered)
    check(not uncovered,
          '每份小时报告都有 _SUMMARY 对应行（缺口: %s）'
          % ([f'{d}-{h}' for d, h in uncovered[:4]] or '无'))

    def _git_hours(cwd):
        try:
            r = subprocess.run(
                ['git', 'log', '--since=48 hours ago',
                 '--date=format:%Y%m%d %H', '--format=%ad'],
                cwd=cwd, capture_output=True, text=True, timeout=20)
            if r.returncode != 0:
                return set()
            out = set()
            for ln in r.stdout.splitlines():
                parts = ln.strip().split()
                if len(parts) == 2:
                    out.add((parts[0], parts[1]))
            return out
        except Exception:
            return set()

    active = _git_hours(ROOT) | _git_hours(os.path.join(ROOT, 'ops'))
    now = _dt.datetime.now()
    cur = (now.strftime('%Y%m%d'), now.strftime('%H'))
    earliest = min(reports) if reports else None

    orphans = []
    for slot in sorted(active):
        if slot == cur:
            continue          # 本轮在途：报告是最后一步，尚未写属正常
        if earliest and slot < earliest:
            continue          # 早于现存最早报告，可能已归档清理
        d, h = slot
        if slot in reports:
            continue
        # 跨小时收尾容差：只有当上一小时的报告**确实写于本小时**时才算覆盖。
        # 不可放宽为「上一小时有报告即可」—— 那会把 20260806-04 这类孤儿
        # 判给 03 的报告放行（本闸门初版即栽在这个假绿上）。
        prev = (d, '%02d' % (int(h) - 1)) if h != '00' else None
        if prev and prev in reports:
            wt = _dt.datetime.fromtimestamp(os.path.getmtime(reports[prev]))
            if (wt.strftime('%Y%m%d'), wt.strftime('%H')) == slot:
                continue
        orphans.append(f'{d}-{h}')
    check(not orphans,
          '无孤儿运行（有 git 活动却无小时报告的时段: %s）' % (orphans[:4] or '无'))

    # ---- 第 5 条不变式（20260806-10 补）：_LATEST 必须跟得上最新报告 ----
    # 初版只锁「报告 ↔ 摘要 ↔ 运行」三者，漏了 _LATEST。08 轮正是漏在这里：
    # 报告/摘要/记忆都写了，唯独 _LATEST 停在上一轮口径，而 _LATEST 恰恰是
    # 用户"看最新状态"的唯一入口 —— 前面都对了，用户看到的仍是旧的。
    #
    # 20260807-19 修误伤：最新那份报告若是 RECONCILED（deploy.mjs 为"非飞轮发起的
    # 部署"落的自动占位，飞轮按 L1.40 补写的指路条），它**不是一次新运行、没有新结论**，
    # 正文明写「完整记录见 roboparts-YYYYMMDD-HH.md」。此时判 _LATEST 落后是假红：
    # 用户打开 _LATEST 看到的恰恰就是那份被指向的、当前有效的结论。
    # 假红的代价不是"多看一行字"—— regression 是 deploy 的闸门，18:05→19:04 这一小时
    # 里任何真实修复都会被它拦下，而绕过它的动作是跳过**全部**闸门。
    def _reconciled_defer_slot(txt):
        """报告自述 RECONCILED 时，返回它指名退让给的那份报告 slot；否则 None。

        必须**指名**：否则只要在报告里写上 RECONCILED 就能让 _LATEST 永久停滞，
        豁免会退化成后门。调用方还要求 _LATEST >= 该 slot 才放行。
        """
        if 'RECONCILED' not in txt[:400]:      # 只认标题区自述，正文提及不算
            return None
        slots = re.findall(r'roboparts-(\d{8})-(\d{2})\.md', txt)
        return max(slots) if slots else None

    def _latest_stale(lslot, newest, cur_slot, newest_txt):
        if newest == cur_slot:
            return False                       # 本轮在途：报告是最后一步
        if lslot >= newest:
            return False
        defer = _reconciled_defer_slot(newest_txt)
        return not (defer and lslot >= defer)

    # 20260808-21 修误伤（「惩罚如实记录」族第 4 次，前三次：L1.21 tree SHA、L1.58
    # 拿"现在"审判过去、L1.49 幽灵待办）：_LATEST 正文写的是**时间区间**
    # （`2026-08-08 19:58–20:20`），因为一轮飞轮确实跨小时；旧解析只抓区间**起点**的
    # 小时，于是"起点落在上一小时"的诚实记录被判成"_LATEST 停在上一轮"。
    # 当轮实测：最新报告 slot=20、_LATEST 起点=19 → 假红。代价不是多看一行字 ——
    # regression 是 deploy 的闸门，一红就锁死这一小时内的全部部署。
    # 而规避方式是"下轮别写区间、只写结束时刻"＝又一次训练沉默，故改为区间感知。
    # 区间不是后门：末刻须晚于起刻且跨度 ≤2 小时，`00:00–23:59` 这类通吃写法无效，
    # 会退回按起点判定（该红照样红）。
    # 解析器唯一源（同上）：区间感知语义只准有一份实现
    _latest_slot = _load_dd().latest_slot

    latest_path = os.path.join(res_dir, '_LATEST.md')
    if not os.path.isfile(latest_path):
        check(False, 'ops/results/_LATEST.md 存在（用户看最新状态的总入口）')
    elif reports:
        newest = max(reports)                      # (YYYYMMDD, HH)
        ltxt = read_text(latest_path)
        lslot = _latest_slot(ltxt)
        check(lslot is not None, '_LATEST.md 含可解析的「运行时间：YYYY-MM-DD HH:MM」')

        # 对照组：区间感知必须"末刻生效"又"不给通吃后门"（纯函数判定，用例内不取环境值）
        _S = lambda t: _latest_slot('运行时间：' + t)
        _slot_cases = [
            ('区间末刻生效(19:58–20:20→20)', _S('2026-08-08 19:58–20:20'), ('20260808', '20')),
            ('ASCII 连字符同样识别',          _S('2026-08-08 19:58-20:20'), ('20260808', '20')),
            ('跨零点进位到次日',              _S('2026-08-08 23:50–00:15'), ('20260809', '00')),
            ('末刻带完整日期',                _S('2026-08-08 23:50–2026-08-09 00:15'),
                                              ('20260809', '00')),
            ('无区间时取起点(同旧版)',        _S('2026-08-08 19:58'), ('20260808', '19')),
            ('通吃区间无效→退回起点',         _S('2026-08-08 00:00–23:59'), ('20260808', '00')),
            ('倒挂区间无效→退回起点',         _S('2026-08-08 20:00–19:00'), ('20260808', '20')),
            ('无运行时间行→None',             _latest_slot('# 本文件没有运行时间'), None),
        ]
        _bad = ['%s(得 %s)' % (n, g) for n, g, w in _slot_cases if g != w]
        check(not _bad,
              '_LATEST 运行时间区间感知：末刻生效、通吃/倒挂区间不得洗白（异常: %s）'
              % (_bad or '无'))

        if lslot:
            stale = _latest_stale(lslot, newest, cur, read_text(reports[newest]))
            check(not stale,
                  '_LATEST.md 与最新小时报告同口径（_LATEST=%s-%s，最新报告=%s-%s '
                  '—— 落后即意味着用户打开总入口看到的是上一轮的结论）'
                  % (lslot[0], lslot[1], newest[0], newest[1]))

        # 对照组：豁免本身必须既抓得住真落后、又不能被一个词绕开
        _P = ('20260807', '18')
        _pos = [
            ('普通报告在前而 _LATEST 落后',
             _latest_stale(('20260807', '17'), _P, ('20260807', '19'), '# 常规报告\n修复…')),
            ('只写 RECONCILED 却不指名退让对象',
             _latest_stale(('20260807', '17'), _P, ('20260807', '19'),
                           '# RECONCILED\n本时段无独立运行')),
            ('RECONCILED 指向 17 但 _LATEST 停在 16',
             _latest_stale(('20260807', '16'), _P, ('20260807', '19'),
                           '# RECONCILED\n见 roboparts-20260807-17.md')),
        ]
        check(all(v for _, v in _pos),
              '阳性对照：三类真落后必须判红（漏网: %s）'
              % ([n for n, v in _pos if not v] or '无'))
        _neg = [
            ('RECONCILED 指向 17 且 _LATEST=17',
             _latest_stale(('20260807', '17'), _P, ('20260807', '19'),
                           '# RoboParts · 18:00（RECONCILED，非独立飞轮轮次）\n'
                           '完整记录见 roboparts-20260807-17.md')),
            ('_LATEST 与最新报告同口径',
             _latest_stale(_P, _P, ('20260807', '19'), '# 常规报告')),
            ('最新报告即本轮在途',
             _latest_stale(('20260807', '17'), _P, _P, '# 常规报告')),
        ]
        check(not any(v for _, v in _neg),
              '阴性对照：三类正常态不得误伤（误伤: %s）'
              % ([n for n, v in _neg if v] or '无'))

    # ---- 第 6 条不变式（20260807-00 补）：报告声称的提交哈希必须真实存在 ----
    # 20260806-21 那轮报告白纸黑字写着「已于 22:00 轮提交为 `4ea6d47`」，
    # 而 `git cat-file -t 4ea6d47` → Not a valid object name，reflog 里也没有。
    # 那轮的 23 个文件（13 处死锚点、api-pricing 串站、L1.34、adapter-generator）
    # 全部滞留工作区，仓库停在 de8ecdf，而线上已部署 —— **线上领先仓库**。
    #
    # 为什么前 5 条全拦不住：报告写了、摘要写了、_LATEST 也能对齐、git 有活动
    # 所以不算孤儿运行 —— 五条不变式**全绿**，唯独报告内容是假的。
    # 前 5 条锁的是"有没有留痕"，这条锁的是"留的痕是不是真的"。
    # 一个不存在的哈希比没有哈希更坏：它让下一轮以为工作已落库而不再追，
    # 滞留就此变成永久性的"线上有、仓库无"，本机一旦回滚即不可重建。
    # 语境窗口**不得跨句读**：首版写 [^\n`]{0,24} 时，"…已落地；另附内容指纹 `abcdef1`"
    # 会因为前句的"落地"把后句的内容指纹也当成"声称已提交"，属误报。
    # 闸门误报比漏报更致命 —— 恒红会逼下一轮放宽它，亲手造出要防的假绿（L1.32 教训）。
    HASH_CTX = re.compile(
        r'(?:提交|commit|推送|push|HEAD)[^\n`；;。，,、]{0,24}`([0-9a-f]{7,10})`',
        re.I)
    # 「记述一个假哈希」不等于「声称提交了它」。20260807-01 实测：00:00 轮的补写报告
    # 为了说明 4ea6d47 是伪造的，原样引用了这个哈希，结果被本闸门判为幽灵 —— 恒红。
    # 若放着不管，下一轮就会被逼去放宽哈希正则，亲手造出这条闸门本要防的假绿（L1.32 教训）。
    # 故引入否定语境豁免：附近出现「不存在/幽灵/假声明/订正」等，判为**在揭露**而非在声称。
    # 代价是有人可能靠写「不存在」绕过 —— 与 L1.36 警示语豁免同一权衡，
    # 相较「永久恒红必被放宽」，此代价可接受，且由功能性阴断言守住正常路径。
    GHOST_OK = ('不存在', '幽灵', '假声明', '伪造', '查无', '订正', '更正', '未生成')

    def _extract_claimed(text):
        """提取「声称已提交」的哈希，连同**声称的对象类型**返回 {(hash, type)}。

        提取与过滤必须同处一个函数：首版把全数字排除写在调用处的循环里，
        功能性断言只够到正则、够不到过滤，注入「取消全数字排除」时断言纹丝不动
        —— 弱断言假绿，由反向注入④暴露。

        20260808-16 修（**闸门误伤，与 L1.58 同族**）：首版只认 commit 对象，
        而本仓 push-gitdata 纪律**要求**每轮如实记录 tree SHA 做比对
        （"推送到远端（tree `2796b954` 与本地一致）"）。该 tree 在仓库中真实存在
        （`git cat-file -t` = tree），却因类型不是 commit 被判「幽灵哈希＝那轮
        已提交是假的」——恒红。危害同 L1.58：**闸门在惩罚如实记录**，而绕开它
        最省事的做法是"下轮别写 tree SHA 了"，即训练沉默、销毁自校验证据。
        改为类型感知：声称 tree 就必须真是 tree，声称提交就必须真是 commit。
        这不是放宽 —— 反而**新增**了"拿 tree SHA 冒充 commit"的检出能力。
        """
        out = set()
        for m in HASH_CTX.finditer(text):
            g = m.group(1)
            if g.isdigit():               # 排除 20260806 这类全数字日期串
                continue
            # 窗口取 ±120 字符而非整行：报告里否定语常因折行落到下一行
            # （实测「…提交为 `4ea6d47`」与「但该哈希从不存在」就分处两行）
            w = text[max(0, m.start() - 120):m.end() + 120]
            if any(k in w for k in GHOST_OK):
                continue
            # 声称类型只看**捕获组之前**的语境，不看后文：否则相邻句子里的
            # "tree" 会污染判定，把真提交误标成 tree（放宽＝制造假绿）。
            lead = text[m.start():m.start(1)].lower()
            out.add((g, 'tree' if 'tree' in lead else 'commit'))
        return out

    _co = now - _dt.timedelta(hours=48)
    cutoff = (_co.strftime('%Y%m%d'), _co.strftime('%H'))
    claimed = set()
    for (d, h), p in reports.items():
        if (d, h) < cutoff:
            continue                      # 只查最近 48h，历史归档不倒查
        claimed |= _extract_claimed(read_text(p))

    # _LATEST / _NEEDS_USER 必须一并扫：它们是用户看"最新状态"和"我要干什么"的
    # 唯一入口，假哈希写在这里的危害**大于**写在小时报告里。首版只扫
    # roboparts-*.md，由反向注入①（往其它结果文件种假哈希）当场暴露。
    for _extra in ('_LATEST.md', '_NEEDS_USER.md'):
        _p = os.path.join(res_dir, _extra)
        if os.path.isfile(_p):
            claimed |= _extract_claimed(read_text(_p))

    _hash_cache = {}

    _repos = [ROOT, os.path.join(ROOT, 'ops')]

    def _obj_type(hh):
        """返回该哈希的真实对象类型，查无返回 None。

        20260810-18 修（**第三次同族误伤**，前两次见上方 tree SHA / 否定语境）：
        用户当日 17:30 执行 `git filter-repo` 清除运营文档历史，全仓 87 个提交
        哈希被整体重写 → 此前如实记录的 3 个哈希在新对象库中查无此物，本闸门
        当场判红。**报告没造假，是历史被合法重写了。**
        走 `lib/hash_history` 统一解析：对象库没有就查 filter-repo 的 old→new
        台账，台账里有 = 它曾真实存在只是被改名。伪造的哈希两边都查不到，
        检出能力一点没降。
        """
        if hh in _hash_cache:
            return _hash_cache[hh]
        st, _cur, typ = _hh.resolve(ROOT, hh, _repos)
        _hash_cache[hh] = typ if st in ('current', 'rewritten') else None
        return _hash_cache[hh]

    def _obj_exists(hh, want='commit'):
        return _obj_type(hh) == want

    # 分两类报错：查无此物 = 幽灵（那轮"已提交"是假的）；
    # 有此物但类型不符 = 张冠李戴（如拿 tree SHA 冒充 commit），同样是假声明。
    ghost = sorted(h for (h, t) in claimed if _obj_type(h) is None)
    mistyped = sorted('%s(称%s实为%s)' % (h, t, _obj_type(h))
                      for (h, t) in claimed
                      if _obj_type(h) is not None and _obj_type(h) != t)
    check(not ghost,
          '报告声称的提交哈希在仓库中真实存在（幽灵哈希: %s —— '
          '不存在即意味着那轮"已提交"是假的，工作仍滞留工作区）'
          % (ghost[:4] or '无'))
    check(not mistyped,
          '声称的对象类型与仓库实际一致（张冠李戴: %s —— '
          '拿 tree SHA 冒充 commit 会让下一轮以为提交已落库）'
          % (mistyped[:4] or '无'))

    # ── 历史重写台账不得成为洗白通道（新增豁免路径就必须同时给出它的边界）──
    # 台账让"查不到的哈希"有了第二条生路，滥用写法是往台账里塞一对都不存在的
    # 哈希，把任意幽灵洗成"重写前的真实哈希"。三条断言封死：
    _led_map = _hh._mapping(ROOT)
    check(all(len(o) == 40 and len(n) == 40 for o, n in _led_map.items()),
          '重写台账里的哈希一律全长 40 位（缩写可撞库，等于放宽匹配面）')
    _bad_new = [n for n in list(_led_map.values())[:200]
                if _hh.object_type(ROOT, n, _repos) != 'commit']
    check(not _bad_new,
          '台账映射的**新**哈希在当前对象库中真实存在（悬空映射: %s —— '
          '两头都不存在的映射＝把幽灵洗成合法）' % (_bad_new[:3] or '无'))
    check(_hh.resolve(ROOT, 'deadbee', _repos)[0] == 'unknown'
          and _hh.resolve(ROOT, 'dead1234', _repos)[0] == 'unknown',
          '阴性: 凭空编造的哈希在台账启用后仍判幽灵（豁免只对真实映射生效）')
    if _led_map:
        _o = sorted(_led_map)[0]
        check(_hh.resolve(ROOT, _o[:7], _repos)[0] == 'rewritten',
              '阳性: 重写前的真实哈希（缩写）能被解析回当前哈希（台账真在起作用）')

    # ── 未同步到远端的历史重写，必须被"看得见" ──
    # 本地把历史洗干净、远端仍留着要删的东西 = 这次重写等于没做，而本地一切正常，
    # 没有任何现象会提醒任何人。所以：只要台账里有未同步事件，
    # (a) 用户入口 _NEEDS_USER.md 必须写着它；(b) 推送脚本必须真的拦得住。
    _pend = [e for e in _hh.load_ledger(ROOT)['events'] if not e.get('remote_synced_at')]
    if _pend:
        _nu = read_text(os.path.join(res_dir, '_NEEDS_USER.md'))
        check('远端历史清理' in _nu,
              '未同步的历史重写已写进 _NEEDS_USER.md（本地洗完远端没洗＝这次重写白做，'
              '且本地毫无异常现象会提醒任何人）')
        try:
            _r = subprocess.run(['node', 'scripts/push-gitdata.mjs'], cwd=ROOT,
                                capture_output=True, encoding='utf-8',
                                errors='replace', timeout=60)
            _out = (_r.stdout or '') + (_r.stderr or '')
        except Exception as _e:
            _out = 'EXC:%s' % _e
        check('本地历史已于' in _out,
              '行为实测: 推送脚本对未同步重写真的拦得住（不是只在注释里写了会拦）')
        check('credential' not in _out.lower(),
              '行为实测: 重写预检早于取凭据（否则真正的阻断原因会被"拿不到 token"盖掉，'
              '下一轮拿到错误诊断）')

    # 阳性下界：正则必须真的抓到东西。否则哪天把 HASH_CTX 写坏成空集，
    # ghost 恒为空 → 恒绿，这条闸门就成了摆设（L1.34 空集假绿的同族）。
    check(len(claimed) >= 1,
          '阳性：确实从近 48h 报告中解析到提交哈希（%d 个 —— '
          '为 0 说明正则失效或近期无提交记录，闸门等于空转）' % len(claimed))

    # 功能性阴阳断言：一律走 _extract_claimed（真实调用路径），不测裸正则。
    # 阳样本**同时**含"提交语境哈希"与"散文里的裸 hex"，这样才具备区分能力：
    # 首版只喂了一个哈希，把语境放宽成裸反引号后结果不变 —— 注入⑤未被拦下。
    _s = '本轮提交 `deadbee` 已落地；另附内容指纹 `abcdef1` 供比对。'
    _pos = _extract_claimed(_s)
    check(_pos == {('deadbee', 'commit')},
          '功能性·阳：只提取提交语境的哈希，散文里的裸 hex 不算声称（实得 %s）'
          % sorted(_pos))
    _neg = _extract_claimed('已提交 `20260806`')
    check(not any(x.isdigit() for x, _t in _neg),
          '功能性·阴：全数字串不被当作提交哈希（实得 %s）' % sorted(_neg))

    # ---- 类型感知的阴阳对照（20260808-16 误伤修复的守门人）----
    # 阳①：如实记录的 tree SHA 必须被标成 tree，而不是按 commit 去查（否则恒红，
    #       逼下一轮删掉 tree 校验证据 —— 这正是本次要根除的"惩罚诚实"）。
    _tree_s = '已推送到远端（tree `2796b954` 与本地一致）'
    check(_extract_claimed(_tree_s) == {('2796b954', 'tree')},
          '功能性·阳：tree 语境的哈希标为 tree（如实写 tree 校验证据不该被判幽灵）')
    # 阴①：同一个哈希若被说成"提交"，就必须按 commit 校验 —— 不许靠改措辞蒙混。
    check(_extract_claimed('本轮提交 `2796b954` 完成') == {('2796b954', 'commit')},
          '功能性·阴：说成"提交"就按 commit 校验（防把 tree 豁免扩成万能挡箭牌）')
    # 阴②：真实仓库里 2796b954 是 tree —— 冒充 commit 必须被 _obj_exists 判否。
    #       这条同时证明放宽后并未恒绿（若 _obj_exists 退化成"存在即真"，此处会假绿）。
    if _obj_type('2796b954') == 'tree':
        check(_obj_exists('2796b954', 'commit') is False,
              '功能性·阴：tree 对象冒充 commit 被判否（放宽类型≠放弃校验）')
        check(_obj_exists('2796b954', 'tree') is True,
              '功能性·阳：tree 对象按 tree 校验通过（不再误伤 push-gitdata 证据）')

    # 否定语境豁免的阴阳对照。两条必须成对存在：
    # 只有"豁免生效"会诱使把 GHOST_OK 放得过宽（极端如加入空串→全豁免→恒绿）；
    # 只有"正常仍被抓"则挡不住误报复发。
    _reveal = ('报告写着「已于 22:00 轮提交为 `4ea6d47`」，\n'
               '但该哈希**从不存在**，工作仍滞留工作区。')
    check(_extract_claimed(_reveal) == set(),
          '功能性·阳：揭露假哈希（附近有「不存在」等）不算声称，防误报逼宽正则')
    _plain = '本轮已提交为 `4ea6d47`，收工。'
    check(_extract_claimed(_plain) == {('4ea6d47', 'commit')},
          '功能性·阴：无否定语境的同一哈希仍判为声称（防豁免被放宽成恒绿）')
    check(_obj_exists('deadbee') is False,
          '功能性：不存在的哈希确实判为不存在（防 _obj_exists 恒真假绿）')

    # 需用户操作项是"我该干什么"的唯一真相源，缺失等于该通道整体失效
    check(os.path.isfile(os.path.join(res_dir, '_NEEDS_USER.md')),
          'ops/results/_NEEDS_USER.md 存在（用户问「我需要干什么」的唯一真相源）')


def layer1_22():
    """【L1.22】预算过滤的诚实性 + 工具参数语义完备性。

    20260806-07 背景：Glama 目录页把我方 5 个工具逐项打分，Purpose/Conciseness
    几乎全 5，唯独 **Parameters 维度 5 个工具里 4 个只有 3/5**，理由是
    "描述没有超出 schema 结构本身、未说明取值范围与参数间关系"。顺着这条线
    去核参数，挖出一个比评分严重得多的行为缺陷：

      线上实测 recommend_for_application(application=humanoid, budget=50)
      返回 Tesla Optimus Gen 3 / Figure 03 / EngineAI T800 —— 数万至十几万
      美元的整机，而响应里回显 budget_usd=50。

    根因两处：
      1. 过滤条件写成 `p == null || p <= budget`，**无价格的条目无条件放行**。
         全库 688 条只有 194 条带 price_range，71.8% 的库存绕过了预算约束。
      2. 解析 `String(price_range).match(/[\\d.]+/g)[0]`，字符类不含逗号，
         'From $13,500' 被截成 13 —— 最贵的条目之一因此能通过 budget=50。
         解析失败必须表现为「未知」，绝不能表现为「很便宜」。

    这与本项目在 check_compatibility 上一贯执行的教义直接冲突：厂商未声明的
    维度记为「无法判定」，既不计入兼容也不计入不兼容。**未知不得冒充通过。**
    预算过滤是这条教义唯一的破口，且破在最像「结论」的那个工具上。

    六条不变式：
      1. 不得再出现「无价格即放行」的短路写法
      2. 必须有 priceFit，且四类判定 within/partial/over/unknown 齐全
      3. 价格解析必须处理千分位逗号（否则 13,500 → 13）
      4. 不得退回单点取值 match(...)[0] 当价格
      5. 传了 budget 时，响应必须同时给出 budget_semantics 与逐品类 budget_note
      6. 每个工具参数的 description 至少 30 字符 —— 防止退回「零件 1 的 ID」
         这种只复述参数名的描述（Glama 扣分点，也是 Agent 首次调用就失败的原因）
    """
    print('\n[L1.22] 预算过滤诚实性 + 参数语义完备性')
    import re as _re
    import json as _json

    mcpf = os.path.join(ROOT, 'functions', 'mcp.js')
    if not os.path.isfile(mcpf):
        check(False, 'functions/mcp.js 存在')
        return
    src = read_text(mcpf)

    # 扫描「禁止出现的旧写法」之前必须剥离注释。
    # 初版没剥，结果闸门匹配到了本文件里**引用旧写法作为说明**的那段注释，
    # 在代码已修好的情况下报红。这种闸门会诱导下一个人靠删注释来"修绿"，
    # 把解释缺陷成因的唯一记录也一并删掉 —— 断言必须只对代码生效。
    def _strip_js_comments(s):
        s = _re.sub(r'/\*[\s\S]*?\*/', '', s)
        s = _re.sub(r'(?m)^\s*//.*$', '', s)
        return s

    code = _strip_js_comments(src)

    # 1. 「无价格即放行」的短路写法
    leak = _re.search(r'p\s*==\s*null\s*\|\|\s*p\s*<=\s*budget', code)
    check(leak is None,
          '预算过滤不放行未知价格条目（禁止 `p == null || p <= budget`：'
          '全库 71.8% 无价格，该写法等于预算参数对多数条目静默失效）')

    # 2. priceFit 四类判定齐全
    # 断言必须锁在 priceFit **函数体内**。初版只在整份源码里搜 'unknown'，
    # 而 'unknown' 在 budget_semantics 文案和 price_fit 兜底赋值里也出现，
    # 于是注入「删掉 priceFit 的 unknown 分支」时闸门照样报绿 —— 假绿。
    fit_body = _re.search(r'const priceFit = \([\s\S]*?\n  \};', code)
    check(fit_body is not None, '存在 priceFit（把价格与预算的关系判定收敛为唯一入口）')
    body = fit_body.group(0) if fit_body else ''
    for label in ('within', 'partial', 'over', 'unknown'):
        check(_re.search(r"'%s'" % label, body) is not None,
              "priceFit 函数体内覆盖 '%s' 判定" % label)

    # 3. 千分位逗号
    check(_re.search(r"replace\(\s*/\(\\d\),", src) is not None,
          "价格解析去千分位逗号（'From $13,500' 否则被截成 13，"
          '最贵条目反而能通过最低预算）')

    # 4. 单点取值
    bad_parse = _re.search(r"match\(/\[\\d\.\]\+/g\)\s*(?:\|\|\s*\[\])?\s*\[0\]", code)
    check(bad_parse is None,
          '不再以 match(/[\\d.]+/g)[0] 单点取值当价格（区间上下界必须都参与判定）')

    # 5. 响应侧口径
    check('budget_semantics' in src,
          '响应带 budget_semantics（budget_usd 单独出现会被读成"已按预算过滤干净"）')
    check('budget_note' in src,
          '逐品类给出 budget_note（各品类价格覆盖率不同，一句总说明会替差的品类背书）')

    # 6. 参数描述完备性
    tools_blk = _re.search(r'const TOOLS = \[([\s\S]*?)\n\];', src)
    if not tools_blk:
        check(False, '能定位 TOOLS 定义块')
        return
    blk = tools_blk.group(1)
    thin = []
    for m in _re.finditer(r"(\w+):\s*\{\s*type:\s*'(?:string|number|boolean)'[\s\S]{0,1200}?description:\s*((?:'[^']*'\s*\+?\s*)+)", blk):
        pname, desc_src = m.group(1), m.group(2)
        text = ''.join(_re.findall(r"'([^']*)'", desc_src))
        if len(text) < 30:
            thin.append('%s(%d字)' % (pname, len(text)))
    check(not thin,
          '每个工具参数的 description >= 30 字（只复述参数名的描述会让 Agent '
          '首次调用即失败，也是 Glama Parameters 维度扣分项；过薄: %s）' % (thin or '无'))


def layer1_23():
    """【L1.23】兼容性判定的三态不变式 —— 「无数据」既不得冒充兼容，也不得冒充不兼容。

    20260806-08 背景：07 轮留下的 P0 是「核实 ROS/mechanical_interface 两个 100%
    到底是字段存在率还是有效声明率」。核实结果是**字段存在率 100%（688/688），
    有效声明率 11.5% 与 0.3%**，站内对外口径诚实（assessed_pct=11.92 /
    fill_pct=0.57，都带 gap_note），没有把占位符渲染成覆盖 —— 那一条可以关。

    但顺着这条线往下游走，挖出比占位符严重得多的缺陷：**数据层诚实，消费层不诚实。**
    实体里 348 条 mechanical_interface.status=not_declared、338 条 n_a，
    引擎却在 protocol / mechanical 两个维度上直接 `compatible: shared.length > 0`，
    没有 null 分支 —— 厂商没公开，我们输出「不兼容」。全库 A/B 实测：
    7140 个组合里 **6062 个（84.9%）被错报不兼容**，其中 5969 个应为「无法判定」。
    BOM 检查器还会据此向用户弹出「不兼容」告警。

    这是 L1.22（预算过滤让「无价格」冒充「在预算内」= 假绿）的**镜像**：
    同一条教义的另一半破口 —— 「无机械数据」冒充「装不上」= 假红。
    L1.22 只锁了假绿，本闸门补上假红，把不变式做成双向。

    修复过程中被反噬出的三个二阶陷阱，一并锁进闸门：
      - 词表不认识 UDP/TCP → 误报「未声明」→ CAN vs Ethernet 真冲突逃逸成 null；
        补词表后 `io-link` / `powerlink` 含子串 `lin`，又与 LIN 总线「共享协议 lin」。
        → 必须词边界匹配，不得裸 includes。
      - 两方都写 proprietary，字面相同被判共享 —— Tesla 与 Figure 的专有总线不互通。
      - 双方都支持 ROS2 就给 overall=true / score=100（舵机 × AI 芯片也能满分）。
        → overall=true 必须至少有一项硬约束（协议/电气/机械）有双方声明。

    九条不变式：
      1. 全仓库 evalDimension 只有一处定义（bom/check.js 曾自带副本，判据会漂移）
      2. 消费方必须 import 引擎，不得本地重写
      3. protocol / mechanical 两个 case 在算 shared **之前**必须有 null 守卫
      4. evalDimension 四个维度全部具备 null 返回路径
      5. proprietary 列入 NON_SHAREABLE，且在 protocol 交集里被排除
      6. matchVocab 用词边界正则（防 io-link → lin）
      7. overall=true 需 HARD_DIMENSIONS 证据门槛
      8. overall=null 时 compatibility_score 必须为 null（0 分会被读成「完全不兼容」）
      9. 消费层判「不兼容」必须显式 `=== false`，不得用 `!compatible`（null 会落进去）
    """
    print('\n[L1.23] 兼容性三态不变式（无数据 ≠ 不兼容）')
    import re as _re

    engf = os.path.join(ROOT, 'functions', '_lib', 'compat_engine.js')
    bomf = os.path.join(ROOT, 'functions', 'api', 'bom', 'check.js')
    if not os.path.isfile(engf):
        check(False, 'functions/_lib/compat_engine.js 存在')
        return
    src = read_text(engf)

    # 同 L1.22：断言只对代码生效。本函数 docstring 与引擎注释里都会引用旧写法
    # 作为缺陷说明，不剥注释就会让「解释缺陷」本身触发红灯，诱导后人删注释修绿。
    def _strip_js_comments(s):
        s = _re.sub(r'/\*[\s\S]*?\*/', '', s)
        s = _re.sub(r'(?m)^\s*//.*$', '', s)
        return s

    code = _strip_js_comments(src)

    # 0. 布尔维度的三态（20260806-12 新增）
    # 字符串维度靠「空串 = 未声明」天然区分声明与否，布尔维度没有这层保护：
    # `x.ros_support === true` 会把 undefined（未声明）与 false（声明为不支持）
    # 压成同一个值，于是 688 个实体中 614 个未声明者与任一 ROS2 组件配对
    # 全部被判「不兼容」，还附带事实错误的告警「双方均有声明且不匹配」。
    # 20260806-08 只修了 protocol/mechanical，本维度漏网四轮。
    sw = code[code.find("case 'software'"):]
    sw = sw[:sw.find('case ') + 1] if sw.find('case ', 5) > 0 else sw[:900]
    check(_re.search(r"typeof\s+a\.ros_support\s*===\s*'boolean'", sw) is not None
          and _re.search(r"typeof\s+b\.ros_support\s*===\s*'boolean'", sw) is not None,
          'software 维度以 typeof === boolean 判定「是否声明」'
          '（=== true 会把未声明压成声明为 false）')
    check(_re.search(r"===\s*true\s*,\s*rb\s*=", sw) is None
          and _re.search(r"const\s+ra\s*=\s*a\.ros_support\s*===\s*true", sw) is None,
          'software 维度不再用 `=== true` 二值化布尔字段（根因写法）')
    check(sw.count('compatible: null') >= 2,
          'software 维度对「单方未声明」与「双方未声明」均返回 null，'
          '而不是只在双方都缺时才三态')

    # 上游消费层不得在进引擎前就把布尔压平（引擎再三态也救不回来）
    if os.path.isfile(bomf):
        _b = _strip_js_comments(read_text(bomf))
        check(_re.search(r'ros_support:\s*e\.ros_support\s*===\s*true', _b) is None
              and _re.search(r'ros_support:\s*it\.ros_support\s*===\s*true', _b) is None,
              'bom/check.js 不在入参归一化时用 `=== true` 压平 ros_support'
              '（会在进引擎之前就抹掉「未声明」）')

    # 1+2. 判据单一来源
    dup = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, 'functions')):
        dirnames[:] = [d for d in dirnames if d != 'node_modules']
        for fn in filenames:
            if not fn.endswith('.js'):
                continue
            p = os.path.join(dirpath, fn)
            body = _strip_js_comments(read_text(p))
            if _re.search(r'(?:function|const)\s+evalDimension\b', body):
                dup.append(os.path.relpath(p, ROOT).replace('\\', '/'))
    check(dup == ['functions/_lib/compat_engine.js'],
          '全仓库 evalDimension 仅引擎一处定义（副本会各自漂移：bom/check.js 的副本'
          '正是本轮假红的第二个现场；定义处: %s）' % (dup or '无'))

    if os.path.isfile(bomf):
        bsrc = read_text(bomf)
        check(_re.search(r"import\s*\{[^}]*evalDimension[^}]*\}\s*from\s*'[^']*compat_engine", bsrc) is not None,
              'bom/check.js 从引擎 import evalDimension（而非本地重写判据）')
        # 9. 消费层不得把 null 读成 false
        check(_re.search(r'\.compatible\s*===\s*false', bsrc) is not None,
              'BOM 告警以 `compatible === false` 判不兼容（用 `!compatible` 会把 '
              'null 一起算进去，等于在界面上把「厂商没公开」写成「装不上」）')
        check(_re.search(r'!\s*d\.compatible\b', _strip_js_comments(bsrc)) is None,
              'BOM 告警不使用 `!d.compatible` 取反式判定（null 会静默落入不兼容分支）')
        # resolved 必须透传硬约束原始字段，否则引擎读不到数据 → 全库退化成 null
        for fld in ('interfaces', 'mechanical_interface'):
            check(_re.search(r'\b%s\b' % fld, bsrc) is not None,
                  'bom/check.js 向引擎透传 %s（不透传则引擎恒判"未声明"，'
                  '三态修复会退化成「全部无法判定」）' % fld)

    # 3. protocol / mechanical 的 null 守卫必须在 shared 之前
    for dim, label in (('protocol', '协议'), ('mechanical', '机械接口')):
        m = _re.search(r"case '%s': \{([\s\S]*?)\n    \}" % dim, code)
        check(m is not None, "evalDimension 存在 case '%s'" % dim)
        if not m:
            continue
        blk = m.group(1)
        i_null = blk.find('compatible: null')
        i_shared = blk.find('const shared')
        check(i_null != -1 and (i_shared == -1 or i_null < i_shared),
              '%s维度：证据缺失守卫（compatible: null）位于 shared 交集计算之前 —— '
              '守卫在后等于先把没数据的判成不兼容（本轮全库 %s 组合受影响）'
              % (label, '84.9%'))

    # 4. 四个维度都要有 null 路径
    ev = _re.search(r'export function evalDimension[\s\S]*?\n\}', code)
    check(ev is not None, '能定位 evalDimension 函数体')
    if ev:
        body = ev.group(0)
        n_null = len(_re.findall(r'compatible: null', body))
        check(n_null >= 4,
              'evalDimension 四个维度均具备「无法判定」返回路径（当前 %d 条，'
              '缺一条就意味着该维度把缺数据二值化）' % n_null)

    # 5. proprietary 不得作为共享依据
    check(_re.search(r"NON_SHAREABLE_PROTOCOLS\s*=\s*\[[^\]]*'proprietary'", code) is not None,
          "NON_SHAREABLE_PROTOCOLS 含 'proprietary'")
    check('NON_SHAREABLE_PROTOCOLS.includes' in code,
          'protocol 交集排除 NON_SHAREABLE（双方都写 proprietary 字面相同 ≠ 互通，'
          'Tesla 与 Figure 的专有总线不会因为都叫"专有"就能对接）')

    # 6. 词边界匹配
    mv = _re.search(r'export function matchVocab[\s\S]*?\n\}', code)
    check(mv is not None, '存在 matchVocab（协议/机械词表匹配的唯一入口）')
    if mv:
        check('RegExp' in mv.group(0),
              'matchVocab 用词边界正则匹配（裸 includes 会让 `io-link`/`powerlink` '
              '命中子串 `lin`，与 LIN 总线互报「共享协议」）')

    # 7. 硬约束门槛
    check(_re.search(r"HARD_DIMENSIONS\s*=\s*\[[^\]]*'protocol'[^\]]*'electrical'[^\]]*'mechanical'", code) is not None,
          'HARD_DIMENSIONS 定义为 协议/电气/机械 三项硬约束')
    jp = _re.search(r'export function judgePair[\s\S]*?\n\}', code)
    check(jp is not None, '能定位 judgePair')
    if jp:
        jb = jp.group(0)
        check('HARD_DIMENSIONS' in jb,
              'judgePair 以硬约束为 overall=true 的门槛（否则「双方都支持 ROS2」'
              '就能让舵机 × AI 芯片拿到 100 分兼容）')
        # 8. null 判定不得给分
        check(_re.search(r"compatibility_score:\s*overall === null \? null", jb) is not None,
              'overall=null 时 compatibility_score 返回 null（返回 0 会被下游和'
              'Agent 读成「完全不兼容」，把「不知道」重新变回假红）')


def layer1_24():
    """【L1.24】错误语义不变式 —— 「你没给参数」不得伪装成「库里没这条」。

    20260806-09 背景：本轮以 Agent 身份实调线上 /mcp，把 check_compatibility 的参数名
    写成 entity_a/entity_b（schema 实为 component1_id/component2_id），线上返回：
        {"error": "未找到实体: undefined", "hint": "请先用 search_components 确认 ID。"}
    两处错：
      1. 这是关于**数据库**的断言（「未找到实体」），而真相是关于**请求**的（没给参数）；
      2. hint 主动误导 —— Agent 照办去 search_components 会发现 ID 明明存在，
         于是卡在「工具说没有、搜索说有」之间，或判定该端点数据不一致而弃用。
    实测「缺参」与「真不存在的 ID」返回**同一形状**，调用方无从区分。

    与 L1.22 / L1.23 同源：L1.22 是「无价格」冒充「在预算内」（假绿），
    L1.23 是「未声明」冒充「不兼容」（假红），本闸门是「缺参数」冒充「查无此物」——
    都是把一种失败渲染成另一种性质的结论。教义要在**所有出口**上复核。
    """
    print('\n[L1.24] 错误语义不变式（缺参 ≠ 查无此物）')
    import re as _re

    f = os.path.join(ROOT, 'functions', 'mcp.js')
    if not os.path.isfile(f):
        check(False, 'functions/mcp.js 存在')
        return
    src = read_text(f)

    # 同 L1.22/L1.23：断言只对代码生效，否则本文档字符串与源码注释里
    # 引用的旧写法会让「解释缺陷」本身触发红灯，诱导后人靠删注释修绿。
    def _strip_js_comments(s):
        s = _re.sub(r'/\*[\s\S]*?\*/', '', s)
        s = _re.sub(r'(?m)^\s*//.*$', '', s)
        return s

    code = _strip_js_comments(src)

    def _body(name):
        m = _re.search(r'function\s+' + name + r'\s*\([^)]*\)\s*\{', code)
        if not m:
            return None
        i = m.end() - 1
        depth = 0
        for j in range(i, len(code)):
            if code[j] == '{':
                depth += 1
            elif code[j] == '}':
                depth -= 1
                if depth == 0:
                    return code[i:j + 1]
        return None

    # 1. dispatch 层必须有 schema 驱动的必填校验
    check(_re.search(r'TOOLS\.find\s*\(', code) is not None,
          'dispatch 层用 TOOLS.find 取工具 spec（校验以对外公布的 schema 为唯一依据）')
    check(_re.search(r'inputSchema\?\.\s*required', code) is not None,
          '必填清单取自 inputSchema.required，而非另写一份硬编码参数名（两份必然漂移）')
    # 缺参分支必须以 -32602 返回，且断言作用域锁到该分支**内部**。
    # 初版在整份源码里搜 '-32602' 与 'missing_parameters'，被「未知工具」分支和
    # 分支外的残留字符串喂饱而恒真 —— 注入「缺参不走 -32602」时假绿放行。
    # 这正是 L1.22 已经写下的教训（存在性断言必须限定作用域），本闸门初版又犯了一次。
    mblk = None
    mm = _re.search(r'if\s*\(\s*missingArgs\.length\s*\)\s*\{', code)
    if mm:
        i = mm.end() - 1
        depth = 0
        for j in range(i, len(code)):
            if code[j] == '{':
                depth += 1
            elif code[j] == '}':
                depth -= 1
                if depth == 0:
                    mblk = code[i:j + 1]
                    break
    check(mblk is not None, '可定位缺参分支 if (missingArgs.length) {...}')
    check(mblk is not None and 'rpcError' in mblk and '-32602' in mblk,
          '缺参分支**内部**以 rpcError(-32602) 返回（协议层请求错误；在整份源码里搜 '
          '-32602 会被「未知工具」分支喂饱而恒真，故必须锁到分支内）')
    check(mblk is not None and 'missing_parameters' in mblk,
          '缺参分支**内部**回传 missing_parameters 明细（让调用方知道缺哪个，不必自己猜）')

    # 2. 守卫必须在实体查找**之前**。锁顺序而非禁用 map[...] 写法：
    #    守卫之后再查找是合法的，一刀切禁用只会逼人绕写法。
    for fn, lookup_re in (
        ('toolDetail', r'map\[\s*id\s*\]'),
        ('toolCompat', r'map\[\s*args\.component1_id\s*\]'),
    ):
        body = _body(fn)
        if body is None:
            check(False, '%s 可定位' % fn)
            continue
        gi = body.find('invalid_params')
        m = _re.search(lookup_re, body)
        check(gi >= 0, '%s 有缺参守卫（error_kind: invalid_params）' % fn)
        check(m is not None and gi >= 0 and gi < m.start(),
              '%s 的缺参守卫位于实体查找之前（放在后面时 map[undefined] 已经落空，'
              '错误仍会被渲染成「未找到实体: undefined」）' % fn)
        check("'not_found'" in body,
              '%s 的查无此物分支标注 error_kind: not_found（让调用方能机器区分两类失败）' % fn)

    # 3. 不得让 undefined 流进「未找到实体」文案
    for fn in ('toolDetail', 'toolCompat'):
        body = _body(fn) or ''
        check(_re.search(r'未找到实体:\s*\$\{\s*args\?\.', body) is None,
              '%s 的 not_found 文案不再内插可选链取值（args?.x 为 undefined 时会打印出'
              '「未找到实体: undefined」，把请求错误伪装成数据事实）' % fn)


def layer1_25():
    """【L1.25】账本诚实不变式 —— 「账本读不出来」不得伪装成「你没有交易」。

    20260806-10 背景：wrangler.toml 只绑定了 USER_CREDITS / API_KEYS / SUPPLIERS /
    SUPPLIER_INQUIRIES / URDF_LIBRARY，**从未绑定 USER_CREDIT_HISTORY**。
    而 4 处代码都写成 `if (env.USER_CREDIT_HISTORY) { ... }`，于是生产环境里：
      - register.js 注册赠送 100 积分 → 账本一条没写
      - webhook.js  真实付款到账      → 账本一条没写（钱进来了，查无对证）
      - history.js  查询              → success:true + history:[] + 消费0/充值0
      - credits-history.html          → 「暂无消费记录 · 您的账户暂无积分变动记录」
    把「我们从没记过账 / 读不出来」渲染成「你没有交易」。这是对用户账户的事实断言，
    而真相是关于我们自己的存储 —— 在钱上撒谎。

    同族第 4 例（L1.22 无价格→在预算内 / L1.23 未声明→不兼容 / L1.24 缺参→查无此物）。
    本闸门另锁三个连带出口：
      a) balance.js 把「key 不存在」渲染成「credits:0, plan:free」并返回 200；
      b) credits.html 把「预读余额失败」当成基线 0，导致失败的支付被判成"充值成功"；
      c) selection/engine.js 把「取数失败」渲染成「该品类无匹配零件」。
    """
    print('\n[L1.25] 账本诚实不变式（读不出账本 ≠ 你没有交易）')
    import re as _re

    def _strip_js_comments(s):
        s = _re.sub(r'/\*[\s\S]*?\*/', '', s)
        s = _re.sub(r'(?m)^\s*//.*$', '', s)
        return s

    # ---------- 1. 账本模块本身 ----------
    lf = os.path.join(ROOT, 'functions', '_lib', 'ledger.js')
    if not os.path.isfile(lf):
        check(False, 'functions/_lib/ledger.js 存在（账本读写唯一入口）')
        return
    lcode = _strip_js_comments(read_text(lf))

    check(_re.search(r"status:\s*'unavailable'", lcode) is not None,
          "readLedger 有 'unavailable' 态（没有后端/读失败 ≠ 空账本）")
    check(_re.search(r"status:\s*'corrupt'", lcode) is not None,
          "readLedger 有 'corrupt' 态（解析不出 ≠ 空账本）")
    check(_re.search(r"status:\s*'empty'", lcode) is not None,
          "readLedger 有 'empty' 态（唯一允许对外说「暂无记录」的情形）")
    bad_records = _re.findall(r"status:\s*'(?:unavailable|corrupt)'[^}]*?records:\s*\[\]", lcode)
    check(not bad_records,
          'unavailable/corrupt 时 records 为 null 而非 []（给 [] 会被上层直接渲染成「没有交易」）')
    m = _re.search(r'export function summarizeLedger\s*\([^)]*\)\s*\{([\s\S]*?)\n\}', lcode)
    check(m is not None, '可定位 summarizeLedger')
    if m:
        sb = m.group(1)
        check(_re.search(r"status\s*!==\s*'ok'[\s\S]{0,80}?status\s*!==\s*'empty'", sb) is not None,
              'summarizeLedger 先判可读性再算数（不可读直接短路）')
        check(_re.search(r'total_consumed:\s*null', sb) is not None and
              _re.search(r'total_recharged:\s*null', sb) is not None,
              '不可读时汇总返回 null 而非 0（0 会被页面渲染成「消费 0 / 充值 0」，'
              '读者分不清「确实没花过」和「我们不知道」）')
    check("'creem_payment'" in lcode and "'grant'" in lcode,
          "RECHARGE_TYPES 涵盖 creem_payment 与 grant（旧实现只认 'recharge'，"
          "一笔真实 Creem 付款在列表里看得见却不计入 total_recharged）")
    check('USER_CREDITS' in lcode and 'LEDGER_FALLBACK_PREFIX' in lcode,
          'ledgerStore 在 USER_CREDIT_HISTORY 未绑定时回落到已绑定的 USER_CREDITS'
          '（否则账本永远写不进去）')

    # ---------- 2. 四处调用方不得再各写各的 ----------
    for rel in [('functions', 'api', 'credits', 'history.js'),
                ('functions', 'api', 'credits', 'balance.js'),
                ('functions', 'api', 'credits', 'webhook.js'),
                ('functions', 'api', 'register.js')]:
        p = os.path.join(ROOT, *rel)
        name = '/'.join(rel[1:])
        if not os.path.isfile(p):
            check(False, f'{name} 存在')
            continue
        c = _strip_js_comments(read_text(p))
        check(_re.search(r"from\s+'[^']*_lib/ledger\.js'", c) is not None,
              f'{name} 通过 _lib/ledger.js 读写账本（唯一入口，杜绝 4 份实现漂移）')
        check(_re.search(r'if\s*\(\s*env\.USER_CREDIT_HISTORY\s*\)', c) is None,
              f'{name} 不再用 `if (env.USER_CREDIT_HISTORY)` 静默跳过'
              f'（该 KV 未绑定时该分支恒 false，等于账本功能整体消失且无人知晓）')

    # ---------- 3. history.js：不可读必须走非 2xx ----------
    hc = _strip_js_comments(read_text(os.path.join(ROOT, 'functions', 'api', 'credits', 'history.js')))
    check('ledgerHttp' in hc and _re.search(r'if\s*\(\s*httpErr\s*\)', hc) is not None,
          'history.js 在返回成功体之前先做不可读拦截')
    i_guard = hc.find('httpErr')
    i_ok = hc.find('success: true')
    check(i_guard != -1 and i_ok != -1 and i_guard < i_ok,
          '不可读拦截位于 success:true 之前（放在后面则空账本已经被当成功返回了）')
    check('ledger_status' in hc,
          'history.js 对外透出 ledger_status，让调用方能区分 empty 与 unavailable')

    # ---------- 4. balance.js：key 不存在 ≠ 余额 0 ----------
    bc = _strip_js_comments(read_text(os.path.join(ROOT, 'functions', 'api', 'credits', 'balance.js')))
    check(_re.search(r"error_kind:\s*'not_found'", bc) is not None,
          "balance.js 对不存在的 key 返回 error_kind:'not_found'（与 history.js 口径一致）")
    nf_blocks = _re.findall(r"error_kind:\s*'not_found'[\s\S]{0,220}?\}\)", bc)
    check(bool(nf_blocks) and all(('credits:' not in b and 'plan:' not in b) for b in nf_blocks),
          'not_found 响应体不含 credits/plan（一个不存在的账户没有余额属性；'
          '带上就等于邀请调用方把它读成「余额 0 的 free 账户」）')
    check(_re.search(r"error_kind:\s*'service_unconfigured'", bc) is not None,
          'balance.js 对「积分系统未绑定」返回 service_unconfigured 而非 credits:0')
    check(_re.search(r"\?\s*read\.records\s*:\s*null", bc) is not None,
          'balance.js 的 history 字段在不可读时为 null 而非 []')

    # ---------- 5. 消费层（前端）不得把 null 兜回 0 ----------
    fh = os.path.join(ROOT, 'credits-history.html')
    if os.path.isfile(fh):
        f = read_text(fh)
        check(_re.search(r'data\.total_consumed\s*\?\?[^\n]*?\?\?\s*0', f) is None and
              _re.search(r'data\.total_consumed\s*\?\?\s*0', f) is None,
              'credits-history.html 不再用 `?? 0` 把 null 兜成 0'
              '（后端诚实返回 null，前端一兜底就前功尽弃 —— 数据层的诚实不会自动传导到消费层）')
        check('historyUnknown' in f,
              '页面有独立的「账本读不出来」状态，与「暂无消费记录」分开')
        check('lastLedgerStatus' in f,
              'renderHistory 依据 lastLedgerStatus 决定显示哪种空态'
              '（空数组有两种来源，不能都归到「你没有交易」）')
        mm = _re.search(r'if\s*\(historyRecords\.length\s*===\s*0\)\s*\{([\s\S]{0,900}?)\n  \}', f)
        check(mm is not None and 'lastLedgerStatus' in mm.group(1),
              '空数组分支**内部**先判 lastLedgerStatus 再决定文案（守卫放在分支外不起作用）')
        check(_re.search(r'let\s+lastLedgerStatus\s*=\s*null', f) is not None,
              "lastLedgerStatus 初值为 null 而非 'empty'（没查过时不能默认「你没有交易」）")

    # ---------- 6. credits.html：基线未知不得当 0 ----------
    fc = os.path.join(ROOT, 'credits.html')
    if os.path.isfile(fc):
        f = read_text(fc)
        # 注释里常引用旧写法作解释，断言只应对「代码」生效（剥离注释后再扫描，
        # 否则会命中自己的解释性注释而假红 —— L1.22 同型教训）
        fc_code = _strip_js_comments(f)
        check(_re.search(r'let\s+creditsBeforePayment\s*=\s*0\s*;', fc_code) is None,
              'creditsBeforePayment 初值不是 0（初值给 0 时，轮询首次读到 credits>0 '
              '就会把一笔**失败**的支付判成「充值成功」）')
        check(_re.search(r'preData\.credits\s*\|\|\s*0', fc_code) is None,
              '预读余额失败时基线为 null 而非 `preData.credits || 0`'
              '（基线为 0 会让"用户本来就有余额"被读成"这笔充值到账了"，'
              '并把整个余额当成本次充值额显示）')
        check(_re.search(r'creditsBeforePayment\s*===\s*null', fc_code) is not None,
              '轮询在基线未知时先补基线并跳过判定，不做"增加"比较')

    # ---------- 7. selection/engine.js：取数失败 ≠ 无匹配 ----------
    ec = os.path.join(ROOT, 'functions', 'api', 'selection', 'engine.js')
    if os.path.isfile(ec):
        e = _strip_js_comments(read_text(ec))
        m2 = _re.search(r'async function fetchCategoryData\s*\([^)]*\)\s*\{([\s\S]*?)\n\}', e)
        check(m2 is not None, '可定位 fetchCategoryData')
        if m2:
            fb = m2.group(1)
            check(_re.search(r'return\s*\[\s*\]', fb) is None,
                  'fetchCategoryData 失败时不再 `return []`'
                  '（空数组会被调用方当成「该品类确实没有符合条件的零件」）')
            check('ok: false' in fb and 'ok: true' in fb,
                  'fetchCategoryData 返回 {ok, items, reason} 三元组')
        check(_re.search(r'if\s*\(\s*!fetched\.ok\s*\)', e) is not None,
              '调用方先判 fetched.ok 再取 items（守卫必须在使用之前）')
        check('unavailable_categories' in e,
              '响应显式声明哪些品类是「没读到数据」而非「没有匹配项」')

    # ---------- 8. bom/check.js：供应商降级要留痕，且不得用模块级可变状态 ----------
    bp = os.path.join(ROOT, 'functions', 'api', 'bom', 'check.js')
    if os.path.isfile(bp):
        b = _strip_js_comments(read_text(bp))
        check('supplier_sources_degraded' in b,
              'BOM 检查透出 supplier_sources_degraded（purchase_options 为空可能是'
              '「没读到」而非「没有渠道」）')
        check(_re.search(r'^const\s+SUPPLIER_DEGRADED\s*=\s*\[\s*\]', b, _re.M) is None,
              'degraded 收集器不是模块级数组（Workers 的模块作用域在同一 isolate 内'
              '跨请求存活，模块级可变状态会把上一个请求的故障算到下一个请求头上'
              '—— 同 mcp.js 模块顶层 Math.random() 那次全站 404 事故）')
        check('newDegradedCollector' in b,
              '存在按请求创建收集器的工厂函数')


def layer1_26():
    """【L1.26】指标归因不变式 —— 「无法归因」不得伪装成「已剔除探针」。

    同族第 5 例，但出口换到了**观测层**：前四例（L1.22 无价格→在预算内、
    L1.23 未声明→不兼容、L1.24 缺参→查无此物、L1.25 读不出账本→你没有交易）
    都发生在对外响应里；本例发生在**我们自己读数的地方**，危害反而更大——
    对外假绿骗的是用户，读数假绿骗的是决策者本人，且会一路写进战略结论。

    历史事故：read_metrics.py 打印「MCP 业务调用 18 次（探针 client 16 次已剔除）」，
    而 biz 从未被减过。client:* 记于 initialize、tool:* 记于 tools/call，
    无状态 HTTP 下分属两个独立请求，两条计数线**不可相减**。
    于是「不可归因」被渲染成「已归因并剔除」，让最影响商业判断的指标凭空获得可信度。

    锁三件事：
      1) 调用现场必须写 toolsrc 归因线（否则永远只有裸数字）；
      2) 读侧不得再宣称「已剔除」，必须给出区间并显式标注不可归因量；
      3) 不得用 client:* 去减 tool:*（跨事件相减是根因本身）。
    """
    print('\n[L1.26] 指标归因不变式（无法归因 ≠ 已剔除探针）')
    import re as _re

    # 同 L1.22~L1.25：断言只对代码生效。本闸门的 docstring 与被测文件的注释里
    # 都必然引用旧话术（「已剔除」）来记录事故成因，直接扫原文会自我假红，
    # 并诱导后人删注释修绿。
    def _strip_js_comments(s):
        s = _re.sub(r'/\*[\s\S]*?\*/', '', s)
        s = _re.sub(r'(?m)^\s*//.*$', '', s)
        return s

    mp = os.path.join(ROOT, 'functions', 'mcp.js')
    if os.path.isfile(mp):
        m = _strip_js_comments(read_text(mp))
        check('toolsrc:' in m,
              'tools/call 现场写 toolsrc:<kind>:<tool> 归因线（无归因线则业务调用'
              '永远是不可分账的裸数字）')
        check(_re.search(r'function\s+callerKind', m) is not None,
              '存在 callerKind() 按 User-Agent 归类调用方（tools/call 现场唯一'
              '稳定可得的调用方线索；clientInfo 只在 initialize 出现）')
        idx = m.find("case 'tools/call'")
        seg = m[idx:idx + 1200] if idx >= 0 else ''
        check('toolsrc:' in seg and 'tool:' in seg,
              'toolsrc 与 tool 在同一 tools/call 分支内成对写入（分开写会重新'
              '制造两条不可对齐的计数线）')

    rp = os.path.join(ROOT, 'scripts', 'read_metrics.py')
    if os.path.isfile(rp):
        r = read_text(rp)
        # 只看代码：注释/docstring 里为复盘事故必然引用旧话术，
        # 直接扫原文会诱导「删注释修绿」（L1.25 初版踩过同一个坑）。
        code = '\n'.join(ln for ln in r.splitlines()
                         if not ln.lstrip().startswith('#'))
        check('已剔除' not in code,
              '读侧不再宣称「探针已剔除」（biz 从未被减过，这句话把无法归因'
              '说成了已归因）')
        check('toolsrc' in code, '读侧消费 toolsrc 归因线')
        check('不可归因' in code,
              '读侧对未覆盖埋点的历史业务调用显式标注「不可归因」，'
              '而不是默认算作真实需求')
        check(_re.search(r'biz\s*-\s*probe_c', code) is None,
              '不存在用 client 计数去减 tool 计数的跨事件相减（根因）')
        check(_re.search(r'real_lo', code) is not None and '区间' in code,
              '真实需求以区间[下界,上界]呈现，而非单一确定数字')


def layer1_27():
    """【L1.27】故障归类不变式 —— 「我们没读到 / 没验成」不得伪装成「没有 / 你没买」。

    同族第 6 例，一次锁住上一轮记忆里预判的两个出口：
      · 上游失败   → 查无此物      （数据面）
      · 权限验不了 → 你是免费用户  （付费面，涉钱）

    历史事故（三处同型，均为静默吞异常）：
      1) api/oss.js loadOss(): fetch 抛错 / !resp.ok / JSON 解析失败一律 catch → {data: []}，
         于是 ?stats=1 返回 total:0、列表返回 total_matched:0，**且都是 HTTP 200**。
         对一个兼容性平台而言，这等于对用户说「开源组件库是空的 / 这个零件不存在」。
      2) api/bom/check.js loadAllEntities(): 三个目录源逐个 continue / catch 吞掉，
         **全部失败也照常返回空 map**，下游把每个 BOM 行判成「自定义组件·无声明」，
         最终以 undecided_pairs + evidence_note 宣称「证据不足」——
         而真相是我们连目录都没读到。等于把 L1.23 刚修好的三态从后门又伪造了一遍。
      3) 两个文件的 resolveTier() 均 catch(e){} 后落到 'free'：KV 抛错、Creem 超时、
         绑定缺失，一律渲染成「你不是 Pro」，付费用户被剥字段并收到升级话术；
         bom/check 更会直接回 402 拒绝服务。与 L1.25 同为涉钱假断言，方向相反：
         L1.25 是「读不出账本→你没有交易」，本例是「验不了密钥→你没有权限」。

    锁四件事：
      1) 数据源加载失败必须以 503 + error_kind 表达，禁止 200 + 空集合；
      2) 目录部分降级必须在结果里显式声明，不得让「未命中」冒充「未声明」；
      3) 鉴权必须四态（含 unverified），禁止把校验故障折叠进 free；
      4) unverified 下禁止升级话术 / 402 拒服务（那是对用户付费状态的断言）。
    """
    print('\n[L1.27] 故障归类不变式（读不到 ≠ 没有；验不了 ≠ 你没买）')
    import re as _re

    # 同 L1.25/L1.26：只对代码生效。本闸门 docstring 与被测文件注释里必然
    # 引用旧写法来记录事故成因，扫原文会自我假红并诱导后人删注释修绿。
    def _strip_js_comments(s):
        s = _re.sub(r'/\*[\s\S]*?\*/', '', s)
        s = _re.sub(r'(?m)^\s*//.*$', '', s)
        return s

    lib = os.path.join(ROOT, 'functions', '_lib', 'upstream.js')
    check(os.path.isfile(lib),
          '存在统一的上游/鉴权诚实层 functions/_lib/upstream.js'
          '（同型缺陷各修各的必然再次漂移）')
    if os.path.isfile(lib):
        u = _strip_js_comments(read_text(lib))
        check('upstream_unavailable' in u and '503' in u,
              '提供 503 upstream_unavailable 出口（区分「我们没读到」与「查询为空」）')
        for st in ('unverified', 'verified_pro', 'verified_free', 'anonymous'):
            check(st in u, f'鉴权状态机含 {st} 态（四态缺一就会把故障折叠成 free）')
        check('auth_unavailable' in u,
              '提供 auth_unavailable 出口：验不了密钥时让路，而不是按免费层拒服务')
        idx = u.find('UNVERIFIED_COPY')
        seg = u[idx:idx + 400] if idx >= 0 else ''
        check('不代表' in seg,
              'unverified 文案显式声明「不代表你的订阅无效」，而非沉默降级')
        # 反向不变式：不得把上游的「裁决」一律说成「故障」。
        # 首版把 Creem 对无效 license 的 404 判成 unverified，等于替一个无效密钥
        # 编造系统故障 —— 与本闸门所修缺陷同族、方向相反。
        check(_re.search(r'r\.status\s*===\s*404', u) is not None
              and _re.search(r"r\.status\s*===\s*404[\s\S]{0,220}verified_free", u) is not None,
              '上游 404/400（查无此 license）判为裁决 verified_free，'
              '不冒充「校验链路不可用」')
        check('key_status' in u,
              '裁决结果附 key_status，区分「密钥无效」与「我们没验成」')

    op = os.path.join(ROOT, 'functions', 'api', 'oss.js')
    if os.path.isfile(op):
        o = _strip_js_comments(read_text(op))
        check('return { meta: {}, data: [] }' not in o,
              'oss.js 不再在 catch 中静默返回空数据集（根因写法）')
        check('upstreamUnavailableResponse' in o,
              'oss.js 数据源不可用时走 503，而不是 200 + total:0')
        check('resolveAuthState' in o and 'resolveTier' not in o,
              'oss.js 已切到四态鉴权，旧的二值 resolveTier 已移除')
        check('tierMessage' in o,
              'oss.js 分层文案经 tierMessage 收口（unverified 下不得输出「需 Pro」）')
        check(_re.search(r"auth_state\s*===\s*'unverified'\s*\?\s*undefined\s*:\s*UPGRADE_URL", o) is not None,
              'unverified 时不下发 upgrade_url（向付费用户投放升级引导即在指认其未付费）')

    bp = os.path.join(ROOT, 'functions', 'api', 'bom', 'check.js')
    if os.path.isfile(bp):
        b = _strip_js_comments(read_text(bp))
        check('loadJsonAsset' in b and 'catalogFailures' in b,
              'bom/check 目录加载改用可回报失败的 loadJsonAsset')
        check(_re.search(r'catalog\.okCount\s*===\s*0', b) is not None
              and 'upstreamUnavailableResponse' in b,
              '三源全失败时拒绝给结论（此时任何「证据不足」都是伪造的）')
        check('evidence_complete' in b and 'catalog_sources_degraded' in b,
              '目录部分降级在 summary 中显式声明，不让「未命中」冒充「未声明」')
        check('lookup_state' in b,
              '每个组件标注 lookup_state，区分 catalog 命中 / 未命中 / 目录降级')
        check("authInfo.auth_state === 'unverified'" in b and 'authUnavailableResponse' in b,
              'unverified 时免费额度拦截让路（回 503 而非 402「升级 Pro」）')
        check('resolveTier' not in b,
              'bom/check 旧的二值 resolveTier 已移除（catch→free 是涉钱假断言的根因）')


def layer1_28():
    """【L1.28】选型引擎的 ROS 三态 —— 「厂商未声明」不得被判成「不支持 ROS」。

    L1.23 修的是 compat_engine 的兼容判定，但**同型缺陷散落在不同文件里各修各的**：
    /designer 背后的 functions/api/selection/engine.js 有四处仍在用 truthy 判断
    （`if (actuator.ros_support)` / `if (!chip.ros_support)`），把 undefined 与 false
    折叠成同一个分支，于是输出「警告：不支持ROS」「原生不支持ROS，需自行编写驱动」。

    影响面不是边角：688 实体中 614 个（89%）从未声明 ros_support，
    执行器 199 个里 167 个（84%）未声明。也就是说选型引擎——平台的旗舰功能——
    对大多数器件给出的是**厂商从未说过的事实断言**。

    讽刺的是同文件 sanityWarnings 里早就写对了（`!== undefined` + 显式 === false/true），
    正确写法一直在旁边，只是没被推广到另外四处。故本闸门锁「全文件级」不变式。
    """
    print('\n[L1.28] 选型引擎 ROS 三态（未声明 ≠ 不支持）')
    import re as _re

    # 同 L1.25~L1.27：只对代码生效。docstring 与引擎注释里必然引用旧写法
    # 来记录事故成因，扫原文会自我假红并诱导后人删注释修绿。
    def _strip_js_comments(s):
        s = _re.sub(r'/\*[\s\S]*?\*/', '', s)
        s = _re.sub(r'(?m)^\s*//.*$', '', s)
        return s

    eng = os.path.join(ROOT, 'functions', 'api', 'selection', 'engine.js')
    check(os.path.isfile(eng), '存在 functions/api/selection/engine.js')
    if not os.path.isfile(eng):
        return
    e = _strip_js_comments(read_text(eng))

    check('function rosState' in e,
          '提供统一的 rosState() 三态判定（同型缺陷各处各判必然再次漂移）')
    for st in ("'yes'", "'no'", "'unknown'"):
        check(st in e, f'rosState 返回值含 {st} 态（三态缺一即退化为布尔）')

    # 核心：禁止任何 truthy / 取反 形式的 ros_support 判断
    truthy = _re.findall(r'if\s*\(\s*!?\s*\w+\.ros_support\s*\)', e)
    check(not truthy,
          f'全文件无 truthy 形式的 ros_support 判断（残留: {truthy}）')

    # 「不支持」话术只允许挂在明确 === 'no' 的分支上
    for kw in ('原生不支持ROS', '不支持ROS'):
        for m in _re.finditer(_re.escape(kw), e):
            seg = e[max(0, m.start() - 320):m.start()]
            check("=== 'no'" in seg,
                  f'「{kw}」话术仅出现在 rosState()===no 分支内，不覆盖未声明项')
            break

    check("=== 'unknown'" in e and '未声明' in e,
          '未声明分支有独立文案，明确告知「非不支持」而非沉默按不支持处理')

    # 反向不变式：未声明不得反过来冒充「支持」而白给生态分（假绿）
    check(_re.search(r"rosState\([^)]*\)\s*===\s*'yes'", e) is not None,
          "加分分支限定 === 'yes'，未声明不得冒充已声明支持（防假绿）")


def layer1_29():
    """【L1.29】对外分发素材的数字必须与真相源一致。

    L2 锁了七处内部数字（entities.json / data.js / 分类JSON / README / llms.txt /
    agent-discovery / api/data.json），但 **content/ 下的对外投稿稿件不在其中**——
    而那才是真正会被外部读到的东西。

    实测：content/ros-discourse-post.md 长期写着「489+ entities」并附一张
    每一格都过期的分类表（Actuators 155 / Sensors 62 / Chips 103 …），
    真值是 688（199/90/108…）。这稿子是准备发到 ROS Discourse 的外链素材，
    发出去等于对整个社区公布一份错误的自我描述，且是**低报**自己的数据量。

    对外说错数字比内部不一致更贵：内部可以随时改，社区帖子和外链改不回来。
    """
    print('\n[L1.29] 对外分发素材数字一致性')
    import re as _re

    ents = load_entities()
    items = ents['entities'] if isinstance(ents, dict) else ents
    total = len(items)
    counts = {}
    for it in items:
        c = it.get('category')
        counts[c] = counts.get(c, 0) + 1

    # 分类中文/英文名 → 真值
    alias = {
        'actuators': ['Actuators'], 'chips': ['Chips'], 'sensors': ['Sensors'],
        'protocols': ['Protocols'], 'robot_ai_models': ['Robot AI Models'],
        'data_acquisition': ['Data Acquisition'], 'llms': ['LLMs'],
        'platforms': ['Platforms'], 'interfaces': ['Interfaces'],
        'flexible_actuators': ['Flexible Actuators'],
    }

    outreach = []
    cdir = os.path.join(ROOT, 'content')
    if os.path.isdir(cdir):
        for fn in os.listdir(cdir):
            if fn.endswith('.md'):
                outreach.append(os.path.join(cdir, fn))
    pdir = os.path.join(ROOT, 'ops', 'promotion')
    if os.path.isdir(pdir):
        for fn in os.listdir(pdir):
            if fn.endswith('.md'):
                outreach.append(os.path.join(pdir, fn))

    check(bool(outreach), 'content/ 或 ops/promotion/ 下存在对外素材')

    # 1) 若稿件声明了实体总数，必须等于真值（含已知过期值 489/512/470）
    bad_total = []
    for p in outreach:
        txt = read_text(p)
        rel = os.path.relpath(p, ROOT).replace('\\', '/')
        for m in _re.finditer(r'\*?\*?(\d{3,4})\+?\*?\*?\s*(?:entities|实体)\b', txt):
            n = int(m.group(1))
            if n != total:
                bad_total.append(f'{rel}:{n}')
    check(not bad_total,
          f'对外素材声明的实体总数均 == 真相源 {total}（不符: {bad_total}）')

    # 2) 若稿件带分类计数表，逐格核对
    bad_cat = []
    for p in outreach:
        txt = read_text(p)
        rel = os.path.relpath(p, ROOT).replace('\\', '/')
        for key, names in alias.items():
            for nm in names:
                m = _re.search(rf'^\|\s*{_re.escape(nm)}\s*\|\s*(\d+)\s*\|',
                               txt, _re.M)
                if m and int(m.group(1)) != counts.get(key, 0):
                    bad_cat.append(f'{rel}:{nm}={m.group(1)}≠{counts.get(key, 0)}')
    check(not bad_cat,
          f'对外素材分类计数表逐格与真值一致（不符: {bad_cat}）')

    # 3) 反向不变式：不得靠删掉数字来"修绿"——旗舰投稿稿件必须仍声明总数
    ros_post = os.path.join(cdir, 'ros-discourse-post.md')
    if os.path.isfile(ros_post):
        t = read_text(ros_post)
        check(_re.search(rf'\b{total}\b\s*(?:entities|实体)', t) is not None,
              f'ROS 投稿稿件仍显式声明实体总数 {total}（防止删数字冒充一致）')


def layer1_30():
    """【L1.30】ros_support 不得由「抽取器种类」推断出来。

    这是同族缺陷（把「不知道」渲染成事实断言）的**根**，比 L1.27/L1.28 更上游。

    L1.27 修了 compat_engine 的布尔三态，L1.28 修了 selection/engine 的四处 truthy。
    但两轮都只修了**消费端**。数据层 `scripts/ingest_oss.mjs` 一直在按抽取器种类
    硬编码 ros_support：

        urdf   (125 条) -> 一律 true    「从 URDF 抓的 => 支持 ROS」
        bom_md ( 63 条) -> 一律 false   「从机械 BOM 抓的 => 不支持 ROS」
        readme (  1 条) -> /ros/i.test(name)  「名字里有 ros => 支持」

    没有一条来自厂商声明。URDF 只能证明**出处**（该关节位点出现在 ROS 模型里），
    证明不了**能力**；bom_md 里的侧板/电池底盖是纯结构件，「支不支持 ROS」
    对它们根本不成立，写 false 是范畴错误；/ros/i 会命中 gy(ros)cope、mic(roS)D。

    两个放大因素：
      1. ros_support 是 /api/oss 的 PREMIUM_FIELDS 之一，即**付费字段**——
         用户花钱买到的是按抽取器种类编出来的值；
      2. 迁移前 OSS 325 条的「未声明」数是 **0**，意味着上两轮辛苦修好的
         unknown 分支在这条数据链上**完全不可达**，是死代码。
         数据层把 unknown 全消灭了，消费端再怎么三态也没用。

    故本闸门锁的是「数据层 + 源码 + 消费端」三处的联合不变式。
    """
    print('\n[L1.30] ros_support 不得由抽取器种类推断（数据层根因）')
    import re as _re

    # ---------- A. 数据层：ros_support 不得与 extractor 共变 ----------
    p = os.path.join(ROOT, 'api', 'oss_components.json')
    doc = json.loads(read_text(p))
    rows = doc['data']

    groups = {}
    for e in rows:
        groups.setdefault(e.get('extractor', '(seed)'), []).append(e)

    # 派生型抽取器（从上游文件 regex 抓出来的）不得携带任何 ros_support 布尔值
    derived_bad = []
    for ext in ('urdf', 'bom_md', 'readme'):
        n = sum(1 for e in groups.get(ext, []) if e.get('ros_support') is not None)
        if n:
            derived_bad.append(f'{ext}={n}条')
    check(not derived_bad,
          f'派生抽取器(urdf/bom_md/readme)不得声明 ros_support（违规: {derived_bad}）')

    # 通用不变式：任一抽取器分组内，ros_support 不得「全组同值且非空」
    covary = []
    for ext, es in groups.items():
        if ext == '(seed)' or len(es) < 5:
            continue
        vals = {e.get('ros_support') for e in es}
        if len(vals) == 1 and vals != {None}:
            covary.append(f'{ext}->{vals.pop()}({len(es)}条)')
    check(not covary,
          f'无抽取器分组的 ros_support 与抽取器种类完全共变（违规: {covary}）')

    # unknown 分支可达性：未声明数必须 > 0，否则消费端三态是死代码
    undeclared = sum(1 for e in rows if e.get('ros_support') is None)
    check(undeclared > 0,
          f'OSS 数据层存在「未声明」项 {undeclared}/{len(rows)}，消费端 unknown 分支可达')

    # 防假绿：不许靠删光整个字段来修绿——种子的真实声明必须还在
    seed_declared = sum(1 for e in groups.get('(seed)', [])
                        if e.get('ros_support') is not None)
    check(seed_declared > 100,
          f'种子数据的真实 ros_support 声明仍保留 {seed_declared} 条（防止删字段冒充合规）')

    # urdf 项须以 ros_ecosystem_origin 如实记录出处（信息不丢，只是不再冒充能力）
    urdf = groups.get('urdf', [])
    if urdf:
        n = sum(1 for e in urdf if e.get('ros_ecosystem_origin') is True)
        check(n == len(urdf),
              f'urdf 项均以 ros_ecosystem_origin 记录出处 {n}/{len(urdf)}（出处≠能力，但出处不该丢）')

    # ---------- B. 源码：三个抽取器内禁止硬编码 ----------
    src = read_text(os.path.join(ROOT, 'scripts', 'ingest_oss.mjs'))
    for fn in ('extractUrdf', 'extractBomMd', 'extractReadme'):
        m = _re.search(rf'function {fn}\s*\([^)]*\)\s*\{{', src)
        if not m:
            check(False, f'{fn} 存在于 ingest_oss.mjs')
            continue
        # 粗取函数体：从函数起点到下一个顶格 function/结尾
        rest = src[m.end():]
        nxt = _re.search(r'\n(?:function |const |\/\/ E\d)', rest)
        body = rest[:nxt.start()] if nxt else rest
        body_nc = _re.sub(r'//[^\n]*', '', body)   # 去注释，避免误伤说明文字
        bad = _re.findall(r'ros_support\s*:\s*(true|false|/ros/i[^,]*|[^,\n]*\.test\([^)]*\))',
                          body_nc)
        check(not bad, f'{fn} 内不得硬编码 ros_support（违规: {bad}）')

    # seed 组装处必须三态透传，不得用 === true 压平
    check("typeof base.ros_support === 'boolean'" in src,
          'makeEntity 对 ros_support 三态透传（不得用 === true 压平未声明）')
    check(_re.search(r'ros_support:\s*base\.ros_support\s*===\s*true', src) is None,
          'makeEntity 已移除 `base.ros_support === true` 压平写法')

    # ---------- C. 消费端：不得把未声明重新折叠回「不支持」 ----------
    # 判定前剥掉整行注释：修复处往往会把「旧写法」原样抄进注释做说明，
    # 若不剥离，闸门会把解释文字误判成缺陷本身（本闸门首次运行即踩到此坑）。
    def _strip_line_comments(t):
        return '\n'.join(ln for ln in t.split('\n') if not ln.lstrip().startswith('//'))

    oss_html = _strip_line_comments(read_text(os.path.join(ROOT, 'oss.html')))
    check(_re.search(r'\$\{\s*e\.ros_support\s*\?', oss_html) is None,
          'oss.html 不再用 truthy 折叠渲染 ROS 列（false 与未声明不得同形）')
    check('rosCell' in oss_html,
          'oss.html 使用 rosCell() 三态渲染')
    for kw in ('未声明',):
        check(kw in oss_html, f'oss.html ROS 列存在「{kw}」独立文案')

    bom_html = _strip_line_comments(read_text(os.path.join(ROOT, 'bom-checker.html')))
    check(_re.search(r'ros_support\s*:\s*!!', bom_html) is None,
          'bom-checker.html 不再用 !! 把「用户没选」压成 false')
    check('ROS2 未知' in bom_html,
          'bom-checker.html 自定义组件提供「ROS2 未知」选项（默认值，使后端三态分支可达）')


def layer1_31():
    """【L1.31】遥测 flush 必须串行化 —— 计数器不得自己丢写。

    实测：对生产 /mcp 连打 2 次 tools/call 后，`mcp:tool:check_compatibility`
    完全没动，而 `mcp:toolsrc:script:check_compatibility` 记到 1。

    根因是 flushMcp 对 KV 做无并发控制的读-改-写：每次 tools/call 连续两次
    recordMcp（tool: 与 toolsrc:），两个 flush 各自 await kv.get 读到同一份旧值，
    后写的 put 覆盖先写的。于是计数**静默低报**。

    这比数字不准更麻烦：MCP 是否存在真实需求是 P0 商业判断，
    而一个会丢写的仪表读出来的值只能算下界，却极易被当成精确值使用——
    与 L1.22 同族（把「测不准」渲染成「测准了」），只是发生在度量层。
    """
    print('\n[L1.31] 遥测 flush 串行化（计数器不得静默丢写）')
    import re as _re

    src = read_text(os.path.join(ROOT, 'functions', 'mcp.js'))
    nc = _re.sub(r'^\s*\*.*$|^\s*//.*$', '', src, flags=_re.M)   # 去注释再判定

    check('_flushChain' in nc and 'function scheduleFlush' in nc,
          '存在 _flushChain + scheduleFlush 串行化机制')
    check(_re.search(r'_flushChain\s*=\s*_flushChain\s*\.then\(', nc) is not None,
          'scheduleFlush 以 promise 链串接（保证下次 get 在上次 put 之后）')
    check(_re.search(r'waitUntil\(\s*flushMcp\(', nc) is None,
          'recordMcp 不得直接 waitUntil(flushMcp())（绕过串行化即恢复竞态）')
    # 注意：不能直接搜 `scheduleFlush(context)` —— 那会匹配到函数**声明**本身，
    # 于是「把调用点删掉、只留一个没人调的 scheduleFlush」也能骗过闸门
    # （反向注入实测确认过这个漏洞）。只认带分号的调用点。
    check(_re.search(r'(?<!function )scheduleFlush\(context\);', nc) is not None,
          'recordMcp 存在 scheduleFlush(context); 调用点（非仅函数声明）')

    # 读侧必须把「下界」这件事讲出来，不能把丢写后的数字当精确值展示
    rm = read_text(os.path.join(ROOT, 'scripts', 'read_metrics.py'))
    check('下界' in rm,
          'read_metrics.py 明示计数为下界（跨 isolate 同分片竞争尚未消除）')

    # ── 功能性验证：静态断言只能证明「写了 promise 链」，证不了「链真的序列化了写」。
    #    本次缺陷恰恰是「看着正常、数字在无声地少」，只有把真实源码放进真实竞态里
    #    跑一遍才作数。verify_flush_race.mjs 从 mcp.js 切真源码 + mock KV(带延迟)，
    #    对「旧版」「修复版」各跑一次，比较落盘计数。
    harness = os.path.join(ROOT, 'scripts', 'verify_flush_race.mjs')
    if not os.path.exists(harness):
        check(False, '存在 scripts/verify_flush_race.mjs 竞态功能性验证')
    else:
        node = _find_node()
        if not node:
            print('  ⏭️  未找到 node，跳过竞态功能性验证（静态断言仍已执行）')
        else:
            try:
                r = subprocess.run([node, harness], cwd=ROOT, capture_output=True,
                                   text=True, encoding='utf-8', errors='replace', timeout=90)
                out = (r.stdout or '') + (r.stderr or '')
                check(r.returncode == 0 and '修复版无丢写' in out,
                      '竞态实跑：修复版落盘计数完整（串行化真的生效，非仅源码形似）')
                # 旧版必须真的丢写，否则这条验证等于没测到东西——
                # 那样「修复版通过」也说明不了问题，必须显式暴露而不是默默算过。
                check('旧版确实丢写' in out,
                      '竞态实跑：旧版复现丢写（证明测试确实压在竞态窗口上）')
            except Exception as e:                                  # noqa: BLE001
                check(False, f'竞态功能性验证执行失败: {e}')


def _find_node():
    """定位 node：环境变量 > PATH > 托管运行时目录。

    刻意不硬编码任何含用户名的绝对路径 —— 本仓库是公开的，
    机器专属路径提交上去既不可移植也等于顺手泄漏本机信息。
    找不到时返回 None，调用侧跳过并明示，绝不当成通过。
    """
    import shutil
    import glob as _glob
    env = os.environ.get('ROBOPARTS_NODE')
    if env and os.path.exists(env):
        return env
    which = shutil.which('node')
    if which:
        return which
    pat = os.path.join(os.path.expanduser('~'), '.workbuddy', 'binaries',
                       'node', 'versions', '*', 'node*')
    for c in sorted(_glob.glob(pat), reverse=True):
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def layer1_32():
    """L1.32 运行留痕机制完整性（20260806-17）

    事故：08-06 15:46 与 16:10 两次运行都完成了实质工作并 commit（OSS ros_support
    去伪造 189 条 / MCP 遥测 flush 竞态修复），却都没写报告、摘要、_LATEST、记忆。
    用户对这两件事完全不知情 —— 而其中一件直接影响 8/7 要读的 MCP 需求判据。

    L1.21 的孤儿检测是**下一轮的事后检测**：工作已经逃逸，且依赖"下一轮恰好跑回归"。
    因此把留痕前移到 deploy.mjs：部署前若本小时无报告，先落 AUTO-STUB 占位。

    但占位会产生一个新风险：**占位本身能让 L1.21 的孤儿检测永远变绿**
    （文件存在了，孤儿就没了），等于用自动化把自己的监控糊住 —— 这正是本仓
    反复栽过的"假绿"同型。所以必须成对存在：

      1. 早于当前小时的报告不得仍是占位（= 部署了却始终没人来填写）；
      2. deploy.mjs 必须真的在部署命令**之前**调用 ensureRunTrace（防被摘掉）；
      3. 占位写入必须维持 _SUMMARY 换行不变式（否则触发 L1.21 的粘连根因）。

    ⚠️ 20260806-18 修正（本闸门自身的缺陷）：首版判据是裸子串 `'AUTO-STUB' in 文本`，
    于是 17:00 那份**如实描述本机制**的正常报告，仅因正文写了这个词就被判成占位，
    闸门当场恒红。这不是普通误报 —— 本闸门存在的唯一理由是防止"用自动化糊住自己的监控"，
    而一个恒红的误报，会把下一轮逼向"放宽 L1.32"，亲手造出它要防的那种假绿；
    且它**自我触发**：以后每份诚实记录该机制的报告都会再次踩中，故障永不收敛。

    根因是判据混淆了两件事：文件**是**占位 ≠ 文件**提到**占位。
    改为独占一行的 sentinel + 行锚定正则，并补一对**功能性**阴阳断言（见下），
    确保"散文提及不触发、真占位必触发"这条性质本身被测到，而不是靠人记得别踩。
    """
    print('\n[L1.32] 运行留痕机制完整性（占位不得糊住孤儿检测）')
    import datetime as _dt

    res_dir = os.path.join(ROOT, 'ops', 'results')
    now = _dt.datetime.now()
    cur = (now.strftime('%Y%m%d'), now.strftime('%H'))

    # 行锚定 sentinel：整行只能是这条标记（容许前后空白）。散文里的行内提及不匹配。
    SENTINEL_RE = re.compile(r'^[ \t]*<!--[ \t]*ROBOPARTS-RUN-TRACE:AUTO-STUB[ \t]*-->[ \t]*$', re.M)

    def _is_stub(text):
        return SENTINEL_RE.search(text) is not None

    stale = []
    for p in glob.glob(os.path.join(res_dir, 'roboparts-*.md')):
        m = re.match(r'roboparts-(\d{8})-(\d{2})\.md$', os.path.basename(p))
        if not m:
            continue
        slot = (m.group(1), m.group(2))
        if slot >= cur:
            continue                       # 本小时在途，允许占位
        if _is_stub(read_text(p)):
            stale.append('%s-%s' % slot)
    check(not stale,
          '无过期占位报告（部署后始终没人填写的时段: %s）' % (stale[:4] or '无'))

    # ── 判据本身的功能性双向验证（首版恒红就栽在这里，故把性质固化成断言）──
    # 阴性：一份**描述该机制**的正常报告，不得被判成占位。
    _prose = ('# 报告\n\n本轮把留痕前移：部署前无报告则落带 `AUTO-STUB` 标记的占位，\n'
              '并由 L1.32 盯住「早于当前小时的报告仍带 AUTO-STUB」。\n')
    check(not _is_stub(_prose),
          '阴性：正文提及 AUTO-STUB 的正常报告不被误判为占位（首版恒红根因）')
    # 阳性：deploy.mjs 真正写出的占位，必须被判中 —— 否则闸门等于不存在。
    check(_is_stub('# RoboParts 飞轮 · x\n\n<!-- ROBOPARTS-RUN-TRACE:AUTO-STUB -->\n\n## 修复\n'),
          '阳性：真占位（独占一行的 sentinel）必被判中')
    # 防"改宽松以求变绿"：判据不得退回裸子串匹配。
    # 注意：needle 必须拼出来，不能写成字面量 —— 否则本断言会扫到**自己这行**而恒红
    # （首版就这么栽了一次：自指扫描，守卫把自己判违规）。
    _src = read_text(os.path.join(ROOT, 'scripts', 'regression.py'))
    _mark = 'AUTO' + '-STUB'
    _bad_forms = ["'%s' in read_text(" % _mark, '"%s" in read_text(' % _mark,
                  "'%s' in text" % _mark]
    check(not any(b in _src for b in _bad_forms),
          '判据未退回裸子串匹配（退回即恢复恒红误报→逼人放宽闸门）')

    dep = read_text(os.path.join(ROOT, 'scripts', 'deploy.mjs'))
    check('function ensureRunTrace' in dep,
          'deploy.mjs 定义 ensureRunTrace（部署前留痕）')
    call_at = dep.find('\nensureRunTrace();')
    deploy_at = dep.find("'pages', 'deploy'")
    check(call_at != -1 and deploy_at != -1 and call_at < deploy_at,
          'ensureRunTrace() 在 wrangler pages deploy 之前被真实调用（非仅定义）')
    # 占位标记必须是「独占一行的 sentinel」常量，且真的被写进占位正文。
    # 只断言 "含 AUTO-STUB 三个字" 是不够的 —— 那正是首版判据，注释里提一嘴就能骗过。
    check(re.search(r"STUB_SENTINEL\s*=\s*'<!-- ROBOPARTS-RUN-TRACE:AUTO-STUB -->'", dep) is not None,
          'deploy.mjs 定义 STUB_SENTINEL 常量（逐字与 L1.32 行锚定正则对齐）')
    _body = dep[dep.find('const body = ['):dep.find("].join('\\n')")] if 'const body = [' in dep else ''
    check(re.search(r'^\s*STUB_SENTINEL,\s*$', _body, re.M) is not None,
          '占位正文把 STUB_SENTINEL 作为独立一行写入（拼进别行则 sentinel 失效）')
    # 端到端：deploy.mjs 实际写出的 sentinel 行，必须能被本闸门的正则判中。
    _m = re.search(r"STUB_SENTINEL\s*=\s*'([^']+)'", dep)
    check(bool(_m) and _is_stub(_m.group(1)),
          '端到端：deploy.mjs 的 sentinel 字面量能被 L1.32 正则匹配（两处定义不得漂移）')
    check(re.search(r"endsWith\('\\n'\)", dep) is not None,
          '占位写 _SUMMARY 前保证以换行结尾（L1.21 粘连根因不得复发）')

    # 实跑才暴露的缺陷（首版就栽了）：Windows + shell:true 下含空格的单个参数
    # 会被拆成两个，`--pretty=format:%h %s` 使 git 输出为空 —— 占位里最关键的
    # git 痕迹直接丢失，而源码级断言全绿。故静态锁死"git 参数不得含空格"。
    bad = re.findall(r"'(--pretty=[^']*\s[^']*)'", dep)
    check(not bad,
          'deploy.mjs 的 git 参数不含空格（Windows shell:true 会拆参致输出为空；违规: %s）' % (bad[:2] or '无'))

    # 占位必须真的能拿到 HEAD —— 直接实跑取一次，空值即判红（功能性验证，非源码形似）
    _r = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT,
                        capture_output=True, encoding='utf-8', errors='replace', shell=True)
    check(bool((_r.stdout or '').strip()),
          '占位所依赖的 git rev-parse 实跑可取到 HEAD（取不到则痕迹形同虚设）')


def layer1_33():
    """L1.33 MCP key_specs 诚实性与品类覆盖（20260806-20）

    同族缺陷第三处。前两处是 20260806-08（protocol/mechanical）与 20260806-12
    （compat_engine 的 ros_support），根因同一个：**布尔字段没有「空串 = 未声明」
    的天然保护**，一旦用 truthy 折叠，「厂商没说」就被渲染成「厂商说不支持」。

    本处发生在 mcp-server/index.js 的 getKeySpecs：同一个函数里所有字符串字段
    都老老实实走 `|| 'N/A'`，唯独 `embodied_ai: item.embodied_ai || false`
    把未声明压成 false —— llms 品类 42 条里有 20 条从未声明，全被 MCP 向调用方
    的 AI Agent 断言成「不支持具身智能」。

    还牵出第二个洞：switch 只覆盖 7 个品类，而数据集有 10 个，
    robot_ai_models / data_acquisition / flexible_actuators 共 108 条（15.7%）
    落到 default 返回 {}。讽刺的是全库仅有的 7 条 embodied_ai=true 全在
    robot_ai_models —— **有信号的品类不给，给的品类没信号**。

    断言以功能性为主（真的跑一遍 688 条），而非"源码长得像"。
    """
    print('\n[L1.33] MCP key_specs 诚实性与品类覆盖')
    idx = os.path.join(ROOT, 'mcp-server', 'index.js')
    src = read_text(idx)

    # —— 防退化（源码级）：布尔能力字段不得再退回 truthy 折叠 ——
    # needle 拼接构造，避免本断言扫到自己（L1.32 首版栽过的自指坑）。
    _or = '|' + '| false'
    bad_fold = re.findall(r'(\w+)\s*:\s*item\.\w+\s*' + re.escape(_or), src)
    check(not bad_fold,
          '布尔能力字段未退回 truthy 折叠（未声明≠false；违规: %s）' % (bad_fold[:3] or '无'))
    # 用 \b + 形参括号锁死：裸子串 'function triSpec' 会被 triSpecXX 之类改名蒙混过关
    check(re.search(r'function\s+triSpec\s*\(', src) is not None,
          '存在 triSpec 三态辅助函数（已声明才回布尔，未声明回 N/A）')

    node = _find_node()
    if not node:
        check(False, '未找到 node，无法功能性验证 getKeySpecs（不当作通过）')
        return

    # —— 功能性验证：抽出函数真的跑一遍全库 ——
    harness = r'''
const fs=require('fs');
const src=fs.readFileSync(process.argv[2],'utf8');
const pick=(n)=>{const i=src.indexOf('function '+n);if(i<0)return null;let d=0;
  for(let j=i;j<src.length;j++){if(src[j]==='{')d++;else if(src[j]==='}'){d--;if(d===0)return src.slice(i,j+1);}}return null;};
for(const fn of ['fmtSpec','triSpec','getKeySpecs']){const s=pick(fn);if(!s){console.log(JSON.stringify({err:'missing:'+fn}));process.exit(0);}eval(s);}
const e=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const ents=e.entities||e;
const cats=new Set(ents.map(x=>x.category));
let empty=0,lied=0,objleak=0,posT=0,posF=0,neg=0;
const emptyCats=new Set();
for(const it of ents){
  const ks=getKeySpecs(it,it.category);
  if(!Object.keys(ks).length){empty++;emptyCats.add(it.category);}
  for(const v of Object.values(ks)) if(v&&typeof v==='object') objleak++;
  if('embodied_ai' in ks){
    const d=typeof it.embodied_ai==='boolean';
    if(!d&&ks.embodied_ai===false)lied++;
    if(!d&&ks.embodied_ai==='N/A')neg++;
    if(d&&it.embodied_ai===true&&ks.embodied_ai===true)posT++;
    if(d&&it.embodied_ai===false&&ks.embodied_ai===false)posF++;
  }
}
console.log(JSON.stringify({empty,emptyCats:[...emptyCats],lied,objleak,posT,posF,neg,nCats:cats.size}));
'''
    import tempfile
    th = tempfile.NamedTemporaryFile('w', suffix='.cjs', delete=False, encoding='utf-8')
    th.write(harness)
    th.close()
    try:
        r = subprocess.run([node, th.name, idx, os.path.join(ROOT, 'api', 'entities.json')],
                           capture_output=True, encoding='utf-8', errors='replace')
        out = (r.stdout or '').strip().splitlines()
        data = json.loads(out[-1]) if out else {'err': 'no output: ' + (r.stderr or '')[:120]}
    finally:
        os.unlink(th.name)

    if data.get('err'):
        check(False, 'getKeySpecs 功能性验证无法执行（%s）' % data['err'])
        return

    # 覆盖完整性：新增品类若没补 case，这里立刻红 —— 防的是"数据加了品类没人管"
    check(data['empty'] == 0,
          '每个品类都有 key_specs（空对象=对调用方等同「无任何规格」；空品类: %s）'
          % (data['emptyCats'] or '无'))
    # 阴性：未声明不得被断言为 false（本次根因）
    check(data['lied'] == 0,
          '阴性：未声明 embodied_ai 不得输出 false（无据断言数: %d）' % data['lied'])
    check(data['neg'] > 0,
          '阴性：未声明确实输出 N/A 表未知（覆盖 %d 条）' % data['neg'])
    # 阳性：已声明必须如实透传，防"一律 N/A"式的假修复
    check(data['posT'] > 0 and data['posF'] > 0,
          '阳性：已声明 true/false 均如实输出（true %d 条 / false %d 条）'
          % (data['posT'], data['posF']))
    check(data['objleak'] == 0,
          'key_specs 不含裸对象（整块 mechanical_interface 倒出是噪声非规格）')


# ---------- L1.34 站内导航可达性 ----------

def _collect_page_ids():
    """{相对路径: set(该页所有 id)}，覆盖根目录与 articles/ 下的 HTML。"""
    ids = {}
    for pat in ('*.html', os.path.join('articles', '*.html')):
        for p in glob.glob(os.path.join(ROOT, pat)):
            rel = os.path.relpath(p, ROOT).replace('\\', '/')
            ids[rel] = set(re.findall(r'id="([^"]+)"', read_text(p)))
    return ids


def _resolve_anchor(page, href):
    """把一条锚点 href 解析成 (目标页相对路径, 锚点名)；无法解析回 (None, None)。"""
    if href.startswith('/#'):
        return 'index.html', href[2:]
    if href.startswith('#'):
        return page, href[1:]
    m = re.match(r'^/([a-z0-9\-/]+)#(.+)$', href)
    if m:
        target, anchor = m.group(1), m.group(2)
        cand = target if target.endswith('.html') else target + '.html'
        if cand == 'articles.html':
            cand = 'articles/index.html'
        return cand, anchor
    return None, None


def layer1_34():
    """L1.34 站内导航可达性：死锚点 + 串站跳转（20260806-21）

    本轮抓到两类**永远不会 404、因此任何状态码巡检都测不出来**的断路：

    1) 死锚点：index.html 的真实锚点是 `api-access`，而全站 13 处
       「免费注册领 100 积分」写的是 `/#api`。点下去只是停在首页顶部 ——
       用户看不到任何注册入口。位置全在关键路径上：/credits 充值页、
       /pricing 主力收钱页，**连 credits-history 的「请输入有效 API Key」
       报错兜底文案里的救命链接也是死的**。拿不到 key = 后面所有付费动作为零。

    2) 串站跳转：api-pricing.html（已被 sitemap 收录）是从兄弟站 GeneTech
       套壳来的，页脚品牌、导航「Main Site」、以及 signUpFree / buyDataPack /
       buyFullBundle 三个按钮全部 window.location 到 genetech.tools —— 实测
       **403**。即标价最高的 $29 / $299 两档和新用户免费入口，点击即出站再撞墙。

    两者根因相同：**闸门只校验「文件在不在、状态码对不对」，从不校验
    「点下去到底能不能到」**。上一轮修 agent-discovery.json 的 pages.dev 残留时，
    断言只绑死那一个文件名，同族的 llms.txt / api-pricing.html 全部漏网。

    阳性断言在此尤其关键：锚点扫描一旦正则写错扫到空集，"0 个死锚点"会天然为真，
    是最舒服的假绿。故强制要求扫到的锚点引用数达到下界。
    """
    print('\n[L1.34] 站内导航可达性（死锚点 / 串站跳转）')
    ids = _collect_page_ids()
    check('index.html' in ids, 'index.html 可读（锚点校验的基准页）')

    dead, total_refs = [], 0
    for page in sorted(ids):
        src = read_text(os.path.join(ROOT, page))
        for href in re.findall(r'href="(#[^"]+|/#[^"]+|/[a-z0-9\-/]+#[^"]+)"', src):
            tf, anchor = _resolve_anchor(page, href)
            if not tf or not anchor:
                continue
            total_refs += 1
            if tf not in ids or anchor not in ids[tf]:
                dead.append('%s -> %s' % (page, href))

    # 阳性：必须真的扫到锚点，否则空集会把"0 死锚点"伪装成通过
    check(total_refs >= 10,
          '阳性：锚点扫描确实生效（共解析 %d 条站内锚点引用，下界 10）' % total_refs)
    check(not dead,
          '无死锚点（点击可达；违规 %d 处: %s）' % (len(dead), dead[:4] or '无'))

    # 同族补位（20260806-22）：上面只管「带 # 的链接」，而**不带锚点的普通站内链接
    # 一样会断**，且断了是真 404。本闸门若只钉死锚点，等于把同一个「点下去到不了」
    # 的问题修了一半 —— 这正是本项目反复出现的「修一处、同族漏网」。
    # 当前实测 0 处，加断言是趁干净锁死，防止新页改名/删页时悄悄留下 404 入口。
    plain, plain_refs = [], 0
    for page in sorted(ids):
        src = read_text(os.path.join(ROOT, page))
        for href in re.findall(r'href="(/[^"#?]*)"', src):
            if href == '/' or href.startswith('/api/'):
                continue
            plain_refs += 1
            t = href.lstrip('/')
            cands = (t, t + '.html', t.rstrip('/') + '/index.html')
            if not any(os.path.exists(os.path.join(ROOT, c)) for c in cands):
                plain.append('%s -> %s' % (page, href))
    check(plain_refs >= 20,
          '阳性：普通站内链接扫描确实生效（共 %d 条，下界 20）' % plain_refs)
    check(not plain,
          '无指向不存在页面的站内链接（真 404 入口；违规 %d 处: %s）'
          % (len(plain), plain[:4] or '无'))

    # 关键入口：13 处修复全部指向它，改名即再次全线断路，必须钉死
    check('api-access' in ids.get('index.html', set()),
          'index.html 保留 #api-access 锚点（全站「免费领 API Key」的唯一落点）')
    api_refs = sum(read_text(os.path.join(ROOT, p)).count('"/#api-access"') for p in ids)
    check(api_refs >= 10,
          '阳性：站内仍有 %d 处指向 #api-access（防被批量改回死锚点）' % api_refs)

    # 串站跳转：兄弟站域名不得出现在本站页面（已实测 genetech.tools/api-key = 403）
    SIBLING = ('genetech.tools', 'quantum-computing.tools', 'brain-science.tools')
    cross = []
    for page in sorted(ids):
        src = read_text(os.path.join(ROOT, page))
        for dom in SIBLING:
            if dom in src:
                cross.append('%s -> %s' % (page, dom))
    check(not cross,
          '站内页面无兄弟站跳转（收钱页曾整页套壳外站；违规: %s）' % (cross[:4] or '无'))

    # 用户复制粘贴的示例代码不得留废弃预览域（openapi 的 Staging 声明属合法，不在此列）
    pricing_src = read_text(os.path.join(ROOT, 'api-pricing.html'))
    check('pages.dev' not in pricing_src,
          'api-pricing.html 示例代码无 pages.dev 预览域（用户会照抄）')
    llms = read_text(os.path.join(ROOT, 'llms.txt'))
    m = re.search(r'^-\s*线上[^\n]*$', llms, re.M)
    check(m is not None and 'pages.dev' not in m.group(0),
          'llms.txt「线上」条目指向正式域名而非预览域（Agent 会照此引用）')


# ---------- L1.35 正式域权威性 ----------

OFFICIAL = 'https://roboparts.cc'
PREVIEW = 'robotparts-924.pages.dev'
# 允许出现预览域的语境：必须在同一行显式标注它不是正式入口
PREVIEW_LABELS = ('预览', 'Staging', 'staging', '非正式', '勿对外引用', '默认域')


def layer1_35():
    """L1.35 正式域权威性：canonical 覆盖 + 预览域引用纪律（20260806-22）

    起因是 L1.34 的反向注入验证：往 llms.txt 里种一个预览域 URL，闸门**没拦住**。
    查下去发现 L1.34 那条断言只校验 `- 线上` 那一行，而 llms.txt 里有 23 处域名引用 ——
    **被守住的是"声明句"，没守住的是 Agent 真正会去调的端点行**。
    这正是本项目反复出现的「断言绑死一行/一个文件名，同族全漏」。

    顺此排查牵出两件线上实况：

    1) **README 自相矛盾**：第 6 行写 `域名: roboparts.cc`，第 7 行紧接着写
       `线上地址: https://robotparts-924.pages.dev`。README 是 GitHub 门面，
       而外链建设正是当前 P0 —— 照 README 引用的人会把链接指向预览域，
       把本就稀缺的域名权重分流到一个不打算运营的域上。

    2) **预览域是可索引的完整副本**：`robotparts-924.pages.dev` 返回 200，
       且它复用同一份 robots.txt（内容写着 "robots.txt for roboparts.cc"，不含
       针对预览域的 Disallow）。同时**全站 canonical 只覆盖了 19 个文章/GEO 页，
       16 个产品页一个都没有**，缺口恰好是首页、/pricing、/data-hub 这些主力页。
       即：最该被认领的页面，恰恰没有任何信号告诉搜索引擎谁是正主。

    故本闸门做两件事：把 canonical 覆盖钉死在 sitemap 收录范围上；
    把"预览域可以出现，但必须当场声明它不是正式入口"变成可执行判据。
    """
    print('\n[L1.35] 正式域权威性（canonical 覆盖 / 预览域引用纪律）')

    sm = read_text(os.path.join(ROOT, 'sitemap.xml'))
    routes = re.findall(r'<loc>https://roboparts\.cc/([a-z0-9\-]*)</loc>', sm)
    # 只管根级 HTML 页面（/api/*.json 等数据端点不在此列）
    pages = [r for r in routes
             if os.path.exists(os.path.join(ROOT, (r or 'index') + '.html'))]
    check(len(pages) >= 15,
          '阳性：sitemap 解析确实生效（解析出 %d 个根级页面，下界 15）' % len(pages))

    missing, wrong = [], []
    for r in pages:
        f = (r or 'index') + '.html'
        src = read_text(os.path.join(ROOT, f))
        m = re.search(r'<link rel="canonical" href="([^"]+)"', src)
        if not m:
            missing.append(f)
            continue
        want = OFFICIAL + '/' + r if r else OFFICIAL + '/'
        if m.group(1).rstrip('/') != want.rstrip('/'):
            wrong.append('%s: %s ≠ %s' % (f, m.group(1), want))
    check(not missing,
          'sitemap 收录页均有 canonical（缺 %d 个: %s）'
          % (len(missing), missing[:5] or '无'))
    check(not wrong,
          'canonical 均指向正式域且路由自洽（错 %d 个: %s）'
          % (len(wrong), wrong[:3] or '无'))

    # canonical 绝不能指向预览域 —— 那等于主动把权重让出去
    bad_canon = []
    for pat in ('*.html', os.path.join('articles', '*.html')):
        for p in glob.glob(os.path.join(ROOT, pat)):
            for u in re.findall(r'<link rel="canonical" href="([^"]+)"', read_text(p)):
                if PREVIEW in u:
                    bad_canon.append(os.path.basename(p))
    check(not bad_canon,
          '无 canonical 指向预览域（违规: %s）' % (bad_canon[:4] or '无'))

    # 对外产物里的预览域：可以出现，但必须同行标注"这不是正式入口"
    ARTIFACTS = ('README.md', 'llms.txt', 'agent-discovery.json', 'server.json')
    naked, seen = [], 0
    for rel in ARTIFACTS:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        for i, line in enumerate(read_text(p).splitlines(), 1):
            if PREVIEW not in line:
                continue
            seen += 1
            if not any(lab in line for lab in PREVIEW_LABELS):
                naked.append('%s:%d' % (rel, i))
    check(seen >= 1,
          '阳性：预览域扫描确实生效（对外产物中共 %d 处引用，下界 1）' % seen)
    check(not naked,
          '对外产物中预览域均已标注为非正式入口（裸引用 %d 处: %s）'
          % (len(naked), naked[:4] or '无'))

    # README 的「线上地址」是外部读者的第一落点，必须是正式域
    rd = read_text(os.path.join(ROOT, 'README.md'))
    live = re.findall(r'^-\s*\*\*线上地址[^*]*\*\*\s*[:：]\s*(\S+)', rd, re.M)
    check(len(live) >= 1, '阳性：README 能解析到「线上地址」条目（%d 处）' % len(live))
    check(all(v.startswith(OFFICIAL) for v in live),
          'README「线上地址」均为正式域（实际: %s）' % (live or '无'))


# ---------- L1.36 对外接入文档的可执行性 ----------
def layer1_36():
    """L1.36 对外接入路径必须真的能走通（20260807-01）

    起因：遥测显示 /mcp 被访问 781 次、UA:tool 873 次（目录站在持续收录），
    但真实业务调用只有 20 次、可归因仅 2 次。查下去发现**所有对外文档给的
    接入方式没有一条能开箱走通**：
      · mcp-server/README.md 教 `npx roboparts-mcp-server` —— 该包 npm 实测 404，从未发布；
      · mcp-guide.html 三份配置全写 `node /path/to/roboparts/mcp-server/index.js`，
        却通篇没有一句 `git clone`（实测 clone 出现 0 次）—— 等于给了一个
        用户根本拿不到的文件路径；
      · 而**唯一真能零门槛用起来的远程直连**（https://roboparts.cc/mcp，
        实测无需 API Key 即可 tools/call 成功）在两份文档里都只字未提。
    server.json 里 remotes 声明是对的，所以**机器（目录站）能发现，人照着文档却接不进来**。

    这条闸门锁的不是"文档写没写"，而是"文档写的那条路是否真的存在"。
    与 L1.21 第 6 条（报告声称的哈希必须真实存在）是同一族：**对外承诺必须可兑现**。
    """
    print('\n[L1.36] 对外接入路径可执行性（文档承诺 vs 真实可用）')

    REMOTE = 'https://roboparts.cc/mcp'
    docs = {
        'mcp-guide.html': os.path.join(ROOT, 'mcp-guide.html'),
        'mcp-server/README.md': os.path.join(ROOT, 'mcp-server', 'README.md'),
    }

    # 已知未发布/不可用的包名。发布成功后必须从这里移除，否则闸门会一直挡着
    # —— 这是刻意的：让"包发出去了"和"文档敢再教用户装"这两件事强绑定。
    UNPUBLISHED = []  # roboparts-mcp-server@1.0.2 已于 2026-08-12 发布至 npm，守卫解除
    # 判定为"警示语"而非"可执行指令"的标记
    WARN_MARK = ('不可用', '尚未发布', '404', '请勿', '⚠')

    present = 0
    offenders = []
    for rel, p in docs.items():
        if not os.path.isfile(p):
            offenders.append('%s:缺失' % rel)
            continue
        present += 1
        txt = read_text(p)

        # (1) 远程直连必须被文档提及 —— 唯一零安装可用路径
        if REMOTE not in txt:
            offenders.append('%s:未提供远程直连 %s' % (rel, REMOTE))

        # (2) 未发布的包名不得作为可执行指令出现（警示行豁免）
        for ln_no, line in enumerate(txt.splitlines(), 1):
            for pkg in UNPUBLISHED:
                if pkg in line and not any(w in line for w in WARN_MARK):
                    # 纯叙述性提及（如包名标题行）不含 npx/npm/args 才放行
                    if re.search(r'npx|npm\s+i|"args"|\'args\'', line):
                        offenders.append('%s:%d 教用户安装未发布包 %s'
                                         % (rel, ln_no, pkg))

        # (3) 给了本地路径占位，就必须同时告诉用户怎么拿到这个文件
        if '/path/to/roboparts' in txt and 'git clone' not in txt:
            offenders.append('%s:出现本地路径占位却无 git clone 获取指引' % rel)

    check(present == len(docs),
          '阳性：对外接入文档均存在（%d/%d —— 为 0 说明扫描目标写错，闸门空转）'
          % (present, len(docs)))
    check(not offenders,
          '对外接入文档给的路径均可走通（问题项 %d: %s）'
          % (len(offenders), offenders[:4] or '无'))

    # 功能性阴断言：把"教用户装未发布包"喂进判据，必须能识别出来。
    # 不测文件、只测判据本身，避免文档一改断言就失效。
    _bad = '      "args": ["-y", "roboparts-mcp-server"]'
    _hit = ('roboparts-mcp-server' in _bad
            and not any(w in _bad for w in WARN_MARK)
            and bool(re.search(r'npx|npm\s+i|"args"|\'args\'', _bad)))
    check(_hit, '功能性·阴：可执行配置里的未发布包名能被识别为违规')

    # 功能性阳断言：警示语里出现同一包名**不得**误报，否则下一轮会被逼着
    # 删掉警示语——那等于为了闸门变绿而把真话抹掉（L1.32 恒红逼出假绿的教训）。
    _warn = '> ⚠️ **`npx roboparts-mcp-server` 目前不可用**：该包尚未发布到 npm'
    _fp = ('roboparts-mcp-server' in _warn
           and not any(w in _warn for w in WARN_MARK))
    check(not _fp, '功能性·阳：警示语中提及未发布包名不算违规（防误报逼删真话）')


# ---------- L1.37 公开端点不得发布未经审核的记录 ----------
def layer1_37():
    """L1.37 「审核」必须是发布的前置条件，而不是装饰（20260807-03）

    起因：`GET /api/suppliers/list` 无鉴权、CORS `*`，而过滤口径写的是
    `review_status !== 'rejected'` —— 即**待审核(pending)也照样公开**。
    配合 `POST /api/suppliers/register` 无鉴权 / 无限流 / 无验证码、落库即 pending，
    构成一条完整链路：**任何人一个匿名 POST 就能把任意公司注入 RoboParts 公开
    供应商目录**。本轮已实测复现（匿名注册的条目数秒内出现在公开列表中，
    探针记录随后已从 KV 清除）。

    危害不在于"有人能写"，而在于**这份目录正被 GPTBot / Meta-ExternalAgent /
    Googlebot 抓取**：未经审核的自助提交会被吸收进 AI 对「RoboParts 供应商网络」
    的回答里。污染当时已实际存在——公开目录中挂着测试数据 "Test Company"（0 产品）。
    approve.js 明明有管理员闸门，却因为发布不以审核为前提而**保护不到读路径**。

    与 L1.21 第 6 条（报告声称的哈希须真存在）、L1.36（文档给的接入路径须真能走通）
    同族：**对外呈现的东西必须名副其实**。这一条锁的是"标着已收录的供应商，
    是否真的过了审"。
    """
    print('\n[L1.37] 公开端点不得发布未审核记录（审核须为发布前置条件）')

    src_path = os.path.join(ROOT, 'functions', 'api', 'suppliers', 'list.js')
    check(os.path.isfile(src_path),
          '阳性：供应商公开列表源文件存在（不存在说明扫描目标写错，闸门空转）')
    src = read_text(src_path) if os.path.isfile(src_path) else ''

    # 判据一：必须是 approved 白名单口径，且不得残留 !== 'rejected' 黑名单口径。
    # 用正则而非裸子串：裸子串 `review_status === 'approved'` 会被
    # `review_status === 'approved_pending'` 之类蒙混（第 46/48 条教训的复用）。
    allow_re = re.compile(r"review_status\s*===\s*(['\"])approved\1")
    deny_re = re.compile(r"review_status\s*!==\s*(['\"])rejected\1")

    def strip_comments(js):
        """只对**代码**判定口径。首版直接扫全文，结果把本次修复自己写的
        「原口径为 !== 'rejected'」那段说明判成了违规——闸门等于在逼我
        删掉解释为什么要修的那段真话（L1.32 恒红逼出假绿的同一陷阱）。
        故先剥注释再判：注释里怎么引用旧口径都不算数，代码里出现一次就红。"""
        js = re.sub(r'/\*.*?\*/', '', js, flags=re.S)
        return '\n'.join(re.sub(r'//.*$', '', ln) for ln in js.splitlines())

    code = strip_comments(src)
    check(bool(allow_re.search(code)),
          "公开列表按 approved 白名单过滤（未见 review_status === 'approved'）")
    check(not deny_re.search(code),
          "公开列表未残留 !== 'rejected' 黑名单口径（该口径会放行 pending）")

    # 判据二：联系方式不得出现在公开投影里（注册表单收了邮箱/电话，
    # 一旦顺手 spread 整条记录就会连人带号一起泄露）。
    proj = src[src.find('publicSuppliers'):] if 'publicSuppliers' in src else ''
    leaked = [f for f in ('contact_email', 'contact_phone', 'contact_name')
              if re.search(r'^\s*%s\s*:' % f, proj, re.M)]
    check(not leaked, '公开投影未泄露联系方式（泄露字段: %s）' % (leaked or '无'))

    # 功能性·阴：把旧的黑名单口径喂进判据，必须判为违规。
    # 只测判据、不测文件，避免文件一改断言就失效。
    _old = "if (supplier.review_status !== 'rejected') { allSuppliers.push(supplier); }"
    check(bool(deny_re.search(_old)) and not allow_re.search(_old),
          '功能性·阴：旧的「pending 也公开」口径能被识别为违规')

    # 功能性·阳：注释里为解释历史而引用旧口径，不得误报成违规。
    # 否则下一轮会被逼着删掉这段说明——又是"为了闸门变绿抹掉真话"。
    _cmt = ("// 原口径为 `review_status !== 'rejected'`，即待审核也公开\n"
            "if (supplier.review_status === 'approved') { allSuppliers.push(supplier); }")
    _cmt_code = strip_comments(_cmt)
    check(not deny_re.search(_cmt_code) and bool(allow_re.search(_cmt_code)),
          '功能性·阳：注释中引用旧口径不算违规（防误报逼删说明）')


# ---------- L1.38 部署前必须先给未入库内容留快照 ----------
def layer1_38():
    """L1.38 上线的东西必须在 git 对象库里留有一份（20260807-05）

    起因：08-06 21:43、08-07 00:00、08-07 03:38 连续三轮完成实质工作并**部署上线**
    却都没 commit，其中 03:38 上线的是一处安全修复（供应商公开目录放行未审核记录）。
    仓库停在旧提交，线上领先仓库 —— 那份代码当时只存在于工作区一个副本里。

    已有的 L1.21/L1.32 留痕机制能**发现**这件事，deploy.mjs 的 AUTO-STUB 能记下
    "哪些文件没提交"，但两者留的都是**描述**，不是**内容**：
    一次 `git checkout .` 或换台机器，线上跑的那份代码就再也拼不回来。
    连续三轮踩同一个坑，说明靠"下一轮记得 commit"这种纪律性约束不成立，
    必须让它**结构上不可能丢**。

    故 deploy.mjs 在部署前调用 snapshotWorkingTree()，把工作区完整快照写成
    非分支 ref（refs/roboparts/deployed/*）。本闸门锁的是这条线不被悄悄拆掉。

    **顺序是这条闸门的要害**：快照必须发生在 wrangler 部署**之前**。
    放到部署之后看着也能跑、断言也能绿，但只要部署失败或进程中断在中间，
    保护就正好在最需要它的那一刻缺席 —— 那才是它本该覆盖的场景。
    """
    print('\n[L1.38] 部署前未入库内容必须留快照（线上领先仓库时不致灭失）')

    lib_rel = os.path.join('scripts', 'lib', 'deploy_snapshot.mjs')
    lib_path = os.path.join(ROOT, lib_rel)
    dep_path = os.path.join(ROOT, 'scripts', 'deploy.mjs')
    ver_path = os.path.join(ROOT, 'scripts', 'verify_deploy_snapshot.mjs')

    check(os.path.isfile(lib_path),
          '阳性：快照模块存在（%s —— 不存在说明扫描目标写错，闸门空转）' % lib_rel)
    check(os.path.isfile(ver_path),
          '快照的功能性验证脚本存在（scripts/verify_deploy_snapshot.mjs）')

    lib = read_text(lib_path) if os.path.isfile(lib_path) else ''
    dep = read_text(dep_path) if os.path.isfile(dep_path) else ''

    check('export function snapshotWorkingTree' in lib,
          '快照模块导出 snapshotWorkingTree（供 deploy 与 verify 共用同一份实现）')
    # 独立成模块的意义就在于 verify 测的是**真实现**而非副本。
    # 若哪天有人把逻辑复制回 deploy.mjs 内联，verify 就会变成测一个没人用的孤儿模块。
    check("from './lib/deploy_snapshot.mjs'" in dep,
          'deploy.mjs 引用共享快照模块（而非内联副本，否则 verify 测的是孤儿代码）')

    # ⚠️ 下面两条必须**剥掉注释再判**。首版用裸子串扫全文，被反向注入⑤当场戳穿：
    # 本模块的文档注释里就写着"用临时 GIT_INDEX_FILE"，于是把**代码里**的
    # GIT_INDEX_FILE 改坏之后，闸门靠注释中那句话照样全绿 ——
    # 断言实际在检查"有没有人提过这个词"，而非"代码有没有在用它"。
    # 第 46/48 条教训（裸子串可被蒙混）在本闸门上的又一次复发。
    lib_code = strip_js_comments(lib)
    # 临时索引是"零副作用"的全部依据：少了它会直接改调用者的暂存区
    check(bool(re.search(r'GIT_INDEX_FILE\s*:', lib_code)),
          '快照在**代码中**使用临时索引 GIT_INDEX_FILE（不污染调用者暂存区）')
    # read-tree 播种是「已追踪但被 ignore 的文件」（mcp-server/*）不丢的唯一保障
    check(bool(re.search(r"\[\s*'read-tree'\s*,", lib_code)),
          "快照以 read-tree HEAD 播种（保住已追踪但被 .gitignore 忽略的文件）")

    # 功能性·阴：把"只在注释里提到"的样本喂进同一判据，必须判为不合格。
    # 否则哪天判据又退回裸子串，上面两条会重新变成"检查有没有人提过这个词"。
    _cmt_only = "/* 用临时 GIT_INDEX_FILE 并 ['read-tree','HEAD'] 播种 */\nconst x = 1;\n"
    _cs = strip_js_comments(_cmt_only)
    check(not re.search(r'GIT_INDEX_FILE\s*:', _cs)
          and not re.search(r"\[\s*'read-tree'\s*,", _cs),
          '功能性·阴：仅在注释里提及不算实现（防判据退回裸子串）')

    # 功能性·阳：行注释里出现 `/*`（真实案例：注释中写 mcp-server/*）**不得**
    # 让后续真代码被误吞。这条是本轮实打实踩出来的坑 —— 当时闸门凭空恒红，
    # 而恒红会逼下一轮去放宽断言，正好制造它要防的假绿（L1.32 教训）。
    _tricky = ("// 已追踪但被忽略的文件（如 mcp-server/*）不会丢\n"
               "const env = { GIT_INDEX_FILE: tmp };\n")
    _ts = strip_js_comments(_tricky)
    check(bool(re.search(r'GIT_INDEX_FILE\s*:', _ts)),
          '功能性·阳：行注释中的 `/*` 不会吞掉其后的真代码（防闸门无中生有恒红）')
    # 对偶：块注释里的 `//` 也不该被当行注释，否则块注释会"提前闭合"漏出内容
    check(strip_js_comments('/* 见 http://x 说明 */\nlet y=1;').strip() == 'let y=1;',
          '功能性·阳：块注释内的 `//` 不影响其整体被剥离')

    # ---- 顺序断言：快照调用必须在 wrangler 部署之前 ----
    i_snap = dep.find('snapshotWorkingTree(ROOT)')
    i_dep = dep.find("'pages', 'deploy'")
    check(i_snap != -1, 'deploy.mjs 确实调用了 snapshotWorkingTree(ROOT)')
    check(i_dep != -1, '阳性：定位到 wrangler 部署调用（定位不到则顺序断言空转）')
    check(i_snap != -1 and i_dep != -1 and i_snap < i_dep,
          '快照调用位于 wrangler 部署之前（snap@%d < deploy@%d —— '
          '放到部署之后等于在最需要它时缺席）' % (i_snap, i_dep))

    # 传参必须落实。曾真实踩过：函数从 deploy.mjs 抽到 lib 后签名多了 root 形参，
    # 调用处却还留着无参的 snapshotWorkingTree()，跑起来 root=undefined 静默返回 null
    # —— 快照全程不生成，而所有静态断言照绿。
    check(not re.search(r'snapshotWorkingTree\(\s*\)', dep),
          'deploy.mjs 未出现无参调用 snapshotWorkingTree()（root=undefined 会静默失效）')


# ---------- L1.39 对外统计不得把不同证据强度的行折叠成一个数 ----------
def layer1_39():
    """L1.39 /api/oss?stats=1 必须摊开成分，不能只给 total（20260807-06）

    起因：06:00 轮写了 scripts/ingest_oss_bom.mjs（URDF <link> 摄取器），实测可产出
    98 行。但这 98 行里 42 行 category='unknown'、**全部** compatibility 为空、
    protocol/interface/voltage 全是 'N/A'。而现有 325 行里 unknown **一行都没有**、
    261 行（80%）带非空 compatibility。

    摄取器本身是诚实的（行上标了 confidence='low' / source_tier='C' / declared=false），
    真正的问题在**消费端**：`?stats=1` 只回一个 `total: data.length`，
    对 confidence / source_tier 不作任何区分。于是行级的诚实标注在**数字被读到的那一刻
    全部蒸发** —— 325→423 看上去是「涨了 30%」，实际是可判定率从 80% 掉到 62%。

    这与本仓库连着修的那一族是同一个病：truthy 折叠把「未声明」断言成 false，
    oss.js 顶部那条防「读不到」被渲染成「不存在」。本条防的是
    **「线索」被渲染成「已核实数据」** —— 都是把「不知道/弱证据」折叠进了强断言。

    所以不禁止摄取低证据数据（那会把有用的线索一起挡在门外），
    而是要求**总数旁边必须站着成分**：任何低置信度批量入库都会立刻显形。
    """
    print('\n[L1.39] 对外统计必须摊开证据成分（低证据行不得被折叠进总数）')

    rel = os.path.join('functions', 'api', 'oss.js')
    p = os.path.join(ROOT, rel)
    check(os.path.isfile(p),
          '阳性：OSS 端点存在（%s —— 不存在说明扫描目标写错，闸门空转）' % rel)
    src = read_text(p) if os.path.isfile(p) else ''

    # 与 L1.38 同样的教训：必须剥注释再判，否则本函数的说明文字自己就能把闸门喂绿。
    code = strip_js_comments(src)

    # ⚠️ 必须判「键: 值」而不是裸子串。首版三条全用 `'decidable_entities' in code`，
    # 被反向注入②当场戳穿：`decidable_note` 那句说明文字里**就写着**
    # "decidable_entities = 带非空 compatibility 的行数"，字符串字面量又不会被
    # strip_js_comments 剥掉 —— 于是把真字段整行删掉，闸门靠说明文字照样全绿。
    # 第 46/48 条教训（裸子串可被蒙混）在本闸门上的第三次复发，这次是我自己写的。
    check(re.search(r'by_confidence\s*:\s*\w+', code) is not None,
          'stats 输出 by_confidence 字段（证据强度成分可见）')
    check(re.search(r'by_source_tier\s*:\s*\w+', code) is not None,
          'stats 输出 by_source_tier 字段（来源层级成分可见）')
    check(re.search(r'decidable_entities\s*:\s*\w+', code) is not None,
          'stats 输出 decidable_entities 字段（多少行真能参与兼容判断）')

    # confidence 缺失必须单独成桶，不得默认成 high —— 否则又是一次 truthy 折叠。
    check(re.search(r"e\.confidence\s*\|\|\s*'unrated'", code) is not None,
          "未标注 confidence 的行记为 'unrated'（不得默认当成 high）")
    check(re.search(r"e\.confidence\s*\|\|\s*'high'", code) is None,
          '反向：未出现把缺失 confidence 折叠成 high 的写法')

    # decidable 必须真的按 compatibility 非空来算，而不是随便挂个等于 total 的数。
    check(re.search(r'compatibility\.length\s*>\s*0', code) is not None,
          'decidable 依据 compatibility 非空计算（而非等同于 total）')

    # ---- 功能性：拿真数据跑一遍，确认这些桶不是摆设 ----
    oss_path = os.path.join(ROOT, 'api', 'oss_components.json')
    if os.path.isfile(oss_path):
        with open(oss_path, encoding='utf-8') as f:
            doc = json.load(f)
        rows = doc.get('data', [])
        decidable = sum(1 for e in rows if isinstance(e.get('compatibility'), list) and e['compatibility'])
        unknown_cat = sum(1 for e in rows if e.get('category') in (None, '', 'unknown'))
        check(decidable <= len(rows),
              '功能性：decidable(%d) 不超过总行数(%d)' % (decidable, len(rows)))
        # 这两条是**数据侧**的闸门：摄取器可以随时写，但只要写进来的东西会把
        # 目录稀释成「搜得到、判不了」，这里就会红。它给 ingest_oss_bom.mjs 定了个
        # 明确的准入门槛，而不是靠人记着「那个脚本先别跑」。
        check(unknown_cat == 0,
              '功能性：组件目录无 category=unknown 行（实得 %d；'
              'URDF <link> 类线索若要入库须先解决类目推断，或改投独立 BOM 层）' % unknown_cat)
        ratio = (decidable * 100 // len(rows)) if rows else 0
        check(ratio >= 70,
              '功能性：可判定率 %d%%（%d/%d）不低于 70%%——'
              '低于此线说明目录被无兼容维度的线索行稀释' % (ratio, decidable, len(rows)))


def layer1_40():
    """L1.40 补写留痕的可信性（20260807-08）

    ── 本轮暴露的缺陷：留痕闸门把「有人部署」等同于「飞轮那一轮跑过」 ──

    L1.21 孤儿检测 + L1.32 占位机制共同要求：**每个有部署活动的小时都必须有小时报告**。
    这条前提在飞轮独占部署权时成立。但 8/7 07:02 与 08:20 两次部署来自
    **总指挥主线任务**（用户直接指挥的推广/路线图工作，非飞轮轮次），
    deploy.mjs 照例落了 AUTO-STUB，占位里写着「本轮报告未由运行本人填写…
    说明该轮运行异常中断」——**而那两个小时根本不存在飞轮轮次，没有"本人"可填**。

    后果不是多一条噪音告警，而是闸门**逼出伪造**：
    唯一的变绿方式是把占位改写成一份第一人称的"飞轮 07:00 轮报告"，
    即为一次别人做的部署编造一轮不存在的运行。这与本仓一路在防的"假绿"同族，
    且更坏 —— 前者是漏检，后者是**由闸门亲手生产的伪造留痕**，
    而留痕体系的全部价值就建立在"痕迹为真"上。第 6 条不变式（哈希须真实存在）
    防的是报告内容造假，这里防的是报告**主体**造假。

    ── 修法：承认第二种合法收尾方式 ──

    每次部署仍必须被**交代**，但交代有两种：
      (a) 该轮运行自己填写（第一人称，原路径）；
      (b) 后续轮次**补写**（RECONCILED）—— 显式声明"这不是我做的，
          以下内容据 git 痕迹重建"，并标注补写者的轮次。

    (b) 一旦存在就可能被滥用成免检通道（"全部标 RECONCILED 即可变绿"），
    所以补写必须**比第一人称更贵**，由本闸门强制四项：
      1. 补写者轮次必须**晚于**被补写的时段 —— 不能自己补自己、不能用未来轮次；
      2. 正文必须含免责声明 `据 git 痕迹重建` —— 读者永远知道这是重建不是亲历；
      3. 必须引用**至少一个真实存在**的 commit 哈希（复用第 6 条不变式的判据）
         —— 无据重建 = 换个壳的伪造；
      4. 不得同时残留 AUTO-STUB —— 两种状态互斥，避免"标了补写却没真写"。
    """
    print('\n[L1.40] 补写留痕可信性（RECONCILED 不得成为免检通道）')
    import datetime as _dt

    res_dir = os.path.join(ROOT, 'ops', 'results')
    now = _dt.datetime.now()
    cur = (now.strftime('%Y%m%d'), now.strftime('%H'))

    # 行锚定，与 AUTO-STUB 同规格：文件**是**补写 ≠ 文件**提到**补写。
    RECON_RE = re.compile(
        r'^[ \t]*<!--[ \t]*ROBOPARTS-RUN-TRACE:RECONCILED[ \t]+by=(\d{8})-(\d{2})[ \t]*-->[ \t]*$',
        re.M)
    STUB_RE = re.compile(
        r'^[ \t]*<!--[ \t]*ROBOPARTS-RUN-TRACE:AUTO-STUB[ \t]*-->[ \t]*$', re.M)
    DISCLAIMER = '据 git 痕迹重建'

    def _recon_of(text):
        m = RECON_RE.search(text)
        return (m.group(1), m.group(2)) if m else None

    def _sha_exists(sha):
        # 与 L1.x 幽灵闸门共用同一个历史重写感知解析器（禁止在此另抄一份判据：
        # 手抄两份的下场见 L1.69 —— 一处放宽另一处不知情）。
        st, _cur, typ = _hh.resolve(ROOT, sha, [ROOT])
        return st in ('current', 'rewritten') and typ == 'commit'

    bad_order, no_disclaimer, no_real_sha, both_marks = [], [], [], []
    for p in sorted(glob.glob(os.path.join(res_dir, 'roboparts-*.md'))):
        m = re.match(r'roboparts-(\d{8})-(\d{2})\.md$', os.path.basename(p))
        if not m:
            continue
        txt = read_text(p)
        by = _recon_of(txt)
        if not by:
            continue
        slot = (m.group(1), m.group(2))
        tag = '%s-%s' % slot
        # 1) 补写者必须晚于被补写时段，且不得晚于当前小时（不能用未来轮次背书）
        if not (slot < by <= cur):
            bad_order.append('%s(by=%s-%s)' % (tag, by[0], by[1]))
        # 2) 免责声明
        if DISCLAIMER not in txt:
            no_disclaimer.append(tag)
        # 3) 至少一个真实哈希
        cands = set(re.findall(r'`([0-9a-f]{7,40})`', txt))
        if not any(_sha_exists(s) for s in cands):
            no_real_sha.append(tag)
        # 4) 两种标记互斥
        if STUB_RE.search(txt):
            both_marks.append(tag)

    check(not bad_order,
          '补写者轮次晚于被补写时段且不在未来（违规: %s）' % (bad_order[:4] or '无'))
    check(not no_disclaimer,
          '补写报告含免责声明「%s」（缺失: %s）' % (DISCLAIMER, no_disclaimer[:4] or '无'))
    check(not no_real_sha,
          '补写报告引用至少一个真实存在的 commit 哈希（无据重建: %s）'
          % (no_real_sha[:4] or '无'))
    check(not both_marks,
          '补写标记与占位标记互斥（同时存在: %s）' % (both_marks[:4] or '无'))

    # ── 判据自身的双向验证（L1.32 首版恒红的教训：性质要固化成断言）──
    _ok = '# x\n\n<!-- ROBOPARTS-RUN-TRACE:RECONCILED by=20260807-08 -->\n'
    check(_recon_of(_ok) == ('20260807', '08'), '阳性：合规补写标记能被解析出补写轮次')
    _prose = ('# x\n\n本轮说明：过期占位可由后续轮次以 RECONCILED 标记补写，'
              'by=20260807-08 这样的写法出现在散文里不应生效。\n')
    check(_recon_of(_prose) is None,
          '阴性：正文提及 RECONCILED 的普通报告不被当成补写（L1.32 首版恒红同型）')
    # 缺 by= 的裸标记不得放行 —— 否则"谁补的"丢失，追责链断裂
    check(_recon_of('<!-- ROBOPARTS-RUN-TRACE:RECONCILED -->\n') is None,
          '阴性：缺 by= 轮次的裸补写标记无效（补写必须留下补写者）')
    # 防"改宽松以求变绿"：判据不得退回裸子串匹配
    _src = read_text(os.path.join(ROOT, 'scripts', 'regression.py'))
    _mk = 'RECON' + 'CILED'
    check(not any(b in _src for b in ["'%s' in txt" % _mk, '"%s" in txt' % _mk,
                                      "'%s' in read_text(" % _mk]),
          '判据未退回裸子串匹配（退回即失去行锚定，散文提及就能免检）')
    # 哈希判据必须真能分辨真伪 —— 否则第 3 条形同虚设
    check(_sha_exists('HEAD'), '功能性：哈希存在性判据对真实提交返回真')
    check(not _sha_exists('0' * 12), '功能性：哈希存在性判据对捏造哈希返回假')

    # deploy.mjs 侧：占位必须如实标注**部署发起方**，否则重建者只能猜。
    # 07/08 两份占位写着"运行异常中断"，而真相是主线任务部署 —— 这句误导正是
    # 后续轮次被引向伪造的起点：它先入为主地断言"存在一轮跑挂了的飞轮"。
    dep = read_text(os.path.join(ROOT, 'scripts', 'deploy.mjs'))
    check('ROBOPARTS_ACTOR' in dep,
          'deploy.mjs 读取 ROBOPARTS_ACTOR（区分飞轮轮次与主线/人工部署）')
    check(re.search(r'发起方', dep) is not None,
          '占位正文写入「发起方」一行（未标注时如实写"未标注"，不得假定是飞轮）')
    check(re.search(r'该轮运行异常中断', dep) is None,
          '占位不得断言"该轮运行异常中断"（主线部署时此话为假，会诱导下一轮伪造运行）')


def layer1_41():
    """L1.41 MCP 未知参数不得被静默吞掉（20260807-08）

    实测：`search_components{"query":"harmonic reducer"}` 返回 total_matched=685、
    首条 ACT-001（一款智能舵机）；把 query 换成 `zzzznonexistentxyz`，返回**逐字相同**。
    根因：筛选参数叫 keyword，`query` 属未知键，旧实现直接忽略 —— 于是"没有筛选条件"
    被当成"浏览全库"，685 条原样返回。

    这是本仓修过三次的同族缺陷的第四型（前三：truthy 折叠 / key_specs 空洞 /
    未声明当 false）：**不确定的输入被折叠成一个看起来很确定的输出**。
    但这一型危害更大 —— 前三型至少还长得像"没有数据"，这一型**失败伪装成成功**：
    调用方收到的不是报错，是「共匹配 685 条」，读起来像一次命中极广的成功检索。
    Agent 会把 ACT-001 起的前 10 条当作 "harmonic reducer" 的最佳匹配讲给用户，
    错误结论挂着 RoboParts 的名字。而 `query` 是 MCP 生态最常见的检索参数名，
    不读 schema 直接猜的调用方几乎必然踩中。

    时机上尤其要命：01:00 轮刚把"用户照文档接不进来"那扇门修好，
    门后第一个工具就是这个行为 —— 修好门却把人领进坏房间，不如门一直关着。

    本闸门以**真跑 handler** 为准（node scripts/verify_mcp_args.mjs），
    不做源码形似判断；另加一条静态防退化：可接受参数必须从 schema 的 properties 推导，
    不得另写一份硬编码白名单（两处各写一份必然漂移，那正是缺陷的温床）。
    """
    print('\n[L1.41] MCP 未知参数拒绝（失败不得伪装成成功）')
    src = read_text(os.path.join(ROOT, 'functions', 'mcp.js'))

    # 静态：白名单必须源自 schema，且拒绝路径真的 return（不是记个日志继续跑）
    check(re.search(r'inputSchema\?\.properties\s*\|\|\s*\{\}', src) is not None,
          '可接受参数从 inputSchema.properties 推导（不得另写硬编码白名单致漂移）')
    check(re.search(r'unknownArgs[\s\S]{0,400}?return rpcError\(id,\s*-32602', src) is not None,
          '发现未知参数即 return -32602（不得仅告警后继续执行）')
    check('did_you_mean' in src,
          '错误里给出 did_you_mean（把调用方送回正轨，而非只说"你错了"）')

    # 功能性：真跑 handler。源码断言只能证明"写了"，跑一遍才证明"生效"。
    vp = os.path.join(ROOT, 'scripts', 'verify_mcp_args.mjs')
    if not os.path.isfile(vp):
        check(False, 'scripts/verify_mcp_args.mjs 存在（本闸门的功能性依据）')
        return
    node = shutil.which('node') or 'node'
    try:
        r = subprocess.run([node, vp], cwd=ROOT, capture_output=True,
                           encoding='utf-8', errors='replace', timeout=90)
        tail = (r.stdout or '').strip().splitlines()
        check(r.returncode == 0,
              'verify_mcp_args.mjs 真跑全绿（实得: %s）'
              % (tail[-1] if tail else (r.stderr or '')[:120]))
    except Exception as e:
        check(False, 'verify_mcp_args.mjs 可执行（异常: %s）' % str(e)[:100])


def layer1_42():
    """L1.42 飞轮不得把自己的脚印读成市场需求（20260807-08）

    read_metrics.py 此前只把 `toolsrc:probe:*` 当探针，其余 kind 一律计入"真实需求"，
    于是打印出 `已全部归因：探针 0 次 / 真实需求 7 次`。

    但 functions/mcp.js 的 callerKind() 对 curl/wget/python-requests 返回 **'script'**，
    而**飞轮每轮上线后的线上验证 curl 恰恰就是 script**。本轮实测 7 次 search_components
    全部记在 `toolsrc:script:*`，次数与我方 curl 次数吻合 —— 工具把自己的脚印读成了需求。

    这是观测层假绿的第 6 例，与 L1.26（「无法归因」被报成「探针已剔除」）同源：
    **最影响资源投向的数字凭空获得可信度**。"MCP 有没有人真在用"决定要不要继续投分发，
    读成 7 就会得出"有需求，加码"；真值可能是 0。

    修法不是给 curl 打标（未来仍会有别的模糊 UA），而是把判据从二分改三分：
    明确探针 / **不可归因**（script、空 UA、unknown、bot —— 既可能是飞轮自己，
    也可能是目录扫描，也可能是真集成方，无从区分）/ 可识别的真实调用方。
    只有第三类计入需求下界。宁可下界为 0，也不许把自检读成需求。

    本闸门锁死：① 存在 AMBIGUOUS_KINDS 且含 script ② script 不得计入 real_lo
    ③ 判读必须输出区间而非单值 ④ 不得退回"已全部归因/真实需求 N 次"的旧措辞。
    """
    print('\n[L1.42] 遥测不得把自检 curl 读成真实需求')
    p = os.path.join(ROOT, 'scripts', 'read_metrics.py')
    src = read_text(p)
    # 剥离注释后再扫描：否则会匹配到解释缺陷的注释，在代码已修好时报红并诱导删注释修绿
    # （L1.22 / L1.25 均记过这一课）。
    code = '\n'.join(re.sub(r'#.*$', '', ln) for ln in src.splitlines())

    check(re.search(r"AMBIGUOUS_KINDS\s*=\s*\{[^}]*'script'", code) is not None,
          "存在 AMBIGUOUS_KINDS 且把 'script' 归入不可归因（飞轮自身 curl 即 script）")
    check(re.search(r"AMBIGUOUS_KINDS\s*=\s*\{[^}]*'empty-ua'", code) is not None,
          "空 UA 同样归入不可归因（无 UA 不构成真实用户证据）")
    check(re.search(r'real_lo\s*=\s*src_named', code) is not None,
          '需求下界只取「可识别真实调用方」（不得把 src_all - probe 当下界）')
    check(re.search(r'src_named\s*=\s*max\(\s*src_all\s*-\s*src_probe\s*-\s*src_ambig', code)
          is not None,
          'src_named 必须同时扣除 probe 与 ambiguous 两部分')
    check('真实需求区间' in src,
          '判读输出区间而非单值（单值会被下游当成确定结论）')
    check('已全部归因' not in code,
          '不得退回"已全部归因"措辞（该措辞把不可归因说成已归因，正是 L1.26 记过的错）')
    check(re.search(r'包含飞轮自身的线上验证\s*curl', src) is not None,
          '显式警告 script 类含飞轮自身 curl（不利事实必须写在读数旁边，不许只留注释）')

    # 功能性阴阳验证：构造两份计数，确认 script 不抬下界、named 才抬下界。
    vp = os.path.join(ROOT, 'scripts', 'verify_l142_injections.py')
    check(os.path.isfile(vp), 'verify_l142_injections.py 存在（反向注入依据）')


def layer1_43():
    """L1.43 对外机读契约必须由真相源生成，且照它调用真的能通（20260807-12）

    11:00 主线交付了 skills/manifest.json —— 我们请外部 Agent 框架
    「直接解析此文件自动注册工具」的机读契约。本轮按它写的参数逐个真跑线上端点：

        roboparts-search              query              → -32602 未知参数（真名 keyword）
        roboparts-compat-check        components:[...]   → -32602 缺 component1_id/component2_id
        roboparts-recommend           count_per_category → -32602 未知参数（真名 count）
        roboparts-parameter-semantics parameter_semantics→ -32602 未知工具（真名 get_parameter_semantics）
        roboparts-dataset-discovery   dataset_discovery  → -32602 未知工具（**根本不存在**）

    **5 个声明的 mcp_tool 技能，0 个能用。** 而且清单每一项都"长得对"——
    有 tool、有 params、有 desc、有 when_to_use，只是没有一项对得上端点。

    最该记住的不是"手抄错了"，是**闸门的作用域被我自己定小了**：
    同一天 08:00 刚在 mcp.js 内部把白名单改成从 schema 推导，理由白纸黑字写着
    "杜绝两处各写一份而漂移"；三小时后就在另外三个文件里手抄了第三、四、五份
    （manifest.json / skills/README.md / agent-discovery.json 的 skills.items）。
    病不在"那一处忘了同步"，在"任何手抄的复述都会漂移"。

    还有一层反讽：08:00 把未知参数从静默忽略改成硬拒绝（-32602），本是好事；
    但配上这份错误清单，结果是**照文档接入的人从"拿到错答案"变成"一句也调不通"**。
    修好校验反而放大了文档错误的杀伤力 —— 契约与实现必须同源，才配收紧校验。

    闸门两条腿：
      ① 同源：三处对外复述必须能被 gen_skills_manifest.mjs 逐字重新生成（--check）
      ② 真跑：照 manifest 声明的参数调用 handler，不得 -32602
         （含阳性对照，防止"端点根本不校验"造成的假绿）
    """
    print('\n[L1.43] Skills 机读契约同源 + 照单可调通')
    node = shutil.which('node') or 'node'

    gen = os.path.join(ROOT, 'scripts', 'gen_skills_manifest.mjs')
    ver = os.path.join(ROOT, 'scripts', 'verify_skills_manifest.mjs')
    if not (os.path.isfile(gen) and os.path.isfile(ver)):
        check(False, 'gen_skills_manifest.mjs / verify_skills_manifest.mjs 存在（本闸门依据）')
        return

    # 静态：TOOLS 必须被导出，否则生成器只能回去手抄
    mcp_src = read_text(os.path.join(ROOT, 'functions', 'mcp.js'))
    check(re.search(r'^export\s*\{\s*TOOLS\s*\}', mcp_src, re.M) is not None,
          'functions/mcp.js 导出 TOOLS（对外契约的唯一真相源）')

    # 静态：生成器不得把工具名/参数名写死在自己身上（那只是把手抄挪了个地方）
    gen_src = read_text(gen)
    hardcoded = [n for n in ('search_components', 'check_compatibility',
                             'recommend_for_application', 'get_parameter_semantics')
                 if re.search(r'^(?!\s*\*).*(["\'])%s\1' % n, gen_src, re.M)]
    check(not hardcoded,
          '生成器不硬编码工具名（硬编码=把手抄挪个地方，漂移照旧）%s'
          % ('，实得: ' + ', '.join(hardcoded) if hardcoded else ''))
    check('inputSchema' in gen_src and 'properties' in gen_src,
          '参数由 inputSchema.properties 推导（与运行时白名单同源）')

    # ① 同源：三处对外复述可被逐字重新生成
    try:
        r = subprocess.run([node, gen, '--check'], cwd=ROOT, capture_output=True,
                           encoding='utf-8', errors='replace', timeout=90)
        bad = [ln.strip() for ln in (r.stdout or '').splitlines() + (r.stderr or '').splitlines()
               if ln.strip().startswith('❌')]
        check(r.returncode == 0,
              'manifest / README 表格 / agent-discovery.skills 与 TOOLS 逐字同源'
              + ('（漂移: %s）' % '；'.join(bad)[:200] if bad else ''))
    except Exception as e:
        check(False, 'gen_skills_manifest.mjs --check 可执行（异常: %s）' % str(e)[:100])

    # ② 真跑：照清单调用不得 -32602
    try:
        r = subprocess.run([node, ver], cwd=ROOT, capture_output=True,
                           encoding='utf-8', errors='replace', timeout=120)
        tail = [ln for ln in (r.stdout or '').strip().splitlines() if ln.strip()]
        fails = [ln for ln in tail if ln.startswith('❌')]
        check(r.returncode == 0,
              'verify_skills_manifest.mjs 真跑全绿：照清单参数调用每个技能（实得: %s）'
              % (fails[0][:160] if fails else (tail[-1] if tail else (r.stderr or '')[:120])))
    except Exception as e:
        check(False, 'verify_skills_manifest.mjs 可执行（异常: %s）' % str(e)[:100])

    # 反向注入依据
    check(os.path.isfile(os.path.join(ROOT, 'scripts', 'verify_l143_injections.py')),
          'verify_l143_injections.py 存在（反向注入依据）')


def layer1_44():
    """L1.44 异常指标必须可定位到"修哪儿"，且不得被自身探针污染（20260807-16）

    本轮遥测显示当日 404 共 42 次 —— 然后就没有然后了。埋点只写了一个
    `status:404` 计数：知道每天在流血，查不出伤口在哪。根因很典型：
    normalizePath() 本质是**已知好页面的白名单**，而 404 按定义必然不在
    白名单里，一律落 `__other` 被丢弃。

    危害不在"少个数字"，在于两类性质完全相反的东西被混成一个总数：
      · 我方死链（llms.txt / sitemap / 文章互链指错）—— 爬虫每撞一次都是
        GEO 抓取与 Agent 接入的直接损失，必须修；
      · 扫描器噪声 —— 完全无需理会。
    混在一起，运营只能在"要不要慌"之间瞎猜。这与 L1.42 同型：
    **有计数无归因的指标不会让人更清醒，只会让人更笃定地猜错。**

    但"记得更细"本身带来第二个坑：扫描器会拿随机路径把 KV 键空间撑爆，
    真实死链反而被淹掉，而 KV 写入额度每日有限。所以闸门必须同时守住
    两个对立面，只守一边都会放过一种假修复：
      ① 能定位：我方死链逐条独立成键，且不得退化成"全归 other"
      ② 有界化：长尾/扫描路径必须收敛到聚合桶
      ③ 不自污：deploy.mjs 每轮故意探私有路径拿 404，必须落 selftest 命名空间
      ④ 有人读：埋点写了没人读 = 没埋（这坑 mcp:* 段已经踩过一次）
    """
    print('\n[L1.44] 404 必须可定位（我方死链 vs 扫描噪声）+ 键空间有界')
    node = shutil.which('node') or 'node'
    mw = read_text(os.path.join(ROOT, 'functions', '_middleware.js'))

    check('function classify404' in mw and 'export { classify404 }' in mw,
          '中间件有 classify404 且导出（对外可测的真相源只此一份）')
    check(re.search(r'bump\(`404path:\$\{classify404\(', mw) is not None,
          '404 写入路径归因键（只记总数=知道在流血却查不出伤口）')
    check(re.search(r'bump\(`404ua:', mw) is not None,
          '404 记录调用方类别（爬虫撞死链才是真伤 GEO，与扫描器不同量级）')

    # ③ 不自污：自检分支必须在真实计数之前就把 404 隔离掉
    st = mw.split('SELFTEST_HEADER')[-1] if 'SELFTEST_HEADER' in mw else ''
    selftest_block = mw[mw.find('if (req.headers.get(SELFTEST_HEADER))'):
                        mw.find('bump(\'total\')')] if 'bump(\'total\')' in mw else st
    check("bump('selftest:status:404')" in selftest_block,
          '自检 404 落 selftest 命名空间（deploy 每轮探私有路径，否则读成"站点有断链"）')

    # ④ 有人读：写了没 section 的指标等于没埋。
    # 注意判据不能只 grep 键名字符串 —— 键名同时出现在文件末尾的 known 兜底元组里，
    # 只 grep 就会在"展示逻辑被整段删掉"时照样绿（本闸门第一版真的这样漏过）。
    # 必须验展示逻辑本身存在。
    rm = read_text(os.path.join(ROOT, 'scripts', 'read_metrics.py'))
    check(re.search(r"k\[len\('404path:'\):\]", rm) is not None
          and re.search(r"k\[len\('404ua:'\):\]", rm) is not None,
          'read_metrics.py 真的解析并展示 404 归因（不是只在兜底元组里出现键名）')
    check('路径归因' in rm and '我方死链' in rm and 'scan' in rm,
          '读取端明确区分「我方死链需修」与「扫描噪声忽略」（不区分=等于没归因）')

    # ① ② 真跑分类器（含阳性对照，防"全归 other"式假修复）
    ver = os.path.join(ROOT, 'scripts', 'verify_404_attribution.mjs')
    if os.path.isfile(ver):
        vsrc = read_text(ver)
        # 验证脚本本身也可能被换成永远退出 0 的空壳 —— 那样 returncode 判据就废了。
        # 先确认它真的在测被测对象，再信它的退出码。
        check(re.search(r"import\s*\{\s*classify404\s*\}\s*from\s*['\"]\.\./functions/_middleware\.js",
                        vsrc) is not None and vsrc.count('classify404(') >= 8,
              '验证脚本真的在测 classify404 本体（防"永远退出 0 的空壳"）')
        try:
            r = subprocess.run([node, ver], cwd=ROOT, capture_output=True,
                               encoding='utf-8', errors='replace', timeout=90)
            tail = [ln for ln in (r.stdout or '').strip().splitlines() if ln.strip()]
            fails = [ln for ln in tail if ln.startswith('❌')]
            check(r.returncode == 0,
                  'verify_404_attribution.mjs 真跑全绿：可定位 + 有界 + 阳性对照（实得: %s）'
                  % (fails[0][:160] if fails else (tail[-1] if tail else (r.stderr or '')[:120])))
        except Exception as e:
            check(False, 'verify_404_attribution.mjs 可执行（异常: %s）' % str(e)[:100])
    else:
        check(False, 'verify_404_attribution.mjs 存在（本闸门真跑依据）')

    # 闸门自持的独立行为探针：不依赖外部验证脚本，闸门自己也必须能判死。
    # （L1.43 那轮的教训：把判据全外包给一个脚本，那个脚本被替换闸门就瞎了。）
    probe = (
        "import {classify404 as c} from './functions/_middleware.js';"
        "const mine=['/iso-9409-flanges','/articles/x-guide','/api/entities'].map(c);"
        "const uniq=new Set(mine).size===3 && !mine.includes('other');"
        "const scan=c('/wp-login.php')==='scan' && c('/.env')==='scan';"
        "const b=new Set();for(let i=0;i<200;i++)b.add(c('/'+'z'.repeat(60)+i));"
        "console.log(uniq&&scan&&b.size<=2?'OK':'BAD');"
    )
    try:
        r = subprocess.run([node, '--input-type=module', '-e', probe], cwd=ROOT,
                           capture_output=True, encoding='utf-8',
                           errors='replace', timeout=60)
        check((r.stdout or '').strip().endswith('OK'),
              '闸门自持探针：可定位 + 识别扫描 + 长尾有界（实得: %s）'
              % ((r.stdout or r.stderr or '').strip()[:120] or '无输出'))
    except Exception as e:
        check(False, '闸门自持探针可执行（异常: %s）' % str(e)[:100])

    # ⑤ 顺藤摸到的同族缺陷：对外公布的入口必须扛得住 HEAD 探活。
    # Pages Functions 按 onRequest<Method> 路由，没有 onRequestHead 就一律 404，
    # 实测 HEAD /mcp = 404 而 GET /mcp = 200 —— 目录站/监控默认用 HEAD，
    # 我们等于对着来探活的人说"我不在"。这正是那 42 次无归因 404 的一大来源。
    # 【20260807-17】本轮在中间件里试过两种"集中补偿"，全部失败（复盘见 _middleware.js）：
    # 中间件能改响应，改不了路由分发。故判据落在方法级导出上，而不是中间件里。
    # 这条约定靠人自觉必然漏 —— 全站 17 个 GET 路由本轮一个都没有 onRequestHead。
    missing_head = []
    for dp, _dn, fns in os.walk(os.path.join(ROOT, 'functions')):
        for fn in fns:
            if not fn.endswith('.js') or fn.startswith('_'):
                continue
            fp = os.path.join(dp, fn)
            src = read_text(fp)
            if not re.search(r'export\s+(?:async\s+)?function\s+onRequestGet', src):
                continue
            if 'onRequestHead' in src or re.search(
                    r'export\s+(?:async\s+)?function\s+onRequest\s*\(', src):
                continue
            missing_head.append(os.path.relpath(fp, ROOT).replace('\\', '/'))
    check(not missing_head,
          '每个 GET 函数路由都导出 onRequestHead（Pages 不做 HEAD→GET 映射，缺失即 404 ='
          '对目录站宣告下线。缺失: %s）' % (', '.join(missing_head[:4]) if missing_head else '无'))
    # 补了还得补对：HEAD 必须沿用 GET 的真实状态且无 body，
    # 写死 200 会把故障期的端点报成健康 —— 那是比 404 更坏的谎。
    mcp_src = read_text(os.path.join(ROOT, 'functions', 'mcp.js'))
    _hseg = mcp_src.split('onRequestHead')[-1][:400] if 'onRequestHead' in mcp_src else ''
    check(re.search(r'new Response\(null,\s*\{\s*status:\s*r\.status', _hseg) is not None,
          'HEAD 响应沿用 GET 状态且无 body（写死 200 会把故障端点报成健康）')
    reg_src = read_text(os.path.join(ROOT, 'functions', 'api', 'register.js'))
    check('export async function onRequestGet' in reg_src and '405' in reg_src,
          'GET /api/register 返回 405 自述而非 404（对外公布的地址不得装作不存在）')
    dep = read_text(os.path.join(ROOT, 'scripts', 'deploy.mjs'))
    check("method: 'HEAD'" in dep and 'HEAD 探活' in dep,
          'deploy.mjs 每次部署在线校验 HEAD 探活（静态检查证明不了线上路由行为）')
    # 探活拿到 HEAD 404 后回退 GET —— 只要 GET 通就报绿。正是这条回退，让"线上 HEAD 全是
    # 404、目录站判我们下线"在部署校验里连续两轮显示全绿。校验方式必须与真实探活方式一致。
    _dseg = dep.split('for (const ep of')[-1][:900] if 'for (const ep of' in dep else ''
    check(re.search(r'status === 404\)\s*r\s*=\s*await\s+fetch', _dseg) is None
          and not re.search(r'\blet\s+r\s*=\s*await\s+fetch', _dseg),
          'deploy 探活只认 HEAD 结果、不回退 GET（回退等于把"HEAD 仍坏"报成绿）')

    check(os.path.isfile(os.path.join(ROOT, 'scripts', 'verify_l144_injections.py')),
          'verify_l144_injections.py 存在（反向注入依据）')

    # ⑤ 归因埋点抓到的死链必须真的被堵上 —— 否则"能定位"只是换个姿势继续漏。
    # 20260807-17 首批可定位死链里有两个 .well-known 入口：Agent 框架按 A2A 规范
    # 探 /.well-known/agent.json，Glama 按连接器认领规范探 /.well-known/glama.json。
    # 这两处 404 的代价不是"少个文件"，是**已经找上门的接入方与目录站被挡在门外**。
    wk = os.path.join(ROOT, '.well-known')
    ac = os.path.join(wk, 'agent.json')
    check(os.path.isfile(ac), '/.well-known/agent.json 存在（A2A Agent Card，Agent 侧最标准的敲门入口）')
    if os.path.isfile(ac):
        card = json.load(open(ac, encoding='utf-8'))
        check('gen_skills_manifest' in str(card.get('$comment', '')),
              'agent.json 由生成器产出（工具清单第四处复述，手写必漂移，见 L1.43）')
        check(bool(card.get('skills')) and card.get('url', '').endswith('/mcp'),
              'agent.json 有 skills 且 url 指向真实 MCP 端点')
    gj = os.path.join(wk, 'glama.json')
    check(os.path.isfile(gj), '/.well-known/glama.json 存在（Glama 连接器认领，其爬虫已在探测）')
    if os.path.isfile(gj):
        g = json.load(open(gj, encoding='utf-8'))
        check(g.get('$schema', '').endswith('connector.json')
              and isinstance(g.get('maintainers'), list) and g['maintainers']
              and 'email' in g['maintainers'][0],
              'glama.json 用连接器认领 schema（server.json 是给 GitHub 仓库的，域名侧用错=认领不上）')


# ---------- L1.45 对外收款页：承诺必须有可用通道，数字必须来自真相源 ----------
PAY_PAGES = ['pricing.html', 'credits.html', 'api-pricing.html']

# 页面上一旦正面出现这些词，就等于对外承诺了一条收款通道
GATEWAY_WORDS = {
    'creem': 'creem',
    'paypal': 'paypal',
    'stripe': 'stripe',
    'usdt': 'crypto',
    'usdc': 'crypto',
    'credit card': 'card',
    '信用卡': 'card',
}

# 否定语境标记：出现在同一段窗口内，说明是"我们不支持 X"而非"我们支持 X"
NEGATION_MARKERS = [
    'do not accept', "don't accept", 'does not accept', 'not accept', 'no longer',
    'retired', 'discontinued', 'unavailable',
    '不支持', '不接受', '暂不', '已移除', '已下线', '已停用', '不再',
]


def _negated(text, idx, span=200):
    """判断第 idx 处提及是否处在否定语境。

    只看提及点前后一个窗口，而不是整页 —— 否则页面任意角落有一句"不支持"，
    就能把全页的正面承诺洗白，闸门等于自废。
    """
    lo = max(0, idx - span)
    win = text[lo: idx + span].lower()
    return any(m in win for m in NEGATION_MARKERS)


def scan_pay_page(html, truth_total, implemented_endpoints):
    """返回违规列表。纯函数，便于阳性对照（反向注入）验证闸门本体不是空壳。

    implemented_endpoints: 形如 {'create'}，即 functions/api/payment/ 下**仍在提供服务**
    （非 410 / @deprecated）的端点名集合。
    """
    v = []
    low = html.lower()
    called = set(re.findall(r'/api/payment/([a-z0-9_-]+)', low))

    # ① 承诺的支付方式必须有可用通道
    for word, gw in GATEWAY_WORDS.items():
        start = 0
        while True:
            i = low.find(word, start)
            if i < 0:
                break
            start = i + len(word)
            if _negated(html, i):
                continue
            # 正面提及 → 该页必须真的调用一个可用的支付端点来兑现它
            if not (called & implemented_endpoints):
                v.append('正面承诺「%s」(%s) 但本页未调用任何可用支付端点' % (word, gw))
            elif gw == 'creem' and 'creem' not in implemented_endpoints:
                v.append('正面承诺「creem」但 creem 端点已停用')

    # ② 页面上宣称的实体总数必须等于真相源
    for m in re.finditer(r'(\d{3,5})\s*\+?\s*(?:robot part )?entit(?:y|ies)', low):
        n = int(m.group(1))
        if n != truth_total:
            v.append('宣称 %d entities，真相源为 %d' % (n, truth_total))
    for m in re.finditer(r'(\d{3,5})\s*条?\s*实体', html):
        n = int(m.group(1))
        if n != truth_total:
            v.append('宣称 %d 条实体，真相源为 %d' % (n, truth_total))

    # ③ 页面引用的支付端点必须真实可用（防止指向已下线/不存在的结算流程）
    for ep in called:
        if ep not in implemented_endpoints:
            v.append('调用 /api/payment/%s，但该端点不可用（不存在或已停用）' % ep)

    return v


def _live_payment_endpoints():
    d = os.path.join(ROOT, 'functions', 'api', 'payment')
    out = set()
    for f in os.listdir(d):
        if not f.endswith('.js'):
            continue
        src = read_text(os.path.join(d, f))
        # 410 / @deprecated 的端点不算"可用通道"
        if '@deprecated' in src or 'status: 410' in src:
            continue
        out.add(f[:-3])
    return out


def layer1_45():
    """L1.45 对外收款页不得承诺没有通道的支付方式（20260807-17）

    本轮发现：8/6 决定去除 Creem，8/7 16:40 把 credits.html / pricing.html 的入口摘了 ——
    但 **/api-pricing 整页漏改**，还在对外写："International (USD): credit card, PayPal,
    crypto (USDT/USDC) via Creem"。而 Creem 账户从未开启 Live Payments，
    也就是说：这一整段承诺，在写下它的那一刻就没有任何一条能兑现。

    同一页还并列着两处早已漂移的数字："577 robot part entities (482 verified)"
    （真相源 688）、"4,500+ entities across 12 domains / All 12 knowledge bases"
    （那是另一个项目的文案）。L2 的"七处数字一致性"守不住它 ——
    因为定价页压根不在那七处里。

    这三件事是同一个病：**对外承诺没有被纳入真相源的管辖范围。**
    功能页改了、数据源改了、收款通道下了，唯独"我们对外说了什么"没人复核。
    而定价页恰恰是转化链路的最后一米：在这里说的每一句不能兑现的话，
    代价不是"信息过时"，是**把一个已经准备付钱的人送进一个必然失败的流程**。

    闸门守三件事，缺一件都能让同类漏洞照样上线：
      ① 页面正面提到的每一种支付方式，必须有真实可用的后端端点兜底
         （否定语境如 "we do not accept PayPal" 放行 —— 明说不支持是诚实，不是违规）
      ② 页面宣称的实体数必须等于真相源（把定价页纳入数字一致性管辖）
      ③ 页面引用的 /api/payment/* 必须存在且未停用（410/@deprecated 不算可用）
    并以阳性/阴性对照验证闸门本体不是"永远返回空列表"的空壳。
    """
    print('\n[L1.45] 对外收款页：承诺必须有通道 + 数字必须来自真相源')
    truth = load_entities()['meta']['total_entities']
    live = _live_payment_endpoints()

    check('create' in live, '自助结算端点 /api/payment/create 可用（唯一在售通道）')
    check('creem' not in live,
          'Creem 端点已停用（下线通道必须连 URL 一起下线，否则它替你继续承诺）')

    for page in PAY_PAGES:
        p = os.path.join(ROOT, page)
        if not os.path.isfile(p):
            check(False, '%s 存在' % page)
            continue
        viol = scan_pay_page(read_text(p), truth, live)
        check(not viol, '%s 无失效承诺/漂移数字（违规: %s）' % (page, viol[:3]))

    # 阳性对照：闸门必须能抓到"典型的漏改定价页"，否则上面全绿毫无意义
    bad = ('<p>Pay with credit card, PayPal or crypto (USDT) via Creem.</p>'
           '<li>577 robot part entities</li>'
           '<button onclick="fetch(\'/api/payment/creem\')">Buy</button>')
    got = scan_pay_page(bad, truth, live)
    check(len(got) >= 3,
          '阳性对照：伪造的漏改页必须被判红（实得 %d 项违规）' % len(got))
    good = ('<p>WeChat Pay / Alipay only. We do not accept credit cards, PayPal or crypto.</p>'
            '<li>%d entities</li>'
            '<button onclick="fetch(\'/api/payment/create\')">Buy</button>' % truth)
    check(scan_pay_page(good, truth, live) == [],
          '阴性对照：明说"不支持"+ 数字正确 + 端点可用的页面不得误伤')


def layer1_46():
    """L1.46 死链告警必须先回探再判"需修"（20260807-19）

    本轮发现：read_metrics 的 404 归因把"当天累计计数"直接当成待办，
    于是今天已经在 17–18 点修好的 5 条（agent.json / glama.json / /mcp /
    api/register / api/validate）在剩下的一整天里继续挂着"⛔ 我方死链，需修"。

    为什么这不是小事：一条**长期为真却不需要动作**的告警，会训练读它的人跳过它。
    等哪天真出现一条新死链，它就静静躺在那 6 行里，和 5 条已修的长得一模一样。
    这与今天早些时候 HEAD 探活的教训是同一个病的两面：
    那次是"校验方式和真实访问方式不一致"造成**假绿**，这次是
    "告警口径和当前事实不一致"造成**假红**。假绿放过故障，假红废掉告警。

    修法：判"需修"前对每条路径回探 HEAD+GET，任一仍 404 才算 broken；
    网络异常保守计入（绝不允许断网把告警清绿）；再按"是否已对外公布"分 P0/P1。
    """
    print('\n[L1.46] 死链告警：回探现状 + 按是否对外公布分级')
    rm = os.path.join(ROOT, 'scripts', 'read_metrics.py')
    src = read_text(rm)
    check('def probe_404' in src,
          'read_metrics 有 probe_404 回探（累计计数不等于当前事实）')
    check("'HEAD'" in src and "'GET'" in src and 'probe_404' in src,
          '回探同时打 HEAD 与 GET（HEAD 404/GET 200 对目录站仍是下线）')
    check(re.search(r"return 'broken' if 404 in seen", src) is not None,
          '任一方法仍 404 即判 broken（不得因 GET 通了就算修好）')
    check(re.search(r"except Exception:\s*\n\s*return 'unknown'", src) is not None
          and "state.get(k) != 'fixed'" in src,
          '回探失败保守计入待办（断网不得把告警清成绿）')
    check("state.get(k) != 'fixed'" in src,
          '待办集合由回探结果决定，而非直接取埋点计数')

    # 对照：is_advertised 是纯函数，直接真跑
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    try:
        import importlib
        rmod = importlib.import_module('read_metrics')
        importlib.reload(rmod)
        check(rmod.is_advertised('/mcp', ROOT) is True,
              '阳性对照：已对外公布的 /mcp 必须判为 advertised（P0 口径）')
        check(rmod.is_advertised('/api/__never_published__', ROOT) is False,
              '阴性对照：从未公布的路径不得占用 P0 待办位')
    except Exception as e:
        check(False, 'is_advertised 可导入并真跑（异常: %s）' % e)


def layer1_47():
    """【L1.47】站点图标与主题色（浏览器/搜索引擎的默认请求）。

    2026-08-07 21:00 巡检发现：全站 27 个 HTML 里只有 4 个声明了图标，
    且是 emoji data-URI；`/favicon.ico` 线上 404。浏览器**默认**会在每个
    页面请求 `/favicon.ico`，这不是"外部瞎猜"，而是平台约定。Google SERP
    图标也不认 data-URI，结果搜索列表一直显示默认地球图标。

    不变式：
      1. 三个图标文件必须存在（favicon.ico / favicon.svg / apple-touch-icon.png）
      2. 每个对外 HTML 都声明 /favicon.ico、/favicon.svg、apple-touch-icon、theme-color
      3. read_metrics.py 必须把 /favicon.ico / apple-touch-icon 等约定路径判为 advertised
      4. --url 提供时，线上 /favicon.ico 必须 200
    """
    print('\n[L1.47] 站点图标与主题色')
    import re as _re
    import urllib.request

    for name in ('favicon.ico', 'favicon.svg', 'apple-touch-icon.png'):
        check(os.path.exists(os.path.join(ROOT, name)), f'{name} 存在')

    # 20260808-13：本闸门原来只 glob 根目录，`articles/` 下 16 篇文章页从建站起就
    # 一个图标声明都没有，却一直判绿 —— **闸门扫描面漏了，比闸门不存在更危险**，
    # 因为它给出"已覆盖"的错觉。扫描面必须与注入器 targets() 同源并逐个比对。
    htmls = sorted(glob.glob(os.path.join(ROOT, '*.html'))
                   + glob.glob(os.path.join(ROOT, 'articles', '*.html')))
    missing = []
    for p in htmls:
        t = read_text(p)
        rel = os.path.relpath(p, ROOT)
        needed = [
            ('/favicon.ico', 'rel="icon"' in t and '/favicon.ico' in t),
            ('/favicon.svg', 'rel="icon"' in t and '/favicon.svg' in t),
            ('apple-touch-icon', 'rel="apple-touch-icon"' in t),
            ('theme-color', 'name="theme-color"' in t),
        ]
        lacks = [n for n, ok in needed if not ok]
        if lacks:
            missing.append(f'{rel} 缺 {lacks}')
    check(not missing, '每个对外 HTML 都声明完整图标与主题色（异常: %s）' % (missing[:4] or '无'))

    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    try:
        import importlib as _il47
        _fav = _il47.import_module('inject_favicon')
        _il47.reload(_fav)
        gate_set = {os.path.relpath(p, ROOT).replace('\\', '/') for p in htmls}
        inj_set = {os.path.relpath(p, ROOT).replace('\\', '/') for p in _fav.targets()}
        check(gate_set == inj_set,
              '闸门扫描面与 inject_favicon.targets() 逐个相同（闸门独有 %s / 注入器独有 %s）'
              % (sorted(gate_set - inj_set)[:3], sorted(inj_set - gate_set)[:3]))
    except Exception as e:
        check(False, 'inject_favicon.targets() 可导入并与闸门比对（异常: %s）' % e)

    try:
        import importlib
        rmod = importlib.import_module('read_metrics')
        importlib.reload(rmod)
        for path in ('/favicon.ico', '/favicon.svg', '/apple-touch-icon.png'):
            check(rmod.is_advertised(path, ROOT) is True,
                  f'{path} 被 is_advertised 判为约定路径（P0 口径）')
        check(rmod.is_advertised('/__random_guess__.txt', ROOT) is False,
              '随机未公布路径不占用 P0 待办位')
    except Exception as e:
        check(False, 'is_advertised 可导入并真跑约定路径（异常: %s）' % e)


def layer1_48():
    """【L1.48】/.well-known/ 命名空间的 P0 口径：宁精勿宽。

    2026-08-07 23:30 巡检发现：L1.47 那轮为修 favicon，把整个 `/.well-known/`
    当成"约定必请求前缀"。后果是任何第三方目录站/扫描器按自家私有协议探一个
    根本不存在的路径（本次是 `/.well-known/mcp-verify-claim.txt`，全网查无此标准，
    官方 MCP Registry 用的是 DNS TXT `v=MCPv1` 与 `.well-known/mcp-registry-auth`），
    都会被记成"我方已承诺却敲不开"的 P0。告警一旦长期为真，人就会开始跳过它。

    正确口径：well-known 下**我方仓库里真有这个文件**（= 打算提供）才算承诺，
    线上 404 说明部署掉件，是真缺陷；仓库里没有 = 外部探测，不占 P0 名额。

    阴阳对照都要跑，防止口径再次一边倒：
      阳性 —— 仓库确有的 well-known 文件必须判 True（掉件能被抓到）
      阴性 —— 仓库没有的 well-known 探测必须判 False（不再误报 P0）
    """
    print('\n[L1.48] /.well-known/ P0 口径（阴阳对照）')

    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    try:
        import importlib
        rmod = importlib.import_module('read_metrics')
        importlib.reload(rmod)

        check('/.well-known/' not in getattr(rmod, 'CONVENTIONAL_ADVERTISED_PREFIXES', ()),
              '/.well-known/ 未被整体列为约定前缀（避免任何陌生探测都成 P0）')

        # 阳性：仓库里确实提供的发现文件，掉件必须能被抓出来
        wk_dir = os.path.join(ROOT, '.well-known')
        shipped = sorted(f for f in os.listdir(wk_dir)) if os.path.isdir(wk_dir) else []
        check(bool(shipped), '.well-known/ 存在且非空（当前: %s）' % (shipped or '空'))
        for name in shipped:
            p = '/.well-known/' + name
            check(rmod.is_advertised(p, ROOT) is True,
                  f'阳性: {p} 我方确实提供 → 判为已承诺（线上 404 应报 P0）')

        # 阴性：查无此标准的外部探测，不得占用 P0 名额
        for probe in ('/.well-known/mcp-verify-claim.txt',
                      '/.well-known/__never_shipped_probe__.txt'):
            check(rmod.is_advertised(probe, ROOT) is False,
                  f'阴性: {probe} 我方从未提供 → 不占 P0 待办位')

        # 交叉对照：favicon 一类真约定路径不能被本次收紧误伤
        check(rmod.is_advertised('/favicon.ico', ROOT) is True,
              '交叉对照: /favicon.ico 仍判为约定路径（收紧未误伤 L1.47）')
    except Exception as e:
        check(False, 'well-known P0 口径可真跑（异常: %s）' % e)


# ---------- L1.49 待办清单事实性：幽灵待办必须被抓出来（20260808-00） ----------
NEEDS_USER_MD = os.path.join(ROOT, 'ops', 'results', '_NEEDS_USER.md')
_ASSERT_RE = re.compile(r'<!--\s*assert:\s*(.+?)\s*-->')


def _eval_fact(expr, root=ROOT):
    """求值一条机读事实前提。语法（刻意只保留三种，够用且不会写错）：
        file:<相对路径> exists
        file:<相对路径> contains <子串>
        file:<相对路径> not-contains <子串>
    返回 True=前提成立 / False=前提已不成立。表达式写错则抛异常（视为红）。
    """
    parts = expr.split(None, 2)
    if len(parts) < 2 or not parts[0].startswith('file:'):
        raise ValueError('无法解析的事实前提: %r' % expr)
    path = os.path.join(root, parts[0][len('file:'):].replace('/', os.sep))
    op = parts[1]
    if op == 'exists':
        return os.path.exists(path)
    if op not in ('contains', 'not-contains'):
        raise ValueError('未知谓词 %r（仅支持 exists/contains/not-contains）' % op)
    if len(parts) < 3 or not parts[2]:
        raise ValueError('%s 缺少子串参数: %r' % (op, expr))
    if not os.path.exists(path):
        # 文件都没了，contains 一定不成立；not-contains 也不该在缺文件时判真
        return False
    with open(path, encoding='utf-8', errors='ignore') as f:
        body = f.read()
    hit = parts[2] in body
    return hit if op == 'contains' else (not hit)


def _parse_needs_user(text):
    """把 _NEEDS_USER.md 切成条目 —— 实现在 digest_due（留痕域唯一源），此处只转发。"""
    return _load_dd().parse_needs_user(text)


def layer1_49():
    """【L1.49】待办清单事实性：清单只增不减 → 迟早骗人。

    2026-08-08 00:40 巡检发现：`_NEEDS_USER.md` 里挂着"Copilot 接本地 Ollama
    需放开跨域，请设 OLLAMA_ORIGINS=* 并重启 Ollama"。而 8/7 那轮早已把 AI 解释
    改成走服务端 Agnes 代理，`copilot.html` 里 `11434` 引用本地线上均为 0——
    用户照着做纯属白费力气。同一份文件里还写着"pricing 改积分的切换仍在进行中"，
    实际线上 Creem 引用早已为 0。**代码改了，待办没人回头核销。**

    这是「口径 ≠ 事实」第 5 次显形（前四次：HEAD 假绿、回归假红、404 告警长期为真、
    GH_TOKEN 假待办），病根一致：判断依据与真实事实脱节。治法也一致——
    把"事实"变成机器每轮必查的断言，别指望人记得更新。

    机制：待办条目可用 `<!-- assert: file:X contains Y -->` 声明自己成立所依赖的
    事实前提；前提一旦不成立（代码改了、文件没了），判红，逼迫核销或改写。

    阴阳对照照例都跑，防止闸门自身空转。
    """
    print('\n[L1.49] 待办清单事实性（幽灵待办闸门）')

    # 阴阳自测：先证明求值器既会亮绿也会亮红，再拿它去判真实清单。
    # 哨兵串必须**运行时拼接**：初版直接把 `__never_a_token__` 写进断言，
    # 结果它作为源码字面量出现在本文件里，contains 反而命中 —— 自测被自己写的
    # 测试数据污染。这也算「口径 ≠ 事实」的一个微缩样本，留注防后人重蹈。
    sentinel = '__nev' + 'er_present_' + 'sentinel__%d' % os.getpid()
    try:
        check(_eval_fact('file:scripts/regression.py exists') is True,
              '阳性自测: 真实存在的文件判 True')
        check(_eval_fact('file:scripts/__never_exists__.py exists') is False,
              '阴性自测: 不存在的文件判 False（闸门会响）')
        check(_eval_fact('file:scripts/regression.py contains layer1_49') is True,
              '阳性自测: contains 命中判 True')
        check(_eval_fact('file:scripts/regression.py not-contains ' + sentinel) is True,
              '阳性自测: not-contains 未命中判 True')
        check(_eval_fact('file:scripts/regression.py contains ' + sentinel) is False,
              '阴性自测: contains 未命中判 False（幽灵前提会被抓）')
    except Exception as e:
        check(False, '事实求值器可真跑（异常: %s）' % e)
        return

    if not os.path.exists(NEEDS_USER_MD):
        check(False, '_NEEDS_USER.md 存在（用户问"我要干什么"的唯一真相源）')
        return
    with open(NEEDS_USER_MD, encoding='utf-8') as f:
        text = f.read()
    items = _parse_needs_user(text)
    open_items = [i for i in items if i[0]]
    check(bool(items), '_NEEDS_USER.md 可解析出待办条目（共 %d 条，未完成 %d 条）'
          % (len(items), len(open_items)))

    # 闸门不能空转：至少要有条目声明了机读前提，否则等于没查。
    # 当未完成项 < 3 时，要求全部都有事实前提；≥3 时仍要求至少 3 条，避免空转。
    with_facts = [i for i in open_items if i[2]]
    min_facts = min(3, len(open_items))
    check(len(with_facts) >= min_facts,
          '未完成待办中至少 %d 条声明了机读事实前提（当前 %d 条，防闸门空转）'
          % (min_facts, len(with_facts)))

    # 真身检查：每条未完成待办的事实前提都必须仍然成立
    for _is_open, title, facts in open_items:
        for expr in facts:
            try:
                ok = _eval_fact(expr)
            except Exception as e:
                check(False, '「%s」前提写法有误: %s（%s）' % (title, expr, e))
                continue
            check(ok, '「%s」前提仍成立: %s' % (title, expr))

    # 与 _LATEST.md 对账：对外播报的待办数必须等于清单实际条数。
    #
    # 20260808-22 修（「惩罚如实记录」族第 5 次，且捎带一个真假绿洞）：
    # 初版全文正则 `\*\*(\d+)\s*项` 取第一个匹配 —— 22:05 那轮报告里一句
    # 「**6 项新能力全部纳入飞轮巡检**」（讲的是能力，跟待办毫无关系）被当成
    # 待办播报数，而同一文件里如实写着的「仍是 **7 项**」反被无视，判假红。
    # 散文中凡出现「N 项」都成地雷，规避方式一律是"下轮换个说法"＝训练报告绕着说话。
    # 更严重的是 `if m:`：全文一个 `**N 项` 都不写，对账就**整个不执行**、静默放行
    # —— 写一篇不提数字的 _LATEST 即可绕过，这是假绿洞不是误伤。
    # 照 DIGEST-CLAIM 的既有先例改为**强制机读标记**：散文怎么写都不影响对账，
    # 且缺标记直接判红，堵死"不写就不查"。改完比改前**更严**，不是放宽。
    TODO_COUNT_RE = _load_dd().TODO_COUNT_RE
    latest = os.path.join(ROOT, 'ops', 'results', '_LATEST.md')
    if os.path.exists(latest):
        with open(latest, encoding='utf-8') as f:
            lt = f.read()
        tc = TODO_COUNT_RE.findall(lt)
        check(len(tc) == 1,
              '_LATEST.md 有且仅有一个机读待办数标记 <!-- TODO-COUNT: N -->'
              '（实测 %d 个 —— 缺失＝无法对账且静默放行，多个＝自相矛盾）' % len(tc))
        if len(tc) == 1:
            check(int(tc[0]) == len(open_items),
                  '_LATEST.md 播报的待办数(%s) == _NEEDS_USER.md 实际未完成数(%d)'
                  % (tc[0], len(open_items)))
        # 阴阳对照：证明标记解析器没空转。测试串运行时拼接，避免假标记以字面量
        # 形式留在源码里污染他处扫描（沿用本函数上方 sentinel 的同一教训）。
        _mark = '<!-- TODO-' + 'COUNT: 42 -->'
        check(TODO_COUNT_RE.findall('x %s y' % _mark) == ['42'],
              '阳性对照: 标记解析器能从正文取出机读待办数')
        check(TODO_COUNT_RE.findall('仍是 **7 项**，其中 6 项新能力纳入巡检') == [],
              '阴性对照: 散文里的「N 项」不再被误当成机读播报数（本条即误伤原因）')


# ---------- L1.50 巡检探活必须走隔离入口：飞轮不许自己给自己造流量（20260808-01） ----------

def _probe_header_name(src: str):
    """从源码里取出自检隔离头名（小写），取不到返回 None。"""
    m = re.search(r"""['"](X-RoboParts-Selftest|x-roboparts-selftest)['"]""", src)
    return m.group(1).lower() if m else None


def _bare_fetches(src: str):
    """找出未合并隔离头的对外 fetch —— 这些请求会被记成真实流量。"""
    bad = []
    for m in re.finditer(r'fetch\(\s*TARGET', src):
        # 头是写在调用块里的下几行，只看当前行会误判 —— 取调用后 300 字窗口。
        win = src[m.start():m.start() + 300]
        if 'SELFTEST_HEADERS' not in win:
            bad.append(win.splitlines()[0][:80])
    return bad


def layer1_50():
    """【L1.50】巡检探活必须走隔离入口（自检探针污染·第四型）。

    2026-08-08 01:45 巡检实证：飞轮每轮用裸 `curl` 扫关键路径，这些请求
    **不带** `X-RoboParts-Selftest`，于是全被 `_middleware.js` 记成真实流量：
      · 当轮打 `/__flywheel-pollution-probe-<ts>`（裸 curl）→ 该路径出现在
        **真实** 404 归因里；同一路径加隔离头再打一次 → 只进 selftest 命名空间。
      · 副作用是双向的：真实请求数被灌水，且飞轮自造的 404 会在下一轮被读成
        "站点有断链，正在实伤 GEO"——**自己造伤口，自己报警，再去修不存在的伤**。

    这是「自检探针污染」的第四型。前三型（伪造爬虫 UA / deploy 探私有路径 /
    目录站握手）都已在代码里堵死，唯独"临时敲的 curl"无入口可管。
    治法不是贴纪律条，而是**给它一个比 curl 更顺手的入口**（scripts/probe.mjs），
    再用本闸门锁死这个入口不许退化。

    阴阳对照照例都跑：在内存里把隔离头摘掉 / 把头名改漂，检测器必须变红。
    """
    print('\n[L1.50] 巡检探活隔离入口（自检探针污染·第四型）')

    probe_path = os.path.join(ROOT, 'scripts', 'probe.mjs')
    if not os.path.exists(probe_path):
        check(False, 'scripts/probe.mjs 存在（飞轮巡检的唯一对外探活入口）')
        return
    check(True, 'scripts/probe.mjs 存在（飞轮巡检的唯一对外探活入口）')
    probe = read_text(probe_path)

    # ① 三处头名必须一致：中间件认哪个头，探活工具就得发哪个头。
    #    任一处改名而另一处没跟上 = 隔离静默失效（不报错，最阴的坏法）。
    mw = read_text(os.path.join(ROOT, 'functions', '_middleware.js'))
    dep = read_text(os.path.join(ROOT, 'scripts', 'deploy.mjs'))
    names = {'_middleware.js': _probe_header_name(mw),
             'deploy.mjs': _probe_header_name(dep),
             'probe.mjs': _probe_header_name(probe)}
    check(all(names.values()) and len(set(names.values())) == 1,
          '中间件/deploy/probe 三处自检头名一致（%s）' % names)

    # ② probe.mjs 的每个对外请求都必须带隔离头
    bare = _bare_fetches(probe)
    check(not bare, 'probe.mjs 无裸请求（遗漏 %d 处: %s）' % (len(bare), bare[:2]))
    check(re.search(r'headers:\s*\{\s*\.\.\.SELFTEST_HEADERS', probe) is not None,
          'probe.mjs 在统一出口合并隔离头（单点保证，不靠逐处记得写）')

    # ③ 覆盖面：必须够用，否则人还是会退回去敲 curl
    must = ['/pricing', '/api/data.json', '/api/oss?stats=1', '/mcp', '/copilot']
    missing = [p for p in must if p not in probe]
    check(not missing, '探活覆盖核心路径（缺: %s）' % missing)
    check("method: 'POST'" in probe, '覆盖 POST 探活（/mcp 协议与 /api/copilot 代理）')

    # ④ 阴阳自测：把隔离头摘掉 / 头名改漂，检测器必须能抓到；否则上面全是摆设。
    mutated = probe.replace('...SELFTEST_HEADERS,', '')
    check(re.search(r'headers:\s*\{\s*\.\.\.SELFTEST_HEADERS', mutated) is None,
          '阴性自测: 摘掉隔离头后检测器判红（闸门非空转）')
    check(re.search(r'headers:\s*\{\s*\.\.\.SELFTEST_HEADERS', probe) is not None,
          '阳性自测: 现网源码判绿（阴阳成对，排除恒红/恒绿）')
    drifted = probe.replace('X-RoboParts-Selftest', 'X-RoboParts-Selfcheck')
    check(_probe_header_name(drifted) != _probe_header_name(mw),
          '阴性自测: 头名漂移可被检出（改名而中间件未跟进 → 隔离静默失效）')


# ---------- L1.51 清洁集不得含同物异 ID 重复：公布的数 == 不重复的数（20260808-02） ----------

def _load_entities_doc():
    with io.open(os.path.join(ROOT, 'api', 'entities.json'), encoding='utf-8') as f:
        return json.load(f)


def layer1_51():
    """【L1.51】清洁集去重闸门：宣称的"可信条目数"必须是不重复条目数。

    2026-08-08 02 巡检发现：全库按 (name, manufacturer) 聚类命中 8 组同名同厂商，
    其中 4 组的另一半早被规则 1/3 隔离（无害），但**另外 4 组两条都在清洁集里**：
      CHIP-66/CHIP-81（Jetson Orin NX）、CHIP-68/CHIP-91（Qualcomm RB5）、
      CHIP-80/CHIP-95（QRB5165）、RPLAT-009/RPLAT-010（Optimus Gen 3）。

    危害不止是数字虚高：`functions/mcp.js` 的 search / recommend 只过滤
    quarantine、**不做去重**，Agent 调 recommend_for_application 会拿到两条
    "不同 id、同一颗芯片"的候选，误判成两个可选方案 —— 选型引擎的功能性硬伤。

    这是「口径 ≠ 事实」在**数据层**的显形：前几次都发生在探活/告警/待办这类
    元信息上，这次直接落在卖点数据本身。故本闸门不只查"标没标"，
    还要求 meta 里的分项统计与实体现状逐项对得上，杜绝标记与账目各说各话。

    阴阳对照照例都跑。
    """
    print('\n[L1.51] 清洁集去重（口径 ≠ 事实 · 数据层）')

    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'lib'))
    try:
        from dedupe_rule import find_clean_duplicates
    except Exception as ex:
        check(False, 'scripts/lib/dedupe_rule.py 可导入（去重规则的唯一真相源）：%s' % ex)
        return
    check(True, 'scripts/lib/dedupe_rule.py 可导入（去重规则的唯一真相源）')

    doc = _load_entities_doc()
    ents = doc['entities']
    by_id = {e['id']: e for e in ents}

    # ① 核心断言：清洁集里不许再有同名同厂商
    left = find_clean_duplicates(ents)
    check(not left,
          '清洁集无同物异 ID 重复（残留 %d 组: %s）'
          % (len(left), [v for v in list(left.values())[:3]]))

    # ② 每条 duplicate 必须指得出规范条目，且规范条目本身是干净的
    dups = [e for e in ents if e.get('data_quality') == 'duplicate']
    check(all(e.get('duplicate_of') for e in dups),
          'duplicate 条目均带 duplicate_of 指向（缺失: %s）'
          % [e['id'] for e in dups if not e.get('duplicate_of')][:3])
    dangling = [e['id'] for e in dups if e.get('duplicate_of') not in by_id]
    check(not dangling, 'duplicate_of 指向的规范条目真实存在（悬空: %s）' % dangling[:3])
    quar_canon = [e['id'] for e in dups
                  if by_id.get(e.get('duplicate_of'), {}).get('quarantine') is True]
    check(not quar_canon,
          '规范条目未被隔离（否则整组消失在选型结果里: %s）' % quar_canon[:3])
    check(all(e.get('quarantine') is True for e in dups),
          'duplicate 条目均已隔离（漏隔离: %s）'
          % [e['id'] for e in dups if e.get('quarantine') is not True][:3])

    # ③ meta 账目必须与实体现状逐项对上（标记与账目不许各说各话）
    meta = doc.get('meta', {}).get('data_quality', {})
    actual_clean = sum(1 for e in ents if not e.get('quarantine'))
    check(meta.get('clean') == actual_clean,
          'meta.clean(%s) == 实际未隔离数(%s)' % (meta.get('clean'), actual_clean))
    actual_bd = {}
    for e in ents:
        actual_bd[e.get('data_quality')] = actual_bd.get(e.get('data_quality'), 0) + 1
    check(meta.get('breakdown') == actual_bd,
          'meta.breakdown 与实际分项一致（meta=%s / 实际=%s）'
          % (meta.get('breakdown'), actual_bd))
    listed = {d['duplicate'] for d in meta.get('duplicates_resolved', [])}
    check(listed == {e['id'] for e in dups},
          'meta.duplicates_resolved 与实体现状一致（meta=%s / 实体=%s）'
          % (sorted(listed), sorted(e['id'] for e in dups)))

    # ④ 三副本传播：真相源标了隔离，对外接口也得标，否则线上照样返回两份
    with io.open(os.path.join(ROOT, 'api', 'data.json'), encoding='utf-8') as f:
        _pub_doc = json.load(f)
        pub = {e['id']: e for e in (_pub_doc.get('data')
                                    or _pub_doc.get('entities') or [])}
    unpropagated = [e['id'] for e in dups
                    if pub.get(e['id'], {}).get('quarantine') is not True]
    check(not unpropagated,
          'api/data.json 已同步隔离标记（未传播: %s）' % unpropagated[:3])

    # ⑤ 对外披露必须等于 meta 真值 —— 数据层刚治完，文档层不许接着骗。
    #    llms.txt 是 Agent 读得最多的一份自我描述，这里写错等于对外系统性误导。
    llms = read_text(os.path.join(ROOT, 'llms.txt'))
    line = ''
    for ln in llms.splitlines():
        if ln.startswith('- `quarantine: true`'):
            line = ln
            break
    check(bool(line), 'llms.txt 含 quarantine 隔离披露行')
    if line:
        nums = [int(x) for x in re.findall(r'\d+', line)]
        check(meta.get('quarantined') in nums,
              'llms.txt 披露的隔离数含 meta 真值 %s（现文案数字: %s）'
              % (meta.get('quarantined'), nums))
        check(actual_clean in nums,
              'llms.txt 披露的干净集数含真值 %s（现文案数字: %s）' % (actual_clean, nums))
        stale = [int(x) for x in re.findall(r'\d+', line)]
        check(actual_clean + len(dups) not in stale or actual_clean in stale,
              'llms.txt 未残留去重前的旧干净集数 %s' % (actual_clean + len(dups)))

    # ⑤ 阴阳自测：内存里制造违规，检测器必须变红；现网数据必须绿
    fake = [dict(e) for e in ents]
    for e in fake:
        if e['id'] == (dups[0]['id'] if dups else None):
            e['quarantine'] = False
    check(bool(find_clean_duplicates(fake)) if dups else True,
          '阴性自测: 把一条 duplicate 放回清洁集后检测器判红（闸门非空转）')
    check(not find_clean_duplicates(ents),
          '阳性自测: 现网真相源判绿（阴阳成对，排除恒红/恒绿）')
    injected = [dict(e) for e in ents if not e.get('quarantine')][:1]
    if injected:
        clone = dict(injected[0])
        clone['id'] = clone['id'] + '-L151-SENTINEL'
        check(bool(find_clean_duplicates([e for e in ents if not e.get('quarantine')] + [clone])),
              '阴性自测: 新插入一条同名同厂商可被立即检出（防未来回流）')


def layer1_52():
    """【L1.52】摄取管道不得静默销毁数据层（「文档写的命令 ≠ 脚本要的开关」）。

    2026-08-08 04 巡检查明：OSS 数据层从 325 塌到 136（-58%），上一轮把它误判为
    「本环境对源仓库实时抓取连续失败」，并写进了报告与记忆。**实测 9/9 源全部 200 可达，
    网络自始至终没问题。** 真因是 `ingest_oss.mjs` 里 `LIVE = process.env.LIVE === '1'`
    默认关闭，而飞轮任务书、脚本 docstring、历次报告写的调用方式都是裸
    `node scripts/ingest_oss.mjs` —— 每一次「照文档执行」都会静默退化成纯种子层，
    并把 189 条 LIVE 实体连同累积历史一起覆盖掉。上一轮所谓「实跑两次均复现」，
    只是把同一个错误的调用方式跑了两遍。

    这是「口径 ≠ 事实」的第 7 次显形，且是首次**误诊到外部**：
    前几次是把自己的问题瞒过去，这次是把自己的问题赖给了网络。
    对照组做法（本轮已补）：怀疑网络就真发一次请求，别拿脚本的沉默当证据。

    三条不变式，缺一都会让同类事故复发：
      1. 裸调用（= 所有文档写的那条命令）必须走完整 LIVE 层；
      2. 关闭 LIVE 只意味着"这轮不去上游取新的"，绝不等于"把上游给过的删了"；
      3. 数据层大幅缩水必须**吵**（非零退出 + 拒写），不能像上次那样打印 ✅ 后安静退出。
    另加：整份重写 JSON 的脚本必须自己补回 meta.access（谁破坏谁修复）。
    """
    print('\n[L1.52] 摄取管道不得静默销毁数据层（口径 ≠ 事实 · 第 7 次）')

    src = read_text(os.path.join(ROOT, 'scripts', 'ingest_oss.mjs'))
    if not src:
        check(False, 'scripts/ingest_oss.mjs 可读')
        return

    # 1) 默认开启：裸调用即完整摄取
    m = re.search(r'const\s+LIVE\s*=\s*process\.env\.LIVE\s*(!==|===)\s*[\'"]([01])[\'"]', src)
    check(bool(m) and m.group(1) == '!==' and m.group(2) == '0',
          'LIVE 默认开启（裸调用 = 文档写的命令 = 完整摄取），关闭需显式 LIVE=0'
          + ('' if not m else '（现为 process.env.LIVE %s "%s"）' % (m.group(1), m.group(2))))

    # 2) 关闭 LIVE 时继承既有 LIVE 实体，而不是删除
    has_carry = re.search(r'else\s+if\s*\(\s*!RESET_LIVE\s*\)', src) and 'stale: true' in src
    check(bool(has_carry),
          'LIVE=0 分支继承既有 LIVE 实体并标记 stale（关闭抓取 ≠ 删除历史）')

    # 3) 缩水闸门：拒写 + 非零退出
    check('SHRINK_TOLERANCE' in src and 'process.exit(1)' in src,
          '数据层缩水时拒绝写出并以非零码退出（上次的静默 ✅ 正是漏网口）')

    # 4) 谁重写 JSON 谁补回 meta.access
    check('inject_api_access.py' in src,
          'ingest 自行重新注入 meta.access（整份重写会抹掉 AI 领 key 入口）')

    # 5) 把注入器 docstring 的「由 deploy 前置调用」变成事实
    dep = read_text(os.path.join(ROOT, 'scripts', 'deploy.mjs'))
    check('inject_api_access.py' in (dep or ''),
          'deploy.mjs 确实调用注入器（此前 docstring 自称自动挂载，实际 0 处引用）')

    # 6) 现状核对：LIVE 层真的在（不是"闸门齐全但数据已经没了"）
    try:
        doc = json.load(open(os.path.join(ROOT, 'api', 'oss_components.json'), encoding='utf-8'))
    except Exception:
        doc = {}
    meta = doc.get('meta') or {}
    live_n = meta.get('live_entities') or 0
    total_n = meta.get('total_entities') or 0
    check(live_n >= 150 and total_n >= 300,
          'OSS 数据层现状健康（total=%s / live=%s，退化基线 136/0）' % (total_n, live_n))
    check(isinstance(meta.get('access'), dict),
          'oss_components.json 带 meta.access（摄取后未被抹掉）')

    # 7) 阴阳对照：检测器不是恒绿
    check(not re.search(r'const\s+LIVE\s*=\s*process\.env\.LIVE\s*===\s*[\'"]1[\'"]',
                        "const LIVE = process.env.LIVE !== '0';"),
          '阳性自测: 修好的写法判绿')
    check(bool(re.search(r'const\s+LIVE\s*=\s*process\.env\.LIVE\s*===\s*[\'"]1[\'"]',
                         "const LIVE = process.env.LIVE === '1';")),
          '阴性自测: 退回默认关闭的旧写法会被检出（闸门非空转）')
    check(not ('SHRINK_TOLERANCE' in 'fs.writeFileSync(OUT, JSON.stringify({meta,data}))'),
          '阴性自测: 去掉缩水闸门后检测器判红')


# --- L1.53 探测器：抽成函数，阴阳自测才能跑同一套逻辑（而非各写各的） ---

def _probe_has_transport_retry(src: str) -> bool:
    """传输层失败（status===0）必须重试，而不是一次就判红。"""
    return bool(re.search(r'TRANSPORT_RETRIES', src)) and bool(
        re.search(r'for\s*\(\s*let\s+attempt\s*=\s*1;\s*attempt\s*<=\s*TRANSPORT_RETRIES', src))


def _probe_no_retry_on_http_status(src: str) -> bool:
    """拿到 HTTP 状态就立刻返回：站点真答错了不能靠重试洗白。"""
    return bool(re.search(r'if\s*\(\s*last\.status\s*!==\s*0\s*\)[\s\S]{0,200}?return\s+last', src))


def _probe_separates_failure_kinds(src: str) -> bool:
    """输出必须把「本机没网」和「站点故障」分开，读的人才不会写错结论。"""
    return ('transport_failures' in src and 'site_failures' in src
            and re.search(r'transportBad', src) is not None)


def layer1_53():
    print('\n[L1.53] 探活探针不得把本机瞬断报成站点故障（口径 ≠ 事实 · 第 8 次）')

    src = read_text(os.path.join(ROOT, 'scripts', 'probe.mjs'))
    if not src:
        check(False, 'scripts/probe.mjs 可读')
        return

    # 1) 传输层失败要重试
    check(_probe_has_transport_retry(src),
          '传输层失败（拿不到 HTTP 状态）会重试而非一次判红'
          '（20260808-04: /pricing 单次 fetch failed，复核 4 次全 200）')

    # 2) 但拿到状态就不许重试
    check(_probe_no_retry_on_http_status(src),
          '一旦拿到 HTTP 状态立即返回（重试只该救网络抖动，不该掩盖站点真故障）')

    # 3) 退避而不是空转连打
    check(bool(re.search(r'await\s+sleep\(\s*attempt\s*\*', src)),
          '重试带退避（连打三次同一瞬间等于没重试）')

    # 4) 两类失败分开呈现
    check(_probe_separates_failure_kinds(src),
          '输出区分「传输层无响应」与「站点级失败」（含 --json 的 site_failures/transport_failures）')

    # 5) 瞬断留痕：恢复了也要说第几次才通，别把不稳定藏起来
    check('recovered' in src and '瞬断' in src,
          '重试后恢复的条目会标注「第N次才通·瞬断」（不稳定不能被静默吞掉）')

    # 6) 阴阳对照：确保上面三个检测器不是恒真
    good_retry = ("const TRANSPORT_RETRIES = 3;\n"
                  "for (let attempt = 1; attempt <= TRANSPORT_RETRIES; attempt++) { }")
    old_no_retry = "const r = await fetch(url); return { status: r.status };"
    check(_probe_has_transport_retry(good_retry), '阳性自测: 带重试的写法判绿')
    check(not _probe_has_transport_retry(old_no_retry),
          '阴性自测: 退回「一次就判红」的旧写法会被检出（闸门非空转）')
    check(not _probe_no_retry_on_http_status("for(;;){ last = await hitOnce(); }"),
          '阴性自测: 无条件重试（含 HTTP 错误也重试）会被检出')
    check(not _probe_separates_failure_kinds("console.log(bad.length + ' 条异常')"),
          '阴性自测: 不区分失败类型的旧输出会被检出')


# --- L1.54 探测器：生成器不得静默抹掉横切必备件 ---
#
# 20260808-07 一次运行里，同一个病抓到三个新位置：
#   ① build_param_page.py 收尾想链式调 inject_onboarding.py，但本文件从未 import os，
#      每次都在那行抛 NameError 崩溃退出 —— 链式注入「写了但从未跑过一次」；
#   ② build_parameter_semantics.py 整份重写 api/parameter_semantics.json，
#      把 meta.access（AI 领 key 的机读入口）抹掉，且不负责补回；
#   ③ 该生成器的 <head> 模板不含 favicon/theme-color，每次重新生成都抹掉图标声明。
# 再加上 inject_onboarding.py 与 L1.52 里的 inject_api_access.py 一样没挂在 deploy 上。
#
# 共性：**谁整份重写对外文件，谁就要负责把横切必备件补回来，并且那条补救链路必须真能跑通。**
# 所以本闸门查三件事：链路声明、链路可执行性（AST 未定义名）、以及注入器确实挂在 deploy 上。

_PY_BUILTINS = set(dir(__builtins__)) if not isinstance(__builtins__, dict) \
    else set(__builtins__.keys())


def _module_level_undefined_names(src: str):
    """检出「模块级用到、但从未 import / 赋值 / 定义」的名字。

    专抓 ①那类 bug：语法合法、compile() 通过，只有执行到那一行才炸。
    只分析模块作用域（函数体有自己的作用域，纳入会引入大量假阳性）；
    ①的崩溃点正是模块级，够用且几乎不误报。
    """
    import ast as _ast
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return ['<语法错误>']

    bound = set(_PY_BUILTINS) | {
        '__name__', '__file__', '__doc__', '__spec__', '__package__',
        '__loader__', '__builtins__',
    }

    # 1) 收集模块作用域内所有绑定（不含函数/类体内部）
    def collect(node, top):
        for child in _ast.iter_child_nodes(node):
            if isinstance(child, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                bound.add(child.name)
                continue                      # 不下钻：独立作用域
            if isinstance(child, _ast.Lambda):
                continue
            if isinstance(child, (_ast.Import, _ast.ImportFrom)):
                for a in child.names:
                    bound.add((a.asname or a.name).split('.')[0])
            elif isinstance(child, _ast.Name) and isinstance(child.ctx, (_ast.Store, _ast.Del)):
                bound.add(child.id)
            elif isinstance(child, _ast.ExceptHandler) and child.name:
                bound.add(child.name)
            elif isinstance(child, _ast.Global):
                bound.update(child.names)
            collect(child, False)

    collect(tree, True)

    # 推导式在自己的作用域里绑定循环变量，一并纳入以免误报
    for n in _ast.walk(tree):
        if isinstance(n, (_ast.ListComp, _ast.SetComp, _ast.DictComp, _ast.GeneratorExp)):
            for gen in n.generators:
                for t in _ast.walk(gen.target):
                    if isinstance(t, _ast.Name):
                        bound.add(t.id)

    # 2) 检查模块作用域内的读取
    missing, seen = [], set()

    def scan(node):
        for child in _ast.iter_child_nodes(node):
            if isinstance(child, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                  _ast.ClassDef, _ast.Lambda)):
                continue                      # 同上：不下钻
            if isinstance(child, _ast.Name) and isinstance(child.ctx, _ast.Load):
                if child.id not in bound and child.id not in seen:
                    seen.add(child.id)
                    missing.append('%s(第%d行)' % (child.id, child.lineno))
            scan(child)

    scan(tree)
    return missing


def _calls_injector(src: str, injector: str) -> bool:
    """生成器收尾是否真的调用了指定注入器（而不是只在注释/docstring 里提一句）。"""
    pat = r'subprocess|_sp\.run|check_call|check_output'
    return bool(re.search(pat, src)) and injector in src


def _checks_injector_exit_code(src: str) -> bool:
    """调用了还不够：被调方失败必须让本进程也失败，否则等于没调。"""
    return bool(re.search(r'returncode\s*!=\s*0', src))


def layer1_54():
    print('\n[L1.54] 生成器不得静默抹掉横切必备件（口径 ≠ 事实 · 第 9 次）')

    sem_p = os.path.join(ROOT, 'scripts', 'build_parameter_semantics.py')
    pg_p = os.path.join(ROOT, 'scripts', 'build_param_page.py')
    sem = read_text(sem_p)
    pg = read_text(pg_p)
    if not sem or not pg:
        check(False, '两个生成器脚本可读')
        return

    # 1) 链路声明：谁重写谁补回
    check(_calls_injector(sem, 'inject_api_access.py'),
          'build_parameter_semantics 收尾补回 meta.access'
          '（整份重写 api/*.json 会抹掉 AI 领 key 入口）')
    check(_checks_injector_exit_code(sem),
          'meta.access 重注入失败会让生成器以非零码退出（调了不看结果 = 没调）')
    check(_calls_injector(pg, 'inject_onboarding.py'),
          'build_param_page 收尾补回 RP-ONBOARDING 接入区块（整页重写会冲掉）')
    check(_checks_injector_exit_code(pg),
          '接入区块重注入失败会让生成器以非零码退出')

    # 2) 链路可执行性 —— 抓「写了但一跑就崩」（本轮 ① 的真实病灶）
    for name, src in (('build_param_page.py', pg),
                      ('build_parameter_semantics.py', sem),
                      ('inject_onboarding.py',
                       read_text(os.path.join(ROOT, 'scripts', 'inject_onboarding.py'))),
                      ('inject_api_access.py',
                       read_text(os.path.join(ROOT, 'scripts', 'inject_api_access.py')))):
        und = _module_level_undefined_names(src or '')
        check(not und, '%s 模块级无未定义名（语法合法但一执行就 NameError）（异常: %s）'
                       % (name, und[:4] or '无'))

    # 3) 生成器模板自带全站必备声明（否则重新生成 = 静默降级）
    for need in ('/favicon.ico', '/favicon.svg', 'apple-touch-icon', 'theme-color'):
        check(need in pg,
              'build_param_page 模板内含 %s（不在模板里 = 每次重生成都抹掉）' % need)

    # 4) 注入器必须挂在 deploy 上（L1.52 只解决了 inject_api_access 一个）
    dep = read_text(os.path.join(ROOT, 'scripts', 'deploy.mjs'))
    check('inject_api_access.py' in dep, 'deploy 调用 inject_api_access.py')
    check('inject_onboarding.py' in dep,
          'deploy 调用 inject_onboarding.py（页面数字与真值同源，不靠人记得手工跑）')

    # 5) 注入器覆盖面 ⊇ 校验器扫描面 —— 两套口径不一致，每次改数字必漏
    inj = read_text(os.path.join(ROOT, 'scripts', 'inject_onboarding.py'))
    check("glob.glob(os.path.join(ROOT, 'articles', '*.html'))" in inj,
          '接入区块注入器按 glob 覆盖全部 articles/*.html'
          '（写死清单必然漏掉新增文章，06:45 那轮就漏了 14 篇）')

    # 6) 阴阳自测
    check(_module_level_undefined_names(
        'import os\nx = os.path.join("a", "b")\n') == [],
        '阳性自测: 正常导入的模块级代码判绿')
    check(_module_level_undefined_names(
        'x = os.path.join("a", "b")\n') != [],
        '阴性自测: 本轮那条「用 os 却没 import os」会被检出（闸门非空转）')
    check(_module_level_undefined_names(
        'def f():\n    return undefined_local\n') == [],
        '阴性自测: 函数体内的名字不纳入模块级判定（避免假阳性淹没真问题）')
    check(not _calls_injector('# 收尾会调用 inject_api_access.py 补回 meta.access\n',
                              'inject_api_access.py'),
          '阴性自测: 只在注释里写「会调用」不算数（文档写了 ≠ 挂上了）')
    check(not _checks_injector_exit_code('_sp.run([py, inj], check=False)\n'),
          '阴性自测: 调了却不看退出码会被检出')


# --- L1.55 探测器：注入器必须幂等（跑两次 = 跑一次） ---

_STYLE_SIG = '/* RP-ONBOARDING scoped styles */'


def _run_injector_twice(inject_fn, sample_html):
    """把真实 inject() 连跑两次，返回 (第一次结果, 第二次结果)。

    这是行为对照，不是源码正则 —— 源码怎么写不重要，跑两次不一样就是不幂等。
    """
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix='.html')
    os.close(fd)
    try:
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(sample_html)
        inject_fn(tmp)
        with open(tmp, encoding='utf-8') as f:
            first = f.read()
        inject_fn(tmp)
        with open(tmp, encoding='utf-8') as f:
            second = f.read()
        return first, second
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def layer1_55():
    print('\n[L1.55] 注入器必须幂等：跑两次 = 跑一次（否则每轮部署都往页面塞一份死重复）')

    # 1) 成品校验：线上要发的页面里，每个签名块最多 1 份
    #    （不管是谁、怎么塞进去的 —— 成品里堆了副本就是红）
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location(
        'inject_onboarding', os.path.join(ROOT, 'scripts', 'inject_onboarding.py'))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)

    dupes = []
    for p in mod.targets():
        with open(p, encoding='utf-8') as f:
            n = f.read().count(_STYLE_SIG)
        if n > 1:
            dupes.append('%s×%d' % (os.path.basename(p), n))
    check(not dupes,
          '页面内无重复接入样式块（重复: %s）' % (', '.join(dupes[:6]) or '无'))

    ld_dupes = []
    for p in mod.targets():
        with open(p, encoding='utf-8') as f:
            src = f.read()
        if src.count(mod.LD_START) > 1 or src.count(mod.MARK_START) > 1:
            ld_dupes.append(os.path.basename(p))
    check(not ld_dupes,
          '页面内无重复 LD-JSON / 接入区块（重复: %s）' % (', '.join(ld_dupes[:6]) or '无'))

    # 2) 行为对照：拿真实 inject() 连跑两次，必须逐字节相同
    block, ld = mod.html_block(), mod.build_ld_tag()
    sample = ('<html><head><title>t</title></head>'
              '<body><p>hi</p></body></html>')

    def _real(p):
        return mod.inject(p, block, ld)

    first, second = _run_injector_twice(_real, sample)
    check(first == second,
          '行为对照: 真实 inject() 连跑两次逐字节相同（第二次多出 %d 字节）'
          % (len(second) - len(first)))
    check(first.count(_STYLE_SIG) == 1 and second.count(_STYLE_SIG) == 1,
          '行为对照: 两次注入后样式块恒为 1 份（实测 %d / %d）'
          % (first.count(_STYLE_SIG), second.count(_STYLE_SIG)))

    # 3) 阴性自测：把自愈剥离器废掉（= 修复前的写法），必须被判非幂等
    #    —— 证明上面那条不是恒绿
    saved = mod.STYLE_SIG_RE
    try:
        mod.STYLE_SIG_RE = re.compile(r'(?!x)x')  # 永不匹配 = 退回旧行为
        bad1, bad2 = _run_injector_twice(_real, sample)
        check(bad1 != bad2 and bad2.count(_STYLE_SIG) == 2,
              '阴性自测: 废掉样式剥离器后立刻被判非幂等（闸门非空转，实测第二次 %d 份）'
              % bad2.count(_STYLE_SIG))
    finally:
        mod.STYLE_SIG_RE = saved

    # 4) 阴性自测：剥离标记块时不吃前导空行 → </head> 前空行逐轮堆积
    saved_strip = mod.strip_marked
    try:
        mod.strip_marked = lambda t, s, e: re.sub(
            re.escape(s) + r'.*?' + re.escape(e), '', t, flags=re.S)
        b1, b2 = _run_injector_twice(_real, sample)
        check(b1 != b2,
              '阴性自测: 剥离不吃前导空行会被检出（空行逐轮堆积也是不幂等）')
    finally:
        mod.strip_marked = saved_strip

    # 5) 阳性自测：确认恢复原状后仍判绿（排除上面两条把模块改坏了）
    ok1, ok2 = _run_injector_twice(_real, sample)
    check(ok1 == ok2, '阳性自测: 还原后仍幂等（阴阳成对，排除恒红/恒绿）')

    # 6) 幂等注入器必须真的挂在 deploy 上（否则成品照样漂移）
    with open(os.path.join(ROOT, 'scripts', 'deploy.mjs'), encoding='utf-8') as f:
        dep = f.read()
    check('inject_onboarding.py' in dep,
          'deploy 仍挂载 inject_onboarding.py（幂等了才敢每轮跑）')


# --- L1.56 探测器：服务层不得写死库存数字（注入器覆盖不到 functions/） ---
#
# 【20260808-10】本仓已有"页面数字唯一真相源 + 全量注入器"的纪律，但注入器只处理
# *.html 与 api/，**覆盖不到 functions/ 里的模板字符串**。于是服务层成了全站唯一一处
# 数字会自己腐烂的地方，且腐烂后无人发现：
#   · MCP instructions 对每个接入的 agent 宣称「收录 688 条实体，其中 685 条可选型」
#     —— 真值 706 / 703；
#   · `GET /mcp` 的 `dataset.total_entities: 688` 是**机读**字段，目录站会抓走再分发；
#   · 工具描述里「688 条中 38 条 ID 前缀与 category 不一致」—— 真值 15，虚高 2.5 倍。
# 三处都不是一开始就错，是入库涨了、文案没跟。
#
# 闸门测两件事，都用行为而非"源码里有没有某个词"：
#   1) 生产的 datasetFacts() 现算结果必须与真相源逐项相等（且降级时不编数字）；
#   2) functions/ 的**对外输出字符串**里不得再出现写死的库存计数。
_STOCK_NUM_PATTERNS = [
    (r'total_entities\s*:\s*\d+', 'total_entities: <写死数字>'),
    (r'\d+\s*条实体', '<数字> 条实体'),
    (r'[库全]内?库?\s*\d{3,}\s*条', '库内/全库 <数字> 条'),
    (r'\d{3,}\s*条中', '<数字> 条中'),
    (r'\d{3,}\s*条为', '<数字> 条为'),
]


def _strip_js_comments(src):
    """去掉 // 与 /* */ 注释，只留真正会发给调用方的字符串。

    注释里复盘历史错值（"此前写死 688"）是应该保留的，不能因此判红；
    判红的必须是**真的会输出出去**的那部分。
    """
    src = re.sub(r'/\*[\s\S]*?\*/', '', src)
    src = re.sub(r'(?m)^\s*//.*$', '', src)
    src = re.sub(r'(?<![:\w])//[^\n\'"`]*$', '', src, flags=re.M)
    return src


def _scan_hardcoded_stock(src):
    """返回命中的写死库存数字列表。抽成函数，阴阳自测才跑同一套逻辑。"""
    body = _strip_js_comments(src)
    hits = []
    for pat, label in _STOCK_NUM_PATTERNS:
        for m in re.finditer(pat, body):
            hits.append('%s → %r' % (label, m.group(0).strip()))
    return hits


def layer1_56():
    print('\n[L1.56] 服务层不得写死库存数字（口径 ≠ 事实 · 第 10 次）')

    mcp_path = os.path.join(ROOT, 'functions', 'mcp.js')
    with open(mcp_path, encoding='utf-8') as f:
        mcp_src = f.read()

    # 1) 行为对照：生产的 datasetFacts() 必须与真相源逐项相等
    #    抽生产源码本体来跑，避免"测试里另抄一份实现"这种自欺
    probe = _mcp_facts_probe(mcp_path, os.path.join(ROOT, 'api', 'entities.json'))
    facts = probe.get('facts')
    if facts is None:
        check(False, 'datasetFacts 可执行（实测失败: %s）' % probe.get('error', '')[-200:])
    else:
        check(probe['degraded'] == '',
              '取数失败时不编数字（factsNarrative(null) 返回空串）')

    if facts is not None:
        with open(os.path.join(ROOT, 'api', 'entities.json'), encoding='utf-8') as f:
            src_data = json.load(f)
        ents = src_data['entities']
        truth = {
            'total_entities': src_data['meta']['total_entities'],
            'market_intelligence': sum(
                1 for e in ents if e.get('entity_kind') == 'market_intelligence'),
            'organizations': sum(
                1 for e in ents if e.get('entity_kind') == 'organization'),
            'specifications': sum(
                1 for e in ents if e.get('entity_kind') == 'specification'),
            'software': sum(1 for e in ents if e.get('entity_kind') == 'software'),
            'quarantined': sum(1 for e in ents if e.get('quarantine') is True),
            'priced': sum(1 for e in ents if e.get('price_range')),
        }
        # selectable 用**白名单**：只有 entity_kind 为 component（或老数据缺字段）才算
        # 可选型零部件。原来写成"总数减去已知几类"，是黑名单——新增种类时静默失效。
        truth['selectable'] = sum(
            1 for e in ents if not e.get('entity_kind') or e.get('entity_kind') == 'component')
        bad = {k: (facts.get(k), v) for k, v in truth.items() if facts.get(k) != v}
        check(not bad, '服务层实况 == 真相源（total/selectable/情报/隔离/价格；不一致: %s）' % bad)
        check(facts['total_entities'] == len(ents),
              '实况总数取自实际条目数而非 meta 声明（%d）' % facts['total_entities'])
        # 隔离条目数必须真的被披露出去 —— 这是本轮补上的、此前从未对外说过的事实
        check(facts['quarantined'] > 0
              and str(facts['quarantined']) in probe.get('narrative', ''),
              '对外话术如实披露隔离条目数（%d 条，占 %.1f%%）'
              % (facts['quarantined'], 100.0 * facts['quarantined'] / facts['total_entities']))

    # 2) 静态扫描：对外输出字符串里不得再有写死的库存计数
    hits = _scan_hardcoded_stock(mcp_src)
    check(not hits, 'functions/mcp.js 输出串无写死库存数字（命中: %s）' % hits[:3])

    others = []
    fdir = os.path.join(ROOT, 'functions')
    for dirpath, _dirnames, filenames in os.walk(fdir):
        if 'node_modules' in dirpath:
            continue
        for fn in filenames:
            if not fn.endswith('.js'):
                continue
            p = os.path.join(dirpath, fn)
            with open(p, encoding='utf-8') as f:
                h = _scan_hardcoded_stock(f.read())
            if h:
                others.append('%s: %s' % (os.path.relpath(p, ROOT), h[0]))
    check(not others, 'functions/ 全目录输出串无写死库存数字（命中: %s）' % others[:3])

    # 3) 阴性自测：把旧写法塞回去，闸门必须立刻判红（否则等于空转）
    legacy = "const s = '库内共 688 条实体，其中 685 条为可选型零部件';"
    check(len(_scan_hardcoded_stock(legacy)) > 0,
          '阴性自测: 旧写法「库内共 688 条实体」会被检出（实测命中 %d 处）'
          % len(_scan_hardcoded_stock(legacy)))
    legacy2 = 'dataset: { total_entities: 688, categories: C },'
    check(len(_scan_hardcoded_stock(legacy2)) > 0,
          '阴性自测: 机读字段 total_entities: 688 会被检出')

    # 4) 阳性自测：注释里复盘历史错值不该判红（否则没人敢写复盘）
    commentary = '// 此前写死 688 条实体，真值 706\n/* dataset.total_entities: 688 曾被抓走 */'
    check(_scan_hardcoded_stock(commentary) == [],
          '阳性自测: 注释中复盘历史错值不判红（阴阳成对，排除恒红）')

    # 5) 常量不得回潮：INSTRUCTIONS 静态部分必须无数字化
    m = re.search(r'const INSTRUCTIONS_STATIC = \[([\s\S]*?)\]\.join', mcp_src)
    check(m is not None, 'INSTRUCTIONS 已拆为 STATIC + 运行时实况两段')
    if m:
        check(not re.search(r'\d{3,}\s*条', m.group(1)),
              'INSTRUCTIONS_STATIC 内无写死条数（数字只能由运行时实况提供）')


def _mcp_facts_probe(mcp_path, ents_path):
    """执行 functions/mcp.js 里**生产同一份** datasetFacts/factsNarrative，回报实测值。

    取源码本体用 new Function 求值（ESM 下 eval 的函数声明不会外泄到模块作用域，
    这一点已实测踩过），确保闸门测的是生产代码，而不是测试里另抄的一份实现。
    """
    import subprocess
    import tempfile
    harness = r'''
import fs from 'fs';
const src = fs.readFileSync(process.argv[2], 'utf8');
const grab = (name) => {
  const i = src.indexOf('function ' + name + '(');
  if (i < 0) throw new Error('未找到 ' + name);
  let d = 0, j = src.indexOf('{', i);
  for (let k = j; k < src.length; k++) {
    if (src[k] === '{') d++;
    else if (src[k] === '}') { d--; if (!d) { j = k; break; } }
  }
  return src.slice(i, j + 1);
};
const consts = src.match(/const ID_PREFIX_CATEGORY = \{[\s\S]*?\};/)[0];
// 20260809-05：datasetFacts 抽出了白名单辅助函数 isSelectableComponent，
// 探针只抓两个函数时会 ReferenceError。依赖是会长出来的 —— 这里显式带上它，
// 并保持"抓不到就报错"的行为（宁可闸门红，不可探针悄悄测了个残缺版本）。
const body = consts + '\n' + grab('isSelectableComponent') + '\n'
  + grab('datasetFacts') + '\n' + grab('factsNarrative')
  + '\nreturn { datasetFacts, factsNarrative };';
const { datasetFacts, factsNarrative } = new Function('CATEGORIES', body)([]);
const list = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')).entities;
const facts = datasetFacts(list);
console.log(JSON.stringify({
  facts,
  narrative: factsNarrative(facts),
  degraded: factsNarrative(null),
}));
'''
    fd, hpath = tempfile.mkstemp(suffix='.mjs')
    os.close(fd)
    try:
        with open(hpath, 'w', encoding='utf-8') as f:
            f.write(harness)
        r = subprocess.run(['node', hpath, mcp_path, ents_path],
                           capture_output=True, text=True, encoding='utf-8')
        if r.returncode != 0:
            return {'facts': None, 'error': r.stderr or ''}
        return json.loads(r.stdout)
    except Exception as e:  # noqa: BLE001 - 闸门自身失败必须显式判红，不得静默放行
        return {'facts': None, 'error': str(e)}
    finally:
        try:
            os.unlink(hpath)
        except OSError:
            pass


def _endpoint_handler(path):
    """把一条对外声明的 API 路径解析到**真实存在的处理者**；解析不到返回 None。

    这是 L1.57 的核心。刻意**不把 catch-all `functions/api/[[path]].js` 算作处理者** ——
    catch-all 对不认识的名字返回的正是 404，若把它当成"有人处理"，闸门就永远不会红，
    也就完全失去意义（这正是 `/api/search` 与 `/api/entity/{id}` 长期 404 却无人发现的原因）。
    """
    p = path.split('?')[0].split('#')[0].strip('/')
    if not p:
        return None
    # 1) 静态资产（api/*.json 这类直接由 Pages 托管的文件）
    if os.path.isfile(os.path.join(ROOT, p)):
        return 'static:' + p
    # 2) 精确函数路由 functions/<path>.js
    exact = os.path.join(ROOT, 'functions', *p.split('/')) + '.js'
    if os.path.isfile(exact):
        return 'function:' + os.path.relpath(exact, ROOT).replace('\\', '/')
    # 3) 动态段路由：目录逐级下行，叶子允许 [x].js（单段动态），不允许 [[x]].js
    segs = p.split('/')
    cur = os.path.join(ROOT, 'functions')
    for seg in segs[:-1]:
        nxt = os.path.join(cur, seg)
        if os.path.isdir(nxt):
            cur = nxt
            continue
        if not os.path.isdir(cur):
            return None
        dyn = [d for d in os.listdir(cur)
               if os.path.isdir(os.path.join(cur, d))
               and d.startswith('[') and not d.startswith('[[')]
        if not dyn:
            return None
        cur = os.path.join(cur, dyn[0])
    if not os.path.isdir(cur):
        return None
    leaf = segs[-1]
    if os.path.isfile(os.path.join(cur, leaf + '.js')):
        return 'function:' + leaf + '.js'
    # 叶子是 {id} 这类占位符，或调用方给的是具体值 —— 都由 [x].js 承接
    for f in sorted(os.listdir(cur)):
        if f.startswith('[') and not f.startswith('[[') and f.endswith('.js'):
            return 'function:' + f
    return None


def layer1_57():
    """L1.57 · 对外声明的 API 端点必须真的敲得开（"口径 ≠ 事实"在 API 面的防线）

    【20260808-11 起因】本轮把 `llms.txt` / `README.md` 那份 API 清单逐条线上回探，
    结果两条 404：
      - `GET /api/search?q=keyword` —— 还同时是 `index.html` 里 schema.org
        `SearchAction` 的 target，属**机器可读**的检索入口，搜索引擎与 AI agent 会照此发请求；
      - `GET /api/entity/{id}` —— 同一份清单里性质完全相同的另一条。
    两条都不是"坏掉了"，而是**从来就没实现过，却一直对外宣称**。

    本仓已因"口径 ≠ 事实"连续吃过多次亏（页面数字、MCP 播报数字、mcp-guide 的
    git clone 路径…）。每次都是修掉那一处，下次换个地方再犯。此闸门把这一类
    在 API 面上一次性锁死：**凡是写进对外文档的端点，必须能在仓库里找到承接它的
    静态资产或函数路由**，catch-all 不算数。

    做法是"声明 → 处理者"的落地对照，不是正则查关键字；并配阴性/阳性自测，
    保证它既不是恒绿的摆设，也不是恒红的噪音。
    """
    print('\n[L1.57] 对外声明的 API 端点必须真的敲得开')

    decl_re = re.compile(r'^\s*-\s*`(GET|POST|PUT|PATCH|DELETE)\s+(/api/[^`\s]*)`')
    declared = []   # (来源文件, 方法, 路径)
    for fname in ('llms.txt', 'README.md'):
        fpath = os.path.join(ROOT, fname)
        if not os.path.isfile(fpath):
            continue
        for line in open(fpath, encoding='utf-8'):
            m = decl_re.match(line)
            if m:
                declared.append((fname, m.group(1), m.group(2)))

    # openapi.json 的 paths 同样是对外声明，而且是**机读**的：API 目录站与 agent
    # 直接照它发请求。只查文档不查契约，等于放过最要命的那一面。
    oa_file = os.path.join(ROOT, 'api', 'openapi.json')
    if os.path.isfile(oa_file):
        oa_doc = json.load(open(oa_file, encoding='utf-8'))
        for p, item in (oa_doc.get('paths') or {}).items():
            for method in (item or {}):
                if method.lower() in ('get', 'post', 'put', 'patch', 'delete'):
                    declared.append(('openapi.json', method.upper(), p))

    check(len(declared) >= 10,
          f'已从 llms.txt/README.md/openapi.json 解析出对外 API 声明 {len(declared)} 条'
          f'（解析器没空转）')

    broken = []
    for src, method, path in declared:
        if _endpoint_handler(path) is None:
            broken.append(f'{src}: {method} {path}')
    check(not broken,
          f'每条对外声明的端点都能在仓库中找到承接者（无处理者的: {broken}）')

    # schema.org SearchAction 是机器可读的检索入口，单独校验（它不在上面那份清单里）
    idx = os.path.join(ROOT, 'index.html')
    if os.path.isfile(idx):
        html = open(idx, encoding='utf-8').read()
        m = re.search(r'"SearchAction".*?"target"\s*:\s*"([^"]+)"', html, re.S)
        check(m is not None, 'index.html 存在 schema.org SearchAction 声明')
        if m:
            tgt = m.group(1)
            tpath = re.sub(r'^https?://[^/]+', '', tgt).split('?')[0]
            check(_endpoint_handler(tpath) is not None,
                  f'SearchAction target 有真实处理者: {tpath}')

    # ── 阴性自测 1：编造一个不存在的端点，解析器必须判为无处理者 ──────────────
    check(_endpoint_handler('/api/definitely_not_a_real_endpoint_zzz') is None,
          '阴性自测: 编造的端点被判为无处理者（解析器不会一律放行）')

    # ── 阴性自测 2：catch-all 不得被当成处理者 ────────────────────────────────
    # 若把 [[path]].js 算数，任何 /api/* 都会"解析成功"，闸门恒绿。
    catch_all = os.path.join(ROOT, 'functions', 'api', '[[path]].js')
    check(os.path.isfile(catch_all)
          and _endpoint_handler('/api/some_unimplemented_name') is None,
          '阴性自测: catch-all 存在但不被计为处理者（否则本闸门恒绿）')

    # ── 阳性自测：已知真实存在的三类路由都要能解析（排除恒红）──────────────
    pos = {
        '/api/entities.json': '静态资产',
        '/api/register': '精确函数路由',
        '/api/entity/{id}': '动态段路由',
    }
    for path, kind in pos.items():
        check(_endpoint_handler(path) is not None,
              f'阳性自测: {kind} {path} 可解析到处理者')

    # ── 本轮补的两个端点，锁死其存在与关键行为 ────────────────────────────
    sp = os.path.join(ROOT, 'functions', 'api', 'search.js')
    check(os.path.isfile(sp), 'functions/api/search.js 存在')
    if os.path.isfile(sp):
        src = open(sp, encoding='utf-8').read()
        check('503' in src and 'dataset_unavailable' in src,
              'search 取数失败返回 503 而非空结果（空结果=把故障伪装成"没搜到"）')
        # 付费字段不得进入检索命中域，否则等于绕开付费墙泄露内容
        weights_blk = src.split('FIELD_WEIGHTS')[1].split('];')[0] if 'FIELD_WEIGHTS' in src else ''
        leaked = [f for f in ('price_range', 'compatibility', 'confidence',
                              'source_url', 'domestic_rate')
                  if "'" + f + "'" in weights_blk]
        check(not leaked, f'search 命中域不含付费字段（泄露的: {leaked}）')
        # 必须报「本次查询被扣下的命中数」，而不是「全库隔离总量」——
        # 后者会让调用方以为有一大批相关结果被藏起来（真数字、假印象）。
        check('quarantine_matched_withheld' in src and 'quarantine_in_index' in src,
              'search 区分「本次被扣下的命中」与「索引内隔离总量」（不用总量冒充命中）')

    ep = os.path.join(ROOT, 'functions', 'api', 'entity', '[id].js')
    check(os.path.isfile(ep), 'functions/api/entity/[id].js 存在')
    if os.path.isfile(ep):
        src = open(ep, encoding='utf-8').read()
        check('_lib/paywall.js' in src,
              'entity 端点复用共享付费墙清单（不另抄一份，避免两份清单分叉）')

    # 付费字段清单必须只有一处定义：catch-all 不得再内联自己的一份
    if os.path.isfile(catch_all):
        src = open(catch_all, encoding='utf-8').read()
        check('_lib/paywall.js' in src and 'const PREMIUM_FIELDS = [' not in src,
              'PREMIUM_FIELDS 单一真相源（catch-all 已改为 import，无内联副本）')

    # ── openapi.json 的口径不得腐烂 ─────────────────────────────────────────
    # 【20260808-11】同轮实测：openapi 的 info.description 写着「…共412个实体」，
    # 真值 706（少报 42%），且 llms / flexible_actuators / data_acquisition
    # 三个品类压根没被提到；`/api/entities.json` 又宣称"消耗50积分"，
    # 而网关 CREDIT_COSTS 实际扣 1（虚报 50 倍，对自己不利地劝退接入）。
    # 现已交由 inject_api_access.py 现算重写，这里用**生产函数**做行为对照。
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    try:
        from inject_api_access import _sync_openapi, _openapi_description, \
            _entities_credit_cost  # noqa: E402
        from onboarding_block import json_access as _ja, facts as _f  # noqa: E402
    except Exception as e:  # noqa: BLE001
        check(False, 'inject_api_access 可导入（openapi 口径真相源）: %s' % e)
        return

    oa_path = os.path.join(ROOT, 'api', 'openapi.json')
    oa = json.load(open(oa_path, encoding='utf-8'))
    access = _ja()

    # 现状必须已是最新：对生产同步函数跑一遍，若还有改动说明线上契约是陈旧的
    probe = json.loads(json.dumps(oa))
    check(_sync_openapi(probe, access) is False,
          'api/openapi.json 各项口径均为现算最新值（跑同步函数无改动）')

    # 阳性：描述里的总数必须等于真值，且十个品类一个不落
    fs = _f()
    desc = oa.get('info', {}).get('description', '')
    check(str(fs['total_entities']) in desc,
          f'openapi 描述含真实实体总数 {fs["total_entities"]}')
    missing_cat = [k for k in fs['category_counts'] if f'({fs["category_counts"][k]})' not in desc]
    check(not missing_cat,
          f'openapi 描述覆盖全部品类，无漏报（漏的: {missing_cat}）')

    # 阳性：契约里的扣费口径 == 网关代码实际扣费
    cost = _entities_credit_cost()
    ent_desc = oa.get('paths', {}).get('/api/entities.json', {}).get('get', {}).get('description', '')
    check(f'{cost} 积分' in ent_desc,
          f'openapi 宣称的 entities.json 扣费与代码一致（{cost} 积分）')

    # 阴性自测：拿修复前那份原文回灌，同步函数必须判为"需要改动"
    stale = json.loads(json.dumps(oa))
    stale['info']['description'] = ('仿生机器人零部件结构化数据API。覆盖执行器(147)、'
                                    '传感器(42)、芯片(95)、协议(64)、平台(23)、大模型(27)、'
                                    '接口(14)共412个实体。')
    check(_sync_openapi(stale, access) is True,
          '阴性自测: 修复前的 412 实体描述会被判为需重写（闸门非空转）')

    stale2 = json.loads(json.dumps(oa))
    stale2['paths']['/api/entities.json']['get']['description'] = '……消耗50积分获取完整数据。'
    check(_sync_openapi(stale2, access) is True,
          '阴性自测: 修复前的"50积分"扣费口径会被判为需重写')

    # 阳性自测：描述生成器确实吐出与真值一致的字符串（排除恒红）
    check(str(fs['total_entities']) in _openapi_description(fs),
          '阳性自测: 描述生成器输出含真实总数（生成器本身不空转）')


def layer1_58():
    """日报节流：判定必须现算，且"声称出了日报"必须有落盘物证。

    起因（2026-08-08 自纠）：飞轮看到 `_last_digest.txt` 是昨天、今天已换日，
    就判定"日报过期"，差点写下「已超 24h，本轮已出日报」——实测只过 20.76h。
    用日历差冒充时间差 = 口径≠事实。此闸门把判定收敛到 digest_due.py 一处，
    并锁死"标记更新了但日报没落盘""_LATEST 声称出了日报但标记没动"两种谎报。
    """
    import importlib.util
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz

    print('\n[L1.58] 日报节流判定现算 + 声称与物证对账')

    res_dir = os.path.join(ROOT, 'ops', 'results')
    if not os.path.isdir(res_dir):
        print('  ⏭️  ops/results 不存在（非飞轮环境），跳过')
        return

    dd_path = os.path.join(ROOT, 'scripts', 'digest_due.py')
    check(os.path.exists(dd_path), 'scripts/digest_due.py 存在（日报到期的唯一判定入口）')
    if not os.path.exists(dd_path):
        return

    dd = _load_dd()

    cst = _tz(_td(hours=8))
    r = dd.evaluate()
    check(r.get('ok') is True,
          '_last_digest.txt 可解析且不在未来（实测: %s）' % (r.get('reason') or 'OK'))

    # ---- 阴性自测：判定函数必须真会翻面，不是恒绿 ----
    # 基准 last **必须钉死在用例内部**，不许读真实 _last_digest.txt：
    # 首版只注入 now、基准仍取环境，结果本轮一出日报（标记 → 16:27），三条钉在
    # 8/7 15:22 上的用例集体翻红 —— 被测流程自己会改的状态，不能当测试基准。
    # 同 L1.59 阴性对照假红（拿 git show HEAD 当"修复前原版"），24h 内第二次。
    base = _dt(2026, 8, 7, 15, 22, 49, tzinfo=cst)
    BASE_RAW = '2026-08-07T15:22:49+0800'
    check(dd.evaluate(now=base + _td(hours=25), last_raw=BASE_RAW)['due'] is True,
          '阴性自测: 距上次 25h 必须判"到期"（否则闸门恒说未到期）')
    check(dd.evaluate(now=base + _td(hours=23, minutes=59),
                      last_raw=BASE_RAW)['due'] is False,
          '阴性自测: 距上次 23h59m 必须判"未到期"（不能提前放行）')
    # 这一条正是 12:00 踩的坑：跨了自然日但只过 20.8h
    cross_day = _dt(2026, 8, 8, 12, 10, 0, tzinfo=cst)
    check(dd.evaluate(now=cross_day, last_raw=BASE_RAW)['due'] is False,
          '阴性自测: 跨自然日但仅 20.8h 必须判"未到期"（日期换了≠满24h）')
    # 隔离性自身要有对照：注入基准后，判定不得再随真实标记文件漂移。
    check(dd.evaluate(now=base + _td(hours=25), last_raw=BASE_RAW)['last_raw']
          == BASE_RAW,
          '阴性自测: 注入的基准确实生效（未被真实 _last_digest.txt 覆盖）')
    # ---- 阳性自测：真实状态能算出数值，不是异常吞掉后恒绿 ----
    check(isinstance(r.get('elapsed_hours'), float) or not r.get('ok'),
          '阳性自测: 真实状态能算出已过小时数（判定函数确实跑到了）')

    # ---- 物证 1：标记时间必须有对应的日报文件落盘 ----
    if r.get('ok'):
        last = _dt.fromisoformat(r['last'])
        digests = [f for f in os.listdir(res_dir)
                   if f.startswith('_DAILY_DIGEST-') and f.endswith('.md')]
        want_day = last.strftime('%Y%m%d')
        same_day = [f for f in digests if want_day in f]
        check(bool(same_day),
              '_last_digest.txt 标记的那天确有日报落盘（%s → %s）'
              % (want_day, same_day or '无 —— 更新了标记却没写日报'))

    # ---- 物证 2：_LATEST.md 的日报声明必须与现算一致 ----
    # 注意：这里**不解析散文**。第一版用「'本轮已出' in 正文」判定，结果同一轮里
    # 报告复盘"我差点写下『本轮已出日报』"这句引文时，闸门把引用当成了主张，判了假红。
    # 子串匹配分不清「主张」与「引用主张」——改为读机读标记，散文怎么写都不影响对账。
    # 声明必须带**声明时刻**：`<!-- DIGEST-CLAIM: skipped @2026-08-08T14:13 -->`
    #
    # 20260808-16 修（**又一次同族误伤**）：首版拿"现在"去对账一个**历史声明**。
    # 14 点档运行时距上次日报 22.9h，如实声明 skipped —— 判定完全正确；可等到
    # 16 点档飞轮起手跑回归时已过 25h，闸门便把那句正确的历史声明判成"漏报"。
    # 它惩罚的不是错误行为，而是**时间流逝**：上一轮无论怎么写都躲不过，除非
    # 预知未来。恒红的下场照例是被放宽，于是真漏报也一起放行。
    # 改为：对账基于声明时刻现算（evaluate 支持注入 now）。抓错的能力一点没丢 ——
    # 本轮若到期还写 skipped，声明时刻就是本轮时刻，现算依旧判红。
    # 防"挑一个对自己有利的时刻"：声明时刻必须与最新小时报告同一 (日期,小时)。
    # 【20260810-10】识别器**引用**唯一入口，不再本地另抄一份正则。
    # 原先这里与 digest_due 各持一份语义 —— 正是 L1.69「手抄两份迟早分叉」的老路。
    # 现在静态闸、`--stamp` 产出、`--verify-latest` 自查三处共用同一个对象。
    check(hasattr(dd, 'CLAIM_RE') and hasattr(dd, 'check_claim')
          and hasattr(dd, 'stamp_latest'),
          'digest_due 暴露唯一识别器 CLAIM_RE + 校验 check_claim + 产出 stamp_latest'
          '（识别器只准有一份）')
    CLAIM_RE = dd.CLAIM_RE
    latest_p = os.path.join(res_dir, '_LATEST.md')
    if os.path.exists(latest_p) and r.get('ok'):
        with open(latest_p, encoding='utf-8') as f:
            lt = f.read()
        claims = CLAIM_RE.findall(lt)
        check(len(claims) == 1,
              '_LATEST.md 有且仅有一个带时刻的机读日报声明 '
              '<!-- DIGEST-CLAIM: issued|skipped @YYYY-MM-DDTHH:MM -->'
              '（实测 %d 个 —— 缺失即无法对账，多个即自相矛盾）' % len(claims))
        if len(claims) == 1:
            _verdict, _at_raw = claims[0]
            _at = _dt.fromisoformat(_at_raw).replace(tzinfo=cst)

            # 声明时刻不得在未来，且必须对齐最新小时报告 —— 否则可以靠回填一个
            # "当时还没到期"的旧时刻永久规避（豁免必须锁死取值范围才不是后门）。
            _rep_hours = sorted(
                m.group(1) for m in
                (re.match(r'roboparts-(\d{8}-\d{2})\.md$', f)
                 for f in os.listdir(res_dir)) if m)
            check(_at <= _dt.now(cst) + _td(minutes=5),
                  '日报声明时刻不得在未来（实测 %s —— 未来时刻＝伪造声明窗口）'
                  % _at_raw)
            if _rep_hours:
                _want = _at.strftime('%Y%m%d-%H')
                # 20260808-22 修（「惩罚如实记录」族第 6 次）：原判据是 `==`，
                # 结果 22:05 那次**非整点授权轮**（只覆写 _LATEST、按纪律不产出
                # 整点报告文件）如实声明 @22:05，而最新报告档还是 21 → 判假红。
                # 可作弊方向只有**回填旧时刻**（假装声明时还没到期）；声明比报告
                # **新**恰恰相反 —— 时刻越晚，dd.evaluate 越容易判到期，是自罚不是逃逸。
                # 故只锁下界：声明 >= 最新报告档，上界由上面"不得在未来"卡死，
                # 取值范围仍是闭区间 [最新报告档, 现在]，反回填能力一点没丢。
                check(_want >= _rep_hours[-1],
                      '日报声明时刻不得早于最新小时报告（声明 %s vs 报告 %s —— '
                      '回填旧时刻即可假装"当时还没到期"永久规避）'
                      % (_want, _rep_hours[-1]))

            _r_at = dd.evaluate(now=_at)
            if _verdict == 'issued':
                check(_r_at['elapsed_hours'] <= 3,
                      '声明 issued 时 _last_digest 必须刚更新'
                      '（声明时刻已过 %.2fh —— 声称出了却没更标记＝谎报）'
                      % _r_at['elapsed_hours'])
            else:
                check(_r_at['due'] is False,
                      '声明 skipped 时**该时刻**现算必须未到期'
                      '（实测 due=%s，声明时刻已过 %.2fh —— 到期了还跳过＝漏报）'
                      % (_r_at['due'], _r_at['elapsed_hours']))

        # 阴性自测：正文里**引用**"本轮已出日报"这句话，不得改变判定
        check(len(CLAIM_RE.findall('我差点写下「本轮已出日报」' + lt)) == len(claims),
              '阴性自测: 正文引用"本轮已出日报"不影响判定（散文不参与对账）')
        # 阳性自测：标记本身确实能被解析出来（排除正则写错导致恒绿）
        check(CLAIM_RE.findall('<!-- DIGEST-CLAIM: issued @2026-08-08T16:00 -->')
              == [('issued', '2026-08-08T16:00')],
              '阳性自测: 机读标记正则确实能识别 verdict+时刻（不空转）')
        # 无时刻的旧格式必须**解析不出**，从而触发"有且仅有一个"判红 ——
        # 否则漏写时刻会被静默当成合法，悄悄退回"拿现在对账历史"的老误伤。
        check(CLAIM_RE.findall('<!-- DIGEST-CLAIM: skipped -->') == [],
              '阴性自测: 不带时刻的旧格式声明不被接受（防静默退回按现在对账）')

    # ---- 时间推移不得把"当时正确的判定"判成错（本次误伤的守门人）----
    # 场景复刻：上次日报 8/7 15:22；14:13 那轮距今 22.85h → 如实声明 skipped，正确。
    # 到 16:18 已过 25h。若仍按"现在"对账，那句正确的历史声明会被判漏报 —— 恒红。
    _claim_at = _dt(2026, 8, 8, 14, 13, tzinfo=cst)
    check(dd.evaluate(now=_claim_at, last_raw='2026-08-07T15:22:49+0800')['due']
          is False,
          '阴性自测: 按声明时刻(14:13/22.85h)对账 skipped 判"未到期"（时间流逝≠谎报）')
    # 阳：抓错能力必须完好 —— 真到期了还声明 skipped，按其声明时刻现算照样判红。
    check(dd.evaluate(now=_dt(2026, 8, 8, 16, 0, tzinfo=cst),
                      last_raw='2026-08-07T15:22:49+0800')['due'] is True,
          '阳性自测: 声明时刻本身已到期时仍判"到期"（漏报照抓，不因改口径放水）')

    # ------------------------------------------------------------------
    # 【20260810-10 新增】机械盖章（--stamp）的阴阳对照。
    #
    # 起因：本轮起手回归的唯一红项就是"_LATEST.md 实测 0 个声明"——上一轮正文
    # 如实写了"无日报"，只是漏了那行标记。**靠人记得写的东西等于迟早不写**，
    # 与 L1.76「数字要机械保鲜、不许逐页手改」是同一条道理，只是当时没推广到标记。
    #
    # 但"自动盖章"天然有放水嫌疑，所以这里必须证明它**只消除书写失误、不消除漏报**：
    #   阳 1：无标记的正文盖完出现且仅出现一个，且能通过校验（治得了本轮这个红）
    #   阳 2：连盖两次仍只有一个（幂等，不会每轮净增一行）
    #   阴 1：真到期了想盖 skipped —— 必须拒绝（否则盖章就成了漏报洗白工具）
    #   阴 2：_last_digest 早已陈旧却想盖 issued —— 必须拒绝（谎报照抓）
    #   阴 3：auto 判定比校验窗口更严 —— 上一轮 09:00 出的日报，不许让 10:15 这轮
    #         自称 issued（校验容差 3h 会放行，故生成侧必须自己更严，否则张冠李戴）
    # ------------------------------------------------------------------
    _fresh = '2026-08-10T10:00:00+0800'          # 刚出过日报
    _stale = '2026-08-07T15:22:49+0800'          # 早该出日报了
    _now_s = _dt(2026, 8, 10, 10, 15, tzinfo=cst)
    _body = '# 最新状态\n\n正文若干。\n'

    # 注：stamp_latest 内部调 check_claim 时会读真实 _last_digest.txt，为做**完全
    # 隔离**的对照，这里用可注入基准的底层件（claim_line + CLAIM_RE + check_claim）
    # 复现其全部逻辑，避免测试基准向被测流程自己会改的环境取值 —— L1.58 早年正是
    # 因为基准取自环境，一出日报就把守护日报的自测全部打红。
    def _stamp_iso(text, verdict, now, last_raw):
        line = dd.claim_line(verdict, now=now)
        newt = dd.CLAIM_RE.sub('', text).rstrip() + '\n\n' + line + '\n'
        bad = [m for ok, m in dd.check_claim(newt, now=now, hours=[],
                                             last_raw=last_raw) if not ok]
        return newt, bad

    _t1, _bad1 = _stamp_iso(_body, 'skipped', _now_s, _fresh)
    check(len(dd.CLAIM_RE.findall(_t1)) == 1 and not _bad1,
          '阳性: 无标记正文盖章后恰好一个声明且自洽（异常: %s）' % (_bad1 or '无'))
    _t2, _bad2 = _stamp_iso(_t1, 'skipped', _now_s, _fresh)
    check(len(dd.CLAIM_RE.findall(_t2)) == 1 and not _bad2,
          '阳性: 连盖两次仍只有一个声明（幂等，不每轮净增一行）')

    _t3, _bad3 = _stamp_iso(_body, 'skipped', _now_s, _stale)
    check(bool(_bad3),
          '阴性: 真到期(距今>24h)却盖 skipped 必须被拒（否则盖章＝漏报洗白工具）')
    _t4, _bad4 = _stamp_iso(_body, 'issued', _now_s, _stale)
    check(bool(_bad4),
          '阴性: _last_digest 陈旧却盖 issued 必须被拒（谎报照抓）')

    # auto 生成侧比校验侧更严：距今 1.25h 落在校验容差(3h)内但超出 auto 窗口(0.5h)
    _r_prev = dd.evaluate(now=_now_s, last_raw='2026-08-10T09:00:00+0800')
    check(dd.decide_verdict(now=_now_s, r=_r_prev) == 'skipped',
          '阴性: 上一轮(09:00)出的日报不得让本轮(10:15)自称 issued'
          '（生成侧 %.1fh 窗口须严于校验侧 %.1fh，否则张冠李戴）'
          % (dd.AUTO_ISSUED_H, dd.ISSUED_FRESH_H))
    check(dd.decide_verdict(
        now=_now_s, r=dd.evaluate(now=_now_s, last_raw='2026-08-10T10:05:00+0800')
    ) == 'issued',
          '阳性: 本轮刚更新标记(10分钟前)时 auto 确实判 issued（不空转）')


def layer1_59():
    """【L1.59】整份重写型生成器不得吞掉别人注册的条目与属性。

    2026-08-08 13:00 巡检发现（上一轮被切断的运行留下的现场）：
      跑一次 `build_articles.py` 之后，llms.txt 的「专题速查页」从 10 条塌成 1 条 ——
      转接件生成器 / 3D 预览库 / 推广中心 / 海报 / GEO 仪表盘 / Copilot / Agent 架构 /
      Build Planner / Skills 清单 共 9 个工具页**从 AI 的第一入口里消失了**；
      同一次构建还把 sitemap 里 geo-dashboard 的 changefreq 从 daily 降成 weekly、
      把 promotion(0.7)/海报(0.7)/skills(0.6) 的 priority 一律抬成 0.9、
      并把 8-06/8-07 更新过的页 lastmod **倒退**写回 8-05。

    根因是同一个：本仓有一类"整份重写型"生成器（覆盖 llms.txt 标记块 / sitemap 区段 /
    404.html），它们对"别人注册进来的东西"没有保留义务。sitemap 那侧在 20260805-21
    修过一次（改为保留式合并），但**只回收了 path，属性照样丢**，llms.txt 那侧压根没修。
    这两处退化都**不会让任何闸门变红**——数字对得上、文件存在、格式合法，只是内容少了。

    不变式（全部用生产函数做行为对照，不在测试里另抄一份实现）：
      1. 把带"外来条目"的夹具喂给生产 sync_llms，外来条目必须一条不少地留下来
      2. 把带差异化属性的夹具喂给生产 sync_sitemap，lastmod/changefreq/priority 原样保留
      3. 已有条目的 lastmod 不得倒退（倒退＝对搜索引擎撒谎说"更旧了"）
      4. 阴性：拿 git 里修复前的原版实测，必须精确命中"吞条目/拉平属性"
      5. 幂等：连跑两次逐字节相同（否则挂进 deploy 就是每小时膨胀器）
      6. agent-discovery 的文章数必须有生成者，且与 content/ 真值一致
    """
    print('\n[L1.59] 整份重写型生成器的「保留式合并」对账')
    import importlib.util
    import shutil
    import tempfile

    src = os.path.join(ROOT, 'scripts', 'build_articles.py')

    def load(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    # 夹具：1 条已知速查页 + 3 条「别人注册的」外来条目
    FOREIGN = [
        '- [法兰转接件生成器](https://roboparts.cc/adapter-generator) — 外来条目A',
        '- [GEO/MCP 健康仪表盘](https://roboparts.cc/geo-dashboard) — 外来条目B',
        '- [RoboParts Skills](https://roboparts.cc/skills/manifest.json) — 外来条目C',
    ]
    LLMS_FIXTURE = (
        '# 头部\n\n<!-- ARTICLES:BEGIN -->\n## 技术文库\n索引页：x\n共 0 篇，约 0 字。\n\n'
        '\n### 专题速查页\n'
        '- [ISO 9409-1 机器人法兰速查](https://roboparts.cc/iso-9409-flange) — 已知条目\n'
        + '\n'.join(FOREIGN) + '\n<!-- ARTICLES:END -->\n\n## API\n尾部\n'
    )
    SITEMAP_FIXTURE = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset>\n'
        '  <!-- SEO Articles -->\n'
        '  <url><loc>https://roboparts.cc/geo-dashboard</loc><lastmod>2026-08-07</lastmod>'
        '<changefreq>daily</changefreq><priority>0.75</priority></url>\n'
        '  <url><loc>https://roboparts.cc/promotion</loc><lastmod>2026-08-06</lastmod>'
        '<changefreq>weekly</changefreq><priority>0.7</priority></url>\n'
        '</urlset>\n'
    )
    ORDERED = [{'title': 'T', 'slug': 'demo-slug', 'date': '2026-08-08',
                'desc': 'd', 'words': 100}]

    def run_syncs(mod, workdir):
        """把生成器的 ROOT 指到临时目录，只跑两个同步函数（不生成页面）。"""
        mod.ROOT = workdir
        io_llms = os.path.join(workdir, 'llms.txt')
        io_sm = os.path.join(workdir, 'sitemap.xml')
        with open(io_llms, 'w', encoding='utf-8') as f:
            f.write(LLMS_FIXTURE)
        with open(io_sm, 'w', encoding='utf-8') as f:
            f.write(SITEMAP_FIXTURE)
        mod.sync_llms(ORDERED)
        mod.sync_sitemap(ORDERED)
        return (open(io_llms, encoding='utf-8').read(),
                open(io_sm, encoding='utf-8').read())

    def sitemap_attr(xml, path):
        m = _re59.search(
            r'<loc>https://roboparts\.cc' + _re59.escape(path) +
            r'</loc><lastmod>([^<]*)</lastmod><changefreq>([^<]*)</changefreq>'
            r'<priority>([^<]*)</priority>', xml)
        return m.groups() if m else None

    import re as _re59

    tmp = tempfile.mkdtemp(prefix='rp_l159_')
    try:
        cur = load(src, '_ba_current')
        llms_now, sm_now = run_syncs(cur, tmp)

        kept = [f for f in FOREIGN if f in llms_now]
        check(len(kept) == len(FOREIGN),
              'sync_llms 保留全部外来速查页条目（实测保留 %d/%d，丢失即 AI 入口隐身）'
              % (len(kept), len(FOREIGN)))

        geo = sitemap_attr(sm_now, '/geo-dashboard')
        check(geo == ('2026-08-07', 'daily', '0.75'),
              'sync_sitemap 原样保留差异化属性（geo-dashboard 实测 %s，期望 daily/0.75）' % (geo,))
        promo = sitemap_attr(sm_now, '/promotion')
        check(promo == ('2026-08-06', 'weekly', '0.7'),
              'sync_sitemap 不把 priority 拉平（promotion 实测 %s，期望 0.7）' % (promo,))
        check(geo and geo[0] == '2026-08-07',
              'lastmod 不得倒退（8-07 的页不能被写回更早日期）')

        # 幂等：同一份产物再跑一遍必须逐字节相同
        cur.ROOT = tmp
        cur.sync_llms(ORDERED)
        cur.sync_sitemap(ORDERED)
        llms_2 = open(os.path.join(tmp, 'llms.txt'), encoding='utf-8').read()
        sm_2 = open(os.path.join(tmp, 'sitemap.xml'), encoding='utf-8').read()
        check(llms_2 == llms_now and sm_2 == sm_now,
              '连跑两次逐字节相同（非幂等的生成器挂进 deploy＝每小时膨胀器）')

        # ---- 阴性对照：拿 git 里修复前的原版实测，必须真的判红 ----
        # 注意：必须钉死「修复提交 ee0761f 的前一版 822296c」，不能用 HEAD——修复已随
        # ee0761f 提交进 HEAD，HEAD 现在是修复版，阴性对照会永远复现不出 bug（假红）。
        # 若重写 git 历史导致 822296c 消失，下面 check(False) 会大声报错而非静默通过。
        old_src = os.path.join(tmp, 'old_build_articles.py')
        # 20260810-18：filter-repo 重写历史后 822296c 已不在对象库，先过重写台账
        # 解析回当前哈希。上面那条注释说的"会大声报错"确实兑现了（本轮真判红），
        # 但正确的收尾是**让阴性对照继续跑得起来**，而不是把它删掉了事。
        _old_sha = _hh.to_current(ROOT, '822296c', [ROOT]) or '822296c'
        r = subprocess.run(['git', 'show', '%s:scripts/build_articles.py' % _old_sha],
                           cwd=ROOT, capture_output=True)
        if r.returncode == 0 and r.stdout:
            with open(old_src, 'wb') as f:
                f.write(r.stdout)
            tmp2 = tempfile.mkdtemp(prefix='rp_l159_old_')
            try:
                old = load(old_src, '_ba_head')
                llms_old, sm_old = run_syncs(old, tmp2)
                lost = [f for f in FOREIGN if f not in llms_old]
                check(len(lost) == len(FOREIGN),
                      '阴性自测: 修复前原版确实吞掉全部外来速查页条目（实测吞掉 %d/%d '
                      '—— 吞不掉说明本闸门在空转）' % (len(lost), len(FOREIGN)))
                geo_old = sitemap_attr(sm_old, '/geo-dashboard')
                check(geo_old is not None and geo_old != ('2026-08-07', 'daily', '0.75'),
                      '阴性自测: 修复前原版确实把 geo-dashboard 属性拉平（实测 %s）' % (geo_old,))
            finally:
                shutil.rmtree(tmp2, ignore_errors=True)
        else:
            check(False, '可从 git 取到修复前原版做阴性对照（git show 失败）')
    except Exception as e:
        check(False, 'L1.59 行为对照可真跑（异常: %s）' % e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- agent-discovery 的文章数必须有生成者，而不是靠人记得改 ----
    ba_src = read_text(src)
    check('def sync_agent_discovery' in ba_src and 'sync_agent_discovery(ordered)' in ba_src,
          'agent-discovery 的文章清单有生成者并被 build() 调用（手工维护＝漂移源）')
    try:
        n_md = len(glob.glob(os.path.join(ROOT, 'content', 'article-*.md')))
        ad = json.loads(read_text(os.path.join(ROOT, 'agent-discovery.json')))
        cl = ad.get('content_library', {})
        check(cl.get('count') == n_md == len(cl.get('articles') or []),
              'agent-discovery 文章数 == content/ 真值 == 条目数（实测 %s/%s/%s）'
              % (cl.get('count'), n_md, len(cl.get('articles') or [])))
    except Exception as e:
        check(False, 'agent-discovery 文章数可对账（异常: %s）' % e)


def layer1_60():
    """【L1.60】提交清单守卫：不许把"不知道从哪来的改动"顺手带上车。

    起因是 2026-08-08 16:18 那轮的真实事故：`git add -A scripts/` 把本轮从未编辑过的
    `scripts/promote.mjs` 一起提交了，而起手 git status 是 0 改动 —— 来源至今未明。
    内容碰巧正确，但「不知道自己提交了什么」本身就是缺陷：下次那些行如果是坏的，
    同样会无声上线。当时的结论是"下轮把这条做成闸门"，这就是那条闸门。

    本闸门校验的是**守卫逻辑没有退化**（守卫真正生效的时机在提交前手动调用），
    重点盯三件容易被自己悄悄放松的事：
      1. 未声明的文件必须判红（否则守卫等于摆设）；
      2. `scripts/` 这类代码目录的通配必须被拒 —— 一条 `scripts/*` 就能罩住事故文件，
         留着它等于给自己开后门；
      3. 判定必须是纯函数、基准钉死在用例内，不许向环境取值（L1.58/L1.59 各栽过一次）。
    """
    print('\n[L1.60] 提交清单守卫（未声明的改动不许上车）')
    guard_path = os.path.join(ROOT, 'scripts', 'staged_guard.py')
    if not os.path.exists(guard_path):
        check(False, 'scripts/staged_guard.py 存在（提交清单守卫已落地）')
        return
    check(True, 'scripts/staged_guard.py 存在（提交清单守卫已落地）')
    try:
        import importlib
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        sg = importlib.import_module('staged_guard')
        importlib.reload(sg)
    except Exception as e:
        check(False, 'staged_guard 可导入（异常: %s）' % e)
        return

    # 守卫自己的阴阳对照，直接并入本次回归计数
    try:
        sg.selftest(check=check)
    except Exception as e:
        check(False, 'staged_guard 自测可真跑（异常: %s）' % e)

    # 防静默削弱：代码目录清单不许被删空
    code_dirs = getattr(sg, 'CODE_DIRS', ())
    check('scripts/' in code_dirs and 'functions/' in code_dirs,
          '代码目录禁通配清单仍含 scripts/ 与 functions/（实测 %s）' % (code_dirs,))

    # CLI 三个入口都在（--begin 记起点 / --intent 声明 / --selftest 自检）
    src = read_text(guard_path)
    check("'--begin'" in src and "'--intent'" in src and "'--selftest'" in src,
          'CLI 保留 --begin/--intent/--selftest 三入口（少一个流程就断）')


_L161_MARKER = re.compile(r'RoboParts|本站|本平台|数据集|实体库|数据规模')

# 种类口径名词 → onboarding_block.facts() 里的键。
#
# 为什么单列一张表（2026-08-09 06:xx 的真实事故）：
#     L1.68 那轮新增了 component/specification/software/organization/market_intelligence
#     五档口径，页面与 Schema.org 从此开始写「507 条实物零部件、94 条…规范、79 条…软件」。
#     但**没有任何一处名词表跟着加**——于是：
#       · L1.61（源头闸）不认得「零部件」，写死的字面量不判红；
#       · L1.62（线上核验）`_NOUN2KEY` 里也没有，取到数字后 `key is None` → 静默 continue，
#         然后照样打印「✅ 17 页均与真相源一致（0 项未核验）」。
#     结果：整轮改动**一行都没部署**，线上 Schema.org 仍对外播「694 条零部件」这句
#     上一轮亲口认定为不诚实的话，而两道闸门全绿。
#
# 教训不是"这次忘了加名词"，是**新增对外口径不会让任何闸门失败**。
# 所以下面配套 L1.69：facts() 里每个 `*_entities` 键都必须在本表中至少有一个名词，
# 少一个就判红——让"加了新口径却没接进核验"在源头就撞墙，而不是等线上播错话。
_KIND_NOUNS = {
    '实物零部件': 'component_entities', '零部件': 'component_entities',
    '接口/协议规范': 'specification_entities', '协议规范': 'specification_entities',
    '规范': 'specification_entities',
    'AI 模型与软件': 'software_entities', 'AI模型与软件': 'software_entities',
    '软件': 'software_entities',
    '企业主体': 'organization_entities',
    '市场情报': 'market_intelligence_entities',
}
# 长名词必须排在短名词前，否则「实物零部件」会被「零部件」先吃掉一半
_KIND_ALT = '|'.join(sorted((re.escape(n) for n in _KIND_NOUNS), key=len, reverse=True))

_L161_COUNT = re.compile(
    r'(?<![\d{])\d{2,4}\s*(?:款|条|个)\s*'
    r'(?:实体|条目|执行器|芯片|传感器|通信协议|协议|机器人AI模型|robot_ai_models)'
    r'|(?<![\d{])\d{1,3}\s*大(?:分类|品类)'
    # 种类口径的数值可以小到个位（企业主体 9 条），不能沿用 \d{2,4}
    r'|(?<![\d{])\d{1,4}\s*(?:款|条|个)\s*(?:' + _KIND_ALT + r')')
_L161_BULLET = re.compile(
    r'^\s*-\s*(?:\*\*)?(?:执行器|传感器|芯片|协议|通信协议|机器人AI模型|robot_ai_models|'
    r'传感器总数|实体|条目|协议库|芯片库|执行器库|传感器库)(?:\*\*)?\s*[:：]\s*\d{2,4}\s*(?:款|条|个)')


def l161_violations(lines):
    """纯函数：给定 content/*.md 的行，返回把数据集规模写死成字面量的行号。

    判定只看传入的行，不读文件、不取环境值（L1.58/L1.59 都栽在向环境取基准）。
    R1 自述句：同一行既有自我指称（RoboParts/数据集/…），又有「裸数字+品类名」；
    R2 品类清单项：`- **执行器**：155条` 这种自家品类定义式，无需自我指称词。
    占位符 `{{RP:...}}` 前面是 `{`，被 (?<![\\d{]) 排除，天然放行。
    """
    bad = []
    for i, line in enumerate(lines, 1):
        if _L161_BULLET.search(line):
            bad.append((i, line.strip()))
        elif _L161_MARKER.search(line) and _L161_COUNT.search(line):
            bad.append((i, line.strip()))
    return bad


def layer1_61():
    """【L1.61】文章正文的数据集规模不得写死 —— 数字只能有一个来源。

    2026-08-08 18:50 查出的存量事故：14 篇已上线长文把规模写成字面量，且早已过期又互相
    矛盾 —— article-01/02 写「427 个实体」、article-06/08/12/14 写「493 个实体」，
    真值 706；执行器写 155（真 217）、芯片写 95 与 103 两种（真 108）、
    传感器 62（真 90）、机器人AI模型 17 与 21 两种（真 44）。
    对外**低报三到六成、且自己打自己**，搜索引擎与 AI 检索读到的就是"这站小且口径不可信"，
    与当初 ros-discourse-post.md 的事故完全同类。根因不是"写错数字"，是**数字有第二个来源**。
    修法：正文只写 {{RP:...}} 占位符，构建时从 onboarding_block.facts() 现取。
    本闸门锁死三件事：占位符机制还在、正文没有字面量回流、注入器失败不再被吞。
    """
    print('\n[L1.61] 文章正文规模数字只认真相源（禁字面量回流）')
    ba = os.path.join(ROOT, 'scripts', 'build_articles.py')
    src = io.open(ba, encoding='utf-8').read() if os.path.exists(ba) else ''
    check('def render_tokens(' in src and 'render_tokens(io.open(' in src,
          'build_articles.py 仍在构建时渲染占位符（机制未被摘掉）')
    check('return p.returncode' in src,
          '注入器返回码被校验（check=False 吞异常会让文章缺接入区块还报成功）')

    pos = [
        '本文基于 RoboParts 数据集收录的 **155 款执行器**实测参数，给出选型方法论。',
        'RoboParts数据集覆盖10大分类、493个实体条目，含155款执行器、103款芯片。',
        'RoboParts平台已收录493个实体、覆盖10大品类，为IPO供应链追踪提供数据基础设施：',
        '- **执行器**：155条，含产线级旋转/线性执行器',
        '- 芯片库：95 个条目，按接口类型分类',
    ]
    for s in pos:
        check(bool(l161_violations([s])), '阳性: 判红「%s」' % s[:28])

    neg = [
        ('单台机器人配备28-45个关节模组，仅此一项成本1万元以上', '别人的机器人关节数不是我方口径'),
        ('国内人形机器人整机企业已超过140家，发布产品超过330款。', '行业统计数字不是我方口径'),
        ('本文基于 RoboParts 数据集收录的 **{{RP:CAT:actuators}} 款执行器**实测参数。', '占位符写法'),
        ('- **执行器**：{{RP:CAT:actuators}} 条，含产线级旋转/线性执行器', '占位符清单项'),
        ('RoboParts 数据集以 CC BY 4.0 许可开放，欢迎引用。', '无数字不判红'),
        ('各省级地区选取重点场景单元不少于20个，央企不少于10个', '政策原文数字不判红'),
    ]
    for s, why in neg:
        check(not l161_violations([s]), '阴性: 放行（%s）' % why)

    probe = ['RoboParts 数据集收录 155 款执行器']
    check(l161_violations(probe) == l161_violations(list(probe)),
          '隔离性: 同输入同结论（不向环境取值）')

    left = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'content', '*.md'))):
        v = l161_violations(io.open(f, encoding='utf-8').read().split('\n'))
        if v:
            left.append('%s:L%s' % (os.path.basename(f), v[0][0]))
    check(not left, 'content/*.md 无写死的规模数字（残留: %s）' % (left[:4] or '无'))

    leak = [os.path.basename(p) for p in glob.glob(os.path.join(ROOT, 'articles', '*.html'))
            if '{{RP' in io.open(p, encoding='utf-8').read()]
    check(not leak, 'articles/*.html 无未渲染占位符泄漏（泄漏: %s）' % (leak[:4] or '无'))


def layer1_62():
    """【L1.62】"线上究竟写了什么"必须有人看 —— 本地绿 + 200 不等于已交付。

    2026-08-08 19:58 事故（「口径 ≠ 事实」第 10 次）：
      上一轮把 14 篇长文的过期规模数字占位符化，回归全绿（含刚加的 L1.61）、
      探活 19/19、推 GitHub 且 tree SHA 自校验一致，报告写"本次修复"。
      **线上一个字都没变。** 实测 11/17 页仍在对外展示
      `493个实体 / 155款执行器 / 103款芯片 / 62条传感器 / 7大品类`（真值 706/217/108/90/10）。
      根因：Pages 并未接 GitHub 自动构建，本机无 CLOUDFLARE_API_TOKEN 跑不了 deploy.mjs，
      而"推了 GitHub ＝ 会自动上线"是个**从未被验证过的假设**，还被当成结论写进了报告。

      更要命的是两道绿灯合起来仍放过了它：regression 只读本地文件（本地对了就绿），
      probe 只看 HTTP 状态码（返回 200 就绿，正文数字全错也绿）。**没人在看线上正文。**

    本闸门锁死补位脚本 verify_live_numbers.py 的**判定行为**（不是它跑没跑）：
      口径边界必须复用 L1.61 正则（不许另造第二套"什么算我方数字"），
      期望值必须由调用方注入（L1.58/L1.59 都栽在判定函数偷偷向环境取基准），
      HTML→文本 这唯一的自有逻辑不能把同行上下文冲散（一冲散就整体假绿）。
    """
    print('\n[L1.62] 线上对外数字核验（本地绿≠已交付）')
    p = os.path.join(ROOT, 'scripts', 'verify_live_numbers.py')
    check(os.path.exists(p), 'verify_live_numbers.py 存在（线上核验入口没被摘掉）')
    if not os.path.exists(p):
        return
    src = io.open(p, encoding='utf-8').read()
    # 断言的是**性质**（从 regression 取 L1.61 口径、自己不另立一套），不是某一种写法。
    # 原先写死字面量 'from regression import _L161_'，一改成括号跨行导入就假红 ——
    # 断言绑在格式上，等于每次合理重构都要先安抚闸门，久了就会有人把闸门删掉。
    imports_l161 = re.search(r'from\s+regression\s+import\s+\(?[^)]*_L161_', src, re.S)
    redefines = re.search(r'^_L161_(?:COUNT|MARKER|BULLET)\s*=', src, re.M)
    check(bool(imports_l161) and not redefines,
          '口径边界复用 L1.61 正则（禁另造第二套"什么算我方数字"）')
    check('X-RoboParts-Selftest' in src, '带隔离头（不污染真实遥测）')

    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import verify_live_numbers as V

    EXP = {'TOTAL': 706, 'CATEGORIES': 10, 'actuators': 217, 'chips': 108, 'sensors': 90}
    # 阳性样本全部取自当日线上真实抓取，不是编的
    pos = [
        ('<p>RoboParts 数据集收录 <strong>155 款执行器</strong></p>', '行内标签包裹的过期数字'),
        ('<div>RoboParts数据集覆盖10大分类、493个实体条目，含103款芯片。</div>', '整句多处过期'),
        ('<li>- **执行器**：155条</li>', '品类清单项'),
    ]
    for html, why in pos:
        check(bool(V.live_violations([('t', html)], EXP)), '阳性: 判红（%s）' % why)

    neg = [
        ('<p>RoboParts 数据集收录 <strong>706 个实体</strong></p>', '渲染正确的真值不判红'),
        ('<p>单台机器人配备28-45个关节模组</p>', '别人的机器人数字不是我方口径'),
        ('<script>var a={entities:493};</script><p>RoboParts 数据集正文无数字</p>', 'script 内是代码'),
        ('<p>RoboParts 数据集收录 999 条法规</p>', '未知名词放行（宁漏勿假红）'),
    ]
    for html, why in neg:
        check(not V.live_violations([('t', html)], EXP), '阴性: 放行（%s）' % why)

    one = '<p>RoboParts 数据集收录 155 款执行器</p>'
    check(not V.live_violations([('t', one)], {'actuators': 155}),
          '基准由调用方注入：期望改成 155 则同句放行（证明判定不偷读真相源）')
    check(V.live_violations([('t', one)], EXP) == V.live_violations([('t', one)], dict(EXP)),
          '隔离性: 同输入同结论（不向环境取值）')
    check(any('收录 155 款执行器' in x for x in V.html_to_lines('<p>收录 <b>155</b> 款执行器</p>')),
          'HTML→文本: 行内标签抹除后同行上下文保留（冲散即整体假绿）')
    check(not any('493' in x for x in V.html_to_lines('<script>var a=493;</script><p>x</p>')),
          'HTML→文本: script 整体剜除')

    # 三态结论：本轮亲手造过一次假绿 —— 17 页里 16 页压根没抓到，
    # 只因唯一抓到那页没问题就打印「✅ 线上数字一致」。会撒谎的闸门比没闸门更坏：
    # 下一轮的我会拿这个绿灯当"线上已验证"。"没核验"必须是独立第三态。
    check(V.verdict(1, 16, 0)[1] == 'UNKNOWN', '三态: 漏抓 16 页 → UNKNOWN，不许坍缩成绿')
    check(V.verdict(1, 16, 0)[0] != 0, '三态: UNKNOWN 退出码非 0（调用方不会误读为成功）')
    check(V.verdict(17, 0, 0) == (0, 'GREEN'), '三态: 全抓到且无失配才是 GREEN')
    check(V.verdict(3, 5, 2)[1] == 'RED', '三态: 红优先于未核验（别被"没抓全"洗白）')
    check(V.verdict(0, 0, 0)[1] == 'UNKNOWN', '三态: 一页没抓到 → UNKNOWN（空集不算通过）')


def _data_embedded_refs(doc):
    """递归取出数据里所有"站内路径"字符串值，返回 {路径: 出现次数}。

    只认以 `/` 开头的**值**（不认键名、不认外链 http），因为它们是数据在对调用方
    做出的路径承诺 —— agent 拿到 `registry_ref` 就会直接去敲。
    """
    refs = {}

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str) and o.startswith('/') and not o.startswith('//'):
            refs[o] = refs.get(o, 0) + 1

    walk(doc)
    return refs


def layer1_63():
    """L1.63 · **数据内嵌**的站内路径必须真的敲得开（补 L1.57 只管文档的盲区）

    【20260808-21 起因】`api/entities.json` 里每条实体的机械接口"诚实缺口"包装都写着
    `registry_ref: /api/mechanical_interfaces.json`，全库共 **707 处**。本轮手工回探
    确认它线上 200、内容正常 —— 但随即发现**没有任何东西在自动看它**：

      - `probe.mjs` 的固定巡检清单里没有它（grep 命中 0）；
      - `regression.py` 从未校验过 `registry_ref`（grep 命中 0）；
      - `L1.57` 只对账 `llms.txt / README.md / openapi.json` 三份**文档**声明，
        而这条路径压根不在文档里，它藏在**数据值**里。

    也就是说：这份注册表一旦改名或挪走，707 条记录会一起指向 404，三道闸门全绿放行。
    这与 `/api/search`、`/api/entity/{id}` 长期 404 是同一族（"口径 ≠ 事实"），
    只不过上一次口径写在文档里、这一次写在数据里。

    刻意复用 L1.57 的 `_endpoint_handler` 而不另造判定：同一个问题只能有一套标准，
    两套迟早互相打架（L1.62 当时也是复用 L1.61 的正则，不另起炉灶）。
    """
    print('\n[L1.63] 数据内嵌的站内路径必须真的敲得开')

    sources = ('api/entities.json', 'api/oss_components.json', 'agent-discovery.json')
    all_refs = {}
    scanned = []
    for rel in sources:
        fp = os.path.join(ROOT, rel)
        if not os.path.isfile(fp):
            continue
        scanned.append(rel)
        for path, n in _data_embedded_refs(json.load(open(fp, encoding='utf-8'))).items():
            all_refs.setdefault(path, {'count': 0, 'src': rel})
            all_refs[path]['count'] += n

    # 解析器空转防线：一条都没扫到时，下面的"无断链"会假绿。
    check(scanned and all_refs,
          '已从数据文件中解析出站内路径引用 %d 条（来源: %s；解析器没空转）'
          % (len(all_refs), ','.join(scanned) or '无'))

    broken = ['%s ×%d (来自 %s)' % (p, v['count'], v['src'])
              for p, v in sorted(all_refs.items())
              if _endpoint_handler(p) is None]
    check(not broken,
          '每条数据内嵌路径都能在仓库中找到承接者（断链: %s）' % (broken or '无'))

    # ── 阳性对照：编造的路径必须判红，否则本闸门恒绿 ──────────────────────
    _fake = {'meta': {'registry_ref': '/api/definitely_not_a_real_registry_zzz.json'}}
    _fake_refs = _data_embedded_refs(_fake)
    check(list(_fake_refs) == ['/api/definitely_not_a_real_registry_zzz.json'],
          '阳性对照: 提取器能从嵌套数据里取出路径值')
    check(_endpoint_handler('/api/definitely_not_a_real_registry_zzz.json') is None,
          '阳性对照: 编造的数据内嵌路径被判为无承接者')

    # catch-all 同样不得洗白（与 L1.57 同一条纪律）
    check(_endpoint_handler('/api/some_unimplemented_registry_name') is None,
          '阳性对照: catch-all 不把未实现的数据内嵌路径算成有承接者')

    # ── 阴性对照：真实存在的引用不得误伤 ──────────────────────────────────
    check(_endpoint_handler('/api/mechanical_interfaces.json') is not None,
          '阴性对照: 真实存在的 registry_ref 不判红')
    check(not _data_embedded_refs({'a': 'https://example.com/x', 'b': 'plain', 'c': 123}),
          '阴性对照: 外链/普通字符串/数字不被误当成站内路径')
    check(list(_data_embedded_refs({'/api/x': 'v'})) == [],
          '阴性对照: 只认值不认键名（键名不是对外承诺）')

    # 隔离性：判定为纯函数，同输入同结论
    check(_data_embedded_refs(_fake) == _fake_refs,
          '隔离性: 同输入同结论（不向环境取值）')


def layer1_64():
    """机械兼容判定只认接口身份键（分类描述不得当成"能装上"的证据）。

    【20260809-02 · "口径 ≠ 事实" 第 11 次】
    L1.23 把兼容三态的**假红**一侧锁死了（无数据 ≠ 不兼容），但同一维度的
    **假绿**一侧留了个口子：`mechanicalEvidence` 曾把 mount_type 与
    standard/flange 并列当作可比对特征。

    mount_type 是"怎么装"的分类描述（direct_mount / flange_mount / shaft_mount…），
    standard/flange 才是"装在什么接口上"的身份键（编码节圆/孔数/螺纹）。
    两件东西同为 direct_mount，只说明各自都不需要转接件，**完全不蕴含彼此孔位能对上**。

    实测现场：宇立 C025XX × C075XX 两个六维力传感器，双方 standard/flange 均为 null、
    仅 mount_type=direct_mount → 引擎输出 `compatible:true / 共享机械接口: direct_mount`，
    并作为**硬约束**把 overall 撑成 true。而这两条记录自己的 gap 字段白纸黑字写着
    「缺法兰节圆/孔数/螺纹规格，无法做孔位级互换判定」——
    **数据层诚实声明了判不了，引擎把它渲染成了肯定结论。**

    为什么必须现在修、而不是等补完数据再说（本闸门的真正理由）：
      全库 248865 个配对里今天只有 1 例假绿 —— 纯属侥幸，因为 366 条的 mount_type
      恰好都还是 'unknown' 被过滤掉了。而 mount_type 是所有字段里**最好填**的一个
      （看一眼产品页就能写），flange/standard 却要翻 datasheet。
      "补 declared 机械数据"是当前排第一的自有待办，它必然优先产出一大批
      "有 mount_type、无法兰规格"的记录。实测反事实：**仅把 100 条的 mount_type
      由 unknown 填成 flange_mount，假绿即由 1 暴涨到 4951**。
      即：这是一颗定时引爆于"我们开始干正事那一刻"的雷。先拆雷，再补数据。

    判据刻意锚在**字段有没有值**上，不锚 status 标签（partial/declared）：
    标签是人工口径、会写错；字段有没有值是行为事实。故 status=partial 但
    给了真法兰标准的记录仍允许比对 —— 不得矫枉过正制造新的假红（L1.23 反噬）。
    """
    print('\n[L1.64] 机械兼容只认接口身份键（分类描述 ≠ 能装上）')
    import re as _re

    engf = os.path.join(ROOT, 'functions', '_lib', 'compat_engine.js')
    if not os.path.isfile(engf):
        check(False, 'functions/_lib/compat_engine.js 存在')
        return
    src = read_text(engf)
    code = _re.sub(r'/\*[\s\S]*?\*/', '', src)
    code = _re.sub(r'(?m)^\s*//.*$', '', code)

    # ① 源码层：mount_type 不得出现在身份键数组里（根因写法）
    me = code[code.find('export function mechanicalEvidence'):]
    me = me[:me.find('\n}') + 2] if '\n}' in me else me
    check('mount_type' not in (me[:me.find('idKeys')] if 'idKeys' in me else me),
          '身份键取值不含 mount_type（旧写法 [standard, flange, mount_type] 是假绿根因）')
    check(_re.search(r'MECH_IDENTITY_FIELDS\s*=\s*\[\s*[\'"]standard[\'"]\s*,\s*[\'"]flange[\'"]\s*\]', code)
          is not None,
          '身份键集合显式声明为 standard/flange 两项（集中定义，不散落）')

    # ② 行为层：拿生产源码 + 真实数据实跑。源码正则只能证明"写法变了"，
    #    证明不了"结论变了"—— 判据必须落在输出上（L1.31/L1.44 同款）。
    node = shutil.which('node') or 'node'
    probe = (
        "import {evalDimension as ev} from './functions/_lib/compat_engine.js';"
        "import fs from 'fs';"
        "const E=JSON.parse(fs.readFileSync('api/entities.json','utf-8')).entities;"
        "const mk=(i,m)=>({id:i,name:i,mechanical_interface:m});"
        "const iso={status:'declared',standard:'ISO 9409-1-50-4-M6',mount_type:'flange_mount'};"
        # 【20260810】假绿的定义必须是「没有身份键交集却判 true」，不能是「判 true」。
        # 原写法 tt = 所有 compatible===true 的对数，并断言 tt==0 —— 那个不变式
        # 只在"机械维度一条真实声明都没有"时才成立。补进第二条有出处的孔位集合
        # （SENS-31）立刻让它变红：闸门于是从"防假绿"退化成"禁止本维度有数据"，
        # 与 add_mechanical_interface.py 曾经删数据同型。改为只数**无出处支撑**的 true。
        "const idv=v=>Array.isArray(v)?v.map(x=>String(x==null?'':x).trim().toLowerCase())"
        ".filter(Boolean):(v?[String(v).trim().toLowerCase()]:[]);"
        "const idset=e=>{const m=(e&&e.mechanical_interface)||{};"
        "return new Set([...idv(m.standard),...idv(m.flange)]);};"
        "const backed=(x,y)=>{const A=idset(x),B=idset(y);"
        "for(const t of A){if(B.has(t))return true;}return false;};"
        # 阳性①：现库真实的那一对，必须由 true 变 null
        "const a=E.find(e=>e.id==='SENS-ft-sri-c025xx'),b=E.find(e=>e.id==='SENS-ft-sri-c075xx');"
        "const p1=(a&&b)?ev('mechanical',a,b).compatible===null:false;"
        # 计数谓词自测：mount_type-only 一对必须算「无支撑」，真孔位一对必须算「有支撑」
        "const bs1=backed(mk('X',{status:'partial',mount_type:'flange_mount'}),"
        "mk('Y',{status:'partial',mount_type:'flange_mount'}))===false;"
        "const bs2=backed(mk('X',iso),mk('Y',{...iso}))===true;"
        # 阳性②：全库扫描不得有任何**无身份键交集**却判 true 的对（真正的假绿）
        "let tt=0,tb=0;for(let i=0;i<E.length;i++)for(let j=i+1;j<E.length;j++){"
        "if(ev('mechanical',E[i],E[j]).compatible===true){"
        "if(backed(E[i],E[j]))tb++;else tt++;}}"
        # 阳性③：反事实 —— 补数据活动的真实形态，填 100 条 mount_type
        "const C=JSON.parse(JSON.stringify(E));let f=0;"
        "for(const e of C){const m=e.mechanical_interface;"
        "if(m&&m.status==='not_declared'&&f<100){m.status='partial';m.mount_type='flange_mount';f++;}}"
        "let t2=0;for(let i=0;i<C.length;i++)for(let j=i+1;j<C.length;j++){"
        "if(ev('mechanical',C[i],C[j]).compatible===true&&!backed(C[i],C[j]))t2++;}"
        # 阴性①：真身份键相同仍判 true（不得矫枉过正成失能）
        "const n1=ev('mechanical',mk('X',iso),mk('Y',{...iso})).compatible===true;"
        # 阴性②：真身份键不同仍判 false（仍有判伪能力）
        "const n2=ev('mechanical',mk('X',iso),"
        "mk('Y',{status:'declared',standard:'ISO 9409-1-31.5-4-M5'})).compatible===false;"
        # 阴性③：锚字段不锚标签 —— partial 但有真法兰，仍可比对
        "const n3=ev('mechanical',mk('X',{status:'partial',flange:'ISO 9409-1-50-4-M6'}),"
        "mk('Y',{status:'partial',flange:'ISO 9409-1-50-4-M6'})).compatible===true;"
        # 说明文案：必须点出缺的是哪一格，不得含糊成"未声明"
        "const nt=ev('mechanical',mk('X',{status:'partial',mount_type:'direct_mount'}),"
        "mk('Y',{status:'partial',mount_type:'direct_mount'})).notes||'';"
        "const n4=/仅声明安装方式/.test(nt)&&/法兰/.test(nt);"
        "console.log(JSON.stringify({p1,tt,tb,t2,n1,n2,n3,n4,bs1,bs2}));"
    )
    try:
        r = subprocess.run([node, '--input-type=module', '-e', probe], cwd=ROOT,
                           capture_output=True, encoding='utf-8',
                           errors='replace', timeout=120)
        out = (r.stdout or '').strip().splitlines()
        d = json.loads(out[-1]) if out else {}
    except Exception as e:
        check(False, 'L1.64 行为探针可执行（异常: %s）' % str(e)[:120])
        return

    check(d.get('p1') is True,
          '阳性对照: 仅共享 mount_type 的真实配对（宇立 C025XX × C075XX）判为 null，'
          '不再输出「共享机械接口: direct_mount」')
    check(d.get('tt') == 0,
          '阳性对照: 全库 248865 配对中 mount_type 撑起的假绿为 0（修复前 1，实得 %s）'
          % d.get('tt'))
    check(d.get('t2') == 0,
          '反事实对照: 补 100 条 mount_type 后假绿仍为 0（修复前 4951，实得 %s）—— '
          '这条才是本闸门的意义：雷在补数据那一刻才引爆' % d.get('t2'))
    check(d.get('n1') is True,
          '阴性对照: 双方同法兰标准仍判 true（没把引擎修成失能）')
    check(d.get('n2') is True,
          '阴性对照: 双方异法兰标准仍判 false（判伪能力保留）')
    check(d.get('n3') is True,
          '阴性对照: status=partial 但有真法兰仍可比对（锚字段不锚标签）')
    check(d.get('n4') is True,
          '说明文案据实指出缺口在法兰/标准规格，不含糊成「未声明」'
          '（对方确实给了东西，说成未声明是记错账）')


def layer1_65():
    """L1.65 —— 公司不是零件：非 component 条目不得冒充零部件。

    【20260809-03 · 类型错误被渲染成数据缺口】
    entity_kind 原本只有 component / market_intelligence 两档，于是
    「Figure AI」「特斯拉」「波士顿动力」这 9 条 type=人形机器人公司 的
    **企业主体条目**只能落进 component。三处对外后果：

      1. /mcp 实况文案实时算出「703 条为可选型零部件」—— 其中 9 条是公司；
      2. 接入区块与 Schema.org 写「706 个零部件实体」—— 同样把公司算成零件；
      3. 兼容性引擎接受公司当操作数，输出
         「Figure AI 未声明通信协议，无法判定（无数据 ≠ 不兼容）」。
         overall 确实是 null，所以永远不报错 —— 但这句话把**类型错误**
         说成了**数据缺口**，等于告诉用户"这家公司只是参数没填，补上就能判"。
         公司没有法兰，永远补不上。正确回答是：它不构成可判定对象。

    与 L1.64 是同一族缺陷的两侧：L1.64 管"用错字段下结论"，
    本闸门管"用错**对象**下结论"。两者都不产生报错，只产生看起来很正常的错话。

    附带效果：机械覆盖率分母由 368 降到 356（12 条非零件退出），
    fill_pct 0.54% → 0.56% —— 分母诚实了，指标反而变好，这正说明原分母是脏的。
    """
    print('\n[L1.65] 公司不是零件：非 component 条目不得进选型/兼容判定')
    import re as _re

    ents = load_entities()
    items = ents.get('entities') or []

    # ① 数据层：企业主体必须被识别出来，且带 kind_basis 说明理由
    orgs = [e for e in items if e.get('entity_kind') == 'organization']
    check(len(orgs) > 0, '库内已识别出 organization 条目（实得 %d 条）' % len(orgs))
    check(all(e.get('kind_basis') for e in orgs),
          'organization 条目均带 kind_basis（为什么判成企业主体，可追溯）')
    # 反向：不得再有 type 以"公司"结尾却仍标 component 的漏网条目
    leak = [e['id'] for e in items
            if e.get('entity_kind') == 'component'
            and _re.search(r'(公司|集团)$', str(e.get('type') or ''))]
    check(not leak, '无 type 以公司/集团结尾却仍标 component 的漏网条目（漏网: %s）' % leak[:5])

    # ② 覆盖率分母：非 component 一律 n_a，不得占用机械声明率分母
    bad_mi = [e['id'] for e in items
              if e.get('entity_kind') in ('organization', 'market_intelligence',
                                          'specification', 'software')
              and (e.get('mechanical_interface') or {}).get('status') != 'n_a']
    check(not bad_mi,
          '非零件条目（企业主体/市场情报/规范/软件）的 mechanical_interface 均为 n_a，'
          '不污染声明率分母（异常: %s）' % bad_mi[:5])

    # ③ 对外文案：facts() 必须区分总条数与零部件条数
    try:
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        from onboarding_block import facts as _facts
        f = _facts()
        kinds_ok = (f.get('component_entities', 0)
                    + f.get('organization_entities', 0)
                    + f.get('market_intelligence_entities', 0)
                    + f.get('specification_entities', 0)
                    + f.get('software_entities', 0)) == f.get('total_entities')
        check(kinds_ok, 'facts() 五类计数求和 == 实体总数（%s+%s+%s+%s+%s vs %s）'
              % (f.get('component_entities'), f.get('organization_entities'),
                 f.get('market_intelligence_entities'), f.get('specification_entities'),
                 f.get('software_entities'), f.get('total_entities')))
        check(f.get('component_entities') != f.get('total_entities'),
              '零部件条数与全库条数已解耦（不再用总数冒充零部件数）')
    except Exception as e:                                    # noqa: BLE001
        check(False, 'facts() 可计算五类计数（异常: %s）' % str(e)[:120])

    # ④ 源码层：选型候选必须用**白名单**排除一切非 component
    #    （20260809-05：原先检查的是黑名单字面量 `entity_kind !== 'organization'`。
    #     黑名单在新增种类时静默失效，闸门却依然全绿 —— 检查项本身也得跟着换成白名单。）
    mcp_src = read_text(os.path.join(ROOT, 'functions', 'mcp.js'))
    check("isSelectableComponent" in mcp_src,
          'mcp.js 选型候选走白名单 isSelectableComponent（新增种类自动被挡，不靠逐个拉黑）')
    check("e.entity_kind !== 'organization'" not in mcp_src,
          'mcp.js 已无逐个拉黑的黑名单残留（黑名单新增种类时静默失效）')
    check("organizations" in mcp_src,
          'mcp.js 实况字段透出 organizations 计数（对外可自查，不是内部悄悄过滤）')

    # ⑤ 行为层：拿生产源码实跑 —— 源码正则只证明写法变了，证不了结论变了
    node = shutil.which('node') or 'node'
    probe = (
        "import {judgePair as J} from './functions/_lib/compat_engine.js';"
        "import fs from 'fs';"
        "const E=JSON.parse(fs.readFileSync('api/entities.json','utf-8')).entities;"
        "const M=Object.fromEntries(E.map(e=>[e.id,e]));"
        # 合成一条企业主体：**阴阳对照不得依赖库内恰好有这种数据**。
        # 若用 E.find(...) 取真实条目，修复前库内一条都没有 → 探针整个抛异常 →
        # 连阴性对照一起变红，闸门就退化成"代码一变就全红"的花架子（L1.64 教训）。
        "const co={id:'ORG-SELFTEST',name:'某机器人公司',category:'platforms',"
        "entity_kind:'organization',type:'人形机器人公司'};"
        "const part=M['ACT-001'];"
        # 阳性①：公司 × 零件 → applicable=false，且文案不得再说"未声明"
        "const r=J(co,part);"
        "const p1=r.applicable===false&&r.overall_compatible===null;"
        "const nt=(r.dimensions||[]).map(d=>d.notes).join(' ');"
        "const p2=/不构成兼容性判定对象/.test(nt)&&!/未声明/.test(nt);"
        # 阳性②：全库任何含非 component 操作数的配对都不得给出 true
        "let bad=0;for(const e of E){if(e.entity_kind&&e.entity_kind!=='component'){"
        "for(const o of E){if(o.id===e.id)continue;"
        "const x=J(e,o);if(x.overall_compatible===true||x.applicable!==false)bad++;}}}"
        # 阴性①：两个真零件仍走正常四维裁决（applicable=true，没把引擎修成失能）
        "const n1=J(M['ACT-001'],M['ACT-002']).applicable===true;"
        # 阴性②：真零件间原有的 false 判伪能力保留（异法兰仍能判 false）
        "const mk=(i,m)=>({id:i,name:i,entity_kind:'component',mechanical_interface:m});"
        "const n2=J(mk('X',{status:'declared',standard:'ISO 9409-1-50-4-M6'}),"
        "mk('Y',{status:'declared',standard:'ISO 9409-1-31.5-4-M5'})).overall_compatible===false;"
        # 阴性③：缺 entity_kind 的老数据按 component 处理，不得被误挡
        "const n3=J({id:'P',name:'P',protocol:'CAN'},{id:'Q',name:'Q',protocol:'CAN'}).applicable===true;"
        "console.log(JSON.stringify({p1,p2,bad,n1,n2,n3}));"
    )
    try:
        r = subprocess.run([node, '--input-type=module', '-e', probe], cwd=ROOT,
                           capture_output=True, encoding='utf-8',
                           errors='replace', timeout=180)
        out = (r.stdout or '').strip().splitlines()
        d = json.loads(out[-1]) if out else {}
    except Exception as e:                                    # noqa: BLE001
        check(False, 'L1.65 行为探针可执行（异常: %s）' % str(e)[:120])
        return

    check(d.get('p1') is True,
          '阳性对照: 公司 × 零件 判定返回 applicable=false / overall=null')
    check(d.get('p2') is True,
          '阳性对照: 说明文案改口为「不构成兼容性判定对象」，'
          '不再出现「未声明」（类型错误不得伪装成数据缺口）')
    check(d.get('bad') == 0,
          '阳性对照: 全库含非 component 操作数的配对 0 例逃逸（实得 %s）' % d.get('bad'))
    check(d.get('n1') is True, '阴性对照: 两个真零件仍走四维裁决（applicable=true）')
    check(d.get('n2') is True, '阴性对照: 真零件间异法兰仍判 false（判伪能力保留）')
    check(d.get('n3') is True,
          '阴性对照: 缺 entity_kind 的老数据按 component 放行（宁可判定，不可静默挡掉真零件）')


def layer1_66():
    """L1.66 —— 补数据通道必须真的能补进去：有据机械声明不得被采集脚本抹掉。

    【20260809-04 · 名叫"补"的脚本其实在删】
    scripts/add_mechanical_interface.py 对全部 706 条无条件重写
    `e['mechanical_interface'] = build(e)`，而 build() 里唯一能产出 partial 的
    来源是**写死在源码里的 2 条白名单**。于是：

      · declared 恒为 0、partial 恒 ≤ 2，与实际采集到多少数据完全无关；
      · 任何人把厂商声明写进 api/entities.json，脚本下一次一跑就抹掉；
      · 而"补 declared 机械数据 / fill_pct 0.54%"恰恰是长期挂在待办第一位的
        头号瓶颈 —— 瓶颈不在没数据，在通道被自己焊死了。

    这一族缺陷的共同点：**声称的能力与真实能力不一致，且不报错**。
    L1.64 是用错字段下结论，L1.65 是用错对象下结论，本闸门是
    "宣称在积累、实际在丢弃"。三者都跑得通、都不抛异常。

    因此本闸门不看源码写法（写法改了不等于行为改了），而是拿生产 build()
    实喂合成条目验证行为；并且**阳性阴性成对**：既要证明有据声明活得下来，
    也要证明无据 / 空壳声明进不来（否则等于给假绿开后门）。
    """
    print('\n[L1.66] 补数据通道：有据机械声明不得被采集脚本抹掉')

    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    try:
        import importlib
        import add_mechanical_interface as AMI
        importlib.reload(AMI)
        build = AMI.build
    except Exception as e:                                    # noqa: BLE001
        check(False, 'add_mechanical_interface.build 可导入（异常: %s）' % str(e)[:120])
        return

    def mk(**kw):
        e = {'id': 'SELFTEST', 'category': 'actuators', 'entity_kind': 'component'}
        e.update(kw)
        return e

    # ── 阳性：有出处的声明必须原样存活 ────────────────────────────────
    p_partial = build(mk(mechanical_interface={
        'status': 'partial', 'mount_type': 'flange_mount',
        'declared_note': '带安装法兰座（厂商产品说明）',
        'source': '厂商官网产品资料', 'confidence': 0.7}))
    check(p_partial.get('status') == 'partial'
          and p_partial.get('mount_type') == 'flange_mount'
          and p_partial.get('declared_note'),
          '阳性: 有出处的 partial 声明被保留（实得 status=%s）' % p_partial.get('status'))

    p_decl = build(mk(mechanical_interface={
        'status': 'declared', 'mount_type': 'flange_mount',
        'standard': 'ISO 9409-1-50-4-M6',
        'source': '厂商数据手册 PDF', 'confidence': 0.9}))
    check(p_decl.get('status') == 'declared'
          and p_decl.get('standard') == 'ISO 9409-1-50-4-M6',
          '阳性: 有出处且带尺寸的 declared 声明被保留（实得 status=%s）' % p_decl.get('status'))

    # ── 阴性：无据 / 空壳 / 无声明 一律不得混成绿 ──────────────────────
    n_nosrc = build(mk(mechanical_interface={
        'status': 'declared', 'standard': 'ISO 9409-1-50-4-M6'}))
    check(n_nosrc.get('status') == 'not_declared',
          '阴性: 无 source 的"已声明"被拒（凭空断言不得进分子，实得 %s）'
          % n_nosrc.get('status'))

    n_hollow = build(mk(mechanical_interface={
        'status': 'declared', 'source': '某处', 'standard': None, 'flange': None}))
    check(n_hollow.get('status') == 'not_declared',
          '阴性: 标签写 declared 但无任何尺寸的空壳被拒（标签绿内容空，实得 %s）'
          % n_hollow.get('status'))

    n_plain = build(mk())
    check(n_plain.get('status') == 'not_declared',
          '阴性: 无声明的普通零部件仍为 not_declared（没把脚本改成一律放绿）')

    # ── 不变式：L1.65 的类型闸优先级不得被本改动翻转 ────────────────────
    n_org = build(mk(entity_kind='organization', mechanical_interface={
        'status': 'declared', 'standard': 'ISO 9409-1-50-4-M6', 'source': '某处'}))
    check(n_org.get('status') == 'n_a',
          '不变式: 企业主体即便带"声明"仍记 n_a（公司没有安装面，L1.65 不被绕过）')

    # ── 数据层：库内每条 declared/partial 都必须带出处 ──────────────────
    items = (load_entities().get('entities') or [])
    unsourced = [e['id'] for e in items
                 if (e.get('mechanical_interface') or {}).get('status') in ('declared', 'partial')
                 and not str((e.get('mechanical_interface') or {}).get('source') or '').strip()]
    check(not unsourced,
          '库内 declared/partial 条目均带 source（无据声明: %s）' % unsourced[:5])

    # ── 通道实效：分子必须真的能大于源码白名单容量 ──────────────────────
    seeded = len(getattr(AMI, 'PARTIAL', {}) or {})
    filled = [e['id'] for e in items
              if (e.get('mechanical_interface') or {}).get('status') in ('declared', 'partial')]
    check(len(filled) > seeded,
          '已有声明条数 %d > 源码白名单 %d 条 —— 通道确实能收外部补录数据，'
          '而不是只能靠改源码（否则 fill_pct 永远是白名单的影子）' % (len(filled), seeded))

    # ── 落盘格式：避免每跑一次就产生一行"无换行符"假差异 ────────────────
    with io.open(os.path.join(ROOT, 'api', 'entities.json'), encoding='utf-8') as f:
        tail = f.read()[-2:]
    check(tail.endswith('\n'),
          'entities.json 以换行结尾（写入器格式统一，避免幂等检查被假差异污染）')


def layer1_67():
    """L1.67 —— 派生接口不得落后于真相源：本地字段级零差异。

    【20260809-04 · 我把真告警当成了假阳性】
    连续两轮部署，post-check 都报「字段级内容漂移: 12/13 条实体线上与真相源不一致」。
    上一轮我的处置是：直连线上抓 `/api/entities.json`，看到数字全对，
    据此判定「CDN 边缘缓存瞬时报错（假阳性）」并放行。**这个判断是错的。**

    告警说的是 `/api/data.json`，我核的是 `/api/entities.json` —— 核错了对象。
    真相是：`api/data.json` 由 `normalize_categories.py` 单独重生成，而
    `govern_entity_kind.py` / `add_mechanical_interface.py` 改完真相源后**没人调它**。
    于是那 13 条（9 企业主体 + 3 市场情报 + 1 新补录）在对外主接口 `/api/data.json`
    里仍是旧形状：`status: not_declared / gap: 厂商未公开` —— 正是 L1.65 刚修掉的
    那句错话，原封不动挂在**调用量最大的那个接口**上。

    两层教训，后者更重：
      1. 派生文件与真相源之间没有强制一致性检查，只靠部署后校验兜底；
      2. **一个每次内容变更都会响的告警，会被训练成"照例忽略"**。它响了两次、
         两次都是真的，而我上一轮亲手把它写进报告说是假阳性。
         告警的价值不取决于它响不响，取决于响了之后有没有人核对它指名的那个对象。

    故本闸门把检测从"部署后 + 靠人判断"提前到"部署前 + 机器判定"。
    """
    print('\n[L1.67] 派生接口与真相源字段级一致（含分类 JSON）')

    def _stable(v):
        if isinstance(v, list):
            return [_stable(x) for x in v]
        if isinstance(v, dict):
            return {k: _stable(v[k]) for k in sorted(v)}
        return v

    def _fp(arr):
        return {e.get('id'): json.dumps(_stable(e), ensure_ascii=False, sort_keys=True)
                for e in arr if isinstance(e, dict) and e.get('id')}

    def _drift(a, b):
        return [k for k in a if k in b and a[k] != b[k]]

    src = load_entities().get('entities') or []
    fsrc = _fp(src)

    # ① 对外主接口 api/data.json —— 调用量最大的那个
    dj_path = os.path.join(ROOT, 'api', 'data.json')
    with io.open(dj_path, encoding='utf-8') as f:
        dj = json.load(f)
    darr = dj.get('data') or dj.get('entities') or []
    fdj = _fp(darr)
    check(len(darr) == len(src),
          'api/data.json 条数与真相源一致（%d vs %d）' % (len(darr), len(src)))
    d1 = _drift(fsrc, fdj)
    check(not d1,
          'api/data.json 与真相源字段级零差异（漂移 %d 条，示例: %s）'
          '—— 不一致时请跑 python scripts/normalize_categories.py 重生成'
          % (len(d1), d1[:3]))

    # ② 10 个分类 JSON —— 同一族，只是分片
    cat_drift = {}
    for name in ('actuators', 'sensors', 'chips', 'interfaces', 'protocols',
                 'llms', 'platforms', 'flexible_actuators', 'robot_ai_models',
                 'data_acquisition'):
        p = os.path.join(ROOT, 'api', '%s.json' % name)
        if not os.path.exists(p):
            continue
        with io.open(p, encoding='utf-8') as f:
            obj = json.load(f)
        arr = obj.get('data') or obj.get('entities') or (obj if isinstance(obj, list) else [])
        dd = _drift(_fp(arr), fsrc)
        if dd:
            cat_drift[name] = dd[:2]
    check(not cat_drift,
          '10 个分类 JSON 与真相源字段级零差异（漂移类目: %s）' % (cat_drift or '无'))

    # ③ 阴性对照：证明比对函数既不恒真也不恒假。
    #    【必须自足】对照数据从**真相源自身**复制，不能拿 darr —— 拿被测对象当对照，
    #    一旦 darr 真的漂移了，对照会跟着一起红，闸门退化成"一坏全红"，
    #    分不清"派生文件坏了"和"比对函数坏了"。这是 L1.64/L1.65 已经吃过的亏。
    if src:
        check(not _drift(fsrc, _fp(json.loads(json.dumps(src)))),
              '阴性对照: 真相源自比对判零差异（比对函数不是恒假）')
        poisoned = json.loads(json.dumps(src))
        poisoned[0]['__selftest_poison__'] = True
        detected = _drift(fsrc, _fp(poisoned))
        check(len(detected) == 1,
              '阴性对照: 篡改 1 条后精确检出 1 条（比对函数不是恒真，实得 %d）'
              % len(detected))


def layer1_68():
    """L1.68 —— 规范不是零件、模型也不是零件（L1.65 的量级补完 + 黑名单换白名单）。

    【20260809-05 · 同一病灶，27% 的量级】
    L1.65 修了 9 条"公司冒充零件"，但同一病灶还有两片没动：

      · protocols(64) + interfaces(37) = 101 条 —— EtherCAT、CANopen、USB 3.0、
        MIPI CSI-2、PCIe…… 这些是**规范本身**，不是实现规范的某个零件。
        修复前实测 judgePair(EtherCAT, DYNAMIXEL XM540) 的原话是：
        「EtherCAT 未声明通信协议，无法判定（无数据 ≠ 不兼容）」。
        EtherCAT 就是通信协议，它不"未声明"，它是被声明的那个东西。
      · llms(42) + robot_ai_models(44) = 86 条 —— GPT-4o、RT-2、π0、LeRobot……
        修复前同样被问出「GPT-4o 未声明机械接口」。

    合计 187 条 = 旧口径「694 条零部件」的 **27%**。与 L1.65 完全同型：
    不报错、overall 恒 null，只是把**类型错误**渲染成**数据缺口**，
    暗示"参数补上就能判"。规范和模型永远补不上法兰。

    附带修掉一个更隐蔽的东西：mcp.js 里的过滤是**黑名单**
    （`entity_kind !== 'market_intelligence' && !== 'organization'`）。
    黑名单当时不算错，问题是**新增种类时静默失效** —— 本轮加两档后，
    黑名单会继续把这 187 条算进"可选型零部件"，且不报任何错。
    种类是开放集合，过滤必须用白名单（isSelectableComponent）。
    """
    print('\n[L1.68] 规范/软件不是零件：类型闸覆盖全部非 component 种类')
    ents = load_entities()
    items = ents.get('entities') or []
    by_id = {e.get('id'): e for e in items}

    # ① 数据层：两档必须被识别出来，且带 kind_basis
    specs = [e for e in items if e.get('entity_kind') == 'specification']
    softs = [e for e in items if e.get('entity_kind') == 'software']
    check(len(specs) >= 90, '库内已识别出 specification 条目（实得 %d 条，期望 ≥90）' % len(specs))
    check(len(softs) >= 70, '库内已识别出 software 条目（实得 %d 条，期望 ≥70）' % len(softs))
    check(all(e.get('kind_basis') for e in specs + softs),
          'specification/software 条目均带 kind_basis（判据可追溯）')

    # ② 阳性样本点名：这几条必须落对档，避免"数量够了但落错人"
    expect = {'PROTO-001': 'specification', 'IF-001': 'specification',
              'LLM-001': 'software', 'RAI-001': 'software',
              'ACT-001': 'component'}
    wrong = {i: (by_id.get(i) or {}).get('entity_kind')
             for i, k in expect.items() if (by_id.get(i) or {}).get('entity_kind') != k}
    check(not wrong, '点名样本落档正确（EtherCAT/USB3.0=规范, GPT-4o/GR00T=软件, '
                     'DYNAMIXEL=零件；错档: %s）' % wrong)

    # ③ 阴性对照：真零件不得被这两条新规则误伤
    #    （误伤比漏判更糟 —— 真零件从选型里消失，用户根本不知道它存在过）
    for cat in ('actuators', 'sensors', 'chips', 'platforms',
                'flexible_actuators', 'data_acquisition'):
        rows = [e for e in items if e.get('category') == cat]
        bad = [e['id'] for e in rows if e.get('entity_kind') in ('specification', 'software')]
        check(not bad, '阴性对照: %s 类目无一条被误判为规范/软件（误伤: %s）' % (cat, bad[:3]))

    # ④ 规则的否决位真的存在：带厂商+物理量的条目落进 interfaces 时仍算零件
    #    （将来录入实物连接器的通道，不能被这条新规则静默吞掉）
    try:
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        from govern_entity_kind import classify as _classify
        fake_conn = {'id': 'X', 'category': 'interfaces', 'name': 'Molex MiniMix 连接器',
                     'manufacturer': 'Molex', 'weight': '12g', 'type': 'connector'}
        k_conn, _ = _classify(fake_conn)
        check(k_conn == 'component',
              '阴性对照: 带厂商+物理量的实物连接器落进 interfaces 仍判 component'
              '（实得 %s —— 否决位有效，未来录连接器不会被吞）' % k_conn)
        k_spec, _ = _classify({'id': 'Y', 'category': 'protocols', 'name': 'EtherCAT'})
        check(k_spec == 'specification', '阳性: 纯规范条目判 specification（实得 %s）' % k_spec)
        k_soft, _ = _classify({'id': 'Z', 'category': 'llms', 'name': 'GPT-4o'})
        check(k_soft == 'software', '阳性: 模型条目判 software（实得 %s）' % k_soft)
        k_junk, _ = _classify({'id': 'W', 'category': 'llms', 'name': '人形机器人',
                               'data_quality': 'non_entity'})
        check(k_junk == 'market_intelligence',
              '阴性对照: 自陈 non_entity 的行业热词不冒充软件（实得 %s）' % k_junk)
    except Exception as e:                                    # noqa: BLE001
        check(False, 'classify() 可独立自测（异常: %s）' % str(e)[:120])

    # ⑤ 源码层：引擎与 MCP 两侧都必须认这两档
    eng = read_text(os.path.join(ROOT, 'functions', '_lib', 'compat_engine.js'))
    check('specification:' in eng and 'software:' in eng,
          'compat_engine 的 KIND_LABEL 已含 specification/software（否则回答里只剩生硬的英文 kind）')
    check('KIND_WHY' in eng and 'KIND_HINT' in eng,
          '类型闸给出分种类的原因与正确问法（只拒绝不指路，调用方只会换个 ID 再撞一次）')
    mcp_src = read_text(os.path.join(ROOT, 'functions', 'mcp.js'))
    check('specifications' in mcp_src and 'software' in mcp_src,
          'mcp.js 实况透出 specifications/software 计数（对外可自查）')


def layer1_69():
    """L1.69 —— 新增对外口径必须同时接进两道闸门，否则判红。

    【20260809-06 · 一个"全绿"的空转轮】
    上一轮（L1.68）把对外口径从「694 条零部件」改成「507 条实物零部件 + 94 规范
    + 79 软件 + 9 企业主体 + 17 市场情报」，页面、Schema.org 全部重写完毕。
    然后：**一行都没部署，也没提交**。而本轮起手体检是这样的——

        regression.py        → ✅ 全部通过，放行发布
        probe.mjs            → ✅ 全部 24 条正常
        verify_live_numbers  → ✅ 线上 17 页 + 3 接口均与真相源一致（0 项未核验）

    三道全绿。可线上 Schema.org 里挂的仍是：
        "706 条实体（其中 694 条零部件…"
    —— 正是上一轮亲口认定为"不诚实"、并宣称已修好的那句话。

    为什么全绿：L1.62 靠 `_NOUN2KEY` 把页面上的名词翻译成真相源的键，
    翻译不出来就 `continue` 放行（"宁可漏报也不假红"）。这条在名词表**跟得上**
    的前提下是对的；本轮新增的五个名词一个都没进表，于是那 5 个数字
    **全部走了放行分支**，而收尾照样打印「0 项未核验」。
    "未核验"统计的是**没抓到的页面数**，不是**没比对的数字个数**——
    页面抓到了、一个数字都没比，仍然记作已核验。

    所以真正的缺陷不是"这次忘了加名词"，是**加了新口径不会让任何东西失败**：
    唯一会喊的角色（核验器）恰好是靠那张没人维护的表来决定喊不喊的。

    本闸门把这层依赖翻过来：以 facts() 为准反查名词表，
    每个 `*_entities` 口径键都必须至少有一个名词能映射到它。
    新增一档口径而忘了接核验 → 这里直接红，不必等线上播错话被人发现。
    """
    print('\n[L1.69] 新增对外口径必须接进核验（名词表覆盖 facts 的全部种类键）')
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import onboarding_block as _ob
    import verify_live_numbers as _vln

    f = _ob.facts()
    # total_entities 是**总数**不是种类档，早已由「实体/条目 → TOTAL」覆盖，排除掉；
    # 其余 `*_entities` 一律视为对外种类口径，必须可核验。
    kind_keys = {k for k in f if k.endswith('_entities')} - {'total_entities'}
    check(len(kind_keys) >= 5,
          'facts() 暴露了多档种类口径（实得 %d 档：%s）'
          % (len(kind_keys), ','.join(sorted(kind_keys))))

    # ① 源头闸（L1.61）：每个种类键都要有名词，写死字面量才会被认出来
    covered_src = set(_KIND_NOUNS.values())
    missing_src = sorted(kind_keys - covered_src)
    check(not missing_src,
          'L1.61 名词表覆盖全部种类口径（未覆盖: %s）' % (missing_src or '无'))

    # ② 线上核验（L1.62）：名词要能翻译成期望值，否则取到数字也会静默放行
    exp = _vln.expected_values(f)
    unreachable = sorted(k for k in kind_keys
                         if k not in exp or k not in set(_vln._NOUN2KEY.values()))
    check(not unreachable,
          'L1.62 期望值+名词表可达全部种类口径（够不着: %s）' % (unreachable or '无'))

    # ③ 阳性对照：线上那句真话的原文，必须能被判出失配
    #    （原文取自 2026-08-09 06:3x 实际抓到的 roboparts.cc 首页 Schema.org，不是我编的）
    live_line = ('"@type":"Dataset","name":"RoboParts 机器人零部件兼容性数据集",'
                 '"description":"706 条实体（其中 694 条零部件）"')
    bad = _vln.number_mismatches([live_line], exp)
    check(any(b[3] == 694 for b in bad),
          '阳性: 线上真实的「694 条零部件」判红（修复前此行被静默放行，实得 %s）'
          % ([(b[2], b[3], b[4]) for b in bad] or '未检出'))

    # ④ 阴性对照：写对了的当期原文不许判红（否则闸门恒红＝没人会再看它）
    #    注意 good_line 必须带自我指称（RoboParts/数据集），否则 L1.61 口径边界
    #    根本不认这一行 —— 那样"不判红"是因为**压根没看**，阴性对照就成了摆设。
    #    第一版正是这么写的，被下面 ⑤ 的篡改对照当场抓出来（"未检出"）。
    good_line = ('RoboParts 数据集："%d 条实体（其中 %d 条实物零部件、%d 条接口/协议规范、'
                 '%d 条 AI 模型与软件、%d 条企业主体、%d 条市场情报）"'
                 % (f['total_entities'], f['component_entities'],
                    f['specification_entities'], f['software_entities'],
                    f['organization_entities'], f['market_intelligence_entities']))
    in_scope = bool(_L161_MARKER.search(good_line) and _L161_COUNT.search(good_line))
    check(in_scope, '阴性对照的样例确实落在 L1.61 口径边界内（否则"不判红"毫无意义）')
    check(not _vln.number_mismatches([good_line], exp),
          '阴性对照: 与真相源一致的当期原话不判红（误报: %s）'
          % (_vln.number_mismatches([good_line], exp) or '无'))

    # ⑤ 阴性对照：判定不是恒红 —— 只改一个数就要精确抓到那一个
    tampered = good_line.replace('%d 条实物零部件' % f['component_entities'],
                                 '999 条实物零部件')
    det = _vln.number_mismatches([tampered], exp)
    check(len(det) == 1 and det[0][3] == 999,
          '阴性对照: 篡改单个种类数被精确检出 1 处（实得 %s）'
          % ([(d[2], d[3]) for d in det] or '未检出'))


def layer1_70():
    """Tier 分级必须服从本仓自己写下的 tier_definition —— 出处只是站点首页，封顶 Tier B。

    【20260809-09】这条规则不是新提的。scripts/quality-baseline.json 的
    `_traceable_history` 2026-08-05 第 3 轮已白纸黑字写下：

        「URL 若仅为厂商首页（如把 Maxon EC Flat 60 挂到 maxongroup.com），
          无论响应多正常一律封顶 Tier B —— 该规则当场挤掉 8 条注水 Tier A」

    但它只活在 scripts/verify_vendor_sources.py 的一张**手维护 REGISTRY**里（57 条）。
    没登记的条目一律绕过 —— 于是复发：本轮全库扫出 88 条「Tier A + 站点根 URL」，
    其中 MOT-maxon-re25 挂的正是 https://www.maxongroup.com，与当年被点名的反例
    同域名、同错法。**规则修过一次却没变成闸门，等于没修**（同 L1.69 教训：
    靠手维护的表决定"看不看"，覆盖面不会自己生长）。

    对外影响是实的：traceable_pct 是 /api 与站点披露的信任主指标，
    注水口径下 57.91%，按本仓自己的定义归位后 47.32% —— 虚高 10.6pp。
    """
    print('\n[L1.70] Tier 分级服从 tier_definition（出处仅站点首页 → 封顶 B）')
    import source_scope as ss
    doc = load_entities()
    ents = doc['entities']

    viol = ss.violations(ents)
    check(len(viol) == 0,
          '无「Tier A + 出处仅站点首页」注水条目（实得 %d 条%s）'
          % (len(viol), '' if not viol else '：' + ', '.join(e['id'] for e in viol[:4])))

    # ① 阳性：当年被点名的注水形态必须判红
    check(ss.tier_cap({'name': 'maxon RE 25 空心杯直流电机',
                       'source_url': 'https://www.maxongroup.com'}) == 'B',
          '阳性: 「maxon RE 25 挂 maxongroup.com 首页」判为封顶 B（2026-08-05 点名的注水形态）')
    check(ss.tier_cap({'name': 'RT-1', 'source_url': 'https://www.deepmind.google'}) == 'B',
          '阳性: 「RT-1 挂 deepmind.google 首页」判为封顶 B')

    # ② 阴性对照：判据不能恒红，否则闸门会被训练成照例忽略
    check(ss.tier_cap({'name': 'Octo', 'source_url': 'https://octo-models.github.io'}) == 'A',
          '阴性对照: 项目自有主页（实体本身即该项目）仍可 Tier A')
    check(ss.tier_cap({'name': 'maxon RE 25',
                       'source_url': 'https://www.maxongroup.com/maxon/view/product/118743'}) == 'A',
          '阴性对照: 带具体路径的产品深链不判红')
    check(ss.scope_of({'name': 'x', 'source_url': ''}) is None,
          '阴性对照: 无 source_url 的条目不由本闸门处置（归 Tier C 治理）')

    # ③ 覆盖面自证（L1.69 教训的直接落实）：新条目**无需任何登记**即被判据覆盖。
    #    若判据退化回"读一张注册表"，注入的样例就不会被检出，这一条立刻转红。
    injected = list(ents) + [{'id': 'ZZZ-probe', 'name': 'Foo Bar 9000 Servo',
                              'source_url': 'https://www.example.com', 'source_tier': 'A'}]
    check(len(ss.violations(injected)) == len(viol) + 1,
          '覆盖面自证: 未登记的新条目也被判据覆盖（注入 1 条注水样例被精确检出）')

    # ④ 定义与判据不许各写各的：tier_definition 里"官网首页=B"这句话是本闸门的依据，
    #    有人把定义改了却不改判据（或反之），闸门就会守着一个已经不存在的口径。
    tdef = (doc.get('meta', {}).get('provenance_coverage', {})
            .get('tier_definition', {}))
    check('首页' in (tdef.get('B') or ''),
          'tier_definition.B 仍明示「官网首页」属 B（本闸门的依据未被悄悄改掉）')


def layer1_73():
    """部署占位必须归属「运行轮次」，而非部署那一刻的墙钟小时（20260809-11）

    ── 缺陷：留痕机制会给自己造出永远填不上的孤儿 ──

    deploy.mjs 的 ensureRunTrace() 按 `now.getHours()` 决定占位落在哪一格，
    隐含前提是「部署时刻的小时 == 该轮报告的小时」。这条前提对飞轮**结构性不成立**：
    一轮运行 09:35 起跑、干完活 10:06 才部署，报告写在 09 格 —— 10 格于是被落了
    一份占位，而那一小时**并不存在第二轮运行**，没有任何人会来填它。

    后果不是多一条噪声。这份孤儿占位同时触发三道闸门：
      L1.32（过期占位：部署后始终没人填写）
      L1.21（_LATEST 与最新小时报告同口径 —— 最新报告变成了那份占位）
      L1.63（日报声明时刻不得早于最新小时报告）
    → 回归 EXIT=1、**禁止发布**。8/9 一天内复发两次（06:43、10:06）。

    真正值得记的是**上一轮怎么放过它的**：06:43 那次已被看见，判语是
    「属误报噪声…若反复出现可考虑给占位加"运行中"判据」——
    把一个会阻断发布的红灯归类成噪声，然后写进备忘录当作已交代。
    三小时后它就把回归卡死了。这是「口径 ≠ 事实」族的又一种形态：
    **判定一个红灯为噪声之前，先确认它到底会不会阻断**；
    “看起来像噪声”和“确实无害”是两件事。

    ── 修法：纠正归属，而不是放宽闸门 ──

    飞轮调用 deploy 前设 `ROBOPARTS_RUN_SLOT=YYYYMMDD-HH`（本轮报告 slot），
    占位即落回本轮那一格，随后被真报告覆盖，孤儿消失。
    检测力度**分毫未减**：若该轮真的中断，占位仍留在本轮格，孤儿检测照抓；
    未设该变量时行为完全不变（主线/人工部署照旧按墙钟留痕，L1.40 纪律保持）。

    ── 为什么必须配这道闸门 ──

    归属逻辑一旦被简化回 `now.getHours()`（比如有人觉得"环境变量太绕"），
    症状要等下一次跨小时部署才复现，而那时红的是另外三道闸门，
    根因又会被当成噪声。故此处做**行为对照**：直接执行生产源码里
    ensureRunTrace 的函数体原文（非另抄实现），在临时目录里跑七种情形，
    看它究竟把占位写到了哪一格。同时守住防滥用边界 ——
    slot 只能向过去、不得超 6 小时，否则可把占位丢进远古格子当免检通道。
    """
    print('\n[L1.73] 部署占位归属「运行轮次」而非墙钟小时（跨小时不得自造孤儿）')
    import json as _json
    import subprocess as _sp
    import tempfile as _tf

    deploy = os.path.join(ROOT, 'scripts', 'deploy.mjs')
    if not os.path.exists(deploy):
        check(False, 'scripts/deploy.mjs 存在（占位机制的宿主）')
        return
    src = open(deploy, encoding='utf-8').read()

    check('ROBOPARTS_RUN_SLOT' in src,
          'deploy.mjs 支持 ROBOPARTS_RUN_SLOT 轮次归属（缺失＝跨小时部署必造孤儿占位）')

    harness = r'''
import fs from 'fs';
import path from 'path';
import os from 'os';

const DEPLOY = process.argv[2];
const src = fs.readFileSync(DEPLOY, 'utf8');
const out = {};

const sm = /const STUB_SENTINEL = '([^']+)';/.exec(src);
const start = src.indexOf('function ensureRunTrace()');
if (!sm || start < 0) {
  console.log(JSON.stringify({ error: 'sentinel 或 ensureRunTrace 未在源码中找到' }));
  process.exit(0);
}
const SENT = sm[1];

let depth = 0, end = -1;
for (let i = src.indexOf('{', start); i < src.length; i++) {
  if (src[i] === '{') depth++;
  else if (src[i] === '}') { depth--; if (depth === 0) { end = i + 1; break; } }
}
const fnSrc = src.slice(start, end);
const make = new Function('fs', 'path', 'spawnSync', 'ROOT', 'STUB_SENTINEL', 'process',
                          fnSrc + '\nreturn ensureRunTrace;');

const p2 = (n) => String(n).padStart(2, '0');
const slotOf = (d) => `${d.getFullYear()}${p2(d.getMonth() + 1)}${p2(d.getDate())}-${p2(d.getHours())}`;
const now = new Date();
const cur = slotOf(now);
const shift = (h) => slotOf(new Date(now.getTime() + h * 3600000));
const fakeSpawn = () => ({ stdout: '' });
const origLog = console.log, origWarn = console.warn;

function run(slotVal, preexist) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rp-rt-'));
  const dir = path.join(root, 'ops', 'results');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, '_SUMMARY.md'), '- seed\n');
  if (preexist) fs.writeFileSync(path.join(dir, `roboparts-${preexist}.md`), '# 真报告\n本轮已自行填写\n');
  const env = {};
  if (slotVal !== null) env.ROBOPARTS_RUN_SLOT = slotVal;
  console.log = () => {}; console.warn = () => {};
  try {
    make(fs, path, fakeSpawn, root, SENT, { env })();
  } finally {
    console.log = origLog; console.warn = origWarn;
  }
  const all = fs.readdirSync(dir).filter((f) => /^roboparts-\d{8}-\d{2}\.md$/.test(f));
  const stubs = all.filter((f) =>
    fs.readFileSync(path.join(dir, f), 'utf8').split('\n').some((l) => l.trim() === SENT));
  const bodies = {};
  for (const f of stubs) bodies[f] = fs.readFileSync(path.join(dir, f), 'utf8');
  fs.rmSync(root, { recursive: true, force: true });
  return { stubs, bodies };
}

out.cur = cur;
out.prev1 = shift(-1);
out.no_slot = run(null);
out.prev_slot = run(shift(-1));
out.future = run(shift(1));
out.too_old = run(shift(-7));
out.garbage = run('not-a-slot');
out.same_hour = run(cur);
out.already = run(shift(-1), shift(-1));
origLog(JSON.stringify(out));
'''

    node = shutil.which('node') or 'node'
    with _tf.TemporaryDirectory() as td:
        hp = os.path.join(td, 'runtrace_probe.mjs')
        with open(hp, 'w', encoding='utf-8') as fh:
            fh.write(harness)
        proc = _sp.run([node, hp, deploy], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    if proc.returncode != 0 or not (proc.stdout or '').strip():
        check(False, '行为对照 harness 可执行（stderr: %s）'
              % ((proc.stderr or '').strip()[:200] or '空'))
        return
    try:
        r = _json.loads((proc.stdout or '').strip().splitlines()[-1])
    except Exception as exc:
        check(False, '行为对照输出可解析（%s）' % exc)
        return
    if r.get('error'):
        check(False, '生产源码可被提取用于对照（%s）' % r['error'])
        return

    cur_f = 'roboparts-%s.md' % r['cur']
    prev_f = 'roboparts-%s.md' % r['prev1']

    # ── 阳性：跨小时部署必须归属本轮 slot，且不得在墙钟格另造一份 ──
    ps = r['prev_slot']['stubs']
    check(ps == [prev_f],
          '阳性: 跨小时部署（slot=上一小时）占位落在**本轮格**且墙钟格无孤儿（实得 %s）' % ps)
    check(cur_f not in ps,
          '阳性: 墙钟小时格未被另造占位（造了就是那份永远没人填的孤儿）')
    body = (r['prev_slot']['bodies'].get(prev_f) or '')
    check('归属说明' in body,
          '阳性: 重定向时正文如实记录「归属说明 + 真实部署时刻」（否则读者无法分辨时间从何而来）')

    # ── 阳性：本轮 slot 已有真报告时，不得再落占位 ──
    check(r['already']['stubs'] == [],
          '阳性: 本轮 slot 已自行报告则不落占位（实得 %s）' % r['already']['stubs'])

    # ── 阴性对照：未设变量／越界值一律回退墙钟，行为不得改变 ──
    check(r['no_slot']['stubs'] == [cur_f],
          '阴性: 未设 ROBOPARTS_RUN_SLOT 时行为不变（墙钟格留痕，实得 %s）' % r['no_slot']['stubs'])
    check(r['future']['stubs'] == [cur_f],
          '阴性: slot 指向未来一律忽略（否则可预先占位逃检，实得 %s）' % r['future']['stubs'])
    check(r['too_old']['stubs'] == [cur_f],
          '阴性: slot 距今超 6h 一律忽略（防把占位丢进远古格当免检通道，实得 %s）'
          % r['too_old']['stubs'])
    check(r['garbage']['stubs'] == [cur_f],
          '阴性: slot 格式非法时安全回退墙钟（实得 %s）' % r['garbage']['stubs'])
    same = r['same_hour']
    check(same['stubs'] == [cur_f] and '归属说明' not in (same['bodies'].get(cur_f) or ''),
          '阴性: slot 即当前小时时与未设一致、不加多余归属说明（实得 %s）' % same['stubs'])


def layer1_74():
    """机械身份键多值必须按集合比对，塌缩成单 token 会产出「假红」（20260809-12）

    ── 缺陷：把装得上说成装不上 ──

    mechanicalEvidence() 原实现取身份键是 `.map(k => mi[k]).map(v => String(v))`。
    对数组值，String(['a','b','c']) === 'a,b,c' —— 得到**一个**永远无法与任何
    单值相交的伪 token。于是：

      夹爪 standard = ['ISO 9409-1-50-4-M6', 'ISO 9409-1-31.5-4-M5', ...]
      手腕 standard = 'ISO 9409-1-50-4-M6'
      → compatible = **false**，notes「机械接口无交集」

    50-4-M6 明明白纸黑字在集合里。这不是"判不了"（null），是**判错**（false）：
    把装得上的组合说成装不上。它比不给结论更有害 —— 三态设计的全部意义就是
    "没数据"要说 null，而这里输出的是带着"有数据支撑"外观的确定性错误结论，
    会让采购方直接排除掉正确选项。

    ── 为什么这不是边角情形 ──

    "一个零件只对应一种孔位"在本行业是少数派：夹爪/工具快换盘/转接板普遍靠更换
    耦合件适配多种法兰。Robotiq 2F-85 官方手册 §6.1.1 一口气列了 6 种耦合件，
    横跨 ISO 9409-1 的 50-4-M6 / 31.5-4-M5 / 40-4-M6 与 PCD56/PCD60 等非 ISO 孔位。
    也就是说：**最需要判定的形态，恰恰是原实现唯一会判错的形态**。

    此前之所以一直没暴露，只是因为全库 standard/flange 非空的条目数为 0 ——
    引擎在机械维度上从没拿到过真数据。缺陷被"油箱是空的"掩盖着，
    而补机械数据正是长期挂在待办首位的头号瓶颈：一旦开始补，它立刻生效。
    故必须在补数据的同一批次里修掉，不能留给"以后再说"。

    ── 判据 ──

    直接 import 生产源码 compat_engine.js 跑行为对照（非另抄实现），
    并**拿修复前的原版归一化逻辑对同一输入实测**，确认它确实会命中（非空转）。
    阴性对照守住两条底线：不得矫枉过正成"总是 true"（真无交集仍须 false），
    以及标量路径行为分毫不变。
    """
    print('\n[L1.74] 机械身份键多值按集合比对（塌缩成单 token = 假红）')
    import json as _json
    import subprocess as _sp

    engine = os.path.join(ROOT, 'functions', '_lib', 'compat_engine.js')
    if not os.path.exists(engine):
        check(False, 'compat_engine.js 存在')
        return

    node = shutil.which('node') or 'node'
    probe = (
        "import {evalDimension as ev, mechanicalEvidence as me} from"
        " './functions/_lib/compat_engine.js';"
        "import fs from 'fs';"
        "const mk=(i,m)=>({id:i,name:i,mechanical_interface:m});"
        "const SET=['ISO 9409-1-50-4-M6','ISO 9409-1-31.5-4-M5','ISO 9409-1-40-4-M6'];"
        "const grip=mk('G',{status:'declared',standard:SET});"
        "const w50=mk('W50',{status:'declared',standard:'ISO 9409-1-50-4-M6'});"
        "const w31=mk('W31',{status:'declared',standard:'ISO 9409-1-31.5-4-M5'});"
        "const wX=mk('WX',{status:'declared',standard:'ISO 9409-1-125-6-M10'});"
        # 阳性：集合内任一孔位命中即 true
        "const p1=ev('mechanical',grip,w50).compatible===true;"
        "const p2=ev('mechanical',grip,w31).compatible===true;"
        "const p3=me(grip).matched.length===3;"
        # 阳性：库内真实条目确实以数组落库且被正确展开
        "const E=JSON.parse(fs.readFileSync('api/entities.json','utf-8')).entities;"
        "const real=E.filter(e=>{const m=e.mechanical_interface||{};"
        "return Array.isArray(m.standard)||Array.isArray(m.flange);});"
        "const p4=real.length>0&&real.every(e=>me(e).matched.length>=2);"
        # 阳性：多值条目必须带出处（无出处的"已声明"是凭空断言）
        "const p5=real.every(e=>String((e.mechanical_interface||{}).source||'').trim().length>0);"
        # 修复前原版归一化：逐字复刻旧的三行写法，对同一输入实测
        "const oldKeys=mi=>['standard','flange'].map(k=>mi[k])"
        ".filter(v=>v&&String(v).toLowerCase()!=='unknown').map(v=>String(v).toLowerCase());"
        "const ok=oldKeys({standard:SET});"
        "const oldShared=ok.filter(x=>x==='iso 9409-1-50-4-m6');"
        "const prefix_hit=(ok.length===1&&oldShared.length===0);"
        # 阴性：真无交集仍须 false（不得矫枉过正成总是 true）
        "const n1=ev('mechanical',grip,wX).compatible===false;"
        # 阴性：标量路径行为不变
        "const iso={status:'declared',standard:'ISO 9409-1-50-4-M6'};"
        "const n2=ev('mechanical',mk('X',iso),mk('Y',{...iso})).compatible===true;"
        "const n3=ev('mechanical',mk('X',iso),"
        "mk('Y',{status:'declared',standard:'ISO 9409-1-31.5-4-M5'})).compatible===false;"
        # 阴性：空集合/全 unknown 不得凭空造出可比对标识
        "const n4=ev('mechanical',mk('X',{status:'partial',standard:[]}),mk('Y',iso))"
        ".compatible===null;"
        "const n5=me(mk('Z',{status:'declared',standard:['unknown','']})).matched.length===0;"
        # 阴性：只有 mount_type 仍判不了且说明点名缺法兰（L1.67 不得回退）
        "const wk=ev('mechanical',mk('X',{status:'partial',mount_type:'direct_mount'}),"
        "mk('Y',{status:'partial',mount_type:'direct_mount'}));"
        "const n6=wk.compatible===null&&/仅声明安装方式/.test(wk.notes||'');"
        # 阴性：全库真实配对不得因本改动冒出「无支撑假绿」
        # 真绿=共享至少一个机械身份键(standard/flange token)；假绿=判兼容却无任何共享身份键
        "const idset=e=>{const m=(e&&e.mechanical_interface)||{};"
        "const arr=x=>Array.isArray(x)?x:(x?String(x).toLowerCase():[]);"
        "return new Set([...arr(m.standard),...arr(m.flange)].filter(Boolean));};"
        "let tt=0,tb=0;"
        "for(let i=0;i<E.length;i++)for(let j=i+1;j<E.length;j++){"
        "if(ev('mechanical',E[i],E[j]).compatible===true){"
        "const A=idset(E[i]),B=idset(E[j]);let sh=false;"
        "for(const t of A)if(B.has(t)){sh=true;break;}"
        "if(sh)tb++;else tt++;}}"
        "console.log(JSON.stringify({p1,p2,p3,p4,p5,prefix_hit,n1,n2,n3,n4,n5,n6,tt,tb,"
        "nreal:real.length}));"
    )
    try:
        r = _sp.run([node, '--input-type=module', '-e', probe], cwd=ROOT,
                    capture_output=True, encoding='utf-8', errors='replace', timeout=180)
        out = _json.loads((r.stdout or '').strip().splitlines()[-1])
    except Exception as exc:
        check(False, '行为对照可执行且输出可解析（%s）' % exc)
        return

    check(out['p1'], '阳性: 集合含对方孔位(50-4-M6)判 true —— 修复前此处是「无交集」假红')
    check(out['p2'], '阳性: 集合含对方另一孔位(31.5-4-M5)同样判 true（非只修了第一项）')
    check(out['p3'], '阳性: 三元集合展开为 3 个可比对 token，未塌缩成 1 个伪 token')
    check(out['p4'],
          '阳性: 库内真实多值条目确实被正确展开（实得 %d 条）' % out['nreal'])
    check(out['p5'], '阳性: 多值声明必须带 source（无出处的已声明＝凭空断言，L1.64 族）')
    check(out['prefix_hit'],
          '非空转自证: 修复前原版归一化对同一输入确实塌缩成 1 个 token 且与 50-4-M6 无交集')
    check(out['n1'], '阴性: 真无交集仍判 false（未矫枉过正成"总是兼容"）')
    check(out['n2'], '阴性: 标量同值仍 true（标量路径行为不变）')
    check(out['n3'], '阴性: 标量异值仍 false（标量路径判伪能力不变）')
    check(out['n4'], '阴性: 空集合判 null，不得凭空造出可比对标识')
    check(out['n5'], '阴性: 全为 unknown/空串的集合不产出 token')
    check(out['n6'], '阴性: 仅 mount_type 仍判不了且点名缺法兰（L1.67 不回退）')
    check(out['tt'] == 0,
          '阴性: 全库真实配对未因多值改动冒出假绿（无支撑假绿 %d 对 / 合法共享孔位 %d 对）'
          % (out['tt'], out.get('tb', 0)))


# 权威出处白名单：题录库 / 国标计划库 / 国标全文公开 / 发布机构官网。
# **刻意不含任何新闻站、公众号、聚合站、厂商软文站** —— 两次"把新闻稿发文时间戳
# 当成标准发布日期"的事故（T/YNIPA 033-2026、T/CAEE 060-2026）都源自这类源头。
_STD_EVIDENCE_HOSTS = {
    'ttbz.org.cn', 'www.ttbz.org.cn',              # 全国团体标准信息平台
    'std.samr.gov.cn',                              # 国家标准计划库
    'openstd.samr.gov.cn',                          # 国家标准全文公开系统
    'cssn.net.cn', 'www.cssn.net.cn',               # 国家标准馆题录库
    'iso.org', 'www.iso.org', 'committee.iso.org',  # ISO 官方条目
    # 【20260811-04 新增】国家数字标准馆。纳入依据不是"看着像官方"，而是实测站脚
    # 版权声明「版权归中国标准化研究院所有」+ service@cnis.ac.cn + 北京海淀知春路4号，
    # 与已在白名单的 cssn.net.cn（中国标准服务网）**同一主办单位**，属一手题录库，
    # 符合本白名单"排除新闻站/公众号/聚合站/厂商软文站"的立意。
    # ⚠ 但它同时是团标枚举器的**发现渠道** —— 发现渠道 == 取证渠道意味着解析错了
    # 没有第二双眼睛。因此纳入白名单必须与 L1.86（原文快照逐字比对）配套，
    # 单独放宽白名单而不配 L1.86 属于放水。
    'ndls.org.cn', 'www.ndls.org.cn',
}

# 带时间/状态断言的字段：只要出现其一，该条就必须配权威出处。
_STD_CLAIM_KEYS = ('issued_at', 'effective_at', 'announced_at',
                   'plan_released_at', 'last_reviewed_at', 'status')


def _std_evidence_host_ok(url):
    try:
        from urllib.parse import urlparse
        host = (urlparse(str(url)).hostname or '').lower()
    except Exception:
        return False
    return host in _STD_EVIDENCE_HOSTS


def _std_audit(spec):
    """返回 (缺出处的条目 id, 出处非权威源的 (id, host))。纯函数，供阴阳对照复用。"""
    missing, bad_host = [], []
    for s in (spec or {}).get('standards', []):
        has_claim = any(s.get(k) for k in _STD_CLAIM_KEYS)
        if not has_claim:
            continue
        ev = str(s.get('evidence') or '').strip()
        if not ev or not str(s.get('evidence_tier') or '').strip():
            missing.append(s.get('id'))
        elif not _std_evidence_host_ok(ev):
            bad_host.append((s.get('id'), ev))
    return missing, bad_host


def layer1_75():
    """标准登记表：任何带日期/状态断言的条目都必须挂权威出处（存量同样受管）。

    ── 为什么加这道闸门 ──

    两周内两次把**新闻稿的发文时间戳**当成标准发布日期（T/YNIPA 033-2026 记成
    "刚启动编制"，实为已实施；T/CAEE 060-2026 记成 7-31 发布，实为 6-10 发布并实施）。
    第一次事后立了"只认题录库/机构公告"的纪律 —— 但**纪律只是人读的一句话，
    它只堵住新入库这道门**，对已经躺在库里的存量记录毫无约束力，
    而 060 恰恰是存量。于是第二次照犯。

    这一轮清点存量才发现：6 条记录里有 **4 条带着日期/状态断言却挂零出处**
    （20262893、20261783、ISO 22166-201、ISO 22166-1）。它们的内容经核验属实，
    但"碰巧是对的"和"可被验证是对的"是两回事 —— 无出处的断言无法被证伪，
    下次错了同样发现不了。

    ── 判据 ──

    对 api/entities.json 落盘的 standard_conformance_spec 实测（不是读源码常量），
    要求带断言的条目 100% 具备 evidence + evidence_tier，且 evidence 主机名
    落在权威白名单内。阴性对照喂入三种伪造形态（新闻站出处、只有 tier 没有链接、
    仅 evidence 无 tier），确认闸门确实会拦 —— 不是恒真空转。
    """
    print('\n[L1.75] 标准登记表：日期/状态断言必须挂权威出处（新闻站出处一律拒收）')
    data = load_entities()
    spec = (data.get('meta') or {}).get('standard_conformance_spec') or {}
    stds = spec.get('standards') or []

    check(len(stds) > 0, '标准登记表非空（实得 %d 条）' % len(stds))
    missing, bad_host = _std_audit(spec)
    check(not missing,
          '阳性: 每条带日期/状态断言的标准都有 evidence + evidence_tier（缺: %s）'
          % (missing or '无'))
    check(not bad_host,
          '阳性: 出处主机名均在权威白名单内（越权: %s）' % (bad_host or '无'))

    # 非空转自证：拿本次修复前的存量快照实测，闸门必须命中那 4 条。
    pre_fix = {'standards': [
        {'id': '20262893-T-604', 'status': '在研（2026-05-22 立项，周期 15 个月）'},
        {'id': '20261783-T-604', 'status': '在研'},
        {'id': 'ISO 22166-201:2024', 'status': '已发布（stage 60.60 现行）'},
        {'id': 'ISO 22166-1:2021', 'status': 'stage 90.92 待修订'},
    ]}
    pre_missing, _ = _std_audit(pre_fix)
    check(len(pre_missing) == 4,
          '非空转自证: 修复前的 4 条无出处存量确实会被本闸门拦下（实得 %d 条）'
          % len(pre_missing))

    # 阴性：新闻站/聚合站出处必须被拒（这正是两次事故的源头形态）
    for host_case in ('https://www.toutiao.com/article/7664664991320031796/',
                      'https://mp.weixin.qq.com/s/abcdef',
                      'https://www.bzchaxun.com/view/6134050011000000.html'):
        _, bad = _std_audit({'standards': [
            {'id': 'FAKE', 'issued_at': '2026-07-31',
             'evidence': host_case, 'evidence_tier': '新闻报道'}]})
        check(len(bad) == 1, '阴性: 非权威源出处被拒（%s）' % host_case.split('/')[2])

    # 阴性：只有 tier 没有链接 / 只有链接没有 tier，都算无出处
    m1, _ = _std_audit({'standards': [
        {'id': 'F1', 'issued_at': '2026-01-01', 'evidence_tier': '题录库'}]})
    check(len(m1) == 1, '阴性: 只声明"出自题录库"却给不出链接，视同无出处')
    m2, _ = _std_audit({'standards': [
        {'id': 'F2', 'issued_at': '2026-01-01',
         'evidence': 'https://www.ttbz.org.cn/x.html'}]})
    check(len(m2) == 1, '阴性: 有链接但未标注出处层级，视同无出处')

    # 阴性：不带任何断言的纯参考条目不该被误伤（闸门不得过度扩张）
    m3, b3 = _std_audit({'standards': [{'id': 'F3', 'name': '仅登记名称，无任何断言'}]})
    check(not m3 and not b3, '阴性: 无日期/状态断言的纯登记条目不被误伤')

    # 观察名单（在研计划）同样要挂出处，且明示不进判据
    wl = spec.get('registry_watchlist')
    if wl:
        check(_std_evidence_host_ok(wl.get('evidence', '')),
              '阳性: 在研观察名单挂权威出处（%s）' % wl.get('evidence_tier'))
        check(all(p.get('id') and p.get('plan_released_at') and p.get('status')
                  for p in wl.get('plans', [])),
              '阳性: 观察名单每条计划均有计划号+下达日期+状态（%d 条）'
              % len(wl.get('plans', [])))
        check('不进判据' in str(wl.get('note', '')),
              '阴性: 在研计划必须明示"内容未定不进判据"，防止拿草案当依据')


def layer1_76():
    """全站对外数量断言必须等于真相源现算值——锚点内外一视同仁。

    ── 为什么加这道闸门 ──

    L1.62（线上数字核验）当轮报「17 页 + 3 接口全绿，0 项未核验」，
    同一时刻线上真实情况却是：

        data-hub.html          「9 大品类 435+ 实体」   真值 708 → 低报 39%
        credits.html           「查询 577 条…实体数据」 真值 708 → 低报 18%
        16 篇文章底部 CTA       「收录 688 个…实体」     真值 708
        articles/index.html    「基于 688 个实体」×6    含 meta/og/twitter/JSON-LD
        mcp-guide / promotion / promo-poster  同族 688

    L1.62 不是失灵，是**它按 data-rp 锚点解析，而这些数字全在锚点之外**。
    于是「核验器覆盖 17 页」被当成了「17 页都被核验」——本项目"口径≠事实"
    家族的又一次现形：**覆盖面不等于覆盖率，未被扫描到的不叫通过。**

    ── 判据 ──

    扫描全站 HTML（根目录 + articles/），剥掉由 facts() 整体重生成的
    LD / MARK 区块后，任何位置（正文、meta 属性、JSON-LD、锚点内）出现的
    「N 个/条 实体」「N 个开源组件」都必须等于真相源现算值。
    约数写法（`700+`）同样判错——它今天对，涨到 800 就变低报，
    而没有任何机制会提醒。
    """
    print('\n[L1.76] 全站数量断言 = 真相源现算值（锚点之外同样受管）')
    import re as _re
    # 识别器只有一份（onboarding_block.stale_count_claims），线上核验共用同一个。
    from onboarding_block import (facts as _facts, stale_count_claims,
                                  MARK_START, MARK_END)
    from inject_onboarding import (LD_START, LD_END, refresh_bare_counts,
                                   refresh_anchors, fact_map as _fmap)

    f = _facts()
    total, oss = f['total_entities'], f['oss_total']

    def _strip_managed(t):
        for a, b in ((LD_START, LD_END), (MARK_START, MARK_END)):
            t = _re.sub(_re.escape(a) + r'.*?' + _re.escape(b), '', t, flags=_re.S)
        return t

    def _scan(text):
        return stale_count_claims(_strip_managed(text), total, oss)

    pages = sorted(glob.glob(os.path.join(ROOT, '*.html'))) + \
        sorted(glob.glob(os.path.join(ROOT, 'articles', '*.html')))
    check(len(pages) >= 20, '全站 HTML 扫描面非空（实得 %d 个页面）' % len(pages))

    offenders = {}
    for p in pages:
        with open(p, encoding='utf-8') as fh:
            bad = _scan(fh.read())
        if bad:
            offenders[os.path.relpath(p, ROOT)] = bad
    check(not offenders,
          '阳性: 全站无陈旧数量断言（越权: %s）'
          % ('无' if not offenders else
             '; '.join('%s:%s' % (k, v[0][0]) for k, v in list(offenders.items())[:4])))

    # ---- 非空转自证：拿本次修复前的真实原文实测，闸门必须命中 ----
    pre_fix = [
        '<p>RoboParts 全量机器人零部件数据，9 大品类 435+ 实体。</p>',      # data-hub
        '<p>RoboParts 收录 <strong>688 个机器人零部件实体</strong></p>',   # 16 篇文章 CTA
        '<meta name="description" content="…全部基于 688 个实体的公开数据集撰写。">',
        '通过积分可以查询 577 条机器人零部件实体数据',                      # credits
        '在 700+ 实体、300+ 开源组件里搜索',                                # 15:30 首页改版
    ]
    hit = [s for s in pre_fix if _scan(s)]
    check(len(hit) == len(pre_fix),
          '非空转自证: 修复前的 5 种真实陈旧写法全部被本闸门命中（实得 %d/5）'
          % len(hit))
    check(bool(_scan('<strong>688 个机器人零部件实体</strong>')),
          '阴性: 紧跟 HTML 标签的陈旧数字会被命中（旧保鲜正则正是漏在这里）')
    check(bool(_scan('9 大品类 435+ 实体')),
          '阴性: 约数写法 435+ 判错（今天对不等于明天对）')
    check(bool(_scan('收录 300+ 开源组件')),
          '阴性: 开源组件数同样受管')
    check(not _scan('在 %d 条实体、%d 个开源组件里搜索' % (total, oss)),
          '阳性: 等于真值的裸文本不被误伤')
    check(not _scan('<span data-rp="total_entities3">%d</span> 条实体' % total),
          '阳性: 锚点内等于真值不被误伤')
    check(bool(_scan('<span data-rp="total_entities3">%d</span> 条实体' % (total - 9))),
          '阴性: 锚点内数字与真值不符照样判错（锚点不是免检牌）')
    check(not _scan('本文基于 217 款执行器实测参数，161 家参展企业、314 项展品'),
          '阳性: 非"实体/开源组件"语境的数字不被误伤')

    # ---- 保鲜器行为对照：喂陈旧原文，必须自愈成真值且第二遍无改动（幂等）----
    stale = '收录 <strong>688 个机器人零部件实体</strong>与 300+ 开源组件'
    once = refresh_bare_counts(stale, total, oss)
    check(not _scan(once), '阳性: 保鲜器把陈旧原文改成真值（%s）' % once[:46])
    check(refresh_bare_counts(once, total, oss) == once,
          '阳性: 保鲜器幂等（连跑两次结果一致，否则挂进部署流程即是放大器）')
    anc = '<span data-rp="oss_total2">1</span>'
    check(refresh_anchors(anc, _fmap()) == '<span data-rp="oss_total2">%d</span>' % oss,
          '阳性: 锚点刷新按去尾号的 KEY 取真值（oss_total2 → oss_total）')
    check(refresh_anchors('<span data-rp="not_a_fact">1</span>', _fmap())
          == '<span data-rp="not_a_fact">1</span>',
          '阴性: 真相源里没有的 KEY 原样放过，不猜着改')

    # ---- 精度：子集口径不是全库口径，拿总数去比它就是造假红 ----
    # 本轮实测：llms.txt「451 条实体落在其作用域内」被首版识别器判成
    # 「≠708」。它确实陈旧（真值 469），但**理由是错的** —— 闸门一旦
    # 用错理由判红，修的人就会把好数字改坏。子集另由 L1.77 管。
    check(not _scan('451 条实体落在其作用域内（caee060_relevant: true）'),
          '阳性: 带范围限定语的子集口径不被总数误伤（假红比漏报更致命）')
    check(not _scan('其中 451 条实体已完成标注'),
          '阳性: 「其中 N」子集写法不被误伤')
    check(bool(_scan('覆盖 688 条实体，其中 451 条实体落在作用域内')),
          '阴性: 同句里的全库口径照判，不因旁边有子集而整句放行')


def layer1_77():
    """子集口径也必须现算——没人盯的数字才是最容易烂的那个。

    ── 为什么单独加 ──
    总数有 L2「七处一致」+ L1.76 全站扫描盯着，**子集数字一个都没人盯**：
    它不参与任何一致性比对，也不在任何锚点里。实测 llms.txt 里
    「451 条实体落在 T/CAEE 060 作用域内」写死了三周，真值已是 469（低报 4%），
    而三道闸门全绿。llms.txt 恰恰是 AI 爬虫抓取权重最高的那一份。
    """
    print('\n[L1.77] 子集口径 = 真相源现算值（llms.txt 等无锚点纯文本）')
    import re as _re
    from onboarding_block import facts as _facts
    from inject_onboarding import SUBSET_RULES, refresh_subsets, fact_map as _fmap

    f = _facts()
    fm = _fmap()
    check(bool(SUBSET_RULES), '子集规则表非空（空表 = 本闸门空转）')

    for rel, pat, key in SUBSET_RULES:
        check(key in fm, '子集键 %s 在真相源里（缺失即该数字重新无人维护）' % key)
        path = os.path.join(ROOT, rel)
        src = open(path, encoding='utf-8').read()
        hits = [int(m.group(1)) for m in pat.finditer(src)]
        check(len(hits) >= 1, '%s 中子集规则有命中（零命中=限定语被改，规则失效）' % rel)
        bad = [v for v in hits if v != f[key]]
        check(not bad, '%s 子集 %s 全部等于真值 %d（越权: %s）' % (rel, key, f[key], bad or '无'))

    # 非空转自证：拿修复前的原值喂进去，必须判错并被保鲜器改对
    rel, pat, key = SUBSET_RULES[0]
    stale = '；451 条实体落在其作用域内（`caee060_relevant: true`）。'
    check([int(m.group(1)) for m in pat.finditer(stale)] == [451],
          '非空转自证: 修复前的原文（451）确实被规则命中')
    check(pat.sub(str(f[key]), stale) != stale and str(f[key]) in pat.sub(str(f[key]), stale),
          '非空转自证: 保鲜器把 451 改成 %d' % f[key])
    check(pat.sub(str(f[key]), pat.sub(str(f[key]), stale)) == pat.sub(str(f[key]), stale),
          '幂等: 连跑两次结果一致（挂进部署流程的东西不幂等即是放大器）')
    check(not _re.search(r'\d+(?=\s*条实体落在其作用域内)', '469 条实体在其他语境'),
          '阴性: 限定语不匹配时规则不生效（不拿规则去改无关数字）')
    check(refresh_subsets(fm, write=False) == [],
          '当前工作区已无待改子集（dry-run 无差异，证明上面读到的就是磁盘现状）')

    # 真值本身必须来自现场统计，不是写死
    ents = json.loads(open(os.path.join(ROOT, 'api/entities.json'), encoding='utf-8').read())
    live = sum(1 for e in (ents.get('entities') or [])
               if isinstance(e.get('standard_conformance'), dict)
               and e['standard_conformance'].get('caee060_relevant') is True)
    check(live == f[key],
          'caee060_relevant 真值由实体库现算（实扫 %d == facts %d）' % (live, f[key]))


# ── L1.78 ───────────────────────────────────────────────────────────────────
# 机械 declared 的 standard token 必须是**有出处的**规范编码，不得凭空造。
# 白名单：token → 证明该编码确实被厂商官方文档以 ISO 编码形式列出的深链。
# 加新 token 的唯一合法路径是往这里加一行并附深链 —— 这正是本闸门要制造的摩擦。
MECH_STD_TOKEN_EVIDENCE = {
    'ISO 9409-1-50-4-M6': (
        'https://assets.robotiq.com/website-assets/support_documents/document/'
        'FT300-S_Sensor_Manual_OMRON_TM_PDF_20210301.pdf'),
    'ISO 9409-1-31.5-4-M5': (
        'https://assets.robotiq.com/website-assets/support_documents/document/'
        'FT300-S_Sensor_Manual_OMRON_TM_PDF_20210301.pdf'),
    'ISO 9409-1-40-4-M6': (
        'https://assets.robotiq.com/website-assets/support_documents/document/'
        'FT300-S_Sensor_Manual_OMRON_TM_PDF_20210301.pdf'),
}
# 机械声明的出处主机名白名单：厂商官方资产域 / 标准机构。软文站、聚合站、
# 电商页一律不算 —— 与 L1.75（标准登记表出处白名单）同一条纪律的机械侧。
MECH_SOURCE_HOSTS = (
    'robotiq.com', 'onrobot.com', 'schunk.com', 'ati-ia.com',
    'universal-robots.com', 'iso.org', 'openstd.samr.gov.cn',
)


def _mech_violations(entities):
    """返回 declared 机械声明中不合规的项。静态闸与采编脚本共用这一份判定。"""
    import re as _re
    bad = []
    for e in entities:
        mi = e.get('mechanical_interface')
        if not isinstance(mi, dict) or mi.get('status') != 'declared':
            continue
        std = mi.get('standard')
        if not std and not mi.get('flange'):
            bad.append((e.get('id'), 'declared 却既无 standard 也无 flange'))
            continue
        url = str(mi.get('source_url') or '')
        m = _re.match(r'https://([^/]+)/', url)
        host = m.group(1).lower() if m else ''
        if not host or not any(host == h or host.endswith('.' + h)
                               for h in MECH_SOURCE_HOSTS):
            bad.append((e.get('id'), '出处主机名不在白名单: %r' % (host or url)))
        for tok in (std or []):
            if str(tok).upper().startswith('ISO 9409-1') and tok not in MECH_STD_TOKEN_EVIDENCE:
                bad.append((e.get('id'), '自造/未挂出处的 ISO 编码: %s' % tok))
    return bad


def layer1_78():
    """机械 declared 的编码不得凭空造 —— 造一个编码比少一个编码危险得多。

    ── 为什么加 ──
    本轮采编 SENS-31 时撞上：同一件耦合件 AGC-CPL-065，Robotiq **2019 版官方手册**
    §6.1.1 写作「P.C.D. 56, 8×M4」（无编码），**现行官方知识库**却写作
    「ISO 9409-1-56-8-M4」。两处都是厂商一手出处，命名却不一致。
    若按"厂商说了就录"塞进比对集合，会同时产生两个后果：
      (a) 我方数据集凭空对外发布一个未经标准原文核实的 ISO 编码，而 llms.txt /
          MCP / api 正被 AI 爬虫抓走，错误编码会被当权威抄走；
      (b) 别的厂商对同一孔位用别的写法时，两边 token 对不上 → 假阴。
    L1.75 已经把"标准登记表的日期断言必须挂权威出处"锁死；机械侧的 standard token
    是同一类东西——**它是对外发布的判据**，却一直没人管出处。本闸门补上这一侧。
    """
    print('\n[L1.78] 机械 declared 的 standard 编码必须有出处（不得替标准发明条目）')
    ents = json.loads(open(os.path.join(ROOT, 'api/entities.json'), encoding='utf-8').read())
    entities = ents.get('entities') or []

    check(bool(MECH_STD_TOKEN_EVIDENCE), 'ISO 编码出处表非空（空表 = 本闸门空转）')
    for tok, ev in MECH_STD_TOKEN_EVIDENCE.items():
        check(ev.startswith('https://'), '编码 %s 的出处是 https 深链' % tok)

    declared = [e for e in entities
                if isinstance(e.get('mechanical_interface'), dict)
                and e['mechanical_interface'].get('status') == 'declared']
    check(len(declared) >= 1, '库中存在 declared 机械声明（0 条 = 本闸门无对象可查）')

    bad = _mech_violations(entities)
    check(not bad, '全部 declared 机械声明的编码与出处均合规（违规: %s）' % (bad or '无'))

    # 非空转自证 ①：拿本轮真实撞上的分歧 token 喂进去，必须被拒
    hit = _mech_violations([{'id': 'TEST-56', 'mechanical_interface': {
        'status': 'declared', 'standard': ['ISO 9409-1-56-8-M4'],
        'source_url': 'https://blog.robotiq.com/knowledge/x'}}])
    check(any('ISO 9409-1-56-8-M4' in r for _, r in hit),
          '非空转自证: 未挂出处的 ISO 9409-1-56-8-M4 确实被拒（本轮真实候选）')

    # 非空转自证 ②：合规 token + 二手软文出处 → 必须因主机名被拒
    hit2 = _mech_violations([{'id': 'TEST-BLOG', 'mechanical_interface': {
        'status': 'declared', 'standard': ['ISO 9409-1-50-4-M6'],
        'source_url': 'https://m.imrobotic.com/news/detail/22649'}}])
    check(any('主机名' in r for _, r in hit2), '阳性: 二手软文出处被拒（与 L1.75 同纪律）')

    # 非空转自证 ③：declared 却空内容 → 必须被拒（标签绿、内容空）
    hit3 = _mech_violations([{'id': 'TEST-EMPTY', 'mechanical_interface': {
        'status': 'declared', 'standard': [], 'flange': None,
        'source_url': 'https://assets.robotiq.com/x.pdf'}}])
    check(any('既无 standard' in r for _, r in hit3), '阳性: declared 但无任何可比对尺寸被拒')

    # 阴性对照：合规条目不得被误伤（假红比漏报更致命，见 L1.77 教训）
    check(not _mech_violations([{'id': 'TEST-OK', 'mechanical_interface': {
        'status': 'declared', 'standard': ['ISO 9409-1-50-4-M6'],
        'source_url': 'https://assets.robotiq.com/website-assets/x.pdf'}}]),
          '阴性: 合规条目不被误伤')
    check(not _mech_violations([{'id': 'TEST-ND', 'mechanical_interface': {
        'status': 'not_declared'}}]),
          '阴性: not_declared 条目不在本闸门管辖内（无数据 ≠ 违规）')
    check(not _mech_violations([{'id': 'TEST-PCD', 'mechanical_interface': {
        'status': 'declared', 'standard': ['PCD56-8xM4'],
        'source_url': 'https://assets.robotiq.com/x.pdf'}}]),
          '阴性: 非 ISO 前缀的孔位记法不被误判为自造 ISO 编码')

    # 机械维度必须真的能配出对，否则"补了数据"只是自我感动
    with_std = [e for e in declared if e['mechanical_interface'].get('standard')]
    pairs = 0
    for i in range(len(with_std)):
        for j in range(i + 1, len(with_std)):
            if (set(with_std[i]['mechanical_interface']['standard'])
                    & set(with_std[j]['mechanical_interface']['standard'])):
                pairs += 1
    check(not (len(with_std) >= 2 and pairs == 0),
          '≥2 条带尺寸 declared 时至少能配出一对（当前 %d 条 / %d 对）'
          % (len(with_std), pairs))


# ── L1.79 ───────────────────────────────────────────────────────────────────
ENUM_LEDGER = 'ops/intel/standards-enum-ledger.json'
ENUM_MAX_AGE_DAYS = 14


def _load_enum_mod():
    """加载 scripts/enumerate_standards.py —— 标准枚举域的**唯一源**。

    判据（逐来源静默时长 / 失败冷却 / 礼貌间隔）与枚举器执行时用的是同一份代码，
    不在这边另抄一份阈值（手抄两份的下场见 L1.69）。
    """
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location(
        'enumerate_standards', os.path.join(ROOT, 'scripts', 'enumerate_standards.py'))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _enum_verdict_legacy(led, now=None):
    """**修复前的原版判据**，只保留用于阴阳对照，不参与真实判定。

    它只看 `runs[-1]`：任意一个来源跑成功，整本台账就算"新鲜"。
    留着它是为了每轮实测证明「新判据确实能抓到旧判据抓不到的形态」——
    否则新加的闸门可能只是换了个写法的同一句空话。
    """
    import datetime as _dt
    now = now or _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8)))
    runs = (led or {}).get('runs') or []
    if not runs:
        return False, '台账无任何运行记录'
    last = runs[-1]
    if not last.get('scanned'):
        return False, '最近一次运行 scanned=0（等于没拉到表）'
    try:
        at = _dt.datetime.fromisoformat(last['at'])
    except Exception:
        return False, '最近一次运行时间戳不可解析'
    age = (now - at).total_seconds() / 86400
    if age > ENUM_MAX_AGE_DAYS:
        return False, '最近一次枚举距今 %.1f 天 > %d 天' % (age, ENUM_MAX_AGE_DAYS)
    return True, '最近一次枚举距今 %.1f 天，扫描 %d 条' % (age, last['scanned'])


def layer1_79():
    """枚举召回不许退化成口号 —— 建了枚举器却不跑，等于还在搜新闻。

    ── 为什么加 ──
    8/10 查明：T/BTIAIRI 0001-2025 这条与本站命题最贴合的接口标准，
    实施半年多都没被我方碰到，唯一原因是它没上过热搜。当轮的处方是
    「按发布机构枚举全表」，并落成 scripts/enumerate_standards.py。
    但处方本身有个众所周知的死法：**脚本躺在仓库里没人跑**。
    那样一来我方对外仍会说"我们按发布平台枚举"，而事实上召回手段
    早已退回关键词——这正是本项目连咬 9 次的「口径 ≠ 事实」。
    所以枚举必须留下可被机器检查的痕迹（台账），台账陈旧即判红。

    ── 顺带锁死的一条 ──
    台账里的 evidence 只能是**解析成功的真链**或空串，不许出现
    "拼出来的看似合理但打不开"的 URL。首版就吐过这种死链
    （std.samr 的 gbDetailed?id=<检索id> 实测 404）。
    死链比空值危险：它看起来已取证，没人会再点开核。
    """
    print('\n[L1.79] 标准枚举召回必须真的在跑（台账新鲜 + 证据链非伪造）')
    import datetime as _dt

    script = os.path.join(ROOT, 'scripts/enumerate_standards.py')
    check(os.path.exists(script), '枚举器脚本存在 %s' % os.path.relpath(script, ROOT))
    src = open(script, encoding='utf-8').read() if os.path.exists(script) else ''
    # 触发器必须是两因子。只留 SCOPE 单因子会把 LNG 加注连接器判成候选（首版实况）
    check('DOMAIN_RE.search' in src and 'SCOPE_RE.search' in src,
          '触发器是两因子（领域 AND 层面），不是词面命中')
    # ttbz 的 /ms/ 被 robots 禁止；脚本里不许出现对它的抓取
    check('/ms/portal' not in src,
          '未抓取 ttbz.org.cn 的 /ms/ 接口（其 robots.txt 显式 Disallow）')

    path = os.path.join(ROOT, ENUM_LEDGER)
    check(os.path.exists(path), '枚举台账存在 %s' % ENUM_LEDGER)
    if not os.path.exists(path):
        return
    led = json.loads(open(path, encoding='utf-8').read())

    # 逐来源判定（唯一源在枚举器里）
    emod = _load_enum_mod()
    ok, why, states = emod.ledger_verdict(led)
    check(ok, '每个声明来源各自都在被真的枚举（%s）' % why)
    for sk, s in (states or {}).items():
        if s['cooling']:
            print('     ⏳ %s 失败冷却中，%s 后可重试' % (sk, s['cool_until']))
        elif s['due']:
            print('     ▶ %s 已到期该跑：`python scripts/enumerate_standards.py --source %s`'
                  % (sk, 'ndls' if sk == 'tuanbiao' else sk))
        if s['never']:
            print('     ⚠ %s 自声明起从未成功枚举过一次，宽限剩 %.1f 天（到期判红）'
                  % (sk, s['grace_days_left']))

    seen = led.get('seen') or {}
    check(len(seen) > 0, '台账已记录命中条目（0 条 = 枚举空跑）')

    # 死链清零：resolved 的必须是 openstd 深链，unresolved 的必须留空
    faked = [c for c, v in seen.items()
             if v.get('evidence_status') == 'resolved'
             and not str(v.get('evidence', '')).startswith(
                 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=')]
    check(not faked, '标 resolved 的证据都是 openstd 真实详情深链（违规: %s）' % faked)
    ghost = [c for c, v in seen.items()
             if v.get('evidence_status') != 'resolved' and v.get('evidence')]
    check(not ghost, '未解析成功的条目一律留空、不拼假链（违规: %s）' % ghost)

    # ── 对照：不做对照的闸门约等于没有 ──
    now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8)))
    MAX = emod.SOURCE_MAX_AGE_DAYS

    def _run(sk, days_ago, scanned=164):
        return {'at': (now - _dt.timedelta(days=days_ago)).isoformat(),
                'scanned': scanned, 'source_key': sk}

    # 本轮真实缺陷的形态：勤快的 gb 一直在成功，哑掉的团标源一次都没成功过。
    # 旧判据只看 runs[-1] → 绿；新判据逐来源计时 → 红。两者同时断言才叫非空转。
    future = now + _dt.timedelta(days=MAX + 3)
    one_mute = {'runs': [{'at': (future - _dt.timedelta(hours=1)).isoformat(),
                          'scanned': 434, 'source_key': 'gb'}]}
    old_ok, old_why = _enum_verdict_legacy(one_mute, future)
    new_ok, new_why, _ = emod.ledger_verdict(one_mute, future)
    check(not new_ok,
          '阳性: 一个来源勤快在跑、另一个从未成功且超期 → 判红（%s）' % new_why)
    check(old_ok,
          '对照: 同一份台账在**修复前的原判据**下是绿的（%s）—— 证明不是换写法的空转' % old_why)

    stale_all = {'runs': [_run('gb', MAX + 3), _run('tuanbiao', MAX + 3)]}
    check(not emod.ledger_verdict(stale_all, now)[0],
          '阳性: 两个来源都超过 %.0f 天未枚举 → 判红' % MAX)
    empty_scan = {'runs': [{'at': (future - _dt.timedelta(hours=1)).isoformat(),
                            'scanned': 0, 'source_key': sk} for sk in ('gb', 'tuanbiao')]}
    check(not emod.ledger_verdict(empty_scan, future)[0],
          '阳性: scanned=0 的空跑不算成功（时间新 ≠ 真的拉到表）')
    check(not emod.ledger_verdict({'runs': []}, now)[0], '阳性: 无运行记录被判红')
    fresh = {'runs': [_run('gb', 1), _run('tuanbiao', 1)]}
    check(emod.ledger_verdict(fresh, now)[0], '阴性: 两来源都新鲜时不被误伤')
    # 从未成功但还在宽限期内：不许假红（假红比漏报更致命），但必须显式挂账
    # （20260828 修正：此前只喂 gb 的 run，tuanbiao 按 8-10 的 declared_at 已超 14 天
    # 宽限 → 判红是**正确行为**，测试构造不出"宽限期内"形态 → 用台账 declared 覆盖
    # 把两来源声明时间移到今天，复现"新来源刚声明、从未成功"的真实场景）
    grace_led = {'runs': [_run('gb', 0.05)],
                 'declared': {'gb': (now - _dt.timedelta(hours=1)).isoformat(),
                              'tuanbiao': (now - _dt.timedelta(hours=1)).isoformat()}}
    check(emod.ledger_verdict(grace_led, now)[0],
          '阴性: 新声明来源在宽限期内不判红（不制造假红）')
    st_now = emod.source_states(grace_led, now)
    check(st_now['tuanbiao']['never'] and st_now['tuanbiao']['grace_days_left'] is not None,
          '阳性: 但它必须被显式挂账为"从未成功 + 宽限倒计时"，不是当作不存在')
    # 失败冷却必须被如实反映：正在冷却的来源不该被判成"该跑"（否则每小时重试烧配额）
    cooling = {'runs': [_run('gb', 0.05)],
               'attempts': {'tuanbiao': {
                   'at': (now - _dt.timedelta(hours=1)).isoformat(),
                   'status': 'failed', 'reason': 'code=5320'}}}
    check(not emod.source_states(cooling, now)['tuanbiao']['due'],
          '阴性: 1 小时前刚被限流的来源不判"该跑"（冷却 %.0fh）' % emod.FAIL_COOLDOWN_HOURS)
    cooled = {'runs': [_run('gb', 0.05)],
              'attempts': {'tuanbiao': {
                  'at': (now - _dt.timedelta(hours=emod.FAIL_COOLDOWN_HOURS + 1)).isoformat(),
                  'status': 'failed', 'reason': 'code=5320'}}}
    check(emod.source_states(cooled, now)['tuanbiao']['due'],
          '阳性: 冷却期一过就重新判"该跑"（否则失败一次 = 永久放弃该来源）')

    # 登记表侧：淘汰留痕必须给出具体理由，不许写"不相关"了事
    ents = json.loads(open(os.path.join(ROOT, 'api/entities.json'), encoding='utf-8').read())
    audit = (ents.get('meta', {}).get('standard_conformance_spec', {})
             .get('enumeration_audit') or {})
    rejected = audit.get('rejected') or []
    check(len(rejected) > 0, '登记表含枚举淘汰留痕（只记收了什么 = 藏起筛选过程）')
    thin = [r.get('id') for r in rejected if len(str(r.get('reason', ''))) < 12]
    check(not thin, '每条淘汰都写了具体理由（理由过短: %s）' % thin)


# ── L1.80 ───────────────────────────────────────────────────────────────────
TRAINING_DATASET = 'api/training_dataset.json'


def _training_dataset_verdict(ds, truth):
    """把「这份对外训练数据集是不是真相源的当期快照」判成违规清单。

    抽成纯函数是为了能拿**伪造的快照**做阴阳对照 —— 只检查当前文件的闸门，
    在文件碰巧正确时永远绿，无法证明它真的会红。
    """
    bad = []
    if not isinstance(ds, dict):
        return ['数据集不可解析']
    meta = ds.get('meta') or {}
    totals = meta.get('totals') or {}
    if totals.get('entities_total') != truth['entities']:
        bad.append('entities_total=%s ≠ 真相源 %s' % (totals.get('entities_total'), truth['entities']))
    n_std = len(ds.get('standards') or [])
    if n_std != truth['standards']:
        bad.append('standards=%d 条 ≠ 登记表 %d 条' % (n_std, truth['standards']))
    hl = ((meta.get('access') or {}).get('honest_limits') or {})
    if 'mechanical_interface_declared_pct' not in hl:
        bad.append('缺 honest_limits.mechanical_interface_declared_pct（对外产物不许省略诚实边界）')
    elif abs(float(hl['mechanical_interface_declared_pct']) - truth['mech_pct']) > 0.005:
        bad.append('mech_pct=%s ≠ 真相源 %s' % (hl['mechanical_interface_declared_pct'], truth['mech_pct']))
    return bad


def layer1_80():
    """对外派生产物必须与真相源同期 —— 「有出处的过期快照」比没有更糟。

    ── 为什么加（8/10 13:00 实况）──
    `api/training_dataset.json` 是 12:25 手工跑一次导出器生成的 10MB 对外数据集，
    随后 13:46 一次非飞轮部署把它推上了生产，data-hub 页面挂了下载按钮、
    MCP `resources/list` 也把它作为资源推给 agent 自动发现。
    问题是：12:26 那轮刚把标准登记表 10 → 11（补录 GB/T 29825-2013），
    而这份数据集里 `standards` 仍是 **10 条**，且没有任何机制会让它跟上。
    它对外的姿态是"权威结构化数据集"，实质是一张定格在某一分钟的快照。

    这是本项目「口径 ≠ 事实」家族的又一变体，且更隐蔽：
    数字本身当时是对的，是**时间**让它变错的。L2 的七处一致只盯 7 个既有位置，
    新产物不进比对集合 = 无人盯（与 8/9 的 llms.txt 子集口径同型复发）。

    ── 修法 ──
    ① 导出器挂上 deploy.mjs（0b2），与真相源同一时刻重生成；
    ② 本闸门把三项对外数字纳入比对：实体总数 / 登记表条数 / 机械声明率；
    ③ 页面或 MCP 只要还在对外发这个 URL，产物就必须存在（引用与产物成对）。
    """
    print('\n[L1.80] 对外训练数据集必须是真相源的当期快照（派生物不许定格）')

    ents = json.loads(open(os.path.join(ROOT, 'api/entities.json'), encoding='utf-8').read())
    spec = ents.get('meta', {}).get('standard_conformance_spec', {})
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import onboarding_block as _ob
    facts = _ob.facts()
    truth = {
        'entities': ents['meta']['total_entities'],
        'standards': len(spec.get('standards') or []),
        'mech_pct': float(facts['mech_pct']),
    }

    # ① 引用与产物成对：还在对外发链接，就不许没有文件
    referers = []
    for rel in ('data-hub.html', 'functions/mcp.js', 'mcp-guide.html'):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p) and 'training_dataset.json' in open(p, encoding='utf-8').read():
            referers.append(rel)
    path = os.path.join(ROOT, TRAINING_DATASET)
    exists = os.path.exists(path)
    if referers:
        check(exists, '对外已发布该数据集链接（%s），产物必须存在于部署树'
              % '、'.join(referers) + ('' if exists else ' —— 跑 `node scripts/export_training_dataset.mjs`'))
    if not exists:
        return

    # ② 导出器必须挂在部署链路上，否则又退回"记得手工跑"
    dep = open(os.path.join(ROOT, 'scripts/deploy.mjs'), encoding='utf-8').read()
    check('export_training_dataset.mjs' in dep,
          '导出器已挂 deploy.mjs（派生物与真相源同一时刻更新，不靠人记得）')

    ds = json.loads(open(path, encoding='utf-8').read())
    bad = _training_dataset_verdict(ds, truth)
    check(not bad, '数据集与真相源同期（实体%d / 登记表%d条 / 机械%.2f%%）%s'
          % (truth['entities'], truth['standards'], truth['mech_pct'],
             '' if not bad else ' 违规: ' + '; '.join(bad)))

    # ── 阴阳对照：拿伪造快照证明它真的会红 ──
    import copy as _copy
    frozen = _copy.deepcopy(ds)
    frozen['standards'] = (frozen.get('standards') or [])[:-1]
    check(any('standards' in b for b in _training_dataset_verdict(frozen, truth)),
          '阳性: 登记表少一条的定格快照被判红（本轮真实故障形态）')

    lowball = _copy.deepcopy(ds)
    lowball['meta']['totals']['entities_total'] = truth['entities'] - 2
    check(any('entities_total' in b for b in _training_dataset_verdict(lowball, truth)),
          '阳性: 实体总数落后真相源被判红')

    stalepct = _copy.deepcopy(ds)
    stalepct['meta'].setdefault('access', {}).setdefault('honest_limits', {})[
        'mechanical_interface_declared_pct'] = 1.40
    check(any('mech_pct' in b for b in _training_dataset_verdict(stalepct, truth)),
          '阳性: 机械声明率停在上一轮数值被判红（1.40 vs 真值 %.2f）' % truth['mech_pct'])

    nolimit = _copy.deepcopy(ds)
    nolimit['meta'].setdefault('access', {}).pop('honest_limits', None)
    check(any('honest_limits' in b for b in _training_dataset_verdict(nolimit, truth)),
          '阳性: 删掉诚实边界（声明值≠实测值）被判红，不许靠省略变绿')

    check(not _training_dataset_verdict(_copy.deepcopy(ds), truth),
          '阴性: 当期快照不被误伤')


# ---------- L1.81 留痕产出必须机械化，且自查覆盖面 ≥ 静态闸（20260810-19） ----------

def layer1_81():
    """【L1.81】摘要行机械生成 + 写完即跑的自查必须覆盖全部留痕件。

    真实故障（本轮起手，两项红同时爆）：
      ① `_SUMMARY.md` 缺 `20260810-17` 对应行。查下来不是漏写 —— 上一轮**手打**了
         一行 `2026-08-10T18:17 | 第67次 | …`：没有前导 `- `、日期时间用 `T` 连、
         分钟位填的是"写入时刻 18:17"而不是"运行档位 17:00"。写的人以为写了，
         识别器一条都不认。**格式写歪与压根没写，对下游是同一件事。**
      ② DIGEST-CLAIM 停在上一轮的 `@16:53`，早于最新小时报告 `-17`。

    8/10 那轮已立结论「凡靠人记得写的，等于迟早不写」，并为**声明**做了机械盖章；
    但摘要行仍是手打 —— 同一个病只治了一半，另一半立刻复发。更关键的是当时的
    `--verify-latest` 只查声明一件事：**自查的覆盖面小于闸门的覆盖面时，自查就是
    安慰剂** —— 跑了也绿，真正拦住的还是下一轮 regression，时序倒挂原样保留。

    故本闸门锁两件事，缺一不可：
      - 产出侧：`append_summary` 机械生成（幂等、拒非法字段、`--hour` 归零分钟位）。
      - 校验侧：`check_trace` 必须覆盖留痕四件套，且能对**本轮真实故障形态**判红。

    照例阴阳对照：既证明它抓得住真故障，也证明它不误伤正常状态。
    """
    print('\n[L1.81] 留痕产出机械化 + 自查覆盖面 ≥ 静态闸')

    dd = _load_dd()
    import tempfile as _tf
    import shutil as _sh
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz

    # ── 产出侧：生成的形状必须被识别器认（run-67 正是断在这一环）────────────
    line = dd.summary_line('修A', '提B', '待C', now=_dt(2026, 8, 10, 17, 42))
    check(dd.SUMMARY_REC_RE.match(line) is not None,
          '阳性: append_summary 产出的行必被 _SUMMARY 识别器命中（产出↔识别闭环）')

    hline = dd.summary_line('修A', '提B', '待C', now=_dt(2026, 8, 10, 17, 42), hour='17')
    check(hline.startswith('- 2026-08-10 17:00 |'),
          '阳性: --hour 把分钟位归零（摘要行标的是运行档位，不是写入时刻）')

    bad_shape = '2026-08-10T18:17 | 第67次 | 修复台账路径不一致'
    check(dd.SUMMARY_REC_RE.match(bad_shape) is None,
          '阴性: 上一轮手打的真实坏格式不被识别（证明"格式写歪=没写"这条判定为真）')

    try:
        dd.summary_line('含|竖线', 'x', 'y')
        _ok_pipe = False
    except ValueError:
        _ok_pipe = True
    check(_ok_pipe, '阳性: 字段含 | 被拒（否则一行被劈成两条记录，下游静默错乱）')

    # ── 机读标记必须**全部**有机械入口（20260811-04 补）────────────────────
    # run-73 的教训：_LATEST.md 挂两个机读标记，DIGEST-CLAIM 有 --stamp 自动补，
    # TODO-COUNT 却一直靠手打，重写 _LATEST.md 时静默丢失。
    # 「唯一入口只覆盖了一半」比"完全没有入口"更危险——它会让人以为已经机械化了。
    check(hasattr(dd, 'stamp_todo'),
          '阳性: TODO-COUNT 也有机械盖章入口 stamp_todo（不再靠手打）')
    _dd_src = read_text(os.path.join(ROOT, 'scripts', 'digest_due.py'))
    _stamp_body = _dd_src.split("if '--stamp' in sys.argv:")[-1].split('return 0')[0]
    check('stamp_todo()' in _stamp_body and 'stamp_latest(' in _stamp_body,
          '阳性: 一次 --stamp 盖齐两个标记（入口覆盖面 == 闸门检查面）')
    if hasattr(dd, 'stamp_todo'):
        _t0 = '正文\n\n<!-- TODO-COUNT: 999 -->\n<!-- TODO-COUNT: 998 -->\n'
        _t1, _l1 = dd.stamp_todo(text=_t0)
        _t2, _l2 = dd.stamp_todo(text=_t1)
        check(_t1 == _t2 and len(dd.TODO_COUNT_RE.findall(_t1)) == 1,
              '阳性: stamp_todo 幂等且收敛到唯一标记（连跑两次零差异）')
        check(_l1 == '<!-- TODO-COUNT: %d -->' % dd.open_todo_count(),
              '阳性: 待办数现算自 _NEEDS_USER.md，不采信正文里的手打值（实得 %s）' % _l1)

    # ── 校验侧：拿临时目录构造完整留痕现场，验证 check_trace 的行为 ──────────
    tmp = _tf.mkdtemp(prefix='rp_trace_')
    try:
        def _scene(summary_lines, latest_extra='', hour='17'):
            """造一份留痕现场，返回 check_trace 的红项列表。"""
            for f in os.listdir(tmp):
                os.remove(os.path.join(tmp, f))
            with open(os.path.join(tmp, 'roboparts-20260810-%s.md' % hour),
                      'w', encoding='utf-8') as f:
                f.write('# 报告\n' + 'x' * 120)
            with open(os.path.join(tmp, '_SUMMARY.md'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(summary_lines) + '\n' if summary_lines else '\n')
            with open(os.path.join(tmp, '_LATEST.md'), 'w', encoding='utf-8') as f:
                f.write('运行时间：2026-08-10 %s:00\n\n%s\n' % (hour, latest_extra))
            now = _dt(2026, 8, 10, 17, 30, tzinfo=_tz(_td(hours=8)))
            # 合成场景用 2026-08-10 时间戳，必须注入同档 last_raw，
            # 否则 check_trace 会读真实的 _last_digest.txt（常为今天）把 skipped 判成漏报。
            return [m for ok, m in dd.check_trace(
                now=now, res_dir=tmp,
                last_raw='2026-08-10T17:20:00+0800') if not ok]

        good_sum = dd.summary_line('a', 'b', 'c', now=_dt(2026, 8, 10, 17, 0))
        claim = dd.claim_line('skipped', now=_dt(2026, 8, 10, 17, 20,
                                                 tzinfo=_tz(_td(hours=8))))
        todo = '<!-- TODO-' + 'COUNT: %d -->' % (dd.open_todo_count() or 0)

        bad = _scene([bad_shape], latest_extra=todo + '\n' + claim)
        check(any('_SUMMARY 对应行' in b for b in bad),
              '阳性: 摘要行格式写歪 → 自查判红（本轮真实故障形态，原自查查不出）')

        bad = _scene([good_sum], latest_extra=todo)
        check(any('DIGEST-CLAIM' in b or '日报声明' in b for b in bad),
              '阳性: 缺日报声明 → 自查判红（覆盖面含声明件）')

        bad = _scene([good_sum], latest_extra=claim)
        check(any('TODO-COUNT' in b for b in bad),
              '阳性: 缺待办数标记 → 自查判红（覆盖面含待办对账件）')

        bad = _scene([good_sum], latest_extra=todo + '\n' + claim, hour='17')
        # 再塞一份更新的报告，_LATEST 运行时间就落后了
        with open(os.path.join(tmp, 'roboparts-20260810-19.md'), 'w', encoding='utf-8') as f:
            f.write('# 报告\n' + 'x' * 120)
        now = _dt(2026, 8, 10, 19, 30, tzinfo=_tz(_td(hours=8)))
        bad2 = [m for ok, m in dd.check_trace(
            now=now, res_dir=tmp,
            last_raw='2026-08-10T17:20:00+0800') if not ok]
        check(any('运行时间' in b and '不早于' in b for b in bad2),
              '阳性: _LATEST 运行时间落后于最新报告 → 判红（对外播报旧结论）')

        ok_scene = _scene([good_sum], latest_extra=todo + '\n' + claim)
        check(not ok_scene,
              '阴性: 留痕齐备的正常现场不被误伤（残留红: %s）' % (ok_scene[:2] or '无'))
    finally:
        _sh.rmtree(tmp, ignore_errors=True)

    # ── 幂等：同档位连写两次仍一条（否则自动任务每轮净增一行）──────────────
    tmp2 = _tf.mkdtemp(prefix='rp_sum_')
    try:
        p = os.path.join(tmp2, '_SUMMARY.md')
        with open(p, 'w', encoding='utf-8') as f:
            f.write('# 历史\n')
        t1, _, r1 = dd.append_summary('x', 'y', 'z', hour='17',
                                      now=_dt(2026, 8, 10, 17, 5), path=p)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(t1)
        t2, _, r2 = dd.append_summary('x2', 'y2', 'z2', hour='17',
                                      now=_dt(2026, 8, 10, 17, 40), path=p)
        n = len([l for l in t2.splitlines() if dd.SUMMARY_REC_RE.match(l)])
        check(r1 is False and r2 is True and n == 1,
              '幂等: 同档位第二次写为**替换**而非追加（实测 %d 条记录）' % n)
        check(t2.endswith('\n'), '追加后仍以换行结尾（L1.21 粘连根因不得复发）')
    finally:
        _sh.rmtree(tmp2, ignore_errors=True)

    # ── 唯一源：静态闸不得自持第二份识别器 ───────────────────────────────
    src = read_text('scripts/regression.py')
    dup = re.findall(r"re\.compile\(r'<!--\\s\*TODO-COUNT", src)
    check(not dup, '静态闸不再自抄 TODO-COUNT 正则（唯一源在 digest_due，手抄两份见 L1.69）')
    check('_load_dd().SUMMARY_REC_RE' in src,
          'L1.21 摘要行识别器引用唯一源（产出与校验同一份形状定义）')

    # ── 唯一入口不得把"用错"翻译成"静默抹历史" ──────────────────────────
    # 事故（run-72）：用 `--summary "…"` 调用（不存在的旗标）→ 被静默忽略 →
    # 三字段回落默认值 '无' → 写出格式完美的 `修复:无 | 提升:无 | 待办:无`
    # → 按档位幂等**替换**掉本该记录的整轮内容 → `--verify-latest` 13 项全绿
    # （它校验的是格式不是内容）。入口越幂等，误用的破坏力越大。
    import subprocess as _sp
    _py, _dd_path = sys.executable, os.path.join(ROOT, 'scripts', 'digest_due.py')

    def _run(*args):
        return _sp.run([_py, _dd_path, '--append-summary'] + list(args),
                       capture_output=True, text=True, cwd=ROOT,
                       encoding='utf-8', errors='replace')

    r = _run('--summary', 'x')
    check(r.returncode == 3 and '无法识别' in (r.stdout + r.stderr),
          '阳性: 未知旗标 --summary 被拒（静默忽略＝整轮历史被一行"无"覆盖）')
    r = _run()
    check(r.returncode == 3 and '三段全空' in (r.stdout + r.stderr),
          '阳性: 三段全空未显式声明时被拒（几乎总是调用姿势错了）')
    r = _run('--hour', '00', '--allow-empty', '--now', '2026-08-29T00:30')
    check(r.returncode == 3 and '棘轮' in (r.stdout + r.stderr),
          '阳性: 棘轮生效——不许用空摘要替换同档位已有的实质内容')
    check(not re.search(r'修复:无 \| 提升:无 \| 待办:无',
                        read_text(os.path.join(ROOT, 'ops', 'results', '_SUMMARY.md'))),
          '_SUMMARY 无"三段全无"的空壳行（有即某轮历史已被抹掉）')
    dd_src = read_text('scripts/digest_due.py')
    check("KNOWN = {'--append-summary'" in dd_src and 'allow-empty' in dd_src,
          '入口自带旗标白名单（新增旗标须同步白名单，否则一样会被静默吞掉）')


def layer1_82():
    """source_tier 必须由证据推导，不得自封 —— 对外信任分级不许注水。

    【20260810-21 · 第 70 次运行】
    L1.70（8/9）修过一次同类问题：「Tier A + 出处仅站点首页」封顶 B，挤掉 88 条。
    但它的入口判据是 `source_url` 存在 —— 于是**根本没有 URL 的条目它一条都看不到**。
    本轮全库实测：tier=A 336 条里，真有深链的仅 48 条，**275 条没有任何 URL**，
    其中包括 source 文本白纸黑字写着 "web aggregation (credibility B)" 却标 A 的条目。

    根因在 enrich_provenance.py：文档字符串定义「Tier A = 有 URL/具名文档，可点开复核」，
    实现却是 `有 source 就 return 'A'`，且那段改动的注释还声称「杜绝指标注水」——
    **反注水的补丁自己就是注水的**。对外 meta.provenance_coverage 因此播报
    traceable_pct=47.32%（真值 12.85%），而该字段正是给 MCP/API 消费方做来源过滤的契约。

    教训（「口径≠事实」第 13 次，也是首次直接对外失实）：
    **闸门只覆盖它当初想到的那一种错法。** L1.70 想到的是「链接不够深」，
    没想到「压根没链接」。故本闸门不枚举错法，改为正面断言：
    库内每一条的 tier 必须等于判据现算值，任何自封都会被逐条抓出。
    """
    print('\n[L1.82] source_tier 由证据推导，不得自封（对外信任分级防注水）')
    import importlib
    gst = importlib.import_module('govern_source_tier')
    doc = load_entities()
    ents = doc['entities']

    # ① 正面断言：全库无自封（不枚举错法，直接比对判据现算值）
    mism = [(e.get('id'), e.get('source_tier'), gst.derive_tier(e)[0])
            for e in ents if e.get('source_tier') != gst.derive_tier(e)[0]]
    check(not mism,
          '全库 source_tier 均等于判据现算值（自封 %d 条%s）'
          % (len(mism), '' if not mism else '：' + ', '.join(
              f'{i}[{o}≠{n}]' for i, o, n in mism[:4])))

    # ② 对外 meta 必须与实体现状一致（播报值不许定格在旧口径）
    cov = doc.get('meta', {}).get('provenance_coverage', {})
    real_a = sum(1 for e in ents if gst.derive_tier(e)[0] == 'A')
    check(cov.get('tier_a_traceable') == real_a,
          'meta.tier_a_traceable(%s) == 实体现算 A 级数(%d)'
          % (cov.get('tier_a_traceable'), real_a))
    check(abs((cov.get('traceable_pct') or 0) - round(real_a * 100.0 / len(ents), 2)) < 0.01,
          'meta.traceable_pct(%s%%) == 现算值(%.2f%%)'
          % (cov.get('traceable_pct'), real_a * 100.0 / len(ents)))
    check('tier_rule' in cov and 'govern_source_tier' in str(cov.get('tier_rule')),
          'meta 显式披露 tier 判据出处（消费方能核对我们按什么给分）')

    # ③ 阳性对照：修复前的真实错误形态必须判红
    check(gst.derive_tier({'source': 'web aggregation (credibility B)'})[0] == 'C',
          '阳性: 无身份聚合来源判 C（本轮真实形态：文本自述 B 却被标 A）')
    check(gst.derive_tier({'source': '厂商目录声明值：ROBOTIS（无原始链接，未核验）'})[0] == 'B',
          '阳性: 具名厂商目录无链接封顶 B（知道去哪找，但点不开）')
    check(gst.derive_tier({'source': 'Research / Community'})[0] == 'C',
          '阳性: 有话无锚点判 C（「有 source 字段」不构成可追溯）')
    check(gst.derive_tier({'name': 'maxon RE 25',
                           'source_url': 'https://www.maxongroup.com'})[0] == 'B',
          '阳性: 厂商首页封顶 B（L1.70 点名形态，合并后仍成立）')
    check(gst.derive_tier({'source': 'RoboParts Bionic Series'})[0] == 'C',
          '阳性: 自造来源判 C（我方自己写的条目名不是外部证据）')

    # ④ 阴性对照：判据不能恒严，否则会把好数据一起改坏（8/9 假红教训）
    check(gst.derive_tier({'source': '官方页面：https://www.hebirobotics.com/actuators'})[0] == 'A',
          '阴性对照: 产品深链仍判 A（不制造假红）')
    check(gst.derive_tier({'name': 'Octo',
                           'source_url': 'https://octo-models.github.io'})[0] == 'A',
          '阴性对照: 项目自有主页仍可 A（L1.70 例外未被本闸门吃掉）')
    check(gst.derive_tier({'source': 'agilityrobotics.com (URL 引用)'})[0] == 'B',
          '阴性对照: 裸域名（无 scheme）识别为根 URL 判 B，不误降为无锚点 C')
    check(gst.derive_tier({'source': 'Tesla 2026 patent filings'})[0] == 'B',
          '阴性对照: 具名主体+可定位材料类型判 B，不与无身份聚合混为一谈')

    # ⑤ 证非空转：拿**修复前的原判据**对同一份数据实测，必须判成绿
    #    （原判据 = 有 source 即 A。若它也能判红，说明本闸门抓的不是新东西）
    def _old_tier(e):
        if not e.get('source'):
            return 'C'
        return e.get('source_tier') or 'A'
    fake = {'id': 'X', 'source': 'web aggregation (credibility B)'}
    check(_old_tier(fake) == 'A' and gst.derive_tier(fake)[0] == 'C',
          '证非空转: 同一条数据在原判据下得 A、新判据下得 C（差异真实存在）')

    # ⑥ 唯一源：判据不得在别处另抄一份
    ep = read_text('scripts/enrich_provenance.py')
    check('from govern_source_tier import' in ep and "return 'A'" not in ep.split('def tier_of')[1][:400],
          'enrich_provenance 引用判据唯一源且已删除「默认盖 A」（手抄两份见 L1.69）')


# ---------- L1.83 对外 meta 文案里的数字必须有锚 ----------
_PCT_TOKEN = re.compile(r'(\d+(?:\.\d+)?)%')


def _meta_pct_claims(meta):
    """递归抽出 meta 全部字符串里的百分比断言 -> [(路径, 数值)]。"""
    found = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f'{path}.{k}')
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f'{path}[{i}]')
        elif isinstance(o, str):
            for m in _PCT_TOKEN.findall(o):
                found.append((path, float(m)))
    walk(meta, 'meta')
    return found


def _pct_anchors(meta, baseline, extra=()):
    """允许出现在文案里的百分比 = 现算/现播的指标值 ∪ 基线台账记录过的历史值。

    别的都算「无锚断言」：既不是现在的事实，也没有任何记录说它曾经是事实。
    """
    anchors = set(float(x) for x in extra)
    cov = meta.get('provenance_coverage', {}) or {}
    for k, v in cov.items():
        if isinstance(v, (int, float)):
            anchors.add(round(float(v), 2))
    for k, v in (cov.get('clean_set') or {}).items():
        if isinstance(v, (int, float)):
            anchors.add(round(float(v), 2))
    for h in (baseline.get('_traceable_history') or []):
        for key in ('value', 'superseded_value'):
            if isinstance(h.get(key), (int, float)):
                anchors.add(round(float(h[key]), 2))
    return anchors


def _unanchored_pcts(meta, baseline, extra=()):
    anchors = _pct_anchors(meta, baseline, extra)
    return [(p, v) for p, v in _meta_pct_claims(meta)
            if not any(abs(v - a) < 0.01 for a in anchors)]


def layer1_83():
    """对外 meta 文案里的百分比必须有锚：要么是现算值，要么台账记过它曾是。

    【20260810-23 · 第 71 次运行】
    上一轮刚把 traceable_pct 从虚报的 47.32% 归位到 12.85%（L1.82），
    但归位用的那段「更正说明」自己是手打的，写着 **「真值 9.46%」**——
    9.46% 是重算中途未合并 L1.70 例外时的中间值，从来不是终值。
    于是线上 `meta.provenance_coverage` 里同时挂着机读字段 12.85 和
    白纸黑字的「真值 9.46%」，**两个数字并排对外打架**，
    而这段文案的全部意义恰恰是「告诉消费方哪个数才是真的」。
    仓库里 regression.py 的注释写的是 12.85%（对的），
    生成器 enrich_provenance.py 写的是 9.46%（错的）—— 上线的是错的那份。

    教训（「口径≠事实」第 14 次）：
    **L1.82 只断言了机读字段，没管紧挨着它的那句人话。**
    L1.76 早就为 HTML 页面立过同一条规矩（数字要机械保鲜、不许手改），
    却没推广到 JSON meta —— 而 meta 的文案正是 MCP/LLM 消费方逐字引用的部分。
    故本闸门不看文案写得对不对，只看**每个百分比是否挂得住锚**：
    要么等于当期现算值，要么等于基线台账记录过的历史值，两者皆非即判红。
    """
    print('\n[L1.83] 对外 meta 文案的百分比必须有锚（不许手打无源数字）')
    doc = load_entities()
    meta = doc.get('meta', {})
    baseline = json.load(open(os.path.join(ROOT, 'scripts', 'quality-baseline.json'),
                              encoding='utf-8'))
    import importlib
    ob = importlib.import_module('onboarding_block')
    facts = ob.facts()
    extra = [facts['mech_pct']]     # meta.access.honest_limits 播报的机械声明率

    # ① 正面断言：库内 meta 全部文案零无锚百分比
    bad = _unanchored_pcts(meta, baseline, extra)
    check(not bad,
          'meta 文案内百分比全部有锚（无锚 %d 处%s）'
          % (len(bad), '' if not bad else '：' + ', '.join(f'{p}={v}%' for p, v in bad[:4])))

    # ② 现算值必须真的出现在更正文案里（不能靠删数字来过闸）
    note = str((meta.get('provenance_coverage') or {}).get('note') or '')
    cur = (meta.get('provenance_coverage') or {}).get('traceable_pct')
    check(f'{cur}%' in note,
          '更正文案播报的是当期现算值 %s%%（不是删数字蒙混）' % cur)

    # ③ 结构：文案必须渲染而非手打（手打的数字不会随重算更新）
    ep = read_text('scripts/enrich_provenance.py')
    check('def build_provenance_note' in ep and "'note': build_provenance_note(" in ep,
          '生成器用渲染函数产出 note（唯一源，非字面量）')
    body = ep.split('def build_provenance_note')[1].split('\ndef ')[0]
    check(not re.search(r"'[^']*\d+\.\d+%", body) and not re.search(r'"[^"]*\d+\.\d+%', body),
          '渲染函数体内无手打百分比字面量（历史值读台账、当期值取现算）')
    check('superseded_value' in json.dumps(baseline, ensure_ascii=False),
          '基线台账登记了断点前的虚数（历史值有唯一出处可读）')

    # ④ 阳性对照：本轮真实故障形态必须判红
    forged = {'provenance_coverage': {'traceable_pct': 12.85,
                                      'note': 'traceable_pct 曾虚报为 47.32%（真值 9.46%）'}}
    check(any(abs(v - 9.46) < 0.01 for _, v in _unanchored_pcts(forged, baseline)),
          '阳性: 中间值 9.46% 判红（本轮真实形态：既非现算值也无台账记录）')
    stale = {'provenance_coverage': {'traceable_pct': 12.85,
                                     'note': '当前可追溯率 47.06%'}}
    check(not _unanchored_pcts(stale, baseline),
          '阴性对照: 台账记过的历史值 47.06% 不判红（谈历史是合法的）')
    drift = {'provenance_coverage': {'traceable_pct': 12.85, 'note': '可追溯率 33.33%'}}
    check(_unanchored_pcts(drift, baseline),
          '阳性: 凭空写的 33.33% 判红（无锚即无源）')

    # ⑤ 阴性对照：不制造假红（8/9 教训——假红比漏报更致命）
    check(not _unanchored_pcts(meta, baseline, extra),
          '阴性对照: 当期真实 meta 全绿（现算值+台账值+机械声明率均获锚）')
    thresh = {'provenance_coverage': {'traceable_pct': 12.85,
                                      'note': 'confidence 上限 0.30，阈值 0.6，共 91 条'}}
    check(not _unanchored_pcts(thresh, baseline),
          '阴性对照: 非百分比数字（阈值 0.30/0.6、条数 91）不误伤')

    # ⑥ 证非空转：拿**冻结的线上历史原文**实测，必须判红
    #
    # 【自证不得锚在会移动的引用上】首版这里写的是 `git show HEAD:api/entities.json`，
    # 提交修复前它是绿的，**提交那一刻 HEAD 就变成修好的版本，自证当场蒸发并永久判红**
    # ——等于断言"仓库现在还带着这个 bug"，而这句话按设计就该在修完后变假。
    # 同型问题 run-70 在 L1.72 上犯过一次（专用自证＝没有自证），本轮换了个形态复发：
    # 那次错在判据太专，这次错在**参照系会动**。自证要拿冻结样本，不能拿活引用。
    LIVE_PRE_FIX_NOTE = (
        '主指标看 traceable_pct（Tier A 可点开复核）；source_pct 含 Tier B 弱归因，仅作过程指标；'
        'Tier C 已显式标注，供 Agent 侧过滤。【2026-08-10 更正】此前实现为「source 字段非空即判 A」，'
        'traceable_pct 曾虚报为 47.32%（真值 9.46%），已按证据重算，'
        '原值留在实体的 source_tier_prev 字段供审计。'
    )
    frozen = {'provenance_coverage': {'traceable_pct': 12.85, 'note': LIVE_PRE_FIX_NOTE}}
    frozen_bad = _unanchored_pcts(frozen, baseline, extra)
    check(any(abs(v - 9.46) < 0.01 for _, v in frozen_bad),
          '证非空转: 2026-08-10 真实上线过的原文实测判红（%s）'
          % (', '.join(f'{v}%' for _, v in frozen_bad[:2]) or '无'))
    # 冻结样本必须真的是"修复前那份"，不许有人把它悄悄改成好数字来过闸
    check('9.46%' in LIVE_PRE_FIX_NOTE and '曾虚报' in LIVE_PRE_FIX_NOTE,
          '冻结样本仍保有故障特征（被改成好数字则自证失去意义）')
    # 当期库内不得再出现该原文（修复不许回滚）
    cur_note = str((meta.get('provenance_coverage') or {}).get('note') or '')
    check('9.46' not in cur_note, '当期 note 不含已废弃的中间值 9.46（修复未回滚）')


# ---------------------------------------------------------------------------
# L1.84 —— sitemap 不得收录任何一层已明确拒绝索引的 URL
# ---------------------------------------------------------------------------

def _page_declares_noindex(html):
    """只认 <meta name="robots"> / <meta name="googlebot"> 里的 noindex 指令。

    刻意不做 'noindex' in html 的子串判断：站内文章完全可能在正文里讨论
    noindex 这个词，按子串判会制造假红 —— 而假红比漏报更致命（8/9 教训），
    因为它会诱导人把本来正确的页面"改好"。
    """
    for tag in re.findall(r'<meta\b[^>]*>', html or '', re.I):
        name = re.search(r'\bname\s*=\s*["\']([^"\']+)["\']', tag, re.I)
        if not name or name.group(1).strip().lower() not in ('robots', 'googlebot'):
            continue
        content = re.search(r'\bcontent\s*=\s*["\']([^"\']*)["\']', tag, re.I)
        if not content:
            continue
        if 'noindex' in [d.strip().lower() for d in content.group(1).split(',')]:
            return True
    return False


def _headers_noindex_paths(headers_text):
    """解析 _headers，返回声明了 X-Robots-Tag: noindex 的路径模式列表。"""
    pats, cur = [], None
    for line in (headers_text or '').splitlines():
        if not line.strip():
            cur = None
            continue
        if not line[0].isspace():
            cur = line.strip()
            continue
        if cur and re.match(r'\s*X-Robots-Tag\s*:', line, re.I):
            if 'noindex' in line.lower():
                pats.append(cur)
    return pats


def _noindex_conflicts(locs, pages, headers_text='', robots_text=''):
    """sitemap 收录、却被某一层显式拒绝索引的路径 → [(path, layer), ...]

    三层信号必须一起看，因为它们互相独立、任一层说 noindex 都会让这条 sitemap
    条目变成自相矛盾的提交：
      ① 页面级 <meta name="robots" content="noindex">
      ② HTTP 头级 _headers 的 X-Robots-Tag: noindex
      ③ robots.txt Disallow（原 L1.8 已覆盖，并入同一判据以免判据分裂成两份）
    """
    import fnmatch
    hdr_pats = _headers_noindex_paths(headers_text)
    disallow = [m.strip() for m in
                re.findall(r'^\s*Disallow:\s*(\S+)\s*$', robots_text or '', re.M)
                if m.strip() and m.strip() != '/']
    out = []
    for p in locs:
        if p in pages and _page_declares_noindex(pages[p]):
            out.append((p, 'meta robots'))
            continue
        if any(fnmatch.fnmatch(p, pat) for pat in hdr_pats):
            out.append((p, 'X-Robots-Tag'))
            continue
        if any(p == d or (d.endswith('*') and p.startswith(d[:-1])) for d in disallow):
            out.append((p, 'robots.txt Disallow'))
    return out


def _sitemap_locs_and_pages():
    """从仓库现状取 sitemap 路径清单 + 其中能落到本地 HTML 的页面正文。"""
    sm = read_text(os.path.join(ROOT, 'sitemap.xml'))
    locs = [l.replace('https://roboparts.cc', '') or '/'
            for l in re.findall(r'<loc>(.*?)</loc>', sm)]
    pages = {}
    for p in locs:
        stem = p.strip('/')
        cands = (['index.html'] if stem == '' else
                 [stem + '.html', os.path.join(stem, 'index.html')])
        for c in cands:
            fp = os.path.join(ROOT, *c.split('/'))
            if os.path.exists(fp):
                pages[p] = read_text(fp)
                break
    return locs, pages


def layer1_84():
    """守护 20260811-00 修复的 SEO 事故（"闸门只管到它看得见的那一层"第 2 次）。

    事故：/supplier-admin 页面自带 <meta name="robots" content="noindex,nofollow">
    （管理后台，意图正确），但 sitemap.xml 同时把它作为待抓 URL 提交，priority 0.6，
    自 2026-07-27 起一直在线。对搜索引擎而言这是自相矛盾的两个信号，GSC 会记为
    「已提交的网址被标记为 noindex」错误——受损的不是这一页，而是**整份 sitemap 的
    可信度**，连带压低全站抓取预算。

    为什么没被拦住：L1.8 早在"robots.txt Disallow 与 sitemap 互相矛盾"事故后立过
    同一条规矩，但只覆盖了 robots.txt 那一层；页面级 meta robots（更强、更常用）
    与 HTTP 头级 X-Robots-Tag 从来没人看。判据只长到它当初被写出来的那一层。

    不变式：sitemap 收录的每个 URL，在三层索引指令上都不得出现 noindex。
    """
    print('\n[L1.84] sitemap 不得收录任何一层已声明 noindex 的 URL（防自相矛盾的提交）')

    locs, pages = _sitemap_locs_and_pages()
    headers_text = read_text(os.path.join(ROOT, '_headers'))
    robots_text = read_text(os.path.join(ROOT, 'robots.txt'))

    # ① 正面断言：当期仓库零冲突
    conflicts = _noindex_conflicts(locs, pages, headers_text, robots_text)
    check(not conflicts,
          'sitemap 全部 %d 条 URL 无 noindex 冲突（冲突: %s）'
          % (len(locs), [f'{p}←{w}' for p, w in conflicts[:4]] or '无'))

    # ② 覆盖面：sitemap 里的页面型 URL 必须真的被读到，否则"零冲突"只是没看
    page_like = [p for p in locs
                 if not re.search(r'\.(json|txt|xml)$', p) and p != '/articles']
    unseen = [p for p in page_like if p not in pages]
    check(not unseen,
          '每条页面型 URL 都取到了本地正文（未取到=判据没看见: %s）' % (unseen[:4] or '无'))
    # 阈值取 35 而非当期值 40：卡在边界上的断言会在任何一次合法下架时以错误的理由变红
    check(len(pages) >= 35, f'实际参与体检的页面数 {len(pages)} ≥ 35（防判据空转）')

    # ③ 阴性对照：不制造假红
    check(not _noindex_conflicts(['/x'], {'/x': '<meta name="robots" content="index,follow">'}),
          '阴性: 声明 index,follow 的页面不判红')
    check(not _noindex_conflicts(['/x'], {'/x': '<p>本文讲解 noindex 的用法</p>'}),
          '阴性: 正文出现 noindex 字样但无 meta 指令的页面不判红（防假红）')
    check(not _noindex_conflicts(['/x'], {'/x': '<meta name="description" content="noindex">'}),
          '阴性: noindex 出现在非 robots 的 meta 里不判红')
    check(not _noindex_conflicts([], {'/order': '<meta name="robots" content="noindex">'}),
          '阴性: 页面 noindex 但未进 sitemap 不判红（这正是正确姿势）')

    # ④ 阳性对照：三层各自都必须能判红
    check(_noindex_conflicts(['/x'], {'/x': '<meta name="robots" content="noindex,nofollow">'}),
          '阳性: 页面级 meta robots noindex 判红')
    check(_noindex_conflicts(['/y.txt'], {}, '/y.txt\n  X-Robots-Tag: noindex\n'),
          '阳性: HTTP 头级 X-Robots-Tag noindex 判红')
    check(_noindex_conflicts(['/z'], {}, '', 'User-agent: *\nDisallow: /z\n'),
          '阳性: robots.txt Disallow 判红（并入同一判据，与 L1.8 不再分裂）')
    check(_noindex_conflicts(['/x'], {'/x': "<meta name='googlebot' content='noindex'>"}),
          '阳性: 单引号 + googlebot 变体同样判红（不靠固定写法蒙混）')

    # ⑤ 证非空转：拿**冻结的线上原文**实测，必须判红
    #    冻结而非现读，理由见 L1.83——自证不能锚在会随修复移动的引用上。
    FROZEN_LOC = '/supplier-admin'
    FROZEN_HTML = ('<!DOCTYPE html><html><head><meta charset="UTF-8">\n'
                   '<meta name="robots" content="noindex,nofollow">\n'
                   '<title>供应商后台</title></head><body></body></html>')
    frozen_hit = _noindex_conflicts([FROZEN_LOC], {FROZEN_LOC: FROZEN_HTML})
    check(bool(frozen_hit),
          '证非空转: 2026-07-27 起真实上线的 /supplier-admin 原样实测判红（%s）'
          % (frozen_hit[0][1] if frozen_hit else '未判红'))
    check('noindex' in FROZEN_HTML and 'robots' in FROZEN_HTML,
          '冻结样本仍保有故障特征（被改成好数字/好标签则自证失去意义）')

    # ⑥ 修复不许回滚
    sm_now = read_text(os.path.join(ROOT, 'sitemap.xml'))
    check('<loc>https://roboparts.cc/supplier-admin</loc>' not in sm_now,
          'sitemap 未把 /supplier-admin 加回（修复未回滚）')
    check(_page_declares_noindex(read_text(os.path.join(ROOT, 'supplier-admin.html'))),
          'supplier-admin 页面仍保持 noindex（修的是 sitemap，不是把后台放出去收录）')
    check('Disallow: /supplier-admin' not in robots_text,
          '未改用 robots.txt Disallow 兜底（Disallow 会挡住爬虫读 noindex，适得其反）')


# ---------- L1.85 机械兼容不得把「同侧一致」当成「可对接」（20260811-03） ----------
def layer1_85():
    """【L1.85】一个布尔值不能同时承担两种物理关系。

    缺陷：机械维度只做「身份键集合求交」，交集非空即输出
    `compatible=true / 共享机械接口`。但库里所有 standard/flange 记录的都是
    **机器人侧（安装侧）**——Robotiq FT 300-S 官方手册 §5.5 写死
    "couplings … for fixation on the Robotiq device side / robot side screws and
    dowel pins are not provided"，而传感器装到耦合件上用的是 M4 螺钉，不是 50-4-M6。
    所以取值相同只证明**能装在同一法兰上（可互换）**，不证明**能彼此对接（可堆叠）**。

    爆炸半径同样在明天：今天只有 ACT-028 / SENS-31 一对有身份键（且恰好真能堆叠），
    但补机械数据是既定路线（fill_pct 1.68% → 更高），届时每一对同法兰工具件
    （两只夹爪 / 两个力传感器）都会输出 compatible:true —— 夹爪装不到夹爪上。
    与 20260809-02 的 mount_type 假绿同型：假绿随数据覆盖率线性增长，
    必须在补数据之前拆开两种关系。

    不变式：
      · 只有「一方工具侧 == 另一方安装侧」才可以说可对接（relation=mateable）；
      · 「双方安装侧相同」只能说可互换（relation=interchangeable），且必须显式声明
        对接关系不判定；
      · 侧别不齐（只声明工具侧）判 null，不得塌成 false（假红）；
      · BOM 的「可互换选型」分组不得把仅靠对接成立的配对并进去。
    """
    print('\n[L1.85] 机械维度必须区分「可互换（同侧一致）」与「可对接（工具侧↔安装侧）」')

    eng = read_text(os.path.join(ROOT, 'functions', '_lib', 'compat_engine.js'))
    ncode = re.sub(r'^\s*\*.*$|^\s*//.*$', '', eng, flags=re.M)   # 去注释再判定

    # ① 引擎侧静态断言：两种关系都要有名字，且工具侧字段真的参与求交
    check("relation: 'mateable'" in ncode and "relation: 'interchangeable'" in ncode,
          '引擎对外透出 relation（mateable / interchangeable），不再只给一个布尔')
    check('MECH_TOOL_IDENTITY_FIELDS' in ncode and 'tool_side' in ncode,
          '存在工具侧身份键字段（tool_side）')
    check(re.search(r'ea\.tool\.filter\(p\s*=>\s*eb\.robot\.includes\(p\)\)', ncode) is not None
          and re.search(r'eb\.tool\.filter\(p\s*=>\s*ea\.robot\.includes\(p\)\)', ncode) is not None,
          '对接判据是「工具侧 ∩ 对方安装侧」且双向（非同侧自比）')
    check(re.search(r"notes:\s*'共享机械接口", ncode) is None,
          '旧措辞「共享机械接口」已下线（它同时被读成可互换与可对接）')

    # ② 消费侧：BOM 的可互换分组必须排除「仅可对接」的配对
    bom = read_text(os.path.join(ROOT, 'functions', 'api', 'bom', 'check.js'))
    nbom = re.sub(r'^\s*\*.*$|^\s*//.*$', '', bom, flags=re.M)
    check("relation === 'mateable'" in nbom,
          'BOM 识别 relation=mateable')
    check(re.search(r'overall_compatible\s*===\s*true\s*&&\s*!mateableOnly\(m\)', nbom) is not None,
          '并查集连通条件已排除仅可对接的配对（否则把力传感器当夹爪的替代品）')

    # ③ 行为对照实跑：静态断言只能证明「写了」，证不了「判对了」。
    #    harness 里含冻结的修复前实现，用同一输入复现缺陷，防判据空转。
    harness = os.path.join(ROOT, 'scripts', 'verify_mech_sides.mjs')
    if not os.path.exists(harness):
        check(False, '存在 scripts/verify_mech_sides.mjs 行为对照')
    else:
        node = _find_node()
        if not node:
            print('  ⏭️  未找到 node，跳过行为对照（静态断言仍已执行）')
        else:
            try:
                r = subprocess.run([node, harness], cwd=ROOT, capture_output=True,
                                   text=True, encoding='utf-8', errors='replace', timeout=90)
                out = (r.stdout or '') + (r.stderr or '')
                check(r.returncode == 0 and '机械侧别行为对照全部通过' in out,
                      '行为对照实跑通过（阳性 3 + 阴性 3 + 真实库覆盖面 + 端到端透传）')
                check('judgePair 输出携带 relation=interchangeable' in out,
                      '端到端：relation 活到 judgePair 输出（首版只改 evalDimension，'
                      '线上实测机读字段丢失、只剩 notes 那句人话）')
                check('修复前实现复现缺陷' in out and '❌' not in out.split('修复前实现复现缺陷')[0],
                      '证非空转：冻结的修复前实现对同一输入确实判成无关系类型的「共享机械接口」')
            except Exception as e:                                  # noqa: BLE001
                check(False, f'机械侧别行为对照执行失败: {e}')


# ---------------------------------------------------------------------------
# L1.86：凡以「发现渠道」为出处的标准条目，字段必须逐字挂得住详情页原文快照
# ---------------------------------------------------------------------------
_SNAP_PATH = os.path.join(ROOT, 'ops', 'intel', 'standards-evidence-snapshots.json')
# 这些主机既是枚举器的发现渠道、又被允许当取证出处 —— 正因为二者同源，
# 才必须额外挂快照做逐字比对。其余白名单主机（ttbz/openstd/iso…）不是发现渠道，
# 天然有"检索到 → 另去官方页核对"这一步交叉验证，不受本闸门约束。
_DUAL_ROLE_HOSTS = {'ndls.org.cn', 'www.ndls.org.cn'}

_SNAP_FIELDS = (('name', 'name'), ('status', 'status'),
                ('issued_at', 'issued_at'), ('effective_at', 'effective_at'))


def _snap_digest(rec):
    keys = ('std_no', 'name', 'status', 'issued_at', 'effective_at', 'administered_by')
    payload = '|'.join(str(rec.get(k, '')) for k in keys)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]


def _snap_audit(spec, snaps):
    """返回 (缺快照的 id, 字段与快照不符的 (id, 字段, 登记值, 快照值))。纯函数，供阴阳对照复用。"""
    from urllib.parse import urlparse
    no_snap, mismatch = [], []
    table = (snaps or {}).get('snapshots') or {}
    for s in (spec or {}).get('standards', []):
        host = (urlparse(str(s.get('evidence') or '')).hostname or '').lower()
        if host not in _DUAL_ROLE_HOSTS:
            continue
        rec = table.get(s.get('id'))
        if not rec:
            no_snap.append(s.get('id'))
            continue
        for sk, rk in _SNAP_FIELDS:
            a, b = str(s.get(sk) or ''), str(rec.get(rk) or '')
            if a != b:
                mismatch.append((s.get('id'), sk, a, b))
    return no_snap, mismatch


def layer1_86():
    """发现渠道 == 取证渠道时，字段必须挂得住详情页原文快照（逐字比对）。

    ── 为什么加这道闸门 ──

    团标召回缺口连续多轮未闭合，本轮靠 ndls.org.cn（国家数字标准馆）整表枚举
    一次性打通：799 条团标进入作用域判定，抓到 T/CAMETA 40004-2021
    《协作机器人末端接口技术条件》—— 登记表里第一条正面命中"腕关节 ↔ 末端执行器
    对接"这个本站核心命题的国内现行标准，而它**从未上过任何热搜**。

    但闭合方式带来一个新风险：**发现它的渠道，和给它做证的渠道，是同一个。**
    此前白名单（ttbz/openstd/iso…）隐含着一层没人写下来的保护 —— 那些源都不是
    发现渠道，所以流程天然是"关键词搜到 → 另去官方页核对"，有两双眼睛。
    ndls 一进来这层保护就消失了：枚举器若把「公布日期」解析成「发布日期」，
    登记表照抄，没有任何环节会发现。

    ── 判据 ──

    以 ndls 为出处的条目，必须在 ops/intel/standards-evidence-snapshots.json
    有一份**独立二次抓取**的详情页原文快照（不复用枚举器的解析结果），
    且 name/status/issued_at/effective_at 四项逐字一致；快照自身带 sha256 摘要，
    事后手改快照来"迁就"登记表同样判红。

    这道闸门的立意是：放宽白名单可以，但必须同时补上被放宽掉的那次交叉验证。
    """
    print('\n[L1.86] 发现渠道==取证渠道的条目，字段必须逐字挂得住详情页原文快照')

    data = load_entities()
    spec = (data.get('meta') or {}).get('standard_conformance_spec') or {}

    check(os.path.exists(_SNAP_PATH),
          '存在取证快照台账 ops/intel/standards-evidence-snapshots.json')
    if not os.path.exists(_SNAP_PATH):
        return
    snaps = json.loads(read_text(_SNAP_PATH))
    table = snaps.get('snapshots') or {}
    check(len(table) > 0, '快照台账非空（实得 %d 条）' % len(table))

    # ① 快照自身完整性：摘要必须自洽（防止事后手改快照去迁就登记表）
    tampered = [k for k, r in table.items() if _snap_digest(r) != r.get('digest')]
    check(not tampered, '阳性: 每条快照的 sha256 摘要与其受控字段自洽（被改动: %s）'
          % (tampered or '无'))
    lacking = [k for k, r in table.items()
               if not all(r.get(x) for x in ('source_url', 'fetched_at', 'source_tier'))]
    check(not lacking, '阳性: 每条快照都记录了来源 URL / 抓取时间 / 来源层级（缺: %s）'
          % (lacking or '无'))

    # ② 登记表 ↔ 快照：逐字比对
    no_snap, mismatch = _snap_audit(spec, snaps)
    check(not no_snap, '阳性: 以发现渠道为出处的条目均已挂快照（缺: %s）' % (no_snap or '无'))
    check(not mismatch, '阳性: 日期/状态/名称与详情页原文逐字一致（不符: %s）'
          % (mismatch or '无'))

    covered = [s.get('id') for s in spec.get('standards', [])
               if 'ndls.org.cn' in str(s.get('evidence') or '')]
    check(len(covered) >= 4,
          '覆盖面: 本闸门实际约束着 %d 条登记表条目（本轮团标入库批次）' % len(covered))

    # ③ 阴性对照 —— 三种真实会发生的错法，闸门必须都能拦
    good_snap = {'snapshots': {'T/X 1-2020': {
        'std_no': 'T/X 1-2020', 'name': 'N', 'status': '现行',
        'issued_at': '2020-01-01', 'effective_at': '2020-02-01',
        'administered_by': 'Z', 'source_url': 'u', 'fetched_at': 't', 'source_tier': 's'}}}
    ndls_ev = 'https://www.ndls.org.cn/standard/detail/x'

    n1, m1 = _snap_audit({'standards': [
        {'id': 'T/X 1-2020', 'name': 'N', 'status': '现行', 'issued_at': '2020-01-05',
         'effective_at': '2020-02-01', 'evidence': ndls_ev}]}, good_snap)
    check(len(m1) == 1 and m1[0][1] == 'issued_at',
          '阴性: 发布日期与原文差 4 天即判红（这正是"新闻稿时间戳"两次事故的形态）')

    n2, _ = _snap_audit({'standards': [
        {'id': 'T/NOT-SNAPSHOTTED 9-2026', 'status': '现行', 'evidence': ndls_ev}]}, good_snap)
    check(len(n2) == 1, '阴性: 以发现渠道为出处却没有快照，判红')

    tamper = json.loads(json.dumps(good_snap))
    tamper['snapshots']['T/X 1-2020']['digest'] = _snap_digest(
        tamper['snapshots']['T/X 1-2020'])
    tamper['snapshots']['T/X 1-2020']['issued_at'] = '2020-01-05'   # 改字段不改摘要
    check(_snap_digest(tamper['snapshots']['T/X 1-2020'])
          != tamper['snapshots']['T/X 1-2020']['digest'],
          '阴性: 事后手改快照迁就登记表，摘要自洽性立刻失守')

    # ④ 阴性（不该判红的）：非发现渠道出处的条目不受本闸门约束，不得误伤
    n4, m4 = _snap_audit({'standards': [
        {'id': 'GB/T 29825-2013', 'issued_at': '2013-11-12', 'status': '现行',
         'evidence': 'https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=X'}]}, good_snap)
    check(not n4 and not m4,
          '阴性(不该红): openstd 等非发现渠道出处不强制快照，无误伤')

    # ⑤ 非空转自证：白名单放宽却不配快照 —— 也就是"只放水不补验证"那种改法
    check(_std_evidence_host_ok('https://www.ndls.org.cn/standard/detail/x'),
          '前置: ndls 已进出处白名单（放宽的代价由本闸门承担）')
    n5, _ = _snap_audit(spec, {'snapshots': {}})
    check(len(n5) >= 4,
          '非空转自证: 若快照台账为空，本轮 %d 条 ndls 出处条目全数判红（证明它真的在管事）'
          % len(n5))


# ---------------------------------------------------------------------------
# L1.87：主动提交给外部引擎的主机，必须先证明它在播本仓内容（20260811-06）
# ---------------------------------------------------------------------------
def _strip_js_comments(src):
    """去掉 // 行注释与 /* */ 块注释。

    闸门只能对"会被执行的代码"下结论。上一批教训（L1.84/L1.61）反复出现同一种假绿：
    判据在注释或字符串里出现，静态扫描就当它已经落地了。
    """
    out = re.sub(r'/\*[\s\S]*?\*/', '', src)
    out = re.sub(r'(?m)^\s*//.*$', '', out)
    out = re.sub(r'(?m)\s//[^\n\'"`]*$', '', out)
    return out


def _promote_parity_audit(promote_src, parity_src):
    """返回问题清单（空 = 合规）。抽成纯函数，才能拿变异源码做阴性对照。"""
    p = _strip_js_comments(promote_src)
    v = _strip_js_comments(parity_src)
    bad = []

    # ① 真的 import 了闸门（不是注释里提一嘴）
    if not re.search(r'import\s*\{[^}]*checkHostParity[^}]*\}\s*from', p):
        bad.append('promote.mjs 未真实 import checkHostParity')

    # ② 顺序：同源校验必须发生在推送 fetch 之前（放在后面 = 先污染再体检）
    m_call = re.search(r'await\s+checkHostParity\s*\(', p)
    m_push = re.search(r'data\.zz\.baidu\.com', p)
    if not m_call:
        bad.append('promote.mjs 未调用 checkHostParity')
    elif m_push and m_call.start() > m_push.start():
        bad.append('checkHostParity 调用点在百度推送 fetch 之后（顺序无效）')

    # ③ fail-closed：不同源必须走"跳过推送"分支，且该分支排在其它跳过条件之前
    m_guard = re.search(r'if\s*\(\s*!\s*parity\.ok\s*\)\s*\{\s*\n\s*note\([^\n]*百度主动推送', p)
    if not m_guard:
        bad.append('缺 fail-closed 分支：!parity.ok 时未跳过百度推送')
    else:
        m_token = re.search(r'else\s+if\s*\(\s*!\s*BAIDU_TOKEN\s*\)', p)
        if m_token and m_guard.start() > m_token.start():
            bad.append('fail-closed 分支排在 BAIDU_TOKEN 判断之后')

    # ④ 主机改写不得因为加闸而被删掉（删了会整批 not_same_site，属于把病治死）
    if 'uu.host = siteHost' not in p:
        bad.append('百度推送的主机改写逻辑丢失')

    # ⑤ 收录查询链接必须用校验过的主机 —— 否则报告继续引导人去查一台假站的收录量
    for eng, pat in (('360', r'so\.com/s\?q=site%3A\$\{([A-Za-z_]+)\}'),
                     ('搜狗', r'sogou\.com/web\?query=site%3A\$\{([A-Za-z_]+)\}'),
                     ('百度', r'baidu\.com/s\?wd=site%3A\$\{([A-Za-z_]+)\}')):
        m = re.search(pat, p)
        if not m:
            bad.append('%s 收录查询链接缺失或被改写' % eng)
        elif m.group(1) != 'parityHost':
            bad.append('%s 收录查询链接用的是 %s，应为 parityHost' % (eng, m.group(1)))

    # ⑥ 闸门实现本身：三条判据齐全，且真相源是本仓文件而不是写死的字面量
    if 'localTitle' not in v or 'readFileSync' not in v:
        bad.append('verify_host_parity.mjs 未以本仓文件为 title 真相源')
    if not re.search(r'status\s*===\s*200', v) or 'notexist' not in v:
        bad.append('verify_host_parity.mjs 缺软 404 判据（不存在路径必须非 200）')
    if 'bom-checker' not in v:
        bad.append('verify_host_parity.mjs 缺深链同源判据')
    for lit in ('开源机器人兼容性平台',):
        if lit in v:
            bad.append('verify_host_parity.mjs 把站点 title 写死了（%s），应现读 index.html' % lit)
    return bad


def layer1_87():
    """【L1.87】把 URL 主动推给搜索引擎之前，必须先证明那台主机在播本仓的内容。

    事故（2026-08-11 06:00 发现）：百度站长验证的主机是 www.roboparts.cc，
    promote.mjs 于是把待推 URL 的主机统一改写成 www —— 这一步按百度的主机精确匹配
    规则是对的。漏掉的是另一件事：www 在阿里云 DNS 有 CNAME 指向 Pages，但**从未
    在 Pages 项目注册为自定义域**，边缘把它路由到了一份旧站（RobotParts DB），且
    任意路径都返回 200 + 同一页首页。于是 8-08 / 8-09 / 8-10 连续三天各 success:10，
    共 30 条 URL 被主动推给百度，抓回去的全是同一页旧首页 —— 主动提交变成了主动
    给自己的域名喂重复内容和软 404。

    元教训（「口径 ≠ 事实」第 16 次的新变种）：前几次是文案与数据打架、是同一次修复的
    两个消费方拿到不同结论；这次是**「我们对这台主机有控制权」被当成了「这台主机在播
    我们的内容」**。百度返回的 not_same_site 只校验主机身份，不校验主机内容；我们把
    它的通过当成了整体通过。凡是对外提交/宣称某主机代表本站的地方，都必须实抓判定。
    """
    print('\n[L1.87] 对外提交前必须实抓证明目标主机与本仓同源（软 404 / 旧站一律拒推）')

    p_path = os.path.join(ROOT, 'scripts', 'promote.mjs')
    v_path = os.path.join(ROOT, 'scripts', 'verify_host_parity.mjs')
    check(os.path.exists(v_path), '存在主机同源闸实现 scripts/verify_host_parity.mjs')
    if not (os.path.exists(p_path) and os.path.exists(v_path)):
        return
    psrc = read_text(p_path)
    vsrc = read_text(v_path)

    # 阳性：生产源码本身必须全部合规
    bad = _promote_parity_audit(psrc, vsrc)
    check(not bad, '阳性: 生产源码通过全部同源闸判据（问题: %s）' % (bad or '无'))

    # 阴性对照 —— 六种真实会发生的改法，闸门必须都拦得住
    neg = [
        ('调用点挪到推送之后（先污染再体检）',
         psrc.replace('const parity = await checkHostParity(BAIDU_SITE);', '')
             .replace('const txt = await r.text();',
                      'const txt = await r.text();\n      const parity = await checkHostParity(BAIDU_SITE);'),
         vsrc),
        ('只在注释里提 checkHostParity',
         psrc.replace("import { checkHostParity } from './verify_host_parity.mjs';",
                      "// import { checkHostParity } from './verify_host_parity.mjs';"),
         vsrc),
        ('去掉 fail-closed 分支',
         psrc.replace("  if (!parity.ok) {\n    note('[百度主动推送] 因主机同源闸未通过，跳过（宁可不推，也不把假站喂给百度）');\n  } else if (!BAIDU_TOKEN) {",
                      '  if (!BAIDU_TOKEN) {'),
         vsrc),
        ('收录查询链接退回 BAIDU_SITE',
         psrc.replace('so.com/s?q=site%3A${parityHost}', 'so.com/s?q=site%3A${BAIDU_SITE}'),
         vsrc),
        ('主机改写被顺手删掉',
         psrc.replace('uu.host = siteHost;', ''),
         vsrc),
        ('闸门把 title 写死不再读本仓',
         psrc,
         vsrc.replace("const homeTitle = localTitle('index.html');",
                      "const homeTitle = 'RoboParts — 开源机器人兼容性平台';")),
    ]
    for name, mp, mv in neg:
        check(bool(_promote_parity_audit(mp, mv)),
              '阴性: 「%s」被判红' % name)

    # 阴性(不该红)：BAIDU_SITE 仍用于主机改写与 API site 参数，属正常用法，不得误伤
    check('site=${BAIDU_SITE}' in _strip_js_comments(psrc),
          '阴性(不该红): BAIDU_SITE 仍作为百度 API 的 site 参数使用，未被本闸门误伤')

    # 非空转自证：拿修复前的原始写法实测，必须命中
    pre_fix = psrc.replace("import { checkHostParity } from './verify_host_parity.mjs';\n", '')
    pre_fix = re.sub(r'\n  // 0\) 【主机同源闸[\s\S]*?\n  // 1\) 百度主动推送',
                     '\n  // 1) 百度主动推送', pre_fix)
    pre_fix = pre_fix.replace('${parityHost}', '${BAIDU_SITE}')
    hits = _promote_parity_audit(pre_fix, vsrc)
    check(len(hits) >= 3,
          '非空转自证: 修复前的原始写法被判红 %d 项（证明它抓得住旧代码的错）' % len(hits))


# ---------------------------------------------------------------------------
# L1.88：枚举器不得把「被挡在门外」自证成「这一类确实没有标准」（20260811-07）
# ---------------------------------------------------------------------------
def _ndls_fixture(total=3, per_year=200):
    """一张形态正常的 ndls 结果集（按年分片，单片不触深度上限）。

    分片是必须的：把几百条塞进同一个年片会命中「需再分片」那道**另一个**真实闸门，
    测出来的红与本闸门无关（首版夹具就踩了这个坑，红得理直气壮却答非所问）。
    """
    years, left, y = [], total, 2025
    while left > 0:
        n = min(per_year, left)
        years.append((y, n)); left -= n; y -= 1
    rows = []
    for yr, n in years:
        rows += [{'a100': 'T/CTEST %d-%d' % (1000 + i, yr), 'a298': '机器人关节接口规范%d' % i,
                  'a104name': '团体标准', 'a000': '现行', 'a101': '%d-01-01' % yr,
                  'a205': '%d-06-01' % yr, 'yf001': 'h%d_%d' % (yr, i),
                  'a826': '25.040.30', 'publicyear': yr} for i in range(n)]

    def transport(body, timeout=30):
        size, page = body.get('size', 50), body.get('page', 1)
        yr = body.get('publicyear')
        sel = [r for r in rows if yr is None or str(r['publicyear']) == str(yr)]
        return {'code': 0, 'data': {
            'count': total, 'results': sel[(page - 1) * size: page * size],
            'aggregations': {'publicyear': {
                'buckets': [{'key': k, 'doc_count': n} for k, n in years]}}}}
    return transport


def layer1_88():
    """【L1.88】标准枚举器必须能区分「这一类没有标准」与「我们被挡在门外」。

    起因（20260811-07 实测）：国家数字标准馆 ndls 前置了加速乐(Jiasule) JS 反爬，
    `/api/standard/list` 不再返回结果集，而是回 `{"visitToken": "..."}`。
    枚举器**照单全收**：total=0 → 年桶为空 → 收 0 条 → `0 == 0` → `complete=True`，
    打印「穷举自证: 0 个年片，实收 0/0 条」，并把 `fully_enumerated: True` 写进台账。
    对一个历史上有 436 条的 ICS 分类，它对外宣称的是"整表过了一遍，一条都没有"。

    根因是一句可以推广的话：**既有三道自证全都在「返回的数据内部」做一致性检查，
    却从没有人验证过「返回的是一张表」这个前提**。前提不成立时，
    内部一致性不会判红，而是各自平凡地成立 —— 自证退化成同义反复。
    抓取失败会重试会告警，假绿会被下游当结论，所以后者贵得多。

    次生危害同样要堵：一次空跑会把 `scan_index[tuanbiao]` 的 799 条扫描面覆盖成 0，
    而扫描面正是回答「这条标准是被筛掉了还是压根没看见」的唯一依据。

    立场：不绕过反爬。对方设卡＝收回授权，正确反应是判红+冷却+另寻合规渠道。
    """
    print('\n[L1.88] 枚举器：空表/挑战页不得自证「穷举」，空扫描面不得抹掉留痕')

    import importlib.util
    p = os.path.join(ROOT, 'scripts', 'enumerate_standards.py')
    check(os.path.exists(p), '存在标准枚举器 scripts/enumerate_standards.py')
    if not os.path.exists(p):
        return
    spec = importlib.util.spec_from_file_location('_enum_std_l188', p)
    E = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(E)
    except Exception as e:
        check(False, '枚举器可导入（实际: %s）' % e)
        return

    def drive(transport, **kw):
        """驱动**生产函数**，只替换传输层（不另抄一份实现来测）。"""
        E.ENUM_COVERAGE.clear()
        E._ndls_post = transport
        try:
            rows = E.enumerate_ndls('25.040.30', page_size=50, max_pages=12, sleep=0, **kw)
            return False, '返回 %d 条 complete=%s' % (
                len(rows), [c['complete'] for c in E.ENUM_COVERAGE])
        except RuntimeError as e:
            return True, str(e)[:70]

    CHALLENGE = {'code': 0, 'data': {'visitToken': 'ndls-platform:VISIT-TOKEN:8a8dfd6c'}}

    # 阳性（不该红）：正常结果集必须照常穷举成功
    red, why = drive(_ndls_fixture(3))
    check(not red, '阳性: 正常结果集正常枚举（%s）' % why)

    # 阴性：五种"拿不到表"的真实形态，必须全部判红
    for name, tr, kw in [
        ('加速乐 visitToken 挑战（真实录制）', lambda b, timeout=30: CHALLENGE, {}),
        ('空表 count=0（杀掉 0==0 同义反复）',
         lambda b, timeout=30: {'code': 0, 'data': {
             'count': 0, 'results': [], 'aggregations': {'publicyear': {'buckets': []}}}}, {}),
        ('缺 results 字段（协议变更）',
         lambda b, timeout=30: {'code': 0, 'data': {'count': 5}}, {}),
        ('data 非对象', lambda b, timeout=30: {'code': 0, 'data': 'nope'}, {}),
        ('相对历史基线缩水 >10%（436→100）', _ndls_fixture(100), {'baseline': 436}),
    ]:
        red, why = drive(tr, **kw)
        check(red, '阴性: 「%s」被判红（%s）' % (name, why if red else '未判红!'))

    # 阴性(不该红)：轻微波动属正常，缩水闸不能严到把正常增删也拦掉
    red, why = drive(_ndls_fixture(420), baseline=436)
    check(not red, '阴性(不该红): 轻微缩水 5%% 放行（%s）' % why)

    # 基线必须取历史最大值：拿退化后的水位当基线，等于把退化认成正常
    b = E.ndls_baselines({'runs': [{'coverage': [{'ics': '25.040.30', 'total': 436}]},
                                   {'coverage': [{'ics': '25.040.30', 'total': 100}]}]})
    check(b.get('25.040.30') == 436, '基线取历史最大值而非最近值（得 %s）' % b)

    # 空扫描面不得覆盖已有留痕（守住 `--why` 的可回答性）
    src = read_text(p)
    check(re.search(r'if\s+new_idx\s+or\s+not\s+prev_idx\s*:', src) is not None,
          '空扫描面保护分支存在（空跑不得把 scan_index 抹成 0）')

    # 非空转自证：拿修复前的判据，喂同一份真实挑战响应，必须复现出假绿
    d = CHALLENGE['data']
    total_old = d.get('count') or 0
    buckets_old = ((d.get('aggregations') or {}).get('publicyear') or {}).get('buckets') or []
    complete_old = (0 == total_old) and not buckets_old   # 原版判据 len(seen_ids)==total
    check(complete_old is True,
          '非空转自证: 修复前判据对同一挑战响应复现「假绿 complete=True」')


# ---------------------------------------------------------------------------
# L1.89：同一个法兰的两种写法，不得被判成「装不上」；也不得被判成「就是同一个」
# ---------------------------------------------------------------------------
def layer1_89():
    """【L1.89】判定侧必须和登记表侧吃同一套书写形式口径（20260811-09）。

    **上一轮只修了一半。** 20260811-08 那轮发现 707 处 `registry_ref` 因写法差异
    （实体 `ISO 9409-1-50-4-M6` 无 A 带空格 vs 登记表 id `ISO9409-1-A50-4-M6`
    有 A 无空格）零命中，于是给登记表补了 aliases 与 normalize_rule。
    但**对用户输出结论的那段代码没动**：`compat_engine.js` 的 `idValues()`
    只做 `trim().toLowerCase()`，实体与实体之间仍是逐字符相等。

    用生产代码实测（修复前）：
        `ISO 9409-1-50-4-M6` × `ISO9409-1-50-4-M6`
        → compatible=**false**，notes「机械接口无交集」
    同一个法兰，只差一个空格，被判"装不上"。这不是"判不了"，是**带着数据外观的
    错误结论** —— 采购方会据此排除掉正确选项，且不会有任何迹象提示他被误导。
    与 20260809-12（数组被 String() 成伪 token 造成假红）同族。

    修复的两条方向相反的不变式，缺一不可：
      ① **纯词法差异必须归一**（大小写 / 空白 / 全角空格 / Unicode 连字符族）——
         这些差异不携带任何语义，允许它们产生结论差异就是制造假红；
      ② **语义未定差异必须判 null**（带 A 与不带 A：尺寸段逐位相同、只差字母前缀）——
         我方未持有 ISO 9409-1:2004 原文，判 true 是凭空断言等价（假绿，且是孔位级
         结论），判 false 是把很可能装得上的说成装不上（假红）。两个方向都是替标准
         做裁决，诚实答案只有第三种：据此判不了，并把分歧讲清楚。

    还锁一条**跨层一致**：登记表的 aliases/normalize_rule 是**查表**便利，
    不是等价断言。若无人写死作用域，下游（含 LLM）极易把"能查到同一行"读成
    "能互相安装"，于是一个便利措施在下游变成孔位级结论 —— 故要求登记表显式声明
    join_scope，且与引擎的 undecided 口径对得上。
    """
    print('\n[L1.89] 机械编码：词法差异不得判「装不上」，语义未定差异不得判死')

    eng_path = os.path.join(ROOT, 'functions', '_lib', 'compat_engine.js')
    if not os.path.isfile(eng_path):
        check(False, 'functions/_lib/compat_engine.js 存在')
        return
    eng = read_text(eng_path)
    ncode = re.sub(r'/\*[\s\S]*?\*/', '', eng)
    ncode = re.sub(r'^\s*//.*$', '', ncode, flags=re.M)

    # ① 引擎侧静态断言：归一化必须在身份键取值那一步生效，不能只写个没人调的工具函数
    check('function normalizeMechToken' in ncode, '引擎存在书写形式归一化函数 normalizeMechToken')
    check(re.search(r'function idValues[\s\S]{0,320}?normalizeMechToken', ncode) is not None,
          '身份键取值 idValues 真的走归一化（不是定义了函数却没人调）')
    check(re.search(r"toLowerCase\(\)\s*\)\s*\n\s*\.filter\(x => x && x !== 'unknown'\)", ncode) is None,
          '旧的 trim().toLowerCase() 取值路径已下线')
    check("relation: 'undecided_designation_form'" in ncode
          and re.search(r"compatible:\s*null[\s\S]{0,200}?undecided_designation_form", ncode) is not None,
          '尺寸段一致、字母前缀不同 → compatible=null（既不判死也不判活）')
    check('function parseIsoFlange' in ncode and 'geomKey' in ncode,
          '存在 ISO 9409-1 编码解析与几何键（判据锚在尺寸段，不靠字符串猜）')

    # ② 跨层一致：登记表必须写死 join 的作用域，且指向引擎的 undecided 口径
    reg_path = os.path.join(ROOT, 'api', 'mechanical_interfaces.json')
    if not os.path.isfile(reg_path):
        check(False, 'api/mechanical_interfaces.json 存在')
    else:
        reg = json.load(open(reg_path, encoding='utf-8'))
        forms = (reg.get('designation_grammar') or {}).get('designation_forms') or {}
        scope = str(forms.get('join_scope') or '')
        check(bool(scope), '登记表已声明 normalize_rule 的作用域 join_scope')
        check('undecided_designation_form' in scope,
              'join_scope 指向引擎的 undecided 口径（两层口径可对账，不各说各话）')
        check('查表' in scope and '等价' in scope,
              'join_scope 明说「仅限查表、不构成等价断言」（防下游把便利读成结论）')

    # ③ 行为对照实跑：静态断言只能证明「写了」，证不了「判对了」。
    #    harness 内含冻结的修复前实现，对同一输入复现假红，防判据空转。
    harness = os.path.join(ROOT, 'scripts', 'verify_mech_designation.mjs')
    if not os.path.exists(harness):
        check(False, '存在 scripts/verify_mech_designation.mjs 行为对照')
        return
    node = _find_node()
    if not node:
        print('  ⏭️  未找到 node，跳过行为对照（静态断言仍已执行）')
        return
    try:
        r = subprocess.run([node, harness], cwd=ROOT, capture_output=True,
                           text=True, encoding='utf-8', errors='replace', timeout=90)
        out = (r.stdout or '') + (r.stderr or '')
        check(r.returncode == 0 and '机械编码书写形式行为对照全部通过' in out,
              '行为对照实跑通过（阳性 6 + 阴性 7 + 解析器 4 + 端到端 3 + 覆盖面 2）')
        check('全部可被 parseIsoFlange 解析' in out,
              '覆盖面：真实库在用的 ISO 编码全部可解析（防判据只对夹具有效）')
        check('修复前实现复现缺陷' in out and '❌' not in out.split('修复前实现复现缺陷')[0],
              '证非空转：冻结的修复前实现对同一法兰的两种写法确实判出 compatible=false')
    except Exception as e:                                          # noqa: BLE001
        check(False, f'机械编码书写形式行为对照执行失败: {e}')


# ---------------------------------------------------------------------------
# L1.90：单实例锁的存活判据不得以 PID 为主判据（20260811-12）
# ---------------------------------------------------------------------------
def layer1_90():
    """【L1.90】飞轮的"存活"必须由心跳证明，不能由 PID 证明。

    **锁写了一整天，一次都没生效过。** v1（提交 d6b076d，标题写着"单实例锁
    根治并发双写"）把 `os.getpid()` 写进锁文件——可 `acquire` 是个打印完就退出的
    辅助命令，飞轮实例本身是一段跨多次工具调用的会话，**根本不存在贯穿全程的
    长活进程**。于是锁文件里的 PID 在写下的下一秒就是 dead，而 v1 判据是
    "PID 确认不存在 → 立刻抢占"，等价于任何后来者任何时刻都能无条件抢占。
    代价：20260811 12:42/12:55 出现两个并非当前实例所做的提交
    （32b3343、300c653），即另一实例全程并发跑完并提交了。

    **它为什么骗过了自测**：v1 的阴性对照是"伪造一个不存在的 pid，期望能抢占"，
    测的恰好是缺陷本身的表现，测试通过反而给缺陷背书。缺的是那条对应现实的用例：
    "上一实例 1 分钟前 acquire（其辅助进程当然已退出），第二实例必须被拒"。

    归类：**代理指标失真** —— 用 A 的生命周期代理 B 的生命周期，而两者根本不同步。
    与 L1.88（空输入下平凡成立的自证）同族：判据在真实形态下恒定取同一个值。
    """
    print('\n[L1.90] 单实例锁：存活由心跳证明，PID 只能加严不能放宽')

    p = os.path.join(ROOT, 'scripts', 'run_lock.py')
    if not os.path.isfile(p):
        check(False, 'scripts/run_lock.py 存在')
        return
    src = read_text(p)

    # ① 静态：必须有心跳字段与续期入口
    check("'heartbeat_at'" in src, '锁记录 heartbeat_at（存活由心跳承载）')
    check(re.search(r"sub\.add_parser\(\s*'renew'\s*\)", src) is not None
          or "add_parser('renew'" in src, '提供 renew 子命令（持锁方可刷新心跳）')
    # ② 静态：DEAD 不得再作为"可抢占"的充分条件
    check(re.search(r"if\s+state\s*==\s*DEAD\s*:\s*\n\s*return\s+True", src) is None,
          'PID==DEAD 不再直接返回「可抢占」（v1 的致命分支已下线）')
    check(re.search(r"if\s+state\s*==\s*ALIVE\s*:[\s\S]{0,200}?return\s+False", src) is not None,
          'PID==ALIVE 仍一律不抢占（PID 只加严）')

    # ③ 行为对照实跑：静态断言只能证明「写了」，证不了「判对了」
    py = sys.executable or 'python'
    try:
        r = subprocess.run([py, p, '--self-test'], cwd=ROOT, capture_output=True,
                           text=True, encoding='utf-8', errors='replace', timeout=120)
        out = (r.stdout or '') + (r.stderr or '')
        check(r.returncode == 0 and '0 失败' in out, '锁自测实跑通过')
        check('第二实例被拒' in out and '❌ 上一实例' not in out,
              '核心用例在跑：上一实例 1 分钟前 acquire → 第二实例被拒')
    except Exception as e:                                          # noqa: BLE001
        check(False, f'锁自测执行失败: {e}')
        return

    # ④ 非空转自证：冻结 v1 判据，对同一现实形态复现「放行」
    #    若 v1 与 v2 在此给出相同答案，说明上面那条用例证明不了任何修复。
    def _v1_decision(pid_state: str, heartbeat_age_min: float, ttl_min: int = 90) -> bool:
        """v1 原判据的冻结复刻：PID 确认不存在 → 可抢占（与心跳无关）。"""
        return pid_state == 'dead'

    v1_says = _v1_decision('dead', 1.0)          # 上一实例 1 分钟前 acquire
    check(v1_says is True,
          '证非空转: 冻结的 v1 判据对同一形态确实放行（＝当初真的在并发双写）')

    try:
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        import importlib
        import datetime as _dt
        rl = importlib.import_module('run_lock')
        importlib.reload(rl)
        now = rl._now()
        fresh = {'owner': 'a', 'pid': 999999, 'label': 't',
                 'started_at': (now - _dt.timedelta(minutes=1)).isoformat(),
                 'heartbeat_at': (now - _dt.timedelta(minutes=1)).isoformat()}
        v2_says = rl._describe(fresh, 30)[0]
        check(v2_says is False and v1_says != v2_says,
              '证非空转: v2 在同一形态下拒绝抢占（两版结论相反，用例有鉴别力）')
    except Exception as e:                                          # noqa: BLE001
        check(False, f'v1/v2 判据对照失败: {e}')



# ---------------------------------------------------------------------------
# L1.91：404 归因的"已对外公布"判据不得用子串匹配（20260811-19）
# ---------------------------------------------------------------------------
def layer1_91():
    """【L1.91】把「更长路径的前缀」误判成「我方已公布」= 制造假红。

    `read_metrics.py` 的 `is_advertised()` 原实现是 `if path in f.read()` 纯子串匹配。
    llms.txt 里公布的是 `/.well-known/mcp.json`，于是探测流量中的
    `/.well-known/mcp`（无 .json，我方从未承诺）被判成
    「P0 我方死链：已对外公布却敲不开」。线上回探实证两者根本不是一条路径：
      /.well-known/mcp.json → 200      /.well-known/mcp → 404

    **假红比漏报更致命**：它会催人去"修"一条本不存在的承诺——最省事的消红办法
    是新建一个我方从未打算提供的 `/.well-known/mcp` 文件，
    等于按错误理由把对外发现面改坏。与 L1.89 同族：**查得到 ≠ 判得对**。

    本闸门测的是生产源码里的那段判据本身（不另抄实现），并要求
    read_metrics 的自测里带**鉴别力自证**：冻结的旧子串实现必须与新实现结论相反。
    """
    print('\n[L1.91] 404 归因：「已公布」须落在路径词元边界，不得子串误命中')

    p = os.path.join(ROOT, 'scripts', 'read_metrics.py')
    if not os.path.isfile(p):
        check(False, 'scripts/read_metrics.py 存在')
        return
    src = read_text(p)

    # ① 静态：旧的纯子串分支必须已下线
    # 只找**代码行**（行首缩进 + if + 结尾冒号）；文档里为了留病历会引用旧代码原文，
    # 不能因为"文档提到了"就判红 —— 那又是一次按错理由判红。
    check(re.search(r'^[ 	]*if\s+path\s+in\s+f\.read\(\)\s*:', src, re.M) is None,
          '旧判据 `if path in f.read():` 代码行已下线（子串误命中来源）')
    check('_mentions_path' in src, '改用词元边界判据 _mentions_path')

    # ② 行为对照实跑：静态只能证明「改了」，证不了「判对了」
    py = sys.executable or 'python'
    try:
        r = subprocess.run([py, p, '--selftest'], cwd=ROOT, capture_output=True,
                           text=True, encoding='utf-8', errors='replace', timeout=120)
        out = (r.stdout or '') + (r.stderr or '')
        check(r.returncode == 0 and '阴阳对照通过' in out, 'read_metrics 判据自测实跑通过')
        check('鉴别力自证' in out and '鉴别力自证失败' not in out,
              '自测含鉴别力自证（旧子串实现与新实现结论相反）')
    except Exception as e:                                          # noqa: BLE001
        check(False, f'read_metrics 自测执行失败: {e}')
        return

    # ③ 直接对生产函数实跑一次真实形态（本轮的原始假红现场）
    try:
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        import importlib
        rm = importlib.import_module('read_metrics')
        manifest = '- 清单文件：`/.well-known/mcp.json` · `/server.json`\n'
        old_says = '/.well-known/mcp' in manifest            # 冻结旧实现
        new_says = rm._mentions_path(manifest, '/.well-known/mcp')
        check(old_says is True and new_says is False,
              '证非空转: 同一清单文本上 旧=已公布(假红) / 新=未公布')
        check(rm._mentions_path(manifest, '/.well-known/mcp.json') is True,
              '真正公布的 /.well-known/mcp.json 仍判已公布（没有一刀切过严）')
    except Exception as e:                                          # noqa: BLE001
        check(False, f'生产函数对照失败: {e}')


def main():
    url = None
    if '--url' in sys.argv:
        url = sys.argv[sys.argv.index('--url') + 1]
    print('=== RoboParts 回归测试 ===')
    layer1()
    layer1_5()
    layer1_6()
    layer1_7()
    layer1_8()
    layer1_9()
    layer1_10()
    layer1_11()
    layer1_12()
    layer1_13()
    layer1_14()
    layer1_15()
    layer1_16()
    layer1_17()
    layer1_18()
    layer1_19()
    layer1_20()
    layer1_21()
    layer1_22()
    layer1_23()
    layer1_24()
    layer1_25()
    layer1_26()
    layer1_27()
    layer1_28()
    layer1_29()
    layer1_30()
    layer1_31()
    layer1_32()
    layer1_33()
    layer1_34()
    layer1_35()
    layer1_36()
    layer1_37()
    layer1_38()
    layer1_39()
    layer1_40()
    layer1_41()
    layer1_42()
    layer1_43()
    layer1_44()
    layer1_45()
    layer1_46()
    layer1_47()
    layer1_48()
    layer1_49()
    layer1_50()
    layer1_51()
    layer1_52()
    layer1_53()
    layer1_54()
    layer1_55()
    layer1_56()
    layer1_57()
    layer1_58()
    layer1_59()
    layer1_60()
    layer1_61()
    layer1_62()
    layer1_63()
    layer1_64()
    layer1_65()
    layer1_66()
    layer1_67()
    layer1_68()
    layer1_69()
    layer1_70()
    layer1_73()
    layer1_74()
    layer1_75()
    layer1_76()
    layer1_77()
    layer1_78()
    layer1_79()
    layer1_80()
    layer1_81()
    layer1_82()
    layer1_83()
    layer1_84()
    layer1_85()
    layer1_86()
    layer1_87()
    layer1_88()
    layer1_89()
    layer1_90()
    layer1_91()
    layer2()
    layer3(url)
    layer4()
    layer_schema_contract()
    print('\n==============================')
    if failures:
        print(f'❌ 阻断：{len(failures)} 项未通过，禁止发布')
        sys.exit(1)
    print('✅ 全部通过，放行发布')
    sys.exit(0)


if __name__ == '__main__':
    main()
