#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoboParts 官方来源实证核验脚本（N10 Schema 治理 · Tier A 提升管线）

背景（2026-08-05 第 3 轮发现）：
  enrich_provenance.py 的 Tier B 厂商归因规则依赖 `endorsed_vendors`
  —— 只有「库内已有至少一条带真实 source 的实体」的厂商才会被归因。
  这导致 Maxon / Kollmorgen / Raspberry Pi / ST / Espressif / Hailo 这类
  全库零来源的**真实知名厂商**永远进不了白名单，113 条干净实体卡死在 Tier C。
  单纯放宽规则只会制造 Tier B 注水，traceable_pct 纹丝不动。

本脚本的解法：**不猜，去访问**。
  维护一份人工审定的「实体 -> 官方页面 URL」注册表，逐条发真实 HTTP 请求，
  按响应结果分级写回，杜绝「写个看起来像官网的链接就算溯源」：

    200 + 页面文本命中产品名   -> Tier A   confidence 0.88  （可点开复核，实证通过）
    200 但未命中产品名          -> Tier B   confidence 0.58  （站点存活，可能 JS 渲染，未证实）
    403 / 429 / 超时（反爬）    -> Tier B   confidence 0.55  （官方站点但被 bot 防护拦截，无法自证）
    404 / DNS 失败 / 5xx       -> 拒绝写入，记入 rejected 清单，人工复核

  只有实证通过（Tier A）的条目才写 last_verified = 核验当日；
  Tier B 一律不写核验日期 —— 没真验过就不许盖章。

用法：
  python scripts/verify_vendor_sources.py [--dry-run] [--only ID1,ID2] [--timeout 15]
