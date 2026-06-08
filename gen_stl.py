"""生成所有12个机器人夹爪转接件STL文件"""

import math
import os

def write_stl_ascii(filename, triangles):
    with open(filename, 'w') as f:
        f.write("solid adapter\n")
        for normal, verts in triangles:
            f.write(f"  facet normal {normal[0]:.6f} {normal[1]:.6f} {normal[2]:.6f}\n")
            f.write("    outer loop\n")
            for v in verts:
                f.write(f"      vertex {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")
        f.write("endsolid adapter\n")
    return len(triangles)

def box(tri, x1, y1, z1, x2, y2, z2):
    v = [
        (x1,y1,z1),(x2,y1,z1),(x2,y2,z1),(x1,y2,z1),
        (x1,y1,z2),(x2,y1,z2),(x2,y2,z2),(x1,y2,z2)
    ]
    faces = [
        (0,1,2,(0,0,-1)),(0,2,3,(0,0,-1)),
        (4,6,5,(0,0,1)),(4,7,6,(0,0,1)),
        (0,4,5,(0,-1,0)),(0,5,1,(0,-1,0)),
        (2,6,7,(0,1,0)),(2,7,3,(0,1,0)),
        (0,3,7,(-1,0,0)),(0,7,4,(-1,0,0)),
        (1,5,6,(1,0,0)),(1,6,2,(1,0,0)),
    ]
    for a,b,c,n in faces:
        tri.append((n, [v[a], v[b], v[c]]))

def cyl(tri, cx, cy, z1, z2, r, seg=24):
    for i in range(seg):
        a1 = 2*math.pi*i/seg
        a2 = 2*math.pi*(i+1)/seg
        c1,s1 = math.cos(a1),math.sin(a1)
        c2,s2 = math.cos(a2),math.sin(a2)
        x1o,y1o = cx+r*c1, cy+r*s1
        x2o,y2o = cx+r*c2, cy+r*s2
        nx,ny = math.cos((a1+a2)/2), math.sin((a1+a2)/2)
        tri.append(((nx,ny,0), [(x1o,y1o,z1),(x2o,y2o,z1),(x2o,y2o,z2)]))
        tri.append(((nx,ny,0), [(x1o,y1o,z1),(x2o,y2o,z2),(x1o,y1o,z2)]))
        tri.append(((0,0,1), [(cx,cy,z2),(x1o,y1o,z2),(x2o,y2o,z2)]))
        tri.append(((0,0,-1), [(cx,cy,z1),(x2o,y2o,z1),(x1o,y1o,z1)]))

def ring(tri, cx, cy, z, r1, r2, seg=24):
    """环形平面（用于法兰盘）"""
    for i in range(seg):
        a1 = 2*math.pi*i/seg
        a2 = 2*math.pi*(i+1)/seg
        p1i = (cx+r1*math.cos(a1), cy+r1*math.sin(a1), z)
        p1o = (cx+r2*math.cos(a1), cy+r2*math.sin(a1), z)
        p2i = (cx+r1*math.cos(a2), cy+r1*math.sin(a2), z)
        p2o = (cx+r2*math.cos(a2), cy+r2*math.sin(a2), z)
        tri.append(((0,0,1), [p1i,p1o,p2o]))
        tri.append(((0,0,1), [p1i,p2o,p2i]))

# ============================================================
# 1. ISO50法兰转M4转接板
# ============================================================
def gen_iso50_to_m4():
    t = []
    h = 5
    box(t, -25,-25,0, 25,25,h)
    # 4个ISO50 M6安装凸耳 (PCD 50mm)
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        cx, cy = 25*math.cos(rad), 25*math.sin(rad)
        box(t, cx-6, cy-4, 0, cx+6, cy+4, h+3)
    # M4侧安装凸台
    box(t, -12, 8, h, 12, 22, h+4)
    # 中心M8定位台阶
    cyl(t, 0, 0, h, h+6, 6, 20)
    return t

# ============================================================
# 2. ISO40法兰转M4转接板
# ISO40: 4x M4安装孔, PCD 36mm
# ============================================================
def gen_iso40_to_m4():
    t = []
    h = 4
    # 圆形底板
    cyl(t, 0, 0, 0, h, 22, 32)
    # 4个M4安装凸耳 (PCD 36mm)
    for angle in [45, 135, 225, 315]:
        rad = math.radians(angle)
        cx, cy = 18*math.cos(rad), 18*math.sin(rad)
        box(t, cx-5, cy-3, h, cx+5, cy+3, h+3)
    # M4输出侧凸台
    box(t, -10, 6, h, 10, 18, h+3)
    # 中心M6台阶
    cyl(t, 0, 0, h, h+5, 4.5, 16)
    return t

