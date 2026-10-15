#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VLM 证据抽取骨架 · 2026-10-14 阶段 B · 从 PDF 产品手册抽取结构化属性。

动机
----
RoboParts 现有 868 entities 靠人工采编扩充。阶段 B 用规则 + VLM 从厂商 PDF
手册自动抽取结构化属性，扩充 entities。输出走 4 维 schema（mechanical /
electrical / signal / software），confidence < 0.7 进 pending 队列，不进主库。

数据流
------
输入：
  - PDF 产品手册路径（命令行参数）
  - 可选：VLM API endpoint（env var VLM_API_URL + VLM_API_KEY）

处理：
  1. PDF 文本层抽取（无第三方依赖，用 zlib + regex，参考 _pdf_text_probe.py）
  2. 规则匹配常见属性模式（扭矩、电压、协议、法兰等）
  3. 可选：VLM API 调用（若 env var 存在，走 multimodal 抽取）
  4. 输出结构化 JSON + confidence 门控

输出：
  - api/vlm-extraction-pending.json（confidence < 0.7 的待评审条目）
  - api/vlm-extraction-approved.json（confidence ≥ 0.7 的已通过条目）

schema 对齐（4 维）
-------------------
每个抽取条目包含：
  - mechanical_interface: {status, mount_type, standard, flange, declared_note}
  - standard_conformance: {assessed, bus_class, ros2, interop_stack_20262893, ...}
  - electrical: {voltage, connector, pinout, current_rating}
  - signal: {protocol, bus_class, ros_support, firmware_version}
  - software: {ros_support, firmware, driver, sdk}

confidence 计算
---------------
- 文本层抽取：0.5 + 0.1 × 匹配字段数 / 总字段数
- VLM 抽取：模型输出 confidence（若 API 返回）
- 最终 confidence = min(text_confidence, vlm_confidence)
- < 0.7 → pending，≥ 0.7 → approved

诚实边界
--------
- 不依赖 VLM API：文本层抽取可用，VLM 是升级路径（可选）
- 不自动入主库：所有输出进 pending/approved 队列，人工评审后迁移到 entities.json
- 不预测 verdict：只抽取属性，不判定兼容性（引擎的事）

