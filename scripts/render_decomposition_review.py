#!/usr/bin/env python3
"""Render a G4-bound, full-size numbered decomposition review and item table."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit("Pillow is required for numbered decomposition reviews; probe it before inventory") from exc


def project_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("review path must be a non-empty project-relative path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError(f"path escapes project: {relative}")
    return path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_sha256(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def safe_cell(value: object) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def review_row(item: dict) -> str:
    return "| " + " | ".join(safe_cell(value) for value in (
        item["id"], item.get("inventory_pass"), item.get("kind"), item.get("label"),
        item.get("role"), item.get("component_id") or item.get("fill_slot_id"),
        item.get("source_class"), item.get("treatment"), item.get("occlusion"),
        ", ".join(item.get("overlaps", [])) if isinstance(item.get("overlaps"), list) else "",
        item.get("crop_padding"), item.get("text_data_decision"),
    )) + " |"


def require_complete_g4(root: Path) -> None:
    """Use the project contract's approval checks before producing new evidence."""
    validator_path = Path(__file__).resolve().with_name("validate_project.py")
    spec = importlib.util.spec_from_file_location("ai_presentation_validator_preflight", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load project validator for G4 preflight")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    validator = module.ProjectValidator(root, "inventory")
    validator.load_required_documents()
    validator.validate_state()
    if validator.errors:
        raise ValueError("current G4 approval packet is incomplete or stale: " + "; ".join(validator.errors))


def require_reviewed_master(root: Path, slide_id: str, record: dict, concept_sha: str) -> None:
    master_relative = record.get("master_path")
    if not isinstance(master_relative, str):
        raise ValueError("decomposition master_path is required")
    master = project_file(root, master_relative)
    master_sha = file_sha256(master)
    if record.get("master_sha256") != master_sha:
        raise ValueError("decomposition master_sha256 is stale")
    manifest = json.loads((root / "component-master-manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("slides"), list):
        raise ValueError("component-master-manifest slides are required")
    masters = [
        item for item in manifest.get("slides", [])
        if isinstance(item, dict) and item.get("slide_id") == slide_id
    ]
    if len(masters) != 1:
        raise ValueError("one current textless master record is required")
    master_record = masters[0]
    if master_record.get("component_master_path") != master_relative or master_record.get("component_master_sha256") != master_sha:
        raise ValueError("decomposition must bind the current textless master")
    review = master_record.get("geometry_review")
    if not isinstance(review, dict) or review.get("status") != "passed" or review.get("display_scale_percent") != 100:
        raise ValueError("master geometry review must pass at 100% before decomposition")
    if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
        raise ValueError("master geometry reviewer is required")
    if review.get("reviewed_contentful_sha256") != concept_sha or review.get("reviewed_master_sha256") != master_sha:
        raise ValueError("master geometry review is stale")
    checks = review.get("checks")
    if not isinstance(checks, dict) or any(
        checks.get(field) is not True
        for field in ("composition_preserved", "fill_slots_preserved", "ordinary_text_removed")
    ):
        raise ValueError("master geometry review checks are incomplete")
    comparison_relative = review.get("comparison_path")
    if not isinstance(comparison_relative, str):
        raise ValueError("master geometry comparison evidence is required")
    comparison = project_file(root, comparison_relative)
    if comparison == master:
        raise ValueError("master geometry comparison must be a separate image")
    if review.get("comparison_sha256") != file_sha256(comparison):
        raise ValueError("master geometry comparison evidence is stale")


def build_review_image(concept: Path, items: list[dict]) -> Image.Image:
    """Draw the deterministic item overlay used by rendering and validation."""
    with Image.open(concept) as source:
        canvas = source.convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")
    width, height = canvas.size
    font_size = max(16, min(32, width // 60))
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default(size=font_size)
    colors = {"visual": (44, 214, 231, 255), "fill-slot": (255, 201, 85, 255), "omitted": (255, 98, 167, 255)}
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("every review item needs a stable string id")
        bbox = item.get("bbox")
        if (
            not isinstance(bbox, list) or len(bbox) != 4
            or any(not isinstance(value, (int, float)) for value in bbox)
            or bbox[0] < 0 or bbox[1] < 0 or bbox[2] <= 0 or bbox[3] <= 0
            or bbox[0] + bbox[2] > 1 or bbox[1] + bbox[3] > 1
        ):
            raise ValueError(f"invalid bbox for {item['id']}")
        x0, y0 = round(bbox[0] * width), round(bbox[1] * height)
        x1, y1 = round((bbox[0] + bbox[2]) * width), round((bbox[1] + bbox[3]) * height)
        kind = item.get("kind")
        color = colors.get(kind) if isinstance(kind, str) else None
        if color is None:
            raise ValueError(f"unknown kind for {item['id']}")
        draw.rectangle((x0, y0, x1, y1), outline=color, width=max(3, width // 400))
        label = item["id"]
        text_box = draw.textbbox((0, 0), label, font=font)
        label_w, label_h = text_box[2] - text_box[0], text_box[3] - text_box[1]
        label_y = max(0, y0 - label_h - 12)
        draw.rounded_rectangle((x0, label_y, min(width, x0 + label_w + 16), label_y + label_h + 10), radius=4, fill=(5, 16, 38, 232))
        draw.text((x0 + 8, label_y + 3), label, font=font, fill=color)
    return canvas


def render_slide(root: Path, slide_id: str) -> tuple[Path, Path]:
    map_path = root / "decomposition-map.json"
    decomposition = json.loads(map_path.read_text(encoding="utf-8"))
    records = [
        slide for slide in decomposition.get("slides", [])
        if isinstance(slide, dict) and slide.get("slide_id") == slide_id
    ]
    if len(records) != 1:
        raise ValueError(f"exactly one decomposition slide is required for {slide_id}")
    record = records[0]
    concept_relative = record.get("concept_path")
    if not isinstance(concept_relative, str):
        raise ValueError("concept_path must be a project-relative string")
    concept = project_file(root, concept_relative)
    concept_sha = file_sha256(concept)
    state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
    gates = state.get("gates", {}) if isinstance(state, dict) else {}
    if not isinstance(gates, dict):
        raise ValueError("run-state gates must be an object")
    g4 = gates.get("concept_contact_sheet", {})
    approved = g4.get("approved_artifacts", {}) if isinstance(g4, dict) else {}
    if not isinstance(g4, dict) or g4.get("status") != "approved" or not isinstance(approved, dict) or approved.get(concept_relative) != concept_sha:
        raise ValueError("current concept must have a hash-matching G4 approval")
    if not {"deck-spec.json", "concept-generation-log.json"}.issubset(approved):
        raise ValueError("G4 approval must bind the deck spec and concept generation log")
    versions = state.get("artifact_versions", {}) if isinstance(state, dict) else {}
    if not isinstance(versions, dict) or g4.get("artifact_version") != versions.get("concept_contact_sheet"):
        raise ValueError("G4 approval artifact version is stale")
    for relative, approved_sha in approved.items():
        if not isinstance(relative, str) or not isinstance(approved_sha, str):
            raise ValueError("G4 approved artifact entry is invalid")
        current = project_file(root, relative)
        if not current.is_file() or file_sha256(current) != approved_sha:
            raise ValueError(f"G4 approved artifact hash is stale: {relative}")
    decomposition_gate = gates.get("decomposition", {})
    if isinstance(decomposition_gate, dict) and decomposition_gate.get("status") == "approved":
        raise ValueError("approved decomposition is immutable; revise the map version and clear the old approval epoch first")
    if record.get("concept_sha256") != concept_sha:
        raise ValueError("decomposition concept_sha256 is stale")
    require_complete_g4(root)
    require_reviewed_master(root, slide_id, record, concept_sha)
    items = record.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("numbered decomposition items are required")
    items_sha256 = value_sha256(items)

    canvas = build_review_image(concept, items)
    rows = [review_row(item) for item in items]

    image_record = record.get("review_image") or {}
    packet_record = record.get("review_packet") or {}
    if not isinstance(image_record, dict) or not isinstance(packet_record, dict):
        raise ValueError("review_image and review_packet must be objects")
    version = decomposition.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("decomposition version is required for versioned review files")
    image_relative = image_record.get("path", f"reviews/{slide_id}-decomposition-{version}.png")
    packet_relative = packet_record.get("path", f"reviews/{slide_id}-decomposition-{version}.md")
    image_path = project_file(root, image_relative)
    packet_path = project_file(root, packet_relative)
    reviews_dir = (root / "reviews").resolve()
    if not image_path.is_relative_to(reviews_dir) or image_path.suffix.lower() != ".png":
        raise ValueError("review image must be a PNG under reviews/")
    if not packet_path.is_relative_to(reviews_dir) or packet_path.suffix.lower() != ".md":
        raise ValueError("review list must be a Markdown file under reviews/")
    packet = (
        f"# {slide_id} 拆件审图清单\n\n"
        f"概念图：`{concept_relative}`  \nSHA-256：`{concept_sha}`  \n"
        f"清单项 SHA-256：`{items_sha256}`\n\n"
        "编号框仅辅助定位；每一项是否真能单独选取、残余装饰是否漏列，必须由用户在 100% 图上确认。\n\n"
        "| 编号 | 盘点轮次 | 类别 | 对象 | 角色 | 对应组件/填充区 | 来源分类 | 处理决定 | 遮挡 | 叠放关系 | 裁剪留白 | 文数处理 |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        + "\n".join(rows) + "\n\n"
        "审批前检查：语义对象、箭头/连接线/阴影/装饰等残余对象、照片边界、事实敏感区域、两件对象是否被合并。\n"
    )
    image_buffer = BytesIO()
    canvas.save(image_buffer, format="PNG")
    image_bytes = image_buffer.getvalue()
    packet_bytes = packet.encode("utf-8")
    for output_path, payload in ((image_path, image_bytes), (packet_path, packet_bytes)):
        if output_path.exists() and output_path.read_bytes() != payload:
            raise ValueError(f"review artifact already exists with different content; use a new versioned path: {output_path}")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(image_bytes)
    packet_path.write_bytes(packet_bytes)
    record["review_image"] = {
        "path": image_relative,
        "sha256": file_sha256(image_path),
        "reviewed_concept_sha256": concept_sha,
        "reviewed_items_sha256": items_sha256,
        "display_scale_percent": 100,
    }
    record["review_packet"] = {
        "path": packet_relative, "sha256": file_sha256(packet_path),
        "reviewed_items_sha256": items_sha256,
    }
    map_path.write_text(json.dumps(decomposition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return image_path, packet_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--slide", required=True)
    args = parser.parse_args()
    try:
        image_path, packet_path = render_slide(args.project_dir.resolve(), args.slide)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"Review image: {image_path}")
    print(f"Review list: {packet_path}")
    print("Human decomposition approval is still required before assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
