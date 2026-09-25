/**
 * URDF Linter — 纯 JS 实现，零依赖，可在 Cloudflare Workers 运行。
 *
 * 定位：URDF 是 ROS 生态通用格式，但几乎没有人做 URDF 的兼容性检查。
 * 本模块提供 10 类静态检查，输出结构化 JSON 报告。
 *
 * 输入：URDF XML 字符串
 * 输出：{ severity, issues[], summary, robot_name, stats }
 *
 * 检查项（10 类）：
 *  1. parse_error          — XML 解析失败
 *  2. missing_root_link    — 无根 link（每个 link 都有父关节）
 *  3. missing_joint_limits — 关节缺少 <limit> 或字段为 NaN
 *  4. invalid_joint_type   — 关节类型不在允许列表
 *  5. duplicate_link_names — 重复 link 名
 *  6. cycle_in_tree        — 关节连接形成循环（URDF 应为树）
 *  7. missing_flange_frame — 缺少 flange/tool0 等 ROS 工业标准帧
 *  8. missing_origin       — link/joint 缺少 <origin>
 *  9. missing_inertial     — link 缺少 <inertial>（非 base frame）
 * 10. mesh_path_issue      — mesh 路径无效或格式不支持
 *
 * 参考：
 *  - ROS Industrial frame conventions: flange, tool0, base
 *  - ISO 9409-1: 机械法兰接口标准
 *  - URDF spec: http://wiki.ros.org/urdf/XML/
 */

const VALID_JOINT_TYPES = new Set(['prismatic', 'revolute', 'continuous', 'fixed', 'mimic']);
const VALID_MESH_EXTENSIONS = new Set(['dae', 'stl', 'obj', 'ply', 'urdf']);
const STANDARD_FRAMES = ['flange', 'tool0', 'base', 'base_link'];

/**
 * 极简 URDF XML 解析器。
 * 不依赖 DOMParser（Workers 环境不完全支持），用状态机解析。
 * 返回结构化树：{ robot, links, joints }
 */
export function parseUrdf(xml) {
  if (!xml || typeof xml !== 'string') {
    return { error: 'empty_input', links: [], joints: [] };
  }

  const issues = [];
  // 检查是否看起来像 URDF
  if (!/<robot[\s>]/.test(xml)) {
    return { error: 'not_a_urdf', links: [], joints: [], issues: [
      { code: 'parse_error', severity: 'error', message: 'Not a valid URDF: missing <robot> root element' }
    ]};
  }

  // 尝试用 DOMParser（如果可用）
  if (typeof DOMParser !== 'undefined') {
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(xml, 'application/xml');
      const parserError = doc.querySelector('parsererror');
      if (parserError) {
        return { error: 'xml_parse_failed', links: [], joints: [], issues: [
          { code: 'parse_error', severity: 'error', message: `XML parse error: ${parserError.textContent.slice(0, 200)}` }
        ]};
      }
      return parseWithDom(doc);
    } catch (e) {
      // fallback to regex parser
    }
  }

  return parseWithRegex(xml);
}

function parseWithDom(doc) {
  const robot = doc.querySelector('robot');
  const robotName = robot?.getAttribute('name') || 'unknown';
  const links = Array.from(doc.querySelectorAll('link')).map(el => extractLink(el));
  const joints = Array.from(doc.querySelectorAll('joint')).map(el => extractJoint(el));
  return { robot: robotName, links, joints };
}