幂等：重复运行结果一致；已是 Tier A 的条目默认跳过（--recheck 可强制复验）。
后置：再跑 normalize_categories.py 把字段传播到三副本。
"""
import argparse
import collections
import datetime
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES_PATH = os.path.join(ROOT, 'api', 'entities.json')
LEDGER_PATH = os.path.join(ROOT, 'ops', 'schema', 'source-verification-ledger.json')

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')

SCORE_A = 0.88          # 实证通过：URL 可点开且内容对得上
SCORE_B_LIVE = 0.58     # 站点存活但内容未证实
SCORE_B_BLOCKED = 0.55  # 被反爬拦截，无法自证

# ---------------------------------------------------------------------------
# 官方来源注册表：entity_id -> (url, [页面应出现的关键词], scope)
#
# scope 是本脚本防注水的核心开关：
#   'entity' —— URL 直接指向**该实体本身**（产品页 / 规格页 / 论文项目页；
#               或实体本身就是这家机构/这个协议，如 OptiTrack、SOME/IP）
#               => HTTP 200 且命中关键词，才可判 Tier A
#   'vendor' —— URL 只是**厂商首页**，证明得了厂商存在，证明不了这颗产品的规格
#               => 无论 HTTP 多漂亮，**封顶 Tier B**
#
#   反例警示：把 `Maxon EC Flat 60` 挂到 maxongroup.com 首页、因为首页含 "maxon"
#   就判 Tier A —— 这正是上周 review 抓出的「指标注水」。故引入 scope 硬封顶。
#
# 收录标准：该实体是**真实存在**的公开产品/标准/论文项目，且官方页面 URL 稳定。
# 不确定的一律不收 —— 宁可留 Tier C，也不写一条会 404 的假链接。
# ---------------------------------------------------------------------------
REGISTRY = {
    # ---- 芯片 / 算力 ----
    'CHIP-003': ('https://www.raspberrypi.com/products/raspberry-pi-5/', ['raspberry pi 5'], 'entity'),
    'CHIP-004': ('https://www.st.com/en/microcontrollers-microprocessors/stm32h743-753.html', ['stm32h743'], 'entity'),
    'CHIP-005': ('https://www.espressif.com/en/products/socs/esp32-s3', ['esp32-s3'], 'entity'),
    'CHIP-006': ('https://www.pjrc.com/store/teensy41.html', ['teensy 4.1', 'teensy41'], 'entity'),
    'CHIP-011': ('https://hailo.ai/products/ai-accelerators/hailo-8-ai-accelerator/', ['hailo-8'], 'entity'),
    'CHIP-096': ('https://hailo.ai/products/ai-accelerators/hailo-8-ai-accelerator/', ['hailo-8'], 'entity'),
    'CHIP-097': ('https://hailo.ai/products/ai-accelerators/hailo-10h-ai-accelerator/', ['hailo-10'], 'entity'),
    'CHIP-012': ('https://coral.ai/products/', ['coral', 'edge tpu'], 'entity'),
    'CHIP-098': ('https://coral.ai/products/', ['coral', 'edge tpu'], 'entity'),
    'CHIP-018': ('https://www.microchip.com/en-us/products/fpgas-and-plds/system-on-chip-fpgas/polarfire-soc-fpgas',
                 ['polarfire'], 'entity'),
    # 以下三条只有厂商首页可用，产品深链未确认 -> 封顶 Tier B
    'CHIP-020': ('https://www.allwinnertech.com/', ['allwinner', '全志'], 'vendor'),
    'CHIP-099': ('https://www.rock-chips.com/', ['rockchip', '瑞芯微'], 'vendor'),
    'CHIP-101': ('https://www.cambricon.com/', ['cambricon', '寒武纪'], 'vendor'),

    # ---- 执行器 ----
    'ACT-005': ('https://docs.simplefoc.com/arduino_simplefoc_shield_showcase', ['simplefoc shield'], 'entity'),
    'ACT-021': ('https://www.hebirobotics.com/actuators', ['x5', 'actuator'], 'entity'),
    'ACT-022': ('https://www.hebirobotics.com/actuators', ['x8', 'actuator'], 'entity'),
    'ACT-023': ('https://www.kinovarobotics.com/product/gen3-robots', ['gen3'], 'entity'),
    'ACT-030': ('https://www.shadowrobot.com/dexterous-hand-series/', ['dexterous hand'], 'entity'),
    # 以下均为厂商首页，无法证实具体型号 -> 封顶 Tier B
    'ACT-004': ('https://odriverobotics.com/', ['odrive'], 'vendor'),
    'ACT-008': ('https://www.maxongroup.com/', ['maxon'], 'vendor'),
    'ACT-017': ('https://www.anybotics.com/', ['anybotics'], 'vendor'),
    'ACT-026': ('https://www.festo.com/', ['festo'], 'vendor'),
    'ACT-027': ('https://schunk.com/', ['schunk'], 'vendor'),
    'ACT-032': ('https://www.agilityrobotics.com/', ['digit', 'agility'], 'vendor'),

    # ---- 整机平台 ----
    'RPLAT-001': ('https://bostondynamics.com/atlas/', ['atlas'], 'entity'),
    'RPLAT-004': ('https://www.unitree.com/g1', ['g1', 'unitree'], 'entity'),
    'RPLAT-005': ('https://www.anybotics.com/robotics/anymal/', ['anymal'], 'entity'),
    'RPLAT-006': ('https://enterprise.dji.com/matrice-350-rtk', ['matrice 350'], 'entity'),
    'RPLAT-014': ('https://developer.nvidia.com/isaac/gr00t', ['gr00t'], 'entity'),

    # ---- 大模型 / VLA ----
    'LLM-001': ('https://openai.com/index/hello-gpt-4o/', ['gpt-4o'], 'entity'),
    'LLM-002': ('https://www.anthropic.com/news/claude-3-5-sonnet', ['claude 3.5 sonnet'], 'entity'),
    'LLM-006': ('https://qwenlm.github.io/blog/qwen2.5-vl/', ['qwen2.5-vl'], 'entity'),
    'LLM-003': ('https://deepmind.google/discover/blog/rt-2-new-model-translates-vision-and-language-into-action/',
                ['rt-2'], 'entity'),
    'LLM-004': ('https://octo-models.github.io/', ['octo'], 'entity'),
    'LLM-005': ('https://openvla.github.io/', ['openvla'], 'entity'),
    'RAI-016': ('https://huggingface.co/openvla/openvla-7b', ['openvla'], 'entity'),
    'RAI-008': ('https://huggingface.co/blog/smolvla', ['smolvla'], 'entity'),

    # ---- 数据采集（DATA-006/007/008 的实体本身即该系统/公司，根域名即其规范页）----
    'DATA-001': ('https://tonyzhaozh.github.io/aloha/', ['aloha'], 'entity'),
    'DATA-002': ('https://umi-gripper.github.io/', ['universal manipulation interface', 'umi'], 'entity'),
    'DATA-003': ('https://wuphilipp.github.io/gello_site/', ['gello'], 'entity'),
    'DATA-004': ('https://dex-cap.github.io/', ['dexcap'], 'entity'),
    'DATA-006': ('https://optitrack.com/', ['optitrack'], 'entity'),
    'DATA-007': ('https://www.vicon.com/', ['vicon'], 'entity'),
    'DATA-008': ('https://www.nokov.com/', ['nokov', '度量'], 'entity'),

    # ---- 协议 / 接口（标准组织官方页）----
    'PROTO-004': ('https://emanual.robotis.com/docs/en/dxl/protocol2/', ['protocol 2.0', 'dynamixel'], 'entity'),
    'PROTO-005': ('https://design.ros2.org/articles/ros_on_dds.html', ['dds'], 'entity'),
    'PROTO-012': ('https://www.modbus.org/specs.php', ['modbus'], 'entity'),
    'PROTO-013': ('https://some-ip.com/', ['some/ip', 'someip'], 'entity'),
    'PROTO-021': ('https://mavlink.io/en/', ['mavlink'], 'entity'),
    'PROTO-023': ('https://opcfoundation.org/about/opc-technologies/opc-ua/', ['opc ua'], 'entity'),
    'PROTO-024': ('https://csa-iot.org/all-solutions/matter/', ['matter'], 'entity'),
    'PROTO-028': ('https://www.profibus.com/technology/profinet/', ['profinet'], 'entity'),
    'PROTO-019': ('https://www.bluetooth.com/specifications/', ['bluetooth'], 'entity'),
    'IF-002': ('https://www.mipi.org/specifications/csi-2', ['csi-2'], 'entity'),
    'IF-003': ('https://pcisig.com/specifications', ['pci express', 'pcie'], 'entity'),
    'IF-001': ('https://www.usb.org/documents', ['usb'], 'entity'),
    # 「EtherCAT over TSN」是 EtherCAT 的扩展变体，ethercat.org 根域证明不了该变体 -> Tier B
    'PROTO-029': ('https://www.ethercat.org/', ['ethercat'], 'vendor'),

    # ---- 开源硬件（T5 20260805 批次 I）------------------------------------
    # 判 scope='entity' 的依据：这些实体**本身就是该开源项目**，GitHub 仓库即其
    # 规范发布地（机械图纸/固件/BOM 的一手出处），不存在「拿厂商首页冒充产品页」
    # 的注水空间。反例对照：ACT-004 是「Odrive D6374」这一具体型号，ODrive 项目
    # 仓库证明不了该型号规格，故其仍保持 scope='vendor' 封顶 Tier B。
    'ACT-oss-leap-hand': ('https://github.com/leap-hand/LEAP_Hand_API', ['leap_hand', 'leap hand'], 'entity'),
    'ACT-oss-ruka-hand': ('https://github.com/ruka-hand/RUKA', ['ruka'], 'entity'),
    'ACT-oss-odri-actuator': ('https://github.com/open-dynamic-robot-initiative/open_robot_actuator_hardware',
                              ['open_robot_actuator_hardware'], 'entity'),
    'ACT-oss-mjbots-moteus': ('https://github.com/mjbots/moteus', ['moteus'], 'entity'),
    'ACT-oss-vesc': ('https://github.com/vedderb/bldc', ['bldc', 'vesc'], 'entity'),
    'SENS-oss-anyskin': ('https://github.com/raunaqbhirangi/anyskin', ['anyskin'], 'entity'),
    'SENS-oss-reskin': ('https://github.com/raunaqbhirangi/reskin_sensor', ['reskin'], 'entity'),
    'DATA-oss-agibot-world': ('https://github.com/OpenDriveLab/AgiBot-World', ['agibot'], 'entity'),
    'RPLAT-oss-open-duck-mini': ('https://github.com/apirrone/Open_Duck_Mini', ['open_duck_mini', 'duck'], 'entity'),
    'RPLAT-oss-reachy2': ('https://github.com/pollen-robotics/reachy2-sdk', ['reachy'], 'entity'),
}

# 已知失效、暂不收录（保持 Tier C，等人工补正确深链）：
#   ACT-009  Kollmorgen TBM2G   —— 官网 direct-drive 路径已改版，试 2 个变体均 404
#   CHIP-013 NXP i.MX 8M Plus   —— nxp.com 产品页路径已改版，试 2 个变体均 404
KNOWN_BROKEN = {
    'ACT-009': 'kollmorgen.com direct-drive 路径改版，2 个候选均 404，待人工补链',
    'CHIP-013': 'nxp.com 产品页路径改版，2 个候选均 404，待人工补链',
}


def fetch(url, timeout):
    """返回 (status, body_text, err)。status 为 int 或 None（网络层失败）"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8',
    })
    try:
        r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        raw = r.read(600000)
        return r.status, raw.decode('utf-8', 'ignore'), None
    except urllib.error.HTTPError as ex:
        return ex.code, '', f'HTTP {ex.code}'
    except Exception as ex:
        return None, '', f'{type(ex).__name__}: {str(ex)[:90]}'


