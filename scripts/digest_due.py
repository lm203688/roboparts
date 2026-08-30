#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""日报是否到期 —— 唯一判定入口（把"人眼看日期"换成"脚本算小时"）。

起因（2026-08-08 12:00 自纠）：飞轮起手时看到 `_last_digest.txt` 是 8/7、当天是 8/8，
就"想当然"判定日报已过期，差点在 `_LATEST.md` 里写下「已超 24h，本轮已出日报」——
实际只过了 20.76h。**日期换了 ≠ 满 24 小时**。这类"跨天错觉"是典型的口径≠事实：
不是数据错，是判断方式错（用日历差代替时间差）。

用法：
    python scripts/digest_due.py            # 人读
    python scripts/digest_due.py --json     # 机读
    python scripts/digest_due.py --stamp    # 把 DIGEST-CLAIM 机械盖进 _LATEST.md
    python scripts/digest_due.py --verify-latest   # 写完 _LATEST.md 后自查（同轮兜底）
退出码：
    0 = 未到期（不该出日报）
    10 = 已到期（本轮必须出日报并更新 _last_digest.txt）
    2 = 状态文件缺失/损坏（当作到期处理，宁可多出一份也不要漏）
    3 = --stamp / --verify-latest 失败（声明与状态矛盾，或标记缺失/重复）

────────────────────────────────────────────────────────────────────────
【20260810-10 增：把"手打声明"改成"机械盖章"】

本轮起手回归 EXIT=1，唯一红项是「_LATEST.md 有且仅有一个 DIGEST-CLAIM（实测 0 个）」。
上一轮（09:00 续跑）正文里如实写了"无日报（距今<24h）"，却漏了那行机读标记。

值得记的是**这个红是怎么绕过上一轮的**：
  1. `_LATEST.md` 由模型每轮**手打**，标记是一条纯靠记性的书写约定 —— 而
     L1.76 那一族的结论早已是「数字要机械保鲜，不能逐页手改」，同样的道理
     对"标记"成立却一直没落实：**凡靠人记得写的，就等于迟早不写。**
  2. 更要命的是**次序**：回归在前、写 `_LATEST.md` 在后。闸门校验的产物是它自己
     跑完之后才生成的，所以这类缺陷**永远由下一轮发现**，本轮自测无论多绿都照过。
     闸门与被检对象存在时序倒挂时，覆盖率再高也只是"迟一轮的告警"。

故这里补两件事，且都放进**唯一入口**（识别器只准有一份，手抄两份的下场见 L1.69）：
  - `claim_line/stamp_latest`：**产出侧**机械生成，模型不再手打。
  - `check_claim`：**校验侧**单一实现，regression 的 L1.58 与 `--verify-latest`
    共用同一份语义，且 `--verify-latest` 可在写完 `_LATEST.md` 后立刻跑，把
    "下一轮才发现"拉回"同一轮发现"。

