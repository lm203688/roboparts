/**
 * RoboParts 领域方言模板系统
 * 
 * 参考：2origin的"核心+方言"架构
 * 
 * 核心概念：
 * 1. 核心（Core）：实体数据 + 兼容性判定逻辑
 * 2. 方言（Dialect）：特定行业的评价维度、筛选规则、推荐策略
 * 
 * 支持的方言模板：
 * - humanoid：人形机器人场景
 * - industrial：工业机械臂场景
 * -灵巧手：灵巧手场景
 * - mobile_robot：移动机器人场景
 * - research：科研教育场景
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIALECTS_DIR = join(__dirname, '..', 'dialects');

// ============================================================
// 方言模板定义
// ============================================================

const DIALECT_TEMPLATES = {
  // 人形机器人方言
  humanoid: {
    id: 'humanoid',
    name: '人形机器人场景',
    description: '适用于双足人形机器人的选型场景，关注关节自由度、力矩分布、平衡控制',
    version: '1.0.0',
    
    // 评价维度权重
    evaluation_dimensions: {
      joint_freedom: { weight: 0.25, description: '关节自由度' },
      torque_distribution: { weight: 0.20, description: '力矩分布' },
      balance_control: { weight: 0.15, description: '平衡控制能力' },
      power_efficiency: { weight: 0.15, description: '能效比' },
      weight_size: { weight: 0.10, description: '重量尺寸' },
      cost: { weight: 0.10, description: '成本' },
      ros_support: { weight: 0.05, description: 'ROS2支持' }
    },
    
    // 关注的实体类型
    focus_categories: {
      actuators: {
        focus_types: ['关节电机', '伺服电机', '力矩电机'],
        key_specs: ['torque', 'speed', 'range_of_motion', 'weight'],
        ideal_torque_range: '5-50 Nm',
        ideal_voltage: '24-48V'
      },
      sensors: {
        focus_types: ['IMU', '力传感器', '关节位置传感器', '触觉传感器'],
        key_specs: ['accuracy', 'resolution', 'response_time'],
        critical_sensors: ['IMU', '关节力矩传感器']
      },
      chips: {
        focus_types: ['计算平台', '运动控制器'],
        key_specs: ['compute_power', 'interfaces', 'real_time_support'],
        required_interfaces: ['CAN', 'EtherCAT', 'RS485']
      }
    },
    
    // 兼容性规则扩展
    compatibility_rules: {
      // 人形机器人特有的检查
      humanoid_specific: [
        {
          name: '关节力矩匹配',
          description: '检查执行器力矩是否满足人形机器人关节需求',
          check: (actuator, specs) => {
            const torque = parseFloat(specs.torque) || 0;
            return torque >= 5 && torque <= 50;
          }
        },
        {
          name: '实时控制支持',
          description: '检查控制器是否支持实时运动控制',
          check: (chip, specs) => {
            return specs.real_time_support || specs.rtos_support;
          }
        }
      ]
    },
    
    // 推荐策略
    recommendation_strategy: {
      prioritize: ['torque', 'weight', 'real_time_support'],
      avoid: ['high_power_consumption', 'low_efficiency'],
      budget_allocation: {
        actuators: 0.45,
        sensors: 0.20,
        chips: 0.25,
        others: 0.10
      }
    },
    
    // 典型配置模板
    typical_configs: [
      {
        name: '轻量级人形',
        description: '适用于科研教育的小型人形机器人',
        total_budget_cny: 50000,
        components: {
          actuators: { count: 12, type: 'servo', max_price_each: 2000 },
          sensors: { imu: 1, force: 6, position: 12 },
          chips: { main_controller: 1, motor_drivers: 4 }
        }
      },
      {
        name: '工业级人形',
        description: '适用于工业应用的大型人形机器人',
        total_budget_cny: 500000,
        components: {
          actuators: { count: 30, type: 'torque_motor', max_price_each: 5000 },
          sensors: { imu: 2, force: 20, position: 30, tactile: 10 },
          chips: { main_controller: 1, motor_drivers: 10, safety_controller: 1 }
        }
      }
    ]
  },
  
  // 工业机械臂方言
  industrial: {
    id: 'industrial',
    name: '工业机械臂场景',
    description: '适用于工业协作机器人和传统工业机械臂，关注精度、负载、重复定位精度',
    version: '1.0.0',
    
    evaluation_dimensions: {
      payload: { weight: 0.25, description: '负载能力' },
      reach: { weight: 0.20, description: '工作半径' },
      repeatability: { weight: 0.20, description: '重复定位精度' },
      speed: { weight: 0.15, description: '运动速度' },
      safety: { weight: 0.10, description: '安全性能' },
      cost: { weight: 0.10, description: '成本' }
    },
    
    focus_categories: {
      actuators: {
        focus_types: ['伺服电机', '力矩电机'],
        key_specs: ['torque', 'speed', 'accuracy', 'repeatability'],
        ideal_repeatability: '±0.01-0.1mm',
        ideal_payload: '3-20kg'
      },
      sensors: {
        focus_types: ['力传感器', '视觉传感器', '编码器'],
        key_specs: ['accuracy', 'resolution', 'response_time'],
        critical_sensors: ['六维力传感器', '视觉系统']
      },
      chips: {
        focus_types: ['运动控制器', 'PLC'],
        key_specs: ['control精度', 'real_time', 'safety'],
        required_features: ['EtherCAT', 'Safety PLC', '实时控制']
      }
    },
    
    compatibility_rules: {
      industrial_specific: [
        {
          name: '负载匹配',
          description: '检查执行器力矩是否满足负载需求',
          check: (actuator, specs, requirements) => {
            const torque = parseFloat(specs.torque) || 0;
            const payload = requirements.payload || 5;
            return torque >= payload * 9.8 * 0.5; // 安全系数
          }
        },
        {
          name: '精度匹配',
          description: '检查传感器精度是否满足定位要求',
          check: (sensor, specs, requirements) => {
            const accuracy = parseFloat(specs.accuracy) || 0;
            const required_accuracy = requirements.repeatability || 0.1;
            return accuracy <= required_accuracy;
          }
        }
      ]
    },
    
    recommendation_strategy: {
      prioritize: ['payload', 'repeatability', 'safety'],
      avoid: ['low_reliability', 'poor_documentation'],
      budget_allocation: {
        actuators: 0.40,
        sensors: 0.25,
        chips: 0.25,
        others: 0.10
      }
    },
    
    typical_configs: [
      {
        name: '协作机器人',
        description: '适用于人机协作的轻型机械臂',
        total_budget_cny: 100000,
        components: {
          actuators: { count: 6, type: 'servo', max_price_each: 5000 },
          sensors: { force: 6, vision: 1, position: 6 },
          chips: { controller: 1, safety_controller: 1 }
        }
      }
    ]
  },
  
  // 灵巧手方言
  dexterous_hand: {
    id: 'dexterous_hand',
    name: '灵巧手场景',
    description: '适用于机器人灵巧手和末端执行器，关注指尖力、自由度、抓取能力',
    version: '1.0.0',
    
    evaluation_dimensions: {
      degrees_of_freedom: { weight: 0.30, description: '自由度数' },
      fingertip_force: { weight: 0.25, description: '指尖力' },
      grip_types: { weight: 0.20, description: '支持抓取类型' },
      size_weight: { weight: 0.15, description: '尺寸重量' },
      cost: { weight: 0.10, description: '成本' }
    },
    
    focus_categories: {
      actuators: {
        focus_types: ['微型伺服', '直线电机', '形状记忆合金'],
        key_specs: ['force', 'stroke', 'size', 'weight'],
        ideal_fingertip_force: '5-50N',
        ideal_dof: '12-20'
      },
      sensors: {
        focus_types: ['触觉传感器', '力传感器', '位置传感器'],
        key_specs: ['tactile_resolution', 'force_accuracy', 'response_time'],
        critical_sensors: ['指尖触觉传感器', '关节位置传感器']
      },
      chips: {
        focus_types: ['嵌入式控制器', 'FPGA'],
        key_specs: ['channels', 'real_time', 'power_consumption'],
        required_features: ['多通道PWM', '实时控制', '低功耗']
      }
    },
    
    compatibility_rules: {
      dexterous_hand_specific: [
        {
          name: '自由度匹配',
          description: '检查执行器数量是否满足自由度需求',
          check: (actuators, requirements) => {
            return actuators.length >= (requirements.dof || 12);
          }
        },
        {
          name: '指尖力匹配',
          description: '检查执行器力是否满足抓取需求',
          check: (actuator, specs, requirements) => {
            const force = parseFloat(specs.force) || 0;
            return force >= (requirements.fingertip_force || 5);
          }
        }
      ]
    },
    
    recommendation_strategy: {
      prioritize: ['dof', 'fingertip_force', 'size'],
      avoid: ['high_power', 'low_reliability'],
      budget_allocation: {
        actuators: 0.50,
        sensors: 0.25,
        chips: 0.15,
        others: 0.10
      }
    }
  },
  
  // 移动机器人方言
  mobile_robot: {
    id: 'mobile_robot',
    name: '移动机器人场景',
    description: '适用于AMR、AGV等移动机器人，关注导航、避障、续航',
    version: '1.0.0',
    
    evaluation_dimensions: {
      navigation_accuracy: { weight: 0.25, description: '导航精度' },
      obstacle_avoidance: { weight: 0.20, description: '避障能力' },
      battery_life: { weight: 0.20, description: '续航时间' },
      payload: { weight: 0.15, description: '承载能力' },
      cost: { weight: 0.10, description: '成本' },
      ros_support: { weight: 0.10, description: 'ROS2支持' }
    },
    
    focus_categories: {
      actuators: {
        focus_types: ['轮毂电机', '伺服电机'],
        key_specs: ['torque', 'speed', 'efficiency'],
        ideal_type: '轮毂电机或差速驱动'
      },
      sensors: {
        focus_types: ['激光雷达', 'IMU', '摄像头', '超声波'],
        key_specs: ['range', 'accuracy', 'update_rate'],
        critical_sensors: ['激光雷达', 'IMU', '轮式编码器']
      },
      chips: {
        focus_types: ['计算平台', '导航控制器'],
        key_specs: ['compute_power', 'gpu', 'interfaces'],
        required_interfaces: ['Ethernet', 'USB', 'CAN']
      }
    },
    
    recommendation_strategy: {
      prioritize: ['navigation_accuracy', 'battery_life', 'ros_support'],
      avoid: ['high_power_consumption', 'poor_reliability'],
      budget_allocation: {
        actuators: 0.30,
        sensors: 0.30,
        chips: 0.25,
        others: 0.15
      }
    }
  },
  
  // 科研教育方言
  research: {
    id: 'research',
    name: '科研教育场景',
    description: '适用于高校科研和教育机器人，关注可扩展性、文档、社区支持',
    version: '1.0.0',
    
    evaluation_dimensions: {
      documentation: { weight: 0.25, description: '文档质量' },
      community_support: { weight: 0.20, description: '社区支持' },
      extensibility: { weight: 0.20, description: '可扩展性' },
      ease_of_use: { weight: 0.15, description: '易用性' },
      cost: { weight: 0.10, description: '成本' },
      educational_value: { weight: 0.10, description: '教育价值' }
    },
    
    focus_categories: {
      actuators: {
        focus_types: ['伺服电机', '舵机'],
        key_specs: ['ease_of_use', 'documentation', 'community'],
        ideal_features: ['Arduino兼容', 'ROS2支持', '开源']
      },
      sensors: {
        focus_types: ['IMU', '摄像头', '超声波'],
        key_specs: ['ease_of_use', 'documentation', 'price'],
        ideal_features: ['即插即用', '详细文档', '低价格']
      },
      chips: {
        focus_types: ['开发板', '单板计算机'],
        key_specs: ['community', 'documentation', 'interfaces'],
        ideal_features: ['Raspberry Pi', 'Arduino', 'ESP32']
      }
    },
    
    recommendation_strategy: {
      prioritize: ['documentation', 'community_support', 'ease_of_use'],
      avoid: ['proprietary_protocols', 'poor_documentation'],
      budget_allocation: {
        actuators: 0.35,
        sensors: 0.25,
        chips: 0.20,
        others: 0.20
      }
    }
  }
};

// ============================================================
// 方言管理器
// ============================================================

class DialectManager {
  constructor() {
    this.dialects = { ...DIALECT_TEMPLATES };
    this.loadCustomDialects();
  }
  
  /**
   * 加载自定义方言
   */
  loadCustomDialects() {
    try {
      if (existsSync(DIALECTS_DIR)) {
        const files = readdirSync(DIALECTS_DIR).filter(f => f.endsWith('.json'));
        for (const file of files) {
          const dialect = JSON.parse(readFileSync(join(DIALECTS_DIR, file), 'utf-8'));
          if (dialect.id) {
            this.dialects[dialect.id] = dialect;
          }
        }
      }
    } catch (error) {
      console.warn('加载自定义方言失败:', error.message);
    }
  }
  
  /**
   * 获取方言
   */
  getDialect(dialectId) {
    return this.dialects[dialectId] || null;
  }
  
  /**
   * 列出所有方言
   */
  listDialects() {
    return Object.values(this.dialects).map(d => ({
      id: d.id,
      name: d.name,
      description: d.description,
      version: d.version
    }));
  }
  
  /**
   * 根据应用场景自动选择方言
   */
  selectDialectForApplication(application) {
    const appToDialect = {
      'humanoid': 'humanoid',
      'quadruped': 'mobile_robot',
      'robot_arm': 'industrial',
      'amr': 'mobile_robot',
      'industrial': 'industrial',
      'dexterous_hand': 'dexterous_hand',
      'research': 'research',
      'education': 'research'
    };
    
    return this.dialects[appToDialect[application]] || this.dialects.research;
  }
  
  /**
   * 应用方言进行零部件评价
   */
  evaluateComponent(component, category, dialectId, requirements = {}) {
    const dialect = this.dialects[dialectId];
    if (!dialect) {
      return { error: `方言 ${dialectId} 不存在` };
    }
    
    const evaluation = {
      component_id: component.id,
      component_name: component.name,
      category: category,
      dialect: dialectId,
      scores: {},
      total_score: 0,
      recommendations: []
    };
    
    // 获取该品类的关注点
    const focus = dialect.focus_categories[category];
    if (!focus) {
      evaluation.note = `方言 ${dialectId} 未定义对 ${category} 品类的关注点`;
      return evaluation;
    }
    
    // 计算各维度得分
    // 【20260909-24】审查采纳 P0-2 修复两处硬伤：
    // ① 维度名对齐——模板 evaluation_dimensions 用的是 joint_freedom /
    //    torque_distribution / weight_size 等场景化维度名，旧 switch 只认
    //    torque/weight/cost 等原型名，导致除 cost 外几乎全部维度落入
    //    default 打 50 分伪分。改为先按维度名语义归类再算分。
    // ② 权重归一化——旧 total_score 直接求和已乘权重的分，自定义方言
    //    权重和不为 1 时总分膨胀/收缩。改为 Σ(score_i×w_i)/Σw_i。
    const dimensions = dialect.evaluation_dimensions;
    const dimNames = Object.keys(dimensions);
    // 【20260909-24】库存实体规格是平铺字段（component.torque），key_specs 层
    // 仅部分实体有。统一走 spec() 兼容两层读取，避免读错层打出伪 0 分。
    const ks = component.key_specs || {};
    const spec = (k) => (ks[k] !== undefined ? ks[k] : component[k]);
    const normText = [
      component.name, component.type, component.description,
      JSON.stringify(ks), JSON.stringify(component.applications || [])
    ].filter(Boolean).join(' ').toLowerCase();

    for (const dim of dimNames) {
      const config = dimensions[dim];
      let score;

      switch (dim) {
        // —— 原型维度名（向后兼容自定义方言）——
        case 'torque':
        case 'force':
        case 'fingertip_force': {
          const force = parseFloat(spec('torque') || spec('force')) || 0;
          const ideal = parseFloat(focus.ideal_torque_range?.split('-')[1] || focus.ideal_fingertip_force?.split('-')[1] || 10);
          score = Math.min(100, (force / ideal) * 100);
          break;
        }
        case 'weight':
        case 'weight_size':
        case 'size_weight': {
          const weight = parseFloat(spec('weight')) || 0;
          score = weight > 0 ? Math.max(0, 100 - weight) : 50;
          break;
        }
        case 'accuracy':
        case 'repeatability':
        case 'navigation_accuracy': {
          const accuracy = parseFloat(spec('accuracy')) || 0;
          score = accuracy > 0 ? Math.min(100, (1 / accuracy) * 100) : 50;
          break;
        }
        case 'cost': {
          const price = component.price_range || '';
          const priceNum = parseFloat(price.replace(/[^0-9.]/g, '')) || 0;
          score = priceNum > 0 ? Math.max(0, 100 - priceNum / 100) : 50;
          break;
        }
        // —— 场景化维度名（内置模板实际使用的名字）：按语义可依据的归类 ——
        case 'joint_freedom':
        case 'degrees_of_freedom': {
          // 自由度：能从规格里读出就按规格打分，读不出算证据不足而非伪 50 分
          const dof = parseFloat(spec('dof') || spec('degrees_of_freedom')) || 0;
          const ideal = parseFloat(focus.ideal_dof?.split('-')[1]) || 0;
          score = ideal > 0 ? Math.min(100, (dof / ideal) * 100) : (dof > 0 ? Math.min(100, dof * 5) : null);
          break;
        }
        case 'torque_distribution': {
          const torque = parseFloat(spec('torque') || spec('rated_torque')) || 0;
          const ideal = parseFloat(focus.ideal_torque_range?.split('-')[1]) || 0;
          score = ideal > 0 ? Math.min(100, (torque / ideal) * 100) : (torque > 0 ? 80 : null);
          break;
        }
        case 'documentation':
        case 'community_support':
        case 'extensibility':
        case 'ease_of_use':
        case 'educational_value':
        case 'balance_control':
        case 'power_efficiency':
        case 'obstacle_avoidance':
        case 'battery_life':
        case 'payload':
        case 'reach':
        case 'speed':
        case 'safety':
        case 'grip_types':
        case 'ros_support': {
          // 这些维度库内无结构化字段：改为证据匹配——关键词在实体文本里
          // 命中按命中打分，完全不命中返回 null（不计入总分）而不是伪 50 分。
          const kw = {
            ros_support: ['ros2', 'ros', '机器人操作系统'],
            documentation: ['文档', 'documentation', 'datasheet', '手册'],
            community_support: ['社区', 'community', '开源', 'open source'],
            ease_of_use: ['即插即用', 'easy', 'arduino', '开箱'],
            safety: ['安全', 'safety', 'collaborative', '协作'],
            payload: ['负载', 'payload']
          }[dim];
          // ros_support 等库内是布尔字段，直接读；再退回关键词匹配。
          const boolField = { ros_support: 'ros_support', safety: 'safety_certified' }[dim];
          const boolHit = boolField !== undefined && spec(boolField) === true;
          if (boolHit || (kw && kw.some(k => normText.includes(k)))) {
            score = 75;
          } else if (kw || boolField) {
            score = null; // 无证据：不假装会打分
          } else {
            score = null;
          }
          break;
        }
        default:
          score = null; // 未知维度：明确不计分，绝不冒充 50 分
      }

      evaluation.scores[dim] = {
        // score=null 表示「库内无证据，本维度不计分」，调用方可据此追问厂商
        score: score === null ? null : Math.round(score * 100) / 100,
        weighted: score === null ? null : Math.round(score * config.weight * 100) / 100,
        weight: config.weight,
        description: config.description
      };
    }

    // 总分 = Σ(维度分×权重)/Σ权重：权重和不规范的自定义方言也不会膨胀收缩。
    const scored = Object.values(evaluation.scores).filter(s => s.score !== null);
    const weightSum = scored.reduce((sum, s) => sum + s.weight, 0);
    evaluation.total_score = weightSum > 0
      ? Math.round(scored.reduce((sum, s) => sum + s.weighted, 0) / weightSum * 100) / 100
      : 0;
    evaluation.scored_dimensions = scored.length;
    evaluation.unscored_dimensions = dimNames.length - scored.length;
    if (evaluation.unscored_dimensions > 0) {
      evaluation.evidence_note =
        `${evaluation.unscored_dimensions} 个维度因库内无对应结构化字段未计分（不冒充 50 分）；` +
        `总分仅基于 ${scored.length} 个有证据维度加权。`;
    }
    
    // 生成推荐
    if (evaluation.total_score >= 70) {
      evaluation.recommendations.push('强烈推荐：该零部件非常适合此场景');
    } else if (evaluation.total_score >= 50) {
      evaluation.recommendations.push('推荐：该零部件适合此场景');
    } else if (evaluation.total_score >= 30) {
      evaluation.recommendations.push('一般：该零部件可用于此场景，但有更好选择');
    } else {
      evaluation.recommendations.push('不推荐：该零部件不太适合此场景');
    }
    
    return evaluation;
  }
  
  /**
   * 根据方言推荐零部件组合
   */
  recommendConfiguration(dialectId, application, budget, count = 3) {
    const dialect = this.dialects[dialectId];
    if (!dialect) {
      return { error: `方言 ${dialectId} 不存在` };
    }
    
    // 获取典型配置
    const typicalConfig = dialect.typical_configs?.[0];
    
    // 预算分配
    const allocation = dialect.recommendation_strategy.budget_allocation;
    const budgetPerCategory = {};
    
    for (const [category, ratio] of Object.entries(allocation)) {
      budgetPerCategory[category] = budget * ratio;
    }
    
    return {
      dialect: dialectId,
      application: application,
      total_budget: budget,
      budget_allocation: budgetPerCategory,
      typical_config: typicalConfig,
      focus_dimensions: dialect.evaluation_dimensions,
      recommendation_strategy: dialect.recommendation_strategy
    };
  }
  
  /**
   * 创建自定义方言
   */
  createDialect(dialectDef) {
    if (!dialectDef.id) {
      return { error: '方言定义缺少 id 字段' };
    }
    
    if (this.dialects[dialectDef.id]) {
      return { error: `方言 ${dialectDef.id} 已存在` };
    }
    
    // 验证必要字段
    const required = ['name', 'description', 'evaluation_dimensions', 'focus_categories'];
    for (const field of required) {
      if (!dialectDef[field]) {
        return { error: `方言定义缺少 ${field} 字段` };
      }
    }
    
    this.dialects[dialectDef.id] = dialectDef;
    
    // 保存到文件
    try {
      if (!existsSync(DIALECTS_DIR)) {
        mkdirSync(DIALECTS_DIR, { recursive: true });
      }
      writeFileSync(
        join(DIALECTS_DIR, `${dialectDef.id}.json`),
        JSON.stringify(dialectDef, null, 2)
      );
    } catch (error) {
      console.warn('保存方言文件失败:', error.message);
    }
    
    return { success: true, dialect_id: dialectDef.id };
  }
}

// ============================================================
// 导出单例实例
// ============================================================

const dialectManager = new DialectManager();

export {
  dialectManager,
  DIALECT_TEMPLATES,
  DialectManager
};

export default dialectManager;