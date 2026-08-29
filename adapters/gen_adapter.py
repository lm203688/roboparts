#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_adapter.py — RoboParts 法兰转接板（adapter plate）参数化生成器

服务端 / CLI 版本，用 CadQuery(OCCT) 生成**真实 BREP 实体**，导出 STEP + STL。
对应浏览器端生成器 `adapter-generator.html`（three.js + OpenSCAD 字符串）的
同等几何，但输出可直接进 CAD（SolidWorks / FreeCAD / Fusion）做二次设计，
精度不受三角面片化限制。

几何模型
--------
一块圆形平板，同时承接两侧机器人法兰（ISO 9409-1 型式 A）：

    外径 R = max(PCD_A, PCD_B) / 2 + outer_margin   (默认 margin = 18mm)
    板厚 = thick

在板上贯穿切除：
    * 侧 A 螺栓孔：n_A 个，均布于 Ø PCD_A 节圆，孔半径 = clr_A / 2
    * 侧 B 螺栓孔：n_B 个，均布于 Ø PCD_B 节圆，孔半径 = clr_B / 2
    * 侧 A / B 定位销孔（可选）：均布于 Ø pin_pcd 节圆，孔半径 = pin_d / 2
    * 中心通孔：半径 = bore / 2（走线 / 走气 / 过轴）

关于 pin_pcd 的口径说明
----------------------
`--a-pin-pcd` / `--b-pin-pcd` 按其名字（PCD = Pitch Circle **Diameter**）解释为
**直径**，销孔圆心落在半径 pin_pcd/2 上。这与 `adapter-generator.html` 的
OpenSCAD 导出分支一致（其 `pins()` 模块内部做 `translate([pcd/2,0,0])`）。

注意：该 HTML 的 three.js **预览**分支存在一处不一致 —— 它把 pinPCD 当成半径
直接用（`s.pinPCD*Math.cos(a)`）。按半径解释会导致销孔与螺栓孔干涉，例如
A100 预设 pinPCD=50 恰好等于其螺栓节圆半径 50，两个销孔会正好压在 0°/180°
的螺栓孔上。因此本脚本采用直径口径（正确解释），并对干涉做显式校验告警。

关于螺纹
--------
`--a-thread` / `--b-thread`（如 M6/M8）在此**仅用于推导螺栓过孔间隙**
（clr = 公称直径 + 0.5mm）与文件命名，孔为光孔（clearance hole），不生成螺纹
牙型 —— 转接板侧通常就是过孔 + 螺母/机器人侧螺纹孔配合。
真实螺纹牙型可在 FreeCAD 的 Thread Profile、或 CadQuery 的线程扩展
（如 cq_warehouse 的 `Thread` / `IsoThread`）中另行追加；本脚本不硬依赖这些
可选库，保持基础孔即可，以确保 `pip install cadquery` 后开箱即用。

用法
----
    python gen_adapter.py --a-preset A50 --b-preset A80 --thick 10 --bore 20
    python gen_adapter.py --a-pcd 63 --a-holes 6 --a-thread M6 \
                          --b-pcd 80 --b-holes 4 --b-thread M8 --thick 12

依赖：pip install cadquery
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# CadQuery 是重依赖（拖 OCCT）。这里做保护性导入，使得即使未安装 cadquery，
# `--help` 与参数校验依然可用，只有真正开始建模时才报缺依赖的错。
try:
    import cadquery as cq
except ImportError:  # pragma: no cover - 取决于运行环境
    cq = None


# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

#: 通孔切除时上下各多伸出的量(mm)。避免切除体与实体表面共面，
#: 共面布尔在 OCCT 里容易产生残留薄片/失败。等价于 OpenSCAD 里常见的 h = t + 2。
EPS = 0.05

#: STL 三角化精度：线性偏差(mm) 与 角度偏差(rad)。0.01mm 足够 3D 打印。
STL_LINEAR_TOL = 0.01
STL_ANGULAR_TOL = 0.1

