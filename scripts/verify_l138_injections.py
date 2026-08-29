# -*- coding: utf-8 -*-
"""L1.38 反向注入验证：把缺陷种回去，闸门必须变红。

闸门写出来是绿的不算数 —— 绿也可能是"根本没在看"。
这里逐项破坏「部署前快照」这条链路，跑一遍 L1.38，要求每项都被抓出来；跑完自动还原。

重点是 ③：把快照调用挪到部署**之后**。这种改动最阴 —— 功能照跑、日志照打、
所有存在性断言照绿，唯独在"部署失败/进程中断"这个它本该覆盖的场景里保护缺席。
只有顺序断言能抓住它，所以顺序断言必须被验证过确实有效。
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(ROOT, 'scripts', 'deploy.mjs')
LIB = os.path.join(ROOT, 'scripts', 'lib', 'deploy_snapshot.mjs')
PY = sys.executable

SNAP_CALL = ('// 0b) 内容快照先于部署：留痕保住「说明」，快照保住「内容」，缺一不可\n'
             'snapshotWorkingTree(ROOT);\n')

# (名称, 目标文件, 替换前, 替换后, 期望变红的断言关键词)
CASES = [
    ('①删掉 deploy.mjs 里的快照调用',
     DEPLOY, SNAP_CALL, '', '确实调用了'),
    ('②退回无参调用（root=undefined 会静默返回 null，快照全程不生成）',
     DEPLOY, 'snapshotWorkingTree(ROOT);', 'snapshotWorkingTree();', '无参调用'),
    ('③把快照挪到部署之后（功能照跑，但在最需要它时缺席）',
     DEPLOY, SNAP_CALL, '', '位于 wrangler 部署之前'),
    ('④改回内联副本（verify 就会去测一个没人用的孤儿模块）',
     DEPLOY, "import { snapshotWorkingTree } from './lib/deploy_snapshot.mjs';\n",
     '', '引用共享快照模块'),
    # ⑤⑥ 必须精确打在**代码**上，不能打在注释上。
    # 首版写成裸词 'GIT_INDEX_FILE'，str.replace(count=1) 命中的是文档注释里
    # 那句"用临时 GIT_INDEX_FILE"，代码毫发无损 —— 用例看似跑了，其实什么也没破坏。
    # 而它反过来暴露了闸门当时的真缺陷：判据也在扫全文，被注释里的同名词喂饱。
    # 一个「注入锚点选错」的用例，恰好证明了「断言选错」。两边都已改成认代码。
    ('⑤去掉临时索引（快照会污染调用者暂存区）',
     LIB, 'GIT_INDEX_FILE: tmpIndex', 'GIT_INDEX_UNUSED: tmpIndex', '临时索引'),
    ('⑥去掉 read-tree 播种（已追踪但被 ignore 的文件会整个丢失）',
     LIB, "['read-tree', 'HEAD']", "['no-read-tree', 'HEAD']", 'read-tree'),
    # ⑦阳性对照：只改注释、不动代码，闸门**必须保持绿**。
    # 少了这条，⑤⑥ 会诱使判据越收越紧，最终把"注释里提到"也当违规 ——
    # 那就又回到"为了闸门变绿去删真话"的老路（L1.32 教训）。
    ('⑦仅改注释不动代码（必须不误报）',
     LIB, '用临时 GIT_INDEX_FILE', '用临时索引文件', None),
]


def run_gate():
    p = subprocess.run([PY, os.path.join(ROOT, 'scripts', 'regression.py')],
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace')
    out = p.stdout or ''
    if '[L1.38]' not in out:
        return '(未跑到 L1.38)'
    seg = out[out.find('[L1.38]'):]
    return seg[:seg.find('[L2]')] if '[L2]' in seg else seg


def main():
    originals = {f: open(f, encoding='utf-8').read() for f in (DEPLOY, LIB)}
    for f in originals:
        shutil.copy2(f, f + '.l138bak')
    ok = True
    try:
        base = run_gate()
        if '❌' in base:
            print('基线就不干净，先修基线：\n' + base)
            return 1
        print('基线：L1.38 全绿 ✅\n')

        for name, target, old, new, kw in CASES:
            orig = originals[target]
            if old not in orig:
                print('%s -> ⚠️ 注入锚点未命中，用例失效（锚点: %r）' % (name, old[:45]))
                ok = False
                continue

            if name.startswith('③'):
                # 顺序注入：不是删掉，而是把同一行搬到部署命令之后。
                # 存在性断言仍然全绿，只有顺序断言能抓住 —— 这正是本用例要证明的。
                anchor = 'const depOut ='
                if anchor not in orig:
                    print('%s -> ⚠️ 搬移锚点未命中' % name)
                    ok = False
                    continue
                mutated = orig.replace(old, '', 1).replace(
                    anchor, 'snapshotWorkingTree(ROOT);\n' + anchor, 1)
            else:
                mutated = orig.replace(old, new, 1)

            open(target, 'w', encoding='utf-8').write(mutated)
            seg = run_gate()
            if kw is None:
                # 阳性对照：期望**不变红**
                if '❌' not in seg:
                    print('%s -> ✅ 未误报' % name)
                else:
                    print('%s -> ❌ 误报了（判据把注释当实现）\n    段落: %s'
                          % (name, seg.strip()[:400]))
                    ok = False
            else:
                hit = [ln for ln in seg.splitlines() if '❌' in ln and kw in ln]
                if hit:
                    print('%s -> ✅ 被拦下' % name)
                else:
                    print('%s -> ❌ 未被拦下（断言是摆设）\n    段落: %s'
                          % (name, seg.strip()[:400]))
                    ok = False
            open(target, 'w', encoding='utf-8').write(orig)

        final = run_gate()
        print('\n还原后复验：', '干净 ✅' if '❌' not in final else ('仍红 ❌\n' + final))
        if '❌' in final:
            ok = False
    finally:
        for f in originals:
            bak = f + '.l138bak'
            if os.path.exists(bak):
                shutil.copy2(bak, f)
                os.remove(bak)

    print('\n结论：', '%d/%d 全部拦下，闸门有效' % (len(CASES), len(CASES)) if ok
          else '存在未被拦下的注入，闸门需加强')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
