// RoboParts 法兰转接板示例 (ISO9409-1-A50-4-M6 ↔ ISO9409-1-A80-6-M8)
// 由 https://roboparts.cc/adapter-generator 生成 · 开源可改
// 用 OpenSCAD 打开：openscad example_adapter.scad  →  F6 预览  →  F7 导出 STL
// 【2026-11-01 R1 数据漂移闭环】旧版此文件 A80 误写 4 孔、pin_pcd 22/38（主版/裁决库
// 权威值 A50 pin_pcd=63、A80=6 孔 pin_pcd=100）。已同步：A80 改 6 孔、pin_pcd 63/100。
outer_d = 116.00;
thickness = 10;

module bolt_circle(pcd, n, r, h){
  for(i=[0:n-1]) rotate([0,0,i*(360/n)]) translate([pcd/2,0,0]) cylinder(r=r,h=h,$fn=32,center=true);
}
module pins(pcd, n, r, h){ if(n>0) for(i=[0:n-1]) rotate([0,0,i*180]) translate([pcd/2,0,0]) cylinder(r=r,h=h,$fn=32,center=true);
}

difference(){
  cylinder(r=outer_d/2, h=thickness, $fn=128, center=true);
  // 侧A 螺栓孔
  bolt_circle(50.00, 4, 3.25, 12.00);
  // 侧A 定位销孔
  pins(63.0, 2, 3.00, 12.00);
  // 侧B 螺栓孔（ISO9409-1-A80-6-M8：6 孔）
  bolt_circle(80.00, 6, 4.25, 12.00);
  // 侧B 定位销孔
  pins(100.0, 2, 4.00, 12.00);
  // 中心通孔
  cylinder(r=10.00, h=12.00, $fn=64, center=true);
}
