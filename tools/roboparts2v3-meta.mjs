#!/usr/bin/env node
// tools/roboparts2v3-meta.mjs
//
// RoboParts 静态库 -> LeRobotDataset v3 meta/roboparts.json 扩展（A 方案，零侵入）
//
// 依据:
//   - intel/reports/lerobot-v3-列映射草案-2026-11-18.md
//   - intel/reports/lerobot-v3-roboparts-schema-草案-2026-11-18.md
//
// 原则（诚实边界，不可破）:
//   1. 只生成 meta 扩展文件，绝不改动 v3 标准的 data/ videos/ 或 meta/info.json、stats.json、tasks.parquet。
//   2. 不编造任何原始时序（图像/力觉/触觉/本体轨迹）——本脚本不产出任何帧数据。
//   3. 声明级参数与 compatibility 判定的溯源字段（source_tier/evidence_basis/quarantine）原样保留。
//
// 用法:
//   node tools/roboparts2v3-meta.mjs --source api/training_dataset.json --dataset-id lerobot/pusht
//                                    [--dry-run] [--out <dir>] [--shard-size 2000] [--drop-undecided]
//
//   --dry-run      只打印将生成的文件清单与体积估算，不写盘
//   --out <dir>    写入 <dir>/meta/roboparts.json 与 roboparts.pairs-NNN.json（默认不写）
//   --shard-size N 每个 pairs 分片的装配对数（默认 2000；全量 10304 -> 6 片）
//   --drop-undecided  仅导出 overall_compatible=true 的对（默认保留全量，负样本有价值）
//
import fs from 'node:fs';
import path from 'node:path';

const SCHEMA_VERSION = '1.0';

function parseArgs(argv) {
  const a = { shardSize: 2000, dryRun: false, dropUndecided: false };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--source') a.source = argv[++i];
    else if (k === '--dataset-id') a.datasetId = argv[++i];
    else if (k === '--out') a.out = argv[++i];
    else if (k === '--shard-size') a.shardSize = parseInt(argv[++i], 10);
    else if (k === '--dry-run') a.dryRun = true;
    else if (k === '--drop-undecided') a.dropUndecided = true;
    else throw new Error(`未知参数: ${k}`);
  }
  if (!a.source || !a.datasetId) throw new Error('缺少 --source / --dataset-id');
  if (!Number.isFinite(a.shardSize) || a.shardSize < 1) throw new Error('--shard-size 须为正整数');
  return a;
}

// components[] -> parts[]（id -> part_id，其余字段保持源名与嵌套结构，不造新词）
function mapParts(components) {
  return components.map((c) => ({
    part_id: c.id,
    name: c.name ?? null,
    name_en: c.name_en ?? null,
    category: c.category ?? null,
    entity_kind: c.entity_kind ?? null,
    manufacturer: c.manufacturer ?? null,
    type: c.type ?? null,
    specs: c.specs ?? {},
    applications: c.applications ?? [],
    price_range: c.price_range ?? null,
    ros_support: c.ros_support ?? null,
    modalities: c.modalities ?? [],
    modality_details: c.modality_details ?? {},
    // 溯源嵌套结构保持原样（含可选 source_url）
    evidence: c.evidence ?? {},
    standards: c.standards ?? {},
  }));
}

// compatibility_edges[] -> assemble_pairs[]
// 注意: decided_dimensions / undecided_dimensions / hard_dimensions_decided 在源里是整数计数，原样保留。
function mapPairs(edges) {
  return edges.map((e) => ({
    pair_id: `${e.a}__${e.b}`,
    part_a: e.a,
    part_b: e.b,
    dimensions: (e.dimensions ?? []).map((d) => ({
      dimension: d.dimension ?? null,
      compatible: d.compatible ?? null,
      score: d.score ?? null,
      notes: d.notes ?? '',
    })),
    overall_compatible: e.overall_compatible ?? null,
    compatibility_score: e.compatibility_score ?? null,
    decided_dimensions: e.decided_dimensions ?? null,
    undecided_dimensions: e.undecided_dimensions ?? null,
    hard_dimensions_decided: e.hard_dimensions_decided ?? null,
    interaction_type: e.interaction_type ?? null,
    force_profile: e.force_profile ?? {},
    verdict_reason: e.verdict_reason ?? '',
    // 溯源原样保留，禁止改写
    evidence_basis: e.evidence_basis ?? '',
  }));
}

