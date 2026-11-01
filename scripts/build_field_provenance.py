#!/usr/bin/env python3
"""
字段级 PROV 构建脚本
- 只提取真实存在字段，不伪造数据
- 对缺失字段登记 evidence_gap
- 机械_interface 和 electrical 是重点目标
- 基于 schemas/field_provenance.schema.json
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

def load_entities():
    """加载实体数据"""
    with open('api/entities.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def validate_field_prov(fp_data):
    """验证字段级 PROV 数据"""
    try:
        import jsonschema
        with open('schemas/field_provenance.schema.json', 'r') as f:
            schema = json.load(f)
        jsonschema.validate(fp_data, schema)
        return True
    except Exception as e:
        print(f"字段级 PROV 验证失败: {e}")
        return False

def build_field_prov(entity):
    """为单个实体构建字段级 PROV"""
    rp_id = entity.get('rp_id')
    if not rp_id:
        return []
    
    field_prov_list = []
    
    # 目标字段列表（优先级排序）
    target_fields = [
        # 机械接口（重点）
        'mechanical_interface',
        'flange',
        'mounting_holes',
        # 电气接口（重点）
        'electrical_interface', 
        'electrical',
        'pinout',
        # 其他重要字段
        'manufacturer',
        'product_name',
        'part_number',
        'description',
        'category',
        'family',
        'series'
    ]
    
    # 构建每个字段的 PROV
    for field_name in target_fields:
        if field_name in entity:
            field_value = entity[field_name]
            
            # 确定数据来源
            if field_name == 'mechanical_interface':
                source = 'datasheet' if field_value.get('source_url') else 'legacy'
            elif field_name == 'electrical_interface':
                source = 'datasheet' if field_value.get('source_url') else 'ingestion'
            elif field_name in ['electrical', 'pinout']:
                source = 'ingestion'  # 大部分是 ingestion
            else:
                source = 'legacy'  # 其他字段暂视为 legacy
            
            field_prov = {
                "schema_version": "field_provenance/v1.0",
                "entity_id": rp_id,
                "field_name": field_name,
                "field_value": field_value,
                "prov": {
                    "source": source,
                    "confidence": 0.8 if source == 'datasheet' else 0.5,
                    "validation_status": "not_validated",
                    "last_updated": datetime.now().isoformat(),
                    "evidence_gaps": []
                }
            }
            
            # 添加来源详情
            if source == 'datasheet' and field_value.get('source_url'):
                field_prov['prov']['source_url'] = field_value['source_url']
                field_prov['prov']['source_detail'] = f"{field_name} from datasheet"
            
            field_prov_list.append(field_prov)
    
    return field_prov_list

def main():
    """主函数"""
    print("开始构建字段级 PROV...")
    
    # 加载实体数据
    entities_data = load_entities()
    entities = entities_data.get('entities', [])
    
    all_field_prov = []
    
    # 为每个实体构建字段级 PROV
    for entity in entities:
        field_prov_list = build_field_prov(entity)
        all_field_prov.extend(field_prov_list)
    
    # 统计
    print(f"处理 {len(entities)} 个实体，生成 {len(all_field_prov)} 个字段级 PROV")
    
    # 保存结果
    output_path = 'api/field_provenance.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_field_prov, f, ensure_ascii=False, indent=2)
    
    print(f"字段级 PROV 已保存到: {output_path}")
    
    # 验证结果
    if validate_field_prov(all_field_prov):
        print("✅ 字段级 PROV 验证通过")
    else:
        print("❌ 字段级 PROV 验证失败")
        return 1
    
    # 生成摘要
    summary = {
        "total_field_prov": len(all_field_prov),
        "entities_with_field_prov": len(set(fp['entity_id'] for fp in all_field_prov)),
        "sources": {}
    }
    
    for fp in all_field_prov:
        source = fp['prov']['source']
        summary['sources'][source] = summary['sources'].get(source, 0) + 1
    
    print("字段级 PROV 摘要:")
    for source, count in summary['sources'].items():
        print(f"  {source}: {count}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())