# ============================================================
# 3. ISO50法兰转舵机支架 (MG996R)
# ============================================================
def gen_iso50_to_servo():
    t = []
    h = 6
    cyl(t, 0, 0, 0, h, 28, 32)
    box(t, -12, -20, h, 12, 20, h+8)
    box(t, -11, -22, h+8, 11, 22, h+12)
    cyl(t, 0, -18, h+12, h+18, 5, 16)
    return t

# ============================================================
# 4. M4接口转舵机支架
# uArm/LoFi的M4法兰接MG996R舵机
# ============================================================
def gen_m4_to_servo():
    t = []
    h = 5
    # M4侧底座
    cyl(t, 0, 0, 0, h, 14, 24)
    # 4个M4安装孔凸台 (PCD 22mm)
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        cx, cy = 11*math.cos(rad), 11*math.sin(rad)
        box(t, cx-4, cy-3, 0, cx+4, cy+3, h+2)
    # 舵机安装臂
    box(t, -10, 4, h, 10, 28, h+6)
    box(t, -9, 6, h+6, 9, 28, h+10)
    # 舵机轴孔
    cyl(t, 0, 24, h+10, h+16, 4, 14)
    return t

# ============================================================
# 5. 双夹爪安装板
# ============================================================
def gen_dual_gripper():
    t = []
    h = 6
    box(t, -30, -15, 0, 30, 15, h)
    cyl(t, 0, 0, h, h+8, 12, 24)
    # 左右夹爪安装区
    for side in [1, -1]:
        box(t, side*12, -10, 0, side*30, 10, h+3)
        for dx in [8, 14]:
            cyl(t, side*dx, 0, h+3, h+7, 3, 12)
    return t

# ============================================================
# 6. 线缆拖链安装支架
# 在机械臂末端安装小型拖链
# ============================================================
def gen_cable_chain():
    t = []
    h = 5
    # 主板
    box(t, -20, -25, 0, 20, 25, h)
    # ISO50中心安装区
    cyl(t, 0, 0, 0, h, 12, 20)
    # 拖链安装槽（C形托架）
    box(t, -8, 10, h, 8, 30, h+4)
    box(t, -10, 12, h+4, 10, 28, h+8)
    # 侧面挡板
    box(t, -12, 10, h, -8, 30, h+8)
    box(t, 8, 10, h, 12, 30, h+8)
    # 安装孔凸台
    for y in [15, 25]:
        cyl(t, -10, y, h+8, h+10, 2, 10)
        cyl(t, 10, y, h+8, h+10, 2, 10)
    return t

# ============================================================
# 7. 被动式快换接头（球头定位）
# ============================================================
def gen_tool_changer():
    t = []
    h = 10
    # 主动板（装在机器人上）
    cyl(t, 0, 0, 0, h/2, 20, 32)
    # 中心定位销
    cyl(t, 0, 0, h/2, h/2+6, 8, 20)
    # 4个球头安装位
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        cx, cy = 15*math.cos(rad), 15*math.sin(rad)
        cyl(t, cx, cy, h/2-1, h/2+4, 4, 12)
    # 周边凸缘
    cyl(t, 0, 0, 0, 0, 24, 32)  # 法兰盘
    return t

# ============================================================
# 8. uArm通用夹爪安装座
# uArm Swift Pro: M4法兰
# ============================================================
def gen_uarm_gripper():
    t = []
    h = 5
    # uArm M4安装底座
    cyl(t, 0, 0, 0, h, 12, 20)
    # 4个M4安装孔
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        cx, cy = 8*math.cos(rad), 8*math.sin(rad)
        box(t, cx-4, cy-3, 0, cx+4, cy+3, h+2)
    # 通用夹爪安装板（大尺寸）
    box(t, -15, 5, h, 15, 30, h+4)
    # 多排安装孔（M3间距）
    for y in [10, 18, 26]:
        for x in [-8, 0, 8]:
            cyl(t, x, y, h+4, h+6, 1.8, 8)
    return t

# ============================================================
# 9. 可定制手指组件
# 模块化夹爪手指，带安装卡扣
# ============================================================
def gen_gripper_jaw():
    t = []
    # L形手指
    h = 4
    # 安装部（卡入夹爪槽）
    box(t, -8, -3, 0, 8, 3, 20)
    # 卡扣凸起
    box(t, -8, -5, 0, 8, -3, 3)
    box(t, -8, 3, 14, 8, 5, 17)
    # 手指部（向下延伸）
    box(t, -6, 0, 14, 6, 4, 20)
    box(t, -6, 0, 20, 6, 3, 50)
    # 指尖圆弧过渡
    cyl(t, 0, 1.5, 44, 54, 6, 12)
    # 安装孔
    cyl(t, 0, 0, 2, 6, 2.5, 10)
    return t

