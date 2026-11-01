#!/usr/bin/env python3
"""
P2-8 跨引擎回放一致性校验
职责：对齐 compose-workbench.html 的 verifyReplayAgainstEngine，用 Python compose 引擎交叉校验导入事件流中的 verdict_computed

逻辑：
1. 从事件流提取 verdict_computed 事件
2. 对每个事件，用 Python compose 引擎重新计算 verdict
3. 与事件中的 verdict 对比，检测真缺陷（同输入不同结论）
4. 与 verify_cross_engine.py 互补：后者用 golden 静态集，这里用动态事件流

入口：python scripts/verify_cross_engine_replay.py [事件流文件路径]
"""

import sys
import json
import os
from pathlib import Path
import traceback

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入 compose 引擎
from scripts.compose_core import compose

# 事件类型定义
EVENT_TYPES = {
    'requirement.updated': { 'label': '需求更新' },
    'candidate.proposed': { 'label': '候选提出' },
    'verdict.computed': { 'label': '裁决计算' },
    'human.approved': { 'label': '人工批准' },
    'revision.frozen': { 'label': '版本冻结' }
}

def norm_verdict(v):
    """归一化三态：compatible / incompatible / unknown（对齐 compose-workbench.html）"""
    if v is None or v == '':
        return 'unknown'
    s = str(v).lower()
    if s in ['true', 'yes', '1', 'compatible']:
        return 'compatible'
    if 'incompatible' in s or s in ['false', 'no', '0']:
        return 'incompatible'
    return 'unknown'

def validate_events(events):
    """结构校验（对齐 compose-workbench.html）"""
    errors = []
    seen = {}
    for i, ev in enumerate(events):
        tag = f'#{i + 1}'
        if not ev or not isinstance(ev, dict):
            errors.append(f'{tag} 不是对象')
            continue
        if not ev.get('trace_id') or not isinstance(ev['trace_id'], str):
            errors.append(f'{tag} trace_id 缺失')
        elif ev['trace_id'] in seen:
            errors.append(f'{tag} trace_id 重复: {ev["trace_id"]}')
        else:
            seen[ev['trace_id']] = True
        if not ev.get('type') or not isinstance(ev['type'], str):
            errors.append(f'{tag} type 缺失')
        elif ev['type'] not in EVENT_TYPES:
            errors.append(f'{tag} type 未知: {ev["type"]}')
        if not ev.get('ts') or not _is_valid_iso(ev['ts']):
            errors.append(f'{tag} ts 非法 ISO')
        payload = ev.get('payload')
        if payload is not None and (not isinstance(payload, dict) or payload is None):
            errors.append(f'{tag} payload 需为对象')
    return {'ok': len(errors) == 0, 'errors': errors}

def _is_valid_iso(ts_str):
    """检查是否为合法 ISO 格式"""
    try:
        import datetime
        datetime.datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return True
    except:
        return False

def load_event_stream(file_path):
    """加载事件流文件（支持 JSON 数组、{schema,events}、NDJSON）"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # 1. NDJSON：多行，每行一个 JSON 对象
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        if len(lines) > 1 and all(l.startswith('{') for l in lines):
            events = []
            for line in lines:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"NDJSON 解析失败: {e}")
                    return None
            return events
        
        # 2. JSON：数组 或 {schema, events} 包裹
        try:
            obj = json.loads(content)
            if isinstance(obj, list):
                return obj
            if isinstance(obj, dict) and 'events' in obj and isinstance(obj['events'], list):
                return obj['events']
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            return None
        
        print("无法识别的事件流格式")
        return None
        
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None

def main():
    print("🔍 P2-8 跨引擎回放一致性校验")
    print("=" * 50)
    
    if len(sys.argv) != 2:
        print("用法: python scripts/verify_cross_engine_replay.py <事件流文件路径>")
        return 1
    
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return 1
    
    # 加载并校验事件流
    events = load_event_stream(file_path)
    if events is None:
        print("❌ 事件流加载失败")
        return 1
    
    # 结构校验
    validation = validate_events(events)
    if not validation['ok']:
        print("❌ 事件流结构校验失败:")
        for error in validation['errors']:
            print(f"  {error}")
        return 1
    
    print(f"✅ 事件流加载成功: {len(events)} 条事件")
    
    # 提取 verdict_computed 事件
    verdict_events = [ev for ev in events if ev.get('type') == 'verdict_computed']
    print(f"📝 verdict_computed 事件: {len(verdict_events)} 条")
    
    if len(verdict_events) == 0:
        print("⚠️ 无裁决事件，跳过校验")
        return 0
    
    # 初始化 compose 引擎
    try:
        engine = ComposeEngine()
    except Exception as e:
        print(f"❌ compose 引擎初始化失败: {e}")
        traceback.print_exc()
        return 1
    
    # 逐个校验 verdict
    mismatched = []
    engine_errors = []
    
    for ev in verdict_events:
        payload = ev.get('payload', {})
        trace_id = ev.get('trace_id', 'unknown')
        
        # 检查必需字段
        if 'a' not in payload or 'b' not in payload:
            mismatched.append({
                'trace_id': trace_id,
                'reason': '缺少 a/b 无法校验',
                'payload': payload
            })
            continue
        
        try:
            # 用 Python compose 引擎重新计算
            a = payload['a']
            b = payload['b']
            
            # 注意：这里需要和 compose-workbench.html 保持一致，只取 verdict
            result = engine.judgePair(a, b)
            actual = norm_verdict(result.get('verdict', result.get('result', result.get('compatible'))))
            
            # 对比事件中的 verdict
            expected = norm_verdict(payload.get('verdict'))
            
            if expected != actual:
                mismatched.append({
                    'trace_id': trace_id,
                    'a': a,
                    'b': b,
                    'expected': expected,
                    'actual': actual,
                    'event_verdict': payload.get('verdict'),
                    'engine_verdict': result.get('verdict')
                })
                
        except Exception as e:
            engine_errors.append({
                'trace_id': trace_id,
                'error': str(e),
                'payload': payload
            })
    
    # 输出结果
    print()
    if len(mismatched) == 0 and len(engine_errors) == 0:
        print(f"✅ 跨引擎回放一致性通过: {len(verdict_events)} 条裁决均与 Python compose 引擎一致")
        return 0
    else:
        if len(mismatched) > 0:
            print(f"❌ 检测到 {len(mismatched)} 处真缺陷（同输入不同结论）:")
            for mm in mismatched:
                print(f"  📍 {mm['trace_id']}: 期望 {mm['expected']} / 实际 {mm['actual']}")
                if mm.get('event_verdict') is not None:
                    print(f"     事件 verdict: {mm['event_verdict']}")
                if mm.get('engine_verdict') is not None:
                    print(f"     引擎 verdict: {mm['engine_verdict']}")
        
        if len(engine_errors) > 0:
            print(f"⚠️ 引擎计算错误 {len(engine_errors)} 处:")
            for err in engine_errors:
                print(f"  📍 {err['trace_id']}: {err['error']}")
        
        print(f"\n 判定: FAIL（真缺陷 {len(mismatched)} + 引擎错误 {len(engine_errors)}）")
        return 1

if __name__ == "__main__":
    sys.exit(main())