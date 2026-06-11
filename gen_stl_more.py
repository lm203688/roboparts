"""生成第二批STL转接件（12个新增设计）—— 扩充平台内容库"""

import math, os

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
    v = [(x1,y1,z1),(x2,y1,z1),(x2,y2,z1),(x1,y2,z1),
         (x1,y1,z2),(x2,y1,z2),(x2,y2,z2),(x1,y2,z2)]
    faces = [(0,1,2,(0,0,-1)),(0,2,3,(0,0,-1)),(4,6,5,(0,0,1)),(4,7,6,(0,0,1)),
             (0,4,5,(0,-1,0)),(0,5,1,(0,-1,0)),(2,6,7,(0,1,0)),(2,7,3,(0,1,0)),
             (0,3,7,(-1,0,0)),(0,7,4,(-1,0,0)),(1,5,6,(1,0,0)),(1,6,2,(1,0,0))]
    for a,b,c,n in faces:
        tri.append((n, [v[a], v[b], v[c]]))

def cyl(tri, cx, cy, z1, z2, r, seg=24):
    for i in range(seg):
        a1 = 2*math.pi*i/seg; a2 = 2*math.pi*(i+1)/seg
        c1,s1 = math.cos(a1),math.sin(a1); c2,s2 = math.cos(a2),math.sin(a2)
        x1o,y1o = cx+r*c1, cy+r*s1; x2o,y2o = cx+r*c2, cy+r*s2
        nx,ny = math.cos((a1+a2)/2), math.sin((a1+a2)/2)
        tri.append(((nx,ny,0), [(x1o,y1o,z1),(x2o,y2o,z1),(x2o,y2o,z2)]))
        tri.append(((nx,ny,0), [(x1o,y1o,z1),(x2o,y2o,z2),(x1o,y1o,z2)]))
        tri.append(((0,0,1), [(cx,cy,z2),(x1o,y1o,z2),(x2o,y2o,z2)]))
        tri.append(((0,0,-1), [(cx,cy,z1),(x2o,y2o,z1),(x1o,y1o,z1)]))

def ring(tri, cx, cy, z, r1, r2, seg=24):
    for i in range(seg):
        a1 = 2*math.pi*i/seg; a2 = 2*math.pi*(i+1)/seg
        p1i = (cx+r1*math.cos(a1), cy+r1*math.sin(a1), z)
        p1o = (cx+r2*math.cos(a1), cy+r2*math.sin(a1), z)
        p2i = (cx+r1*math.cos(a2), cy+r1*math.sin(a2), z)
        p2o = (cx+r2*math.cos(a2), cy+r2*math.sin(a2), z)
        tri.append(((0,0,1), [p1i,p1o,p2o]))
        tri.append(((0,0,1), [p1i,p2o,p2i]))

# ============================================================
# 13. ISO50法兰转ISO40法兰转接环
# 工业场景最常见: 大法兰臂装小法兰夹爪
# ============================================================
def gen_iso50_to_iso40():
    t = []
    # 大法兰侧 (ISO50, R25)
    cyl(t, 0, 0, 0, 6, 28, 32)
    # 过渡锥台
    for layer in range(4):
        z1 = 6 + layer; z2 = 7 + layer
        r1 = 28 - layer * 2; r2 = 28 - (layer+1) * 2
        cyl(t, 0, 0, z1, z2, r1, 24)
    # 小法兰侧 (ISO40, R22)
    cyl(t, 0, 0, 10, 14, 22, 32)
    # ISO50安装凸耳
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        cx, cy = 25*math.cos(rad), 25*math.sin(rad)
        box(t, cx-6, cy-4, 0, cx+6, cy+4, 4)
    # ISO40安装凸耳
    for angle in [45, 135, 225, 315]:
        rad = math.radians(angle)
        cx, cy = 18*math.cos(rad), 18*math.sin(rad)
        box(t, cx-5, cy-3, 10, cx+5, cy+3, 14)
    # 中心定位
    cyl(t, 0, 0, 6, 10, 8, 20)
    return t

# ============================================================
# 14. 舵机夹爪爪指套装 (完整平行爪)
# ============================================================
def gen_servo_claw():
    t = []
    # 底座
    box(t, -15, -8, 0, 15, 8, 6)
    # 舵机安装面
    box(t, -15, -10, 6, 15, 10, 10)
    # 舵机轴孔
    cyl(t, 0, 0, 6, 12, 5, 16)
    # 左爪导轨
    box(t, -15, -6, 6, -2, 6, 8)
    # 右爪导轨
    box(t, 2, -6, 6, 15, 6, 8)
    # 左爪手指
    box(t, -14, 8, 2, -3, 10, 6)
    box(t, -14, 8, 6, -3, 10, 40)
    cyl(t, -8.5, 9, 36, 42, 4, 12)
    # 右爪手指
    box(t, 3, 8, 2, 14, 10, 6)
    box(t, 3, 8, 6, 14, 10, 40)
    cyl(t, 8.5, 9, 36, 42, 4, 12)
    # 安装孔
    for x in [-10, 10]:
        cyl(t, x, 0, 0, 8, 2.5, 10)
    return t

