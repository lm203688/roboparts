/**
 * P2 数据去重 + entities.json 设为唯一事实源
 * 
 * 将 data.json 和 graph.json 转为 entities.json 的 build 产物，
 * 消除"同一事实存多处"的不一致风险。
 */

const fs = require('fs');
const path = require('path');

const baseDir = path.join(__dirname, '..', 'api');
const entitiesData = JSON.parse(fs.readFileSync(path.join(baseDir, 'entities.json'), 'utf8'));
const entities = entitiesData.entities;

// === 生成 data.json（扁平投影，无 meta） ===
const dataFlat = entities.map(e => ({
  id: e.id,
  rp_id: e.rp_id,
  name: e.name,
  name_en: e.name_en,
  category: e.category,
  manufacturer: e.manufacturer,
  type: e.type,
  voltage: e.voltage,
  protocol: e.protocol,
  interface: e.interface,
  entity_kind: e.entity_kind,
  source_tier: e.source_tier,
  confidence: e.confidence,
  verified: e.verified,
}));

const dataJson = {
  meta: {
    generated_from: 'entities.json',
    generated_at: new Date().toISOString(),
    entity_count: entities.length,
    note: 'Read-only projection of entities.json. Do NOT edit directly.',
  },
  count: entities.length,
  data: dataFlat,
};
fs.writeFileSync(path.join(baseDir, 'data.json'), JSON.stringify(dataJson, null, 2), 'utf8');
console.log('✅ data.json: 已从 entities.json 重新生成（' + entities.length + ' 条）');

// === 生成 graph.json（关系投影） ===
const compatData = JSON.parse(fs.readFileSync(path.join(baseDir, 'compatibility.json'), 'utf8'));
const edges = (compatData.rules || []).map(r => ({
  from: r.from_rp_id || r.from,
  to: r.to_rp_id || r.to,
  type: r.relationship_type || 'compatible',
  derived: r.derived || false,
  confidence: r.confidence || 0.85,
}));

const graphJson = {
  meta: {
    generated_from: 'entities.json + compatibility.json',
    generated_at: new Date().toISOString(),
    node_count: entities.length,
    edge_count: edges.length,
    note: 'Read-only graph projection. Do NOT edit directly.',
  },
  nodes: entities.map(e => ({
    id: e.rp_id || e.id,
    label: e.name || e.name_en || e.id,
    category: e.category,
    manufacturer: e.manufacturer,
    entity_kind: e.entity_kind,
  })),
  edges: edges,
};
fs.writeFileSync(path.join(baseDir, 'graph.json'), JSON.stringify(graphJson, null, 2), 'utf8');
console.log('✅ graph.json: 已从 entities.json + compatibility.json 重新生成');
console.log('   节点:', entities.length, ' 边:', edges.length);

// === 添加只读标记到 entities.json meta ===
entitiesData.meta = entitiesData.meta || {};
entitiesData.meta.canonical_source = true;
entitiesData.meta.canonical_note = 'entities.json is the SINGLE SOURCE OF TRUTH. data.json and graph.json are generated projections.';
entitiesData.meta.projection_generated_at = new Date().toISOString();
fs.writeFileSync(path.join(baseDir, 'entities.json'), JSON.stringify(entitiesData, null, 2), 'utf8');
console.log('✅ entities.json: 已标记为 canonical source');

console.log('\n=== P2 数据去重完成 ===');
console.log('data.json 和 graph.json 已转为 build 产物，禁止手动编辑');
