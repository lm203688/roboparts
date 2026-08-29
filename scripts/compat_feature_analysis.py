#!/usr/bin/env python3
"""
兼容性特征重要性分析 (QuantFeature 方法论)

方法论来源: QuantFeature Engine — "统一特征引擎 → 逐特征测试预测力 → 剔除无效 → 组合评分"
适配 RoboParts: 对兼容性规则中的接口类型/类别/标准/协议等维度做特征重要性排序，
找出真正有判别力的兼容性维度，替代当前的硬编码 IF-P-THEN 规则。

输出: ops/feature-importance-report.json (特征排名+统计)
      ops/feature-importance-report.md  (可读报告)
"""

import json
import os
import sys
from collections import Counter, defaultdict
from math import log2

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR = os.path.join(WORKSPACE, "api")
OPS_DIR = os.path.join(WORKSPACE, "ops")

os.makedirs(OPS_DIR, exist_ok=True)


def load_json(rel_path):
    path = os.path.join(API_DIR, rel_path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_compatibility_rules():
    """加载兼容性规则，提取每对(from, to)的接口信息"""
    rules = []
    data = load_json("compatibility.json")
    for r in data.get("rules", []):
        rules.append(r)
    return rules


def load_entities_features():
    """加载所有实体，提取标准化特征"""
    data = load_json("entities.json")
    entities = {}
    for entry in data.get("entities", []):
        eid = entry.get("id")
        if not eid:
            continue
        # 提取兼容相关的核心特征
        feats = {
            "category": entry.get("category", "unknown"),
            "type": entry.get("type", "unknown"),
            "manufacturer": entry.get("manufacturer", "unknown"),
            "application": entry.get("application", "unknown"),
            "source_tier": entry.get("source_tier", "C"),
            "verified": entry.get("verified", False),
            "quarantine": entry.get("quarantine", True),
            "has_mechanical_interface": entry.get("mechanical_interface", {}).get("status") == "declared",
            "mount_type": entry.get("mechanical_interface", {}).get("mount_type", "unknown"),
            "flange_standard": entry.get("mechanical_interface", {}).get("standard", None),
            "bus_class": entry.get("standard_conformance", {}).get("bus_class", "unknown"),
            "interop_posture": entry.get("standard_conformance", {}).get("interop_posture", "unknown"),
            "has_torque": entry.get("torque") is not None and entry.get("torque") != "",
            "has_voltage": entry.get("voltage") is not None and entry.get("voltage") != "",
        }
        entities[eid] = feats
    return entities


def build_compat_pairs(rules, entities):
    """构建兼容对特征矩阵"""
    pairs = []
    for rule in rules:
        frm = rule.get("from", "")
        to = rule.get("to", "")
        interface = rule.get("interface", "unknown")
        rel_type = rule.get("type", "unknown")

        feat_frm = entities.get(frm, {})
        feat_to = entities.get(to, {})

        if not feat_frm or not feat_to:
            continue

        pair = {
            "from": frm,
            "to": to,
            "interface": interface,
            "rel_type": rel_type,
            "from_category": feat_frm.get("category"),
            "to_category": feat_to.get("category"),
            "from_type": feat_frm.get("type"),
            "to_type": feat_to.get("type"),
            "from_manufacturer": feat_frm.get("manufacturer"),
            "to_manufacturer": feat_to.get("manufacturer"),
            "from_category_eq_to": feat_frm.get("category") == feat_to.get("category"),
            "from_type_eq_to": feat_frm.get("type") == feat_to.get("type"),
            "from_has_mechanical": feat_frm.get("has_mechanical_interface"),
            "to_has_mechanical": feat_to.get("has_mechanical_interface"),
            "from_bus_class": feat_frm.get("bus_class"),
            "to_bus_class": feat_to.get("bus_class"),
            "from_interop": feat_frm.get("interop_posture"),
            "to_interop": feat_to.get("interop_posture"),
            "interface_class": classify_interface(interface),
        }
        pairs.append(pair)
    return pairs


def classify_interface(interface_str):
    """按接口描述分类"""
    if not interface_str or interface_str == "unknown":
        return "unknown"
    s = interface_str.lower()
    if "iso 9409" in s:
        return "iso_9409"
    if "press_fit" in s or "press fit" in s:
        return "press_fit"
    if "thread" in s or "m8" in s or "m6" in s or "m10" in s:
        return "threaded"
    if "bus" in s or "ether" in s or "can" in s or "rs485" in s or "uart" in s or "spi" in s or "i2c" in s:
        return "digital_bus"
    if "power" in s or "voltage" in s:
        return "power"
    if "tendon" in s or "muscle" in s:
        return "bio"
    if "eskin" in s:
        return "eskin"
    return "other"


def compute_feature_importance(pairs):
    """
    用信息增益 (Information Gain) 评估每个特征的预测力。
    目标变量: rel_type (兼容性关系类型)
    """
    if not pairs:
        return []

    target = "rel_type"
    total = len(pairs)

    # 计算目标变量的熵
    target_counts = Counter(p[target] for p in pairs)
    target_entropy = -sum((c / total) * log2(c / total) for c in target_counts.values() if c > 0)

    # 对每个特征计算信息增益
    features = [
        "from_category", "to_category", "from_type", "to_type",
        "from_manufacturer", "to_manufacturer",
        "from_category_eq_to", "from_type_eq_to",
        "from_has_mechanical", "to_has_mechanical",
        "from_bus_class", "to_bus_class",
        "from_interop", "to_interop",
        "interface_class",
    ]

    results = []
    for feat in features:
        # 按特征值分组
        groups = defaultdict(list)
        for p in pairs:
            val = p.get(feat, "unknown")
            groups[val].append(p)

        # 条件熵
        conditional_entropy = 0
        for val, group in groups.items():
            n = len(group)
            if n == 0:
                continue
            group_target_counts = Counter(p[target] for p in group)
            group_entropy = -sum(
                (c / n) * log2(c / n) for c in group_target_counts.values() if c > 0
            )
            conditional_entropy += (n / total) * group_entropy

        # 信息增益
        info_gain = target_entropy - conditional_entropy

        # 特征基数 (不同值的数量)
        cardinality = len(groups)

        results.append({
            "feature": feat,
            "info_gain": round(info_gain, 4),
            "normalized_gain": round(info_gain / target_entropy, 4) if target_entropy > 0 else 0,
            "cardinality": cardinality,
            "top_values": dict(Counter(p.get(feat, "unknown") for p in pairs).most_common(5)),
        })

    results.sort(key=lambda x: x["info_gain"], reverse=True)
    return results


def compute_compatibility_patterns(pairs):
    """统计兼容性规律"""
    patterns = {
        "total_pairs": len(pairs),
        "relation_types": dict(Counter(p["rel_type"] for p in pairs)),
        "interface_classes": dict(Counter(p["interface_class"] for p in pairs)),
        "same_category_pairs": sum(1 for p in pairs if p.get("from_category_eq_to")),
        "cross_category_pairs": sum(1 for p in pairs if not p.get("from_category_eq_to")),
        "has_mechanical_both": sum(1 for p in pairs if p.get("from_has_mechanical") and p.get("to_has_mechanical")),
        "cross_vendor_pairs": sum(1 for p in pairs if p.get("from_manufacturer") != p.get("to_manufacturer")),
    }
    return patterns


def main():
    print("[*] 加载兼容性规则...")
    rules = load_compatibility_rules()
    print(f"    规则数: {len(rules)}")

    print("[*] 加载实体特征...")
    entities = load_entities_features()
    print(f"    实体数: {len(entities)}")

    print("[*] 构建兼容对特征矩阵...")
    pairs = build_compat_pairs(rules, entities)
    print(f"    有效兼容对: {len(pairs)}")

    if not pairs:
        print("[!] 无有效兼容对，跳过分析")
        return

    print("[*] 计算特征重要性 (信息增益)...")
    importance = compute_feature_importance(pairs)

    print("[*] 统计兼容规律...")
    patterns = compute_compatibility_patterns(pairs)

    # 输出 JSON
    report_json = {
        "method": "Information Gain (QuantFeature 方法论)",
        "target_variable": "rel_type (兼容性关系类型)",
        "total_pairs_analyzed": len(pairs),
        "feature_importance": importance,
        "compatibility_patterns": patterns,
        "recommendations": generate_recommendations(importance, patterns),
    }

    out_json = os.path.join(OPS_DIR, "feature-importance-report.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)
    print(f"[✓] JSON 报告: {out_json}")

    # 输出 Markdown
    out_md = os.path.join(OPS_DIR, "feature-importance-report.md")
    write_markdown(out_md, report_json, importance, patterns)
    print(f"[✓] Markdown 报告: {out_md}")


def generate_recommendations(importance, patterns):
    """基于分析结果生成推荐"""
    recs = []

    # 找出最有判别力的特征
    top_feat = importance[0]["feature"] if importance else None
    if top_feat:
        recs.append({
            "priority": "P0",
            "action": f"优先使用 '{top_feat}' 作为兼容性判定的首要维度",
            "rationale": f"信息增益最高 ({importance[0]['info_gain']})，对兼容性关系类型有最强区分力",
        })

    # 检查是否有机械接口维度不足
    mech_feats = [f for f in importance if "mechanical" in f["feature"]]
    if mech_feats and mech_feats[0]["info_gain"] < 0.1:
        recs.append({
            "priority": "P1",
            "action": "机械接口维度的预测力偏低，说明当前数据中机械接口声明率过低",
            "rationale": f"仅 {patterns.get('has_mechanical_both', 0)}/{patterns.get('total_pairs', 0)} 兼容对双方都声明了机械接口",
        })

    recs.append({
        "priority": "P1",
        "action": "interface_class 接口类型分类可直接作为兼容性第一层过滤条件",
        "rationale": "接口类型 (ISO 9409 / 螺纹 / 总线 / 生物) 决定物理连接可能性，是最粗粒度的过滤维度",
    })

    recs.append({
        "priority": "P2",
        "action": "跨厂商兼容对的分析是 RoboParts 差异化价值核心",
        "rationale": f"当前 {patterns.get('cross_vendor_pairs', 0)}/{patterns.get('total_pairs', 0)} 对跨厂商兼容关系",
    })

    recs.append({
        "priority": "P2",
        "action": "将特征重要性排序用于评分模型设计",
        "rationale": "按 info_gain 降序作为特征权重，构建兼容性评分 (0-100)，替代硬编码 IF-P-THEN",
    })

    return recs


def write_markdown(path, report, importance, patterns):
    lines = []
    lines.append("# 兼容性特征重要性分析报告")
    lines.append("")
    lines.append(f"> 方法: {report['method']}")
    lines.append(f"> 分析样本: {report['total_pairs_analyzed']} 条兼容性关系")
    lines.append(f"> 目标变量: {report['target_variable']}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 一、特征重要性排名")
    lines.append("")
    lines.append("| 排名 | 特征 | 信息增益 | 标准化增益 | 基数 | 解释 |")
    lines.append("|------|------|----------|------------|------|------|")

    explanations = {
        "from_category": "来源方零部件类别",
        "to_category": "目标方零部件类别",
        "from_type": "来源方零部件类型",
        "to_type": "目标方零部件类型",
        "from_manufacturer": "来源厂商",
        "to_manufacturer": "目标厂商",
        "from_category_eq_to": "双方类别是否一致",
        "from_type_eq_to": "双方类型是否一致",
        "from_has_mechanical": "来源方是否声明机械接口",
        "to_has_mechanical": "目标方是否声明机械接口",
        "from_bus_class": "来源方总线类型",
        "to_bus_class": "目标方总线类型",
        "from_interop": "来源方互操作姿态",
        "to_interop": "目标方互操作姿态",
        "interface_class": "接口分类 (ISO/螺纹/总线/生物)",
    }

    for i, feat in enumerate(importance, 1):
        exp = explanations.get(feat["feature"], "")
        lines.append(f"| {i} | `{feat['feature']}` | {feat['info_gain']} | {feat['normalized_gain']} | {feat['cardinality']} | {exp} |")

    lines.append("")
    lines.append("## 二、兼容性规律统计")
    lines.append("")
    lines.append(f"- 总兼容对: **{patterns['total_pairs']}**")
    lines.append(f"- 跨类别兼容对: {patterns['cross_category_pairs']} ({patterns['cross_category_pairs']/max(patterns['total_pairs'],1)*100:.1f}%)")
    lines.append(f"- 同类别兼容对: {patterns['same_category_pairs']} ({patterns['same_category_pairs']/max(patterns['total_pairs'],1)*100:.1f}%)")
    lines.append(f"- 跨厂商兼容对: {patterns['cross_vendor_pairs']} ({patterns['cross_vendor_pairs']/max(patterns['total_pairs'],1)*100:.1f}%)")
    lines.append(f"- 双方均有机械接口声明: {patterns['has_mechanical_both']}")
    lines.append("")
    lines.append("### 关系类型分布")
    lines.append("")
    lines.append("| 关系类型 | 数量 |")
    lines.append("|----------|------|")
    for k, v in patterns["relation_types"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("### 接口分类分布")
    lines.append("")
    lines.append("| 接口分类 | 数量 |")
    lines.append("|----------|------|")
    for k, v in patterns["interface_classes"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## 三、行动建议")
    lines.append("")
    for rec in report["recommendations"]:
        lines.append(f"### {rec['priority']}: {rec['action']}")
        lines.append(f"- **依据**: {rec['rationale']}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 四、QuantFeature 方法论在本项目的落地路径")
    lines.append("")
    lines.append("1. **统一特征引擎** (`compat_score_engine.py`): 将每个零部件的 20+ 属性抽为标准化 feature vector")
    lines.append("2. **特征重要性排序**: 本报告已给出第一版排序，后续随着数据增长需定期重跑")
    lines.append("3. **评分模型**: 按 info_gain 降序加权，构建兼容性评分 (0-100)，输出\"兼容概率\"而非\"是/否\"")
    lines.append("4. **增量学习**: 新用户提交的兼容性反馈 (确认/否决) 作为 label，用于迭代优化特征权重")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
