"""
RoboParts — Multi-Factor Selection Engine
==========================================
Replicates the website's smart selection algorithm for actuator matching.

Scoring weights:
  - Torque/Price ratio  : 30%
  - Weight (lightweight): 20%
  - Protocol match      : 25%
  - Bionic features     : 15%
  - Standard compliance : 10%
"""

import json
import re
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "roboparts_full.json"

with open(DATA_PATH, "r", encoding="utf-8") as f:
    DB = json.load(f)


def extract_number(s: str) -> float:
    """Extract first numeric value from a string."""
    if not s:
        return 0.0
    match = re.search(r"[\d.]+", str(s))
    return float(match.group()) if match else 0.0


def score_actuator(act: dict, req_torque: float, req_protocol: str,
                   budget: float = None, bionic_priority: bool = False,
                   require_standard: bool = False) -> float:
    """
    Score an actuator against requirements.
    Returns 0-100 score (higher = better match).
    """
    specs = act.get("specs", {})
    score = 0.0

    # 1. Torque/Price ratio (30%)
    torque = extract_number(specs.get("额定扭矩", specs.get("最大扭矩", "0")))
    price_str = specs.get("价格区间", "$0")
    price = extract_number(price_str)
    if price <= 0:
        price = 1000  # Default assumption
    torque_price_ratio = torque / price
    # Normalize: assume 0.1-0.5 is typical range
    score += min(torque_price_ratio / 0.5, 1.0) * 30

    # 2. Weight — lighter is better (20%)
    weight = extract_number(specs.get("重量", "9999g"))
    # Normalize: <500g = excellent, >3000g = poor
    weight_score = max(0, 1 - (weight / 3000))
    score += weight_score * 20

    # 3. Protocol match (25%)
    proto = str(specs.get("通信协议", "")).upper()
    if req_protocol.upper() in proto:
        score += 25
    elif "CAN" in proto and "CAN" in req_protocol.upper():
        score += 20  # Partial match for CAN variants

    # 4. Bionic features (15%)
    bionic = act.get("bionic_features", [])
    if bionic and len(bionic) > 0:
        score += 15 if bionic_priority else 10

    # 5. Standard compliance (10%)
    std = act.get("standard_compliance", [])
    if std and len(std) > 0:
        score += 10 if require_standard else 5

    # Penalty: torque insufficient
    if req_torque > 0 and torque < req_torque * 0.8:
        score *= 0.5

    return round(score, 1)


def select_actuators(joint_name: str, req_torque_nm: float,
                     req_protocol: str = "CAN FD", budget_usd: float = None,
                     top_n: int = 5, **kwargs) -> list:
    """
    Smart actuator selection with multi-factor scoring.

    Args:
        joint_name: Human-readable joint name (for display)
        req_torque_nm: Required torque in Newton-meters
        req_protocol: Preferred communication protocol
        budget_usd: Maximum budget in USD (optional)
        top_n: Number of top results to return
        **kwargs: bionic_priority, require_standard

    Returns:
        List of (actuator, score) tuples sorted by score descending.
    """
    results = []
    for act in DB.get("actuators", []):
        s = score_actuator(act, req_torque_nm, req_protocol,
                           budget_usd, **kwargs)
        if s > 30:  # Minimum relevance threshold
            results.append((act, s))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_n]


# ── Demo: Select actuators for key humanoid joints ──────────────────────────
if __name__ == "__main__":
    joints = [
        ("髋关节 (Hip)", 120, "CAN FD"),
        ("膝关节 (Knee)", 100, "CAN FD"),
        ("踝关节 (Ankle)", 60, "CAN"),
        ("肩关节 (Shoulder)", 50, "EtherCAT"),
        ("肘关节 (Elbow)", 30, "CAN"),
        ("腕关节 (Wrist)", 10, "RS-485"),
    ]

    print("=" * 70)
    print("RoboParts Smart Actuator Selection — Humanoid Robot")
    print("=" * 70)

    for joint, torque, protocol in joints:
        print(f"\n{'─' * 70}")
        print(f"Joint: {joint} | Required Torque: {torque}Nm | Protocol: {protocol}")
        print("─" * 70)

        top = select_actuators(joint, torque, protocol, top_n=3,
                               bionic_priority=True, require_standard=True)

        for rank, (act, score) in enumerate(top, 1):
            specs = act.get("specs", {})
            print(f"  #{rank} [{score}/100] {act['name']}")
            print(f"      Manufacturer: {act.get('manufacturer', 'N/A')}")
            print(f"      Torque: {specs.get('额定扭矩', 'N/A')} | "
                  f"Weight: {specs.get('重量', 'N/A')} | "
                  f"Price: {specs.get('价格区间', 'N/A')}")
            print(f"      Protocol: {specs.get('通信协议', 'N/A')} | "
                  f"Bionic: {act.get('bionic_features', [])}")

    print(f"\n{'=' * 70}")
    print("Try the online tool: https://roboparts.cc")
    print("=" * 70)
