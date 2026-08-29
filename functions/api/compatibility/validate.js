/**
 * Compatibility API - Validate module combinations
 * POST /api/compatibility/validate
 * HEAD /api/compatibility/validate
 */
export async function onRequestHead(context) {
  return new Response(null, {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    }
  });
}

export async function onRequestPost(context) {
  const { env, request } = context;
  
  try {
    const body = await request.json();
    const { modules } = body;
    
    if (!modules || !Array.isArray(modules)) {
      return new Response(JSON.stringify({
        success: false,
        error: 'modules array is required'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    const rules = getCompatibilityRules();
    const result = validateCompatibility(modules, rules);
    
    return new Response(JSON.stringify({
      success: true,
      data: result
    }), {
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

/**
 * Compatibility API - Get compatible modules
 * GET /api/compatibility/compatible/:id
 */
export async function onRequestGet(context) {
  const { env, params } = context;
  const moduleId = params.id;
  
  try {
    const rules = getCompatibilityRules();
    const compatible = rules[moduleId] || [];
    
    const modules = await getModules();
    const compatibleModules = modules.filter(m => compatible.includes(m.id));
    
    return new Response(JSON.stringify({
      success: true,
      data: {
        module_id: moduleId,
        compatible: compatibleModules,
        total: compatibleModules.length
      }
    }), {
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    }
  });
}

function validateCompatibility(modules, rules) {
  const conflicts = [];
  const warnings = [];
  
  for (let i = 0; i < modules.length; i++) {
    for (let j = i + 1; j < modules.length; j++) {
      const a = modules[i];
      const b = modules[j];
      
      const aCompat = rules[a] || [];
      const bCompat = rules[b] || [];
      
      if (!aCompat.includes(b) && !bCompat.includes(a)) {
        conflicts.push({
          modules: [a, b],
          reason: '接口不兼容',
          severity: 'error'
        });
      }
    }
  }
  
  const categories = {};
  modules.forEach(m => {
    const cat = m.split('-').slice(0, 2).join('-');
    categories[cat] = (categories[cat] || 0) + 1;
  });
  
  for (const [cat, count] of Object.entries(categories)) {
    if (cat.includes('JOINT') && count > 4) {
      warnings.push({
        type: 'redundancy',
        message: `关节模块数量较多 (${count})，可能造成资源浪费`,
        severity: 'warning'
      });
    }
  }
  
  return {
    valid: conflicts.length === 0,
    conflicts,
    warnings,
    summary: {
      total_modules: modules.length,
      conflicts_count: conflicts.length,
      warnings_count: warnings.length
    }
  };
}

function getCompatibilityRules() {
  return {
    'BIONIC-JOINT-001': ['BIONIC-ACTUATOR-001', 'BIONIC-ACTUATOR-002', 'BIONIC-FRAME-001', 'BIONIC-SKIN-001', 'CONN-M3-001'],
    'BIONIC-JOINT-002': ['BIONIC-ACTUATOR-001', 'BIONIC-FRAME-001', 'CONN-M3-001', 'CONN-M4-001'],
    'BIONIC-JOINT-003': ['BIONIC-FRAME-001', 'CONN-M3-001'],
    'BIONIC-ACTUATOR-001': ['BIONIC-JOINT-001', 'BIONIC-JOINT-002', 'CTRL-ESP32-001', 'CTRL-RPI-001'],
    'BIONIC-ACTUATOR-002': ['BIONIC-JOINT-001', 'CTRL-ESP32-001'],
    'BIONIC-SENSOR-001': ['BIONIC-FRAME-001', 'CTRL-ESP32-001', 'CTRL-RPI-001'],
    'BIONIC-SENSOR-002': ['CTRL-ESP32-001', 'CTRL-RPI-001'],
    'BIONIC-FRAME-001': ['BIONIC-JOINT-001', 'BIONIC-JOINT-002', 'BIONIC-JOINT-003', 'BIONIC-SENSOR-001', 'BIONIC-SKIN-001'],
    'BIONIC-SKIN-001': ['BIONIC-FRAME-001', 'BIONIC-JOINT-001'],
    'CTRL-ESP32-001': ['BIONIC-ACTUATOR-001', 'BIONIC-ACTUATOR-002', 'BIONIC-SENSOR-001', 'BIONIC-SENSOR-002'],
    'CTRL-RPI-001': ['BIONIC-ACTUATOR-001', 'BIONIC-SENSOR-001', 'BIONIC-SENSOR-002'],
  };
}

async function getModules() {
  return [
    { id: 'BIONIC-JOINT-001', name: '球窝关节', category: 'bionic_joints' },
    { id: 'BIONIC-JOINT-002', name: '铰链关节', category: 'bionic_joints' },
    { id: 'BIONIC-JOINT-003', name: '滑动关节', category: 'bionic_joints' },
    { id: 'BIONIC-ACTUATOR-001', name: '肌腱驱动', category: 'bionic_actuators' },
    { id: 'BIONIC-ACTUATOR-002', name: '人工肌肉', category: 'bionic_actuators' },
    { id: 'BIONIC-SENSOR-001', name: '电子皮肤', category: 'bionic_sensors' },
    { id: 'BIONIC-SENSOR-002', name: '本体感知', category: 'bionic_sensors' },
    { id: 'BIONIC-FRAME-001', name: '仿生骨架', category: 'bionic_structures' },
    { id: 'BIONIC-SKIN-001', name: '仿生皮肤', category: 'bionic_structures' },
    { id: 'CTRL-ESP32-001', name: 'ESP32', category: 'controllers' },
    { id: 'CTRL-RPI-001', name: '树莓派 4B', category: 'controllers' },
    { id: 'CONN-M3-001', name: 'M3 螺栓', category: 'connectors' },
    { id: 'CONN-M4-001', name: 'M4 螺栓', category: 'connectors' },
  ];
}