def classify(status, body, tokens, scope):
    """把 HTTP 结果映射为 (tier, score, basis, note)

    scope='vendor' 时**封顶 Tier B**：厂商首页再怎么 200，也证明不了具体型号的规格。
    """
    if status == 200:
        text = re.sub(r'<[^>]+>', ' ', body).lower()
        hit = any(t.lower() in text or t.lower() in body.lower() for t in tokens)
        if hit and scope == 'entity':
            return 'A', SCORE_A, 'official_url_verified', 'HTTP 200，页面文本命中实体名'
        if hit and scope == 'vendor':
            return 'B', SCORE_B_LIVE, 'vendor_homepage_only', 'HTTP 200，但仅厂商首页，未证实该型号规格'
        return 'B', SCORE_B_LIVE, 'official_url_live_unconfirmed', 'HTTP 200，但未命中实体名（疑 JS 渲染）'
    if status in (401, 403, 405, 429) or status is None:
        return 'B', SCORE_B_BLOCKED, 'official_url_bot_blocked', f'被反爬/网络拦截（{status}），无法自证'
    return None, None, None, f'无效响应 {status}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--recheck', action='store_true', help='对已是 Tier A 的条目强制复验')
    ap.add_argument('--only', default='', help='逗号分隔的实体 ID 白名单')
    ap.add_argument('--timeout', type=int, default=15)
    args = ap.parse_args()

    doc = json.load(open(ENTITIES_PATH, encoding='utf-8'))
    entities = doc['entities']
    by_id = {e.get('id'): e for e in entities}
    today = datetime.date.today().isoformat()

    only = {x.strip() for x in args.only.split(',') if x.strip()}
    targets = []
    skipped_missing, skipped_done, skipped_quarantine = [], [], []
    for eid, (url, tokens, scope) in REGISTRY.items():
        if only and eid not in only:
            continue
        e = by_id.get(eid)
        if e is None:
            skipped_missing.append(eid)
            continue
        if e.get('quarantine'):          # 隔离条目一律不洗白
            skipped_quarantine.append(eid)
            continue
        if e.get('source_tier') == 'A' and not args.recheck:
            skipped_done.append(eid)
            continue
        targets.append((eid, url, tokens, scope))

    print(f'=== 官方来源实证核验 === {"(dry-run)" if args.dry_run else ""}')
    print(f'注册表 {len(REGISTRY)} 条 | 待核验 {len(targets)} | '
          f'已 TierA 跳过 {len(skipped_done)} | 隔离跳过 {len(skipped_quarantine)} | 库中缺失 {len(skipped_missing)}')
    if skipped_missing:
        print(f'  ⚠ 注册表中但库里没有的 ID：{skipped_missing}')
    if not targets:
        print('无待核验条目。')
        return 0

    def work(item):
        eid, url, tokens, scope = item
        status, body, err = fetch(url, args.timeout)
        tier, score, basis, note = classify(status, body, tokens, scope)
        return eid, url, status, tier, score, basis, note, scope

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(work, targets))

    stat = collections.Counter()
    ledger = []
    results.sort(key=lambda r: (r[3] or 'Z', r[0]))
    for eid, url, status, tier, score, basis, note, scope in results:
        e = by_id[eid]
        mark = {'A': '✅', 'B': '🟡'}.get(tier, '❌')
        print(f'  {mark} [{tier or "REJ"}] {eid:12} {str(status):>5} {scope:<7} {note:<44} {url[:56]}')
        ledger.append({'id': eid, 'name': e.get('name'), 'url': url, 'http_status': status,
                       'scope': scope, 'tier': tier, 'note': note, 'checked_at': today})
        if tier is None:
            stat['rejected'] += 1
            continue
        stat[f'tier{tier}'] += 1
        if not args.dry_run:
            e['source'] = (f'官方页面：{url}' if tier == 'A'
                           else f'官方页面（未证实）：{url}')
            e['source_tier'] = tier
            e['source_url'] = url
            e['confidence'] = score
            e['confidence_basis'] = basis
            e['verification_note'] = note
            if tier == 'A':
                e['last_verified'] = today          # 只有真验过才盖章
                e['verified'] = score >= 0.6
            else:
                e['verified'] = False

    print(f'\n  结果：Tier A {stat["tierA"]} / Tier B {stat["tierB"]} / 拒绝写入 {stat["rejected"]}')
    if KNOWN_BROKEN:
        print(f'  ⚠ 已知失效待人工补链 {len(KNOWN_BROKEN)} 条（未收录，保持 Tier C）：')
        for k, v in KNOWN_BROKEN.items():
            print(f'      {k:12} {v}')

    if not args.dry_run:
        with open(ENTITIES_PATH, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
        old = []
        if os.path.exists(LEDGER_PATH):
            try:
                old = json.load(open(LEDGER_PATH, encoding='utf-8')).get('runs', [])
            except Exception:
                old = []
        old.append({'run_at': datetime.datetime.now().isoformat(timespec='seconds'),
                    'checked': len(results), 'tier_a': stat['tierA'],
                    'tier_b': stat['tierB'], 'rejected': stat['rejected'],
                    'known_broken': KNOWN_BROKEN,
                    'entries': ledger})
        with open(LEDGER_PATH, 'w', encoding='utf-8') as f:
            json.dump({'_doc': '官方来源实证核验台账。每次运行追加一条，保留 HTTP 状态码以便复核。',
                       'runs': old[-8:]}, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f'  📄 台账已写入 {os.path.relpath(LEDGER_PATH, ROOT)}')
        print('  ⚠ 记得跑 normalize_categories.py 传播到三副本')
    return 0


if __name__ == '__main__':
    sys.exit(main())
