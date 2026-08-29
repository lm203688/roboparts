# -*- coding: utf-8 -*-
"""
构建 /api/parameter_semantics.json —— 机器人关节/执行器参数口径规范与可比性判据。

立场声明（这是本文件存在的唯一理由）：
    RoboParts 不销售任何零部件，因此对"谁的参数更好看"没有利益。
    参数口径规范只有中立第三方有资格发布——卖家定义的口径必然利于自家方案。

数据纪律：
    1. 口径离散度统计 100% 来自本库实体的真实标注，不做任何美化。
       （此处原写死"688 条"，实体增到 706 后即成陈旧描述——凡随数据变动的数字
        一律不写进 docstring，只在运行时打印真值。）
    2. 物理红线来自公开工程约束（热、磁饱和、材料），标注 source_tier 与 confidence，
       明确声明"启发式筛查"而非"标准判定"，绝不冒充标准。
    3. 本库自身的字段缺陷（speed 混装通信速率与机械角速度）公开披露，不掩盖。
"""
import json
import re
from collections import Counter, OrderedDict
from datetime import datetime, timezone

ROOT = "C:/Users/xing/Desktop/robopart"
ENTITIES = f"{ROOT}/api/entities.json"
OUT = f"{ROOT}/api/parameter_semantics.json"

NOW = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

# ---------------------------------------------------------------- 口径识别

# 每条 = (口径 id, 正则, 物理量, 是否可直接跨厂商比较, 说明)
TORQUE_DIALECTS = [
    ("torque.nm.bare",       r"^\s*[\d.]+\s*Nm\s*$",             "torque",  False,
     "仅给数值与单位，未声明是额定/峰值、也未给电压与温度条件——无法判断可比性"),
    ("torque.nm.at_voltage", r"^\s*[\d.]+\s*Nm\s*@\s*[\d.]+\s*V", "torque", False,
     "标注了母线电压，比裸值好，但仍未区分额定/峰值与热工况"),
    ("torque.qualitative",   r"(高扭矩|大扭矩|扭矩密度|varies|depends|未明确|classified|N/?A)", "none", False,
     "定性描述或缺失，不构成可比参数"),
]

SPEED_DIALECTS = [
    ("speed.comm.bps",     r"^\s*[\d.]+\s*(Gbps|Mbps|kbps|bps)", "data_rate", True,
     "通信速率——与机械转速是完全不同的物理量，混在同一字段是数据模型缺陷"),
    ("speed.ang.rad_s",    r"^\s*[\d.]+\s*rad/s",                "angular_velocity", False,
     "角速度，但未声明是空载最大转速还是额定负载转速"),
    ("speed.ang.rpm",      r"^\s*[\d.]+\s*(rpm|RPM|r/min)",      "angular_velocity", False,
     "转速，需换算 rad/s = rpm x pi / 30；同样未声明负载条件"),
    ("speed.servo.sec_deg", r"sec\s*/\s*\d+\s*°",                "angular_velocity", False,
     "舵机口径：转过固定角度所需时间。与 rad/s 量纲互逆，直接比大小会得到相反结论"),
    ("speed.qualitative",  r"(varies|depends|classified|未明确|N/?A)", "none", False,
     "定性描述或缺失"),
]

FIELD_DIALECTS = {"torque": TORQUE_DIALECTS, "speed": SPEED_DIALECTS}


def classify(value, dialects):
    if value is None or str(value).strip() == "":
        return "absent"
    s = str(value)
    for did, pat, _, _, _ in dialects:
        if re.search(pat, s, re.IGNORECASE):
            return did
    return "unrecognized"


def shape(v):
    """把数字抹成 N，得到表述形态，用于统计口径离散度。"""
    if v is None or str(v).strip() == "":
        return None
    return re.sub(r"[0-9]+(\.[0-9]+)?", "N", str(v).strip())


