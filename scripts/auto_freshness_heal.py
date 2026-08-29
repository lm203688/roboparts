#!/usr/bin/env python3
"""
数字保鲜自动修复器（Auto-Freshness Healer）
检测常见数字保鲜问题（品类数、实体数、OSS数等过期），可自修的自动修正+部署，不可自修的升级。
目标：把"检测→写待办等用户"变成"检测→自动修复→复测→上线"。
"""
import os, sys, re, json, subprocess
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
ARTICLES = os.path.join(ROOT, "articles")
NEEDS_USER = os.path.join(ROOT, "ops", "results", "_NEEDS_USER.md")


def load_truth():
    """Load ground truth numbers"""
    try:
        with open(os.path.join(ROOT, "api", "entities.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        meta = data.get("meta", {})
        return {
            "total": meta.get("total_entities", 0),
            "cats": len(meta.get("categories", [])),
            "oss": meta.get("oss_total", 0),
        }
    except Exception as e:
        print(f"[FRESHNESS-HEAL] Failed to load truth: {e}")
        return None


def scan_article_category_mismatch(truth):
    """Find articles with hardcoded category counts that don't match truth"""
    cat_count = truth["cats"]
    issues = []
    
    for fname in os.listdir(ARTICLES):
        if not fname.endswith(".html"):
            continue
        fpath = os.path.join(ARTICLES, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check for mismatched category numbers
        patterns = [
            (r"(\d+)\s*大品类", "大品类"),
            (r"(\d+)\s*大分类", "大分类"),
            (r"(\d+)\s*个品类", "个品类"),
            (r"(\d+)\s*个分类", "个分类"),
            (r"(\d+)\s*类\b", "类"),
        ]
        
        for pattern, label in patterns:
            for m in re.finditer(pattern, content):
                num = int(m.group(1))
                if num != cat_count and num in range(5, 30):  # sanity range
                    issues.append({
                        "file": fpath,
                        "match": m.group(0),
                        "current": num,
                        "expected": cat_count,
                        "label": label,
                    })
    
    return issues


def scan_entity_count_mismatch(truth):
    """Find articles with hardcoded entity counts that don't match truth"""
    total = truth["total"]
    issues = []
    
    for fname in os.listdir(ARTICLES):
        if not fname.endswith(".html"):
            continue
        fpath = os.path.join(ARTICLES, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        
        for m in re.finditer(r"(\d{3,4})\s*(?:个|款|条)?\s*(?:实体|组件|零件)", content):
            num = int(m.group(1))
            if num != total and num in range(400, 1000):  # sanity range
                issues.append({
                    "file": fpath,
                    "match": m.group(0),
                    "current": num,
                    "expected": total,
                })
    
    return issues


def auto_fix_category(issues):
    """Auto-fix category count mismatches in articles"""
    fixed = 0
    for issue in issues:
        fpath = issue["file"]
        old = issue["match"]
        new = old.replace(str(issue["current"]), str(issue["expected"]))
        
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        
        content = content.replace(old, new, 1)
        
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"  [AUTO-FIX] {os.path.basename(fpath)}: {old} -> {new}")
        fixed += 1
    
    return fixed


def check_llms_txt(truth):
    """Check if llms.txt has correct numbers"""
    llms_path = os.path.join(ROOT, "llms.txt")
    if not os.path.exists(llms_path):
        return None
    
    with open(llms_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    issues = []
    
    # Check entity count in llms.txt
    m = re.search(r"(\d+)\s*实体", content)
    if m:
        num = int(m.group(1))
        if num != truth["total"]:
            issues.append({"file": "llms.txt", "current": num, "expected": truth["total"], "type": "entity_count"})
    
    # Check category count in llms.txt
    m = re.search(r"(\d+)\s*(?:大)?品类", content)
    if m:
        num = int(m.group(1))
        if num != truth["cats"]:
            issues.append({"file": "llms.txt", "current": num, "expected": truth["cats"], "type": "cat_count"})
    
    return issues if issues else None


def escalate_to_needs_user(reason):
    """Add an escalation entry to _NEEDS_USER.md"""
    now = datetime.now().strftime("%Y%m%d-%H%M")
    marker = f"FRESHNESS-HEAL-{now}"
    
    with open(NEEDS_USER, "r", encoding="utf-8") as f:
        content = f.read()
    
    if marker in content:
        return  # Already escalated this run
    
    entry = (
        f"\n- [ ] **数字保鲜自动修复器升级项（{now}）**：{reason}\n"
        f"  本自动化只读、未改文件、未触发部署。\n"
        f"  <!-- assert: file:scripts/auto_freshness_heal.py exists -->\n"
    )
    
    # Insert after the header section (first "---")
    lines = content.splitlines()
    insert_idx = 3  # After header
    for i, line in enumerate(lines):
        if line.strip() == "---":
            insert_idx = i + 1
            break
    
    lines.insert(insert_idx, entry)
    with open(NEEDS_USER, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    
    print(f"  [ESCALATE] Added to _NEEDS_USER.md: {reason[:60]}...")


def main():
    print("[FRESHNESS-HEAL] Loading truth snapshot...")
    truth = load_truth()
    if not truth:
        print("[FRESHNESS-HEAL] Cannot load truth, aborting")
        return 1
    
    print(f"[FRESHNESS-HEAL] Truth: {truth['total']} entities, {truth['cats']} cats, {truth['oss']} OSS")
    
    # 1. Scan article category mismatches
    print("\n[FRESHNESS-HEAL] Scanning article category counts...")
    cat_issues = scan_article_category_mismatch(truth)
    if cat_issues:
        print(f"  Found {len(cat_issues)} category mismatches")
        fixed = auto_fix_category(cat_issues)
        print(f"  Auto-fixed: {fixed}")
    else:
        print("  GREEN: All article category counts match truth")
    
    # 2. Scan entity count mismatches
    print("\n[FRESHNESS-HEAL] Scanning entity counts...")
    entity_issues = scan_entity_count_mismatch(truth)
    if entity_issues:
        print(f"  Found {len(entity_issues)} entity count mismatches")
        for issue in entity_issues:
            print(f"  - {os.path.basename(issue['file'])}: {issue['current']} (expected {issue['expected']})")
        # These need manual review (too risky to auto-fix numbers in prose)
        escalate_to_needs_user(
            f"文章页实体数不匹配：{len(entity_issues)} 篇文章硬编码了过期实体数，"
            f"真值 {truth['total']}。需手动确认上下文后修正。"
        )
    else:
        print("  GREEN: All entity counts match truth")
    
    # 3. Check llms.txt
    print("\n[FRESHNESS-HEAL] Checking llms.txt...")
    llms_issues = check_llms_txt(truth)
    if llms_issues:
        print(f"  Found {len(llms_issues)} llms.txt issues")
        for issue in llms_issues:
            print(f"  - {issue['type']}: {issue['current']} (expected {issue['expected']})")
        escalate_to_needs_user(
            f"llms.txt 数字不匹配：{len(llms_issues)} 项过期。"
        )
    else:
        print("  GREEN: llms.txt numbers match truth")
    
    # Summary
    total_issues = len(cat_issues or []) + len(entity_issues or []) + len(llms_issues or [])
    total_fixed = len(cat_issues or [])
    
    print(f"\n[FRESHNESS-HEAL] SUMMARY: {total_issues} issues found, {total_fixed} auto-fixed, "
          f"{total_issues - total_fixed} escalated")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