#: 螺栓过孔间隙 = 公称直径 + 该值(mm)。与 adapter-generator.html 的预设一致
#: (M6->6.5, M8->8.5, M10->10.5, M12->12.5)。
CLEARANCE_ADD = 0.5

DEFAULT_OUTER_MARGIN = 18.0

#: ISO 4762 内六角圆柱头螺钉头部直径，用于推导默认沉孔直径。
SHCS_HEAD_D: Dict[float, float] = {
    3: 5.5, 4: 7.0, 5: 8.5, 6: 10.0, 8: 13.0,
    10: 16.0, 12: 18.0, 14: 21.0, 16: 24.0,
}

#: ISO 9409-1 型式 A 标准法兰预设（与 adapter-generator.html 的 PRESETS 对齐）。
#: 注：机器人行业 "A{n}" 中 n = 节圆直径 PCD；pin_pcd 为定位销节圆直径（仅标准梯级填真实值，
#: 偏离尺寸 A20/A31.5/A100/A160/A250 厂商销孔几何未知，pins=0）。
PRESETS: Dict[str, Dict] = {
    "A20": dict(label="ISO9409-1-A20-4-M3", pcd=20.0, holes=4, thread="M3",
                clr=3.5, pins=0, pin_d=0.0, pin_pcd=0.0),
    "A31.5": dict(label="ISO9409-1-A31.5-4-M5", pcd=31.5, holes=4, thread="M5",
                  clr=5.5, pins=0, pin_d=0.0, pin_pcd=0.0),
    "A40": dict(label="ISO9409-1-A40-4-M6", pcd=40.0, holes=4, thread="M6",
                clr=6.5, pins=2, pin_d=6.0, pin_pcd=50.0),
    "A50": dict(label="ISO9409-1-A50-4-M6", pcd=50.0, holes=4, thread="M6",
                clr=6.5, pins=2, pin_d=6.0, pin_pcd=63.0),
    "A80": dict(label="ISO9409-1-A80-6-M8", pcd=80.0, holes=6, thread="M8",
                clr=8.5, pins=2, pin_d=8.0, pin_pcd=100.0),
    "A100": dict(label="ISO9409-1-A100-4-M8", pcd=100.0, holes=4, thread="M8",
                 clr=8.5, pins=0, pin_d=0.0, pin_pcd=0.0),
    "A160": dict(label="ISO9409-1-A160-4-M12", pcd=160.0, holes=4, thread="M12",
                 clr=13.0, pins=0, pin_d=0.0, pin_pcd=0.0),
    "A250": dict(label="ISO9409-1-A250-4-M16", pcd=250.0, holes=4, thread="M16",
                 clr=17.0, pins=0, pin_d=0.0, pin_pcd=0.0),
}

#: 未指定预设时的自定义侧默认值（对齐 HTML 的 CUSTOM）。
CUSTOM_DEFAULT = dict(label="custom", pcd=60.0, holes=4, thread="M6",
                      clr=None, pins=0, pin_d=6.0, pin_pcd=None)


class ParamError(ValueError):
    """参数非法。由 main() 捕获后打印为友好错误并以退出码 2 结束。"""


# --------------------------------------------------------------------------
# 参数模型
# --------------------------------------------------------------------------

@dataclass
class Hole:
    """一个待切除的圆孔（贯穿），可带沉孔。"""
    x: float
    y: float
    r: float
    kind: str           # 'bolt' | 'pin' | 'bore'
    tag: str            # 用于报错/告警的可读标识，如 'A-bolt#2'
    cbore_d: float = 0.0
    cbore_depth: float = 0.0
    cbore_from_top: bool = False


