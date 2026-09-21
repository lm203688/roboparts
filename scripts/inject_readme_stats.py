# -*- coding: utf-8 -*-
"""
inject_readme_stats.py —— README 里的**所有数字**由脚本现算注入
================================================================

背景（_MARKET_POSITIONING-20260918.md · P0-2）：
    README 顶部长期写死「688 实体 / 最后更新 2026-08-05」，而真值早已是
    798 实体。GitHub 访客第一印象就是「这项目 6 周没维护」。
    与 onboarding_block 同一纪律：数字唯一真相源 = facts()，README 不写第二份。

【20260921】只注入顶部两行是不够的 —— 定位审计实测：顶部已保鲜到 798，
但 §5「数据分类」仍是 8 月初的快照，8 个品类计数全错且缺 10 个品类：

    actuators   写 217  实 220        sensors          写  90  实  95
    interfaces  写  14  实  44        llms             写  23  实  42
    platforms   写  26  实  41        flexible_actuators 写 6   实  22
    robot_ai_models 写 30 实 46       data_acquisition   写 27  实  46

**没有闸门盯着品类计数**（L2「七处一致」只比对总数），所以它漂了 7 周无人发现。
「总数对、分项错」比总数错更隐蔽：读者核对总数能得到"新鲜"的错觉。
故本脚本把 §5 品类表也收进注入面，并让 §11 的闸门项数从 ci_gate.py 现读
（此前写「8 项」，实际是 9 项子闸门）。

用法（由 scripts/deploy.mjs / regen_derived.py 调用）：
    python scripts/inject_readme_stats.py
幂等：marker 包裹，重复运行只刷新中间内容。
"""
import os
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import onboarding_block as ob  # noqa: E402

MARK_START = '<!-- RP-STATS:START 由 scripts/inject_readme_stats.py 生成，勿手改 -->'
MARK_END = '<!-- RP-STATS:END -->'
CATS_START = '<!-- RP-CATS:START 由 scripts/inject_readme_stats.py 生成，勿手改 -->'
CATS_END = '<!-- RP-CATS:END -->'
GATES_START = '<!-- RP-GATES:START 由 scripts/inject_readme_stats.py 生成，勿手改 -->'
GATES_END = '<!-- RP-GATES:END -->'

#: 品类中文说明（编辑性文字，归生成器持有；计数一律来自 facts()）
CAT_DESC = {
    'actuators': '执行器（电机、谐波减速器、行星滚柱丝杠、无框力矩电机、驱动器、关节模组、灵巧手、腱绳驱动手、开源力控关节、SEA、柔性驱动器）',
    'chips': '芯片（AI 芯片、边缘推理加速器、MCU、FPGA、通信芯片）',
    'sensors': '传感器（视觉相机、六维力/力矩传感器、关节扭矩传感器、触觉传感器、磁性电子皮肤、激光雷达、IMU）',
    'protocols': '通信协议（EtherCAT、CANopen、ROS2、MQTT 等）',
    'data_acquisition': '数据采集设备（遥操作、外骨骼采集、动作捕捉、数据手套、开源具身数据集平台）',
    'robot_ai_models': '机器人 AI 模型（VLA 模型、世界模型、机器人基础模型）',
    'interfaces': '接口标准（法兰、总线、连接器标准文本）',
    'llms': '大模型（VLA 模型、机器人基础模型）',
    'platforms': '机器人平台（含开源可复现整机）',
    'grippers': '夹爪与末端执行器',
    'flexible_actuators': '柔性执行器（人工肌肉、柔性驱动器、仿生脊柱）',
    'bionic_mechanisms': '仿生机构（仿生关节、仿生驱动器、仿生传感器）',
    'reducers': '减速器（谐波、行星、RV）',
    'controllers': '控制器',
    'structural': '结构件',
    'cables': '线缆',
    'connectors': '连接器',
    'pcb': 'PCB',
    'power': '电源',
    'integrated_joints': '一体化关节模组',
}