# ============================================================
# 15. 画笔/工具夹持器 (教学演示用)
# ============================================================
def gen_mount_pen():
    t = []
    h = 5
    # 安装底板
    box(t, -12, -12, 0, 12, 12, h)
    # 4个安装孔凸台
    for x,y in [(-8,-8),(8,-8),(-8,8),(8,8)]:
        cyl(t, x, y, 0, h+1, 3, 10)
    # 笔夹持器 (圆柱)
    cyl(t, 0, 0, h, h+25, 8, 24)
    # 笔夹持器内部（锥形收缩）
    cyl(t, 0, 0, h+25, h+30, 6, 24)
    # 顶部紧固环
    cyl(t, 0, 0, h+22, h+25, 10, 24)
    # 侧螺丝孔
    box(t, 8, -2, h+20, 12, 2, h+24)
    return t

# ============================================================
# 16. 通用吸盘安装座
# ============================================================
def gen_adapter_suction():
    t = []
    h = 4
    # 安装底板
    cyl(t, 0, 0, 0, h, 18, 24)
    # 中心气管通道
    cyl(t, 0, 0, h, h+20, 4, 16)
    # 吸盘接口（法兰盘）
    cyl(t, 0, 0, h+16, h+20, 12, 20)
    # 吸盘裙边
    cyl(t, 0, 0, h+20, h+24, 14, 20)
    ring(t, 0, 0, h+20, 4, 14, 20)
    # 安装孔
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        cx, cy = 12*math.cos(rad), 12*math.sin(rad)
        cyl(t, cx, cy, 0, h+1, 2, 10)
    # 侧管接口
    box(t, 4, -18, h, 18, -12, h+6)
    cyl(t, 11, -15, h, h+6, 3, 10)
    return t

# ============================================================
# 17. 平面指尖 (适用于平行夹爪)
# ============================================================
def gen_finger_flat():
    t = []
    # 安装卡槽
    box(t, -8, -4, 0, 8, 4, 8)
    # 卡扣
    box(t, -8, -6, 0, 8, -4, 3)
    # 手指主体
    box(t, -6, 4, 0, 6, 8, 8)
    box(t, -6, 8, 4, 6, 40, 8)
    # 平面指尖
    box(t, -6, 36, 0, 6, 42, 8)
    # 安装孔
    cyl(t, 0, 2, 1, 5, 2.5, 10)
    # 指尖纹理槽（增加摩擦力）
    for y in range(16, 36, 4):
        box(t, -5, y, 8.1, 5, y+1, 8.3)
    return t

# ============================================================
# 18. 圆弧指尖 (适用于圆柱物体)
# ============================================================
def gen_finger_round():
    t = []
    # 安装卡槽
    box(t, -8, -4, 0, 8, 4, 8)
    box(t, -8, -6, 0, 8, -4, 3)
    # 手指主体
    box(t, -6, 4, 0, 6, 8, 8)
    box(t, -6, 8, 4, 6, 35, 8)
    # 圆弧指尖
    cyl(t, 0, 35, 4, 8, 8, 16)
    # 安装孔
    cyl(t, 0, 2, 1, 5, 2.5, 10)
    return t

# ============================================================
# 19. 小型控制器安装盒 (末端安装电子模块)
# ============================================================
def gen_adapter_elec_box():
    t = []
    h = 4
    # 安装底板
    box(t, -18, -18, 0, 18, 18, h)
    # 4个安装孔
    for x,y in [(-14,-14),(14,-14),(-14,14),(14,14)]:
        cyl(t, x, y, 0, h+1, 2.5, 10)
    # 盒体
    box(t, -16, -16, h, 16, 16, h+14)
    box(t, -15, -15, h+14, 15, 15, h+16)
    # 侧面开口（走线）
    box(t, -16, -4, h+4, -17, 4, h+10)
    # 内部支撑柱
    for x,y in [(-10,-10),(10,-10),(-10,10),(10,10)]:
        cyl(t, x, y, h, h+3, 2, 8)
    # 盖板（分开的，用螺丝固定）
    box(t, -14, -14, h+16, 14, 14, h+17)
    return t

# ============================================================
# 20. 弹性手指 (带弹簧槽的柔性手指)
# ============================================================
def gen_finger_spring():
    t = []
    # 安装部
    box(t, -8, -4, 0, 8, 4, 10)
    box(t, -8, -6, 0, 8, -4, 4)
    box(t, -8, 4, 8, 8, 6, 12)
    # 弹性段（薄壁设计）
    box(t, -5, 6, 4, 5, 30, 8)
    box(t, -4, 6, 8, 4, 30, 12)
    # 弹簧槽
    box(t, -2, 12, 8.1, 2, 24, 11.9)
    # 指尖
    cyl(t, 0, 30, 4, 12, 5, 14)
    # 安装孔
    cyl(t, 0, 0, 2, 6, 2.5, 10)
    return t