盖章不等于放水：verdict 仍须与真实状态自洽 —— 到期了还想盖 skipped 会被拒绝
（exit 3），谎报 issued 而 `_last_digest.txt` 没更新同样被拒。它消掉的只是
"忘了写"这一类纯书写失误，"该出没出"的抓错能力一点没动。
────────────────────────────────────────────────────────────────────────
"""
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = os.path.join(ROOT, 'ops', 'results', '_last_digest.txt')
LATEST = os.path.join(ROOT, 'ops', 'results', '_LATEST.md')
CST = timezone(timedelta(hours=8))
PERIOD_H = 24.0

# 机读日报声明的**唯一**识别器。regression.py 的 L1.58 直接引用本对象，
# 不得另抄一份正则（两份语义迟早分叉）。
CLAIM_RE = re.compile(
    r'<!--\s*DIGEST-CLAIM:\s*(issued|skipped)\s*@\s*'
    r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\s*-->')

# 声明 issued 时允许的 _last_digest 最大陈旧小时数（与 L1.58 判据一致）
ISSUED_FRESH_H = 3.0
# --stamp auto 判为"本轮刚出过日报"的窗口：标记新于此即认定 issued
AUTO_ISSUED_H = 0.5

# ── 以下三个识别器同样是**唯一源**（regression.py 引用，不得另抄）────────────
# _SUMMARY.md 摘要行。分组: 年 月 日 时 分
SUMMARY_REC_RE = re.compile(
    r'-\s*(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})\s*\|')
# _LATEST.md 的「运行时间」（支持 `HH:MM–HH:MM` 区间写法）
RUNTIME_RE = re.compile(
    r'运行时间[：:]\s*(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})'
    r'(?:\s*[-–—~～至到]\s*(?:\d{4}-\d{2}-\d{2}\s+)?(\d{2}):(\d{2}))?')
# _LATEST.md 的机读待办数
TODO_COUNT_RE = re.compile(r'<!--\s*TODO-COUNT:\s*(\d+)\s*-->')
_ASSERT_RE = re.compile(r'<!--\s*assert:\s*(.+?)\s*-->')

RES_DIR = os.path.join(ROOT, 'ops', 'results')
SUMMARY = os.path.join(RES_DIR, '_SUMMARY.md')
NEEDS_USER = os.path.join(RES_DIR, '_NEEDS_USER.md')


def evaluate(now=None, last_raw=None):
    """返回 dict：判定结果。

    now / last_raw 均可注入，便于自测做**完全隔离**的阴阳对照。

    20260808-16 补 last_raw（起因值得记）：L1.58 的三条阴性用例原本只注入 now，
    基准 last 仍去读真实的 `_last_digest.txt`。本轮出了日报、把标记更新到 16:27 之后，
    那些钉死在 8/7 15:22 基准上的用例全部翻红 —— **测试依赖了外部可变状态**，
    而它恰恰是被测流程自己会改的状态：日报一出，守护日报的自测就自毁。
    这与 L1.59 阴性对照假红（拿 `git show HEAD` 当"修复前原版"，修复进 HEAD 后失效）
    是同一族，24h 内第二次。凡对照用例，基准必须钉死在用例内部，不许向环境取值。
    """
    now = now or datetime.now(CST)
    out = {'now': now.isoformat(), 'period_hours': PERIOD_H}

    if last_raw is None:
        if not os.path.exists(MARK):
            out.update(ok=False, due=True, reason='状态文件不存在，按到期处理')
            return out
        raw = io.open(MARK, encoding='utf-8').read().strip()
    else:
        raw = str(last_raw).strip()
    out['last_raw'] = raw
    try:
        last = datetime.fromisoformat(raw)
    except ValueError:
        out.update(ok=False, due=True, reason='状态文件无法解析为 ISO 时间，按到期处理')
        return out
    if last.tzinfo is None:
        last = last.replace(tzinfo=CST)

    elapsed = (now - last).total_seconds() / 3600.0
    nxt = last + timedelta(hours=PERIOD_H)
    out.update(
        ok=True,
        last=last.isoformat(),
        elapsed_hours=round(elapsed, 2),
        next_due=nxt.isoformat(),
        due=elapsed >= PERIOD_H,
        future=elapsed < 0,
    )
    if out['future']:
        # 标记时间在未来 = 状态文件被写坏或时钟异常，必须报出来而不是静默当"很新"
        out.update(ok=False, due=True, reason='状态文件时间在未来（写坏或时钟异常）')
    return out


def decide_verdict(now=None, r=None):
    """本轮该盖哪种章 —— 由**真实状态**推导，不接受调用方随口指定。

    只有当 `_last_digest.txt` 新到"像是本轮刚写的"（<= AUTO_ISSUED_H）才算 issued。
    刻意不用 L1.58 的 3 小时窗口来判 auto：那是**校验**的容差，若拿它当**生成**
    依据，上一轮 09:00 出的日报会让 10:15 这轮也自称 issued —— 校验还会放行，
    于是"谁出的日报"被悄悄张冠李戴。生成侧必须比校验侧更严。
    """
    now = now or datetime.now(CST)
    r = r or evaluate(now=now)
    if not r.get('ok'):
        return 'skipped'
    return 'issued' if r.get('elapsed_hours', 1e9) <= AUTO_ISSUED_H else 'skipped'


def claim_line(verdict, now=None):
    """生成规范形态的机读声明行（产出侧唯一入口）。"""
    if verdict not in ('issued', 'skipped'):
        raise ValueError('verdict 只能是 issued / skipped，收到 %r' % (verdict,))
    now = now or datetime.now(CST)
    return '<!-- DIGEST-CLAIM: %s @%s -->' % (verdict, now.strftime('%Y-%m-%dT%H:%M'))


def report_hours(res_dir=None):
    """已落盘的整点报告档位，升序（用于反回填下界）。"""
    res_dir = res_dir or os.path.dirname(LATEST)
    if not os.path.isdir(res_dir):
        return []
    return sorted(
        m.group(1) for m in
        (re.match(r'roboparts-(\d{8}-\d{2})\.md$', f) for f in os.listdir(res_dir))
        if m)


def check_claim(text, now=None, hours=None, last_raw=None):
    """校验侧唯一实现：返回 [(ok, 说明), ...]。

    regression 的 L1.58 与 CLI `--verify-latest` 共用本函数，保证"静态闸说的"
    与"写完自查说的"是同一套语义。
    """
    now = now or datetime.now(CST)
    hours = report_hours() if hours is None else hours
    out = []
    claims = CLAIM_RE.findall(text)
    ok_one = (len(claims) == 1)
    out.append((ok_one,
                '_LATEST.md 有且仅有一个带时刻的机读日报声明 '
                '<!-- DIGEST-CLAIM: issued|skipped @YYYY-MM-DDTHH:MM -->'
                '（实测 %d 个 —— 缺失即无法对账，多个即自相矛盾）' % len(claims)))
    if not ok_one:
        return out

    verdict, at_raw = claims[0]
    at = datetime.fromisoformat(at_raw).replace(tzinfo=CST)

    out.append((at <= now + timedelta(minutes=5),
                '日报声明时刻不得在未来（实测 %s —— 未来时刻＝伪造声明窗口）' % at_raw))
    if hours:
        want = at.strftime('%Y%m%d-%H')
        out.append((want >= hours[-1],
                    '日报声明时刻不得早于最新小时报告（声明 %s vs 报告 %s —— '
                    '回填旧时刻即可假装"当时还没到期"永久规避）' % (want, hours[-1])))

    r_at = evaluate(now=at, last_raw=last_raw)
    if verdict == 'issued':
        out.append((r_at['elapsed_hours'] <= ISSUED_FRESH_H,
                    '声明 issued 时 _last_digest 必须刚更新'
                    '（声明时刻已过 %.2fh —— 声称出了却没更标记＝谎报）'
                    % r_at['elapsed_hours']))
    else:
        out.append((r_at['due'] is False,
                    '声明 skipped 时**该时刻**现算必须未到期'
                    '（实测 due=%s，声明时刻已过 %.2fh —— 到期了还跳过＝漏报）'
                    % (r_at['due'], r_at['elapsed_hours'])))
    return out


def stamp_latest(path=None, verdict=None, now=None, text=None):
    """把声明机械盖进 _LATEST.md：幂等（先删旧标记再追加），且**自洽才落盘**。

    返回 (新正文, 声明行)。若 verdict 与真实状态矛盾则抛 AssertionError ——
    盖章只消除"忘了写"，不消除"该出没出"。
    """
    path = path or LATEST
    now = now or datetime.now(CST)
    verdict = verdict or decide_verdict(now=now)
    if text is None:
        text = io.open(path, encoding='utf-8').read()

    line = claim_line(verdict, now=now)
    stripped = CLAIM_RE.sub('', text).rstrip()
    new = stripped + '\n\n' + line + '\n'

    bad = [m for ok, m in check_claim(new, now=now) if not ok]
    if bad:
        raise AssertionError('盖章被拒（声明与真实状态矛盾）：\n  - ' + '\n  - '.join(bad))
    return new, line


def stamp_todo(path=None, text=None):
    """把 `<!-- TODO-COUNT: N -->` 机械盖进 _LATEST.md，N 从 _NEEDS_USER.md 现算。

    【20260811-04 补】run-73 暴露：_LATEST.md 上挂着两个机读标记，
    `DIGEST-CLAIM` 早有唯一入口会自动补，**`TODO-COUNT` 却一直靠手打** ——
    按报告重写 _LATEST.md 时它就这么没了，靠下一轮 regression 判红兜住。
    「唯一入口只覆盖了一半的机读标记」和完全没有入口一样，都是在赌人记性；
    区别只是前者会给人一种"已经机械化了"的错觉。

    幂等：先删所有旧标记再追加一条。数值现算，杜绝手打与实际对不上。
    """
    path = path or LATEST
    if text is None:
        text = io.open(path, encoding='utf-8').read()
    n = open_todo_count()
    if n is None:
        raise AssertionError('盖章被拒：_NEEDS_USER.md 不存在，待办数无从现算')
    line = '<!-- TODO-COUNT: %d -->' % n
    stripped = TODO_COUNT_RE.sub('', text).rstrip()
    new = stripped + '\n\n' + line + '\n'
    if len(TODO_COUNT_RE.findall(new)) != 1:
        raise AssertionError('盖章被拒：TODO-COUNT 标记数不为 1')
    return new, line


# ══════════════════════════════════════════════════════════════════════════
# 【20260810-19 增：留痕自查从「只查声明」扩到「留痕全套」】
#
# 起因：本轮起手回归 EXIT=1，两项红全部指向**上一轮**（run-67）的留痕：
#   ① `_SUMMARY.md` 缺 `20260810-17` 对应行 —— 不是漏写，是**手打写错了格式**
#      （写成 `2026-08-10T18:17 | 第67次 | …`，既无前导 `- `、又用 T 分隔、
#      分钟位还是写入时刻而非运行档位），识别器一条都匹配不到。
#   ② DIGEST-CLAIM 停在 `@16:53`，早于最新小时报告 `-17`（上一轮没跑 --stamp）。
#
# 8/10 那轮的结论是「凡靠人记得写的，等于迟早不写」，于是给**声明**做了机械盖章；
# 但 `_SUMMARY` 行仍是手打 —— 同一个病，只治了一半。而 `--verify-latest` 当时
# 只查声明这一件事，所以即便上一轮跑了自查也照样绿。**自查的覆盖面小于闸门的
# 覆盖面时，自查就只是安慰剂**：真正拦住发布的是下一轮的 regression，
# 时序倒挂原样保留。
#
# 故本次两件事同时做，缺一不可：
#   - 产出侧：`summary_line/append_summary` 机械生成摘要行（幂等，同档位替换）。
#   - 校验侧：`check_trace` 把留痕四件套（小时报告 / _SUMMARY 对账 / _LATEST
#     运行时间 / TODO-COUNT / DIGEST-CLAIM）收进**一个**自查入口，与 regression
#     共用同一批识别器，让「写完即跑」的覆盖面追平「下一轮才跑」的闸门。
# ══════════════════════════════════════════════════════════════════════════

def latest_slot(txt, max_span_min=120):
    """解析 _LATEST 的「运行时间」，返回它实际覆盖到的**最末** slot；解析不出返回 None。

    区间感知（`19:00–20:10` 记作 20 点）不是后门：末刻须晚于起刻且跨度 ≤2h，
    `00:00–23:59` 这类通吃写法无效，会退回按起点判定。
    """
    m = RUNTIME_RE.search(txt)
    if not m:
        return None
    day = m.group(1) + m.group(2) + m.group(3)
    start = int(m.group(4)) * 60 + int(m.group(5))
    if m.group(6) is None:
        return (day, m.group(4))
    end = int(m.group(6)) * 60 + int(m.group(7))
    if end < start:
        end += 24 * 60
    if not (0 < end - start <= max_span_min):
        return (day, m.group(4))
    if end >= 24 * 60:
        day = (datetime.strptime(day, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
    return (day, '%02d' % ((end // 60) % 24))


def parse_needs_user(text):
    """把 _NEEDS_USER.md 切成条目：[[是否未完成, 标题, [事实前提...]], ...]"""
    items, cur = [], None
    for line in text.splitlines():
        s = line.lstrip()
        if s.startswith('- [ ]') or s.startswith('- [x]') or s.startswith('- [X]'):
            if cur:
                items.append(cur)
            cur = [s.startswith('- [ ]'), s[5:].strip()[:60], []]
        elif cur is not None:
            m = _ASSERT_RE.search(line)
            if m:
                cur[2].append(m.group(1))
    if cur:
        items.append(cur)
    return items


def open_todo_count(path=None):
    """_NEEDS_USER.md 里未完成（`- [ ]`）的条数；文件不存在返回 None。"""
    path = path or NEEDS_USER
    if not os.path.exists(path):
        return None
    return sum(1 for it in parse_needs_user(io.open(path, encoding='utf-8').read()) if it[0])


def summary_line(fixed, improved, todo, now=None, hour=None):
    """生成规范形态的 _SUMMARY 摘要行（产出侧唯一入口）。

    `hour` 显式给出运行档位（'19'）时，分钟位强制归零 —— 摘要行标的是
    **运行档位**，不是写入时刻；run-67 正是把写入时刻 18:17 当成档位写进去，
    与报告 `-17` 对不上而判红。
    """
    now = now or datetime.now(CST)
    if hour is not None:
        now = now.replace(hour=int(hour), minute=0)
    fields = [str(fixed or '无').strip(), str(improved or '无').strip(), str(todo or '无').strip()]
    for f in fields:
        if '\n' in f or '|' in f:
            raise ValueError('摘要字段不得含换行或 | （会把一行劈成多条）: %r' % f[:40])
    return '- %s | 修复:%s | 提升:%s | 待办:%s' % (
        now.strftime('%Y-%m-%d %H:%M'), fields[0], fields[1], fields[2])


def append_summary(fixed, improved, todo, now=None, hour=None, path=None):
    """把摘要行机械写入 _SUMMARY.md：幂等（同档位已存在则整行替换）。

    同时锁死粘连根因 —— 追加前若文件不以换行结尾，先补换行。
    返回 (新正文, 摘要行, 是否为替换)。
    """
    path = path or SUMMARY
    line = summary_line(fixed, improved, todo, now=now, hour=hour)
    m = SUMMARY_REC_RE.match(line)
    slot = (m.group(1) + m.group(2) + m.group(3), m.group(4))

    raw = io.open(path, encoding='utf-8').read() if os.path.exists(path) else ''
    out, replaced = [], False
    for ln in raw.splitlines():
        mm = SUMMARY_REC_RE.match(ln.lstrip())
        if mm and (mm.group(1) + mm.group(2) + mm.group(3), mm.group(4)) == slot:
            if not replaced:
                out.append(line)
                replaced = True
            continue          # 同档位重复行一并收敛掉
        out.append(ln)
    if not replaced:
        out.append(line)
    return '\n'.join(out).rstrip('\n') + '\n', line, replaced


def check_trace(now=None, res_dir=None, last_raw=None):
    """留痕全套自查（写完 _LATEST/_SUMMARY 后立刻跑）：返回 [(ok, 说明), ...]。

    与 regression 的 L1.21 / L1.49 / L1.58 共用同一批识别器，保证"写完自查说的"
    与"静态闸说的"是同一套语义 —— 覆盖面追平后，留痕缺陷不再迟一轮才暴露。

    last_raw 可注入（默认读真实 _last_digest.txt），让自查在测试里完全隔离于
    环境状态 —— 否则真实标记一新鲜，依赖 2026-08-10 时间戳的合成场景就会误伤。
    """
    now = now or datetime.now(CST)
    res_dir = res_dir or RES_DIR
    out = []

    reports = {}
    for f in os.listdir(res_dir) if os.path.isdir(res_dir) else []:
        m = re.match(r'roboparts-(\d{8})-(\d{2})\.md$', f)
        if m:
            reports[(m.group(1), m.group(2))] = os.path.join(res_dir, f)
    out.append((bool(reports), '本轮小时报告已落盘（ops/results/roboparts-YYYYMMDD-HH.md）'))
    if not reports:
        return out

    newest = max(reports)
    empty = [os.path.basename(p) for p in reports.values() if os.path.getsize(p) < 80]
    out.append((not empty, '小时报告均非空（<80B 视为写入中断: %s）' % (empty[:3] or '无')))

    sum_path = os.path.join(res_dir, '_SUMMARY.md')
    if not os.path.isfile(sum_path):
        out.append((False, '_SUMMARY.md 存在（上报链路的落点）'))
    else:
        raw = io.open(sum_path, encoding='utf-8').read()
        head = [m for m in (SUMMARY_REC_RE.match(ln.lstrip()) for ln in raw.splitlines()) if m]
        glued = len(SUMMARY_REC_RE.findall(raw)) - len(head)
        out.append((glued == 0, '_SUMMARY 每条摘要独占一行（粘连 %d 条）' % glued))
        out.append((raw.endswith('\n'), '_SUMMARY 以换行结尾（粘连的根因）'))
        covered = {(m.group(1) + m.group(2) + m.group(3), m.group(4)) for m in head}
        gaps = sorted(k for k in reports if k not in covered)
        out.append((not gaps,
                    '每份小时报告都有 _SUMMARY 对应行（缺口: %s —— 格式写歪等同没写）'
                    % (['%s-%s' % g for g in gaps[:4]] or '无')))

    latest_path = os.path.join(res_dir, '_LATEST.md')
    if not os.path.isfile(latest_path):
        out.append((False, '_LATEST.md 存在（用户看最新状态的总入口）'))
        return out
    ltxt = io.open(latest_path, encoding='utf-8').read()

    lslot = latest_slot(ltxt)
    out.append((lslot is not None, '_LATEST.md 含可解析的「运行时间：YYYY-MM-DD HH:MM」'))
    if lslot is not None:
        out.append((lslot >= newest,
                    '_LATEST 运行时间(%s-%s) 不早于最新小时报告(%s-%s) —— '
                    '落后即对外播报的是旧结论' % (lslot + newest)))

    tc = TODO_COUNT_RE.findall(ltxt)
    out.append((len(tc) == 1,
                '_LATEST.md 有且仅有一个 <!-- TODO-COUNT: N -->（实测 %d 个）' % len(tc)))
    n_open = open_todo_count()
    if len(tc) == 1 and n_open is not None:
        out.append((int(tc[0]) == n_open,
                    '_LATEST 播报待办数(%s) == _NEEDS_USER 实际未完成数(%d)' % (tc[0], n_open)))

    # hours 由本次扫到的报告推出（而非再读一次真实目录）——否则传了 res_dir 也测不动
    out.extend(check_claim(ltxt, now=now, last_raw=last_raw,
                           hours=sorted('%s-%s' % k for k in reports)))
    return out


def main():
    if '--stamp' in sys.argv or '--verify-latest' in sys.argv:
        if not os.path.exists(LATEST):
            print('⚠️  _LATEST.md 不存在，无法盖章/自查')
            return 3
        if '--stamp' in sys.argv:
            # --stamp 一次盖齐 _LATEST.md 上的**两个**机读标记。
            # 先 TODO-COUNT 后 DIGEST-CLAIM，顺序固定，两者都幂等。
            try:
                txt, todo_line = stamp_todo()
                new, line = stamp_latest(text=txt)
            except AssertionError as e:
                print('❌ %s' % e)
                return 3
            io.open(LATEST, 'w', encoding='utf-8').write(new)
            print('✅ 已盖章: %s' % todo_line)
            print('✅ 已盖章: %s' % line)
            return 0
        rows = check_trace()
        for ok, m in rows:
            print('%s %s' % ('✅' if ok else '❌', m))
        return 0 if all(ok for ok, _ in rows) else 3

    if '--append-summary' in sys.argv:
        # 【为什么这里要挑剔】run-72 用 `--summary "…"`（不存在的旗标）调用本入口：
        # 旗标被静默忽略，三个字段全部回落默认值 '无'，写出一行格式完美的
        # `修复:无 | 提升:无 | 待办:无`，并按档位幂等**替换**掉了本该记录的内容。
        # --verify-latest 的 13 项全绿，因为它校验的是格式不是内容。
        # 也就是说：唯一入口把"用错"翻译成了"静默抹掉历史"，而不是报错。
        # 三道闸：① 不认识的旗标直接拒 ② 三段全空必须显式声明 ③ 已有内容不许被空行替换。
        KNOWN = {'--append-summary', '--fixed', '--improved', '--todo',
                 '--hour', '--allow-empty', '--now'}
        VALUED = {'--fixed', '--improved', '--todo', '--hour', '--now'}
        toks, i, unknown = sys.argv[1:], 0, []
        while i < len(toks):
            t = toks[i]
            if t.startswith('--'):
                if t not in KNOWN:
                    unknown.append(t)
                i += 2 if t in VALUED else 1
            else:
                i += 1
        if unknown:
            print('❌ 无法识别的旗标 %s；本入口只接受 %s'
                  % (unknown, sorted(KNOWN - {'--append-summary'})))
            print('   （静默忽略旗标会让整段运行历史被一行"无"覆盖掉，故直接拒绝）')
            return 3

        def _arg(name, default=None):
            return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default
        fixed, improved, todo = (_arg('--fixed', '无'), _arg('--improved', '无'),
                                 _arg('--todo', '无'))
        blank = all(str(v or '无').strip() in ('', '无') for v in (fixed, improved, todo))
        if blank and '--allow-empty' not in sys.argv:
            print('❌ 三段全空：这几乎总是调用姿势错了（旗标名写错/内容没传进来）。')
            print('   真的是空转轮次请显式加 --allow-empty。')
            return 3
        try:
            now_arg = None
            if '--now' in sys.argv:
                try:
                    now_arg = datetime.strptime(_arg('--now'), '%Y-%m-%dT%H:%M')
                except ValueError:
                    print('❌ --now 格式错误，应为 YYYY-MM-DDTHH:MM')
                    return 3
            new, line, replaced = append_summary(
                fixed, improved, todo, hour=_arg('--hour'), now=now_arg)
        except (ValueError, IndexError) as e:
            print('❌ 摘要行被拒: %s' % e)
            return 3
        if blank and replaced:
            prev = [ln for ln in io.open(SUMMARY, encoding='utf-8').read().splitlines()
                    if ln.lstrip().startswith(line[:18])]
            if any(not re.search(r'修复:无 \| 提升:无 \| 待办:无\s*$', p) for p in prev):
                print('❌ 拒绝用空摘要替换同档位已有的实质内容（棘轮：历史只增不抹）')
                return 3
        io.open(SUMMARY, 'w', encoding='utf-8').write(new)
        print('✅ 已%s: %s' % ('替换' if replaced else '追加', line[:110]))
        return 0

    r = evaluate()
    if '--json' in sys.argv:
        print(json.dumps(r, ensure_ascii=False))
    else:
        if not r.get('ok'):
            print('⚠️  %s' % r.get('reason'))
        else:
            print('上次日报 : %s' % r['last'])
            print('现在     : %s' % r['now'][:19])
            print('已过     : %.2f 小时（周期 %.0fh）' % (r['elapsed_hours'], PERIOD_H))
            print('下次到期 : %s' % r['next_due'][:16].replace('T', ' '))
        print('判定     : %s' % ('【到期】本轮必须出日报' if r['due'] else '【未到期】本轮不出日报'))
    if not r.get('ok'):
        return 2
    return 10 if r['due'] else 0


if __name__ == '__main__':
    sys.exit(main())
