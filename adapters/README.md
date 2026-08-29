# RoboParts 法兰转接件生成器（开源）

> 把**不兼容的机器人法兰**变成**兼容**。

当机器人腕部法兰（侧 A）与工具 / 末端执行器法兰（侧 B）的螺栓节圆、孔数、螺纹不一致时，本工具自动生成一块可 3D 打印的转接板，让你把两端连起来。

这是 [RoboParts](https://roboparts.cc)「兼容无忧」从**判定**走向**解决**的一步：不仅告诉你"拼不拼得上"，还直接给你能打印的零件。

## 在线版（零安装，推荐）

🌐 **https://roboparts.cc/adapter-generator**

- 选两侧 ISO 9409-1 法兰（A50/A80/A100/A160）或自定义参数
- 浏览器内实时 3D 预览（three.js，无需后端）
- 一键下载 **STL**（直接 3D 打印）或 **OpenSCAD 源文件**（免费桌面端二次编辑）
- 生成的配置可**分享链接**复现，并支持 X / Reddit / Hacker News / 知乎 一键分发

## 命令行版（高精度 STEP，CadQuery）

适合要进 CAD（SolidWorks / FreeCAD / Fusion）做二次设计的场景，输出真实 BREP 实体而非三角面片。

```bash
pip install cadquery
python gen_adapter.py --a-preset A50 --b-preset A80 --thick 10 --bore 20
```

参数（两侧各一套，可被预设 + 显式覆盖）：

| 参数 | 含义 |
|---|---|
| `--a-preset` / `--b-preset` | ISO 9409-1 标准预设 A50/A80/A100/A160 |
| `--a-pcd` / `--b-pcd` | 螺栓节圆直径 PCD (mm) |
| `--a-holes` / `--b-holes` | 螺栓孔数 |
| `--a-thread` / `--b-thread` | 螺纹规格（M6/M8/M10，用于推导过孔间隙） |
| `--a-pins` / `--b-pins` | 定位销孔数（0 或 2） |
| `--a-pin-d` / `--b-pin-d` | 定位销孔直径 (mm) |
| `--thick` | 板厚 (mm) |
| `--bore` | 中心通孔直径 (mm) |
| `--out-dir` | 输出目录 |
| `--strict` | 几何告警（干涉/边距不足）升级为错误，不产出 |

导出 `flange-adapter_A50-4-M6__A80-6-M8.step` 与 `.stl`。脚本会主动校验**孔位干涉**与**外缘壁厚**并告警（可用 `--strict` 拒绝出图）。

## 示例

`example_adapter.scad` 是 A50↔A80 的 OpenSCAD 源文件，可直接 `openscad example_adapter.scad` 预览或导出 STL。

## 装配安全红线（来自 ISO 9409-1 法兰规范）

1. 螺栓**不得过长**——超长会顶破腕部油封导致减速器漏油，装机前查原厂允许旋入深度。
2. 螺栓强度等级按原厂（如 ABB 强制 12.9 级），禁用不锈钢 / 低等级防咬死或松动。
3. 定位销用 g6 过渡配合，严禁过盈硬敲损伤销孔。
4. 本工具产物为**几何转接建议**，不构成认证，量产前请样机实测。

## 开源生态

参考 [OpenSCAD](https://openscad.org/) / [CadQuery](https://cadquery.readthedocs.io/) / [build123d](https://build123d.readthedocs.io/) / [FreeCAD](https://www.freecad.org/)。

---

RoboParts · 开源机器人零部件兼容性平台 · https://roboparts.cc · 数据集与兼容性矩阵免费可引用（CC-BY 4.0）
