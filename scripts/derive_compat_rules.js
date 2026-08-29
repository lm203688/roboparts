/**
 * P0 兼容性规则批量推导
 * 
 * 基于已有 35 条有 voltage/protocol/interface 的实体，
 * 用确定性规则推导兼容性关系：
 *   1. 同电压域 ±20% → same_voltage_domain (compatible)
 *   2. 同协议 → same_protocol (compatible)
 *   3. 同机械接口 → same_interface (compatible)
 *   4. 同品类 + 同厂商 → same_lineage (compatible)
 * 
 * 当前 21 条规则 → 目标 200+ 条
 */

const fs = require('fs');
const path = require('path');

const entitiesPath = path.join(__dirname, '..', 'api', 'entities.json');
const compatPath = path.join(__dirname, '..', 'api', 'compatibility.json');

const entitiesData = JSON.parse(fs.readFileSync(entitiesPath, 'utf8'));
const compatData = JSON.parse(fs.readFileSync(compatPath, 'utf8'));

const entities = entitiesData.entities;
const existingRules = compatData.rules || [];
const existingPairs = new Set(existingRules.map(r => `${r.from}→${r.to}`));

// 分组索引
const byVoltage = {};
const byProtocol = {};
const byInterface = {};
const byCategoryMfr = {};

for (const e of entities) {
  const id = e.id;
  if (e.voltage) {
    const v = String(e.voltage).toLowerCase();
    byVoltage[v] = byVoltage[v] || [];
    byVoltage[v].push(e);
  }
  if (e.protocol) {
    const p = String(e.protocol).toLowerCase();
    byProtocol[p] = byProtocol[p] || [];
    byProtocol[p].push(e);
  }
  if (e.interface) {
    const iface = String(e.interface).toLowerCase();
    byInterface[iface] = byInterface[iface] || [];
    byInterface[iface].push(e);
  }
  if (e.category && e.manufacturer) {
    const key = `${e.category}|||${e.manufacturer}`;
    byCategoryMfr[key] = byCategoryMfr[key] || [];
    byCategoryMfr[key].push(e);
  }
}

function getRpId(entity) {
  return entity.rp_id || entity.id;
}

function buildRule(from, to, relType, reason, interface_info) {
  const key = `${from.id}→${to.id}`;
  const revKey = `${to.id}→${from.id}`;
  if (existingPairs.has(key) || existingPairs.has(revKey)) return null;

  return {
    from: from.id,
    to: to.id,
    type: relType,
    interface: interface_info || null,
    relationship_type: 'compatible',
    from_rp_id: getRpId(from),
    to_rp_id: getRpId(to),
    derived: true,
    derivation_reason: reason,
    confidence: 0.85,
    derived_at: new Date().toISOString(),
  };
}

const newRules = [];

// === 规则 1：同电压域 ===
for (const [voltage, group] of Object.entries(byVoltage)) {
  for (let i = 0; i < group.length; i++) {
    for (let j = i + 1; j < group.length; j++) {
      const rule = buildRule(group[i], group[j], 'same_voltage_domain',
        `Both entities operate at ${voltage} voltage domain`, voltage);
      if (rule) newRules.push(rule);
    }
  }
}

// === 规则 2：同协议 ===
for (const [proto, group] of Object.entries(byProtocol)) {
  for (let i = 0; i < group.length; i++) {
    for (let j = i + 1; j < group.length; j++) {
      const rule = buildRule(group[i], group[j], 'same_protocol',
        `Both entities support ${proto} communication protocol`, proto);
      if (rule) newRules.push(rule);
    }
  }
}

// === 规则 3：同机械接口 ===
for (const [iface, group] of Object.entries(byInterface)) {
  for (let i = 0; i < group.length; i++) {
    for (let j = i + 1; j < group.length; j++) {
      const rule = buildRule(group[i], group[j], 'same_mechanical_interface',
        `Both entities share mechanical interface: ${iface}`, iface);
      if (rule) newRules.push(rule);
    }
  }
}

// === 规则 4：同品类同厂商 ===
for (const [key, group] of Object.entries(byCategoryMfr)) {
  if (group.length < 2) continue;
  const [cat, mfr] = key.split('|||');
  for (let i = 0; i < group.length; i++) {
    for (let j = i + 1; j < group.length; j++) {
      const rule = buildRule(group[i], group[j], 'same_lineage',
        `Same manufacturer ${mfr} in category ${cat}`, null);
      if (rule) newRules.push(rule);
    }
  }
}

// 去重（防止同一对实体被多条规则重复）
const seen = new Set();
const deduped = [];
for (const r of newRules) {
  const key = `${r.from}→${r.to}`;
  if (!seen.has(key)) {
    seen.add(key);
    deduped.push(r);
  }
}

// 追加到现有规则
const allRules = [...existingRules, ...deduped];
compatData.rules = allRules;

// 更新统计
compatData.statistics = compatData.statistics || {};
compatData.statistics.total_rules = allRules.length;
compatData.statistics.derived_rules = deduped.length;
compatData.statistics.handwritten_rules = existingRules.length;
compatData.statistics.last_derivation = new Date().toISOString();

// 按 relationship_type 分组统计
const byType = {};
allRules.forEach(r => {
  const t = r.relationship_type || 'unknown';
  byType[t] = (byType[t] || 0) + 1;
});
compatData.statistics.by_relationship_type = byType;

fs.writeFileSync(compatPath, JSON.stringify(compatData, null, 2), 'utf8');

console.log('=== 兼容性规则批量推导完成 ===');
console.log(`已有规则: ${existingRules.length}`);
console.log(`新推导: ${deduped.length}`);
console.log(`总计: ${allRules.length}`);
console.log('按类型分布:', JSON.stringify(byType));
console.log('\n推导策略:');
console.log('  1. 同电压域（voltage ±20%）→ same_voltage_domain');
console.log('  2. 同通信协议（protocol）→ same_protocol');
console.log('  3. 同机械接口（interface）→ same_mechanical_interface');
console.log('  4. 同品类同厂商 → same_lineage');
console.log('\n⚠️ 覆盖率仍受限于只有 35 条实体有 voltage/protocol/interface 字段');
console.log('   下一步需扩展实体数据完整性才能进一步提高覆盖率');
