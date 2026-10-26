from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

NAVY = '#102A43'
BLUE = '#1677FF'
CYAN = '#0E9F9F'
PURPLE = '#7357C8'
ORANGE = '#D97706'
LIGHT = '#F4F7FB'
GRAY = '#52667A'
GREEN = '#25855A'


def box(ax, x, y, w, h, title, body, color=BLUE, fs=12):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.014,rounding_size=0.018',
                                facecolor='white', edgecolor=color, linewidth=1.8))
    ax.text(x+w/2, y+h*0.68, title, ha='center', va='center', color=color,
            fontsize=fs+1, fontweight='bold')
    ax.text(x+w/2, y+h*0.32, body, ha='center', va='center', color=GRAY,
            fontsize=fs-1, linespacing=1.45)


def arrow(ax, x1, y1, x2, y2, color='#8AA0B5'):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>', mutation_scale=14,
                                linewidth=1.5, color=color))

# Figure 1: target architecture
fig, ax = plt.subplots(figsize=(16, 10), dpi=160)
fig.patch.set_facecolor(LIGHT)
ax.set_facecolor(LIGHT)
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
ax.text(0.05, 0.945, 'RoboParts 目标架构：可验证组合与证据操作系统', fontsize=24,
        color=NAVY, fontweight='bold', va='center')
ax.text(0.05, 0.905, '大模型提出候选与抽取证据；确定性引擎裁决；人类确认高风险结论',
        fontsize=13, color=GRAY, va='center')

box(ax, .05, .72, .26, .12, '双通道交互层', '工程师工作台 · Agent / MCP\n共享项目状态 · 审批 · 可回放事件', BLUE)
box(ax, .37, .72, .26, .12, '项目与任务层', 'Project v2 · 版本化快照\n事件溯源 · 差异比较 · 跨设备恢复', PURPLE)
box(ax, .69, .72, .26, .12, '交付与适配层', 'BOM / 转接件 / URDF / MJCF\nROS 2 · OpenUSD · AAS 模块护照', CYAN)

box(ax, .05, .43, .41, .18, 'Composition IR + 确定性规则引擎', '机械 / 电气 / 信号 / 软件 / 运行时 / 动力学\n三态裁决 · 反例 · 修复建议 · 约束求解\n组合不是文本相似度，而是可证伪的工程契约', BLUE, 13)
box(ax, .54, .43, .41, .18, 'Evidence Graph + Module Passport', '字段级来源坐标 · 单位 / 公差 · 版本 · 时效\n厂商声明 / 推断 / 估算 / 实测严格分离\n实体、接口、资产、策略与验证结果统一溯源', PURPLE, 13)

box(ax, .05, .18, .26, .13, '多模态取证', 'Datasheet · 工程图 · CAD\n针脚 / 尺寸 / 规则结构化抽取', ORANGE)
box(ax, .37, .18, .26, .13, '验证与评估', 'Golden 场景 · 变异测试\n跨引擎导入 · 真机标定', GREEN)
box(ax, .69, .18, .26, .13, '外部生态', '厂商数据 · Onshape / CAD\nIsaac / MuJoCo · ROS 2', CYAN)

arrow(ax, .18, .72, .22, .61); arrow(ax, .50, .72, .50, .61)
arrow(ax, .82, .72, .79, .61)
arrow(ax, .46, .52, .54, .52)
arrow(ax, .18, .31, .22, .43); arrow(ax, .50, .31, .50, .43); arrow(ax, .82, .31, .79, .43)
ax.text(.5, .075, '核心边界：不复制通用 CAD、通用仿真器或世界模型；RoboParts 负责约束、证据与验证闭环。',
        ha='center', fontsize=13, color=NAVY, fontweight='bold')
fig.savefig(OUT/'roboparts_target_architecture.png', bbox_inches='tight', facecolor=fig.get_facecolor())
plt.close(fig)

# Figure 2: roadmap
fig, ax = plt.subplots(figsize=(17, 8.5), dpi=160)
fig.patch.set_facecolor(LIGHT); ax.set_facecolor(LIGHT)
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
ax.text(.04, .93, '从“页面与目录”走向“可验证工程闭环”', fontsize=24, color=NAVY, fontweight='bold')
ax.text(.04, .88, '每一阶段以可观察的退出条件验收，而不是以新增页面数验收', fontsize=13, color=GRAY)

stages = [
    (.04, .23, '0–2 周｜止血与对齐', BLUE,
     ['修复规划恢复 / BOM / 分享断点', '消除仓库与生产漂移', 'CSP、MJCF、CI Windows 验证'],
     '退出：五步主链路 E2E 通过\n生产冒烟全绿，CI 无环境性失败'),
    (.28, .23, '3–8 周｜真实任务闭环', PURPLE,
     ['Project v2 服务端快照与事件', '50 个高价值实体补字段级证据', '30–50 个 Golden 场景'],
     '退出：六轴臂＋夹爪任务可保存\n恢复、复算、导出、分享并回放'),
    (.52, .23, '2–4 月｜资产与标准契约', CYAN,
     ['仿真资产 L0–L2 分级', 'ROS 2 Runtime Profile', 'ISO 22166 CIM 模块护照'],
     '退出：导出物可导入、运动学有效\n来源、单位、估算边界可机器读取'),
    (.76, .20, '4–12 月｜生态与数字线程', GREEN,
     ['MCP 双版本 / 事件流工作台', 'OpenUSD / AAS / 跨引擎回归', '策略硬件匹配与运行期反馈'],
     '退出：外部 Agent 可完成组合任务\n验证结果回流并提升兼容覆盖率'),
]
for x, w, title, color, items, exit_text in stages:
    ax.add_patch(FancyBboxPatch((x, .24), w, .53, boxstyle='round,pad=.014,rounding_size=.02',
                                facecolor='white', edgecolor=color, linewidth=2))
    ax.text(x+w/2, .72, title, ha='center', va='center', fontsize=14, color=color, fontweight='bold')
    for i, item in enumerate(items):
        ax.text(x+.018, .62-i*.085, '• '+item, ha='left', va='center', fontsize=11.5, color=NAVY)
    ax.plot([x+.018, x+w-.018], [.405, .405], color='#DDE6EF', lw=1)
    ax.text(x+w/2, .325, exit_text, ha='center', va='center', fontsize=10.5, color=GRAY, linespacing=1.5)
    if x < .7:
        arrow(ax, x+w+.003, .505, x+w+.025, .505)
ax.text(.5, .12, '资源优先级：证据密度与主链路可靠性 ＞ 新页面、新模型、新协议数量',
        ha='center', fontsize=15, color=NAVY, fontweight='bold')
fig.savefig(OUT/'roboparts_upgrade_roadmap.png', bbox_inches='tight', facecolor=fig.get_facecolor())
plt.close(fig)

print('Generated report figures in', OUT)
