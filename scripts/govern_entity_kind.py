# -*- coding: utf-8 -*-
"""Schema 治理：区分「零部件实体」与「市场情报条目」，为全部实体补 entity_kind。

═══════════════════════════════════════════════════════════════════════════
【20260806-00 · 发现经过 —— 是新通道自己把它照出来的】

本轮上线 hosted MCP 端点后跑第一次 recommend_for_application(humanoid)，
platforms 品类返回了 `ACT-patsnap-actuator`「PatSnap Humanoid Actuator Analysis」。
那不是一个机器人平台，是一份**专利分析报告**。

顺藤摸瓜查出 3 条同类：
  ACT-roland-berger-hd-actuator  罗兰贝格（管理咨询公司，不造执行器）的执行器趋势条目
  act-patsnap-analysis           Humanoid Actuator Patent Landscape（专利地图）
  ACT-patsnap-actuator           PatSnap Humanoid Actuator Analysis（市场报告）

三条全部标着 source_tier=A / verified=True / quarantine=False —— 
也就是说**我们自己的质量标记认为它们完全没问题**。
这是比"数据有错"更深一层的问题：错的不是数值，是**类别**。
现有 quarantine 机制只能表达"这条数据可疑"，无法表达"这条数据没错但它根本不是零件"。

为什么必须现在修：/mcp 是免鉴权零摩擦入口，AI Agent 第一次接触我们很可能就是
"给人形机器人推荐几个执行器"。如果头几条里混进咨询公司的报告，
对方对整个 688 条数据集的信任会一次性归零 —— 而它不会给第二次机会。

处置原则（不删、不藏、不改总数）：
  - 三条**保留**在库内（专利地图与市场报告本身有参考价值，只是不该当零件卖）
  - 新增 entity_kind 字段显式区分，理由写进 kind_basis
  - meta 里透出 component_count / market_intelligence_count 两个数
  - total_entities 仍为 688（它们确实在库内，改小反而是另一种不诚实）
  - 对外的零件检索/推荐默认只返回 component

⚠️ 不变式（regression.py L1.16 守护）：
   - 每条实体都必须有 entity_kind
   - market_intelligence 条目必须带 kind_basis
   - component_count + market_intelligence_count == total_entities
═══════════════════════════════════════════════════════════════════════════
"""
import json, os, io, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIMARY = os.path.join(ROOT, "api", "entities.json")

# 判定为「非零件」的信号。保守起见只认这几个明确的值，
# 宁可漏判也不误伤真实零件（误伤会让真零件从检索里消失，比混入报告更糟）。
NONPART_TYPES = {"market_report", "patent_analysis"}
NONPART_STATUS = {"market_trend"}

# ── 第三档 organization（20260809-03 补）───────────────────────────────────
# 原来只有 component / market_intelligence 两档，于是「Figure AI」「特斯拉」
# 「波士顿动力」这类**企业主体条目**（type=人形机器人公司）只能落进 component。
# 后果不是分类难看，是三处对外失真：
#   1. /mcp 实况文案称「N 条为可选型零部件」—— 其中 9 条是公司；
#   2. 接入区块/Schema.org 称「N 个零部件实体」—— 同上；
#   3. 兼容性判定接受公司当操作数，输出「Figure AI 未声明通信协议，无法判定」
#      —— 把**类型错误**渲染成**数据缺口**，暗示"这家公司只是没填参数"。
# 判据取 type 结尾（公司/集团/Inc/Corp/…）：型号名不会以"公司"结尾，无歧义。
_ORG_TYPE_TAIL = re.compile(
    r"(公司|集团|研究院|实验室|inc\.?|corp\.?|corporation|company|gmbh|ltd\.?)$", re.I)

# ── 第四、五档 specification / software（20260809-05 补）──────────────────
# L1.65 只修了"公司冒充零件"这 9 条，同一病灶更大的两片没动：
#   · protocols(64) + interfaces(37) = 101 条 —— EtherCAT、CANopen、USB 3.0、
#     MIPI CSI-2、PCIe…… 这些是**规范本身**，不是实现规范的某个零件。
#     实测旧引擎对 (EtherCAT, DYNAMIXEL XM540) 的回答是
#     「EtherCAT 未声明通信协议，无法判定」—— EtherCAT 就是通信协议，
#     它不是"未声明"，它是被声明的那个东西。这句话比不回答更坏。
#   · llms(42) + robot_ai_models(44) = 86 条 —— GPT-4o、RT-2、π0、LeRobot……
#     软件模型没有法兰、没有电压，同样被问出「GPT-4o 未声明机械接口」。
# 合计 187 条，占旧口径「694 条零部件」的 **27%**。
# 判据取「类目 + 物理证据否决」：类目信号足够强（这两组类目现有 187 条无一条
# 同时具备厂商与物理量），同时保留否决位 —— 将来若有实物连接器落进 interfaces
# （带厂商且带重量/尺寸/电压/价格），仍按 component 处理，避免"往这个类目里
# 放真零件就被静默吞掉"。
SPEC_CATEGORIES = {"protocols", "interfaces"}
SOFTWARE_CATEGORIES = {"llms", "robot_ai_models"}
_PHYSICAL_FIELDS = ("weight", "dimensions", "voltage", "torque",
                    "price_range", "current", "package", "mass")


def _has_physical_evidence(e):
    """有厂商 + 至少一个物理量 → 视为实物，规范类判据让位。"""
    return bool(e.get("manufacturer")) and any(e.get(k) for k in _PHYSICAL_FIELDS)


