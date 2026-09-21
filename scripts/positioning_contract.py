# -*- coding: utf-8 -*-
"""定位口径契约 —— 「我们对外自称什么」的唯一判据源。

为什么需要这个文件（20260921 补的盲区）
--------------------------------------------------
本轮把全站定位从 **6 套收敛为 1 套**（「机器人零件兼容性判定层」），验收方式是一次
**人工 grep**，结论写在 `docs/positioning-audit-20260921.md:276`：
「仓内：仿生机器人生态平台 = 0 · RobotParts = 0 · 中文圈 = 0 · 133+ = 0」。
问题不在那次 grep 做错了，而在**它是人手做的、只做过一次、没有任何机制承接**：

  · 谁再往任一页面/JSON 里写回「仿生机器人生态平台」，不会有任何东西报警；
  · 更隐蔽的一半是反向的：**源改了、线上没改**。数字轴有
    `scripts/verify_live_numbers.py` 回探（它能抓到"推了 GitHub 没部署"），
    而"我们自称是什么"这一轴线上**完全没有核验** ——
    定位恰恰是比数字更外显的主张：它写在 title / meta / llms.txt / agent-discovery
    这些**最容易被搜索引擎与 AI 抓走二次分发**的位置上。

本仓已经因为「口径 ≠ 事实」连咬 9 次（见 `_NEEDS_USER.md` 的历次订正），共同形状都是
**「检查的粒度小于被检事实，绿灯的含义被悄悄放大」**。这里不重复那个错误：
判据**不手写期望值**，而是让本地源文件自己说话 ——

  ① 退役表述（本文件常量表）：本地 0 命中 + 线上 0 命中；
  ② 本地某文件含定位表述族 → **线上同一路径必须也含**（抓"源改了没部署"）；
  ③ 本地不含的，不作要求（宁漏勿假红）。

消费者（一份定义、两处使用，与 `env_contract.json` 被 L1.94 与 loop_matrix 共用的先例一致）
  · `scripts/ci_gate.py`            —— 离线闸门：`--check` + `--self-test`
  · `scripts/verify_live_numbers.py` —— 线上核验：`positioning_violations()`

CLI
    python scripts/positioning_contract.py --check       # 本地扫描，命中退役表述则 exit 1
    python scripts/positioning_contract.py --self-test   # 阴阳对照自证（含临时目录端到端）
    python scripts/positioning_contract.py --list        # 打印面清单与判据表
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- 判据表

# 已退役表述：任何**可部署面**上出现即为漂移（源里出现是源头脏，线上出现是没部署）
RETIRED = [
    '仿生机器人生态平台',
    '开源机器人兼容性平台',
    '中文圈',
    '对标 TraceParts',
    'RobotParts',          # 另一产品名，曾长期与本站混用
]

# 现行定位表述族：同一主张的合法变体（多一个「的」不算两套口径）
# 注意：'零件兼容性判定层' 是另两条的子串，族匹配取"任一命中"，故这里三条等价于一条
# 语义锚点；保留三条是为了让 `--list` 能展示口径的完整措辞范围。
FAMILY = [
    '机器人零件兼容性判定层',
    '机器人零件的兼容性判定层',
    '零件兼容性判定层',
]

# 判据表到此为止。**刻意不设「最小锚点串」常量**：
# 曾想用 '零件兼容性判定层' 做单一锚点，结果把合法变体「机器人零件**的**兼容性判定层」
# 判成假红（本自证阴性① 当场抓到）。族匹配没有任何单一子串能替代，别再加回去。

# 扫描面：只扫**会上线或被 AI 抓走**的东西。刻意排除：
#   scripts/  本文件自己就含退役字符串常量（扫自己必然假红）
#   docs/     内部审计文档**应当**能引用退役表述（那是它在记录历史）
#   ops/      内部运营留痕（已在 .gitignore，不上线）
#   node_modules / .git / venv / 子模块
SKIP_DIRS = {
    '.git', 'node_modules', 'ops', 'docs', 'scripts', 'tests', 'test',
    '.workbuddy', '.venv', 'venv', '__pycache__', '.github',
    'roboparts-dataset-github',
}
# 只扫文本类。**刻意不含 .py**（脚本里出现这些词多半是在做检查或记录历史）
SCAN_EXT = ('.html', '.htm', '.txt', '.json', '.md', '.js', '.mjs', '.cjs',
            '.xml', '.yml', '.yaml')

# ---------------------------------------------------------------- 纯函数

_TAG = re.compile(r'<[^>]+>')
_WS = re.compile(r'\s+')


def squash(text):
    """HTML/文本 → 用来做短语匹配的「挤干」串。

    两步都不能省，各自堵一类假红（都是本仓真实出现过的形态）：
      ① 抹标签：`机器人零件<span>兼容性</span>判定层` 原文不含短语，实际页面上却是；
      ② 抹空白：短语被渲染成两行时，逐行匹配必然漏网。
    宁可漏（假绿）不可假红 —— 假红会让闸门被无视，那等于没有闸门。
    """
    if not text:
        return ''
    return _WS.sub('', _TAG.sub('', text))


def family_hits(text):
    """文本里出现的定位表述（去重、稳定顺序）。"""
    s = squash(text)
    return [v for v in FAMILY if v in s]


def retired_hits(text):
    """文本里出现的退役表述（去重、稳定顺序）。"""
    s = squash(text)
    return [v for v in RETIRED if v in s]


def positioning_violations(pairs, local_map):
    """纯函数：[(线上路径, 线上原文)] × {线上路径: 本地原文} → [(路径, 说明)]

    三条判据，全部只看输入，不向环境取值：
      ① 线上含退役表述      → 漂移（改了源没部署，或有人写回了旧口径）
      ② 本地含族表述而线上不含 → 漂移（源已改、产物没跟上）
      ③ 本地不含族表述        → 不作要求（该页本来就不谈定位）
    本地文件缺失时跳过 ②③ —— 拿不到源就不能断言产物落后，宁漏勿假红。
    """
    out = []
    for name, text in pairs:
        ret = retired_hits(text)
        for s in ret:
            out.append((name, '线上仍含退役表述「%s」' % s))
        local = local_map.get(name)
        if local is None:
            continue
        # 线上侧必须走**族匹配**，不能拿 ANCHOR 单串去比：
        # 「机器人零件**的**兼容性判定层」是合法变体，单串比对会把它判成假红
        # —— 本自证阴性① 就是这么抓到的，不是推测。
        if family_hits(local) and not family_hits(text):
            out.append((name, '本地源含定位表述而线上不含（疑似未部署）'))
    return out


# ---------------------------------------------------------------- 本地扫描

def local_map(paths):
    """线上路径 → 本地文件原文。取不到（文件不存在）时不放进 map。"""
    m = {}
    for p in paths:
        fp = local_file(p)
        if fp and os.path.exists(fp):
            try:
                with open(fp, encoding='utf-8', errors='replace') as f:
                    m[p] = f.read()
            except OSError:
                pass
    return m


def local_file(live_path):
    """线上路径 → 本地绝对路径。'/' → index.html；无扩展名补 .html。"""
    rel = live_path.lstrip('/')
    if not rel:
        rel = 'index.html'
    elif '.' not in os.path.basename(rel):
        rel = rel + '.html'
    return os.path.join(ROOT, rel.replace('/', os.sep))


def scan_surface(root=None):
    """遍历可部署面，返回 {相对路径: 原文}（只含文本类文件）。"""
    root = root or ROOT
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(SCAN_EXT):
                continue
            p = os.path.join(dirpath, fn)
            try:
                with open(p, encoding='utf-8', errors='replace') as f:
                    out[os.path.relpath(p, root).replace(os.sep, '/')] = f.read()
            except OSError:
                pass
    return out


def check_local(root=None):
    """本地扫描：返回 (退役命中 {文件: [串]}, 含定位表述的文件数, 扫描文件数)。"""
    surface = scan_surface(root)
    bad = {}
    with_family = 0
    for rel, text in surface.items():
        h = retired_hits(text)
        if h:
            bad[rel] = h
        if family_hits(text):
            with_family += 1
    return bad, with_family, len(surface)


# ---------------------------------------------------------------- 自证

def self_test():
    """阴阳对照。每一条都对应本仓真实出现过的形态，不是编出来的。"""
    fails = []
    n = 0

    def check(ok, msg):
        nonlocal n
        n += 1
        print('  %s %s' % ('✅' if ok else '❌', msg))
        if not ok:
            fails.append(msg)

    LOC = '/x'
    fam_local = '<title>RoboParts — 机器人零件兼容性判定层</title>'
    fam_live = '<title>RoboParts — 机器人零件兼容性判定层</title>'

    # ---- 阳性：必须判红 ----
    check(positioning_violations([(LOC, '<p>RoboParts — 仿生机器人生态平台</p>')], {}),
          '阳性①: 线上退役表述判红')
    check(positioning_violations([(LOC, '<p>本站是中文圈稀缺的平台</p>')], {}),
          '阳性②: 线上「中文圈」判红')
    check(positioning_violations([(LOC, fam_live)], {LOC: fam_local}) == [],
          '阴性对照前置: 本地在线同含族表述时放行')
    check(positioning_violations([(LOC, '<p>RoboParts — 开源机器人兼容性平台</p>')],
                                 {LOC: fam_local}),
          '阳性③: 源已改而线上仍是旧口径 → 判红（本轮的病根形态）')
    check(positioning_violations([(LOC, '<title>RoboParts</title>')], {LOC: fam_local}),
          '阳性④: 线上丢失定位表述 → 判红（未部署/被回滚）')

    # ---- 阴性：必须放行，否则天天假红 ----
    check(positioning_violations([(LOC, '<title>RoboParts — 机器人零件的兼容性判定层</title>')],
                                 {LOC: '<title>RoboParts — 机器人零件兼容性判定层</title>'}) == [],
          '阴性①: 多一个「的」的合法变体放行')
    check(positioning_violations([(LOC, '<p>不抽佣，只登记答不出来的部分</p>')], {}) == [],
          '阴性②: 本地无源可比时不作要求')
    check(positioning_violations([(LOC, '<p>正文完全不谈定位</p>')],
                                 {LOC: '<p>正文完全不谈定位</p>'}) == [],
          '阴性③: 双方都不含族表述时放行（该页本就不谈定位）')
    check(positioning_violations(
        [('/a', '<h1>机器人零件<span>兼容性</span>判定层</h1>')],
        {'/a': fam_local}) == [],
        '阴性④: 短语被标签切开仍算命中（假红杀手）')
    check(positioning_violations(
        [('/a', '<h1>机器人零件\n兼容性判定层</h1>')], {'/a': fam_local}) == [],
        '阴性⑤: 短语被换行切开仍算命中')
    check(positioning_violations(
        [('/api.json', '{"site_name":"RoboParts — 仿生机器人生态平台"}')], {}) != [],
        '阳性⑤: JSON 接口里的退役表述同样判红（机读面也是主张）')

    # ---- 自证本身必须能失败：恒返回 [] 的桩必须过不了阳性用例 ----
    # 断言必须是「真判定器全命中 **且** 桩全放过」，不能写成「不是所有用例都空」——
    # 后者对恒空桩恰好为 False，看似在测桩、实则在测我自己写反的布尔式。
    pos_cases = [('<p>线上写回仿生机器人生态平台</p>', {}),
                 ('<p>本站是中文圈稀缺的平台</p>', {})]
    stub = lambda *_a: []  # noqa: E731
    real_flags = all(positioning_violations([(LOC, s)], m) for s, m in pos_cases)
    stub_flags = all(stub([(LOC, s)], m) for s, m in pos_cases)
    check(real_flags and not stub_flags,
          '自证有效性: 真判定器全命中而恒空桩全放过（real=%s stub=%s）'
          % (real_flags, stub_flags))

    # ---- 本地扫描端到端：允许面命中、禁扫面不命中 ----
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, 'articles'), exist_ok=True)
        os.makedirs(os.path.join(d, 'docs'), exist_ok=True)
        os.makedirs(os.path.join(d, 'scripts'), exist_ok=True)
        with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
            f.write('<h1>RoboParts — 机器人零件兼容性判定层</h1>')
        with open(os.path.join(d, 'articles', 'a.html'), 'w', encoding='utf-8') as f:
            f.write('<footer>RoboParts — 仿生机器人生态平台</footer>')   # 该被扫到
        with open(os.path.join(d, 'docs', 'audit.md'), 'w', encoding='utf-8') as f:
            f.write('历史口径：仿生机器人生态平台')                        # 应被跳过
        with open(os.path.join(d, 'scripts', 's.py'), 'w', encoding='utf-8') as f:
            f.write('RETIRED = ["仿生机器人生态平台"]')                    # 应被跳过
        bad, with_family, total = check_local(d)
        check(list(bad) == ['articles/a.html'],
              '端到端: 只命中可部署面（实得 %s）' % list(bad))
        check(with_family == 1, '端到端: 统计到 1 个含定位表述的面（实得 %d）' % with_family)
        check(total == 2, '端到端: 扫描面只含 2 个文本文件（实得 %d）' % total)

    print()
    if fails:
        print('定位口径契约自证: FAIL（%d/%d 项）' % (len(fails), n))
        for x in fails:
            print('   ❌', x)
        return 1
    print('定位口径契约自证: PASS（%d 项，含 4 条阴性对照 + 3 项端到端）' % n)
    return 0


# ---------------------------------------------------------------- CLI

def main():
    if '--self-test' in sys.argv:
        print('=== 定位口径契约 · 阴阳对照自证（不联网）===')
        return self_test()

    bad, with_family, total = check_local()

    if '--list' in sys.argv:
        print('扫描面: %d 个文本文件（跳过 %s）' % (total, '/'.join(sorted(SKIP_DIRS))))
        print('含定位表述的文件: %d' % with_family)
        print('退役表述判据 %d 条: %s' % (len(RETIRED), ' · '.join(RETIRED)))
        print('定位表述族 %d 条: %s' % (len(FAMILY), ' · '.join(FAMILY)))
        return 0

    print('=== 定位口径本地扫描 ===')
    print('扫描面 %d 个文本文件；含定位表述 %d 个' % (total, with_family))
    if bad:
        print('❌ %d 个文件仍含退役表述：' % len(bad))
        for rel, hits in sorted(bad.items()):
            print('   %-58s %s' % (rel, '、'.join(hits)))
        print('\n   这些位置会被搜索引擎与 AI 抓走二次分发，改回现行定位表述：')
        print('   「机器人零件兼容性判定层」（源改了要记得重新部署）')
        return 1
    print('✅ 0 处退役表述（%d 个面全清）' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
