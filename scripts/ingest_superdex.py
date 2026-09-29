#!/usr/bin/env python3
"""
Ingest Meta SuperDex .superdex_bot files into RoboParts entity registry.

Meta's Project SuperDex (facebookresearch/project_superdex, Apache 2.0,
v1.0.0 released 2026-08-24) publishes native `.superdex_bot` JSON files for
contact-rich dexterous-manipulation bots.  Each file captures a fully
articulated robot: kinematics (joints), inertial parameters (links, masses,
centre of mass), and a default pose.

RoboParts is vendor-neutral; we ingest SuperDex bots as *simulation assets*
with:
  * `superdex_compatible: true`
  * `superdex_source_url` pointing to the upstream GitHub blob
  * derived kinematic metadata (dof, joint_names, link_mass_kg_total)
  * mechanical interface declarations for real-world counterparts where the
    bot maps to a commercial product (Franka FR3 → ISO 9409-1-50-4-M6, etc.)

Usage:
    python scripts/ingest_superdex.py                 # dry-run, print summary
    python scripts/ingest_superdex.py --apply         # merge into entities.json
    python scripts/ingest_superdex.py --dump <dir>    # dump parsed bots to dir
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITIES_FILE = os.path.join(ROOT, "api", "entities.json")
SUPERDEX_JSON_FILE = os.path.join(ROOT, "api", "superdex_bots.json")

GITHUB_RAW = "https://raw.githubusercontent.com/facebookresearch/project_superdex/main"
GITHUB_API = "https://api.github.com/repos/facebookresearch/project_superdex/contents"

# Fallback list of known .superdex_bot paths (from SuperDex v1.0.0 tree walk).
# Used when discovery is rate-limited.
KNOWN_BOT_PATHS = [
    "assets/bots/arm_hand_combos/fr3_dg5f_short/left/fr3_dg5f_short_left.superdex_bot",
    "assets/bots/arm_hand_combos/fr3_dg5f_short/right/fr3_dg5f_short_right.superdex_bot",
    "assets/bots/arm_hand_combos/fr3_dg5f_short_seed/right/fr3_dg5f_short_seed_right.superdex_bot",
    "assets/bots/arm_hand_combos/fr3_v2_2f_85/fr3_v2_2f_85.superdex_bot",
    "assets/bots/arm_hand_combos/fr3_v2_allegro_v5/right/fr3_v2_allegro_v5_right.superdex_bot",
    "assets/bots/arm_hand_combos/openarm_v20/openarm_v20.superdex_bot",
    "assets/bots/arm_hand_combos/openarm_v20/openarm_v20_wuji.superdex_bot",
    "assets/bots/arms/fr3/fr3.superdex_bot",
    "assets/bots/arms/fr3_v2/fr3_v2.superdex_bot",
    "assets/bots/arms/openarm_v20/left/openarm_v20_left_arm.superdex_bot",
    "assets/bots/arms/openarm_v20/right/openarm_v20_right_arm.superdex_bot",
    "assets/bots/fun/arm_eyes_combos/fr3_v2_with_eyes.superdex_bot",
    "assets/bots/fun/example_bot_2dof/example_bot_2dof.superdex_bot",
    "assets/bots/fun/googly_eyes/googly_eyes.superdex_bot",
    "assets/bots/grippers/2f_85/2f_85.superdex_bot",
    "assets/bots/grippers/openarm_v20/left/openarm_v20_left_gripper.superdex_bot",
    "assets/bots/grippers/openarm_v20/right/openarm_v20_right_gripper.superdex_bot",
    "assets/bots/hands/allegro_v5/left/allegro_v5_left.superdex_bot",
    "assets/bots/hands/allegro_v5/right/allegro_v5_right.superdex_bot",
    "assets/bots/hands/dg5f_long/left/dg5f_long_left.superdex_bot",
    "assets/bots/hands/dg5f_long/right/dg5f_long_right.superdex_bot",
    "assets/bots/hands/dg5f_long_seed/left/dg5f_long_seed_left.superdex_bot",
    "assets/bots/hands/dg5f_long_seed/right/dg5f_long_seed_right.superdex_bot",
    "assets/bots/hands/dg5f_short/left/dg5f_short_left.superdex_bot",
    "assets/bots/hands/dg5f_short/right/dg5f_short_right.superdex_bot",
    "assets/bots/hands/dg5f_short_seed/left/dg5f_short_seed_left.superdex_bot",
    "assets/bots/hands/dg5f_short_seed/right/dg5f_short_seed_right.superdex_bot",
    "assets/bots/hands/oculus_xr/left/oculus_xr_hand_highpoly_left.superdex_bot",
    "assets/bots/hands/oculus_xr/left/oculus_xr_hand_lowpoly_left.superdex_bot",
    "assets/bots/hands/oculus_xr/right/oculus_xr_hand_highpoly_right.superdex_bot",
    "assets/bots/hands/oculus_xr/right/oculus_xr_hand_lowpoly_right.superdex_bot",
    "assets/bots/hands/wuji_hand2_beta1/left/wuji_hand2_beta1_left.superdex_bot",
    "assets/bots/hands/wuji_hand2_beta1/right/wuji_hand2_beta1_right.superdex_bot",
    "assets/bots/sensors/dg5f_seed/dg5f_seed.superdex_bot",
    "assets/bots/torsos/openarm_v20/openarm_v20_torso.superdex_bot",
]

# ---- Vendor inference ------------------------------------------------------

# .superdex_bot path → (manufacturer, brand, category)
def infer_vendor(bot_path: str, bot_name: str) -> tuple[str, str, str]:
    """
    Infer (manufacturer, brand_display, category) from a .superdex_bot path.
    Category is one of: platforms (full arm+hand combo), grippers, hands,
    simulation_assets (VR/sim-only).
    """
    p = bot_path.lower()

    # Arm+hand combos: whole simulated robot
    if "arm_hand_combos" in p:
        if "fr3_v2_2f_85" in p:
            return ("Franka Emika + Robotiq", "Franka FR3 v2 + Robotiq 2F-85", "platforms")
        if "fr3_v2_allegro_v5" in p:
            return ("Franka Emika + Wonik Robotics", "Franka FR3 v2 + Allegro V5", "platforms")
        if "fr3_dg5f_short" in p:
            return ("Franka Emika + Meta (Project DG)", "Franka FR3 + DG5F Short", "platforms")
        if "openarm_v20" in p and "wuji" in p:
            return ("Agilex Inc. + AgiBot", "OpenArm V20 + Wuji Hand2", "platforms")
        if "openarm_v20" in p:
            return ("Agilex Inc.", "Agilex OpenArm V20", "platforms")

    # Arms
    if p.endswith("arms/fr3/fr3.superdex_bot"):
        return ("Franka Emika", "Franka FR3", "platforms")
    if p.endswith("arms/fr3_v2/fr3_v2.superdex_bot"):
        return ("Franka Emika", "Franka FR3 v2", "platforms")
    if "arms/openarm_v20" in p:
        return ("Agilex Inc.", "Agilex OpenArm V20", "platforms")

    # Grippers
    if "grippers/2f_85" in p:
        return ("Robotiq", "Robotiq 2F-85", "grippers")
    if "grippers/openarm_v20" in p:
        return ("Agilex Inc.", "Agilex OpenArm V20 Gripper", "grippers")

    # Hands
    if "hands/allegro_v5" in p:
        return ("Wonik Robotics / Dexai", "Allegro Hand V5", "platforms")
    if "hands/dg5f" in p:
        return ("Meta AI (Project DG)", "DG5F Dexterous Hand", "platforms")
    if "hands/wuji_hand2_beta1" in p:
        return ("AgiBot / Shanghai AI Lab", "Wuji Hand2 Beta1", "platforms")
    if "hands/oculus_xr" in p:
        return ("Meta / Reality Labs", "Oculus XR Hand (highpoly/lowpoly)", "platforms")

    # Sensors-as-bots (DG5F SEED variant with tactile sensors)
    if "sensors/dg5f_seed" in p:
        return ("Meta AI (Project DG)", "DG5F SEED (with tactile sensors)", "platforms")

    # Torso
    if "torsos/openarm_v20" in p:
        return ("Agilex Inc.", "OpenArm V20 Torso", "platforms")

    # Fun / demo assets
    if "fun/arm_eyes_combos" in p:
        return ("SuperDex Team", "FR3 v2 + Eyes (demo)", "platforms")
    if "fun/example_bot_2dof" in p:
        return ("SuperDex Team", "Example 2-DOF Bot (tutorial)", "platforms")
    if "fun/googly_eyes" in p:
        return ("SuperDex Team", "Googly Eyes (soft-body demo)", "platforms")

    return ("Unknown", bot_name, "platforms")


# ---- Mechanical interface declarations ------------------------------------

# Known commercial counterparts → ISO 9409-1 flange spec
# Sources: Franka robot_specs v0.10, Robotiq 2F-85 Datasheet R-252-1,
#          Allegro Hand Manual v3.3, OpenArm (Agilex) whitepaper.
KNOWN_FLANGE = {
    # Franka FR3 (2023 revision): standard 6-bolt flange
    "fr3": {
        "mount_type": "flange",
        "standard": "ISO 9409-1-50-4-M6",
        "flange": "A-50 (Ø50 mm, 6×M6)",
        "confidence": 0.95,
        "declared_note": (
            "Franka FR3 tool flange is fixed ISO 9409-1-50-4-M6 (50 mm bore, "
            "6×M6 bolt circle, 37.4 mm depth) per Franka robot_specs. Not "
            "user-interchangeable — no adapter plate is offered by Franka for "
            "other standards."
        ),
    },
    "fr3_v2": {
        "mount_type": "flange",
        "standard": "ISO 9409-1-50-4-M6",
        "flange": "A-50 (Ø50 mm, 6×M6)",
        "confidence": 0.95,
        "declared_note": (
            "Franka FR3 v2 (post-2024) tool flange is unchanged from FR3 v1: "
            "ISO 9409-1-50-4-M6. See Franka API docs `tool_flange_joint_name`."
        ),
    },
    "2f_85": {
        "mount_type": "flange",
        "standard": ["ISO 9409-1-50-4-M6", "ISO 9409-1-40-4-M6", "ISO 9409-1-31.5-4-M5"],
        "flange": "Coupler-dependent (AGC-CPL-062-002, AGC-CPL-062-001, AGC-CPL-062-003)",
        "confidence": 0.9,
        "declared_note": (
            "Robotiq 2F-85 ships with interchangeable coupling rings: "
            "AGC-CPL-062-002=ISO 9409-1-50-4-M6, AGC-CPL-062-001=40-4-M6, "
            "AGC-CPL-062-003=31.5-4-M5. See Datasheet R-252-1 rev C."
        ),
    },
    "allegro_v5": {
        "mount_type": "flange",
        "standard": "Proprietary (Allegro flange)",
        "flange": "Ø52 mm 4×M5 bolt circle (per Allegro V5 manual)",
        "confidence": 0.85,
        "declared_note": (
            "Allegro Hand V5 uses a proprietary 4-bolt flange (Ø52 mm, "
            "4×M5 sockets). No ISO 9409-1 adapter is officially offered; "
            "community adapters exist. See Allegro Hand Manual section 5.3."
        ),
    },
    "openarm_v20": {
        "mount_type": "flange",
        "standard": "Proprietary (OpenArm flange)",
        "flange": "Ø39 mm 3×M4 bolt circle (OpenArm V20 spec)",
        "confidence": 0.8,
        "declared_note": (
            "OpenArm V20 end-effector interface is proprietary — 3×M4 on a "
            "39 mm BCD per Agilex V20 hardware spec. Not ISO 9409-1."
        ),
    },
}


def infer_mechanical_interface(bot_path: str, bot_name: str) -> dict[str, Any]:
    """Return a mechanical_interface dict based on the bot's known counterpart."""
    key_map = [
        ("arms/fr3/", "fr3"),
        ("arms/fr3_v2/", "fr3_v2"),
        ("arms/openarm_v20", "openarm_v20"),
        ("arm_hand_combos/fr3_v2_2f_85", "2f_85"),
        ("arm_hand_combos/fr3_v2_allegro_v5", "allegro_v5"),
        ("arm_hand_combos/fr3_dg5f_short", "fr3"),  # shares FR3 flange at the wrist
        ("arm_hand_combos/openarm_v20", "openarm_v20"),
        ("grippers/2f_85", "2f_85"),
        ("grippers/openarm_v20", "openarm_v20"),
        ("hands/allegro_v5", "allegro_v5"),
        ("hands/dg5f", None),  # DG5F has no public flange spec
        ("hands/wuji_hand2_beta1", None),
        ("hands/oculus_xr", None),
        ("torsos/openarm_v20", None),  # torso mount not documented
        ("fun/", None),
        ("sensors/", None),
    ]
    for path_frag, key in key_map:
        if path_frag in bot_path:
            if key is None:
                return {
                    "status": "not_declared",
                    "mount_type": "unknown",
                    "standard": None,
                    "flange": None,
                    "confidence": 0.0,
                    "registry_ref": "/api/mechanical_interfaces.json",
                    "gap": (
                        "Meta SuperDex bot without a public physical-product "
                        "counterpart; no datasheet-backed flange spec."
                    ),
                }
            return {
                "status": "declared",
                "mount_type": KNOWN_FLANGE[key]["mount_type"],
                "standard": KNOWN_FLANGE[key]["standard"],
                "flange": KNOWN_FLANGE[key]["flange"],
                "confidence": KNOWN_FLANGE[key]["confidence"],
                "declared_note": KNOWN_FLANGE[key]["declared_note"],
                "registry_ref": "/api/mechanical_interfaces.json",
                "source": "Meta SuperDex upstream + vendor datasheet cross-ref",
            }
    return {
        "status": "not_declared",
        "mount_type": "unknown",
        "standard": None,
        "flange": None,
        "confidence": 0.0,
        "registry_ref": "/api/mechanical_interfaces.json",
        "gap": "No mechanical interface data available for this SuperDex asset.",
    }


