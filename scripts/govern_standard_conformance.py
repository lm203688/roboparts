#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Schema 治理：为实体补 standard_conformance（标准符合度追踪）。

背景（P0 情报 20260805）：
  - T/CAEE 060-2026《人形机器人互操作性与安全通用准则》已发布（团体标准）
  - 20262893-T-604《人形机器人模块化通用技术要求》国标在研（TC591 归口，15 个月周期）
    其「最小互操作技术栈」= 千兆以太网 + PTP + ROS 2 控制接口，硬件最小模块 = 一体化关节
  - 工信部人形机器人标委会新增 WG7 数据工作组；核心部件与通信接口立 6 项标准

设计原则（严禁编造）：
  1. 只从实体**已声明**的 protocol / interface / bus / communication / ros_support 推导；
  2. 无声明数据 -> assessed=False，一律 unknown，绝不猜测；
  3. 本字段是「符合度线索」而非第三方认证结论，disclaimer 写在 meta 里（不逐条重复，控体积）；
  4. interop_posture（厂商互操作立场）只对**有公开信源明确点名**的厂商赋值，其余 unknown。

幂等：可重复运行。运行后需再跑 normalize_categories.py 重生成派生文件。
"""
import copy
import json
import os
import re
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# RP_ENTITIES_JSON 重定向：闸门可在副本上试算而不碰真实数据（见 ci_gate.py）。
ENTITIES_PATH = (os.environ.get('RP_ENTITIES_JSON')
                 or os.path.join(ROOT, 'api', 'entities.json'))

# ---- 总线类别归一 ----------------------------------------------------------
# 顺序敏感：先匹配更具体的
BUS_RULES = [
    ('EtherCAT',    r'ethercat'),
    ('PROFINET',    r'profinet'),
    ('EtherNet/IP', r'ethernet\s*[/\-]?\s*ip|ethernetip'),
    ('CANopen',     r'canopen'),
    ('CAN',         r'\bcan\b|can\s*bus'),
    ('RS485',       r'rs\s*-?\s*485|ttl\s*/\s*rs485'),
    ('RS232',       r'rs\s*-?\s*232'),
    ('Modbus',      r'modbus'),
    ('IO-Link',     r'io-?link'),
    ('Ethernet',    r'\bethernet\b|\btcp\b|\budp\b'),
    ('UART',        r'\buart\b|\bttl\b'),
    ('USB',         r'\busb\b'),
    ('SPI',         r'\bspi\b'),
    ('I2C',         r'\bi2c\b'),
    ('PWM',         r'\bpwm\b'),
    ('PCIe',        r'\bpcie\b'),
    ('MIPI',        r'\bmipi\b'),
    ('WiFi',        r'wifi|wi-fi'),
    ('proprietary', r'proprietary|专有|private|custom|helix|dynamixel'),
]

# 20262893-T-604 最小互操作技术栈：千兆以太网 + PTP + ROS 2
ETHERNET_CLASS = {'Ethernet', 'EtherCAT', 'PROFINET', 'EtherNet/IP'}

# T/CAEE 060-2026 互操作相关类目（模块互操作与接口规范直接作用对象）
CAEE060_CATEGORIES = {
    'actuators', 'flexible_actuators', 'interfaces',
    'protocols', 'sensors', 'platforms',
}

# ISO 22166 模块化标准适用域（保守：仅模块化最相关的四类，无编号口径一律不采）
# 20260808-13：原注释写"三类"而集合实为四类 —— 注释与代码不一致同属口径≠事实，一并纠正。
ISO22166_RELEVANT_CATEGORIES = {
    'actuators', 'flexible_actuators', 'interfaces', 'platforms',
}

# 仅收录公开信源明确点名的厂商立场（信源：WAIC2026 报道 / 标委会公开材料）
# closed=全栈自研封闭  semi_open=半开放自研  multi_protocol=多协议兼容
INTEROP_POSTURE = {
    'tesla':      'closed',
    'figure':     'closed',
    'unitree':    'semi_open',
    '宇树':        'semi_open',
    '智元':        'semi_open',
    'agibot':     'semi_open',
    '星动纪元':     'multi_protocol',
    'robotera':   'multi_protocol',
    '华沿':        'multi_protocol',
}

STANDARDS_SPEC = {
    "version": "2026-08-10",
    "purpose": "追踪实体对人形机器人互操作性标准的符合度线索",
    "standards": [
        {
            "id": "T/CAEE 060-2026",
            # 题录库题名用「人型」，新闻稿多写作「人形」。检索时两种写法都要试，
            # 否则会误判为"查无此标"。
            "name": "人型机器人互操作性与安全通用准则",
            "name_variant": "人形机器人互操作性与安全通用准则（新闻稿常用写法）",
            "type": "团体标准",
            "status": "现行",
            "issued_at": "2026-06-10",
            "effective_at": "2026-06-10",
            "announced_at": "2026-07-24",
            "project_no": "2025-003T-CAEE",
            "issuer": "中国电子装备技术开发协会",
            # 【20260809-12 更正】此前记为「已发布 / 7-31 / 2026-07」——那是新闻稿的
            # 发文时间戳，不是标准的发布时间。题录库载明 2026-06-10 发布并实施、
            # 2026-07-24 公布、状态现行：该标准已实施约两个月，而非"刚刚发布"。
            # 同形态错误在 T/YNIPA 033-2026 上已犯过一次，这是第二次。
            "evidence": "https://www.ttbz.org.cn/standardDetail/"
                        "97d5dfe73aa7424b96af6492e346ae66.html",
            "evidence_tier": "题录库（全国团体标准信息平台）",
        },
        {
            "id": "T/CAEE 073-2026",
            "name": "人形机器人智能决策与自主行为标准框架",
            "type": "团体标准",
            "status": "现行",
            "issued_at": "2026-06-10",
            "effective_at": "2026-06-10",
            "announced_at": "2026-07-24",
            "project_no": "2025-004T-CAEE",
            "issuer": "中国电子装备技术开发协会",
            # 与 060 同一批公告（中电协【2026】410 号）发布，此前我方完全未记录 ——
            # 漏记本身说明我方是"跟着新闻稿走"而非"跟着题录库走"：新闻只报了 060。
            "evidence": "https://www.ttbz.org.cn/2064542694756528130.html",
            "evidence_tier": "题录库（发布机构公告原文）",
            "scope_note": "决策/自主行为层，不直接作用于零部件机械或电气接口，暂不进判据",
        },
        {
            "id": "20262893-T-604",
            "name": "人形机器人模块化通用技术要求",
            "type": "推荐性国家标准",
            "status": "在研（2026-05-22 下达计划，周期 15 个月，当前「正在起草」）",
            "plan_released_at": "2026-05-22",
            "issuer": "TC591 全国机器人标准化技术委员会",
            "executor": "TC591/SC5 全国机器人标准化技术委员会人形机器人分技术委员会",
            "min_interop_stack": "千兆以太网 + PTP + ROS 2 控制接口",
            "min_hw_module": "一体化关节",
            "min_sw_module": "ROS 2 组件",
            # 【20260809-13 存量补证】此前该条带「2026-05-22 立项」日期断言却无任何
            # 证据链接。经国家标准计划库核验：断言属实（下达 2026-05-22 / 周期 15 个月 /
            # 正在起草 / 公示 2026-04-02~05-02），仅补链接与执行单位，未改事实。
            "evidence": "https://std.samr.gov.cn/gb/search/gbDetailed"
                        "?id=529F257D3C34D47BE06397BE0A0AFFBC",
            "evidence_tier": "国家标准计划库（std.samr.gov.cn 计划详情）",
        },
        {
            "id": "20261783-T-604",
            "name": "人形机器人智能化能力评价方法",
            "type": "推荐性国家标准",
            "status": "在研（2026-03-31 下达计划，周期 12 个月，当前「正在起草」）",
            "plan_released_at": "2026-03-31",
            "issuer": "TC591 全国机器人标准化技术委员会",
            "executor": "TC591/SC5 人形机器人分技术委员会",
            # 【20260809-13 存量补证】原记仅「在研」二字，既无日期也无出处 ——
            # 这种"看起来无害的模糊记法"同样无法被证伪，是错误的温床。
            "evidence": "https://std.samr.gov.cn/gb/search/gbDetailed"
                        "?id=4E646C4DFD7176CBE06397BE0A0AD8CD",
            "evidence_tier": "国家标准计划库（std.samr.gov.cn 计划详情）",
            "scope_note": "智能化能力评价，不作用于零部件接口，不进判据",
        },
        {
            "id": "ISO 22166-201:2024",
            "name": "Robotics — Modularity for service robots — Part 201: Common information model (CIM) for modules",
            "type": "国际标准（ISO/TC 299）",
            "status": "已发布（stage 60.60 现行）",
            "issued_at": "2024-02-23",
            "issuer": "ISO/TC 299",
            "note": "模块公共信息模型：规定模块该用哪些属性描述才能互操作/可复用/可组合。仅作适用域标注，不构成符合性结论。",
            "evidence": "https://www.iso.org/standard/82334.html",
            "evidence_tier": "发布机构官方条目（ISO 官网 life cycle）",
        },
        {
            "id": "ISO 22166-1:2021",
            "name": "Robotics — Modularity for service robots — Part 1: General requirements",
            "type": "国际标准（ISO/TC 299）",
            "status": "stage 90.92 待修订（2025-06-26 进入），后继项目 ISO/AWI 22166-1",
            "issued_at": "2021-02-01",
            "issuer": "ISO/TC 299",
            "evidence": "https://www.iso.org/standard/72715.html",
            "evidence_tier": "发布机构官方条目（ISO 官网 life cycle）",
        },
        # ------------------------------------------------------------------
        # 【20260809-13 补录】现行国标：直接管"驱动模块接口 / 一体化关节"。
        # 补录动机不是"又发现两条新标准"，而是发现追踪表存在**选择性偏差**：
        # 原 6 条 = 2 团标 + 2 在研国标 + 2 ISO，**一条现行且直接作用于零部件
        # 接口的国标都没有**。因为过去的入库触发器是"新闻里出现人形机器人标准"，
        # 而不是"作用域命中零部件接口"。热点驱动 ≠ 作用域驱动。
        # ------------------------------------------------------------------
        {
            "id": "GB/T 38560-2020",
            "name": "工业机器人的通用驱动模块接口",
            "name_en": "Interface of universal driver module for industrial robots",
            "type": "推荐性国家标准",
            "status": "现行（2025-12-08 复审结论：继续有效）",
            "issued_at": "2020-03-06",
            "effective_at": "2020-10-01",
            "last_reviewed_at": "2025-12-08",
            "issuer": "TC591 全国机器人标准化技术委员会",
            "evidence": "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo"
                        "?hcno=808ACC3D1777B5E4E9EB3D3F4F028C89",
            "evidence_tier": "国家标准全文公开系统（openstd.samr.gov.cn）",
            "scope_note": "驱动模块 = 伺服电机+减速器+制动器+编码器+驱动器 的独立驱动单元；"
                          "规定其设计原则与模块化结构设计要求。与本站 actuators/drivetrain "
                          "类目作用域直接重合，但标准本身不规定具体尺寸配合，故仅作适用域"
                          "标注，不进兼容判据。",
        },
        {
            "id": "GB/T 43200-2023",
            "name": "机器人一体化关节性能及试验方法",
            "name_en": "Performance and related test methods of mechatronic joints for robots",
            "type": "推荐性国家标准",
            "status": "现行",
            "issued_at": "2023-09-07",
            "effective_at": "2024-04-01",
            "issuer": "TC591 全国机器人标准化技术委员会",
            "evidence": "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo"
                        "?hcno=B2E40B3445ACE9E166E8E402E89853AF",
            "evidence_tier": "国家标准全文公开系统（openstd.samr.gov.cn）",
            "scope_note": "适用于协作机器人及腿足式机器人关节，其他机器人关节参照执行。"
                          "规定性能项与试验方法，不规定接口尺寸，不进兼容判据。",
        },
        # ------------------------------------------------------------------
        # 【20260810-12 补录】**第一条由「枚举发布平台全表」而非关键词检索找到的标准。**
        # 此前所有入库线索都来自"某处提到了它"；本条是 scripts/enumerate_standards.py
        # 把国家标准题录表按主题词整表拉下来（164 条去重）后，用两因子触发器
        # （领域=机器人零部件 且 层面=接口）筛出来的——它 2013 年就发布了，
        # 十二年间没有任何一篇我方读过的报道提过它。这正是 8/10 立下的教训：
        # 关键词召回的天花板是"曾被报道过"，枚举召回才够到"曾被发布过"。
        # ------------------------------------------------------------------
        {
            "id": "GB/T 29825-2013",
            "name": "机器人通信总线协议",
            "type": "国家标准（指导性技术文件）",
            "status": "现行",
            "issued_at": "2013-11-12",
            "effective_at": "2014-04-01",
            # 两个官方源给的发布日期不一致，不擅自二选一：
            #   std.samr 题录 ISSUE_DATE = 2013-11-12
            #   openstd 列表「发布日期」列 = 2023-11-02（疑为复审/数据更新时间）
            # 按题录库口径取 2013-11-12，并把分歧显式留痕，避免后人误以为是新标。
            "date_discrepancy_note": "openstd 列表页发布日期列显示 2023-11-02，"
                                     "与 std.samr 题录 2013-11-12 不一致；实施日期两源"
                                     "一致为 2014-04-01。已按题录库取值并留痕，未做静默取舍。",
            "issuer": "TC591 全国机器人标准化技术委员会",
            "evidence": "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo"
                        "?hcno=6337492B943BFA7D793FF14B579499EA",
            "evidence_tier": "国家标准全文公开系统（openstd.samr.gov.cn）",
            "discovered_by": "scripts/enumerate_standards.py（发布平台整表枚举，非关键词搜新闻）",
            "scope_note": "规定机器人通信总线协议，作用于本站 protocol/bus 维度——"
                          "这是本登记表首条直接落在**通信接口层**的现行国标（此前 10 条"
                          "要么管机械/整机，要么是团标）。但它是**指导性技术文件**（性质列"
                          "「指导」），非强制亦非推荐性，且发布于 2013 年、早于 EtherCAT/"
                          "CANopen 在机器人关节上的普及，与当下实体声明的总线类别对应关系"
                          "尚未逐条核对。故本轮仅作适用域标注，**不进兼容判据**，"
                          "待取得全文并逐条比对后再决定是否升级为判据。",
        },
        # ------------------------------------------------------------------
        # 【20260809-14 补录】现行团标，直接管「直驱关节模组」接口。
        # 来源 cssn.net.cn（中国标准服务网·题录库，白名单主机），非新闻稿；
        # 与上一轮补录 GB/T 38560-2020 / GB/T 43200-2023 同一动机：
        # 追踪表此前缺「现行且直接管零部件接口」的标准，且入库偏新闻驱动。
        # 本条由 P0 情报按「作用域命中零部件接口」反查题录库所得，不是热搜撞出来的。
        # ------------------------------------------------------------------
        {
            "id": "T/WEA 122-2026",
            "name": "轮足式机器人及直驱关节模组技术要求",
            "type": "团体标准",
            "status": "现行",
            "issued_at": "2026-07-16",
            "effective_at": "2026-07-16",
            "issuer": "中国智慧工程研究会",
            "evidence": "https://cssn.net.cn/cssn/productDetail/cf84f92855118095d61b1a2d85ae587d",
            "evidence_tier": "题录库（中国标准服务网 cssn.net.cn）",
            "scope_note": "规定轮足式机器人及直驱关节模组全维度技术要求，含机械/电气/通信接口"
                          "统一规范（支持 EtherCAT/CANopen 总线）、扭矩密度/运动精度/动态响应/"
                          "扭转刚度等核心性能与 EMC/环境适应性指标。与本站 actuators/一体化关节"
                          "类目作用域直接重合，但标准不规定具体尺寸配合，故仅作适用域标注，不进兼容判据。",
        },
        # ------------------------------------------------------------------
        # 【20260810-10 补录】迄今与本站命题最贴合的一条：它是登记表里第一条
        # 同时规定「机械 + 电气 + 通信」三层接口的现行标准，作用域正是一体化关节。
        #
        # 值得记的是**它是怎么被漏掉的**：公布于 2025-09-28、2025-12-25 起实施，
        # 到本轮已现行 7 个半月，而我方连续多轮"P0 情报"都没碰到它 —— 因为它
        # 从未上过热搜。前几轮已把入库触发器从"新闻提到人形机器人"改成"作用域
        # 命中零部件接口"，但**检索手段仍是关键词搜新闻/题录库**，关键词只能捞到
        # 被人写过的东西。本条是改用「按发布机构枚举其已发布标准全表」找到的：
        # 归口单位（北京智能机器人产业技术创新联盟）在 ttbz 的团体页把 7 项标准
        # 全列了出来，一次抓取即穷举。**触发器对了不等于召回率够** —— 关键词搜索
        # 的召回天花板是"曾被报道过"，机构枚举的召回天花板才是"曾被发布过"。
        # ------------------------------------------------------------------
        {
            "id": "T/BTIAIRI 0001-2025",
            "name": "人形机器人电驱动一体化关节接口要求",
            "type": "团体标准",
            "status": "现行",
            "issued_at": "2025-09-25",
            "announced_at": "2025-09-28",
            "effective_at": "2025-12-25",
            "issuer": "北京智能机器人产业技术创新联盟",
            "ics": "25.040.30 工业机器人、机械手",
            "industry_class": "C3489 其他通用零部件制造",
            "evidence": "https://www.ttbz.org.cn/standardDetail/"
                        "edvhdjkontoth7ysxhv8ur1on2t6ubn.html",
            "evidence_tier": "题录库（全国团体标准信息平台 ttbz.org.cn 标准详情页）",
            "scope_note": "登记表中作用域最贴近本站命题的一条：正文按「机械接口 / 电气接口 / "
                          "通信接口 / 线缆·连接器·引出线」四段规定一体化关节接口。机械侧分"
                          "旋转关节（输出盘径向圆跳动、凸缘止口对输出盘轴线径向圆跳动）与"
                          "直线关节（球轴承孔位径向圆跳动、基座轴承孔径向跳动）；电气侧规定"
                          "额定直流电压、接插件、工频耐压等级、绝缘电阻，并要求中空孔走线"
                          "（关节级联供电 / 关节并联供电两种方式）；通信侧规定端子与协议层。"
                          "注意：所规定的机械项是**形位公差/跳动类指标**，不是孔位圆直径、"
                          "螺栓数、螺纹规格这类可直接判互换的名义配合尺寸，故与 ISO 9409-1 "
                          "不同，本条仍只作适用域标注，不进兼容判据。",
        },
        # ------------------------------------------------------------------
        # 【20260810-19 补录】以下 4 条来自修复翻页 bug 后的 GB 整表枚举。
        # 修复前 std.samr 的 `current` 参数被服务端静默忽略，每个检索词只反复
        # 返回前 50 条 —— 名义上"整表枚举 164 条"，实为 7 个词各取前 50 去重。
        # 改用 `pageNo` 后扫描面 164 → 434 条，下面这些落在第 50 条之后的标准
        # 才第一次进入视野。GB/T 14468 系列自 2006 年起现行、题名直书"工业机器人
        # 机械接口"，正是本站旗舰页 ISO 9409-1 的国标对位对象，却被漏了三周。
        # 教训：上一轮说"关键词召回天花板是曾被报道过"，这轮补一句 ——
        # **枚举器有 bug 时，它的召回天花板是「第一页」**，而且不会报错。
        # ------------------------------------------------------------------
        {
            "id": "GB/T 14468.1-2006",
            "name": "工业机器人 机械接口 第1部分：板类",
            "type": "国家标准",
            "status": "现行",
            "issued_at": "2006-04-03",
            "effective_at": "2006-09-01",
            "issuer": "国家标准化管理委员会",
            "evidence": "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno="
                        "8ACD319F2788EDB5B6B80ACA3F78AEB7",
            "evidence_tier": "题录库（国家标准全文公开系统 openstd.samr.gov.cn）",
            "scope_note": "登记表中与本站命题作用域最正面重合的国家标准：题名即「工业"
                          "机器人 机械接口 板类」，与本站旗舰页 ISO 9409-1（圆形安装板"
                          "机械接口）为同一对象域。**正文尺寸口径尚未核对原文**，在拿到"
                          "全文前不断言其与 ISO 9409-1 的采标关系或数值一致性，"
                          "故暂只作适用域标注、不进兼容判据。",
        },
        {
            "id": "GB/T 14468.2-2006",
            "name": "工业机器人 机械接口 第2部分：轴类",
            "type": "国家标准",
            "status": "现行",
            "issued_at": "2006-04-03",
            "effective_at": "2006-09-01",
            "issuer": "国家标准化管理委员会",
            "evidence": "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno="
                        "95C45813FFB28336745A0FB812ED747A",
            "evidence_tier": "题录库（国家标准全文公开系统 openstd.samr.gov.cn）",
            "scope_note": "14468 系列第 2 部分，对象为轴类机械接口（对位 ISO 9409-2 的"
                          "对象域）。同样未核原文尺寸口径，不进兼容判据。",
        },
        {
            "id": "GB/T 32197-2025",
            "name": "工业机器人控制器开放式通信接口规范",
            "type": "国家标准",
            "status": "现行",
            "issued_at": "2025-04-25",
            "effective_at": "2025-11-01",
            "issuer": "国家标准化管理委员会",
            "evidence": "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno="
                        "F240EEB38623E809D6BF7BC79DA70013",
            "evidence_tier": "题录库（国家标准全文公开系统 openstd.samr.gov.cn）",
            "scope_note": "作用对象是控制器这一零部件本身的通信接口（与本站控制器类目"
                          "直接对应），且为 2025 年发布、2025-11-01 起实施的现行国标。"
                          "正文协议层要求未核，不进兼容判据。",
        },
        {
            "id": "GB/T 33266-2016",
            "name": "模块化机器人高速通用通信总线性能",
            "type": "国家标准",
            "status": "现行",
            "issued_at": "2016-12-13",
            "effective_at": "2017-07-01",
            "issuer": "国家标准化管理委员会",
            "evidence": "https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno="
                        "9D69D85CDFF8D30184BC47CE7C2D59C2",
            "evidence_tier": "题录库（国家标准全文公开系统 openstd.samr.gov.cn）",
            "scope_note": "模块化机器人总线域，与本站 bus_class 维度同域。但题名限定"
                          "「性能」，规定的是速率/时延一类指标而非引脚与协议定义，"
                          "与 T/BTIAIRI 0001-2025 同理：只作适用域标注，不进判据。",
        },
        # ------------------------------------------------------------------
        # 【20260811-04 新增】团标域首次整表枚举（ndls.org.cn ICS 25.040.30 +
        # 25.040.01 共 799 条去重）后的入库批次。此前 9 轮"标准域零可入库"
        # 全部来自关键词检索，而这 4 条**一条都没上过热搜** —— 与 8/10 抓到
        # T/BTIAIRI 0001-2025 时的教训完全同型：关键词的天花板是"曾被报道过"。
        # 每条的日期/状态都挂 ops/intel/standards-evidence-snapshots.json 的
        # 详情页原文快照（独立二次抓取，不复用枚举器的解析结果），由 L1.86 逐字比对。
        # ------------------------------------------------------------------
        {
            "id": "T/CAMETA 40004-2021",
            "name": "协作机器人末端接口技术条件",
            "type": "团体标准",
            "status": "现行",
            "issued_at": "2021-05-17",
            "effective_at": "2021-06-16",
            "issuer": "中国机电一体化技术应用协会",
            "evidence": "https://www.ndls.org.cn/standard/detail/"
                        "1ce7b58b386d8dc3ad4067c1297495c8",
            "evidence_tier": "题录库（国家数字标准馆 ndls.org.cn，中国标准化研究院主办）",
            "scope_note": "题录页范围条文原文：「规定了不同负载范围的协作机器人，腕关节与"
                          "末端执行器的接口技术条件」——这是登记表中第一条作用域正面命中"
                          "本站核心命题（腕部法兰 ↔ 末端执行器对接）的国内现行标准，"
                          "且与 run-73 刚落地的 mateable（工具侧↔安装侧）判据同一对象。"
                          "起草单位含节卡/遨博/越疆/艾利特/新松/配天/同川等主流协作臂厂商。"
                          "诚实边界：题录页只公开范围与章节名，未公开孔位/螺纹的名义尺寸，"
                          "因此仍只作适用域标注，不进兼容判据。",
        },
        {
            "id": "T/CEATEC 162-2026",
            "name": "机器人自动快换盘机械总成技术规范",
            "type": "团体标准",
            "status": "现行",
            "issued_at": "2026-01-30",
            "effective_at": "2026-01-30",
            "issuer": "中国欧洲经济技术合作协会",
            "evidence": "https://www.ndls.org.cn/standard/detail/"
                        "72b96326b68d584f187492858aa39b5e",
            "evidence_tier": "题录库（国家数字标准馆 ndls.org.cn，中国标准化研究院主办）",
            "scope_note": "快换盘（tool changer）是机器人侧与工具侧之间的物理对接件本身，"
                          "作用域正是本站 mateable 判据的对象。题录页范围为"
                          "「技术要求、试验方法、检验规则、标志、包装、运输和贮存」，"
                          "属产品规范而非接口尺寸规范，不进判据。",
        },
        {
            "id": "T/CAMETA 001110-2026",
            "name": "工业机器人传感器接口与通信协议规范",
            "type": "团体标准",
            "status": "现行",
            "issued_at": "2026-01-26",
            "effective_at": "2026-04-01",
            "issuer": "中国机电一体化技术应用协会",
            "evidence": "https://www.ndls.org.cn/standard/detail/"
                        "9ca6687bdaa78ff25956fe806a78d398",
            "evidence_tier": "题录库（国家数字标准馆 ndls.org.cn，中国标准化研究院主办）",
            "scope_note": "作用域为传感器零部件的接口 + 通信协议两层，与本站 sensors 类目"
                          "及 bus_class 维度同域。**诚实边界：该条题录页未公开范围条文**"
                          "（另三条都有），作用域判断仅依据标题与 ICS 25.040.30，"
                          "证据强度低于同批其余三条，取到全文前不进判据。",
        },
        {
            "id": "T/QGCML 3326-2024",
            "name": "工业机器人管线包接口规范",
            "type": "团体标准",
            "status": "现行",
            "issued_at": "2024-03-14",
            "effective_at": "2024-03-29",
            "issuer": "全国城市工业品贸易中心联合会",
            "evidence": "https://www.ndls.org.cn/standard/detail/"
                        "e9e8aa3af6dfdddea4379ae524d4f649",
            "evidence_tier": "题录库（国家数字标准馆 ndls.org.cn，中国标准化研究院主办）",
            "scope_note": "题录页范围原文含「机器人结构、机器人电缆配置」，作用域是管线包"
                          "（dress pack）与机器人本体的走线接口，对应本站 cables/connectors "
                          "类目。发布单位为贸易中心联合会而非机器人技术归口机构，"
                          "权威层级弱于同批 CAMETA 两条，据此标注但不进判据。",
        },
        {
            # 【20260812 新增·作用域内现行团标】具身智能机器人连接器/线束组件技术要求。
            # 多源交叉核验：ttbz 发布机构官网（standardDetail 白名单）、spc 中国标准在线
            # 服务网、ndls 国家标准馆、牵头单位盛格纳新闻稿均记为 T/AIIA 021—2026 现行、
            # 公布/实施 2026-04-01、归口深圳市人工智能产业协会。
            # 注：cssn.net.cn 某镜像页 AI 提取误读为「T/AIIA 002-2026」，与 4 个权威源
            # 冲突，以 ttbz（发布机构官网）为准 → 标准号为 021-2026，非 002。
            "id": "T/AIIA 021-2026",
            "name": "具身智能机器人用线束组件技术要求",
            "type": "团体标准",
            "status": "现行",
            "issued_at": "2026-03-31",
            "effective_at": "2026-04-01",
            "announced_at": "2026-04-01",
            "issuer": "深圳市人工智能产业协会",
            "evidence": "https://www.ttbz.org.cn/standardDetail/"
                        "qzn63aj7q6ng2jvy3qxldbfpcf5fknw.html",
            "evidence_tier": "题录库（全国团体标准信息平台 ttbz.org.cn，发布机构官网公示）",
            "scope_note": "连接器/线束组件技术要求，属零部件接口域（ROBOT_RE∩IFACE_RE 作用"
                          "域内，可入库追踪）；系「技术要求/试验方法」类规范，非尺寸级互换"
                          "标准，不进机械/电气兼容判据。结束连续约 37 轮标准域零新增。",
        },
    ],
    # ----------------------------------------------------------------------
    # 观察名单：TC591/SC5 在研的零部件/接口类国标计划。
    # 只记计划号 + 名称 + 下达日期 + 状态（均取自国家标准计划库归口清单页），
    # **不推断内容、不预测发布时间** —— 在研标准内容随时可变，任何基于草案
    # 内容的判据都是在给自己埋一次"事后发现口径变了"。
    # ----------------------------------------------------------------------
    "registry_watchlist": {
        "note": "在研计划，仅追踪立项事实；内容未定，一律不进判据",
        "evidence": "https://std.samr.gov.cn/search/orgDetailView?tcCode=TC591SC5",
        "evidence_tier": "国家标准计划库（TC591/SC5 归口清单）",
        "plans": [
            {"id": "20262884-T-604", "name": "人形机器人零部件 关节电机驱动器技术规范",
             "plan_released_at": "2026-05-22", "status": "正在起草"},
            {"id": "20262885-T-604", "name": "人形机器人零部件 减速装置技术规范",
             "plan_released_at": "2026-05-22", "status": "正在起草"},
            {"id": "20262887-T-604", "name": "人形机器人零部件 一体化关节电磁兼容通用技术规范",
             "plan_released_at": "2026-05-22", "status": "正在起草"},
            {"id": "20262890-T-604", "name": "人形机器人可靠性试验方法 第2部分：直线关节",
             "plan_released_at": "2026-05-22", "status": "正在起草"},
            {"id": "20262892-T-604", "name": "人形机器人可靠性试验方法 第3部分：旋转关节",
             "plan_released_at": "2026-05-22", "status": "正在起草"},
            {"id": "20263166-T-604", "name": "人形机器人零部件 关节力矩传感器技术规范",
             "plan_released_at": "2026-06-27", "status": "正在起草"},
            {"id": "20261647-T-604", "name": "人形机器人短距交互通信技术规范",
             "plan_released_at": "2026-03-31", "status": "正在起草"},
        ],
    },
    # 【20260810-12 新增】枚举召回的**淘汰留痕**。
    # 只记"收了什么"而不记"看见了什么却没收"，等于把筛选过程藏起来——
    # 下一轮换个人（或换个我）会把同样几条重新捞一遍、重新争论一遍。
    # 这里写清每条为什么不进登记表，让触发器的判断本身可被复核、可被推翻。
    "enumeration_audit": {
        "note": "由 scripts/enumerate_standards.py 整表枚举命中两因子、但经人工作用域"
                "复核后未进登记表的条目。淘汰理由必须具体到「域不对」而非「感觉不相关」。",
        "source": "std.samr.gov.cn 国家标准题录检索（GB/GB-T 全表分页枚举）"
                  " + ndls.org.cn 国家数字标准馆（团体标准 ICS 整表枚举）",
        "last_run": "2026-08-11",
        "scan_width": "国标 434 条题录（7 个检索词去重后）；两因子命中 17 条。"
                      "此前记录的 164 条是分页 bug 下的虚数，见 scripts/enumerate_standards.py "
                      "的 pageNo 自证闸注释。"
                      "团标 799 条（ICS 25.040.30 收 436/436 穷举自证通过；"
                      "ICS 25.040.01 收 363/365，缺 2 条如实记账不冒充全表）；"
                      "两因子命中 9 条，入库 4 条、淘汰 4 条、废止 1 条。",
        "rejected": [
            {"id": "GB/T 33267-2016", "name": "机器人仿真开发环境接口",
             "reason": "接口对象是仿真软件开发环境，不是物理零部件的机械/电气/通信接口"},
            {"id": "GB/T 40807-2021", "name": "微系统用生产设备 末端执行器与处理器的接口",
             "reason": "半导体/微系统生产设备域，末端执行器所指对象与本站机器人零部件不同"},
            {"id": "GB/T 47446-2026", "name": "空间站机械臂操作对象接口要求",
             "reason": "航天专用域（2026-11-01 实施）；虽是机械臂接口标准，但操作对象接口"
                       "为空间站专属工况，不适用于通用零部件互换判定。已列入下轮观察",
             "watch": True},
            {"id": "GB/T 17487-1998", "name": "四油口和五油口液压伺服阀 安装面",
             "reason": "液压伺服阀域；本站实体以电驱动为主，液压安装面无对应实体"},
            # 以下 3 条来自 20260810-19 翻页修复后新增的 270 条扫描面。
            {"id": "GB/T 21412.8-2010",
             "name": "石油天然气工业 水下生产系统的设计和操作 第8部分：水下生产系统的水下机器人（ROV）接口",
             "reason": "海洋油气水下生产系统域；这里的「机器人」指水下 ROV 作业装备，"
                       "接口对象是水下采油树等生产设施，与本站陆上机器人零部件互换无交集。"
                       "属两因子（领域词『机器人』+ 层面词『接口』）的典型误命中"},
            {"id": "GB/T 43047-2023", "name": "物流机器人 控制系统接口技术规范",
             "reason": "接口对象是整机控制系统与上位调度系统之间的软件/数据接口，"
                       "不是零部件的机械/电气接口 —— 与已排除的 GB/T 33267-2016"
                       "（仿真开发环境接口）同型"},
            {"id": "GB/T 47864-2026", "name": "工业移动机器人调度系统底层数据接口要求",
             "reason": "同 GB/T 43047：系统级数据接口，非零部件接口。"
                       "2026-07-02 发布、2027-02-01 实施，列入下轮观察",
             "watch": True},
            # 以下 4 条来自 20260811-04 团标域首次整表枚举（ndls.org.cn，799 条）。
            {"id": "T/SAIAS 043-2025", "name": "人形机器人操作运动控制接口规范",
             "reason": "领域词命中最强（人形机器人），但层面是**运动控制的软件/指令接口**，"
                       "与已排除的 GB/T 33267（仿真环境接口）、GB/T 43047（调度系统接口）同型："
                       "接口两端都是软件，不落在零部件的机械/电气/物理连接层。"
                       "列入下轮观察 —— 若后续版本规定关节侧指令报文与电气时序，则应重判",
             "watch": True},
            {"id": "T/SSITS 203-2020", "name": "工业应用移动机器人 数据通信接口规范",
             "reason": "AMR 整机与上位系统之间的数据通信接口，接口对象是整机不是零部件；"
                       "与 GB/T 47864（调度系统底层数据接口）同型"},
            {"id": "T/CEEIA 797-2024", "name": "建筑机器人通信协议导则",
             "reason": "领域是建筑施工机器人整机域，且文件性质为「导则」（指导性、非判据性）；"
                       "两因子里领域词是靠『机器人』泛匹配进来的，属误命中"},
            {"id": "T/CIE 043-2017", "name": "光纤芯交换机器人通信协议格式规范",
             "reason": "对象是通信机房的光纤配线自动交换设备，此处『机器人』指配线机械手，"
                       "与本站机器人零部件无实体交集；两因子词面误命中的第二型"},
        ],
    },
    "field_semantics": {
        "assessed": "该实体是否声明了足以推导符合度的接口/协议数据",
        "bus_class": "归一化总线类别，源自实体已声明的 protocol/interface/bus/communication",
        "ros2": "是否声明 ROS 2 支持；null 表示未声明",
        "interop_stack_20262893": "对最小互操作技术栈的匹配度 full/partial/none/unknown",
        "caee060_relevant": "是否落在 T/CAEE 060-2026 的互操作规范作用域内",
        "interop_posture": "厂商互操作立场 closed/semi_open/multi_protocol/unknown",
        "iso22166_relevant": "是否落在 ISO 22166 服务机器人模块化标准的适用域内（基于类目保守标注，非符合性结论）",
    },
    "disclaimer": (
        "本字段由实体已声明的接口/协议数据推导得出，属符合度线索，"
        "不构成第三方认证或合规结论；未声明数据的实体一律标记 assessed=false 与 unknown，未作任何推测。"
    ),
}


def bus_class_of(entity):
    """从已声明字段推导总线类别；无声明返回 None。"""
    parts = []
    for key in ('protocol', 'interface', 'bus', 'communication'):
        val = entity.get(key)
        if val:
            parts.append(str(val))
    # compatibility 列表里常含 ROS2 等，不用于总线判定，避免误判
    if not parts:
        return None
    blob = ' '.join(parts).lower()
    for label, pattern in BUS_RULES:
        if re.search(pattern, blob):
            return label
    return 'other'


def ros2_of(entity):
    """是否声明 ROS 2；未声明返回 None。"""
    if entity.get('ros_support') is True:
        return True
    if entity.get('ros_support') is False:
        return False
    blob = ' '.join(
        str(entity.get(k, '')) for k in ('protocol', 'interface', 'description')
    )
    compat = entity.get('compatibility')
    if isinstance(compat, list):
        blob += ' ' + ' '.join(str(c) for c in compat)
    if re.search(r'ros\s*-?\s*2|ros2', blob, re.I):
        return True
    return None


def posture_of(entity):
    maker = str(entity.get('manufacturer') or '').lower()
    if not maker:
        return 'unknown'
    for key, val in INTEROP_POSTURE.items():
        if key in maker:
            return val
    return 'unknown'


def stack_match(bus, ros2):
    """对 20262893-T-604 最小互操作技术栈的匹配度。

    full    = 以太网类总线 且 声明 ROS 2
    partial = 二者其一
    none    = 有声明数据但两项都不满足
    unknown = 无声明数据
    """
    if bus is None and ros2 is None:
        return 'unknown'
    eth = bus in ETHERNET_CLASS
    has_ros2 = ros2 is True
    if eth and has_ros2:
        return 'full'
    if eth or has_ros2:
        return 'partial'
    return 'none'


def build(entity):
    bus = bus_class_of(entity)
    ros2 = ros2_of(entity)
    assessed = bus is not None or ros2 is not None
    return {
        'assessed': assessed,
        'bus_class': bus or 'unknown',
        'ros2': ros2,
        'interop_stack_20262893': stack_match(bus, ros2),
        'caee060_relevant': entity.get('category') in CAEE060_CATEGORIES,
        'interop_posture': posture_of(entity),
        'iso22166_relevant': entity.get('category') in ISO22166_RELEVANT_CATEGORIES,
    }


def rebuild(doc):
    """在内存里重算 standard_conformance 与覆盖率块，返回 (changed, coverage)。

    不碰磁盘 —— 写入与 --check 共用同一份算法，杜绝「闸门说的」与「生成器做的」分叉。
    """
    entities = doc.get('entities') or doc.get('data') or []
    changed = 0
    for e in entities:
        sc = build(e)
        if e.get('standard_conformance') != sc:
            e['standard_conformance'] = sc
            changed += 1

    # ---- 汇总覆盖率 ----
    total = len(entities)
    assessed = sum(1 for e in entities if e['standard_conformance']['assessed'])
    stack = {}
    buses = {}
    postures = {}
    for e in entities:
        sc = e['standard_conformance']
        stack[sc['interop_stack_20262893']] = stack.get(sc['interop_stack_20262893'], 0) + 1
        buses[sc['bus_class']] = buses.get(sc['bus_class'], 0) + 1
        postures[sc['interop_posture']] = postures.get(sc['interop_posture'], 0) + 1

    coverage = {
        'total': total,
        'assessed': assessed,
        'assessed_pct': round(assessed / total * 100, 2) if total else 0,
        'caee060_relevant': sum(
            1 for e in entities if e['standard_conformance']['caee060_relevant']
        ),
        'iso22166_relevant': sum(
            1 for e in entities if e['standard_conformance']['iso22166_relevant']
        ),
        'interop_stack_distribution': dict(sorted(stack.items(), key=lambda x: -x[1])),
        'bus_class_distribution': dict(sorted(buses.items(), key=lambda x: -x[1])),
        'interop_posture_distribution': dict(sorted(postures.items(), key=lambda x: -x[1])),
        'computed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'gap_note': (
            f'仅 {assessed}/{total} 条实体声明了接口/协议数据，'
            '其余无法评估互操作符合度——这是兼容性数据集的首要补全方向。'
        ),
    }
    return changed, coverage


def main():
    with open(ENTITIES_PATH, 'r', encoding='utf-8') as f:
        doc = json.load(f)

    if '--check' in sys.argv:
        # 只试算不落盘：在深拷贝上重算，比对除 computed_at 外的全部字段。
        _, want = rebuild(copy.deepcopy(doc))
        cur = (doc.get('meta') or {}).get('standard_conformance_coverage') or {}
        strip = lambda d: {k: v for k, v in d.items() if k != 'computed_at'}
        diff = {k: (cur.get(k), want[k]) for k in want if k != 'computed_at'
                and cur.get(k) != want[k]}
        if diff:
            print('❌ standard_conformance_coverage 与现算不一致（跑 '
                  'python scripts/govern_standard_conformance.py 收敛）')
            for k, (a, b) in diff.items():
                if isinstance(a, dict) and isinstance(b, dict):
                    inner = {kk: (a.get(kk), b.get(kk)) for kk in set(a) | set(b)
                             if a.get(kk) != b.get(kk)}
                    print(f'   - {k}: {inner}')
                else:
                    print(f'   - {k}: 落盘 {a} → 现算 {b}')
            return 1
        print(f'✅ standard_conformance_coverage 一致'
              f'（total={want["total"]} / assessed={want["assessed"]}）')
        return 0

    changed, coverage = rebuild(doc)
    meta = doc.setdefault('meta', {})
    meta['standard_conformance_spec'] = STANDARDS_SPEC
    meta['standard_conformance_coverage'] = coverage

    with open(ENTITIES_PATH, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f'✅ standard_conformance 已写入：变更 {changed} 条 / 共 {coverage["total"]} 条')
    print(f'   可评估：{coverage["assessed"]} ({coverage["assessed_pct"]}%)')
    print(f'   互操作栈匹配：{coverage["interop_stack_distribution"]}')
    print(f'   总线分布 top: {list(coverage["bus_class_distribution"].items())[:8]}')
    print(f'   厂商立场：{coverage["interop_posture_distribution"]}')
    print('⚠️  请接着运行 scripts/normalize_categories.py 重生成派生文件')
    return 0


if __name__ == '__main__':
    main()