function extractLink(el) {
  const link = { name: el.getAttribute('name') || 'unnamed' };
  // visual
  const visuals = Array.from(el.querySelectorAll('visual'));
  link.visuals = visuals.map(v => ({
    origin: extractOrigin(v.querySelector('origin')),
    geometry: extractGeometry(v.querySelector('geometry')),
    material: extractMaterial(v.querySelector('material')),
  }));
  // collision
  const collisions = Array.from(el.querySelectorAll('collision'));
  link.collisions = collisions.map(c => ({
    origin: extractOrigin(c.querySelector('origin')),
    geometry: extractGeometry(c.querySelector('geometry')),
  }));
  // inertial
  const inertial = el.querySelector('inertial');
  link.inertial = inertial ? {
    origin: extractOrigin(inertial.querySelector('origin')),
    mass: inertial.querySelector('mass')?.getAttribute('value') || null,
    inertia: {
      ixx: inertial.querySelector('inertia')?.getAttribute('ixx') || null,
      ixy: inertial.querySelector('inertia')?.getAttribute('ixy') || null,
      ixz: inertial.querySelector('inertia')?.getAttribute('ixz') || null,
      iyy: inertial.querySelector('inertia')?.getAttribute('iyy') || null,
      iyz: inertial.querySelector('inertia')?.getAttribute('iyz') || null,
      izz: inertial.querySelector('inertia')?.getAttribute('izz') || null,
    },
  } : null;
  return link;
}

function extractJoint(el) {
  const joint = {
    name: el.getAttribute('name') || 'unnamed',
    type: el.getAttribute('type') || 'unknown',
    parent: el.querySelector('parent')?.getAttribute('link') || null,
    child: el.querySelector('child')?.getAttribute('link') || null,
    origin: extractOrigin(el.querySelector('origin')),
  };
  const limit = el.querySelector('limit');
  joint.limit = limit ? {
    lower: parseFloat(limit.getAttribute('lower')) || null,
    upper: parseFloat(limit.getAttribute('upper')) || null,
    effort: parseFloat(limit.getAttribute('effort')) || null,
    velocity: parseFloat(limit.getAttribute('velocity')) || null,
  } : null;
  // mimic
  const mimic = el.querySelector('mimic');
  if (mimic) {
    joint.mimic = {
      joint: mimic.getAttribute('joint') || null,
      multiplier: parseFloat(mimic.getAttribute('multiplier')) || 1,
      offset: parseFloat(mimic.getAttribute('offset')) || 0,
    };
  }
  return joint;
}

function extractOrigin(el) {
  if (!el) return null;
  return {
    xyz: (el.getAttribute('xyz') || '0 0 0').split(/\s+/).map(Number),
    rpy: (el.getAttribute('rpy') || '0 0 0').split(/\s+/).map(Number),
  };
}

function extractGeometry(el) {
  if (!el) return null;
  const mesh = el.querySelector('mesh');
  if (mesh) {
    return { type: 'mesh', filename: mesh.getAttribute('filename') || null };
  }
  const box = el.querySelector('box');
  if (box) {
    const size = box.getAttribute('size') || '0 0 0';
    return { type: 'box', size: size.split(/\s+/).map(Number) };
  }
  const cyl = el.querySelector('cylinder');
  if (cyl) {
    return { type: 'cylinder', radius: parseFloat(cyl.getAttribute('radius')) || null,
             length: parseFloat(cyl.getAttribute('length')) || null };
  }
  const sph = el.querySelector('sphere');
  if (sph) {
    return { type: 'sphere', radius: parseFloat(sph.getAttribute('radius')) || null };
  }
  return { type: 'unknown' };
}

function extractMaterial(el) {
  if (!el) return null;
  const color = el.querySelector('color');
  if (color) {
    return { name: el.getAttribute('name') || null,
             rgba: color.getAttribute('rgba')?.split(/\s+/).map(Number) || null };
  }
  const texture = el.querySelector('texture');
  return { name: el.getAttribute('name') || null,
           texture: texture?.getAttribute('filename') || null };
}

// ==================== 正则 fallback 解析器 ====================

