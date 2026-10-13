import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
scene_path = ROOT / "scene.json"
inventory_path = ROOT / "inventory.json"
scene = json.loads(scene_path.read_text(encoding="utf-8"))
inventory = json.loads(inventory_path.read_text(encoding="utf-8"))

semantic_roles = {
    "S02-background-paper": "background plate with engineering-paper grid, edge schematics and tiled floor",
    "S02-flow-orange-heat-production": "hot route from heating furnace to production machine with elbow at furnace outlet",
    "S02-flow-orange-production-exhaust": "hot route from production outlet upturned toward exhaust and joining the downflow",
    "S02-flow-orange-exhaust-exchanger": "hot route down from the joined exhaust branch to the heat exchanger",
    "S02-flow-teal-return": "teal return loop from exchanger via recovery assembly toward furnace",
    "S02-flow-orange-exchanger-side": "orange highlighted exchanger-side outlet pipe with return elbow",
    "S02-device-heating": "heating furnace assembly",
    "S02-device-production": "production machine and attached conveyor",
    "S02-device-exhaust": "exhaust tower and stack assembly",
    "S02-device-recovery": "heat-recovery vessel and pump assembly",
    "S02-device-exchanger": "plate heat exchanger assembly",
    "S02-arrow-hot-heat-production": "solid white arrowhead from heating toward production",
    "S02-arrow-hot-production-exhaust": "solid white arrowhead from production toward exhaust branch",
    "S02-arrow-hot-exhaust-down": "solid white downward arrowhead on exchanger feed",
    "S02-arrow-hot-exchanger-out": "solid white arrowhead on exchanger outlet",
    "S02-arrow-return-left-1": "solid white leftward arrowhead on teal return",
    "S02-arrow-return-left-2": "solid white leftward arrowhead on teal return",
    "S02-arrow-return-left-3": "solid white leftward arrowhead on teal return",
    "S02-arrow-return-up-1": "solid white upward arrowhead on furnace return riser",
    "S02-arrow-return-up-2": "large solid white upward arrowhead entering the furnace",
    "S02-badge-shell-heating": "heating badge shell",
    "S02-badge-shell-production": "production badge shell",
    "S02-badge-shell-exhaust": "exhaust badge shell",
    "S02-badge-shell-reuse": "reuse badge shell",
    "S02-badge-shell-exchanger": "exchanger badge shell",
    "S02-text-badge-heating": "heating badge label",
    "S02-text-badge-production": "production badge label",
    "S02-text-badge-exhaust": "exhaust badge label",
    "S02-text-badge-reuse": "reuse badge label",
    "S02-text-badge-exchanger": "exchanger badge label",
    "S02-text-title": "large Chinese title",
    "S02-text-subtitle": "Chinese subtitle",
    "S02-text-footer": "Chinese engineering-parameter disclaimer",
    "S02-divider-title": "short title/subtitle separator",
    "S02-divider-footer-left": "footer rule left",
    "S02-divider-footer-right": "footer rule right",
}

inventory["reference"]["source_equipment_path"] = "../../../ai-presentation-workflow-architecture-20261012/pilots/delivery-modes/assets-three/assets/process-equipment.png"
inventory["reference"]["source_equipment_sha256"] = "059ceceb695caf9f97d84d58d718006fd4eb606e445d8d0879801d2a8411ad2a"
for treatment in inventory["embedded_treatments"]:
    if treatment["host"] == "flow route SVGs":
        treatment["treatment"] = "52px colored halo, 44px dark casing, 38px luminous orange/cyan gradient tube, upper white specular line; gradient is localized to each segment cross-section"

groups = {"semantic": [], "residual": []}
for item in scene["items"]:
    item["semantic_role"] = semantic_roles.get(item["id"], item.get("semantic_role", item["role"]))
    if item["role"] == "connector":
        item["pipe_style"] = "52px colored halo, 44px dark casing, 38px luminous orange/cyan gradient tube, upper white specular line; each straight, elbow, and vertical segment has a local cross-section gradient"
    group = "residual" if item["id"].startswith("S02-divider-") or item["id"].startswith("S02-collar-") or item["id"].startswith("S02-support-") else "semantic"
    groups[group].append(item)
inventory["passes"]["semantic"]["items"] = groups["semantic"]
inventory["passes"]["residual"]["items"] = groups["residual"]
inventory["passes"]["semantic"]["item_count"] = len(groups["semantic"])
inventory["passes"]["residual"]["item_count"] = len(groups["residual"])
inventory["coverage"].update({
    "total_items": len(scene["items"]),
    "semantic_items": len(groups["semantic"]),
    "residual_items": len(groups["residual"]),
    "unmatched_visible_elements": 0,
    "missing_required_components": [],
    "separate_equipment_assets": 5,
    "independent_flow_routes": 5,
    "independent_arrowheads": 9,
    "badge_shells": 5,
    "editable_text_objects": sum(item["role"] == "text" for item in scene["items"]),
    "independent_pipe_flange_collars": sum(item["id"].startswith("S02-collar-") for item in scene["items"]),
    "independent_ground_support_stanchions": sum(item["id"].startswith("S02-support-") for item in scene["items"]),
})

bindings = []
for item in scene["items"]:
    path = ROOT / item["file"]
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    item["sha256"] = digest
    bindings.append({
        "id": item["id"], "role": item["role"], "semantic_role": item["semantic_role"],
        "representation": item["representation"], "file": item["file"],
        "bytes": len(raw), "sha256": digest,
        "media_type": "image/png" if path.suffix.lower() == ".png" else "image/svg+xml",
    })
inventory["file_bindings"] = bindings

allowed_roles = {"background", "illustration", "connector", "arrow", "text", "special-typography", "decoration", "chart"}
assert all(item["role"] in allowed_roles for item in scene["items"])
assert len(scene["items"]) == len(bindings) == 45
assert len(groups["semantic"]) == 33 and len(groups["residual"]) == 12
assert inventory["omissions"] == []
assert not any(item["id"].startswith("S02-device-") and item["file"] == "assets/process-equipment.png" for item in scene["items"])
for item in scene["items"]:
    path = ROOT / item["file"]
    if path.suffix.lower() == ".svg":
        ET.parse(path)
    if item["role"] == "text":
        node = ET.parse(path).getroot().find("{http://www.w3.org/2000/svg}text")
        assert node is not None and "".join(node.itertext()) == item["text"]

scene_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"validated scene={len(scene['items'])}; semantic={len(groups['semantic'])}; residual={len(groups['residual'])}; bindings={len(bindings)}; SVG XML valid")
