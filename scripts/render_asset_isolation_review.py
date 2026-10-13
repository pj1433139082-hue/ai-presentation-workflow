#!/usr/bin/env python3
"""Build a per-asset concept/cutout/light/dark review sheet without approving it."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as exc:
    raise RuntimeError("Pillow is required for asset isolation review") from exc


def value_sha256(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("review path must be a non-empty project-relative string")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError(f"path escapes project: {relative}")
    return path


def source_items_for_asset(decomposition: dict, asset_id: str) -> list[dict]:
    matches = []
    for slide in decomposition.get("slides", []):
        if not isinstance(slide, dict):
            continue
        for item in slide.get("items", []):
            if isinstance(item, dict) and item.get("kind") == "visual" and item.get("component_id") == asset_id:
                matches.append({
                    "slide_id": slide.get("slide_id"), "item_id": item.get("id"),
                    "concept_path": slide.get("concept_path"), "concept_sha256": slide.get("concept_sha256"),
                    "item_sha256": value_sha256(item), "label": item.get("label"),
                    "bbox": item.get("bbox"), "crop_padding": item.get("crop_padding"),
                    "treatment": item.get("treatment"), "role": item.get("role"),
                })
    return matches


def safe_cell(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def review_row(item: dict) -> str:
    return "| " + " | ".join(safe_cell(item[key]) for key in (
        "slide_id", "item_id", "label", "role", "treatment", "concept_path"
    )) + " |"


def build_isolation_image(root: Path, asset_path: Path, source_items: list[dict], *, pixels=None) -> Image.Image:
    if not source_items:
        raise ValueError("asset must map to at least one decomposition item")
    if pixels is None:
        with Image.open(asset_path) as opened:
            component = opened.convert("RGBA")
    else:
        component = pixels.read(asset_path, "RGBA")
    reference_crops = []
    for item in source_items:
        concept = project_file(root, item["concept_path"])
        if pixels is None:
            if file_sha256(concept) != item["concept_sha256"]:
                raise ValueError("concept crop source is stale")
            with Image.open(concept) as opened:
                source = opened.convert("RGB")
        else:
            source = pixels.read(concept, "RGB", expected_sha256=item["concept_sha256"])
        try:
            width, height = source.size
            x, y, w, h = item["bbox"]
            left, top, right, bottom = item["crop_padding"]
            box = (
                max(0, math.floor((x - left) * width)),
                max(0, math.floor((y - top) * height)),
                min(width, math.ceil((x + w + right) * width)),
                min(height, math.ceil((y + h + bottom) * height)),
            )
            reference_crops.append(source.crop(box))
        finally:
            source.close()
    panel_width = max(component.width, *(crop.width for crop in reference_crops))
    panel_height = max(component.height, *(crop.height for crop in reference_crops))
    gap = 16
    margin = 16
    row_height = panel_height + 24
    sheet = Image.new("RGB", (margin * 2 + panel_width * 3 + gap * 2, margin * 2 + row_height * len(source_items)), (13, 27, 51))
    for row, crop in enumerate(reference_crops):
        y0 = margin + row * row_height
        sheet.paste(crop, (margin, y0))
        light = Image.new("RGB", (panel_width, panel_height), (234, 239, 244))
        draw = ImageDraw.Draw(light)
        tile = 16
        for cy in range(0, panel_height, tile):
            for cx in range(0, panel_width, tile):
                if (cx // tile + cy // tile) % 2:
                    draw.rectangle((cx, cy, min(panel_width - 1, cx + tile - 1), min(panel_height - 1, cy + tile - 1)), fill=(192, 202, 214))
        light.paste(component, ((panel_width - component.width) // 2, (panel_height - component.height) // 2), component)
        sheet.paste(light, (margin + panel_width + gap, y0))
        dark = Image.new("RGB", (panel_width, panel_height), (6, 12, 24))
        dark.paste(component, ((panel_width - component.width) // 2, (panel_height - component.height) // 2), component)
        sheet.paste(dark, (margin + 2 * (panel_width + gap), y0))
    return sheet


def require_approved_inventory(root: Path, fragment: dict | None = None) -> dict:
    validator_path = Path(__file__).resolve().with_name("validate_project.py")
    spec = importlib.util.spec_from_file_location("ai_presentation_asset_isolation_preflight", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load project validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validator = module.ProjectValidator(root, "inventory")
    validator.load_required_documents()
    if fragment is not None:
        current = validator.docs["asset-manifest.json"]
        current_assets = current.get("assets", [])
        fragment_assets = fragment.get("assets", [])
        if not isinstance(current_assets, list) or not isinstance(fragment_assets, list):
            raise ValueError("global and fragment asset manifests must contain arrays")
        by_id = {asset.get("id"): asset for asset in current_assets if isinstance(asset, dict)}
        if len(by_id) != len(current_assets):
            raise ValueError("global asset manifest has duplicate or invalid records")
        fragment_ids: set[str] = set()
        for asset in fragment_assets:
            if not isinstance(asset, dict) or not isinstance(asset.get("id"), str):
                raise ValueError("fragment asset records need unique string IDs")
            if asset["id"] in fragment_ids:
                raise ValueError(f"fragment repeats asset ID: {asset['id']}")
            fragment_ids.add(asset["id"])
            prior = by_id.get(asset["id"])
            if prior is not None and prior != asset:
                raise ValueError(f"fragment conflicts with global asset: {asset['id']}")
            by_id[asset["id"]] = asset
        validator.docs["asset-manifest.json"] = {**current, "assets": list(by_id.values())}
    # Isolation is needed to prepare the pilot, before pilot-plan/review can pass.
    validator.stage_index = module.STAGES.index("pilot")
    validator.validate_state()
    validator.validate_decomposition_map()
    if validator.errors:
        raise ValueError("approved decomposition preflight failed: " + "; ".join(validator.errors))
    return validator.docs


def render_asset(root: Path, asset_id: str, manifest_fragment: Path | None = None) -> tuple[Path, Path]:
    manifest_path = root / "asset-manifest.json"
    if manifest_fragment is not None:
        manifest_path = (root / manifest_fragment).resolve()
        shard_root = (root / "page-shards").resolve()
        if not manifest_path.is_relative_to(shard_root) or manifest_path.suffix.lower() != ".json" or not manifest_path.is_file():
            raise ValueError("manifest fragment must be an existing JSON file under page-shards/")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("slide_id"), str):
            raise ValueError("manifest fragment must declare its slide_id")
    else:
        manifest = None
    docs = require_approved_inventory(root, manifest)
    if manifest is None:
        manifest = docs["asset-manifest.json"]
    assets = [asset for asset in manifest.get("assets", []) if isinstance(asset, dict) and asset.get("id") == asset_id]
    if len(assets) != 1:
        raise ValueError("exactly one asset manifest record is required")
    asset = assets[0]
    if manifest_fragment is not None and manifest["slide_id"] not in asset.get("slide_ids", [asset.get("slide_id")]):
        raise ValueError("fragment slide_id is not an approved owner of this asset")
    output_relative = asset.get("output")
    if not isinstance(output_relative, str):
        raise ValueError("asset output path must be declared before isolation review")
    asset_path = project_file(root, output_relative)
    asset_sha = file_sha256(asset_path)
    if asset.get("sha256") != asset_sha:
        raise ValueError("asset output hash is stale")
    source_items = source_items_for_asset(docs["decomposition-map.json"], asset_id)
    if not source_items:
        raise ValueError("asset has no visual object in the approved decomposition")
    source_hash = value_sha256(source_items)
    sheet = build_isolation_image(root, asset_path, source_items)
    evidence = asset.get("isolation_review") or {}
    if not isinstance(evidence, dict):
        raise ValueError("isolation_review must be an object")
    if evidence.get("status") == "passed":
        raise ValueError("approved isolation review is immutable; use a new asset or review version")
    image_relative = evidence.get("image_path", f"reviews/assets/{asset_id}-{asset_sha[:12]}-isolation.png")
    packet_relative = evidence.get("packet_path", f"reviews/assets/{asset_id}-{asset_sha[:12]}-isolation.md")
    image_path = project_file(root, image_relative)
    packet_path = project_file(root, packet_relative)
    review_dir = (root / "reviews" / "assets").resolve()
    if not image_path.is_relative_to(review_dir) or image_path.suffix.lower() != ".png":
        raise ValueError("isolation image must be a PNG under reviews/assets/")
    if not packet_path.is_relative_to(review_dir) or packet_path.suffix.lower() != ".md":
        raise ValueError("isolation list must be Markdown under reviews/assets/")
    rows = "\n".join(review_row(item) for item in source_items)
    packet = (
        f"# {asset_id} 逐件隔离审图\n\n"
        f"组件 SHA-256：`{asset_sha}`  \n清单项 SHA-256：`{source_hash}`\n\n"
        "从左到右：获批概念局部、透明素材叠在浅色棋盘、透明素材叠在深色背景。每行对应一次使用。\n\n"
        "| 页面 | 拆件编号 | 对象 | 角色 | 处理路线 | 概念图 |\n|---|---|---|---|---|---|\n"
        + rows + "\n\n"
        "人工检查：只有一个应独立操作的对象；无邻居残留、无不该出现的文字/数据；轮廓、方向、颜色与概念图相符；浅深背景均无白边黑边。\n"
    )
    buffer = BytesIO()
    sheet.save(buffer, format="PNG")
    payloads = ((image_path, buffer.getvalue()), (packet_path, packet.encode("utf-8")))
    for path, payload in payloads:
        if path.exists() and path.read_bytes() != payload:
            raise ValueError(f"review artifact exists with different content; use a new path: {path}")
    for path, payload in payloads:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    if evidence and (
        evidence.get("status") != "pending"
        or evidence.get("asset_sha256") != asset_sha
        or evidence.get("reviewed_items_sha256") != source_hash
    ):
        history = asset.get("review_history", [])
        if not isinstance(history, list):
            raise ValueError("review_history must be a list")
        history.append(evidence)
        asset["review_history"] = history
    asset["isolation_review"] = {
        "status": "pending", "reviewer": None, "image_path": image_relative,
        "image_sha256": file_sha256(image_path), "packet_path": packet_relative,
        "packet_sha256": file_sha256(packet_path), "asset_sha256": asset_sha,
        "reviewed_items_sha256": source_hash,
        "checks": {
            "single_object": False, "no_neighbor_residue": False,
            "no_ordinary_text_or_data": False, "edge_clean": False,
            "concept_match": False,
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return image_path, packet_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--asset", required=True)
    parser.add_argument("--manifest-fragment", type=Path, help="Update a page-local asset fragment instead of the global manifest")
    args = parser.parse_args()
    try:
        image_path, packet_path = render_asset(args.project_dir.resolve(), args.asset, args.manifest_fragment)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"Isolation image: {image_path}")
    print(f"Review list: {packet_path}")
    print("Human review is still required before marking the asset approved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