@dataclass
class FlangeSide:
    """一侧法兰的完整参数。"""
    name: str           # 'A' | 'B'
    label: str
    pcd: float
    holes: int
    thread: str
    clr: float
    pins: int
    pin_d: float
    pin_pcd: float
    cbore_d: float = 0.0
    cbore_depth: float = 0.0

    def short_label(self) -> str:
        """用于文件名的紧凑标签，如 A50-4-M6。"""
        return "A{:g}-{}-{}".format(self.pcd, self.holes, self.thread.upper())

    def validate(self) -> None:
        n = self.name
        if self.pcd <= 0:
            raise ParamError(f"侧 {n}: --{n.lower()}-pcd 必须 > 0（当前 {self.pcd}）")
        if self.holes < 1:
            raise ParamError(
                f"侧 {n}: --{n.lower()}-holes 必须 >= 1（当前 {self.holes}）；"
                f"法兰至少要有一个螺栓孔")
        if self.holes > 64:
            raise ParamError(f"侧 {n}: --{n.lower()}-holes 过大（当前 {self.holes}，上限 64）")
        if self.clr <= 0:
            raise ParamError(f"侧 {n}: 螺栓过孔间隙必须 > 0（当前 {self.clr}）")
        if self.pins < 0:
            raise ParamError(f"侧 {n}: --{n.lower()}-pins 不能为负（当前 {self.pins}）")
        if self.pins > 0:
            if self.pin_d <= 0:
                raise ParamError(
                    f"侧 {n}: pins={self.pins} 但 --{n.lower()}-pin-d 未给出或 <= 0")
            if self.pin_pcd <= 0:
                raise ParamError(
                    f"侧 {n}: pins={self.pins} 但 --{n.lower()}-pin-pcd 未给出或 <= 0")
        if self.cbore_depth < 0:
            raise ParamError(f"侧 {n}: --{n.lower()}-cbore-depth 不能为负")
        if self.cbore_depth > 0 and self.cbore_d <= self.clr:
            raise ParamError(
                f"侧 {n}: 沉孔直径 {self.cbore_d} 必须大于过孔直径 {self.clr}")

    def hole_list(self) -> List[Hole]:
        """生成该侧的所有孔（螺栓孔 + 定位销孔），圆心在 XY 平面。"""
        out: List[Hole] = []
        # 侧 A 的沉孔开在底面(z=0)，侧 B 的开在顶面(z=thick)。
        from_top = (self.name == "B")

        r = self.pcd / 2.0
        step = 360.0 / self.holes
        for i in range(self.holes):
            ang = math.radians(step * i)
            out.append(Hole(
                x=r * math.cos(ang), y=r * math.sin(ang), r=self.clr / 2.0,
                kind="bolt", tag=f"{self.name}-bolt#{i + 1}",
                cbore_d=self.cbore_d, cbore_depth=self.cbore_depth,
                cbore_from_top=from_top,
            ))

        if self.pins > 0:
            # pin_pcd 是直径 -> 圆心半径 = pin_pcd / 2（见模块 docstring 说明）
            rp = self.pin_pcd / 2.0
            pstep = 360.0 / self.pins
            for i in range(self.pins):
                ang = math.radians(pstep * i)
                out.append(Hole(
                    x=rp * math.cos(ang), y=rp * math.sin(ang), r=self.pin_d / 2.0,
                    kind="pin", tag=f"{self.name}-pin#{i + 1}",
                ))
        return out


# --------------------------------------------------------------------------
# 参数解析与推导
# --------------------------------------------------------------------------

