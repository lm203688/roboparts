/**
 * RoboParts 信誉积分系统
 * 
 * 参考：枢衡集群的CAD信誉账本 + 智能体蜂群的信誉机制
 * 
 * 核心功能：
 * 1. 记录每个数据源/Agent的信誉积分
 * 2. 根据数据质量行为进行加分/扣分
 * 3. 信誉分影响数据可信度权重
 * 4. 支持信誉查询和审计日志
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPUTATION_FILE = join(__dirname, '..', 'api', 'reputation_ledger.json');
const AUDIT_LOG_FILE = join(__dirname, '..', 'api', 'audit_log.json');

// ============================================================
// 信誉规则配置
// ============================================================

const REPUTATION_RULES = {
  // 初始分值
  INITIAL_SCORE: 100,
  
  // 扣分规则
  PENALTIES: {
    // 致命错误：捏造数据、虚构事实、伪造引用源
    FATAL_HALLUCINATION: -15,
    // 逻辑跳跃：缺乏证据支撑的断言
    LOGIC_JUMP: -10,
    // 边界越权：角色职责范围外的操作
    BOUNDARY_VIOLATION: -5,
    // 数据不一致：同一实体在不同文件中数据不一致
    DATA_INCONSISTENCY: -8,
    // 格式违规：数据格式不符合规范
    FORMAT_VIOLATION: -3,
    // 重复数据：同一实体重复出现
    DUPLICATE_DATA: -5
  },
  
  // 加分规则
  BONUSES: {
    // 盲区击穿：挖掘反共识但被数据证实的关键弱信号
    BLIND_SPOT_BREAKTHROUGH: +10,
    // 完美抗压：在极限压力测试下无明显破绽
    PERFECT_RESISTANCE: +5,
    // 涌现重构：基于事实提出创新且逻辑闭环的新方案
    EMERGENT_RECONSTRUCTION: +5,
    // 数据贡献：贡献高质量新实体数据
    DATA_CONTRIBUTION: +8,
    // 错误发现：发现并报告数据错误
    ERROR_DISCOVERY: +6,
    // 格式改进：改进数据格式和规范
    FORMAT_IMPROVEMENT: +3
  },
  
  // 阈值机制
  THRESHOLDS: {
    HIGH_TRUST: 120,      // 高度信任：输出享有更高优先级
    NORMAL: 80,           // 正常：标准流程
    WARNING: 60,          // 警告：触发强制复盘
    CRITICAL: 40          // 逻辑熔断：重置当前节点
  }
};

// ============================================================
// 信誉账本管理
// ============================================================

class ReputationLedger {
  constructor() {
    this.ledger = this.loadLedger();
    this.auditLog = this.loadAuditLog();
  }
  
  /**
   * 加载信誉账本
   */
  loadLedger() {
    try {
      if (existsSync(REPUTATION_FILE)) {
        const data = readFileSync(REPUTATION_FILE, 'utf-8');
        return JSON.parse(data);
      }
    } catch (error) {
      console.warn('信誉账本加载失败，使用默认账本:', error.message);
    }
    
    // 默认账本结构
    return {
      meta: {
        version: '1.0.0',
        created_at: new Date().toISOString(),
        last_updated: new Date().toISOString(),
        total_agents: 0,
        average_score: REPUTATION_RULES.INITIAL_SCORE
      },
      agents: {},
      summary: {
        high_trust: 0,
        normal: 0,
        warning: 0,
        critical: 0
      }
    };
  }
  
  /**
   * 加载审计日志
   */
  loadAuditLog() {
    try {
      if (existsSync(AUDIT_LOG_FILE)) {
        const data = readFileSync(AUDIT_LOG_FILE, 'utf-8');
        return JSON.parse(data);
      }
    } catch (error) {
      console.warn('审计日志加载失败，使用默认日志:', error.message);
    }
    
    return {
      meta: {
        version: '1.0.0',
        created_at: new Date().toISOString(),
        total_entries: 0
      },
      entries: []
    };
  }
  
  /**
   * 保存信誉账本
   */
  saveLedger() {
    try {
      this.ledger.meta.last_updated = new Date().toISOString();
      writeFileSync(REPUTATION_FILE, JSON.stringify(this.ledger, null, 2));
    } catch (error) {
      console.error('保存信誉账本失败:', error.message);
    }
  }
  
  /**
   * 保存审计日志
   */
  saveAuditLog() {
    try {
      this.auditLog.meta.total_entries = this.auditLog.entries.length;
      writeFileSync(AUDIT_LOG_FILE, JSON.stringify(this.auditLog, null, 2));
    } catch (error) {
      console.error('保存审计日志失败:', error.message);
    }
  }
  
  /**
   * 获取或创建Agent信誉记录
   */
  getOrCreateAgent(agentId, agentType = 'unknown') {
    if (!this.ledger.agents[agentId]) {
      this.ledger.agents[agentId] = {
        id: agentId,
        type: agentType,
        score: REPUTATION_RULES.INITIAL_SCORE,
        history: [],
        created_at: new Date().toISOString(),
        last_active: new Date().toISOString(),
        total_actions: 0,
        positive_actions: 0,
        negative_actions: 0
      };
      this.ledger.meta.total_agents++;
    }
    
    this.ledger.agents[agentId].last_active = new Date().toISOString();
    return this.ledger.agents[agentId];
  }
  
  /**
   * 记录信誉变动
   */
  recordChange(agentId, changeType, reason, details = {}) {
    const agent = this.getOrCreateAgent(agentId, details.agent_type || 'unknown');
    
    // 确定分值变动
    let scoreChange = 0;
    let category = '';
    
    if (REPUTATION_RULES.PENALTIES[changeType] !== undefined) {
      scoreChange = REPUTATION_RULES.PENALTIES[changeType];
      category = 'penalty';
    } else if (REPUTATION_RULES.BONUSES[changeType] !== undefined) {
      scoreChange = REPUTATION_RULES.BONUSES[changeType];
      category = 'bonus';
    } else {
      console.warn(`未知的信誉变动类型: ${changeType}`);
      return null;
    }
    
    // 更新分值
    const oldScore = agent.score;
    agent.score = Math.max(0, agent.score + scoreChange);
    agent.total_actions++;
    
    if (scoreChange > 0) {
      agent.positive_actions++;
    } else if (scoreChange < 0) {
      agent.negative_actions++;
    }
    
    // 记录历史
    const record = {
      timestamp: new Date().toISOString(),
      change_type: changeType,
      category: category,
      score_change: scoreChange,
      old_score: oldScore,
      new_score: agent.score,
      reason: reason,
      details: details
    };
    
    agent.history.push(record);
    
    // 记录审计日志
    this.auditLog.entries.push({
      agent_id: agentId,
      ...record
    });
    
    // 保存
    this.saveLedger();
    this.saveAuditLog();
    
    return record;
  }
  
  /**
   * 获取Agent信誉状态
   */
  getAgentStatus(agentId) {
    const agent = this.ledger.agents[agentId];
    if (!agent) {
      return null;
    }
    
    let status = 'normal';
    if (agent.score >= REPUTATION_RULES.THRESHOLDS.HIGH_TRUST) {
      status = 'high_trust';
    } else if (agent.score >= REPUTATION_RULES.THRESHOLDS.NORMAL) {
      status = 'normal';
    } else if (agent.score >= REPUTATION_RULES.THRESHOLDS.WARNING) {
      status = 'warning';
    } else {
      status = 'critical';
    }
    
    return {
      id: agent.id,
      type: agent.type,
      score: agent.score,
      status: status,
      total_actions: agent.total_actions,
      positive_actions: agent.positive_actions,
      negative_actions: agent.negative_actions,
      created_at: agent.created_at,
      last_active: agent.last_active,
      recent_history: agent.history.slice(-10) // 最近10条记录
    };
  }
  
  /**
   * 获取全局信誉统计
   */
  getGlobalStats() {
    const agents = Object.values(this.ledger.agents);
    
    // 重新计算统计
    const stats = {
      high_trust: 0,
      normal: 0,
      warning: 0,
      critical: 0
    };
    
    let totalScore = 0;
    
    for (const agent of agents) {
      totalScore += agent.score;
      
      if (agent.score >= REPUTATION_RULES.THRESHOLDS.HIGH_TRUST) {
        stats.high_trust++;
      } else if (agent.score >= REPUTATION_RULES.THRESHOLDS.NORMAL) {
        stats.normal++;
      } else if (agent.score >= REPUTATION_RULES.THRESHOLDS.WARNING) {
        stats.warning++;
      } else {
        stats.critical++;
      }
    }
    
    this.ledger.summary = stats;
    this.ledger.meta.average_score = agents.length > 0 ? totalScore / agents.length : REPUTATION_RULES.INITIAL_SCORE;
    
    return {
      meta: this.ledger.meta,
      summary: stats,
      average_score: this.ledger.meta.average_score,
      total_agents: agents.length
    };
  }
  
  /**
   * 获取审计日志（支持过滤）
   */
  getAuditLog(filters = {}) {
    let entries = [...this.auditLog.entries];
    
    // 按Agent ID过滤
    if (filters.agent_id) {
      entries = entries.filter(e => e.agent_id === filters.agent_id);
    }
    
    // 按变动类型过滤
    if (filters.change_type) {
      entries = entries.filter(e => e.change_type === filters.change_type);
    }
    
    // 按类别过滤（penalty/bonus）
    if (filters.category) {
      entries = entries.filter(e => e.category === filters.category);
    }
    
    // 按时间范围过滤
    if (filters.start_time) {
      entries = entries.filter(e => new Date(e.timestamp) >= new Date(filters.start_time));
    }
    if (filters.end_time) {
      entries = entries.filter(e => new Date(e.timestamp) <= new Date(filters.end_time));
    }
    
    // 按数量限制
    const limit = filters.limit || 100;
    entries = entries.slice(-limit);
    
    return {
      meta: this.auditLog.meta,
      filtered_count: entries.length,
      entries: entries
    };
  }
}

// ============================================================
// 导出单例实例
// ============================================================

const reputationLedger = new ReputationLedger();

export {
  reputationLedger,
  REPUTATION_RULES,
  ReputationLedger
};

export default reputationLedger;