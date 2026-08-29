#!/usr/bin/env node
/**
 * 5-category entity_kind migration + meta field fix
 * Regression expects: component / organization / specification / software / market_intelligence
 * Current data has: type / standard (2-category from enhance_p2.py)
 *
 * Mapping logic (from regression L1.68 sample expectations):
 *   protocols → specification
 *   interfaces (pure spec, no vendor) → specification
 *   llms / robot_ai_models → software
 *   bionic_mechanisms → organization (market_intelligence if it's a company)
 *   everything else (actuators, sensors, chips, platforms, data_acquisition,
 *   flexible_actuators, connectors, reducers, controllers, grippers, structural,
 *   cables, power, pcb, integrated_joints) → component
 *   RP-STD-* prefix → specification (standards)
 */
const fs = require('fs');
const path = 'api/entities.json';
const e = JSON.parse(fs.readFileSync(path, 'utf8'));
const ents = e.entities;

// 5-category mapping
function mapEntityKind(ent) {
  const rpId = ent.rp_id || '';
  const category = ent.category || '';
  const name = ent.name || '';
  const type = ent.type || '';
  const entityType = (ent.entity_type || '').toLowerCase();

  // Standards: RP-STD-* or category=interfaces with standard-like naming
  if (rpId.startsWith('RP-STD-')) {
    return 'specification';
  }

  // Protocols → specification (EtherCAT, CAN, etc.)
  if (category === 'protocols') {
    return 'specification';
  }

  // Interfaces: check if it's a spec or a physical connector
  if (category === 'interfaces') {
    // Pure spec interfaces (USB 3.0, CAN bus, etc.)
    const specKeywords = ['usb', 'can', 'rs', 'ieee', 'ethernet', 'tcp', 'ip', 'protocol'];
    const typeLower = type.toLowerCase();
    const nameLower = name.toLowerCase();
    if (specKeywords.some(k => typeLower.includes(k) || nameLower.includes(k))) {
      return 'specification';
    }
    // Physical connectors stay as component
    if (ent.manufacturer) {
      return 'component';
    }
    return 'specification';
  }

  // LLMs and AI models → software
  if (['llms', 'robot_ai_models'].includes(category)) {
    return 'software';
  }

  // Bionic mechanisms: usually organizations (Figure AI, Boston Dynamics, etc.)
  if (category === 'bionic_mechanisms') {
    // Check if it's a company/organization
    const orgKeywords = ['ai', 'robot', 'inc', 'corp', 'tech', 'co.', 'ltd', 'group'];
    const typeLower = type.toLowerCase();
    const nameLower = name.toLowerCase();
    if (orgKeywords.some(k => typeLower.includes(k) || nameLower.includes(k))) {
      return 'organization';
    }
    // Check entity_type
    if (entityType === 'organization' || entityType === 'company') {
      return 'organization';
    }
    // Default for bionic_mechanisms: if it's a company, org; if it's a robot model, component
    // Conservative: if manufacturer field is empty (the entity IS the company), it's org
    if (!ent.manufacturer || ent.manufacturer === name) {
      return 'organization';
    }
    return 'component';
  }

  // Market intelligence (if entity_type says so)
  if (entityType === 'market_intelligence' || entityType === 'market') {
    return 'market_intelligence';
  }

  // Everything else → component
  return 'component';
}

let changed = 0;
ents.forEach(ent => {
  const old = ent.entity_kind;
  const newKind = mapEntityKind(ent);
  if (old !== newKind) {
    ent.entity_kind = newKind;
    if (!ent.entity_kind_basis) {
      ent.entity_kind_basis = '由 category + rp_id 前缀 + name/type 自动映射至 5 分类';
    }
    changed++;
  }
});

// Verify the sample entities
const samples = {
  'PROTO-001': 'specification',
  'IF-001': 'specification',
  'LLM-001': 'software',
  'RAI-001': 'software',
  'ACT-001': 'component'
};
ents.forEach(ent => {
  const id = ent.id || ent.rp_id || '';
  if (samples[id]) {
    const expected = samples[id];
    if (ent.entity_kind !== expected) {
      console.log('MISMATCH', id, 'got:', ent.entity_kind, 'expected:', expected);
    }
  }
});

// Now recalculate everything
const total = ents.length;
const kinds = {};
ents.forEach(x => { kinds[x.entity_kind] = (kinds[x.entity_kind]||0)+1; });
console.log('entity_kind distribution:', kinds);
console.log('changed:', changed);

// Update meta
const clean = ents.filter(x => !x.quarantine).length;
const realA = ents.filter(x => x.source_tier === 'A' && !x.quarantine).length;
const tierB = ents.filter(x => x.source_tier === 'B' && !x.quarantine).length;
const tierC = ents.filter(x => x.source_tier === 'C' && !x.quarantine).length;
const sourceCount = ents.filter(x => x.source).length;
const lastVerified = ents.filter(x => x.last_verified).length;
const verifiedTrue = ents.filter(x => x.verified === true).length;
const verifiedFalse = ents.filter(x => x.verified === false).length;

// mechanical_interface coverage
const declared = ents.filter(x => x.mechanical_interface?.status === 'declared').length;
const partial = ents.filter(x => x.mechanical_interface?.status === 'partial').length;
const not_declared = ents.filter(x => x.mechanical_interface?.status === 'not_declared').length;
const n_a = ents.filter(x => x.mechanical_interface?.status === 'n_a').length;

// breakdown
const breakdown = {};
ents.forEach(x => {
  const dq = typeof x.data_quality === 'string' ? x.data_quality : 'ok';
  breakdown[dq] = (breakdown[dq]||0)+1;
});