_THREAD_RE = re.compile(r"^\s*M\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def thread_nominal(thread: str) -> float:
    """从 'M6' / 'M10' 解析公称直径。解析不出来就报错。"""
    m = _THREAD_RE.match(thread or "")
    if not m:
        raise ParamError(
            f"无法解析螺纹规格 {thread!r}；应形如 M6 / M8 / M10。"
            f"若为非公制螺纹，请直接用 --a-clr / --b-clr 显式给出过孔直径")
    return float(m.group(1))


def clearance_for_thread(thread: str) -> float:
    """螺栓过孔直径 = 公称直径 + 0.5mm。"""
    return thread_nominal(thread) + CLEARANCE_ADD


def default_cbore_d(thread: str) -> float:
    """默认沉孔直径：ISO 4762 内六角头直径 + 1mm 装配间隙。"""
    nominal = thread_nominal(thread)
    head = SHCS_HEAD_D.get(nominal)
    if head is None:
        head = nominal * 1.6
    return head + 1.0


def resolve_side(args: argparse.Namespace, name: str) -> FlangeSide:
    """把 CLI 参数（可能来自预设 + 显式覆盖）解析成一个 FlangeSide。"""
    s = name.lower()

    def arg(key: str):
        return getattr(args, f"{s}_{key}")

    preset_key = arg("preset")
    if preset_key:
        base = dict(PRESETS[preset_key])
    else:
        base = dict(CUSTOM_DEFAULT)

    pcd = arg("pcd") if arg("pcd") is not None else base["pcd"]
    holes = arg("holes") if arg("holes") is not None else base["holes"]
    thread = arg("thread") if arg("thread") is not None else base["thread"]

    # clr 优先级：显式 --x-clr > (显式改了螺纹则按新螺纹重算) > 预设值 > 按螺纹推导
    if arg("clr") is not None:
        clr = arg("clr")
    elif arg("thread") is not None:
        clr = clearance_for_thread(thread)
    elif base.get("clr") is not None:
        clr = base["clr"]
    else:
        clr = clearance_for_thread(thread)

    pins = arg("pins") if arg("pins") is not None else base["pins"]
    pin_d = arg("pin_d") if arg("pin_d") is not None else base["pin_d"]

    if arg("pin_pcd") is not None:
        pin_pcd = arg("pin_pcd")
    elif base.get("pin_pcd") is not None:
        pin_pcd = base["pin_pcd"]
    else:
        # 自定义侧默认销节圆：尽量往内让开螺栓圆，同时不至于压到中心。
        pin_pcd = max(pcd - 28.0, (pin_d or 0.0) + 12.0)

    cbore_depth = arg("cbore_depth") or 0.0
    if arg("cbore_d") is not None:
        cbore_d = arg("cbore_d")
    elif cbore_depth > 0:
        cbore_d = default_cbore_d(thread)
    else:
        cbore_d = 0.0

    label = base.get("label") or "custom"
    if preset_key is None:
        label = "custom"

    side = FlangeSide(name=name.upper(), label=label, pcd=float(pcd),
                      holes=int(holes), thread=str(thread), clr=float(clr),
                      pins=int(pins), pin_d=float(pin_d or 0.0),
                      pin_pcd=float(pin_pcd or 0.0),
                      cbore_d=float(cbore_d), cbore_depth=float(cbore_depth))
    side.validate()
    return side


# --------------------------------------------------------------------------
# 几何校验（干涉 / 边距）
# --------------------------------------------------------------------------

def check_geometry(holes: List[Hole], outer_r: float, thick: float) -> List[str]:
    """
    返回告警列表（不致命）。真正非法的情况在别处直接抛 ParamError。

    两类检查：孔是否冲出板外缘、任意两孔是否互相干涉。中心通孔本身也在
    `holes` 里，所以"螺栓孔/销孔啃到中心孔"这种情况由两两检查自然覆盖。
    两侧法兰的孔圈很容易撞在一起，这是转接板设计最常见的坑，故显式提示。
    """
    warns: List[str] = []

    for h in holes:
        if h.kind == "bore":
            continue  # 中心孔必然在板中心，谈不上"冲出外缘"
        # 剩余壁厚 = 外缘 - (孔心距 + 孔半径)
        wall = outer_r - (math.hypot(h.x, h.y) + h.r)
        if wall < 0:
            warns.append(
                f"{h.tag} 已超出板外缘 {abs(wall):.2f}mm —— 孔会被切开成豁口，"
                f"请增大 --outer-margin")
        elif wall < 2.0:
            warns.append(
                f"{h.tag} 距板外缘仅剩 {wall:.2f}mm 壁厚（建议 >= 2mm），"
                f"考虑增大 --outer-margin")

    for i in range(len(holes)):
        for j in range(i + 1, len(holes)):
            a, b = holes[i], holes[j]
            dist = math.hypot(a.x - b.x, a.y - b.y)
            gap = dist - (a.r + b.r)
            # 涉及中心通孔时换一种说法，"孔位撞车"只适用于两个法兰孔
            if "bore" in (a.kind, b.kind):
                hint = "会连成一个异形孔，请减小 --bore 或调整该孔位置"
            else:
                hint = "两侧法兰孔位撞车，考虑旋转某一侧或改用异形孔"
            if dist < 1e-6:
                warns.append(f"{a.tag} 与 {b.tag} 完全同心重合")
            elif gap < 0:
                warns.append(f"{a.tag} 与 {b.tag} 干涉 {abs(gap):.2f}mm —— {hint}")
            elif gap < 1.5:
                warns.append(
                    f"{a.tag} 与 {b.tag} 之间仅剩 {gap:.2f}mm 材料（建议 >= 1.5mm）")

    if thick < 4.0:
        warns.append(f"板厚 {thick:g}mm 偏薄，法兰转接板一般 >= 4mm 以保证刚度")

    return warns


# --------------------------------------------------------------------------
# 建模
# --------------------------------------------------------------------------

def _cylinder(x: float, y: float, r: float, z0: float, h: float):
    """在 (x,y) 处生成一个从 z0 起、高 h 的圆柱切除体。"""
    return (cq.Workplane("XY")
            .workplane(offset=z0)
            .moveTo(x, y)
            .circle(r)
            .extrude(h))


def build_adapter(side_a: FlangeSide, side_b: FlangeSide, thick: float,
                  bore: float, outer_margin: float):
    """
    构建转接板实体，返回 (Workplane, outer_r, holes)。

    做法：先 extrude 一个圆柱底板，再逐个 cut 掉贯穿圆柱。
    切除体上下各多伸 EPS，等价于 OpenSCAD 的 h=t+2 手法，
    也等价于 CadQuery 的 `cutBlind(-cq.Through)`，但对共面布尔更稳健。
    """
    if cq is None:
        raise RuntimeError(
            "未安装 cadquery，无法建模。请先执行：pip install cadquery")

    outer_r = max(side_a.pcd, side_b.pcd) / 2.0 + outer_margin

    holes = side_a.hole_list() + side_b.hole_list()
    if bore > 0:
        holes.append(Hole(x=0.0, y=0.0, r=bore / 2.0, kind="bore", tag="center-bore"))

    if bore / 2.0 >= outer_r:
        raise ParamError(
            f"中心通孔半径 {bore / 2.0:g}mm 不小于板外径半径 {outer_r:g}mm，"
            f"板会被完全掏空")

    # 底板
    part = cq.Workplane("XY").circle(outer_r).extrude(thick)

    # 逐孔切除
    for h in holes:
        part = part.cut(_cylinder(h.x, h.y, h.r, -EPS, thick + 2 * EPS))

        # 可选沉孔：让内六角螺钉头沉入板内，避免干涉、提高装配精度。
        if h.cbore_depth > 0 and h.cbore_d > 0:
            if h.cbore_depth >= thick:
                raise ParamError(
                    f"{h.tag}: 沉孔深度 {h.cbore_depth}mm 不小于板厚 {thick}mm")
            cb_r = h.cbore_d / 2.0
            if h.cbore_from_top:
                part = part.cut(_cylinder(h.x, h.y, cb_r,
                                          thick - h.cbore_depth,
                                          h.cbore_depth + EPS))
            else:
                part = part.cut(_cylinder(h.x, h.y, cb_r, -EPS,
                                          h.cbore_depth + EPS))

    return part, outer_r, holes


# --------------------------------------------------------------------------
# 导出
# --------------------------------------------------------------------------

_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_name(text: str) -> str:
    return _SAFE_RE.sub("-", text).strip("-") or "part"


def export_part(part, out_dir: str, base_name: str) -> List[str]:
    """导出 STEP + STL，返回写出的文件路径列表。"""
    os.makedirs(out_dir, exist_ok=True)
    written = []

    step_path = os.path.join(out_dir, base_name + ".step")
    cq.exporters.export(part, step_path, exportType="STEP")
    written.append(step_path)

    stl_path = os.path.join(out_dir, base_name + ".stl")
    cq.exporters.export(part, stl_path, exportType="STL",
                        tolerance=STL_LINEAR_TOL,
                        angularTolerance=STL_ANGULAR_TOL)
    written.append(stl_path)

    return written


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def add_side_args(parser: argparse.ArgumentParser, name: str) -> None:
    s = name.lower()
    g = parser.add_argument_group(f"侧 {name} 法兰参数")
    g.add_argument(f"--{s}-preset", choices=sorted(PRESETS),
                   help="ISO 9409-1 标准预设，可被下面的显式参数覆盖")
    g.add_argument(f"--{s}-pcd", type=float, metavar="MM",
                   help="螺栓节圆直径 PCD (mm)")
    g.add_argument(f"--{s}-holes", type=int, metavar="N", help="螺栓孔数量")
    g.add_argument(f"--{s}-thread", type=str, metavar="MX",
                   help="螺纹规格，如 M6；用于推导过孔间隙与命名")
    g.add_argument(f"--{s}-clr", type=float, metavar="MM",
                   help="螺栓过孔直径 (mm)，默认 = 公称直径 + 0.5")
    g.add_argument(f"--{s}-pins", type=int, metavar="N",
                   help="定位销孔数量（通常 0 或 2）")
    g.add_argument(f"--{s}-pin-d", type=float, metavar="MM", help="定位销孔直径 (mm)")
    g.add_argument(f"--{s}-pin-pcd", type=float, metavar="MM",
                   help="定位销节圆直径 (mm，直径口径，非半径)")
    g.add_argument(f"--{s}-cbore-d", type=float, metavar="MM",
                   help="螺栓沉孔直径 (mm)，默认按 ISO 4762 内六角头推导")
    g.add_argument(f"--{s}-cbore-depth", type=float, metavar="MM",
                   help="螺栓沉孔深度 (mm)，>0 才开沉孔；侧A沉在底面，侧B沉在顶面")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gen_adapter.py",
        description="RoboParts 法兰转接板参数化生成器（CadQuery → STEP + STL）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  # 用标准预设：A50 机器人侧 ↔ A80 工具侧\n"
            "  python gen_adapter.py --a-preset A50 --b-preset A80 "
            "--thick 10 --bore 20\n\n"
            "  # 全自定义参数\n"
            "  python gen_adapter.py --a-pcd 63 --a-holes 6 --a-thread M6 \\\n"
            "                        --b-pcd 80 --b-holes 4 --b-thread M8 \\\n"
            "                        --thick 12 --bore 25 --out-dir ./out\n\n"
            "  # 预设 + 局部覆盖 + 沉孔\n"
            "  python gen_adapter.py --a-preset A100 --b-preset A160 \\\n"
            "                        --b-pins 2 --b-pin-d 10 --b-pin-pcd 90 \\\n"
            "                        --a-cbore-depth 6 --thick 14\n"
        ),
    )
    add_side_args(p, "A")
    add_side_args(p, "B")

    g = p.add_argument_group("板体参数")
    g.add_argument("--thick", type=float, default=10.0, metavar="MM",
                   help="板厚 (mm)，默认 10")
    g.add_argument("--bore", type=float, default=20.0, metavar="MM",
                   help="中心通孔直径 (mm)，0 表示不开孔，默认 20")
    g.add_argument("--outer-margin", type=float, default=DEFAULT_OUTER_MARGIN,
                   metavar="MM",
                   help=f"外缘余量 (mm)：外径 = max(PCD)/2 + 该值，"
                        f"默认 {DEFAULT_OUTER_MARGIN:g}")

    g = p.add_argument_group("输出")
    g.add_argument("--out-dir", type=str, default=".", metavar="DIR",
                   help="输出目录，默认当前目录（不存在会自动创建）")
    g.add_argument("--name", type=str, default="flange-adapter", metavar="NAME",
                   help="输出文件名前缀，默认 flange-adapter")
    g.add_argument("--strict", action="store_true",
                   help="把几何告警（干涉/边距不足）升级为错误，不产出文件")
    g.add_argument("--quiet", action="store_true", help="只输出产出文件路径")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        side_a = resolve_side(args, "A")
        side_b = resolve_side(args, "B")

        if args.thick <= 0:
            raise ParamError(f"--thick 必须 > 0（当前 {args.thick}）")
        if args.bore < 0:
            raise ParamError(f"--bore 不能为负（当前 {args.bore}）")
        if args.outer_margin <= 0:
            raise ParamError(f"--outer-margin 必须 > 0（当前 {args.outer_margin}）")
    except ParamError as exc:
        print(f"参数错误: {exc}", file=sys.stderr)
        return 2

    if cq is None:
        print("错误: 未找到 cadquery。请先安装：\n    pip install cadquery",
              file=sys.stderr)
        return 3

    try:
        part, outer_r, holes = build_adapter(
            side_a, side_b, args.thick, args.bore, args.outer_margin)
    except ParamError as exc:
        print(f"参数错误: {exc}", file=sys.stderr)
        return 2

    warns = check_geometry(holes, outer_r, args.thick)
    if warns:
        stream = sys.stderr
        print(f"{'错误' if args.strict else '几何告警'}: 共 {len(warns)} 条",
              file=stream)
        for w in warns:
            print(f"  - {w}", file=stream)
        if args.strict:
            print("已启用 --strict，未产出文件。", file=stream)
            return 4

    base = "{}_{}__{}".format(safe_name(args.name),
                              safe_name(side_a.short_label()),
                              safe_name(side_b.short_label()))
    try:
        written = export_part(part, args.out_dir, base)
    except Exception as exc:  # OCCT / 文件系统层面的失败
        print(f"导出失败: {exc}", file=sys.stderr)
        return 5

    if not args.quiet:
        n_bolt = sum(1 for h in holes if h.kind == "bolt")
        n_pin = sum(1 for h in holes if h.kind == "pin")
        print("转接板已生成")
        print(f"  外径      Ø{outer_r * 2:.1f} mm")
        print(f"  板厚      {args.thick:g} mm")
        print(f"  中心通孔  " + (f"Ø{args.bore:g} mm" if args.bore > 0 else "无"))
        print(f"  侧 A      {side_a.label} | PCD Ø{side_a.pcd:g}, "
              f"{side_a.holes}×{side_a.thread} (过孔 Ø{side_a.clr:g})"
              + (f", {side_a.pins}×销 Ø{side_a.pin_d:g} @PCD Ø{side_a.pin_pcd:g}"
                 if side_a.pins else ""))
        print(f"  侧 B      {side_b.label} | PCD Ø{side_b.pcd:g}, "
              f"{side_b.holes}×{side_b.thread} (过孔 Ø{side_b.clr:g})"
              + (f", {side_b.pins}×销 Ø{side_b.pin_d:g} @PCD Ø{side_b.pin_pcd:g}"
                 if side_b.pins else ""))
        print(f"  孔总数    {n_bolt} 螺栓 + {n_pin} 销"
              + (" + 1 中心孔" if args.bore > 0 else ""))
        print("  输出:")

    for path in written:
        size = os.path.getsize(path)
        if args.quiet:
            print(path)
        else:
            print(f"    {path}  ({size:,} bytes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
