// W2 mechanical-category seed entities (real, verified public sources).
// Appends 19 entities to api/entities.json and refreshes meta counts.
// No fabricated specs: only verified facts from vendor product pages.
const fs = require('fs');
const path = require('path');

const ENT = 'api/entities.json';
const raw = fs.readFileSync(ENT, 'utf8');
const doc = JSON.parse(raw);
const ents = doc.entities;

const baseMI = () => ({
  verified: false,
  data_quality: 'ok',
  quarantine: false,
  standard_conformance: { assessed: false },
  mechanical_interface: {
    status: 'not_declared',
    mount_type: 'unknown',
    standard: null,
    flange: null,
    confidence: 0,
    registry_ref: '/api/mechanical_interfaces.json',
    gap: '厂商未公开或尚未采集机械安装接口规格'
  },
  entity_kind: 'component'
});

const A = (tier) => tier === 'A';

const NEW = [
  // ---------- reducers ----------
  Object.assign(baseMI(), {
    id: 'RED-001', name: 'Harmonic Drive CSF/SHF Series', name_en: 'Harmonic Drive CSF/SHF Series',
    category: 'reducers', manufacturer: 'Harmonic Drive LLC', type: 'strain_wave_gear',
    description: 'Zero-backlash strain wave (harmonic) gears for robot joints; families include CSF, SHF, SHG, SHD and FHA integrated actuators. Made in USA/Japan/Germany, ISO 9001 / AS9100.',
    applications: ['humanoid', 'manipulator', 'semiconductor', 'medical', 'aerospace'],
    source: '厂商产品页：Harmonic Drive（gear-units 深链，已核验）',
    source_url: 'https://harmonicdrive.net/products/gear-units',
    source_tier: 'A', confidence: 0.7, confidence_basis: 'verified_product_page',
    needs_provenance: false,
    specs: { gear_type: 'strain wave (harmonic)', backlash: 'zero-backlash', families: ['CSF', 'SHF', 'SHG', 'SHD', 'FHA'] }
  }),
  Object.assign(baseMI(), {
    id: 'RED-002', name: 'Nabtesco RV Reducer', name_en: 'Nabtesco RV Reducer',
    category: 'reducers', manufacturer: 'Nabtesco', type: 'cycloidal_pin_reducer',
    description: 'Cycloidal pin-wheel precision reducer (RV) for industrial robot joints; high rigidity, compact, overload-resistant. Cited as ~60% global industrial-robot reducer share.',
    applications: ['industrial_robot', 'manipulator', 'humanoid'],
    source: '厂商产品页：Nabtesco（RV 介绍页，已核验）',
    source_url: 'https://www.nabtesco-motion.cn/cn/products/introduction/',
    source_tier: 'A', confidence: 0.7, confidence_basis: 'verified_product_page',
    needs_provenance: false,
    specs: { gear_type: 'cycloidal pin-wheel (RV)', rigidity: 'high', backlash: 'near-zero' }
  }),
  Object.assign(baseMI(), {
    id: 'RED-003', name: 'Leaderdrive 绿的谐波 Strain Wave Gears', name_en: 'Leaderdrive Strain Wave Gears',
    category: 'reducers', manufacturer: 'Leaderdrive (绿的谐波)', type: 'strain_wave_gear',
    description: 'China-listed (SSE STAR 688017) harmonic drive maker; 21 series incl. LCD/LCS/LHS/LHD for robot and humanoid joints; ISO 9001/14001.',
    applications: ['humanoid', 'manipulator', 'industrial_robot'],
    source: '厂商产品页：Leaderdrive（about 页，已核验）',
    source_url: 'https://www.leaderdrive.com/about.html',
    source_tier: 'A', confidence: 0.65, confidence_basis: 'verified_product_page',
    needs_provenance: false,
    specs: { gear_type: 'strain wave (harmonic)', series: ['LCD', 'LCS', 'LHS', 'LHD'], listing: 'SSE STAR 688017' }
  }),
  // ---------- controllers ----------
  Object.assign(baseMI(), {
    id: 'CTRL-001', name: 'ODrive Pro', name_en: 'ODrive Pro',
    category: 'controllers', manufacturer: 'ODrive Robotics', type: 'servo_motor_controller',
    description: 'High-performance BLDC/PMAC servo controller with FOC; torque/velocity/position/trajectory control; isolated CAN/CAN-FD, USB, UART, SPI/RS485 encoders.',
    applications: ['manipulator', 'exoskeleton', 'mobile_robot', 'humanoid'],
    source: '厂商产品页：ODrive（shop/odrive-pro 深链，已核验规格）',
    source_url: 'https://odriverobotics.com/shop/odrive-pro',
    source_tier: 'A', confidence: 0.8, confidence_basis: 'verified_product_page',
    needs_provenance: false,
    specs: { continuous_power: '3 kW', peak_power: '5 kW', voltage: '14-58 V (14S)', continuous_current: '70 A', control_modes: ['torque', 'velocity', 'position', 'trajectory'], interfaces: ['CAN/CAN-FD', 'USB', 'UART', 'SPI/RS485'], footprint: '51x64 mm' }
  }),
  Object.assign(baseMI(), {
    id: 'CTRL-002', name: 'CubeMars AK80-64', name_en: 'CubeMars AK80-64',
    category: 'controllers', manufacturer: 'CubeMars', type: 'integrated_actuator',
    description: 'Highly integrated robotic actuator: BLDC motor + 64:1 planetary reducer + driver + encoder; supports servo and MIT control modes; used in exoskeletons, cobot arms, legged robots.',
    applications: ['humanoid', 'quadruped', 'exoskeleton', 'cobot'],
    source: '厂商产品页：CubeMars（ak80-64 深链，已核验规格）',
    source_url: 'https://cubemars.com/cn/product/ak80-64-kv80-robotic-actuator.html',
    source_tier: 'A', confidence: 0.8, confidence_basis: 'verified_product_page',
    needs_provenance: false,
    specs: { peak_torque: '120 Nm', rated_torque: '48 Nm', reduction: '64:1 planetary', modes: ['servo', 'MIT'], integration: 'motor+reducer+driver+encoder' }
  }),
  Object.assign(baseMI(), {
    id: 'CTRL-003', name: 'Roboteq Motor Controller', name_en: 'Roboteq Motor Controller',
    category: 'controllers', manufacturer: 'Roboteq', type: 'motor_controller',
    description: 'Brushed/brushless DC motor controllers for mobile robots and AGVs; CAN, RS232, USB interfaces; single/dual channel drive.',
    applications: ['mobile_robot', 'AGV', 'cobot'],
    source: '厂商主页：Roboteq（根域名，未核验具体型号规格）',
    source_url: 'https://www.roboteq.com',
    source_tier: 'B', confidence: 0.5, confidence_basis: 'named_vendor_catalog',
    needs_provenance: true,
    specs: { type: 'brushed/brushless DC motor controller', interfaces: ['CAN', 'RS232', 'USB'] }
  }),
  // ---------- grippers ----------
  Object.assign(baseMI(), {
    id: 'GRIP-001', name: 'OnRobot 2FG7', name_en: 'OnRobot 2FG7',
    category: 'grippers', manufacturer: 'OnRobot', type: 'electric_parallel_gripper',
    description: 'Electric parallel gripper for tight spaces and demanding payloads; IP67, ISO Class 5 cleanroom certified; intelligent grip/lost-grip detection.',
    applications: ['machine_tending', 'material_handling', 'cleanroom'],
    source: '厂商产品页：OnRobot（en/products/2fg7 深链，已核验规格）',
    source_url: 'https://onrobot.com/en/products/2fg7',
    source_tier: 'A', confidence: 0.85, confidence_basis: 'verified_product_page',
    needs_provenance: false,
    specs: { payload: '11 kg', grip_force: '20-140 N', stroke: 'up to 73 mm', ip_rating: 'IP67', cleanroom: 'ISO Class 5', type: 'electric parallel' }
  }),
  Object.assign(baseMI(), {
    id: 'GRIP-002', name: 'Robotiq 2F-85', name_en: 'Robotiq 2F-85',
    category: 'grippers', manufacturer: 'Robotiq', type: 'adaptive_gripper',
    description: 'World best-selling adaptive 2-finger gripper for collaborative robots; internal/external parallel and encompassing grip; plug-and-play with major cobots.',
    applications: ['pick_and_place', 'machine_tending', 'assembly', 'quality_testing'],
    source: '厂商产品页：Robotiq（2f85-140 深链，已核验规格）',
    source_url: 'https://robotiq.com/products/2f85-140-adaptive-robot-gripper',
    source_tier: 'A', confidence: 0.85, confidence_basis: 'verified_product_page',
    needs_provenance: false,
    specs: { payload: '5 kg', stroke: '85 mm', grip_force: '20-235 N', power: '24 V, 2 A', cycles: '2,000,000', type: 'adaptive 2-finger' }
  }),
  Object.assign(baseMI(), {
    id: 'GRIP-003', name: 'SCHUNK EGP', name_en: 'SCHUNK EGP',
    category: 'grippers', manufacturer: 'SCHUNK', type: 'electric_parallel_gripper',
    description: 'Electric 2-finger parallel gripper for small components; brushless DC servo, IO-Link option, high cycle rate; compact for minimal interference contour.',
    applications: ['pick_and_place', 'assembly', 'electronics_handling', 'lab_automation'],
    source: '厂商产品页：SCHUNK（egp 系列深链，已核验规格）',
    source_url: 'https://schunk.com/gb_en/gripping-systems/series/egp/',
    source_tier: 'A', confidence: 0.8, confidence_basis: 'verified_product_page',
    needs_provenance: false,
    specs: { grip_force: '140-300 N (EGP40/60/64)', stroke: '6-10 mm', repeatability: '0.02 mm', interface: 'IO-Link / digital I/O', type: 'electric parallel' }
  }),
  Object.assign(baseMI(), {
    id: 'GRIP-004', name: 'DH Robotics 大寰 Electric Gripper', name_en: 'DH Robotics Electric Gripper',
    category: 'grippers', manufacturer: 'DH Robotics (大寰)', type: 'electric_gripper',
    description: 'China-based electric/servo gripper maker; AG series with force control and feedback; used in 3C, automotive and lab automation.',
    applications: ['machine_tending', '3c_assembly', 'lab_automation'],
    source: '厂商主页：DH Robotics（根域名，未核验具体型号规格）',
    source_url: 'http://dh-robotics.com/',
    source_tier: 'B', confidence: 0.55, confidence_basis: 'named_vendor_catalog',
    needs_provenance: true,
    specs: { type: 'electric/servo gripper', examples: ['AG-95', 'AG-160'], note: 'force control, real-time feedback' }
  }),
  // ---------- structural ----------
  Object.assign(baseMI(), {
    id: 'STR-001', name: 'MISUMI Aluminum Extrusion', name_en: 'MISUMI Aluminum Extrusion',
    category: 'structural', manufacturer: 'MISUMI', type: 'aluminum_extrusion',
    description: 'T-slot aluminum framing (5/6/8 series) with brackets and connectors; cut-to-length service; used for robot frames, enclosures and workstations.',
    applications: ['frame', 'enclosure', 'workstation', 'fixture'],
    source: '厂商产品页：MISUMI（铝合金型材详情页，已核验）',
    source_url: 'https://www.misumi.com.cn/vona2/detail/110302368740/',
    source_tier: 'A', confidence: 0.7, confidence_basis: 'verified_product_page',
    needs_provenance: false,
    specs: { type: 'T-slot aluminum extrusion', series: ['5', '6', '8'], material: 'A6N01S-T5 / 6063', customization: 'cut-to-length' }
  }),
  Object.assign(baseMI(), {
    id: 'STR-002', name: '80/20 T-slot Framing', name_en: '80/20 T-slot Framing',
    category: 'structural', manufacturer: '80/20 Inc', type: 'aluminum_extrusion',
    description: 'Modular T-slot aluminum framing system (fractional and metric profiles) for machine frames, guards and custom structures.',
    applications: ['frame', 'enclosure', 'guard', 'fixture'],
    source: '厂商主页：80/20（根域名，未核验具体型材编号）',
    source_url: 'https://8020.net',
    source_tier: 'B', confidence: 0.6, confidence_basis: 'named_vendor_catalog',
    needs_provenance: true,
    specs: { type: 'T-slot aluminum framing', profiles: 'fractional & metric' }
  }),
  Object.assign(baseMI(), {
    id: 'STR-003', name: 'item MB Building Kit', name_en: 'item MB Building Kit System',
    category: 'structural', manufacturer: 'item Industrietechnik', type: 'aluminum_profile_system',
    description: 'Aluminum profile and connector system (MB Building Kit) for machine frames, workstations and automation structures.',
    applications: ['frame', 'workstation', 'automation_structure'],
    source: '厂商主页：item（根域名，未核验具体型材编号）',
    source_url: 'https://www.item24.com',
    source_tier: 'B', confidence: 0.6, confidence_basis: 'named_vendor_catalog',
    needs_provenance: true,
    specs: { type: 'aluminum profile system', system: 'MB Building Kit' }
  }),
  // ---------- cables ----------
  Object.assign(baseMI(), {
    id: 'CAB-001', name: 'igus chainflex Robot Cable', name_en: 'igus chainflex Robot Cable',
    category: 'cables', manufacturer: 'igus', type: 'robot_cable',
    description: 'Continuous-flex cables and e-chain energy chains for multi-axis robots; CFROBOT series rated up to ±360°/m torsion; up to 4-year chainflex guarantee.',
    applications: ['robot_dress_pack', 'cable_chain', 'multi_axis'],
    source: '厂商产品页：igus（motor-cables 深链，已核验）',
    source_url: 'https://www.igus.com/cables/motor-cables',
    source_tier: 'A', confidence: 0.75, confidence_basis: 'verified_product_page',
    needs_provenance: false,
    specs: { type: 'continuous-flex robot cable', torsion: 'up to ±360°/m', system: 'e-chain energy chain', guarantee: 'up to 4 years', series: 'CFROBOT' }
  }),
  Object.assign(baseMI(), {
    id: 'CAB-002', name: 'LEONI Robot Cable', name_en: 'LEONI Robot Cable',
    category: 'cables', manufacturer: 'LEONI', type: 'robot_cable',
    description: 'Cable solutions for robotics: drag-chain and torsion-resistant designs for continuous-motion robot applications.',
    applications: ['robot_dress_pack', 'cable_chain'],
    source: '厂商主页：LEONI（根域名，未核验具体型号规格）',
    source_url: 'https://www.leoni.com',
    source_tier: 'B', confidence: 0.5, confidence_basis: 'named_vendor_catalog',
    needs_provenance: true,
    specs: { type: 'robot cable / drag-chain cable' }
  }),
  // ---------- power ----------
  Object.assign(baseMI(), {
    id: 'PWR-001', name: 'Tattu/Grepow Smart LiPo Battery', name_en: 'Tattu/Grepow Smart LiPo Battery',
    category: 'power', manufacturer: 'Tattu (Grepow)', type: 'smart_lipo_battery',
    description: 'Smart LiPo battery packs (6S/12S/14S/18S) with BMS and DroneCAN for drones/UGV/robotics; AS9100D aerospace-certified; up to 25C discharge.',
    applications: ['UGV', 'drone', 'mobile_robot', 'payload'],
    source: '厂商产品页：Grepow/Tattu（products 深链，已核验）',
    source_url: 'https://www.grepow.com/products.html',
    source_tier: 'A', confidence: 0.7, confidence_basis: 'verified_product_page',
    needs_provenance: false,
    specs: { type: 'smart LiPo battery', config: ['6S', '12S', '14S', '18S'], bms: 'yes', protocol: 'DroneCAN', cert: 'AS9100D', discharge: 'up to 25C' }
  }),
  Object.assign(baseMI(), {
    id: 'PWR-002', name: 'MEAN WELL Industrial PSU', name_en: 'MEAN WELL Industrial Power Supply',
    category: 'power', manufacturer: 'MEAN WELL', type: 'power_supply',
    description: 'Industrial switching power supplies (DIN-rail and enclosed) commonly used to power robot controllers and actuators.',
    applications: ['controller_power', 'actuator_power', 'enclosure'],
    source: '厂商主页：MEAN WELL（根域名，未核验具体型号规格）',
    source_url: 'https://www.meanwell.com',
    source_tier: 'B', confidence: 0.6, confidence_basis: 'named_vendor_catalog',
    needs_provenance: true,
    specs: { type: 'industrial power supply (SMPS)', form: 'DIN-rail / enclosed' }
  }),
  // ---------- pcb ----------
  Object.assign(baseMI(), {
    id: 'PCB-001', name: 'SimpleFOC Board', name_en: 'SimpleFOC Board',
    category: 'pcb', manufacturer: 'SimpleFOC', type: 'foc_driver_board',
    description: 'Open-source Field-Oriented-Control driver boards and Arduino SimpleFOC library for BLDC/PMSM motor control.',
    applications: ['bldc_control', 'actuator_control', 'prototyping'],
    source: '厂商主页：SimpleFOC（根域名，未核验具体板型）',
    source_url: 'https://www.simplefoc.com',
    source_tier: 'B', confidence: 0.6, confidence_basis: 'named_vendor_catalog',
    needs_provenance: true,
    specs: { type: 'FOC driver board / library', motor: 'BLDC/PMSM', open_source: 'yes', interface: 'Arduino/SPI' }
  }),
  Object.assign(baseMI(), {
    id: 'PCB-002', name: 'PCBWay Robotics PCB Fabrication', name_en: 'PCBWay Robotics PCB Fabrication',
    category: 'pcb', manufacturer: 'PCBWay', type: 'pcb_fabrication_service',
    description: 'PCB prototyping and assembly service for robot electronics: motor-driver boards, control PCBs, SMT and through-hole.',
    applications: ['driver_board', 'control_pcb', 'prototyping'],
    source: '厂商主页：PCBWay（根域名，未核验具体工艺规格）',
    source_url: 'https://www.pcbway.com',
    source_tier: 'B', confidence: 0.6, confidence_basis: 'named_vendor_catalog',
    needs_provenance: true,
    specs: { type: 'PCB fabrication & assembly service', capability: 'prototype to production, SMT' }
  })
];

// de-dup guard
const have = new Set(ents.map(e => e.id));
const fresh = NEW.filter(e => !have.has(e.id));
if (fresh.length !== NEW.length) {
  console.error('WARN: some ids already present, skipped:', NEW.length - fresh.length);
}
ents.push(...fresh);

// refresh meta counts
const meta = doc.meta;
const cc = meta.category_counts || {};
for (const e of fresh) cc[e.category] = (cc[e.category] || 0) + 1;
meta.category_counts = cc;
meta.total = ents.length;
meta.total_entities = ents.length;
if (!meta.categories || !meta.categories.includes('reducers')) {
  // keep whatever normalize sets; just note
}

fs.writeFileSync(ENT, JSON.stringify(doc, null, 2));
console.log('Appended', fresh.length, 'entities. New total =', ents.length);
const byCat = {};
for (const e of ents) byCat[e.category] = (byCat[e.category] || 0) + 1;
for (const c of ['reducers','controllers','grippers','structural','cables','power','pcb','integrated_joints'])
  console.log('  ', c, byCat[c] || 0);