function parseWithRegex(xml) {
  const robotMatch = /<robot[^>]*name=["']([^"']*)["'][^>]*>/.exec(xml);
  const robotName = robotMatch ? robotMatch[1] : 'unknown';

  const links = [];
  const linkRe = /<link\s+name=["']([^"']*)["'][^>]*>([\s\S]*?)<\/link>/g;
  let m;
  while ((m = linkRe.exec(xml)) !== null) {
    links.push({
      name: m[1],
      raw: m[2],
      visuals: extractVisualsFromRaw(m[2]),
      collisions: extractCollisionsFromRaw(m[2]),
      inertial: extractInertialFromRaw(m[2]),
    });
  }

  const joints = [];
  const jointRe = /<joint\s+name=["']([^"']*)["'][^>]*type=["']([^"']*)["'][^>]*>([\s\S]*?)<\/joint>/g;
  while ((m = jointRe.exec(xml)) !== null) {
    const body = m[3];
    const parent = /<parent\s+link=["']([^"']*)["']/.exec(body);
    const child = /<child\s+link=["']([^"']*)["']/.exec(body);
    const originMatch = /<origin\s+xyz=["']([^"']*)["'][^>]*rpy=["']([^"']*)["']/.exec(body);
    const limitMatch = /<limit\s+([^>]*?)\/?>/.exec(body);
    joints.push({
      name: m[1],
      type: m[2],
      parent: parent ? parent[1] : null,
      child: child ? child[1] : null,
      origin: originMatch ? {
        xyz: originMatch[1].split(/\s+/).map(Number),
        rpy: originMatch[2].split(/\s+/).map(Number),
      } : null,
      limit: limitMatch ? {
        lower: parseFloat(/lower=["']([^"']*)["']/.exec(limitMatch[1])?.[1]) || null,
        upper: parseFloat(/upper=["']([^"']*)["']/.exec(limitMatch[1])?.[1]) || null,
        effort: parseFloat(/effort=["']([^"']*)["']/.exec(limitMatch[1])?.[1]) || null,
        velocity: parseFloat(/velocity=["']([^"']*)["']/.exec(limitMatch[1])?.[1]) || null,
      } : null,
    });
  }

  return { robot: robotName, links, joints };
}

function extractVisualsFromRaw(raw) {
  const visuals = [];
  const re = /<visual>([\s\S]*?)<\/visual>/g;
  let m;
  while ((m = re.exec(raw)) !== null) {
    visuals.push({ raw: m[1] });
  }
  return visuals;
}

function extractCollisionsFromRaw(raw) {
  const collisions = [];
  const re = /<collision>([\s\S]*?)<\/collision>/g;
  let m;
  while ((m = re.exec(raw)) !== null) {
    collisions.push({ raw: m[1] });
  }
  return collisions;
}

function extractInertialFromRaw(raw) {
  const m = /<inertial>([\s\S]*?)<\/inertial>/.exec(raw);
  if (!m) return null;
  return { raw: m[1] };
}

// ==================== 检查规则 ====================

