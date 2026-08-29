/**
 * Marketplace API - List items
 * GET /api/marketplace
 * HEAD /api/marketplace
 */
export async function onRequestHead(context) {
  return new Response(null, {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'public, max-age=3600'
    }
  });
}

export async function onRequestGet(context) {
  const { env, request } = context;
  const url = new URL(request.url);
  
  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = parseInt(url.searchParams.get('limit') || '20');
  const category = url.searchParams.get('category');
  const search = url.searchParams.get('search');
  const sort = url.searchParams.get('sort') || 'newest';
  
  try {
    let items = [];
    
    if (env.MARKETPLACE_KV) {
      const data = await env.MARKETPLACE_KV.get('marketplace:items', 'json');
      items = data || [];
    } else {
      items = getDemoItems();
    }
    
    if (category) {
      items = items.filter(i => i.data_type === category);
    }
    
    if (search) {
      const q = search.toLowerCase();
      items = items.filter(i => 
        i.title.toLowerCase().includes(q) ||
        i.description.toLowerCase().includes(q) ||
        i.tags.some(t => t.toLowerCase().includes(q))
      );
    }
    
    switch (sort) {
      case 'popular':
        items.sort((a, b) => b.stats.downloads - a.stats.downloads);
        break;
      case 'rating':
        items.sort((a, b) => b.stats.rating - a.stats.rating);
        break;
      case 'newest':
      default:
        items.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    }
    
    const total = items.length;
    const offset = (page - 1) * limit;
    const paged = items.slice(offset, offset + limit);
    
    return new Response(JSON.stringify({
      success: true,
      data: paged,
      pagination: { page, limit, total, pages: Math.ceil(total / limit) }
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
 * Marketplace API - Create item
 * POST /api/marketplace
 */
export async function onRequestPost(context) {
  const { env, request } = context;
  
  try {
    const body = await request.json();
    
    const item = {
      id: `market-${Date.now()}`,
      user_id: body.user_id || 'anonymous',
      data_type: body.data_type || 'assembly',
      title: body.title,
      description: body.description || '',
      tags: body.tags || [],
      modules: body.modules || [],
      files: body.files || {},
      price: body.price || 0,
      currency: 'CNY',
      license: body.license || 'CC-BY-SA',
      stats: { downloads: 0, likes: 0, rating: 0, reviews: 0 },
      created_at: new Date().toISOString().split('T')[0],
      updated_at: new Date().toISOString().split('T')[0],
      verified: false
    };
    
    if (env.MARKETPLACE_KV) {
      const existing = await env.MARKETPLACE_KV.get('marketplace:items', 'json') || [];
      existing.push(item);
      await env.MARKETPLACE_KV.put('marketplace:items', JSON.stringify(existing));
    }
    
    return new Response(JSON.stringify({ success: true, data: item }), {
      status: 201,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: e.message }), {
      status: 400,
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

function getDemoItems() {
  return [
    {
      id: 'market-001',
      user_id: 'user-123',
      data_type: 'assembly',
      title: '6轴仿人机械臂 v2',
      description: '基于仿生关节的6轴机械臂，支持3D打印',
      tags: ['bionic', 'arm', '6dof', '3d_printable'],
      modules: ['BIONIC-JOINT-001', 'BIONIC-ACTUATOR-001', 'BIONIC-FRAME-001'],
      files: { config: '/market/config/assembly-001.json' },
      price: 0,
      currency: 'CNY',
      license: 'CC-BY-SA',
      stats: { downloads: 234, likes: 89, rating: 4.7, reviews: 23 },
      created_at: '2026-08-15',
      updated_at: '2026-08-15',
      verified: true
    },
    {
      id: 'market-002',
      user_id: 'user-456',
      data_type: 'model',
      title: '仿生手指 STL 模型',
      description: '3自由度仿生手指，可3D打印',
      tags: ['bionic', 'finger', 'stl', '3d_printable'],
      modules: ['BIONIC-JOINT-002', 'BIONIC-ACTUATOR-002'],
      files: { stl: ['/market/stl/finger.stl'] },
      price: 50,
      currency: 'CNY',
      license: 'CC-BY-NC',
      stats: { downloads: 156, likes: 67, rating: 4.5, reviews: 15 },
      created_at: '2026-08-12',
      updated_at: '2026-08-12',
      verified: true
    },
    {
      id: 'market-003',
      user_id: 'user-789',
      data_type: 'code',
      title: 'ROS2 关节控制器',
      description: '支持仿生关节的ROS2控制节点',
      tags: ['ros2', 'controller', 'bionic', 'driver'],
      modules: ['BIONIC-JOINT-001', 'CTRL-ESP32-001'],
      files: { code: ['/market/code/joint_controller.zip'] },
      price: 0,
      currency: 'CNY',
      license: 'MIT',
      stats: { downloads: 312, likes: 102, rating: 4.8, reviews: 28 },
      created_at: '2026-08-10',
      updated_at: '2026-08-10',
      verified: true
    }
  ];
}
