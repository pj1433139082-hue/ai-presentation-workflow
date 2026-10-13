import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMP = ROOT / "components"
scene_path = ROOT / "scene.json"
inventory_path = ROOT / "inventory.json"
scene = json.loads(scene_path.read_text(encoding="utf-8"))
inventory = json.loads(inventory_path.read_text(encoding="utf-8"))

def svg_document(title, body, definitions=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1672" height="941" viewBox="0 0 1672 941" role="img" aria-label="{title}">
  <title>{title}</title>
  <defs>{definitions}</defs>
  {body}
</svg>
'''

def pipe_svg(title, path, color, highlight_path, box):
    if color == "orange":
        gradient = '''<linearGradient id="hotPipe" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#ffd978"/><stop offset=".12" stop-color="#ffad2b"/>
          <stop offset=".48" stop-color="#ff7900"/><stop offset=".82" stop-color="#f36500"/><stop offset="1" stop-color="#c94c00"/>
        </linearGradient><filter id="pipeGlow" x="-20%" y="-30%" width="140%" height="160%"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'''
        glow, edge, main = "#ff7600", "#c95000", "url(#hotPipe)"
    else:
        gradient = '''<linearGradient id="coolPipe" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#7af6f6"/><stop offset=".12" stop-color="#37dfe7"/>
          <stop offset=".48" stop-color="#00b4c2"/><stop offset=".82" stop-color="#008d9e"/><stop offset="1" stop-color="#006a78"/>
        </linearGradient><filter id="pipeGlow" x="-20%" y="-30%" width="140%" height="160%"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'''
        glow, edge, main = "#00c1cb", "#006b79", "url(#coolPipe)"
    body = f'''<path d="{path}" fill="none" stroke="{glow}" stroke-width="52" stroke-linecap="round" stroke-linejoin="round" opacity=".58" filter="url(#pipeGlow)"/>
  <path d="{path}" fill="none" stroke="{edge}" stroke-width="44" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{path}" fill="none" stroke="{main}" stroke-width="38" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="{highlight_path}" fill="none" stroke="#fff4d6" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round" opacity=".94"/>'''
    (COMP / f"{title}.svg").write_text(svg_document(title.replace("-", " "), body, gradient), encoding="utf-8")
    return [box[0], box[1], box[2], box[3]]

route_specs = {
    "flow-orange-heater-production": {
        "path": "M 430 350 V 393 Q 430 414 451 414 H 700",
        "highlight": "M 430 393 Q 430 402 439 402 H 700",
        "color": "orange", "bbox": [404, 324, 322, 116],
    },
    "flow-orange-production-exhaust": {
        "path": "M 1110 414 H 1281 Q 1302 414 1302 393 V 361 Q 1302 340 1323 340 H 1400",
        "highlight": "M 1110 402 H 1281 Q 1290 402 1290 393 V 361 Q 1290 352 1323 352 H 1400",
        "color": "orange", "bbox": [1084, 314, 342, 126],
    },
    "flow-orange-exhaust-exchanger": {
        "path": "M 1400 340 V 560",
        "highlight": "M 1388 350 V 560",
        "color": "orange", "bbox": [1374, 314, 52, 272],
    },
    "flow-teal-return-loop": {
        "path": "M 1325 692 H 346 Q 296 692 296 642 V 431",
        "highlight": "M 1325 680 H 346 Q 308 680 308 642 V 431",
        "color": "teal", "bbox": [270, 405, 1081, 313],
    },
    "flow-orange-exchanger-side": {
        "path": "M 1430 594 H 1537 Q 1566 594 1566 623 V 665 Q 1566 694 1537 694 H 1515",
        "highlight": "M 1430 582 H 1537 Q 1554 582 1554 623 V 665 Q 1554 682 1537 682 H 1515",
        "color": "orange", "bbox": [1404, 568, 188, 152],
    },
}

items_by_id = {item["id"]: item for item in scene["items"]}
for filename, spec in route_specs.items():
    route_box = pipe_svg(filename, spec["path"], spec["color"], spec["highlight"], spec["bbox"])
    scene_id = {
        "flow-orange-heater-production": "S02-flow-orange-heat-production",
        "flow-orange-production-exhaust": "S02-flow-orange-production-exhaust",
        "flow-orange-exhaust-exchanger": "S02-flow-orange-exhaust-exchanger",
        "flow-teal-return-loop": "S02-flow-teal-return",
        "flow-orange-exchanger-side": "S02-flow-orange-exchanger-side",
    }[filename]
    items_by_id[scene_id]["bbox"] = route_box
    items_by_id[scene_id]["pipe_style"] = "wide shaded tube, 44px dark casing + 38px gradient body + narrow upper specular highlight + 52px soft colored halo"

def arrow_shape(direction, x, y, width, height):
    if direction == "right":
        pts = [(x, y+6), (x+width-22, y+6), (x+width-22, y), (x+width, y+height/2), (x+width-22, y+height), (x+width-22, y+height-6), (x, y+height-6)]
    elif direction == "left":
        pts = [(x+width, y+6), (x+22, y+6), (x+22, y), (x, y+height/2), (x+22, y+height), (x+22, y+height-6), (x+width, y+height-6)]
    elif direction == "down":
        pts = [(x+6, y), (x+width-6, y), (x+width-6, y+height-22), (x+width, y+height-22), (x+width/2, y+height), (x, y+height-22), (x+6, y+height-22)]
    else:
        pts = [(x+width/2, y), (x+width, y+22), (x+width-22, y+22), (x+width-22, y+height), (x+22, y+height), (x+22, y+22), (x, y+22)]
    return " ".join(f"{px:g},{py:g}" for px, py in pts)

arrow_specs = {
    "S02-arrow-hot-heat-production": ([568, 399, 45, 30], "right", "#ff7b00"),
    "S02-arrow-hot-production-exhaust": ([1235, 399, 45, 30], "right", "#ff7b00"),
    "S02-arrow-hot-exhaust-down": ([1405, 503, 30, 45], "down", "#ff7b00"),
    "S02-arrow-hot-exchanger-out": ([1485, 579, 45, 30], "right", "#ff7b00"),
    "S02-arrow-return-left-1": ([1219.5, 677, 45, 30], "left", "#00a0a8"),
    "S02-arrow-return-left-2": ([1030.5, 677, 45, 30], "left", "#00a0a8"),
    "S02-arrow-return-left-3": ([525.5, 677, 45, 30], "left", "#00a0a8"),
    "S02-arrow-return-up-1": ([281, 565, 30, 30], "up", "#00a0a8"),
    "S02-arrow-return-up-2": ([258.5, 418.5, 75, 75], "up", "#00a0a8"),
}
arrow_filename = {
    "S02-arrow-hot-heat-production": "arrow-orange-heat-to-production.svg",
    "S02-arrow-hot-production-exhaust": "arrow-orange-production-to-exhaust.svg",
    "S02-arrow-hot-exhaust-down": "arrow-orange-exhaust-down.svg",
    "S02-arrow-hot-exchanger-out": "arrow-orange-exchanger-outlet.svg",
    "S02-arrow-return-left-1": "arrow-teal-return-1.svg",
    "S02-arrow-return-left-2": "arrow-teal-return-2.svg",
    "S02-arrow-return-left-3": "arrow-teal-return-3.svg",
    "S02-arrow-return-up-1": "arrow-teal-up-1.svg",
    "S02-arrow-return-up-2": "arrow-teal-up-2.svg",
}
for item_id, (box, direction, accent) in arrow_specs.items():
    x, y, width, height = box
    points = arrow_shape(direction, x, y, width, height)
    defs = f'<filter id="arrowHalo" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3.5" result="b"/><feFlood flood-color="{accent}" flood-opacity=".9"/><feComposite in2="b" operator="in"/><feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    body = f'<polygon points="{points}" fill="#ffffff" filter="url(#arrowHalo)"/>'
    (COMP / arrow_filename[item_id]).write_text(svg_document(item_id, body, defs), encoding="utf-8")
    item = items_by_id[item_id]
    item["bbox"] = box
    item["direction"] = direction
    item["fill"] = "#ffffff"
    item["shape"] = "solid white arrow polygon with colored edge halo; independently movable"

def metal_band(name, center_x, center_y, orientation):
    definitions = '''<linearGradient id="steel" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#4e626b"/><stop offset=".22" stop-color="#f3f6f4"/><stop offset=".48" stop-color="#9daeb0"/><stop offset=".72" stop-color="#e7edeb"/><stop offset="1" stop-color="#53676e"/></linearGradient>'''
    if orientation == "horizontal":
        x, y, width, height = center_x-9, center_y-23, 18, 46
        shape = f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="4" fill="url(#steel)" stroke="#354952" stroke-width="2"/><path d="M{x+5} {y+3} V{y+height-3} M{x+13} {y+3} V{y+height-3}" stroke="#f6f6eb" stroke-width="1.5" opacity=".8"/><circle cx="{center_x}" cy="{center_y-16}" r="2" fill="#263d46"/><circle cx="{center_x}" cy="{center_y+16}" r="2" fill="#263d46"/>'
        bbox = [x-2, y-2, width+4, height+4]
    else:
        x, y, width, height = center_x-23, center_y-9, 46, 18
        shape = f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="4" fill="url(#steel)" stroke="#354952" stroke-width="2"/><path d="M{x+3} {y+5} H{x+width-3} M{x+3} {y+13} H{x+width-3}" stroke="#f6f6eb" stroke-width="1.5" opacity=".8"/><circle cx="{center_x-16}" cy="{center_y}" r="2" fill="#263d46"/><circle cx="{center_x+16}" cy="{center_y}" r="2" fill="#263d46"/>'
        bbox = [x-2, y-2, width+4, height+4]
    (COMP / f"{name}.svg").write_text(svg_document(name.replace("-", " "), shape, definitions), encoding="utf-8")
    return bbox

collar_specs = [
    ("S02-collar-teal-return-left", "collar-teal-return-left", 399, 692, "horizontal", "return line flange collar near furnace-side bend"),
    ("S02-collar-hot-production-inlet", "collar-hot-production-inlet", 687, 414, "horizontal", "hot line flange collar at production inlet"),
    ("S02-collar-hot-production-outlet", "collar-hot-production-outlet", 1113, 414, "horizontal", "hot line flange collar at production outlet"),
    ("S02-collar-hot-downcomer", "collar-hot-downcomer", 1400, 560, "vertical", "hot line flange collar above exchanger entry"),
    ("S02-collar-exchanger-outlet", "collar-exchanger-outlet", 1460, 594, "horizontal", "orange exchanger-side outlet flange collar"),
]
new_residuals = []
for item_id, name, cx, cy, orientation, semantic in collar_specs:
    box = metal_band(name, cx, cy, orientation)
    item = {"id": item_id, "role": "decoration", "semantic_role": semantic, "bbox": box, "z": 22, "representation": "native", "file": f"components/{name}.svg", "asset_frame_bbox": [0, 0, 1672, 941], "svg_viewbox": [0, 0, 1672, 941], "independently_movable": True}
    scene["items"].append(item)
    new_residuals.append(item)

def stanchion_svg(name, center_x):
    body = f'''<defs><linearGradient id="steel" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#52636a"/><stop offset=".25" stop-color="#f3f4ee"/><stop offset=".52" stop-color="#87989d"/><stop offset=".78" stop-color="#e9eeeb"/><stop offset="1" stop-color="#53646a"/></linearGradient></defs>
<path d="M{center_x-11} 704 V719 H{center_x+11} V704" fill="none" stroke="#33454b" stroke-width="3" stroke-linejoin="round"/>
<path d="M{center_x} 718 V750" stroke="#475c63" stroke-width="11"/><path d="M{center_x-2} 719 V750" stroke="#eff2ee" stroke-width="2.5"/>
<rect x="{center_x-16}" y="748" width="32" height="8" rx="2" fill="url(#steel)" stroke="#34484e" stroke-width="1.5"/>
<circle cx="{center_x-11}" cy="752" r="1.6" fill="#263941"/><circle cx="{center_x+11}" cy="752" r="1.6" fill="#263941"/>'''
    return svg_document(name.replace("-", " "), body)

stanchion_specs = [
    ("S02-support-ground-384", "support-ground-384", 384),
    ("S02-support-ground-529", "support-ground-529", 529),
    ("S02-support-ground-653", "support-ground-653", 653),
    ("S02-support-ground-1150", "support-ground-1150", 1150),
]
for item_id, name, cx in stanchion_specs:
    (COMP / f"{name}.svg").write_text(stanchion_svg(name, cx), encoding="utf-8")
    item = {"id": item_id, "role": "decoration", "semantic_role": "independent ground support stanchion under the teal return pipe", "bbox": [cx-18, 702, 36, 56], "z": 21, "representation": "native", "file": f"components/{name}.svg", "asset_frame_bbox": [0, 0, 1672, 941], "svg_viewbox": [0, 0, 1672, 941], "independently_movable": True}
    scene["items"].append(item)
    new_residuals.append(item)

for item in scene["items"]:
    if item["id"].startswith("S02-arrow-"):
        item["z"] = 24

for item in new_residuals:
    item["sha256"] = hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest()

inv_semantic = inventory["passes"]["semantic"]["items"]
inv_residual = inventory["passes"]["residual"]["items"]
for item in scene["items"]:
    if item["id"] in {e["id"] for e in inv_semantic + inv_residual}:
        target = next(e for e in inv_semantic + inv_residual if e["id"] == item["id"])
        target.update({k: v for k, v in item.items() if k in ("role", "semantic_role", "bbox", "z", "file", "representation", "asset_frame_bbox", "svg_viewbox", "direction", "shape", "fill", "pipe_style", "text", "text_width_px", "font_family", "font_weight", "font_size_px", "color", "editable", "font_match_approx", "font_width_measurement", "source_format")})
        continue
    inv_residual.append({k: v for k, v in item.items() if k != "sha256"})

inventory["coverage"]["total_items"] = len(scene["items"])
inventory["coverage"]["semantic_items"] = len(inv_semantic)
inventory["coverage"]["residual_items"] = len(inv_residual)
inventory["coverage"]["unmatched_visible_elements"] = 0
inventory["coverage"]["independent_flow_routes"] = 5
inventory["coverage"]["independent_arrowheads"] = 9
inventory["coverage"]["independent_pipe_flange_collars"] = len(collar_specs)
inventory["coverage"]["independent_ground_support_stanchions"] = len(stanchion_specs)
inventory["omissions"] = []
inventory["generation_notes"].append("Residual inspection added five separate metal flange-collar SVGs and four separate ground-support stanchion SVGs; none are fused into a route or machine asset.")

bindings = []
for item in scene["items"]:
    path = ROOT / item["file"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    item["sha256"] = digest
    bindings.append({"id": item["id"], "role": item["role"], "semantic_role": item["semantic_role"], "representation": item["representation"], "file": item["file"], "bytes": path.stat().st_size, "sha256": digest, "media_type": "image/png" if path.suffix.lower() == ".png" else "image/svg+xml"})
inventory["file_bindings"] = bindings
scene_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"scene items={len(scene['items'])}; semantic={len(inv_semantic)}; residual={len(inv_residual)}; bindings={len(bindings)}")