export function lintUrdf(xml, options = {}) {
  const issues = [];
  const stats = {
    links: 0, joints: 0, valid_links: 0, valid_joints: 0,
    missing_limits: 0, missing_inertial: 0, duplicate_links: 0,
    mesh_count: 0, fixed_joints: 0, revolute_joints: 0, prismatic_joints: 0,
  };

  const parsed = parseUrdf(xml);
  if (parsed.error) {
    return {
      severity: 'error',
      robot_name: parsed.robot || null,
      issues: parsed.issues || [{ code: 'parse_error', severity: 'error', message: parsed.error }],
      summary: 'Failed to parse URDF',
      stats: { links: 0, joints: 0 },
    };
  }

  const { robot: robotName, links, joints } = parsed;
  stats.links = links.length;
  stats.joints = joints.length;

  // 1. 检查重复 link 名
  const linkNames = new Map();
  for (const link of links) {
    if (!link.name) {
      issues.push({ code: 'missing_link_name', severity: 'error', message: 'Link with missing name' });
      continue;
    }
    if (linkNames.has(link.name)) {
      issues.push({ code: 'duplicate_link_names', severity: 'error',
                    message: `Duplicate link name: '${link.name}'`, link: link.name });
      stats.duplicate_links++;
    } else {
      linkNames.set(link.name, link);
    }
  }

  // 2. 检查关节引用不存在的 link
  for (const joint of joints) {
    if (joint.parent && !linkNames.has(joint.parent)) {
      issues.push({ code: 'invalid_joint_parent', severity: 'error',
                    message: `Joint '${joint.name}' references non-existent parent link '${joint.parent}'`,
                    joint: joint.name, link: joint.parent });
    }
    if (joint.child && !linkNames.has(joint.child)) {
      issues.push({ code: 'invalid_joint_child', severity: 'error',
                    message: `Joint '${joint.name}' references non-existent child link '${joint.child}'`,
                    joint: joint.name, link: joint.child });
    }
  }

  // 3. 检查关节类型
  for (const joint of joints) {
    if (!VALID_JOINT_TYPES.has(joint.type)) {
      issues.push({ code: 'invalid_joint_type', severity: 'error',
                    message: `Joint '${joint.name}' has invalid type '${joint.type}'. Valid: ${[...VALID_JOINT_TYPES].join(', ')}`,
                    joint: joint.name, type: joint.type });
    }
    if (joint.type === 'fixed') stats.fixed_joints++;
    if (joint.type === 'revolute') stats.revolute_joints++;
    if (joint.type === 'prismatic') stats.prismatic_joints++;
  }

  // 4. 检查关节限位
  for (const joint of joints) {
    if (joint.type === 'fixed' || joint.type === 'continuous') continue; // fixed 不需要限位，continuous 忽略上下限
    if (!joint.limit) {
      issues.push({ code: 'missing_joint_limits', severity: 'warning',
                    message: `Joint '${joint.name}' (${joint.type}) has no <limit> element`,
                    joint: joint.name });
      stats.missing_limits++;
      continue;
    }
    if (joint.limit.lower === null || joint.limit.upper === null) {
      issues.push({ code: 'missing_joint_limits', severity: 'warning',
                    message: `Joint '${joint.name}' has incomplete <limit> (lower: ${joint.limit.lower}, upper: ${joint.limit.upper})`,
                    joint: joint.name, lower: joint.limit.lower, upper: joint.limit.upper });
      stats.missing_limits++;
    }
    if (joint.limit.effort === null || joint.limit.velocity === null) {
      issues.push({ code: 'missing_joint_limits', severity: 'info',
                    message: `Joint '${joint.name}' has no effort/velocity limit (effort: ${joint.limit.effort}, velocity: ${joint.limit.velocity})`,
                    joint: joint.name, effort: joint.limit.effort, velocity: joint.limit.velocity });
    }
  }

  // 5. 检查根 link（没有父关节的 link）
  const childLinks = new Set(joints.map(j => j.child));
  const rootLinks = links.filter(l => !childLinks.has(l.name));
  if (rootLinks.length === 0) {
    issues.push({ code: 'missing_root_link', severity: 'error',
                  message: 'No root link found (every link has a parent joint). URDF should be a tree with exactly one root.' });
  } else if (rootLinks.length > 1) {
    issues.push({ code: 'multiple_root_links', severity: 'warning',
                  message: `Multiple root links found: ${rootLinks.map(l => l.name).join(', ')}. URDF should have exactly one root.` });
  }

  // 6. 检查循环（图遍历）
  const adjacency = new Map();
  for (const joint of joints) {
    if (joint.parent && joint.child) {
      if (!adjacency.has(joint.parent)) adjacency.set(joint.parent, []);
      adjacency.get(joint.parent).push(joint.child);
    }
  }
  const visited = new Set();
  const inStack = new Set();
  function hasCycle(node) {
    visited.add(node);
    inStack.add(node);
    for (const neighbor of (adjacency.get(node) || [])) {
      if (!visited.has(neighbor)) {
        if (hasCycle(neighbor)) return true;
      } else if (inStack.has(neighbor)) {
        return true;
      }
    }
    inStack.delete(node);
    return false;
  }
  for (const link of links) {
    if (link.name && !visited.has(link.name)) {
      if (hasCycle(link.name)) {
        issues.push({ code: 'cycle_in_tree', severity: 'error',
                      message: `Cycle detected in kinematic tree involving link '${link.name}'. URDF must be a tree (no cycles).`,
                      link: link.name });
        break;
      }
    }
  }

  // 7. 检查标准帧
  const hasFlange = links.some(l => l.name === 'flange');
  const hasTool0 = links.some(l => l.name === 'tool0');
  const hasBase = links.some(l => l.name === 'base' || l.name === 'base_link');
  if (!hasFlange) {
    issues.push({ code: 'missing_flange_frame', severity: 'warning',
                  message: 'Missing "flange" link. ROS Industrial convention expects a "flange" frame at the end of the arm.',
                  standard_frame: 'flange' });
  }
  if (!hasTool0) {
    issues.push({ code: 'missing_flange_frame', severity: 'info',
                  message: 'Missing "tool0" link. ROS Industrial convention uses "tool0" as the tool mounting point.',
                  standard_frame: 'tool0' });
  }
  if (!hasBase) {
    issues.push({ code: 'missing_flange_frame', severity: 'warning',
                  message: 'Missing "base" or "base_link" link. ROS Industrial convention expects a base frame.',
                  standard_frame: 'base/base_link' });
  }

  // 8. 检查 origin
  for (const joint of joints) {
    if (!joint.origin) {
      issues.push({ code: 'missing_origin', severity: 'info',
                    message: `Joint '${joint.name}' has no <origin>. Defaulting to identity transform.`,
                    joint: joint.name });
    }
  }

  // 9. 检查 inertial
  for (const link of links) {
    if (!link.name) continue;
    if (link.name === 'flange' || link.name === 'tool0' || link.name === 'base' || link.name === 'base_link') continue;
    if (!link.inertial) {
      issues.push({ code: 'missing_inertial', severity: 'warning',
                    message: `Link '${link.name}' has no <inertial> data. This will affect dynamics simulation.`,
                    link: link.name });
      stats.missing_inertial++;
    }
  }

  // 10. 检查 mesh 路径
  for (const link of links) {
    if (!link.name) continue;
    const checkGeometry = (geom, ctx) => {
      if (geom?.type === 'mesh' && geom.filename) {
        const ext = geom.filename.split('.').pop().toLowerCase();
        if (!VALID_MESH_EXTENSIONS.has(ext)) {
          issues.push({ code: 'mesh_path_issue', severity: 'warning',
                        message: `Link '${link.name}' (${ctx}): mesh file '${geom.filename}' has unsupported extension '.${ext}'. Supported: ${[...VALID_MESH_EXTENSIONS].join(', ')}`,
                        link: link.name, filename: geom.filename });
        }
        // 检查是否 package:// 路径（ROS 约定）
        if (!geom.filename.startsWith('package://') && !geom.filename.startsWith('http') && !geom.filename.startsWith('/')) {
          issues.push({ code: 'mesh_path_issue', severity: 'info',
                        message: `Link '${link.name}' (${ctx}): mesh file '${geom.filename}' uses a relative path. Prefer 'package://' URIs for portability.`,
                        link: link.name, filename: geom.filename });
        }
        stats.mesh_count++;
      }
    };
    if (link.visuals) {
      for (const v of link.visuals) checkGeometry(v.geometry, 'visual');
    }
    if (link.collisions) {
      for (const c of link.collisions) checkGeometry(c.geometry, 'collision');
    }
  }

  // 计算严重级别
  const hasError = issues.some(i => i.severity === 'error');
  const hasWarning = issues.some(i => i.severity === 'warning');
  const severity = hasError ? 'error' : (hasWarning ? 'warning' : 'info');

  // 汇总
  const errorCount = issues.filter(i => i.severity === 'error').length;
  const warningCount = issues.filter(i => i.severity === 'warning').length;
  const infoCount = issues.filter(i => i.severity === 'info').length;

  const summary = `URDF '${robotName}': ${links.length} links, ${joints.length} joints. ` +
    `${errorCount} error(s), ${warningCount} warning(s), ${infoCount} info(s). ` +
    `Root links: ${rootLinks.length}. Revolute: ${stats.revolute_joints}, Fixed: ${stats.fixed_joints}, Prismatic: ${stats.prismatic_joints}.`;

  return {
    severity,
    robot_name: robotName,
    issues,
    summary,
    stats: {
      ...stats,
      total_links: links.length,
      total_joints: joints.length,
      root_links: rootLinks.map(l => l.name),
      link_names: links.map(l => l.name).filter(Boolean),
      joint_names: joints.map(j => j.name).filter(Boolean),
      error_count: errorCount,
      warning_count: warningCount,
      info_count: infoCount,
    },
  };
}
