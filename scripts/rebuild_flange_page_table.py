#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate the '四大标准尺寸族对照表' in iso-9409-flange.html from verified
platforms.json HUB data, so the page can't drift from the dataset again."""
import json, re

HTML = "iso-9409-flange.html"
# 【20260818-W2】90 台机器人硬件清单已迁至 api/robot_fleet.json（与 platforms 实体类目解耦）。
d = json.load(open("api/robot_fleet.json", encoding="utf-8"))
data = d["data"]
hub = [e for e in data if str(e.get("id", "")).startswith("HUB-")]

CANON = {(50, 4, "M6"), (40, 4, "M6"), (80, 6, "M8")}
PAY = {20: "微型", 31.5: "小型", 40: "小型/协作", 50: "小型/协作",
       80: "中型", 100: "大型", 160: "大型", 250: "超重载"}

groups = {}
for e in hub:
    mi = e.get("mechanical_interface") or {}
    fl = mi.get("flange") or {}
    pcd = fl.get("pcd_mm")
    n = fl.get("bolt_count")
    thr = fl.get("thread")
    if not pcd or not n or not thr:
        continue
    groups.setdefault((pcd, n, thr), []).append(e.get("name", ""))

rows = []
for (pcd, n, thr), hosts in sorted(groups.items(), key=lambda kv: kv[0][0]):
    desig = "ISO9409-1-A%s-%d-%s" % (pcd, n, thr)
    canon = (pcd, n, thr) in CANON
    mark = "✅ 标准梯级" if canon else "⚠️ 厂商偏离"
    dow = ("2×φ%sH7" % thr.lstrip("M")) if canon else "—（需查手册）"
    pay = PAY.get(pcd, "通用")
    hosts_s = "、".join(sorted(set(hosts)))
    rows.append(
        "<tr><td><code>%s</code></td><td>%s</td><td>%d</td><td>%s</td>"
        "<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (desig, pcd, n, thr, dow, pay, mark, hosts_s)
    )

new_table = (
    '<div class="tablebox"><table><thead><tr>'
    "<th>Designation</th><th>节圆 d1 (mm)</th><th>螺栓数</th><th>螺纹</th>"
    "<th>定位销孔</th><th>典型负载级</th><th>是否 ISO 标准梯级</th><th>已核实机型</th>"
    "</tr></thead><tbody>"
    + "".join(rows)
    + "</tbody></table></div>"
    '<p class="meta">数据来源：Industrial Robotics Hub ISO 9409-1 法兰查表（%d 台机器人逐型核实，源等级 B，不编造规格），'
    "并经 ISO 9409-1:2004 型式A 标准梯级交叉校验。⚠️ 厂商偏离 = 该 (PCD,孔数,螺纹) 实测真实存在、"
    "但不等于 ISO 标准梯级（同一 A 标号在不同厂商可能对应不同几何，见下文）。</p>"
    % len(hub)
)

old_block_re = re.compile(
    r'<div class="tablebox"><table><thead><tr><th>Designation</th>.*?'
    r'数据来源：Industrial Robotics Hub ISO 9409-1 法兰查表.*?</p>',
    re.S,
)
html = open(HTML, encoding="utf-8").read()
m = old_block_re.search(html)
assert m, "old table block not found"
html2 = html[: m.start()] + new_table + html[m.end():]
open(HTML, "w", encoding="utf-8").write(html2)
print("replaced table block; new rows:", len(rows))
