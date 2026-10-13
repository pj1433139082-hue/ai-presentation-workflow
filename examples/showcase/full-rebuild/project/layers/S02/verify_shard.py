import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parent
scene = json.loads((ROOT / "scene.json").read_text(encoding="utf-8"))
inventory = json.loads((ROOT / "inventory.json").read_text(encoding="utf-8"))
bindings = {entry["id"]: entry for entry in inventory["file_bindings"]}
accepted_roles = {"background", "illustration", "connector", "arrow", "text", "special-typography", "decoration", "chart"}

assert len(scene["items"]) == 45 == len(bindings)
assert all(item["role"] in accepted_roles for item in scene["items"])
assert len(inventory["passes"]["semantic"]["items"]) == 33
assert len(inventory["passes"]["residual"]["items"]) == 12
assert inventory["omissions"] == []

assets = []
for item in scene["items"]:
    path = ROOT / item["file"]
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    binding = bindings[item["id"]]
    assert digest == item["sha256"] == binding["sha256"]
    assert len(raw) == binding["bytes"]
    record = {"id": item["id"], "role": item["role"], "file": item["file"], "sha256": digest, "bytes": len(raw)}
    if path.suffix.lower() == ".svg":
        root = ET.parse(path).getroot()
        assert root.attrib.get("viewBox") == "0 0 1672 941"
        if item["role"] == "text":
            node = root.find("{http://www.w3.org/2000/svg}text")
            assert node is not None and "".join(node.itertext()) == item["text"]
            record["live_text"] = "".join(node.itertext())
    else:
        with Image.open(path) as image:
            record["pixel_size"] = list(image.size)
            record["mode"] = image.mode
            assert list(image.size) == item["asset_px_size"]
            if item["role"] == "illustration":
                assert image.mode == "RGBA"
                alpha = image.getchannel("A")
                threshold = alpha.point(lambda p: 255 if p > 8 else 0)
                bounds = threshold.getbbox()
                bounds_box = [bounds[0], bounds[1], bounds[2] - bounds[0], bounds[3] - bounds[1]]
                expected = item["asset_alpha_bbox_px_gt8"]
                assert bounds_box == expected
                record["alpha_bbox_gt8"] = bounds_box
                record["transparent_pixels"] = sum(1 for p in alpha.getdata() if p == 0)
            else:
                assert image.mode == "RGB"
                record["alpha"] = "opaque"
    assets.append(record)

calls = []
for folder in sorted((ROOT / "attempts").iterdir()):
    if not folder.is_dir():
        continue
    record = json.loads((folder / "record.json").read_text(encoding="utf-8"))
    copied = ROOT / record["attempt_copy"]
    assert copied.is_file()
    calls.append({
        "call_id": record["call_id"], "status": record["status"], "tool": record["tool"],
        "attempt_record": str((folder / "record.json").relative_to(ROOT)).replace("\\", "/"),
        "original_codex_output_path": record["original_codex_output_path"],
        "prompt_sha256": hashlib.sha256(record["prompt"].encode("utf-8")).hexdigest(),
        "input_references": record["input_references"],
        "attempt_copy": record["attempt_copy"],
    })
assert sum(call["status"] == "accepted" for call in calls) == 6
assert sum(call["status"] == "rejected" for call in calls) == 1

report = {
    "slide_id": "S02",
    "verification_status": "shard checks passed; final merged layout still requires parent render review",
    "canvas": [1672, 941],
    "inventory_counts": inventory["coverage"],
    "source_references": scene["reference"],
    "image_generation_calls": calls,
    "verified_files": assets,
    "font_measurement": {
        "font_file": "C:/Windows/Fonts/NotoSansSC-VF.ttf",
        "method": "Pillow ImageFont.getlength",
        "title": "把损失，接回流程。",
        "natural_width_at_90px": 810,
        "source_width_px": 736,
        "editable_svg_textLength": 736,
        "fit_ratio": 736 / 810,
    },
    "visual_review": {
        "background_plate": "inspected; reconstructed paper/grid/floor retained while foreground devices, pipes, arrows, badges, text and dividers were removed",
        "five_device_pngs": "individually inspected as isolated equipment with transparent backgrounds; no neighboring device or shared flow route is included",
        "full_composite": "pending parent merged HTML/PPTX render comparison",
    },
}
(ROOT / "qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"verified PNGs={sum(a['file'].endswith('.png') for a in assets)}; SVGs={sum(a['file'].endswith('.svg') for a in assets)}; image calls={len(calls)}; assets={len(assets)}")
