# 运动学可达性层（2026-09-19）

## 一句话

把 RoboParts 的「零件级 + 判定」从**静态机械接口**（能不能拧上去）延伸到**动态可达性**
（拼出来的臂/腿够不够得到目标距离），并把「缺什么数据」显式登记出来。

## 为什么做这一层

借鉴 **PyRoki**（UC Berkeley，MIT，IROS 2025，`github.com/chungmin99/pyroki`）的
**URDF 优先数据模型**：它把 URDF 解析 / 正逆运动学 / 碰撞检测拆成互不依赖的模块，
跑在 CPU/GPU/TPU 上。我们不搬代码（Python + JAX **跑不进 Cloudflare Workers 边缘**），
只搬它的前提——**零件若不带运动学元数据，任何 IK 判定都无从谈起**。

于是本层的真实产出不是「一个能算的解算器」，而是：

1. 一张**运动学真相源**（`kinematics/source.json`），登记每条参考构型的链；
2. 一个**fail-closed 的判定引擎**（`scripts/build_kinematics.py`），
   只对参数齐全的链给结论，否则一律 `unknown`；
3. 一个**阴阳自测闸门**（`scripts/verify_kinematics.py`，已挂 CI 第 21 项）。

## 判定语义（刻意选 sound 方向）

```
max_reach_mm = Σ link_mm          # 可达半径上界
target > max_reach  → unreachable      # 可靠结论
target ≤ max_reach  → not_ruled_out    # 保守：仅表示未被排除
```

忽略关节限位与自碰撞，所以两个方向的**可信度不对称**：负面结论（够不到）可靠，
正面结论保守。这与项目既有纪律一致——宁缺勿假，不把「未排除」说成「可达」。

## 当前覆盖（诚实值）

| 链 | 构型 | DOF | 状态 | 缺什么 |
|---|---|---|---|---|
| `KC-OMY-ARM` | OpenManipulator (RB-OMY) | 4 | `insufficient_data` | joint_order / joint_axis / **link_mm** / joint_limits_deg |
| `KC-ODM-BIPED` | Open Duck Mini v2 (RB-ODM) | 14 | `insufficient_data` | 同上 |

**computed = 0 / 2。这是数据缺口，不是算法缺陷。**

自由度与关节类型来自 `api/reference_builds.json` 的已核实事实；连杆长度/轴向/限位三项
厂商公开页面未给出（emanual 未列 horn PCD 与连杆节距），因此登记为待测，**不臆造**。
补上 `joints[].link_mm` 后该链自动进入 `computed`，**无需改代码**。

## 为什么非做「阴阳自测」不可

一个「永远返回 `insufficient_data`」的引擎，跟一个写坏的引擎，**输出长得一模一样**。
只比对外 JSON 会 100% 假绿。所以 `verify_kinematics.py` 必须：

- **阳性对照**：构造参数齐全的假链（2 关节 / 100+150mm），断言 `max_reach=250`、
  150mm → `not_ruled_out`、300mm → `unreachable`；
- **阴性对照**：抽掉一个 `link_mm`，断言回 `insufficient_data` 且点名 `link_mm@j2`；
- **守卫**：`0 / 负值 / bool / 字符串` 一律不得被当有效长度（静默算成 0 = 假绿）；
- **口径**：`fixed` 关节不得虚增可动数；`prismatic` 必须计入；
- **漂移**：`api/kinematics.json` 必须等于真相源现算结果。

变异对照已实测：把可动关节类型清空 → 8 处判红；让引擎永远返回 `computed` → 14 处判红；
还原后复绿。**闸门是承重的。**

> 顺带记一个真 bug：自测里 `check(name, cond, detail)` 的 `detail` 传了 list，
> 只在**判红分支**做字符串拼接时才炸（绿路径永远掩盖它）。已修为统一 `str()`。
> 这正是「只测绿路径」的典型陷阱——变异对照是把它逼出来的唯一手段。

## 落地清单

| 文件 | 角色 |
|---|---|
| `kinematics/source.json` | 唯一真相源（链拓扑 + 出处白名单 + 探测距离） |
| `scripts/build_kinematics.py` | 生成器 → `api/kinematics.json`（幂等、无时间戳、`--check` 防漂移） |
| `scripts/verify_kinematics.py` | 阴阳自测 + 漂移闸门 |
| `api/kinematics.json` | 对外产物（含 `meta.access` 领 key 入口、`meta.honest_limits` 边界） |
| `scripts/ci_gate.py` | 第 21 项闸门 |

## 下一步（按 ROI）

1. **补 `link_mm`**：这也是「机械声明率 5.75%」缺口的一部分——运动学元数据与机械接口
   声明可以同一批来源一起补，边际成本低。
2. **补 `joint_limits_deg`**：有了限位才能从「上界」升级为真正的可达判定。
3. **升格为 MCP 工具**（`check_kinematic_reach`）：需同步 `mcp.js TOOLS` →
   `skills.meta.json` → `read_metrics.py` 的 `BUSINESS_TOOLS`，再跑 `gen_skills_manifest.mjs`。
   本轮**刻意不做**，以控制爆炸半径。
4. 若将来需要完整 IK：pyRoki 只能在**旁挂服务**（ECS 上的 Python 侧）跑，
   边缘端只读预计算产物——不要试图把它塞进 Workers。
