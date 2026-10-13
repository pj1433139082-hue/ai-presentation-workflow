#!/usr/bin/env python3
"""Extract one unoccluded object from a G4-approved textless master with a reviewed mask."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image, ImageChops
except ImportError as exc:
    raise RuntimeError("Pillow is required for deterministic pixel-preserving extraction") from exc


def project_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("project path must be a non-empty relative string")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError(f"path escapes project: {relative}")
    return path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crop_box(size: tuple[int, int], bbox: list[float], padding: list[float]) -> tuple[int, int, int, int]:
    if (
        len(bbox) != 4 or len(padding) != 4
        or any(type(value) not in {int, float} for value in bbox + padding)
        or bbox[0] < 0 or bbox[1] < 0 or bbox[2] <= 0 or bbox[3] <= 0
        or bbox[0] + bbox[2] > 1 or bbox[1] + bbox[3] > 1
        or any(value < 0 or value > 0.2 for value in padding)
    ):
        raise ValueError("bbox or crop_padding is invalid")
    width, height = size
    left = max(0, math.floor((bbox[0] - padding[0]) * width))
    top = max(0, math.floor((bbox[1] - padding[1]) * height))
    right = min(width, math.ceil((bbox[0] + bbox[2] + padding[2]) * width))
    bottom = min(height, math.ceil((bbox[1] + bbox[3] + padding[3]) * height))
    if right - left < 3 or bottom - top < 3:
        raise ValueError("declared crop is too small for an isolated object")
    return left, top, right, bottom


def extract_pixels(
    source_path: Path, mask_path: Path, bbox: list[float], padding: list[float]
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Keep source RGB unchanged; use mask only for output alpha."""
    with Image.open(source_path) as source_file:
        source = source_file.convert("RGBA")
    with Image.open(mask_path) as mask_file:
        mask = mask_file.convert("L")
    if source.size != mask.size:
        raise ValueError("mask dimensions must match the textless master")
    box = crop_box(source.size, bbox, padding)
    mask_bounds = mask.getbbox()
    if mask_bounds is None:
        raise ValueError("mask has no selected object pixels")
    if (
        mask_bounds[0] < box[0] or mask_bounds[1] < box[1]
        or mask_bounds[2] > box[2] or mask_bounds[3] > box[3]
    ):
        raise ValueError("mask extends outside declared crop")
    crop = source.crop(box)
    crop_mask = mask.crop(box)
    crop.putalpha(ImageChops.multiply(crop.getchannel("A"), crop_mask))
    alpha = crop.getchannel("A")
    if alpha.getbbox() is None:
        raise ValueError("selected mask has no visible source pixels")
    width, height = crop.size
    # An object intentionally clipped by the master canvas may reach that same
    # edge in the output. Interior crop edges still require transparent padding.
    if (
        (box[1] > 0 and alpha.crop((0, 0, width, 1)).getbbox())
        or (box[3] < source.height and alpha.crop((0, height - 1, width, height)).getbbox())
        or (box[0] > 0 and alpha.crop((0, 0, 1, height)).getbbox())
        or (box[2] < source.width and alpha.crop((width - 1, 0, width, height)).getbbox())
    ):
        raise ValueError("mask touches output border; enlarge crop padding or revise object boundary")
    return crop, box