// facts counts for 5 categories
const kindCounts = {};
Object.keys(kinds).forEach(k => kindCounts[k + '_entities'] = kinds[k]);

const now = new Date().toISOString();

// Rebuild meta
e.meta.clean = clean;
e.meta.total = total;
e.meta.total_entities = total;
e.meta.tier_a_traceable = realA;
e.meta.traceable_pct = parseFloat((realA/total*100).toFixed(2));
e.meta.breakdown = breakdown;

e.meta.data_quality = {
  audited_at: now,
  total, clean, quarantined: total - clean,
  quarantine_pct: ((total-clean)/total*100).toFixed(2),
  breakdown,
  policy: 'quarantine=true 的条目不删除，前端默认不进选型结果',
  duplicate_policy: '同名同厂商的重复登记只保留一条规范条目，其余标 data_quality=duplicate + duplicate_of=<规范 id> 并隔离。',
  duplicates_resolved: e.meta.data_quality?.duplicates_resolved || []
};

e.meta.provenance_coverage = {
  source_pct: (sourceCount/total*100).toFixed(2),
  traceable_pct: parseFloat((realA/total*100).toFixed(2)),
  confidence_pct: 100,
  last_verified_pct: (lastVerified/total*100).toFixed(2),
  tier_a_traceable: realA,
  tier_b_attributable: tierB,
  tier_c_none: tierC,
  verified_true: verifiedTrue,
  verified_false: verifiedFalse,
  verify_threshold: 0.6,
  clean_set: {
    total: clean,
    source_pct: (ents.filter(x => x.source && !x.quarantine).length/clean*100).toFixed(2),
    traceable_pct: parseFloat((realA/clean*100).toFixed(2)),
    confidence_pct: 100,
    last_verified_pct: (ents.filter(x => x.last_verified && !x.quarantine).length/clean*100).toFixed(2),
  },
  tier_definition: {
    A: '可点开复核的一手来源（官方规格书/标准文本/带链接厂商文档）',
    B: '弱归因（厂商目录声明值、官网首页，无原始链接）',
    C: '无溯源（历史导入，待补来源，confidence 上限 0.30）'
  },
  tier_rule: 'source_tier 由证据形态推导，不由录入者自封。判据唯一源 scripts/govern_source_tier.py',
  total_clean: clean,
  total
};

e.meta.mechanical_interface_coverage = {
  total, declared, partial, not_declared, n_a,
  coupled_categories: ['actuators','sensors','platforms','flexible_actuators','connectors'],
  coupled_count: ents.filter(x => ['actuators','sensors','platforms','flexible_actuators','connectors'].includes(x.category)).length
};

e.meta.entity_kinds = kinds;
e.meta.entity_kinds.definition = {
  component: '型号/实例级条目（零部件型号、协议规范条目等）',
  specification: '规范/协议类条目（EtherCAT/USB/ISO 标准等）',
  software: '软件/模型类条目（GPT-4o/GR00T 等 AI 模型）',
  organization: '企业主体（Figure AI/波士顿动力 等公司）',
  market_intelligence: '市场情报/非实体信息'
};

// Write with newline
let s = JSON.stringify(e, null, 2);
if (!s.endsWith('\n')) s += '\n';
fs.writeFileSync(path, s, 'utf8');
console.log('entities.json updated');
console.log('kindCounts:', kindCounts);

// Now rebuild all derived files
// data.json
const dj = {meta:{generated_from:'entities.json',generated_at:now,entity_count:total,total_entities:total,note:'Read-only projection'},count:total,data:ents.map(x=>({...x}))};
fs.writeFileSync('api/data.json', JSON.stringify(dj, null, 2), 'utf8');

// graph.json
const compat = JSON.parse(fs.readFileSync('api/compatibility.json','utf8'));
const edges = (compat.rules||[]).map(r => ({from:r.from_rp_id||r.from,to:r.to_rp_id||r.to,type:r.relationship_type||'compatible',derived:r.derived||false,confidence:r.confidence||0.85}));
fs.writeFileSync('api/graph.json', JSON.stringify({meta:{generated_from:'entities.json + compatibility.json',generated_at:now,node_count:total,edge_count:edges.length},nodes:ents.map(x=>({id:x.rp_id||x.id,label:x.name||x.name_en||x.id,category:x.category,manufacturer:x.manufacturer,entity_kind:x.entity_kind})),edges}, null, 2), 'utf8');

// Category JSONs
Object.keys(e.meta.category_counts).forEach(cat => {
  const catEnts = ents.filter(x => x.category === cat);
  fs.writeFileSync('api/'+cat+'.json', JSON.stringify({meta:{category:cat,source:'entities.json projection',generated_at:now},count:catEnts.length,updated:now,data:catEnts}, null, 2), 'utf8');
});

// data.js
const db = { updated: now, stats: e.meta.category_counts };
Object.keys(e.meta.category_counts).forEach(cat => { db[cat] = ents.filter(x => x.category === cat); });
fs.writeFileSync('data.js', 'const DB = ' + JSON.stringify(db) + ';\n', 'utf8');

// agent-discovery.json
let ad = JSON.parse(fs.readFileSync('agent-discovery.json','utf8'));
ad.total_entities = total;
ad.categories = {};
Object.keys(e.meta.category_counts).forEach(k => { ad.categories[k] = e.meta.category_counts[k]; });
fs.writeFileSync('agent-discovery.json', JSON.stringify(ad, null, 2), 'utf8');

console.log('All derived files rebuilt');
console.log('Total:', total, 'Clean:', clean, 'Tier A:', realA);
console.log('Kinds:', JSON.stringify(kinds));