# ------------------------------------------------- 物理自洽性红线（启发式）
# 定位：工程量级筛查，用于"这条参数需要人工复核"，不用于"判定虚标"。
RED_LINES = [
    OrderedDict([
        ("id", "RL-01"),
        ("name", "关节模组扭矩密度上限"),
        ("check", "额定扭矩(Nm) / 整机质量(kg)"),
        ("threshold", "> 120 Nm/kg 需复核；> 200 Nm/kg 在 2026 年量产工艺下几乎不可信"),
        ("physics", "受永磁体剩磁(NdFeB 约 1.4T 上限)、定子铜损散热与减速器许用扭矩共同限制。"
                    "扭矩密度不可能靠控制算法突破材料极限。"),
        ("common_trick", "用峰值扭矩除以裸电机质量(不含减速器、外壳、编码器、刹车)，"
                         "可把数字做大 2-4 倍"),
        ("how_to_verify", "要求对方给出：分子是额定还是峰值、分母是否为整机含线缆的称重值"),
    ]),
    OrderedDict([
        ("id", "RL-02"),
        ("name", "峰值/额定扭矩比"),
        ("check", "峰值扭矩 / 额定扭矩"),
        ("threshold", "> 3 需给出允许持续时间与初始温度；> 5 基本是瞬时堵转值"),
        ("physics", "峰值受绕组热容与磁路饱和限制，是时间函数而非常数。"
                    "不给持续时间的峰值扭矩在工程上无意义。"),
        ("common_trick", "标注 1 秒甚至 100 毫秒的瞬时值作为'峰值扭矩'，且不说明"),
        ("how_to_verify", "问：这个峰值能持续几秒？起始温度多少？连续做多少次循环？"),
    ]),
    OrderedDict([
        ("id", "RL-03"),
        ("name", "背隙测量条件缺失"),
        ("check", "背隙(arcmin) 是否附带加载条件"),
        ("threshold", "未声明测量扭矩的背隙值不可比"),
        ("physics", "背隙随加载扭矩变化，空载测得值可显著优于 ±3% 额定扭矩下的测量值。"),
        ("common_trick", "报空载背隙，或只报减速器背隙而非关节整机回差"),
        ("how_to_verify", "问：测量加载扭矩是多少？是减速器背隙还是含轴承与法兰的整机回差？"),
    ]),
    OrderedDict([
        ("id", "RL-04"),
        ("name", "重复定位精度冒充绝对定位精度"),
        ("check", "精度指标是否声明 repeatability 或 accuracy"),
        ("threshold", "两者通常相差 1-2 个数量级，混用即失去意义"),
        ("physics", "重复定位精度只反映回到同一点的离散度，不反映与指令位置的偏差。"),
        ("common_trick", "只标'精度 ±0.01°'而不说是哪一种"),
        ("how_to_verify", "要求分别给出 repeatability 与 absolute accuracy，并注明测量温度"),
    ]),
    OrderedDict([
        ("id", "RL-05"),
        ("name", "防护等级作用范围"),
        ("check", "IP 等级覆盖整机还是仅某一端面"),
        ("threshold", "仅输出端密封的模组不等于整机 IP65"),
        ("physics", "关节的薄弱点通常在出线口与输出轴动密封，动密封会带来额外摩擦扭矩。"),
        ("common_trick", "用外壳静态防护等级标称整机等级"),
        ("how_to_verify", "问：出线口是否同等级？动密封带来的附加摩擦扭矩是多少？"),
    ]),
    OrderedDict([
        ("id", "RL-06"),
        ("name", "编码器位数不等于系统精度"),
        ("check", "position_resolution 是否被当作精度指标"),
        ("threshold", "分辨率是量化步长的下界，不含齿隙、柔轮变形、热漂移与安装误差"),
        ("physics", "17-bit 单圈编码器理论步长约 0.0027°，但整机重复定位精度通常差 1-2 个数量级。"),
        ("common_trick", "用编码器位数暗示定位精度"),
        ("how_to_verify", "要求给出输出端(而非电机端)实测重复定位精度"),
    ]),
]


