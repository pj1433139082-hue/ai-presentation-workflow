#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a standalone PPTX reconstruction proof from normalized project/scene.json.

This proof deck is independent of the APW assets-mode endpoint. It uses only
per-item PNG/JPEG sources, standalone SVG picture objects, and editable text boxes.
It never inserts a concept-slide raster.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

W_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENE = W_ROOT / "project" / "scene.json"
DEFAULT_OUTPUT = W_ROOT / "proof" / "independent-pptx"
EXPECTED_SLIDES = ("S01", "S02", "S03")
SLIDE_WIDTH_IN = 13.333333333333334
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg"}

NODE_BRIDGE = r"""
const fs = require("node:fs");
const pptxgen = require(process.argv[2]);
const cfg = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
async function main() {
  const pptx = new pptxgen();
  pptx.defineLayout({
    name: "APW_RECONSTRUCTION_CANVAS",
    width: cfg.slide_width_in,
    height: cfg.slide_height_in,
  });
  pptx.layout = "APW_RECONSTRUCTION_CANVAS";
  pptx.author = "APW reconstruction proof builder";
  pptx.company = "Independent reconstruction proof";
  pptx.title = "Independent slide reconstruction proof";
  pptx.subject = "Standalone proof deck; not formal APW assembly acceptance";
  for (const page of cfg.slides) {
    const slide = pptx.addSlide();
    slide.background = { color: "FFFFFF" };
    for (const item of page.items) {
      const p = item.position_in;
      if (item.type === "text") {
        const options = {
          x: p.x, y: p.y, w: p.w, h: p.h,
          objectName: item.id,
          fontFace: item.font_family,
          fontSize: item.font_size_pt,
          bold: item.bold,
          color: item.color,
          align: item.text_align,
          valign: "middle",
          margin: 0,
          wrap: true,
          fit: "none",
        };
        if (item.line_height_multiple > 0) options.lineSpacingMultiple = item.line_height_multiple;
        if (item.italic) options.italic = true;
        slide.addText(item.text, options);
      } else {
        slide.addImage({
          path: item.source_path,
          x: p.x, y: p.y, w: p.w, h: p.h,
          objectName: item.id,
          altText: item.id + " - " + item.role,
        });
      }
    }
  }
  await pptx.writeFile({ fileName: cfg.output_path });
}
main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exitCode = 1;
});
"""

def fail(message: str) -> None:
    raise ValueError(message)

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def ensure_within(path: Path, root: Path, label: str) -> Path:
    resolved, root_resolved = path.resolve(), root.resolve()
    if not resolved.is_relative_to(root_resolved):
        fail(f"{label} must stay inside worktree {root_resolved}: {resolved}")
    return resolved

def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{label} must be a number")
    number = float(value)
    if not math.isfinite(number):
        fail(f"{label} must be finite")
    return number

def canvas_size(value: Any, label: str) -> tuple[int, int]:
    if not isinstance(value, dict):
        fail(f"{label} must contain width and height")
    result: list[int] = []
    for field in ("width", "height"):
        raw = value.get(field)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            fail(f"{label}.{field} must be a positive integer")
        number = float(raw)
        if not math.isfinite(number) or number <= 0 or not number.is_integer():
            fail(f"{label}.{field} must be a positive integer")
        result.append(int(number))
    return result[0], result[1]

def box(value: Any, label: str, canvas: tuple[int, int], allow_off_canvas: bool = False) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        fail(f"{label} must be [x, y, width, height]")
    x, y, w, h = (finite_number(value[i], f"{label}[{i}]") for i in range(4))
    if w <= 0 or h <= 0:
        fail(f"{label} width and height must be positive")
    eps = 1e-5
    if not allow_off_canvas and (x < -eps or y < -eps or x + w > canvas[0] + eps or y + h > canvas[1] + eps):
        fail(f"{label} lies outside {canvas[0]}x{canvas[1]} canvas")
    if allow_off_canvas and (x + w <= 0 or y + h <= 0 or x >= canvas[0] or y >= canvas[1]):
        fail(f"{label} does not intersect the slide canvas")
    return x, y, w, h