# ============================================================
# 10. myCobot舵机转接板
# Elephant myCobot 280: M4法兰
# ============================================================
def gen_elephant_servo():
    t = []
    h = 4
    # myCobot M4底座
    cyl(t, 0, 0, 0, h, 10, 18)
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        cx, cy = 6*math.cos(rad), 6*math.sin(rad)
        box(t, cx-3, cy-2, 0, cx+3, cy+2, h+2)
    # 舵机安装面
    box(t, -10, 5, h, 10, 25, h+5)
    box(t, -9, 7, h+5, 9, 25, h+9)
    # 舵机轴孔
    cyl(t, 0, 20, h+9, h+14, 4, 14)
    return t

# ============================================================
# 11. 夹爪集成摄像头安装座
# 侧面安装微型摄像头
# ============================================================
def gen_mount_camera():
    t = []
    h = 5
    # 夹爪连接板
    box(t, -12, -15, 0, 12, 15, h)
    # 4个安装孔
    for x,y in [(-8,-10),(8,-10),(-8,10),(8,10)]:
        box(t, x-2, y-2, 0, x+2, y+2, h+1)
    # 摄像头安装臂（侧面伸出）
    box(t, 12, -5, 0, 25, 5, h+3)
    box(t, 12, -4, h+3, 24, 4, h+6)
    # 摄像头座（圆柱形，适配标准摄像头模块）
    cyl(t, 18, 0, h+6, h+10, 6, 14)
    # 摄像头镜头孔
    cyl(t, 18, 0, h+10, h+12, 3, 12)
    return t

# ============================================================
# 12. NEMA17步进电机安装板
# ISO50法兰安装NEMA17电机
# ============================================================
def gen_nema17():
    t = []
    h = 6
    # ISO50底板
    cyl(t, 0, 0, 0, h, 28, 32)
    # 过渡连接部
    box(t, -14, 0, h, 14, 16, h+4)
    # NEMA17安装面 (42.3mm x 42.3mm → 简化为21x21)
    box(t, -21, 10, h+4, 21, 32, h+8)
    # 4个NEMA17安装孔 (PCD 31mm)
    for x,y in [(-15.5, 16), (15.5, 16), (-15.5, 26), (15.5, 26)]:
        cyl(t, x, y, h+8, h+11, 2, 12)
    # 电机轴孔
    cyl(t, 0, 21, h+8, h+14, 11, 20)
    # 中心定位台阶
    cyl(t, 0, 21, h+8, h+12, 5, 16)
    return t

# ============================================================
# 生成所有文件
# ============================================================
base = "e:/workbuddy/发明家/robot-parts-platform/stl"
os.makedirs(base, exist_ok=True)

generators = {
    'adapter-iso50-m4': ('ISO50法兰转M4转接板', gen_iso50_to_m4),
    'adapter-iso40-m4': ('ISO40法兰转M4转接板', gen_iso40_to_m4),
    'adapter-iso50-servo': ('ISO50法兰转舵机支架', gen_iso50_to_servo),
    'adapter-m4-servo': ('M4接口转舵机支架', gen_m4_to_servo),
    'adapter-dual-gripper': ('双夹爪安装板', gen_dual_gripper),
    'adapter-cable-chain': ('线缆拖链安装支架', gen_cable_chain),
    'tool-changer-passive': ('被动式快换接头', gen_tool_changer),
    'adapter-uarm-gripper': ('uArm通用夹爪安装座', gen_uarm_gripper),
    'gripper-jaw-custom': ('可定制手指组件', gen_gripper_jaw),
    'adapter-elephant-servo': ('myCobot舵机转接板', gen_elephant_servo),
    'mount-camera': ('夹爪集成摄像头安装座', gen_mount_camera),
    'adapter-nema17': ('NEMA17步进电机安装板', gen_nema17),
}

print("生成12个STL文件...")
total = 0
for name, (desc, gen) in generators.items():
    tris = gen()
    path = f"{base}/{name}.stl"
    count = write_stl_ascii(path, tris)
    size_kb = os.path.getsize(path) / 1024
    total += count
    print(f"  [{desc}] {count}三角面, {size_kb:.1f}KB")

print(f"\n总计: {total}三角面, 12个文件")
print("完成!")
