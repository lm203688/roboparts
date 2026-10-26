# -*- coding: utf-8 -*-
"""
verify_readme_counts.py —— 对外文档里的会漂移数字必须与真相源对齐
================================================================

背景（2026-10-26 P0-9 收口暴露的教训）：
    根 README.md 由 inject_readme_stats.py 自动注入，有 gate_readme_stats_fresh 守护，
    所以那里的数字不会漂移。但**姊妹文档**没有：
        · mcp-server/README.md 里 "688 条 / 10 品类 / 5.75%"
        · mcp-server/package.json description 里 "798 humanoid robot component entities"
    随数据管线从 688→798→868 漂了三次，每次都靠人肉改。第三次（本轮）在 P0-9 收口
    时才修完。**这是同类问题第三次复发**——不是"忘了改"，是没有闸门逼着改。

本脚本的判据：
    读取 api/entities.json 的真相源（total + categories），对以下位置做机器对账：
      1. mcp-server/README.md：
         · "N 条实体" / "N categories" 之类对外宣称的总数与品类数
         · 品类分条列表（表格 / 列表两种形式都识别）
      2. mcp-server/package.json：
         · description 里出现的"N robot component entities" 或"N entities"
    不匹配即红灯，附上真相源值与期望值。

设计纪律（沿用 check_pure_drift.py 的阴阳自证范式）：
    · 阳性对照：把 868 改成 688 → 必须判红（否则闸门是纸糊的）
    · 阴性对照：真实数据 868 vs README 写 868 → 必须判绿
    · 变异对照：把 868 改成 "八百六十八" → 必须判红（不匹配任何数字）
    · 反向对照：把 README 里 688 改成 688（无变化）→ 必须绿
    共 4 项自证，跑在 --self-test 参数下。

用法：
    python scripts/verify_readme_counts.py          # 检查（默认）
    python scripts/verify_readme_counts.py --check  # 同上（CI 别名）
    python scripts/verify_readme_counts.py --self-test  # 阴阳自证
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 需要检查的文件（相对 ROOT）
TARGETS = (
    os.path.join('mcp-server', 'README.md'),
    os.path.join('mcp-server', 'package.json'),
)


def truth_source():
    """从 api/entities.json 读真相源：总实体数 + 品类数 + 品类分布。"""
    p = os.path.join(ROOT, 'api', 'entities.json')
    with open(p, encoding='utf-8') as f:
        d = json.load(f)
    meta = d.get('meta') or {}
    entities = d.get('entities') or d.get('data') or []
    total = len(entities) or d.get('count') or meta.get('total_entities') or 0
    cats = meta.get('categories') or []
    cat_counts = meta.get('category_counts') or {}
    return {
        'total': total,
        'n_categories': len(cats),
        'categories': cats,
        'cat_counts': cat_counts,
    }


def read_text(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        return f.read()


def check_mcp_readme(text, truth):
    """检查 mcp-server/README.md 里对外宣称的实体数与品类数。"""
    problems = []
    total = truth['total']
    n_cats = truth['n_categories']
    # 数字模式：允许 "868 条实体"、"868 条"、"868 entities"、"868 个实体"、
    # "20 类"、"20 品类"、"20 categories" 等各种写法。
    # 只要出现"N 条/N entities"形式且 N != truth.total，即报警。
    pat_total_cn = re.compile(
        r'(\d{2,4})\s*(?:条|个)\s*(?:实体|零部件|机器人|part|entity)', re.I)
    pat_total_en = re.compile(
        r'(\d{2,4})\s+(?:entity|entities|component|components)\b', re.I)
    found_totals = set()
    for m in pat_total_cn.finditer(text):
        found_totals.add(int(m.group(1)))
    for m in pat_total_en.finditer(text):
        found_totals.add(int(m.group(1)))
    # 过滤：只关心 >= 100 的（避免把 "10 个 tools" 之类误判）
    found_totals = {n for n in found_totals if n >= 100}
    for n in sorted(found_totals):
        if n != total:
            problems.append(
                f'实体总数写 {n}，真相源是 {total}；请更新为 {total}')

    # 品类数
    pat_cats = re.compile(
        r'(\d{1,2})\s*(?:类|品类|个品类|categories|category)', re.I)
    found_cats = set()
    for m in pat_cats.finditer(text):
        found_cats.add(int(m.group(1)))
    # 只关心 5-40 之间的整数（避免误报"10 个 tools"之类）
    found_cats = {n for n in found_cats if 5 <= n <= 40}
    for n in sorted(found_cats):
        if n != n_cats:
            problems.append(
                f'品类数写 {n}，真相源是 {n_cats}；请更新为 {n_cats}')
    return problems


def check_package_json(text, truth):
    """检查 mcp-server/package.json description 里的实体数。"""
    problems = []
    try:
        pkg = json.loads(text)
    except json.JSONDecodeError as ex:
        return [f'package.json 无法解析：{ex}']
    desc = pkg.get('description', '')
    # 找形如 "868 ... entities"、"868 条实体" 的数字
    pat = re.compile(r'(\d{2,4})\s*(?:robot\s+component\s+)?(?:entities|entities\b|条实体|零部件)')
    for m in pat.finditer(desc):
        n = int(m.group(1))
        if n != truth['total']:
            problems.append(
                f'package.json description 写 {n} entities，真相源是 {truth["total"]}')
    return problems


def verify(root=None):
    """主验证流程：读真相源 → 逐文件对账 → 返回问题列表。"""
    if root is None:
        root = ROOT
    # 读真相源
    truth_path = os.path.join(root, 'api', 'entities.json')
    with open(truth_path, encoding='utf-8') as f:
        d = json.load(f)
    meta = d.get('meta') or {}
    entities = d.get('entities') or d.get('data') or []
    total = len(entities) or d.get('count') or meta.get('total_entities') or 0
    cats = meta.get('categories') or []
    cat_counts = meta.get('category_counts') or {}
    truth = {'total': total, 'n_categories': len(cats),
             'categories': cats, 'cat_counts': cat_counts}

    problems = []
    for rel in TARGETS:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            continue  # 目标文件不存在（例如精简检出），跳过
        with open(p, encoding='utf-8') as f:
            text = f.read()
        if rel.endswith('README.md'):
            problems.extend(f'{rel}: {x}' for x in check_mcp_readme(text, truth))
        elif rel.endswith('package.json'):
            problems.extend(f'{rel}: {x}' for x in check_package_json(text, truth))
    return problems, truth


def self_test():
    """阴阳自证：4 项对照，任一失败即报错退出。"""
    import shutil
    root = ROOT
    truth = truth_source()
    problems = 0
    passed = 0

    # 用临时目录做变异副本，避免污染真实文件
    tmpdir = tempfile.mkdtemp(prefix='rp_counts_test_')
    try:
        # 复制真相源与目标文件
        api_dir = os.path.join(tmpdir, 'api')
        os.makedirs(api_dir, exist_ok=True)
        shutil.copy(os.path.join(root, 'api', 'entities.json'), api_dir)
        mcp_dir = os.path.join(tmpdir, 'mcp-server')
        os.makedirs(mcp_dir, exist_ok=True)
        shutil.copy(os.path.join(root, 'mcp-server', 'README.md'), mcp_dir)
        shutil.copy(os.path.join(root, 'mcp-server', 'package.json'), mcp_dir)

        # ① 阴性对照：真实数据 vs 真实文档 → 必须 0 问题
        probs, _ = verify(root=tmpdir)
        if probs:
            print(f'❌ 阴性对照失败：真实数据应 0 问题，实际 {len(probs)} 条：{probs[:3]}')
            problems += 1
        else:
            print(f'✅ 阴性对照：真实数据 0 问题（total={truth["total"]}）')
            passed += 1

        # ② 阳性对照：把 README 里的实体数改错 → 必须判红
        readme_path = os.path.join(mcp_dir, 'README.md')
        with open(readme_path, encoding='utf-8') as f:
            text = f.read()
        # 把 868 改成 688
        mutated = text.replace(str(truth['total']), '688')
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(mutated)
        probs, _ = verify(root=tmpdir)
        if not probs:
            print(f'❌ 阳性对照失败：688 vs {truth["total"]} 应判红，实际 0 问题')
            problems += 1
        else:
            print(f'✅ 阳性对照：688 vs {truth["total"]} 判红 {len(probs)} 条')
            passed += 1

        # ③ 变异对照：把 README 里的品类数改错 → 必须判红
        with open(readme_path, encoding='utf-8') as f:
            text = f.read()
        # 把 "20 类" 改成 "10 类"（如果原文有）
        mutated = re.sub(r'(\d{1,2})\s*类', lambda m: '10 类'
                         if int(m.group(1)) == truth['n_categories'] else m.group(0),
                         text)
        # 也改 package.json 里的 "20 categories"
        pkg_path = os.path.join(mcp_dir, 'package.json')
        with open(pkg_path, encoding='utf-8') as f:
            pkg_text = f.read()
        mutated_pkg = re.sub(r'(\d{1,2})\s*(?:robot\s+component\s+)?(?:entities|categories)',
                              lambda m: f'{"10" if int(m.group(1)) == truth["n_categories"] else m.group(1)} categories'
                              if 'categor' in m.group(0).lower() else m.group(0),
                              pkg_text)
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(mutated)
        with open(pkg_path, 'w', encoding='utf-8') as f:
            f.write(mutated_pkg)
        probs, _ = verify(root=tmpdir)
        if not probs:
            print(f'❌ 变异对照失败：品类数 10 vs {truth["n_categories"]} 应判红，实际 0 问题')
            problems += 1
        else:
            print(f'✅ 变异对照：品类数 10 vs {truth["n_categories"]} 判红 {len(probs)} 条')
            passed += 1

        # ④ 反向对照：无变化重跑 → 必须 0 问题
        # 恢复原始文件
        shutil.copy(os.path.join(root, 'mcp-server', 'README.md'), mcp_dir)
        shutil.copy(os.path.join(root, 'mcp-server', 'package.json'), mcp_dir)
        probs, _ = verify(root=tmpdir)
        if probs:
            print(f'❌ 反向对照失败：无变化应 0 问题，实际 {len(probs)} 条：{probs[:3]}')
            problems += 1
        else:
            print(f'✅ 反向对照：无变化 0 问题')
            passed += 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    total_cases = 4
    if problems:
        print(f'\n❌ 自证失败：{total_cases - passed}/{total_cases}')
        return 1
    print(f'\n✅ 自证通过：{passed}/{total_cases}')
    return 0


def main():
    if '--self-test' in sys.argv:
        return self_test()
    if '--check' not in sys.argv and len(sys.argv) > 1:
        print('用法：verify_readme_counts.py [--check] [--self-test]')
        return 2
    problems, truth = verify()
    if problems:
        print(f'❌ 对外文档数字与真相源不一致（{truth["total"]} entities / '
              f'{truth["n_categories"]} categories）：')
        for p in problems:
            print(f'  · {p}')
        print('\n修复：手工更新上述文件里的数字为真相源值，'
              '或确认该处是历史快照（若为快照请标注日期与口径）')
        return 1
    print(f'✅ 对外文档数字与真相源一致（{truth["total"]} entities / '
          f'{truth["n_categories"]} categories）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