def resolve_source(raw_path: Any, slide_id: str, scene_dir: Path, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        fail(f"{label} requires a non-empty path")
    supplied = Path(raw_path)
    candidates = [supplied] if supplied.is_absolute() else [
        scene_dir / supplied,
        W_ROOT / supplied,
        W_ROOT / "project" / "layers" / slide_id / supplied,
        W_ROOT / "shards" / slide_id / supplied,
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_relative_to(W_ROOT.resolve()) and resolved.is_file():
            return resolved
    fail(f"{label} was not found inside W: {raw_path}")

def concept_path_for(slide: dict[str, Any], slide_id: str, scene_path: Path) -> Path | None:
    raw = slide.get("concept_path") or slide.get("concept")
    candidates = ([Path(str(raw))] if Path(str(raw)).is_absolute() else
                  [scene_path.parent / str(raw), W_ROOT / str(raw)]) if raw else [
                      W_ROOT / "project" / "concepts" / f"{slide_id}.png"
                  ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return None

def bind_source_contract(scene_path: Path) -> dict[str, Any]:
    """Bind the proof to project map, asset prompt records, and reconstruction inputs."""
    project_root = scene_path.parent.resolve()
    result: dict[str, Any] = {"status": "bound", "dependency_files": []}

    def bind_file(path: Path, label: str, expected_hash: str | None = None) -> dict[str, str]:
        try:
            relative_candidate = path.relative_to(project_root)
        except ValueError:
            fail(f"{label} path is not project-relative: {path}")
        cursor = project_root
        for part in relative_candidate.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                fail(f"{label} path crosses a symlink: {cursor}")
        resolved = path.resolve()
        if not resolved.is_relative_to(project_root):
            fail(f"{label} path escapes project root: {resolved}")
        if not resolved.is_file():
            fail(f"{label} file is missing: {resolved}")
        current_hash = sha256_file(resolved)
        if expected_hash and current_hash != expected_hash:
            fail(f"{label} SHA-256 mismatch: {resolved}")
        return {"path": resolved.relative_to(W_ROOT.resolve()).as_posix(), "sha256": current_hash}

    map_path = project_root / "reconstruction-map.json"
    manifest_path = project_root / "asset-manifest.json"
    generation_path = project_root / "concept-generation-log.json"
    for key, path in (("reconstruction_map", map_path), ("asset_manifest", manifest_path),
                      ("concept_generation_log", generation_path)):
        if path.is_file():
            result[key] = bind_file(path, key.replace("_", " "))
    if not map_path.is_file():
        result["status"] = "source-map-not-present"

    if map_path.is_file():
        reconstruction_map = json.loads(map_path.read_text(encoding="utf-8"))
        dependencies = reconstruction_map.get("dependency_files", [])
        if not isinstance(dependencies, list):
            fail("reconstruction-map.json dependency_files must be an array")
        for index, dependency in enumerate(dependencies):
            if not isinstance(dependency, dict) or not isinstance(dependency.get("path"), str):
                fail(f"reconstruction-map.json dependency_files[{index}] needs a path")
            dependency_hash = dependency.get("sha256")
            if not isinstance(dependency_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", dependency_hash):
                fail(f"reconstruction-map.json dependency_files[{index}] needs a SHA-256")
            relative = Path(dependency["path"])
            if relative.is_absolute() or ".." in relative.parts:
                fail(f"reconstruction-map.json dependency path is not project-relative: {relative}")
            result["dependency_files"].append(
                bind_file(project_root / relative, f"dependency_files[{index}]", dependency_hash)
            )
    result["dependency_file_count"] = len(result["dependency_files"])
    result["generation_inputs_bound"] = bool(result.get("asset_manifest") and result.get("concept_generation_log"))
    return result

def full_canvas(frame: tuple[float, float, float, float], canvas: tuple[int, int]) -> bool:
    x, y, w, h = frame
    eps = 0.01
    return x <= eps and y <= eps and w >= canvas[0] - eps and h >= canvas[1] - eps

def alpha_adjusted_frame(source: Path, visible_bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Place a transparent wordmark by its visible pixels, not its padding."""
    try:
        from PIL import Image
    except ImportError as exc:
        fail(f"Pillow is required to place transparent special typography: {exc}")
    with Image.open(source) as image:
        width, height = image.size
        rgba = image.convert("RGBA")
        alpha_bbox = rgba.getchannel("A").getbbox()
    if not alpha_bbox:
        fail(f"special-typography source has no visible pixels: {source}")
    left, top, right, bottom = alpha_bbox
    target_x, target_y, target_w, target_h = visible_bbox
    scale_x = target_w / (right - left)
    scale_y = target_h / (bottom - top)
    return (target_x - left * scale_x, target_y - top * scale_y, width * scale_x, height * scale_y)

def normalize_scene(scene_path: Path, allow_incomplete: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    scene_path = ensure_within(scene_path, W_ROOT, "scene path")
    if not scene_path.is_file():
        fail(f"scene file not found: {scene_path}")
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    if not isinstance(scene, dict) or not isinstance(scene.get("slides"), list) or not scene["slides"]:
        fail("merged scene.json must contain a non-empty slides[] array")
    canvas = canvas_size(scene.get("canvas"), "scene.canvas")
    slides_by_id: dict[str, dict[str, Any]] = {}
    for index, slide in enumerate(scene["slides"]):
        if not isinstance(slide, dict):
            fail(f"scene.slides[{index}] must be an object")
        slide_id = slide.get("slide_id")
        if not isinstance(slide_id, str) or slide_id not in EXPECTED_SLIDES:
            fail(f"unexpected or missing slide_id at scene.slides[{index}]")
        if slide_id in slides_by_id:
            fail(f"duplicate slide_id: {slide_id}")
        if canvas_size(slide.get("canvas", scene.get("canvas")), f"{slide_id}.canvas") != canvas:
            fail(f"{slide_id}.canvas differs from scene.canvas")
        slides_by_id[slide_id] = slide
    missing = [sid for sid in EXPECTED_SLIDES if sid not in slides_by_id]
    if missing and not allow_incomplete:
        fail(f"scene is missing required pages {missing}; use --allow-incomplete only for a marked dry run")
    if len(slides_by_id) < 2:
        fail("at least two pages are required for a reconstruction proof")

    width_in = SLIDE_WIDTH_IN
    height_in = width_in * canvas[1] / canvas[0]
    scale_in = width_in / canvas[0]
    pages, source_bindings, concept_hashes = [], {}, {}
    scene_dir = scene_path.parent

    for slide_id in EXPECTED_SLIDES:
        slide = slides_by_id.get(slide_id)
        if slide is None:
            continue
        raw_items = slide.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            fail(f"{slide_id}.items must be a non-empty array")
        concept = concept_path_for(slide, slide_id, scene_path)
        concept_hash = sha256_file(concept) if concept else None
        if concept_hash:
            concept_hashes[slide_id] = concept_hash
        items, seen, backgrounds, media = [], set(), [], []

        for index, raw_item in enumerate(raw_items):
            label = f"{slide_id}.items[{index}]"
            if not isinstance(raw_item, dict):
                fail(f"{label} must be an object")
            item_id, role = raw_item.get("id"), raw_item.get("role")
            if not isinstance(item_id, str) or not item_id:
                fail(f"{label}.id is required")
            if item_id in seen:
                fail(f"{slide_id} has duplicate item id {item_id}")
            seen.add(item_id)
            if not isinstance(role, str) or not role:
                fail(f"{label}.role is required")
            z = finite_number(raw_item.get("z"), f"{label}.z")
            item_bbox = box(raw_item.get("bbox"), f"{label}.bbox", canvas)
            representation = raw_item.get("representation")
            if representation not in {"asset", "native"}:
                fail(f"{label}.representation must be asset or native")
            source = resolve_source(raw_item.get("path"), slide_id, scene_dir, f"{label}.path") if raw_item.get("path") else None
            source_extension = source.suffix.lower() if source else ""
            # Some source manifests retain the semantic glyph text on a
            # special-typography PNG. That is a picture asset, not an ordinary
            # editable text box; ordinary text remains editable as usual.
            image_backed_typography = (
                role == "special-typography" and source_extension in IMAGE_EXTENSIONS
            )
            is_text = raw_item.get("type") == "text" and not image_backed_typography
            if role == "text" and not is_text:
                fail(f"{label} role=text requires type=text")
            if source:
                source_rel = source.relative_to(W_ROOT.resolve()).as_posix()
                source_hash = sha256_file(source)
                source_bindings.setdefault(source_rel, {"path": source_rel, "sha256": source_hash})
            elif not is_text:
                fail(f"{label} requires a path to an independent image or SVG")
            if is_text:
                text = raw_item.get("text")
                if not isinstance(text, str) or not text.strip() or source is None:
                    fail(f"{label} needs non-empty text and its native source JSON path")
                if source.suffix.lower() == ".json":
                    try:
                        source_record = json.loads(source.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        source_record = None
                    if isinstance(source_record, dict) and "text" in source_record and source_record["text"] != text:
                        fail(f"{label} text does not match its native text source")
                font_size = finite_number(raw_item.get("font_size_px"), f"{label}.font_size_px")
                font_weight = finite_number(raw_item.get("font_weight", 400), f"{label}.font_weight")
                line_height = finite_number(raw_item.get("line_height", 1.0), f"{label}.line_height")
                if font_size <= 0 or line_height <= 0 or line_height > 9.99:
                    fail(f"{label} has an invalid font size or line height")
                color = raw_item.get("color", "#000000")
                if not isinstance(color, str) or not re.fullmatch(r"#?[0-9a-fA-F]{6}", color):
                    fail(f"{label}.color must be a six-digit hex value")
                align = raw_item.get("text_align", "left")
                if align == "middle":
                    align = "center"
                if align not in {"left", "center", "right", "justify"}:
                    fail(f"{label}.text_align is unsupported: {align}")
                font_family = raw_item.get("font_family", "Arial")
                if not isinstance(font_family, str) or not font_family.strip():
                    fail(f"{label}.font_family is required")
                font_family = font_family.split(",")[0].strip().strip("'\\\"")
                items.append({
                    "id": item_id, "role": role, "type": "text", "text": text, "z": z,
                    "frame_px": list(item_bbox), "frame_kind": "bbox",
                    "source_path": source_rel, "source_sha256": source_hash,
                    "position_in": {
                        "x": item_bbox[0] * scale_in, "y": item_bbox[1] / canvas[1] * height_in,
                        "w": item_bbox[2] * scale_in, "h": item_bbox[3] / canvas[1] * height_in,
                    },
                    "font_family": font_family, "font_size_pt": font_size * scale_in * 72,
                    "font_size_px": font_size, "font_weight": font_weight, "bold": font_weight >= 600,
                    "color": color.lstrip("#").upper(), "text_align": align,
                    "line_height_multiple": line_height, "italic": bool(raw_item.get("italic", False)),
                })
                continue

            if source is None or source.suffix.lower() not in IMAGE_EXTENSIONS:
                fail(f"{label} source must be a PNG, JPEG, or SVG file")
            extension = source.suffix.lower()
            if extension == ".svg":
                frame = box(raw_item.get("asset_frame_bbox", raw_item.get("bbox")), f"{label}.asset_frame_bbox", canvas, allow_off_canvas=True)
                frame_kind = "asset_frame_bbox"
            else:
                if image_backed_typography and not raw_item.get("image_frame") and not raw_item.get("asset_frame_bbox"):
                    frame = alpha_adjusted_frame(source, item_bbox)
                    frame_kind = "alpha_adjusted_visible_bbox"
                else:
                    frame = box(raw_item.get("image_frame", raw_item.get("asset_frame_bbox", raw_item.get("bbox"))), f"{label}.image_frame", canvas, allow_off_canvas=True)
                    frame_kind = "image_frame"
                if role != "background" and full_canvas(frame, canvas):
                    fail(f"{label} is a full-canvas raster; possible flattened-slide source")
            if concept_hash and source_hash == concept_hash:
                fail(f"{label} source hash equals the concept raster; flattened concept use is prohibited")
            if role == "background":
                backgrounds.append({"z": z, "frame": frame, "source": source, "extension": extension})
            items.append({
                "id": item_id, "role": role, "type": "image", "z": z,
                "frame_px": list(frame), "frame_kind": frame_kind,
                "source_path": str(source), "source_path_rel": source_rel, "source_sha256": source_hash,
                "extension": extension,
                "position_in": {
                    "x": frame[0] * scale_in, "y": frame[1] / canvas[1] * height_in,
                    "w": frame[2] * scale_in, "h": frame[3] / canvas[1] * height_in,
                },
            })
            media.append({"id": item_id, "role": role, "path": source_rel, "sha256": source_hash, "extension": extension})

        if len(backgrounds) != 1:
            fail(f"{slide_id} requires exactly one independent background item; found {len(backgrounds)}")
        bg = backgrounds[0]
        if bg["extension"] != ".png" or not full_canvas(bg["frame"], canvas):
            fail(f"{slide_id} background must be a full-canvas independent PNG")
        if any(item["z"] < bg["z"] for item in items):
            fail(f"{slide_id} background z must be at or below every other item")
        items.sort(key=lambda item: item["z"])
        role_counts = {}
        for item in items:
            role_counts[item["role"]] = role_counts.get(item["role"], 0) + 1
        pages.append({
            "slide_id": slide_id, "items": items, "role_counts": role_counts,
            "concept_path": concept.relative_to(W_ROOT.resolve()).as_posix() if concept and concept.is_relative_to(W_ROOT.resolve()) else None,
            "concept_sha256": concept_hash, "media": media,
        })

    complete = not missing and len(pages) == len(EXPECTED_SLIDES)
    metadata = {
        "complete": complete, "expected_slide_ids": list(EXPECTED_SLIDES),
        "present_slide_ids": [page["slide_id"] for page in pages], "missing_slide_ids": missing,
        "canvas": {"width": canvas[0], "height": canvas[1]}, "slide_width_in": width_in,
        "slide_height_in": height_in, "scene_path": scene_path.relative_to(W_ROOT.resolve()).as_posix(),
        "scene_sha256": sha256_file(scene_path), "sources": sorted(source_bindings.values(), key=lambda x: x["path"]),
        "concept_hashes": concept_hashes,
    }
    payload = {
        "slide_width_in": width_in, "slide_height_in": height_in,
        "slides": [{
            "slide_id": page["slide_id"],
            "items": [{key: item[key] for key in (
                "id", "role", "type", "position_in", "font_family", "font_size_pt", "bold",
                "color", "text_align", "line_height_multiple", "italic", "text", "source_path", "extension"
            ) if key in item} for item in page["items"]],
        } for page in pages],
    }
    return {"pages": pages, "payload": payload}, metadata

def pptxgen_module() -> tuple[Path, str]:
    appdata = Path(os.environ.get("APPDATA", r"C:\Users\14331\AppData\Roaming"))
    package_root = appdata / "npm" / "node_modules" / "pptxgenjs"
    package_json = package_root / "package.json"
    if not package_json.is_file():
        fail(f"PptxGenJS not found at {package_root}")
    package = json.loads(package_json.read_text(encoding="utf-8"))
    version = str(package.get("version", "unknown"))
    if not (package_root / package.get("main", "dist/pptxgen.cjs.js")).is_file():
        fail(f"PptxGenJS entrypoint missing under {package_root}")
    return package_root, version

def run_pptxgenjs(payload: dict[str, Any], output_path: Path) -> tuple[str, str]:
    module_root, version = pptxgen_module()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload["output_path"] = str(output_path)
    helper_fd, helper_path = tempfile.mkstemp(prefix="apw-pptx-", suffix=".cjs", dir=output_path.parent)
    data_fd, data_path = tempfile.mkstemp(prefix="apw-scene-", suffix=".json", dir=output_path.parent)
    try:
        with os.fdopen(helper_fd, "w", encoding="utf-8") as stream:
            stream.write(NODE_BRIDGE)
        with os.fdopen(data_fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
        result = subprocess.run(
            [os.environ.get("APW_NODE", "node"), helper_path, str(module_root), data_path],
            cwd=str(W_ROOT), check=True, capture_output=True, text=True, encoding="utf-8",
        )
        return version, result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        fail(f"PptxGenJS failed: {exc.stderr.strip() or exc.stdout.strip() or exc}")
    finally:
        for path in (helper_path, data_path):
            try:
                Path(path).unlink()
            except FileNotFoundError:
                pass

def inspect_package(pptx_path: Path, pages: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    if not pptx_path.is_file() or not pptx_path.stat().st_size:
        fail(f"PPTX output is missing or empty: {pptx_path}")
    expected_media = {}
    for page in pages:
        for item in page["items"]:
            if item["type"] == "image":
                expected_media[item["source_sha256"]] = {"path": item["source_path_rel"], "sha256": item["source_sha256"]}
    with zipfile.ZipFile(pptx_path) as package:
        names = package.namelist()
        slide_xmls = sorted(name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
        media = sorted(name for name in names if name.startswith("ppt/media/"))
        embedded_font_parts = sorted(name for name in names if name.startswith("ppt/fonts/") or name.endswith(".fntdata"))
        media_hashes = {sha256_bytes(package.read(name)): name for name in media}
        externals = []
        for name in names:
            if name.endswith(".rels"):
                content = package.read(name).decode("utf-8", errors="replace")
                if 'TargetMode="External"' in content or "TargetMode='External'" in content:
                    externals.append(name)
        missing = [bind for hash_value, bind in expected_media.items() if hash_value not in media_hashes]
        if missing:
            fail(f"PPTX is missing original embedded source bytes: {missing}")
        if externals:
            fail(f"PPTX contains external relationships and is not portable: {externals}")
        if len(slide_xmls) != len(pages):
            fail(f"PPTX contains {len(slide_xmls)} slides; expected {len(pages)}")
        concepts = [sid for sid, value in metadata["concept_hashes"].items() if value in media_hashes]
        if concepts:
            fail(f"PPTX embeds the flattened concept raster for {concepts}")
    return {
        "pptx_sha256": sha256_file(pptx_path), "pptx_size_bytes": pptx_path.stat().st_size,
        "slide_xml_count": len(slide_xmls), "embedded_media_count": len(media),
        "source_media_hashes_found": len(expected_media),
        "source_media": [
            {**binding, "embedded_member": media_hashes[binding["sha256"]]}
            for binding in expected_media.values()
        ],
        "embedded_font_parts": embedded_font_parts,
        "external_relationships": externals, "concept_rasters_embedded": concepts,
    }

def normalize_ppt_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")

def render_and_inspect(pptx_path: Path, render_dir: Path, pages: list[dict[str, Any]], canvas: dict[str, int]) -> dict[str, Any]:
    try:
        import win32com.client
    except ImportError as exc:
        fail(f"pywin32 required for actual PowerPoint COM rendering: {exc}")
    render_dir.mkdir(parents=True, exist_ok=True)
    app = presentation = None
    slide_evidence = []
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        app.DisplayAlerts = 0
        version = str(app.Version)
        presentation = app.Presentations.Open(str(pptx_path), True, False, False)
        if int(presentation.Slides.Count) != len(pages):
            fail(f"PowerPoint reopened {presentation.Slides.Count} slides; expected {len(pages)}")
        for page_index, page in enumerate(pages, start=1):
            slide = presentation.Slides.Item(page_index)
            expected = {item["id"]: item for item in page["items"]}
            actual_shapes, text_shapes, unknown = [], [], []
            picture_types = {11, 13, 28}
            for i in range(1, int(slide.Shapes.Count) + 1):
                shape = slide.Shapes.Item(i)
                name, shape_type = str(shape.Name), int(shape.Type)
                has_text = int(shape.HasTextFrame) != 0 and int(shape.TextFrame.HasText) != 0
                record = {
                    "name": name, "type": shape_type, "left_pt": float(shape.Left), "top_pt": float(shape.Top),
                    "width_pt": float(shape.Width), "height_pt": float(shape.Height), "has_text": has_text,
                }
                actual_shapes.append(record)
                item = expected.get(name)
                if has_text:
                    text_value = normalize_ppt_text(str(shape.TextFrame.TextRange.Text))
                    text_record = {**record, "text": text_value, "font_name": str(shape.TextFrame.TextRange.Font.Name)}
                    text_shapes.append(text_record)
                    if item is None or item["type"] != "text":
                        unknown.append({"name": name, "type": shape_type, "reason": "unexpected text shape"})
                    elif text_value != normalize_ppt_text(item["text"]):
                        fail(f"PowerPoint text mismatch for {page['slide_id']}/{name}")
                elif shape_type not in picture_types:
                    unknown.append({"name": name, "type": shape_type, "reason": "not a picture object"})
            expected_text = sum(item["type"] == "text" for item in page["items"])
            expected_pics = sum(item["type"] == "image" for item in page["items"])
            actual_pics = sum(shape["type"] in picture_types and not shape["has_text"] for shape in actual_shapes)
            if int(slide.Shapes.Count) != len(page["items"]):
                fail(f"{page['slide_id']} shape count differs from scene item count")
            expected_svgs = {item["id"] for item in page["items"] if item["type"] == "image" and item["extension"] == ".svg"}
            actual_svgs = {shape["name"] for shape in actual_shapes if shape["type"] == 28}
            expected_rasters = {item["id"] for item in page["items"] if item["type"] == "image" and item["extension"] != ".svg"}
            actual_rasters = {shape["name"] for shape in actual_shapes if shape["type"] in {11, 13}}
            if len(text_shapes) != expected_text or actual_pics != expected_pics or unknown:
                fail(f"{page['slide_id']} object-kind mismatch: text={len(text_shapes)}/{expected_text}, pictures={actual_pics}/{expected_pics}, other={unknown}")
            if actual_svgs != expected_svgs or actual_rasters != expected_rasters:
                fail(f"{page['slide_id']} embedded image kinds do not match the source formats")
            if {shape["name"] for shape in actual_shapes} != set(expected):
                fail(f"{page['slide_id']} PowerPoint shape names do not bind one-to-one to scene item IDs")
            render_path = render_dir / f"{page['slide_id']}.png"
            slide.Export(str(render_path), "PNG", canvas["width"], canvas["height"])
            if not render_path.is_file() or not render_path.stat().st_size:
                fail(f"PowerPoint did not render {render_path}")
            from PIL import Image
            with Image.open(render_path) as image:
                size = list(image.size)
            if size != [canvas["width"], canvas["height"]]:
                fail(f"{page['slide_id']} render size {size} differs from canvas {canvas}")
            slide_evidence.append({
                "slide_id": page["slide_id"], "render_path": render_path.relative_to(W_ROOT.resolve()).as_posix(),
                "render_sha256": sha256_file(render_path), "render_size_px": size,
                "shape_count": len(actual_shapes), "picture_count": actual_pics,
                "svg_graphic_picture_count": len(actual_svgs), "editable_text_shape_count": len(text_shapes), "role_counts": page["role_counts"],
                "shapes": actual_shapes, "text_shapes": text_shapes, "unexpected_shapes": unknown,
            })
        return {"renderer": "Microsoft PowerPoint COM", "renderer_version": version,
                "slide_count": int(presentation.Slides.Count), "slides": slide_evidence}
    finally:
        if presentation is not None:
            try:
                presentation.Close()
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass

def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Independent PPTX reconstruction proof", "",
        f"- Status: {report['status']}",
        f"- Scope: {report['proof_scope']}",
        f"- Formal assembly acceptance: {report['formal_assembly_acceptance']}",
        f"- Backend: PptxGenJS {report['backend']['pptxgenjs_version']}; rendered by {report['powerpoint']['renderer']} {report['powerpoint']['renderer_version']}.",
        f"- Scene: {report['scene']['path']} (SHA-256 {report['scene']['sha256']}).",
        f"- PPTX: {report['pptx']['path']} (SHA-256 {report['pptx']['pptx_sha256']}).", "",
        "## PowerPoint reopen and render evidence", "",
    ]
    source_contract = report.get("source_contract", {})
    if source_contract.get("reconstruction_map") and source_contract.get("asset_manifest"):
        lines.insert(7, f"- Source contract: {source_contract['reconstruction_map']['path']} and {source_contract['asset_manifest']['path']}; {source_contract['dependency_file_count']} generation/source dependencies verified by hash.")
    else:
        lines.insert(7, "- Source contract: no reconstruction map and asset manifest were provided.")
    font_binding = report.get("font_binding", {})
    if font_binding:
        declared = ", ".join(font_binding["declared_in_scene"]) or "none"
        observed = ", ".join(font_binding["observed_by_powerpoint"]) or "none"
        font_note = "font files are not embedded; another system may substitute" if not font_binding["fonts_embedded"] else "font files are embedded"
        lines.insert(8, f"- Text fonts: declared {declared}; observed by PowerPoint {observed}; {font_note}.")
    for slide in report["powerpoint"]["slides"]:
        lines.append(
            f"- {slide['slide_id']}: {slide['shape_count']} total objects "
            f"({slide['picture_count']} picture objects, {slide['editable_text_shape_count']} editable text boxes); "
            f"render {slide['render_path']} (SHA-256 {slide['render_sha256']})."
        )
    if report.get("editability_experiment"):
        edit = report["editability_experiment"]
        lines.extend([
            "", "## Copy-only editability experiment", "",
            f"- Status: {edit['status']}; PowerPoint {edit['powerpoint_version']}.",
            f"- Native text edit saved and reopened: {edit['edited_text_persisted_after_save_reopen']}; picture move/Undo restored its original position: {edit['undo_restored_position']}.",
            f"- Evidence: {edit['evidence_path']} (SHA-256 {edit['evidence_sha256']}); source PPTX hash matched this report.",
        ])
    lines.extend(["", "The builder binds item sources by SHA-256 and confirms they are embedded in the PPTX. "
                  "Counts and file bindings do not establish visual faithfulness or prove that no scene element was omitted.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, default=DEFAULT_SCENE, help="merged normalized project/scene.json")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT, help="proof output folder inside W")
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="build a marked dry-run; default requires S01, S02, and S03")
    args = parser.parse_args()
    scene_path = args.scene if args.scene.is_absolute() else W_ROOT / args.scene
    out_dir = ensure_within(args.out_dir if args.out_dir.is_absolute() else W_ROOT / args.out_dir, W_ROOT, "output path")
    scene, metadata = normalize_scene(scene_path, args.allow_incomplete)
    out_dir.mkdir(parents=True, exist_ok=True)
    complete = metadata["complete"]
    name = "independent-reconstruction-proof-3pages.pptx" if complete else "independent-reconstruction-proof-incomplete.pptx"
    status = "built-3-page-independent-proof" if complete else "incomplete-dry-run-only"
    pptx_path = out_dir / name
    backend_version, node_output = run_pptxgenjs(scene["payload"], pptx_path)
    module_root, _ = pptxgen_module()
    package_json_path = module_root / "package.json"
    package_info = json.loads(package_json_path.read_text(encoding="utf-8"))
    package_entry = module_root / package_info.get("main", "dist/pptxgen.cjs.js")
    package_evidence = inspect_package(pptx_path, scene["pages"], metadata)
    if any(sha256_file(W_ROOT / source["path"]) != source["sha256"] for source in metadata["sources"]):
        fail("one or more input source files changed during export")
    powerpoint = render_and_inspect(
        pptx_path, out_dir / "powerpoint-renders", scene["pages"], metadata["canvas"]
    )
    declared_fonts = sorted({
        item["font_family"] for page in scene["pages"] for item in page["items"]
        if item["type"] == "text" and item.get("font_family")
    })
    observed_fonts = sorted({
        shape["font_name"] for page in powerpoint["slides"] for shape in page["text_shapes"]
        if shape.get("font_name")
    })
    report = {
        "status": status,
        "proof_scope": "independent PPTX reconstruction proof outside APW assets-mode endpoint",
        "formal_assembly_acceptance": "not-claimed",
        "visual_faithfulness_assessment": "not-determined-by-file-binding-or-object-counts",
        "concept_slide_raster_used_as_source": False,
        "complete": complete,
        "scene": {"path": metadata["scene_path"], "sha256": metadata["scene_sha256"]},
        "source_contract": bind_source_contract(scene_path),
        "canvas": metadata["canvas"],
        "expected_slide_ids": metadata["expected_slide_ids"],
        "present_slide_ids": metadata["present_slide_ids"],
        "missing_slide_ids": metadata["missing_slide_ids"],
        "builder": {
            "path": Path(__file__).resolve().relative_to(W_ROOT.resolve()).as_posix(),
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "backend": {
            "pptxgenjs_version": backend_version,
            "pptxgenjs_module": str(module_root),
            "pptxgenjs_package_json_sha256": sha256_file(package_json_path),
            "pptxgenjs_entry_path": package_entry.relative_to(module_root).as_posix(),
            "pptxgenjs_entry_sha256": sha256_file(package_entry),
            "node_output": node_output,
        },
        "pptx": {"path": pptx_path.relative_to(W_ROOT.resolve()).as_posix(), **package_evidence},
        "source_files": metadata["sources"],
        "source_bytes_unchanged": True,
        "powerpoint": powerpoint,
        "font_binding": {
            "declared_in_scene": declared_fonts,
            "observed_by_powerpoint": observed_fonts,
            "fonts_embedded": bool(package_evidence["embedded_font_parts"]),
            "embedded_font_parts": package_evidence["embedded_font_parts"],
        },
        "pages": [{
            "slide_id": page["slide_id"], "item_count": len(page["items"]),
            "editable_text_item_count": sum(item["type"] == "text" for item in page["items"]),
            "picture_item_count": sum(item["type"] == "image" for item in page["items"]),
            "role_counts": page["role_counts"], "concept_path": page["concept_path"],
            "concept_sha256": page["concept_sha256"],
            "items": [{
                "id": item["id"], "role": item["role"], "type": item["type"], "z": item["z"],
                "frame_px": item["frame_px"],
                "source_path": item.get("source_path_rel", item.get("source_path")),
                "source_sha256": item["source_sha256"], "frame_kind": item["frame_kind"],
            } for item in page["items"]],
        } for page in scene["pages"]],
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    experiment_path = out_dir / "editability-test.json"
    if experiment_path.is_file():
        try:
            experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            experiment = None
        if (
            isinstance(experiment, dict)
            and experiment.get("status") == "passed"
            and experiment.get("original_unchanged") is True
            and experiment.get("source_pptx_sha256") == package_evidence["pptx_sha256"]
        ):
            report["editability_experiment"] = {
                "status": experiment["status"],
                "powerpoint_version": experiment["powerpoint_version"],
                "edited_text_persisted_after_save_reopen": experiment["edited_text_persisted_after_save_reopen"],
                "undo_restored_position": experiment["undo_restored_position"],
                "evidence_path": experiment_path.relative_to(W_ROOT.resolve()).as_posix(),
                "evidence_sha256": sha256_file(experiment_path),
                "source_pptx_sha256": experiment["source_pptx_sha256"],
            }
    report_path = out_dir / "proof-evidence.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path = out_dir / "proof-evidence.md"
    write_markdown(report, markdown_path)
    print(json.dumps({
        "status": status, "pptx": str(pptx_path), "evidence": str(report_path),
        "renderer": powerpoint["renderer_version"],
        "pages": [{
            "slide_id": slide["slide_id"], "shapes": slide["shape_count"], "pictures": slide["picture_count"],
            "svg_graphics": slide["svg_graphic_picture_count"], "editable_text": slide["editable_text_shape_count"], "render": slide["render_path"],
        } for slide in powerpoint["slides"]],
        "source_bytes_unchanged": True, "external_relationships": package_evidence["external_relationships"],
        "concept_rasters_embedded": package_evidence["concept_rasters_embedded"],
    }, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