function mapStandards(standards) {
  return standards.map((s) => ({
    id: s.id ?? null,
    name: s.name ?? null,
    type: s.type ?? null,
    status: s.status ?? null,
    issued_at: s.issued_at ?? null,
    issuer: s.issuer ?? null,
    evidence_tier: s.evidence_tier ?? null,
  }));
}

function main() {
  const a = parseArgs(process.argv.slice(2));
  const raw = fs.readFileSync(a.source, 'utf8');
  const o = JSON.parse(raw);

  const parts = mapParts(o.components ?? []);
  let pairs = mapPairs(o.compatibility_edges ?? []);
  const totalPairs = pairs.length;
  if (a.dropUndecided) pairs = pairs.filter((p) => p.overall_compatible === true);
  const standards_ref = mapStandards(o.standards ?? []);

  const root = {
    schema_version: SCHEMA_VERSION,
    dataset_binding: {
      dataset_id: a.datasetId,
      bound_at: new Date().toISOString(),
      roboparts_snapshot: `api/training_dataset.json@${o.meta?.generated_at ?? 'unknown'}`,
      source_schema_version: o.meta?.schema_version ?? null,
      shard_size: a.shardSize,
      pairs_total_source: totalPairs,
      pairs_exported: pairs.length,
      drop_undecided: a.dropUndecided,
    },
    parts,
    standards_ref,
    honesty: o.meta?.honesty ?? {},
    provenance: o.meta?.provenance ?? {},
    consumption_note:
      'RoboParts 不提供原始图像/力觉/触觉时序与本体轨迹；本文件仅承载声明级参数与兼容性判定，供消费方作先验。' +
      '未声明维度记为无法判定，不计入分子也不计入分母。',
  };

  const bytes = (obj) => Buffer.byteLength(JSON.stringify(obj), 'utf8');
  const rootBytes = bytes(root);
  const shards = [];
  for (let i = 0; i < pairs.length; i += a.shardSize) {
    const slice = pairs.slice(i, i + a.shardSize);
    shards.push({
      name: `roboparts.pairs-${String(i / a.shardSize).padStart(3, '0')}.json`,
      count: slice.length,
      bytes: bytes({ schema_version: SCHEMA_VERSION, dataset_binding: root.dataset_binding, assemble_pairs: slice }),
    });
  }

  const mb = (n) => (n / (1024 * 1024)).toFixed(2);
  console.log('=== roboparts2v3-meta 生成计划 ===');
  console.log(`源: ${a.source}`);
  console.log(`绑定 dataset_id: ${a.datasetId}`);
  console.log(`parts: ${parts.length}  |  standards_ref: ${standards_ref.length}  |  pairs: ${pairs.length}/${totalPairs}${a.dropUndecided ? ' (drop-undecided)' : ''}`);
  console.log(`roboparts.json 估算: ${bytes(root)} B (~${mb(rootBytes)} MB)`);
  console.log(`pairs 分片 ${shards.length} 片 (shard-size=${a.shardSize}):`);
  for (const s of shards) console.log(`  ${s.name}  pairs=${s.count}  ~${mb(s.bytes)} MB`);
  const total = rootBytes + shards.reduce((t, s) => t + s.bytes, 0);
  console.log(`合计估算: ~${mb(total)} MB`);

  if (a.dryRun || !a.out) {
    console.log(a.dryRun ? '\n[dry-run] 未写盘。加 --out <dir> 生成到 <dir>/meta/' : '\n未指定 --out，未写盘。');
    return;
  }

  const dir = path.join(a.out, 'meta');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'roboparts.json'), JSON.stringify(root, null, 2), 'utf8');
  console.log(`\n已写 ${path.join(dir, 'roboparts.json')}`);
  for (let i = 0; i < pairs.length; i += a.shardSize) {
    const slice = pairs.slice(i, i + a.shardSize);
    const name = `roboparts.pairs-${String(i / a.shardSize).padStart(3, '0')}.json`;
    const obj = { schema_version: SCHEMA_VERSION, dataset_binding: root.dataset_binding, assemble_pairs: slice };
    fs.writeFileSync(path.join(dir, name), JSON.stringify(obj, null, 2), 'utf8');
    console.log(`已写 ${path.join(dir, name)}`);
  }
  console.log('\n⚠ 只生成了 meta 扩展。v3 标准的 data/ videos/ meta/info.json|stats.json|tasks.parquet 均未改动。');
}

main();