# ============================================================
# 21. 快锁销机构
# ============================================================
def gen_quick_lock_pin():
    t = []
    # 底座
    cyl(t, 0, 0, 0, 4, 15, 24)
    # 定位环
    cyl(t, 0, 0, 4, 6, 18, 24)
    ring(t, 0, 0, 4, 15, 18, 24)
    ring(t, 0, 0, 6, 15, 18, 24)
    # 弹簧容纳腔
    cyl(t, 0, 0, 6, 16, 6, 20)
    # 销体
    cyl(t, 0, 0, 16, 24, 5, 20)
    # 销头（球头）
    cyl(t, 0, 0, 22, 26, 7, 20)
    # 安装螺栓孔
    cyl(t, 0, 0, 0, -2, 3, 12)
    return t

# ============================================================
# 22. LED照明环 (末端视觉照明)
# ============================================================
def gen_mount_led_ring():
    t = []
    h = 3
    # 安装底板
    cyl(t, 0, 0, 0, h, 18, 24)
    # 4个安装孔
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        cx, cy = 12*math.cos(rad), 12*math.sin(rad)
        cyl(t, cx, cy, 0, h+1, 2, 10)
    # LED环支架
    cyl(t, 0, 0, h, h+4, 22, 24)
    ring(t, 0, 0, h, 18, 22, 24)
    # LED凹槽
    for i in range(12):
        angle = 2*math.pi*i/12
        cx, cy = 20*math.cos(angle), 20*math.sin(angle)
        cyl(t, cx, cy, h+1, h+3, 2, 8)
    # 线缆出口
    box(t, 4, 0, 0, 8, 4, h)
    cyl(t, 6, 2, -2, h+1, 2, 10)
    return t

# ============================================================
# 23. ISO50端盖保护罩 (保护法兰盘)
# ============================================================
def gen_endcap_iso50():
    t = []
    # 盖板
    cyl(t, 0, 0, 0, 3, 28, 32)
    # 凸缘（卡入法兰槽）
    cyl(t, 0, 0, 3, 6, 25, 24)
    ring(t, 0, 0, 3, 20, 25, 24)
    ring(t, 0, 0, 6, 20, 25, 24)
    # 中心标识凸台
    cyl(t, 0, 0, 0, -1, 8, 20)
    # O型圈槽
    ring(t, 0, 0, 6, 22, 24, 32)
    return t

# ============================================================
# 24. 螺丝刀/电动工具安装座
# ============================================================
def gen_mount_screwdriver():
    t = []
    h = 5
    # 安装底板
    cyl(t, 0, 0, 0, h, 20, 24)
    # 4个M6安装凸耳
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        cx, cy = 25*math.cos(rad), 25*math.sin(rad)
        box(t, cx-5, cy-4, 0, cx+5, cy+4, h+2)
    # 工具夹持筒
    cyl(t, 0, 0, h, h+30, 10, 24)
    # 筒壁加厚
    cyl(t, 0, 0, h, h+10, 12, 24)
    # 紧固夹缝（侧面切割）
    box(t, -12, -2, h+8, -9, 2, h+26)
    box(t, 9, -2, h+8, 12, 2, h+26)
    # 紧固螺丝位
    box(t, -14, 0, h+16, -9, 3, h+20)
    cyl(t, -11, 1.5, h+16, h+20, 2, 10)
    return t

# ============================================================
# 生成所有文件
# ============================================================
base = "e:/workbuddy/发明家/robot-parts-platform/stl"
os.makedirs(base, exist_ok=True)

generators = {
    'adapter-iso50-iso40': ('ISO50法兰转ISO40法兰转接环', gen_iso50_to_iso40),
    'adapter-servo-claw': ('舵机夹爪爪指套装', gen_servo_claw),
    'mount-pen-holder': ('画笔工具夹持器', gen_mount_pen),
    'adapter-suction-cup': ('通用真空吸盘安装座', gen_adapter_suction),
    'gripper-finger-flat': ('平行夹爪平面指尖', gen_finger_flat),
    'gripper-finger-round': ('平行夹爪圆弧指尖', gen_finger_round),
    'adapter-elec-box': ('小型控制器安装盒', gen_adapter_elec_box),
    'gripper-finger-spring': ('弹性手指组件', gen_finger_spring),
    'adapter-quick-lock-pin': ('快锁销机构', gen_quick_lock_pin),
    'mount-led-ring': ('LED照明环安装座', gen_mount_led_ring),
    'endcap-iso50': ('ISO50法兰端盖保护罩', gen_endcap_iso50),
    'mount-screwdriver': ('螺丝刀工具安装座', gen_mount_screwdriver),
}

print("生成12个新STL文件...")
total = 0
for name, (desc, gen) in generators.items():
    tris = gen()
    path = f"{base}/{name}.stl"
    count = write_stl_ascii(path, tris)
    size_kb = os.path.getsize(path) / 1024
    total += count
    print(f"  [{desc}] {count}三角面, {size_kb:.1f}KB")

print(f"\n总计: {total}三角面, 12个新文件")
print("完成!")
