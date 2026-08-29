# RoboParts 服务端参数化生成脚本

## gen_adapter.py — 法兰转接板生成器

按两侧机器人法兰参数（ISO 9409-1 型式 A）生成一块可 3D 打印 / 可加工的
**转接板（adapter plate）**，导出 **STEP** 与 **STL**。

这是浏览器端生成器 [`adapter-generator.html`](../../adapter-generator.html)
（three.js 预览 + OpenSCAD 字符串导出）的服务端对应实现。区别在于：本脚本用
CadQuery(OCCT) 生成**真实 BREP 实体**，STEP 可直接进 SolidWorks / FreeCAD /
Fusion 做二次设计，圆孔是精确解析曲面而非三角面片近似。

### 几何模型

```
外径 R = max(PCD_A, PCD_B) / 2 + outer_margin     (outer_margin 默认 18mm)
板厚   = thick
```

在圆板上贯穿切除：

| 特征 | 位置 | 尺寸 |
|---|---|---|
| 侧 A 螺栓孔 | 均布于 Ø`a_pcd` 节圆，`n_A` 个 | 孔径 = `a_clr` |
| 侧 B 螺栓孔 | 均布于 Ø`b_pcd` 节圆，`n_B` 个 | 孔径 = `b_clr` |
| 定位销孔（可选） | 均布于 Ø`pin_pcd` 节圆 | 孔径 = `pin_d` |
| 中心通孔 | 板心 | 孔径 = `bore`，走线/走气/过轴 |
| 沉孔（可选） | 各螺栓孔上 | `cbore_d` × `cbore_depth`，侧 A 沉底面、侧 B 沉顶面 |

### 安装

```bash
pip install cadquery
```

国内网络建议走镜像：

```bash
pip install cadquery -i https://mirrors.aliyun.com/pypi/simple/
```

需要 Python 3.10+（已在 Python 3.13 + cadquery 2.8 / cadquery-ocp 7.9 验证）。
`cadquery-ocp` 约 47MB，首次安装较慢。

### 运行示例

```bash
# 1) 标准预设：A50 机器人侧 ↔ A80 工具侧，板厚 10，中心孔 Ø20
python gen_adapter.py --a-preset A50 --b-preset A80 --thick 10 --bore 20

# 2) 全自定义参数
python gen_adapter.py --a-pcd 63 --a-holes 6 --a-thread M6 \
                      --b-pcd 80 --b-holes 4 --b-thread M8 \
                      --thick 12 --bore 25 --out-dir ./out

# 3) 预设 + 局部覆盖 + 螺栓沉孔
python gen_adapter.py --a-preset A100 --b-preset A160 \
                      --b-pins 2 --b-pin-d 10 --b-pin-pcd 90 \
                      --a-cbore-depth 6 --thick 14

# 完整参数说明
python gen_adapter.py --help
```

内置预设：`A50` / `A80` / `A100` / `A160`（对应 ISO9409-1-A50-4-M6、
A80-6-M8、A100-6-M10、A160-8-M16）。预设值可被任意显式参数覆盖。

### 输出

在 `--out-dir`（默认当前目录）写出两个文件，文件名含两侧法兰标签：

```
flange-adapter_A50-4-M6__A80-6-M8.step    # BREP 实体，进 CAD 做二次设计
flange-adapter_A50-4-M6__A80-6-M8.stl     # 三角网格，直接切片 3D 打印
```

STL 三角化精度为线性偏差 0.01mm、角度偏差 0.1rad，足够 FDM/SLA 打印。
用 `--name` 改文件名前缀，`--quiet` 只打印产出路径（方便脚本管道）。

### 参数校验

* **非法参数**（`holes < 1`、`pcd <= 0`、`thick <= 0`、螺纹格式无法解析、
  沉孔深度 >= 板厚、中心孔大过整板等）会打印中文错误并以退出码 `2` 结束。
* **几何告警**（不致命，仍会出图）：孔冲出板外缘、孔与孔干涉、孔与中心通孔
  连通、剩余壁厚不足、板厚偏薄。加 `--strict` 可把告警升级为错误（退出码 `4`）。

退出码：`0` 成功 / `2` 参数错误 / `3` 缺 cadquery / `4` strict 模式下有告警 /
`5` 导出失败。

> 实测提示：`--a-preset A50 --b-preset A80 --bore 20` 会报告干涉告警 —— A50 的
> 销节圆 Ø22 与 Ø20 中心孔重叠 2mm，且 A50 螺栓孔与 A80 销孔撞车 1.25mm。这是
> 预设销位本身的问题，不是脚本 bug。实际使用时按告警调小 `--bore`（如 14）或
> 用 `--a-pin-pcd` / `--b-pin-pcd` 指定真实机型的销位。

### 已知口径说明

* **`--a-pin-pcd` / `--b-pin-pcd` 是直径**（PCD = Pitch Circle *Diameter*），
  销孔圆心落在半径 `pin_pcd / 2` 上。这与 `adapter-generator.html` 的 OpenSCAD
  导出分支一致。该 HTML 的 three.js **预览**分支把 pinPCD 当半径用，存在不一致：
  按半径解释会导致销孔压在螺栓孔上（A100 预设 pinPCD=50 恰等于其螺栓节圆半径
  50，两个销孔正好落在 0°/180° 的螺栓孔位置）。本脚本采用直径口径。
* **孔是光孔，不带螺纹牙型。** `--a-thread` 仅用于推导过孔间隙
  （间隙孔径 = 公称直径 + 0.5mm）与文件命名。转接板侧通常就是过孔配螺母、
  或与机器人侧的螺纹孔配合。真实螺纹牙型可在 FreeCAD 的 Thread Profile、
  或 CadQuery 的线程扩展（如 `cq_warehouse` 的 `IsoThread`）中另行追加 ——
  脚本刻意不硬依赖这些可选库，保证 `pip install cadquery` 后开箱即用。
* 非公制螺纹（如 G1/4）解析不了，请直接用 `--a-clr` / `--b-clr` 显式给出过孔直径。