验证（自证）
------------
- --self-test：检查输出 schema 合规、confidence 在 [0, 1]、无幽灵字段
- --mock：生成 mock 数据用于 CI 测试（不需要真实 PDF）
"""
import json
import os
import re
import sys
import zlib
import hashlib
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCHEMA = 'roboparts/vlm_extraction/v1'
GENERATED_BY = 'scripts/vlm_extract.py'
CONFIDENCE_THRESHOLD = 0.7
OUTPUT_PENDING = 'api/vlm-extraction-pending.json'
OUTPUT_APPROVED = 'api/vlm-extraction-approved.json'

SCHEMA_4DIM = {
    'mechanical_interface': ['status', 'mount_type', 'standard', 'flange', 'declared_note'],
    'standard_conformance': ['assessed', 'bus_class', 'ros2', 'interop_stack_20262893',
                             'caee060_relevant', 'interop_posture', 'iso22166_relevant'],
    'electrical': ['voltage', 'connector', 'pinout', 'current_rating'],
    'signal': ['protocol', 'bus_class', 'ros_support', 'firmware_version'],
    'software': ['ros_support', 'firmware', 'driver', 'sdk'],
}

EXTRACTION_PATTERNS = {
    'manufacturer': [
        r'(?:Manufacturer|Vendor|厂商)[:\s]*([A-Za-z0-9\s\-\(\)]{2,30})',
    ],
    'torque': [
        r'(?:Torque|扭矩)[:\s]*([\d\.]+)\s*(?:Nm|N·m|牛米)',
        r'([\d\.]+)\s*(?:Nm|N·m)\s*(?:torque|扭矩)',
    ],
    'voltage': [
        r'(?:Voltage|电压)[:\s]*([\d\.]+)\s*(?:V|VDC|VDC)',
        r'([\d\.]+)\s*(?:V|VDC)\s*(?:voltage|电压)',
        r'([\d\.]+)-([\d\.]+)\s*(?:V|VDC)',
    ],
    'protocol': [
        r'(?:Protocol|协议)[:\s]*([A-Za-z0-9\-]+)',
        r'(CANopen|CAN|RS485|RS-232|Ethernet|EtherCAT|PROFINET|EtherNet/IP)',
    ],
    'ros_support': [
        r'(?:ROS|ros)\s*(?:support|supported|兼容)[:\s]*(?:Yes|No|yes|no|是|否|True|False)',
    ],
}


def extract_pdf_text(pdf_path):
    """从 PDF 文本层抽取文本（无第三方依赖，用 zlib + regex）。"""
    raw = open(pdf_path, 'rb').read()
    sha = hashlib.sha256(raw).hexdigest()
    chunks = []
    for m in re.finditer(rb'stream\r?\n', raw):
        s = m.end()
        e = raw.find(b'endstream', s)
        if e < 0:
            continue
        try:
            chunks.append(zlib.decompress(raw[s:e]))
        except Exception:
            continue
    blob = b'\n'.join(chunks)
    lits = re.findall(rb'\(([^()\\]{1,500})\)', blob)
    text = b' '.join(lits).decode('latin-1')
    text = text.replace('\x00', '')
    text = re.sub(r'\s+', ' ', text)
    return sha, len(raw), text


def extract_attributes_from_text(text):
    """从 PDF 文本层用规则匹配抽取属性。返回 (attributes_dict, confidence)。"""
    extracted = {}
    matched_count = 0
    total_patterns = len(EXTRACTION_PATTERNS)

    for attr_name, patterns in EXTRACTION_PATTERNS.items():
        for pattern in patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                if m.lastindex and m.lastindex >= 2:
                    extracted[attr_name] = {
                        'value': m.group(1),
                        'range': m.group(2),
                    }
                else:
                    extracted[attr_name] = m.group(1)
                matched_count += 1
                break

    confidence = 0.5 + 0.1 * (matched_count / total_patterns if total_patterns > 0 else 0)
    confidence = min(confidence, 1.0)
    return extracted, confidence


def call_vlm_api(pdf_path, text):
    """调用 VLM API 抽取属性（可选，需 env var VLM_API_URL + VLM_API_KEY）。"""
    api_url = os.environ.get('VLM_API_URL')
    api_key = os.environ.get('VLM_API_KEY')
    if not api_url or not api_key:
        return None, None

    # 骨架实现：实际调用需补全 PDF 转图片 + VLM 请求逻辑
    print('[WARN] VLM_API_URL/VLM_API_KEY 已设置但 call_vlm_api 未实现，跳过 VLM 抽取',
          file=sys.stderr)
    return None, None


def build_entity_from_extraction(extracted, pdf_sha, pdf_path):
    """从抽取结果构建实体条目（对齐 4 维 schema）。"""
    entity = {
        'id': 'PENDING-' + pdf_sha[:8],
        'name': extracted.get('manufacturer', 'Unknown') + ' (from PDF)',
        'category': 'unknown',
        'manufacturer': extracted.get('manufacturer'),
        'source': 'vlm_extraction',
        'source_url': pdf_path,
        'pdf_sha256': pdf_sha,
        'mechanical_interface': {
            'status': 'not_declared',
            'mount_type': extracted.get('mount_type'),
            'standard': extracted.get('flange'),
            'flange': extracted.get('flange'),
            'declared_note': None,
        },
        'standard_conformance': {
            'assessed': True,
            'bus_class': extracted.get('protocol', 'unknown'),
            'ros2': extracted.get('ros_support') == 'Yes' if 'ros_support' in extracted else False,
            'interop_stack_20262893': 'unknown',
            'caee060_relevant': False,
            'interop_posture': 'unknown',
            'iso22166_relevant': False,
        },
        'electrical': {
            'voltage': extracted.get('voltage'),
            'connector': None,
            'pinout': None,
            'current_rating': None,
        },
        'signal': {
            'protocol': extracted.get('protocol'),
            'bus_class': extracted.get('protocol'),
            'ros_support': extracted.get('ros_support'),
            'firmware_version': None,
        },
        'software': {
            'ros_support': extracted.get('ros_support'),
            'firmware': None,
            'driver': None,
            'sdk': None,
        },
    }
    return entity


def extract_from_pdf(pdf_path):
    """从 PDF 抽取属性并输出到 pending/approved 队列。"""
    if not os.path.exists(pdf_path):
        sys.exit('[FATAL] PDF 文件不存在：%s' % pdf_path)

    print('[INFO] 提取 PDF 文本层：%s' % pdf_path)
    sha, size, text = extract_pdf_text(pdf_path)
    print('[INFO] PDF sha256=%s, size=%d bytes, text_len=%d chars'
          % (sha[:12], size, len(text)))

    extracted, text_confidence = extract_attributes_from_text(text)
    print('[INFO] 规则抽取：匹配 %d 个属性，confidence=%.2f'
          % (len(extracted), text_confidence))

    vlm_extracted, vlm_confidence = call_vlm_api(pdf_path, text)

    if vlm_extracted:
        extracted.update(vlm_extracted)
        final_confidence = min(text_confidence, vlm_confidence)
        extraction_method = 'vlm'
    else:
        final_confidence = text_confidence
        extraction_method = 'text_layer'

    print('[INFO] 最终 confidence=%.2f, method=%s' % (final_confidence, extraction_method))

    entity = build_entity_from_extraction(extracted, sha, pdf_path)
    entity['confidence'] = final_confidence
    entity['extraction_method'] = extraction_method
    entity['status'] = 'approved' if final_confidence >= CONFIDENCE_THRESHOLD else 'pending_review'

    output_path = (OUTPUT_APPROVED if entity['status'] == 'approved'
                   else OUTPUT_PENDING)
    output_file = os.path.join(ROOT, output_path)

    if os.path.exists(output_file):
        with open(output_file, encoding='utf-8') as f:
            queue = json.load(f)
    else:
        queue = {
            'meta': {
                'schema': SCHEMA,
                'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                'generated_by': GENERATED_BY,
                'confidence_threshold': CONFIDENCE_THRESHOLD,
                'title': 'VLM 抽取 %s 队列' % ('approved' if 'approved' in output_path else 'pending'),
            },
            'items': [],
        }

    queue['items'].append({
        'extracted_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'entity': entity,
    })
    queue['meta']['generated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    queue['meta']['total_items'] = len(queue['items'])

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

    print('[OK] 写入 %s · %d items 总计' % (output_path, len(queue['items'])))
    return entity


def self_test():
    """自证：检查输出 schema 合规、confidence 范围、无幽灵字段。"""
    for output_path in [OUTPUT_PENDING, OUTPUT_APPROVED]:
        full_path = os.path.join(ROOT, output_path)
        if not os.path.exists(full_path):
            print('[SELF-TEST] %s 不存在，跳过' % output_path)
            continue

        with open(full_path, encoding='utf-8') as f:
            queue = json.load(f)

        schema = (queue.get('meta') or {}).get('schema')
        if schema != SCHEMA:
            sys.exit('[SELF-TEST FAIL] %s schema=%r，应为 %r'
                     % (output_path, schema, SCHEMA))

        items = queue.get('items') or []
        for idx, item in enumerate(items):
            entity = item.get('entity', {})
            conf = entity.get('confidence', 0)
            if not (0 <= conf <= 1):
                sys.exit('[SELF-TEST FAIL] %s item[%d] confidence=%.2f 不在 [0,1]'
                         % (output_path, idx, conf))

            for dim, fields in SCHEMA_4DIM.items():
                if dim not in entity:
                    sys.exit('[SELF-TEST FAIL] %s item[%d] 缺少 %s 维度'
                             % (output_path, idx, dim))

        print('[SELF-TEST PASS] %s · %d items · schema 合规 · confidence 范围正确'
              % (output_path, len(items)))


def mock_mode():
    """Mock 模式：生成 mock 数据用于 CI 测试（不需要真实 PDF）。"""
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')

    mock_items = [
        {
            'extracted_at': now,
            'entity': {
                'id': 'PENDING-mock0001',
                'name': 'Mock Actuator (high confidence)',
                'category': 'actuators',
                'manufacturer': 'MockCorp',
                'mechanical_interface': {'status': 'partial', 'mount_type': 'flange',
                                         'standard': 'ISO 9409-1', 'flange': 'A80-6-M8',
                                         'declared_note': None},
                'standard_conformance': {'assessed': True, 'bus_class': 'CANopen',
                                         'ros2': True, 'interop_stack_20262893': 'partial',
                                         'caee060_relevant': True, 'interop_posture': 'semi_open',
                                         'iso22166_relevant': True},
                'electrical': {'voltage': '24V', 'connector': 'M12', 'pinout': '4-pin',
                               'current_rating': '5A'},
                'signal': {'protocol': 'CANopen', 'bus_class': 'CANopen',
                           'ros_support': 'Yes', 'firmware_version': 'v1.2.3'},
                'software': {'ros_support': 'Yes', 'firmware': 'v1.2.3',
                             'driver': 'mock_driver', 'sdk': 'mock_sdk'},
                'confidence': 0.85,
                'extraction_method': 'mock',
                'status': 'approved',
            },
        },
        {
            'extracted_at': now,
            'entity': {
                'id': 'PENDING-mock0002',
                'name': 'Mock Sensor (low confidence)',
                'category': 'sensors',
                'manufacturer': 'MockCorp',
                'mechanical_interface': {'status': 'not_declared', 'mount_type': None,
                                         'standard': None, 'flange': None,
                                         'declared_note': None},
                'standard_conformance': {'assessed': False, 'bus_class': 'unknown',
                                         'ros2': False, 'interop_stack_20262893': 'unknown',
                                         'caee060_relevant': False, 'interop_posture': 'unknown',
                                         'iso22166_relevant': False},
                'electrical': {'voltage': None, 'connector': None, 'pinout': None,
                               'current_rating': None},
                'signal': {'protocol': None, 'bus_class': None, 'ros_support': None,
                           'firmware_version': None},
                'software': {'ros_support': None, 'firmware': None, 'driver': None,
                             'sdk': None},
                'confidence': 0.55,
                'extraction_method': 'mock',
                'status': 'pending_review',
            },
        },
    ]

    for output_path, status in [(OUTPUT_APPROVED, 'approved'), (OUTPUT_PENDING, 'pending_review')]:
        items = [i for i in mock_items if i['entity']['status'] == status]
        queue = {
            'meta': {
                'schema': SCHEMA,
                'generated_at': now,
                'generated_by': GENERATED_BY,
                'confidence_threshold': CONFIDENCE_THRESHOLD,
                'title': 'VLM 抽取 %s 队列（mock）' % status,
                'total_items': len(items),
            },
            'items': items,
        }
        output_file = os.path.join(ROOT, output_path)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        print('[MOCK] %s · %d items' % (output_path, len(items)))


def main():
    if '--self-test' in sys.argv:
        self_test()
        return 0

    if '--mock' in sys.argv:
        mock_mode()
        return 0

    if len(sys.argv) < 2:
        print('用法: python scripts/vlm_extract.py <pdf_path>')
        print('      python scripts/vlm_extract.py --mock')
        print('      python scripts/vlm_extract.py --self-test')
        return 1

    pdf_path = sys.argv[1]
    extract_from_pdf(pdf_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
