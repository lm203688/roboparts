// RoboParts 法兰转接板示例 (ISO9409-1-A50-4-M6 ↔ ISO9409-1-A80-6-M8)
// 由 https://roboparts.cc/adapter-generator 生成 · 开源可改
// 用 OpenSCAD 打开：openscad example_adapter.scad  →  F6 预览  →  F7 导出 STL
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
  pins(22.0, 2, 3.00, 12.00);
  // 侧B 螺栓孔
  bolt_circle(80.00, 4, 4.25, 12.00);
  // 侧B 定位销孔
  pins(38.0, 2, 4.00, 12.00);
  // 中心通孔
  cylinder(r=10.00, h=12.00, $fn=64, center=true);
}