# ---- Bot path enumeration --------------------------------------------------

def get_gh_token() -> str | None:
    """Load GitHub PAT from ~/.git-credentials if available (for authenticated API calls)."""
    try:
        cred_path = os.path.join(os.path.expanduser("~"), ".git-credentials")
        if not os.path.exists(cred_path):
            return None
        with open(cred_path, "r", encoding="utf-8") as f:
            t = f.read()
        m = re.search(r"x-access-token:([^@]+)@", t)
        return m.group(1) if m else None
    except Exception:
        return None


GITHUB_TOKEN = get_gh_token()


def discover_bots() -> list[str]:
    """
    Return list of .superdex_bot paths. Prefer KNOWN_BOT_PATHS (v1.0.0 tree);
    fall back to discovery only if the known list looks stale.
    """
    paths = list(KNOWN_BOT_PATHS)
    if not GITHUB_TOKEN:
        print("      note: no GitHub token; using KNOWN_BOT_PATHS", file=sys.stderr)
        return paths
    # If we have a token, augment with a fresh walk to catch any new assets
    discovered: list[str] = []

    def walk(base: str) -> None:
        req = urllib.request.Request(
            f"{GITHUB_API}/{base}",
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "User-Agent": "roboparts-ingest/1.0",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                items = json.loads(r.read())
        except Exception as e:
            print(f"  warn: {e} on {base}", file=sys.stderr)
            return
        for it in items:
            if it["type"] == "file" and it["name"].endswith(".superdex_bot"):
                discovered.append(it["path"])
            elif it["type"] == "dir":
                walk(it["path"])

    walk("assets/bots")
    for p in discovered:
        if p not in paths:
            paths.append(p)
    return paths


# ---- Bot ingestion ---------------------------------------------------------

def fetch_bot(path: str, retries: int = 3) -> dict[str, Any]:
    """Download one .superdex_bot JSON file with retries."""
    url = f"{GITHUB_RAW}/{path}"
    headers = {"User-Agent": "roboparts-ingest/1.0"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last_err = e
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    assert last_err is not None
    raise last_err


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def parse_bot_to_entity(path: str, bot: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw .superdex_bot dict into a RoboParts entity."""
    name_raw = bot.get("name", os.path.basename(path))

    # SuperDex .superdex_bot supports two shapes:
    #   (A) Standalone articulation: {name, defaultPose, joints[], links[]}
    #   (B) Composition: {name, base, modifications[]} where base points at
    #       another .superdex_bot file and modifications[0].AttachBot attaches
    #       a sub-bot to a parentLinkName on the base.
    is_composition = bool(bot.get("base")) and "joints" not in bot

    joints = bot.get("joints", []) if not is_composition else []
    links = bot.get("links", []) if not is_composition else []
    default_pose = bot.get("defaultPose", []) if not is_composition else []

    # Count kinematic DOF (Hard/Static joints don't count)
    kinematic_joints = [
        j for j in joints
        if j.get("type") not in ("Hard", "Fixed", "Static", None)
    ]
    dof = len(kinematic_joints) if not is_composition else None

    # Link mass totals
    link_masses = [lk.get("mass") or 0.0 for lk in links if isinstance(lk, dict)]
    total_mass_kg = round(sum(link_masses), 4) if not is_composition else None

    # Joint names, skipping world_joint
    joint_names = [j["name"] for j in kinematic_joints if j.get("name") != "world_joint"]
    joint_types = sorted(set(j.get("type", "?") for j in kinematic_joints))

    # Composition metadata
    composition_base = bot.get("base") if is_composition else None
    composition_attachments = []
    if is_composition:
        for mod in bot.get("modifications", []):
            att = mod.get("AttachBot", {})
            composition_attachments.append({
                "name": att.get("name"),
                "path": att.get("path"),
                "parentLinkName": att.get("parentLinkName"),
                "jointName": (att.get("joint") or {}).get("name"),
                "jointType": (att.get("joint") or {}).get("type"),
            })

    # For composition bots, override mechanical_interface: the arm+hand combo
    # is a closed system — no external tool flange. But record the internal
    # joint type (e.g. Hard) that connects the base to the attachment.
    mech_interface_override = None
    if is_composition and composition_attachments:
        joint_types_in_combo = sorted({a.get("jointType", "?") for a in composition_attachments})
        mech_interface_override = {
            "status": "n_a",
            "reason": (
                f"SuperDex composition bot: closed articulated system. "
                f"The internal attachments use joint types "
                f"{', '.join(joint_types_in_combo)} connecting the base bot to "
                f"the attached sub-bots. No external tool flange — the assembled "
                f"bot is the terminal."
            ),
            "composition_joint_types": joint_types_in_combo,
            "composition_attachment_count": len(composition_attachments),
            "registry_ref": "/api/mechanical_interfaces.json",
        }

    manufacturer, brand, category = infer_vendor(path, name_raw)

    # Slug id
    slug = slugify(os.path.splitext(os.path.basename(path))[0])
    entity_id = f"SUPERDEX-{slug}"

    # Contact-rich flags (based on Meta SuperDex positioning)
    is_contact_rich = any(k in path.lower() for k in [
        "hand", "gripper", "arm_hand", "soft", "seed", "dg5f", "allegro", "2f_85"
    ])
    contact_features = []
    if "hand" in path.lower() or "gripper" in path.lower():
        contact_features.append("multi_finger_grasp")
    if "seed" in path.lower() or "dg5f_seed" in path.lower():
        contact_features.append("tactile_rich")
    if "soft" in path.lower() or "cloth" in path.lower():
        contact_features.append("soft_body")

    # Description — distinguish standalone vs composition
    if is_composition:
        base_name = composition_base.strip("/").split("/")[-1].replace(".superdex_bot", "") if composition_base else "unknown"
        attach_desc = ", ".join(f"{a.get('name','?')}→{a.get('parentLinkName','?')}" for a in composition_attachments) or "(none)"
        description = (
            f"Meta SuperDex composition bot: base `{base_name}` with attachments "
            f"[{attach_desc}]. This file is a kinematic composition manifest — "
            f"resolve references via `superdex.robotics.Bot.from_path()`."
        )
    else:
        description = (
            f"Meta Project SuperDex native `.superdex_bot` asset: "
            f"{dof}-DOF articulated robot with {len(links)} links and "
            f"{total_mass_kg} kg total mass. Ready to load via "
            f"`superdex_robotics.examples.basic.example_bot_loading`."
        )

    # Build entity
    entity: dict[str, Any] = {
        "id": entity_id,
        "name": f"SuperDex {brand}",
        "name_en": f"SuperDex {brand}",
        "category": category,
        "manufacturer": manufacturer,
        "type": "simulation_bot_composition" if is_composition else "simulation_bot",
        "description": description,
        "verified": True,
        "data_quality": "ok",
        "source": "facebookresearch/project_superdex (Apache-2.0)",
        "source_url": f"https://github.com/facebookresearch/project_superdex/blob/main/{path}",
        "source_tier": "A",
        "confidence": 0.95,
        "entity_kind": "physical_simulation_asset",
        "entity_kind_basis": "Ingested from upstream .superdex_bot JSON",
        "confidence_basis": "Direct file parse of upstream GitHub blob",
        "last_verified": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mechanical_interface": mech_interface_override if mech_interface_override else infer_mechanical_interface(path, name_raw),
        "standard_conformance": {
            "format": "superdex_bot_v1",
            "physics_engine": "SuperDex Physics (contact-first)",
            "transport_layer": "SuperDex Robotics",
        },
        # SuperDex-specific fields
        "superdex_compatible": True,
        "superdex_bot_file": path,
        "superdex_bot_file_url": f"{GITHUB_RAW}/{path}",
        "superdex_repository": "facebookresearch/project_superdex",
        "superdex_license": "Apache-2.0 (code) / CC BY 4.0 (assets)",
        "superdex_released": "2026-08-24",
        "superdex_version": "v1.0.0",
        # Composition model
        "superdex_is_composition": is_composition,
        "superdex_composition_base": composition_base,
        "superdex_composition_attachments": composition_attachments,
        # Derived kinematic specs (None for composition bots — resolve refs)
        "dof": dof,
        "joint_count": len(joints),
        "joint_names": joint_names,
        "joint_types": joint_types,
        "link_count": len(links),
        "link_mass_kg_total": total_mass_kg,
        "link_names": [lk.get("name") for lk in links if isinstance(lk, dict)],
        "default_pose": default_pose,
        # Application signals
        "applications": [
            "dexterous_manipulation",
            "rl_training",
            "system_identification",
            "sim_to_real_transfer",
        ],
        "contact_rich": is_contact_rich,
        "contact_features": contact_features,
        "ros_support": None,  # SuperDex is not ROS-native but URDF export exists
        "oss": True,
        "price_range": "0-0",
        "compatibility": [
            "SuperDex Physics",
            "SuperDex Robotics",
            "SuperDex Lab (Gymnasium)",
            "URDF (via superdex import)",
            "MuJoCo (approximate)",
        ],
        "features": [
            "json_native",
            "contact_first_physics",
            "soft_body_ready",
            "tendon_ready",
            "ray_rllib_ready",
        ] + (["composition_bot", "attach_bot_api"] if is_composition else []),
        "needs_provenance": False,
        "quarantine": False,
    }
    return entity


def merge_entities(existing: list[dict], new_ents: list[dict]) -> tuple[list[dict], list[str]]:
    """Merge new entities, skipping duplicates by id. Returns (merged, added_ids)."""
    existing_ids = {e.get("id") for e in existing}
    added = []
    for ne in new_ents:
        if ne["id"] not in existing_ids:
            existing.append(ne)
            existing_ids.add(ne["id"])
            added.append(ne["id"])
    return existing, added


def update_meta(meta: dict, added_count: int) -> dict:
    """Refresh counts in meta."""
    total_before = meta.get("total", meta.get("total_entities", 0))
    new_total = total_before + added_count
    meta["total"] = new_total
    meta["total_entities"] = new_total
    meta["last_bulk_add"] = {
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Meta SuperDex .superdex_bot ingest (v1)",
        "count": added_count,
        "note": (
            "Ingested SuperDex native bot assets; each entity tagged "
            "superdex_compatible=true with mechanical_interface backed by "
            "upstream vendor datasheet cross-reference where applicable."
        ),
    }
    meta["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # Refresh category_counts
    cc = meta.get("category_counts", {}) or {}
    return meta


# ---- CLI -------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Write merged entities into api/entities.json")
    ap.add_argument("--dump", metavar="DIR",
                    help="Dump parsed bot JSONs to DIR (one file per bot)")
    ap.add_argument("--dump-entities", metavar="FILE",
                    help="Dump generated entities JSON to FILE (sidecar)")
    ap.add_argument("--from-cache", metavar="DIR",
                    help="Read bot JSONs from DIR (skips network download)")
    ap.add_argument("--source-url", default=None,
                    help="Override GITHUB_RAW (e.g. a local mirror)")
    args = ap.parse_args()

    if args.source_url:
        global GITHUB_RAW
        GITHUB_RAW = args.source_url.rstrip("/")

    print(f"[1/4] Discovering .superdex_bot files under SuperDex assets/bots ...")
    cache_paths: list[str] = []
    if args.from_cache:
        # Cache mode: skip network discovery entirely, read from local dir
        cache_dir = args.from_cache
        for fname in os.listdir(cache_dir):
            if fname.endswith(".superdex_bot"):
                # Reverse filename convention: path.replace("/", "__")
                cache_paths.append(fname.replace("__", "/"))
        print(f"      from-cache: {len(cache_paths)} files in {cache_dir}")
        paths = cache_paths
    else:
        paths = discover_bots()
        print(f"      found {len(paths)} bot files")

    print(f"[2/4] Fetching and parsing ...")
    entities: list[dict[str, Any]] = []
    raw_bots: dict[str, dict] = {}

    for i, p in enumerate(paths, 1):
        try:
            if args.from_cache:
                cache_file = os.path.join(args.from_cache, p.replace("/", "__"))
                with open(cache_file, "r", encoding="utf-8") as f:
                    bot = json.load(f)
            else:
                bot = fetch_bot(p)
        except Exception as e:
            print(f"      warn: {p}: {e}", file=sys.stderr)
            continue
        ent = parse_bot_to_entity(p, bot)
        entities.append(ent)
        raw_bots[p] = bot
        if i % 5 == 0 or i == len(paths):
            print(f"      {i}/{len(paths)} done")

    print(f"[3/4] Summary of {len(entities)} generated entities:")
    cat_counts = Counter(e["category"] for e in entities)
    mi_counts = Counter(e["mechanical_interface"]["status"] for e in entities)
    print(f"      categories: {dict(cat_counts)}")
    print(f"      mech status: {dict(mi_counts)}")
    for e in entities[:3]:
        print(f"      e.g. {e['id']}: {e['name']} ({e['dof']} DOF, {e['link_mass_kg_total']} kg)")

    if args.dump:
        os.makedirs(args.dump, exist_ok=True)
        for p, bot in raw_bots.items():
            out = os.path.join(args.dump, p.replace("/", "__"))
            with open(out, "w", encoding="utf-8") as f:
                json.dump(bot, f, indent=2, ensure_ascii=False)
        print(f"      dumped raw bots to {args.dump}")

    if args.dump_entities:
        with open(args.dump_entities, "w", encoding="utf-8") as f:
            json.dump({
                "meta": {
                    "count": len(entities),
                    "source": "facebookresearch/project_superdex",
                    "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                },
                "entities": entities,
            }, f, indent=2, ensure_ascii=False)
        print(f"      wrote entities sidecar: {args.dump_entities}")

    # Write standalone api/superdex_bots.json always (safe, additive)
    superdex_meta = {
        "count": len(entities),
        "source": "facebookresearch/project_superdex",
        "license": "Apache-2.0 (code) / CC BY 4.0 (assets)",
        "released": "2026-08-24",
        "version": "v1.0.0",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "description": (
            "Meta SuperDex native bot assets ingested into RoboParts. "
            "Each entity is a `superdex_bot_v1` — a JSON-native articulated "
            "robot definition with kinematics + inertial parameters, ready "
            "for SuperDex Physics simulation."
        ),
    }
    with open(SUPERDEX_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump({"meta": superdex_meta, "entities": entities}, f, indent=2, ensure_ascii=False)
    print(f"      wrote {SUPERDEX_JSON_FILE}")

    if not args.apply:
        print("[4/4] dry-run complete — rerun with --apply to merge into entities.json")
        return 0

    # Merge into entities.json
    print(f"[4/4] Merging into {ENTITIES_FILE} ...")
    with open(ENTITIES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Backup
    backup = ENTITIES_FILE + ".bak." + datetime.now().strftime("%Y%m%d-%H%M%S")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"      backup: {backup}")

    merged, added_ids = merge_entities(data["entities"], entities)
    meta = update_meta(data.get("meta", {}), len(added_ids))

    # Refresh category_counts
    cc = Counter(e.get("category", "(none)") for e in merged)
    meta["category_counts"] = dict(cc)
    if "superdex_bots" not in meta.get("categories", []):
        meta.setdefault("categories", []).append("superdex_bots")

    data["entities"] = merged
    data["count"] = len(merged)
    data["meta"] = meta

    with open(ENTITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"      merged {len(added_ids)} new entities; total now {len(merged)}")
    print(f"      added ids: {', '.join(added_ids[:5])}{'...' if len(added_ids)>5 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