def last_updated():
    """最后更新取最近一次提交日期（fallback 当天）。"""
    try:
        out = subprocess.run(
            ['git', 'log', '-1', '--date=short', '--format=%cd'],
            cwd=ROOT, capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return date.today().isoformat()


def stats_block(f, day):
    return (
        f'- **数据量**：{f["total_entities"]} 实体'
        f'（{f["component_entities"]} 实物零部件 / {f["specification_entities"]} 接口规范 / '
        f'{f["software_entities"]} AI 模型软件 / {f["organization_entities"]} 企业主体 / '
        f'{f["market_intelligence_entities"]} 市场情报）；'
        f'机械接口声明率 {f["mech_pct"]}%（{f["mech_declared"]}/{f["mech_applicable"]}）；'
        f'开源组件 {f["oss_total"]}\n'
        f'- **最后更新**：{day}'
    )


def cats_block(f):
    """§5 数据分类：计数来自 facts()，按条数降序。缺说明的品类照样列出（不静默丢品类）。"""
    cc = f['category_counts']
    if sum(cc.values()) != f['total_entities']:
        raise SystemExit('!! 分品类求和(%d) != 总数(%d)，拒绝注入 README'
                         % (sum(cc.values()), f['total_entities']))
    missing = sorted(set(cc) - set(CAT_DESC))
    if missing:
        # 新增品类却没人写说明 → 让它以裸计数出现而不是被漏掉，但必须吵一声。
        print('   ⚠ README 品类说明缺失（将只列计数）: %s' % ' '.join(missing))
    lines = []
    for cat, n in sorted(cc.items(), key=lambda x: (-x[1], x[0])):
        desc = CAT_DESC.get(cat, '')
        lines.append('- **%s**: %d 条%s' % (cat, n, (' — ' + desc) if desc else ''))
    return '\n'.join(lines)


def gate_count():
    """ci_gate.py 注册的子闸门数 —— 现读，不在 README 手写「8 项」。

    刻意用 `--list` 的**实际输出行数**而不是正则解析源码：正则版只会数到
    它认得的写法，注册表换个形式（多行 lambda / 元组换行）就静默少数几项，
    而"少数了几项"没有任何人会发现。跑一次拿行数，是唯一不会说谎的口径。
    """
    p = os.path.join(ROOT, 'scripts', 'ci_gate.py')
    out = subprocess.run([sys.executable, p, '--list'],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise SystemExit('!! ci_gate.py --list 退出码 %s，README 闸门项数拒绝生成：%s'
                         % (out.returncode, (out.stderr or '')[-300:]))
    names = [x for x in out.stdout.splitlines() if x.strip()]
    if not names:
        raise SystemExit('!! ci_gate.py --list 输出为空，README 闸门项数拒绝生成')
    return len(names)


def _replace_between(text, start, end, body):
    if start in text and end in text:
        head = text[:text.index(start)]
        tail = text[text.index(end) + len(end):]
        return head + body + tail
    return None


def inject():
    f = ob.facts()
    day = last_updated()
    readme = os.path.join(ROOT, 'README.md')
    with open(readme, encoding='utf-8') as fh:
        text = fh.read()
    changed = []

    # ① 顶部数据量 / 最后更新
    seg = f'{MARK_START}\n{stats_block(f, day)}\n{MARK_END}'
    new = _replace_between(text, MARK_START, MARK_END, seg)
    if new is None:
        new = text.replace('# RoboParts — 机器人零件兼容性判定层\n',
                           '# RoboParts — 机器人零件兼容性判定层\n\n' + seg + '\n', 1)
    if new != text:
        changed.append('数据量/最后更新')
    text = new

    # ② §5 品类表
    seg = f'{CATS_START}\n{cats_block(f)}\n{CATS_END}'
    new = _replace_between(text, CATS_START, CATS_END, seg)
    if new is None:
        raise SystemExit('!! README 缺 RP-CATS 标记：§5 品类表不在注入面内就必然再次失修')
    if new != text:
        changed.append('品类表(%d 类)' % len(f['category_counts']))
    text = new

    # ③ §11 闸门项数（inline，形如 `# 仓内可判定的 N 项闸门`）
    n = gate_count()
    new = _replace_between(text, GATES_START, GATES_END, '%s%d%s' % (GATES_START, n, GATES_END))
    if new is None:
        raise SystemExit('!! README 缺 RP-GATES 标记')
    if new != text:
        changed.append('闸门项数(%d)' % n)
    text = new

    with open(readme, 'w', encoding='utf-8') as fh:
        fh.write(text)
    print('✅ README 注入完成：%d 实体 / %s；变更 %s'
          % (f['total_entities'], day, '、'.join(changed) or '无'))


if __name__ == '__main__':
    inject()
