#!/usr/bin/env python3
"""Render a source-vs-output photo review without approving an alteration."""

from __future__ import annotations

import argparse
import hashlib
import json
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_file(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative.strip() or "\\" in relative or ":" in relative:
        raise ValueError("photo review path must be project-relative")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("photo review path escapes project")
    return path


def comparison_image(source: Path, output: Path) -> Image.Image:
    panels = []
    for path in (source, output):
        with Image.open(path) as opened:
            rgba = opened.convert("RGBA")
        if rgba.width < 3 or rgba.height < 3:
            raise ValueError("photo must have visible dimensions")
        panels.append(rgba)
    width = max(panel.width for panel in panels)
    height = max(panel.height for panel in panels)
    margin, gap = 16, 20
    canvas = Image.new("RGB", (margin * 2 + width * 2 + gap, margin * 2 + height), (18, 28, 43))
    for index, panel in enumerate(panels):
        background = Image.new("RGB", (width, height), (224, 231, 239))
        draw = ImageDraw.Draw(background)
        for y in range(0, height, 20):
            for x in range(0, width, 20):
                if (x // 20 + y // 20) % 2:
                    draw.rectangle((x, y, min(width - 1, x + 19), min(height - 1, y + 19)), fill=(190, 201, 213))
        background.paste(panel, ((width - panel.width) // 2, (height - panel.height) // 2), panel)
        canvas.paste(background, (margin + index * (width + gap), margin))
    return canvas


def render(root: Path, asset_id: str) -> Path:
    root = root.resolve()
    manifest_path = root / "asset-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets = [asset for asset in manifest.get("assets", []) if isinstance(asset, dict) and asset.get("id") == asset_id]
    if len(assets) != 1:
        raise ValueError("exactly one photo asset is required")
    asset = assets[0]
    if asset.get("role") not in {"ordinary-photo", "photo-cutout"} or not str(asset.get("strategy", "")).startswith("postprocessed-"):
        raise ValueError("photo comparison is only for a postprocessed ordinary photo")
    source_record = asset.get("source_photo")
    if not isinstance(source_record, dict):
        raise ValueError("classified source photo is missing")
    source = project_file(root, source_record.get("path"))
    output = project_file(root, asset.get("output"))
    if digest(source) != source_record.get("sha256") or digest(output) != asset.get("sha256"):
        raise ValueError("photo source or output hash is stale")
    existing = asset.get("photo_review")
    if isinstance(existing, dict) and existing.get("status") == "passed":
        raise ValueError("passed photo review is immutable; use a new output version")
    image = comparison_image(source, output)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    relative = f"reviews/photos/{asset_id}-{asset['sha256'][:12]}-comparison.png"
    path = project_file(root, relative)
    if path.exists() and path.read_bytes() != buffer.getvalue():
        raise ValueError("photo review evidence path is occupied; use a new output version")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buffer.getvalue())
    if isinstance(existing, dict):
        history = asset.setdefault("photo_review_history", [])
        if not isinstance(history, list):
            raise ValueError("photo_review_history must be a list")
        history.append(existing)
    asset["photo_review"] = {
        "status": "pending", "reviewer": None,
        "source_sha256": source_record["sha256"], "output_sha256": asset["sha256"],
        "image_path": relative, "image_sha256": digest(path),
        "checks": {
            "subject_identity": False, "architecture": False,
            "perspective": False, "key_scene_content": False,
            "no_factual_additions": False, "source_text_preserved": False,
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--asset", required=True)
    args = parser.parse_args()
    try:
        path = render(args.project_dir, args.asset)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"Photo comparison: {path}")
    print("A human must compare source and output before approving the photo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
