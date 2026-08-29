# -*- coding: utf-8 -*-
"""L1.21 第 6 条不变式（报告声称的提交哈希必须真实存在）反向注入验证（20260807-00）

背景：20260806-21 的报告写着「已于 22:00 轮提交为 4ea6d47」，而该哈希从不存在。
前 5 条留痕不变式**全绿**——报告有、摘要有、_LATEST 可对齐、git 有活动故不算孤儿运行
——唯独报告内容是假的。前 5 条锁"有没有留痕"，第 6 条锁"留的痕是不是真的"。

这条闸门本身也可能因为正则写坏、_obj_exists 恒真而变成摆设，所以逐条造真缺陷，
要求**对应那条**必须变红。

用法： python scripts/verify_hashclaim_injections.py
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, 'scripts', 'regression.py')
RES = os.path.join(ROOT, 'ops', 'results')


def read(p):
    with open(p, encoding='utf-8', errors='ignore') as f:
        return f.read()


def write(p, s):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


# 只看这 5 条断言的成败，避免被其它层的红牵连误判
KEYS = {
    'ghost': '报告声称的提交哈希在仓库中真实存在',
    'lower': '阳性：确实从近 48h 报告中解析到提交哈希',
    'fpos':  '功能性·阳：只提取提交语境的哈希',
    'fneg':  '功能性·阴：全数字串不被当作提交哈希',
    'fexi':  '功能性：不存在的哈希确实判为不存在',
    'reveal': '功能性·阳：揭露假哈希',
    'fneg2': '功能性·阴：无否定语境的同一哈希仍判为声称',
}


def run():
    """返回 {key: True(绿)/False(红)/None(未出现)}"""
    r = subprocess.run([sys.executable, REG], cwd=ROOT,
                       capture_output=True, text=True, timeout=300,
                       encoding='utf-8', errors='ignore')
    out = r.stdout or ''
    res = {}
    for k, needle in KEYS.items():
        res[k] = None
        for ln in out.splitlines():
            if needle in ln:
                res[k] = ('✅' in ln)
                break
    return res


def main():
    base = run()
    print('[基线] ' + ' '.join(
        '%s=%s' % (k, {True: '绿', False: '红', None: '缺'}[v])
        for k, v in base.items()))
    if not all(base.values()):
        print('❌ 基线未全绿，先修好再注入（否则注入结论不可信）')
        return 1

    reg_src = read(REG)
    cases = []

    # ① 在 _LATEST.md 里种一个不存在的哈希 —— 原缺陷重现 + 验证扫描范围。
    # 首版闸门只扫 roboparts-*.md，本注入当场证明 _LATEST（用户看的总入口）
    # 是盲区；扩围后此注入应被拦下。
    latest = os.path.join(RES, '_LATEST.md')
    latest_src = read(latest)

    cases.append(('①_LATEST 声称一个不存在的哈希（原缺陷+扫描范围）', 'ghost',
                  lambda: write(latest, latest_src + '\n本轮提交 `beefca7` 已落地。\n'),
                  lambda: write(latest, latest_src)))

    # ② 正则写坏成永不匹配 —— 阳性下界必须察觉"闸门空转"
    RE_SRC = r"(?:提交|commit|推送|push|HEAD)[^\n`；;。，,、]{0,24}`([0-9a-f]{7,10})`"

    def inj_re_dead():
        write(REG, reg_src.replace(
            RE_SRC, r"(?:ZZZ_NEVER_MATCH_ZZZ)`([0-9a-f]{7,10})`"))

    cases.append(('②HASH_CTX 永不匹配（闸门空转成恒绿）', 'lower',
                  inj_re_dead, lambda: write(REG, reg_src)))

    # ③ _obj_exists 恒真 —— 最阴险的假绿：幽灵哈希从此永不报
    def inj_exists_true():
        write(REG, reg_src.replace(
            '        _hash_cache[hh] = ok\n        return ok',
            '        _hash_cache[hh] = True\n        return True'))

    cases.append(('③_obj_exists 恒真（幽灵哈希永不报）', 'fexi',
                  inj_exists_true, lambda: write(REG, reg_src)))

    # ④ 去掉全数字排除 —— 20260806 这类日期串会被当哈希，造成大批误报
    def inj_no_digit_guard():
        # 20260807-01 起源串改为 `if g.isdigit(): continue`（否定语境豁免重构所致）。
        # 注入前先断言源串命中，否则 replace 静默失效 → 假绿。
        old = "            if g.isdigit():               # 排除 20260806 这类全数字日期串\n" \
              "                continue"
        assert old in reg_src, '注入④源串漂移，需同步更新'
        write(REG, reg_src.replace(old, "            if False:\n                continue"))

    cases.append(('④取消全数字排除（日期串被误判为哈希）', 'fneg',
                  inj_no_digit_guard, lambda: write(REG, reg_src)))

    # ⑥ 否定语境豁免放宽为无条件豁免（GHOST_OK 含空串 → 一切哈希都算"揭露"→ 恒绿）
    # 这是 20260807-01 新增豁免带来的新攻击面，必须自带对应注入
    def inj_ghost_ok_wide():
        old = "    GHOST_OK = ('不存在', '幽灵', '假声明', '伪造', '查无', '订正', '更正', '未生成')"
        assert old in reg_src, '注入⑥源串漂移，需同步更新'
        write(REG, reg_src.replace(old, "    GHOST_OK = ('',)"))

    cases.append(('⑥否定语境豁免放宽为恒真（豁免吞掉一切声称）', 'fneg2',
                  inj_ghost_ok_wide, lambda: write(REG, reg_src)))

    # ⑤ 提取语境放宽为裸哈希 —— 会把散文里提到的任意 hex 串也当成"声称已提交"
    def inj_bare():
        write(REG, reg_src.replace(RE_SRC, r"`([0-9a-f]{7,10})`"))

    cases.append(('⑤语境放宽为裸反引号（散文 hex 串也算声称）', 'fpos',
                  inj_bare, lambda: write(REG, reg_src)))

    ok = 0
    for name, key, inject, undo in cases:
        try:
            # 注入前后必须真的有字节变化。首版栽在这里：改了 regression.py 的正则后，
            # 本脚本 replace 的源串还是旧的 → 替换静默失效 → 文件没动 → 断言当然绿，
            # 却被记成"闸门漏网"。**注入无效与闸门漏网必须能区分开**，否则整份
            # 验证报告的每一行都不可信。
            snap = (read(REG), read(latest))
            inject()
            if (read(REG), read(latest)) == snap:
                print('❌ %s → 注入未生效（replace 源串已漂移），结论作废' % name)
                continue
            got = run()
            hit = (got.get(key) is False)
            print('%s %s → %s 变%s' % (
                '✅' if hit else '❌', name, key,
                {True: '绿', False: '红', None: '缺'}[got.get(key)]))
            ok += 1 if hit else 0
        finally:
            undo()

    fin = run()
    restored = all(fin.values())
    print('[还原] ' + ('✅ 全绿' if restored else '❌ 未还原: %s' % fin))
    print('\n结论：%d/%d 处注入被对应断言拦下%s'
          % (ok, len(cases), '' if ok == len(cases) else ' —— 有漏网，闸门不可信'))
    return 0 if (ok == len(cases) and restored) else 1


if __name__ == '__main__':
    sys.exit(main())