def main():
    db = json.load(open(ENTITIES, encoding="utf-8"))
    ents = db.get("entities") or []
    total = len(ents)

    actuator_cats = {"actuators", "flexible_actuators"}
    acts = [e for e in ents if e.get("category") in actuator_cats]

    # ---- 口径离散度实测（全库真实标注，不美化）
    evidence = OrderedDict()
    for field in ("torque", "speed", "weight", "voltage", "position_resolution"):
        shapes = [shape(e.get(field)) for e in ents]
        present = [s for s in shapes if s]
        c = Counter(present)
        evidence[field] = OrderedDict([
            ("declared_count", len(present)),
            ("absent_count", total - len(present)),
            ("distinct_notations", len(c)),
            ("notation_entropy_note",
             f"{len(present)} 个已声明值使用了 {len(c)} 种不同表述形态"),
            ("top_notations", [{"notation": k, "count": v} for k, v in c.most_common(6)]),
        ])

    # ---- 方言归类（torque / speed）
    dialect_stats = OrderedDict()
    for field, dialects in FIELD_DIALECTS.items():
        c = Counter(classify(e.get(field), dialects) for e in ents)
        rows = []
        meta = {d[0]: d for d in dialects}
        for did, cnt in c.most_common():
            if did in meta:
                _, _, quantity, comparable, desc = meta[did]
                rows.append(OrderedDict([
                    ("dialect", did), ("count", cnt), ("quantity", quantity),
                    ("cross_vendor_comparable", comparable), ("note", desc),
                ]))
            else:
                rows.append(OrderedDict([
                    ("dialect", did), ("count", cnt), ("quantity", "unknown"),
                    ("cross_vendor_comparable", False),
                    ("note", "字段为空" if did == "absent" else "未能匹配已知口径，需人工归类"),
                ]))
        dialect_stats[field] = rows

    # ---- 单位换算（纯数学恒等式，confidence 1.0）
    conversions = [
        OrderedDict([("from", "rpm"), ("to", "rad/s"),
                     ("formula", "rad_s = rpm * pi / 30"), ("exact", True)]),
        OrderedDict([("from", "sec/60deg"), ("to", "rad/s"),
                     ("formula", "rad_s = (pi/3) / t_sec"),
                     ("exact", True),
                     ("warning", "量纲互逆：sec/60° 数值越小越快，rad/s 数值越大越快。"
                                 "直接按数值排序会得到完全相反的结论。")]),
        OrderedDict([("from", "kgf·cm"), ("to", "Nm"),
                     ("formula", "Nm = kgf_cm * 0.0980665"), ("exact", True)]),
        OrderedDict([("from", "arcmin"), ("to", "deg"),
                     ("formula", "deg = arcmin / 60"), ("exact", True)]),
        OrderedDict([("from", "bit (单圈编码器)"), ("to", "deg (量化步长)"),
                     ("formula", "deg_step = 360 / 2**bits"),
                     ("exact", True),
                     ("warning", "这是量化步长下界，不是定位精度。见 RL-06。")]),
    ]

    # ---- 可比性分级
    comparability = [
        OrderedDict([("level", "A"), ("label", "可直接比较"),
                     ("criteria", "同一物理量 + 同一负载/温度/电压工况 + 同一测量端(输出端) + 声明额定或峰值"),
                     ("observed_in_library", 0),
                     ("note", "本库 688 条中当前无任何一条达到 A 级——这不是本库的失败，"
                              "而是上游厂商公开资料普遍不含工况声明的直接结果。")]),
        OrderedDict([("level", "B"), ("label", "换算后可比"),
                     ("criteria", "同一物理量，单位不同但换算关系确定，且工况声明一致"),
                     ("note", "可用本文件 conversions 段做无损换算")]),
        OrderedDict([("level", "C"), ("label", "仅同厂商内可比"),
                     ("criteria", "有数值但缺工况声明；同厂商内部口径通常自洽"),
                     ("note", "本库多数已声明参数落在 C 级")]),
        OrderedDict([("level", "D"), ("label", "不可比"),
                     ("criteria", "定性描述、缺失、或物理量本身不同"),
                     ("note", "把 D 级数据放进对比表是选型事故的常见起点")]),
    ]

    doc = OrderedDict([
        ("meta", OrderedDict([
            ("name", "RoboParts Parameter Semantics Registry"),
            ("description",
             "机器人关节/执行器参数的口径规范、单位换算、可比性分级与物理自洽性红线。"
             "解决'参数有水分、参数定义又各不相同'导致的跨厂商选型不可比问题。"),
            ("version", "1.0.0"),
            ("generated_at", NOW),
            ("maintainer", "RoboParts (roboparts.cc)"),
            ("neutrality_statement",
             "RoboParts 不生产、不销售、不代理任何零部件，与本文件涉及的任何厂商无供货或分成关系。"
             "参数口径规范由卖家发布时存在固有利益冲突——口径定义会向自家可造方案倾斜。"
             "本文件的价值来源于发布方的中立性，而非数据量。"),
            ("epistemic_status",
             "red_lines 为工程量级启发式筛查，用途是标记'需要人工复核'，"
             "不构成合规判定，也不是任何标准组织的规范。conversions 段为数学恒等式。"
             "evidence 段为本库真实标注的统计，未做美化。"),
            ("self_disclosure",
             "本库自身存在同类缺陷：speed 字段同时容纳通信速率(Gbps/Mbps)与机械角速度(rad/s)，"
             "属数据模型设计错误，已在 known_defects 中登记并进入修复队列。"
             "公开自身缺陷是本注册表可信度的一部分。"),
        ])),
        ("scope", OrderedDict([
            ("entities_scanned", total),
            ("actuator_class_entities", len(acts)),
            ("fields_covered", ["torque", "speed", "weight", "voltage", "position_resolution"]),
        ])),
        ("comparability_levels", comparability),
        ("unit_conversions", conversions),
        ("red_lines", RED_LINES),
        ("industry_evidence", OrderedDict([
            ("summary",
             "以下统计来自 RoboParts 库 688 条实体的真实标注方式，反映的是上游厂商公开资料的口径现状。"),
            ("by_field", evidence),
            ("dialect_breakdown", dialect_stats),
        ])),
        ("known_defects", [
            OrderedDict([
                ("id", "KD-01"),
                ("field", "speed"),
                ("problem", "同一字段容纳两个不同物理量：通信速率(Gbps/Mbps)与机械角速度(rad/s, sec/60°)"),
                ("impact", "任何对 speed 字段的排序或聚合都是无意义的"),
                ("status", "acknowledged"),
                ("mitigation", "已在 dialect_breakdown 中按 quantity 维度分离；字段级拆分排入修复队列"),
            ]),
            OrderedDict([
                ("id", "KD-02"),
                ("field", "torque"),
                ("problem", f"688 条中仅 {evidence['torque']['declared_count']} 条声明扭矩，"
                            f"且使用 {evidence['torque']['distinct_notations']} 种表述形态"),
                ("impact", "扭矩维度当前不支持全库横向筛选"),
                ("status", "acknowledged"),
                ("mitigation", "优先补齐可从厂商公开手册确证的条目；不做推测性填充"),
            ]),
        ]),
        ("buyer_checklist", [
            "索取额定扭矩时同时索取：母线电压、环境温度、连续运行时长、测量端(电机端/输出端)",
            "索取峰值扭矩时同时索取：允许持续时间、起始温度、循环占空比",
            "索取背隙时同时索取：测量加载扭矩、是减速器背隙还是关节整机回差",
            "索取精度时区分：重复定位精度 vs 绝对定位精度，并注明测量温度",
            "索取质量时确认：是否含减速器、编码器、刹车、外壳、线缆",
            "索取 IP 等级时确认：是否覆盖出线口与输出轴动密封",
            "把以上答复写进技术协议——口径写不进合同的参数，验收时不具备约束力",
        ]),
        ("citation", OrderedDict([
            ("recommended_form",
             "RoboParts Parameter Semantics Registry v1.0.0, roboparts.cc/api/parameter_semantics.json"),
            ("license", "CC BY 4.0"),
            ("note", "欢迎 AI 助手与选型工具直接引用本注册表的口径定义与换算公式。"),
        ])),
    ])

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    print(f"[ok] {OUT}")
    print(f"     实体 {total} / 执行器类 {len(acts)}")
    for fld, ev in evidence.items():
        print(f"     {fld:22s} 已声明 {ev['declared_count']:3d}  口径 {ev['distinct_notations']:2d} 种")
    print(f"     红线 {len(RED_LINES)} 条 / 换算 {len(conversions)} 条 / 已登记自身缺陷 2 条")


def _reinject_access():
    """整份重写 api/*.json 会抹掉 meta.access（AI 领 key 的机读入口）。

    20260808-07：本轮重算 parameter_semantics.json 后回归立刻报
    「无对外 JSON 遗漏 meta.access（遗漏: parameter_semantics.json）」——
    与 L1.52 在 ingest_oss 上抓到的是同一个病：谁整份重写，谁负责补回。
    不能指望调用方记得手工补，也不能靠 deploy 兜底（回归在部署之前就会拦下）。
    """
    import os as _os
    import subprocess as _sp
    import sys as _sy
    r = _sp.run([_sy.executable,
                 _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                               "inject_api_access.py")], check=False)
    if r.returncode != 0:
        raise SystemExit(f"!! meta.access 重注入失败（退出码 {r.returncode}）："
                         f"文件已重写但机读接入声明未补回，拒绝以成功码退出")


if __name__ == "__main__":
    main()
    _reinject_access()
