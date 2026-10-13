import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
scene_path = ROOT / "scene.json"
inventory_path = ROOT / "inventory.json"
scene = json.loads(scene_path.read_text(encoding="utf-8"))
inventory = json.loads(inventory_path.read_text(encoding="utf-8"))

old_roles = {}
for group in ("semantic", "residual"):
    for item in inventory["passes"][group]["items"]:
        old_roles[item["id"]] = item["role"]

role_by_prefix = (
    ("S02-background-", "background"),
    ("S02-device-", "illustration"),
    ("S02-flow-", "connector"),
    ("S02-arrow-", "arrow"),
    ("S02-text-", "text"),
    ("S02-badge-shell-", "decoration"),
    ("S02-divider-", "decoration"),
)

for item in scene["items"]:
    item["semantic_role"] = old_roles[item["id"]]
    item["role"] = next(role for prefix, role in role_by_prefix if item["id"].startswith(prefix))
    if item["role"] != "text":
        continue
    item["asset_frame_bbox"] = [0, 0, 1672, 941]
    item["svg_viewbox"] = [0, 0, 1672, 941]
    slug = item["id"].removeprefix("S02-text-")
    item["file"] = f"components/text-{slug}.svg"
    item["text_width_px"] = item["bbox"][2]
    item["source_format"] = "editable SVG text node"
    if item["id"] == "S02-text-title":
        item["position"]["y"] = 112
        item["font_width_measurement"] = {
            "font_file": "C:/Windows/Fonts/NotoSansSC-VF.ttf",
            "natural_width_at_90px": 810,
            "source_target_width_px": 736,
            "svg_textLength_adjustment": 0.908642,
            "method": "Pillow ImageFont.getlength",
        }
    text = escape(item["text"])
    x, y = item["position"]["x"], item["position"]["y"]
    anchor = "middle" if item["position"].get("anchor") == "middle" else "start"
    spacing = item.get("letter_spacing_px")
    tracking = f' letter-spacing="{spacing}px"' if spacing is not None else ""
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1672" height="941" viewBox="0 0 1672 941" role="img" aria-label="{text}">
  <title>{text}</title>
  <metadata>Editable text source for {item["id"]}. Copy is exact; font family is an approximate source match.</metadata>
  <text x="{x}" y="{y}" text-anchor="{anchor}" textLength="{item['text_width_px']}" lengthAdjust="spacingAndGlyphs" font-family="Noto Sans SC, Microsoft YaHei, sans-serif" font-size="{item['font_size_px']}" font-weight="{item['font_weight']}" fill="{item['color']}"{tracking}>{text}</text>
</svg>
'''
    (ROOT / item["file"]).write_text(svg, encoding="utf-8")

scene_by_id = {item["id"]: item for item in scene["items"]}
for group in ("semantic", "residual"):
    for item in inventory["passes"][group]["items"]:
        updated = scene_by_id[item["id"]]
        item["role"] = updated["role"]
        item["semantic_role"] = updated["semantic_role"]
        if updated.get("file"):
            item["file"] = updated["file"]
        if updated["role"] == "text":
            for field in ("text", "text_width_px", "font_family", "font_weight", "font_size_px", "color", "editable", "font_match_approx", "asset_frame_bbox", "svg_viewbox", "font_width_measurement", "source_format"):
                if field in updated:
                    item[field] = updated[field]

bindings = []
for item in scene["items"]:
    relpath = item.get("file")
    if not relpath:
        continue
    path = ROOT / relpath
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    item["sha256"] = digest
    bindings.append({
        "id": item["id"],
        "role": item["role"],
        "semantic_role": item["semantic_role"],
        "representation": item["representation"],
        "file": relpath,
        "bytes": path.stat().st_size,
        "sha256": digest,
        "media_type": "image/png" if path.suffix.lower() == ".png" else "image/svg+xml",
    })

inventory["file_bindings"] = bindings
inventory["coverage"]["total_items"] = len(scene["items"])
inventory["coverage"]["semantic_items"] = len(inventory["passes"]["semantic"]["items"])
inventory["coverage"]["residual_items"] = len(inventory["passes"]["residual"]["items"])
inventory["coverage"]["editable_text_objects"] = sum(
    item["role"] == "text" and item.get("editable", False) for item in scene["items"]
)
text_note = "Each visible text object has its own full-canvas SVG with a live editable text node, plus scene/inventory text metadata."
if text_note not in inventory["generation_notes"]:
    inventory["generation_notes"].append(text_note)
scene_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"scene items={len(scene['items'])}; file bindings={len(bindings)}; editable text={inventory['coverage']['editable_text_objects']}")