# 只有 component 才是"可判定接口的实物零部件"。其余种类一律不进选型/兼容判定。
NON_COMPONENT_KINDS = ("market_intelligence", "organization", "specification", "software")


def classify(e):
    """返回 (entity_kind, kind_basis)。"""
    t = str(e.get("type", "")).strip().lower()
    s = str(e.get("status", "")).strip().lower()
    cat = e.get("category")
    if t in NONPART_TYPES:
        return "market_intelligence", f"type={t}（研究/报告类条目，非可采购零部件）"
    if s in NONPART_STATUS:
        return "market_intelligence", f"status={s}（市场趋势条目，非具体在售型号）"
    # 条目自己的质量标记已写明"根本不是实体"（行业热词/趋势片段，如「AI芯片」
    # 「人形机器人·销量增长133%」）。既然自陈非实体，就不该再被归成软件或零件。
    if e.get("data_quality") == "non_entity":
        return "market_intelligence", "data_quality=non_entity（行业热词/趋势片段，条目自陈非实体）"
    if t and _ORG_TYPE_TAIL.search(t):
        return "organization", f"type={t}（企业/机构主体，不是实物零部件，无接口可判定）"
    if cat in SPEC_CATEGORIES and not _has_physical_evidence(e):
        return "specification", (f"category={cat}（接口/协议规范本身，"
                                 "非实现它的零件；无厂商+物理量证据）")
    if cat in SOFTWARE_CATEGORIES:
        return "software", f"category={cat}（AI 模型/软件条目，无机械与电气接口）"
    return "component", None


def recompute_meta(d):
    ents = d["entities"]
    comp = sum(1 for e in ents if e.get("entity_kind") == "component")
    mi = sum(1 for e in ents if e.get("entity_kind") == "market_intelligence")
    org = sum(1 for e in ents if e.get("entity_kind") == "organization")
    spec = sum(1 for e in ents if e.get("entity_kind") == "specification")
    soft = sum(1 for e in ents if e.get("entity_kind") == "software")
    d["meta"]["entity_kinds"] = {
        "component": comp,
        "market_intelligence": mi,
        "organization": org,
        "specification": spec,
        "software": soft,
        "definition": {
            "component": "可采购/可选型的实物零部件",
            "market_intelligence": "市场报告、专利地图、趋势条目 —— 保留供参考，但不作为选型候选返回",
            "organization": "企业/机构主体条目（如 Figure AI、波士顿动力）—— 保留供检索，"
                            "但没有物理接口，不进选型候选、不作为兼容性判定操作数",
            "specification": "接口/协议规范本身（EtherCAT、USB 3.0、MIPI CSI-2…）—— 可被检索、"
                             "可作为筛选条件，但规范之间不存在装配关系，不作为兼容性判定操作数",
            "software": "AI 模型 / 软件框架条目（GPT-4o、RT-2、LeRobot…）—— 无机械与电气接口，"
                        "不进选型候选、不作为兼容性判定操作数",
        },
        "note": "total_entities 仍为全库条数；零件检索、推荐与兼容性判定只认 component",
    }
    d["meta"]["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    return comp, mi, org, spec, soft


def main():
    with io.open(PRIMARY, encoding="utf-8") as f:
        d = json.load(f)

    patched = {}
    changed = 0
    flagged = []
    for e in d["entities"]:
        kind, basis = classify(e)
        if e.get("entity_kind") != kind:
            changed += 1
        e["entity_kind"] = kind
        if basis:
            e["kind_basis"] = basis
            flagged.append((e["id"], e.get("category"), e.get("name", "")[:46], basis))
        else:
            e.pop("kind_basis", None)
        patched[e["id"]] = {"entity_kind": kind}
        if basis:
            patched[e["id"]]["kind_basis"] = basis

    comp, mi, org, spec, soft = recompute_meta(d)
    with io.open(PRIMARY, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")   # 与其它写入器统一，避免 L1.66 的"以换行结尾"检查被这里破坏

    print("entities.json changed=%d total=%d component=%d market_intelligence=%d "
          "organization=%d specification=%d software=%d"
          % (changed, len(d["entities"]), comp, mi, org, spec, soft))
    print("\n标记为非零件条目（保留在库，但不进零件推荐/兼容判定）:")
    for i, c, n, b in flagged:
        print(f"  {i}  [{c}]  {n}\n      理由: {b}")

    # 同步其它 api/*.json 中的同 id 记录（与 govern_tier_c.py 同一套做法）
    api_dir = os.path.join(ROOT, "api")
    total_hits = 0
    for fn in sorted(os.listdir(api_dir)):
        if not fn.endswith(".json") or fn == "entities.json":
            continue
        p = os.path.join(api_dir, fn)
        try:
            with io.open(p, encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue
        hits = [0]

        def walk(o):
            if isinstance(o, dict):
                i = o.get("id")
                if isinstance(i, str) and i in patched and ("name" in o or "category" in o):
                    for k, v in patched[i].items():
                        o[k] = v
                    if patched[i]["entity_kind"] == "component":
                        o.pop("kind_basis", None)
                    hits[0] += 1
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(obj)
        if hits[0]:
            with io.open(p, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            total_hits += hits[0]
            print(f"  同步 {fn}: {hits[0]} 条")
    print(f"\n派生文件共同步 {total_hits} 条记录")


if __name__ == "__main__":
    main()