def require_approved_inventory(root: Path) -> dict:
    validator_path = Path(__file__).resolve().with_name("validate_project.py")
    spec = importlib.util.spec_from_file_location("ai_presentation_asset_preflight", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load project validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validator = module.ProjectValidator(root, "inventory")
    validator.load_required_documents()
    # Asset creation precedes the pilot; still enforce the approved decomposition gate.
    validator.stage_index = module.STAGES.index("pilot")
    validator.validate_state()
    validator.validate_scene_graph()
    validator.validate_component_master_manifest()
    validator.validate_decomposition_map()
    if validator.errors:
        raise ValueError("approved decomposition preflight failed: " + "; ".join(validator.errors))
    return validator.docs


def extract_project_item(root: Path, slide_id: str, item_id: str, mask_relative: str) -> Path:
    docs = require_approved_inventory(root)
    decomposition = docs["decomposition-map.json"]
    records = [
        record for record in decomposition["slides"]
        if isinstance(record, dict) and record.get("slide_id") == slide_id
    ]
    if len(records) != 1:
        raise ValueError("slide must have exactly one current decomposition record")
    record = records[0]
    items = [item for item in record["items"] if isinstance(item, dict) and item.get("id") == item_id]
    if len(items) != 1:
        raise ValueError("item must have exactly one current decomposition record")
    item = items[0]
    if (
        item.get("kind") != "visual" or item.get("source_class") != "design-object"
        or item.get("treatment") != "preserve-pixels" or item.get("occlusion") != "none"
        or item.get("contains_ordinary_text_or_data") is not False
    ):
        raise ValueError("pixel preservation requires one unoccluded textless design object")
    manifest = docs["asset-manifest.json"]
    assets = [asset for asset in manifest["assets"] if isinstance(asset, dict) and asset.get("id") == item.get("component_id")]
    if len(assets) != 1:
        raise ValueError("item must link one asset manifest entry")
    asset = assets[0]
    if asset.get("strategy") != "preserved-transparent-png":
        raise ValueError("manifest strategy must be preserved-transparent-png")
    if not isinstance(asset.get("review_history", []), list) or not isinstance(asset.get("extraction_history", []), list):
        raise ValueError("asset review and extraction histories must be lists")
    output_relative = asset.get("output")
    if not isinstance(output_relative, str):
        raise ValueError("asset output path must be declared before extraction")
    output = project_file(root, output_relative)
    if not output.is_relative_to((root / "assets").resolve()) or output.suffix.lower() != ".png":
        raise ValueError("output must be a PNG under assets/")
    if output.exists():
        raise ValueError("output already exists; use a new versioned asset path")
    source_relative = record["master_path"]
    source = project_file(root, source_relative)
    mask = project_file(root, mask_relative)
    if not mask.is_file() or mask.suffix.lower() != ".png":
        raise ValueError("one current PNG mask is required")
    image, box = extract_pixels(source, mask, item["bbox"], item["crop_padding"])
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    payload = buffer.getvalue()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(payload)
    alpha = image.getchannel("A")
    transparent = alpha.histogram()[0]
    asset["sha256"] = hashlib.sha256(payload).hexdigest()
    asset["alpha"] = {"has_alpha": True, "transparent_pixel_ratio": transparent / (image.width * image.height)}
    if isinstance(asset.get("isolation_review"), dict):
        asset.setdefault("review_history", []).append(asset.pop("isolation_review"))
    # The manifest begins with a planned route. Preserve only a completed
    # extraction as history; a route stub has no source or output to verify.
    prior_extraction = asset.get("extraction")
    if isinstance(prior_extraction, dict) and prior_extraction.get("output_path"):
        asset.setdefault("extraction_history", []).append(prior_extraction)
    asset["extraction"] = {
        "route": "preserve-pixels", "source_item": {"slide_id": slide_id, "item_id": item_id},
        "source_path": source_relative, "source_sha256": file_sha256(source),
        "mask_path": mask_relative, "mask_sha256": file_sha256(mask), "source_crop_px": list(box),
        "output_path": output_relative, "output_sha256": asset["sha256"],
    }
    asset["status"] = "needs-isolation-review"
    manifest_path = root / "asset-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--slide", required=True)
    parser.add_argument("--item", required=True)
    parser.add_argument("--mask", required=True, help="Project-relative full-size PNG alpha mask")
    args = parser.parse_args()
    try:
        output = extract_project_item(args.project_dir.resolve(), args.slide, args.item, args.mask)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"Extracted component: {output}")
    print("Human isolation review is still required; this command does not approve the asset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
