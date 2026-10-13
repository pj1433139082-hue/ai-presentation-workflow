#!/usr/bin/env python3
"""Prepare immutable visual evidence for every assembled slide; never approve it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

from assemble_editable_pptx import render_powerpoint
from deck_qa_evidence import contact_sheet, overlay, side_by_side
from validate_project import ProjectValidator, value_sha256


CHECKS = (
    "independent_objects", "geometry", "hierarchy", "color_and_z", "content_truth",
    "visual_relationships", "readability_full_size", "main_image_space", "editability",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(root: Path, version: str) -> Path:
    root = root.resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", version):
        raise ValueError("version must be a safe short identifier")
    validator = ProjectValidator(root, "assembly")
    errors = validator.run()
    if errors:
        raise ValueError("assembly preflight failed: " + "; ".join(errors[:5]))
    assembly = validator.docs["assembly-map.json"]
    deck = validator.docs["deck-spec.json"]
    scene = validator.docs["scene-graph.json"]
    manifest = validator.docs["asset-manifest.json"]
    if not isinstance(assembly, dict) or not assembly.get("output"):
        raise ValueError("a rendered PPTX assembly is required")
    previous = root / "qa-report.json"
    if not previous.resolve().is_relative_to(root):
        raise ValueError("QA report path must stay inside the project")
    old_report: bytes | None = None
    archive_path: Path | None = None
    if previous.exists():
        old_report = previous.read_bytes()
        old = json.loads(old_report.decode("utf-8"))
        if not isinstance(old, dict):
            raise ValueError("existing QA report must be an object")
        if old.get("status") == "pending" and not old.get("subject_sha256"):
            old_report = None
        elif old.get("status") in {"pending-human", "failed"}:
            old_version = old.get("version")
            if not isinstance(old_version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", old_version) or old_version == version:
                raise ValueError("preserve the old QA version and select a distinct safe new version")
            archive_path = root / "reviews" / "qa" / old_version / "qa-report.snapshot.json"
            if not archive_path.parent.resolve().is_relative_to(root) or archive_path.exists():
                raise ValueError("old QA packet cannot be safely archived; do not overwrite it")
        else:
            raise ValueError("passed/released QA cannot be overwritten; create a new project revision")
    out = root / "reviews" / "qa" / version
    if not out.parent.resolve().is_relative_to(root):
        raise ValueError("QA evidence path must stay inside the project")
    if out.exists():
        raise ValueError("QA evidence version already exists")
    deck_slides = deck["slides"]
    assembled = assembly["slides"]
    renders = assembly["renders"]
    if len(deck_slides) != len(assembled) or len(renders) != len(assembled):
        raise ValueError("full-deck slide/render coverage differs")
    out.mkdir(parents=True)
    verified_renders: list[dict[str, str]] = []
    if validator.quality_profile() == "production":
        fresh = render_powerpoint(root / assembly["output"], out / "verified-renders", len(assembled))
        for index, (record, current) in enumerate(zip(fresh, renders), start=1):
            verified_path = Path(record["path"])
            current_path = root / current["path"]
            with Image.open(verified_path) as verified, Image.open(current_path) as prior:
                if verified.size != prior.size or ImageChops.difference(verified.convert("RGB"), prior.convert("RGB")).getbbox():
                    raise ValueError(f"slide {index} declared render does not match a fresh PowerPoint render of the current PPTX")
            verified_renders.append({"path": verified_path.relative_to(root).as_posix(),
                                     "sha256": digest(verified_path), "pptx_sha256": assembly["sha256"]})
    scene_by_id = {item["slide_id"]: item for item in scene["slides"]}
    asset_by_id = {item["id"]: item for item in manifest["assets"]}
    slide_records: list[dict[str, Any]] = []
    thumbnails: list[tuple[str, Image.Image]] = []
    evidence_files: list[str] = []
    for index, (deck_slide, assembled_slide, rendered) in enumerate(zip(deck_slides, assembled, renders), start=1):
        slide_id = deck_slide["id"]
        if assembled_slide["slide_id"] != slide_id or assembled_slide["output_index"] != index:
            raise ValueError(f"{slide_id} assembly order differs from the approved deck")
        concept_path = root / deck_slide["concept_path"]
        render_path = root / rendered["path"]
        with Image.open(concept_path) as concept_image, Image.open(render_path) as render_image:
            if concept_image.format != "PNG" or render_image.format != "PNG":
                raise ValueError(f"{slide_id} concept and render must be PNG")
            side = side_by_side(concept_image, render_image)
            blend = overlay(concept_image, render_image)
            thumbnails.append((slide_id, render_image.copy()))
        side_path = out / f"{slide_id}-side-by-side.png"
        blend_path = out / f"{slide_id}-overlay.png"
        packet_path = out / f"{slide_id}-review.md"
        side.save(side_path)
        blend.save(blend_path)
        component_ids = assembled_slide["component_ids"]
        packet_path.write_text("\n".join([
            f"# 全册逐页审图：{slide_id}", "",
            "左：获批完整概念图；右：实际 PPTX 全尺寸渲染。叠图只帮助定位，不要求纹理像素完全相等。", "",
            f"- 概念图：`{deck_slide['concept_path']}`",
            f"- 实渲染：`{rendered['path']}`",
            f"- 组件：{', '.join(component_ids)}",
            f"- 可编辑填充区：{', '.join(assembled_slide['fill_slot_ids'])}", "",
            "逐项检查：独立对象、构图、层级、颜色与叠放、内容真实、视觉关系、100% 可读性、主图空间、编辑性。",
            "缺陷要写明页/对象、证据、严重度、所属阶段、局部修复入口与次数；不能改用整页扁平图。", "",
        ]), encoding="utf-8")
        paths = [concept_path, render_path, side_path, blend_path, packet_path]
        evidence_files.extend(path.relative_to(root).as_posix() for path in paths)
        slide_records.append({
            "slide_id": slide_id, "status": "pending-human", "reviewer": None, "reviewed_at": None,
            "checks": {key: False for key in CHECKS}, "issues": [],
            "bindings": {
                "concept_sha256": digest(concept_path), "render_sha256": digest(render_path),
                "deck_slide_sha256": value_sha256(deck_slide),
                "scene_slide_sha256": value_sha256(scene_by_id[slide_id]),
                "assembly_slide_sha256": value_sha256(assembled_slide),
                "style_sha256": digest(root / "style-contract.json"),
                "assets": {component_id: value_sha256(asset_by_id[component_id]) for component_id in component_ids},
                "pptx_sha256": assembly["sha256"],
            },
            "evidence": {
                "side_by_side": {"path": side_path.relative_to(root).as_posix(), "sha256": digest(side_path)},
                "overlay": {"path": blend_path.relative_to(root).as_posix(), "sha256": digest(blend_path)},
                "packet": {"path": packet_path.relative_to(root).as_posix(), "sha256": digest(packet_path)},
            },
            "evidence_files": [path.relative_to(root).as_posix() for path in paths],
        })
    contact = out / "final-contact-sheet.png"
    contact_sheet(thumbnails).save(contact)
    exceptions = out / "exception-register.json"
    index_path = out / "deliverable-index.json"
    write_json(exceptions, {"status": "pending-human", "issues": []})
    write_json(index_path, {
        "status": "draft", "pptx": {"path": assembly["output"], "sha256": assembly["sha256"]},
        "contact_sheet": {"path": contact.relative_to(root).as_posix(), "sha256": digest(contact)},
        "slides": [{"slide_id": row["slide_id"], "status": "pending-human"} for row in slide_records],
    })
    evidence_files.extend(path.relative_to(root).as_posix() for path in (contact, exceptions, index_path))
    evidence_files.extend(row["path"] for row in verified_renders)
    report = {
        "version": version, "status": "pending-human", "subject_sha256": assembly["sha256"],
        "checks_performed": ["contract", "alpha", "inventory", "overlay"],
        "deck_checks": {"reference_transfer": False, "composition_richness": False,
                        "readability_full_size": False, "visual_coherence": False, "truth_consistency": False},
        "deck_bindings": {
            "reference_study_sha256": digest(root / "reference-study.json"),
            "style_sha256": digest(root / "style-contract.json"),
            "deck_sha256": digest(root / "deck-spec.json"),
            "storyboard_sha256": digest(root / "storyboard.json"),
            "pptx_sha256": assembly["sha256"],
            "contact_sheet_sha256": digest(contact),
        },
        "evidence_files": evidence_files,
        "verified_renders": verified_renders,
        "final_contact_sheet": contact.relative_to(root).as_posix(), "contact_sheet_sha256": digest(contact),
        "exception_register": exceptions.relative_to(root).as_posix(),
        "deliverable_index": index_path.relative_to(root).as_posix(),
        "differences": [], "exceptions": [], "repairs": [], "slides": slide_records,
        "final_reviewer": None,
    }
    if old_report is not None and archive_path is not None:
        archive_path.write_bytes(old_report)
    write_json(previous, report)
    return previous


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.project_dir, args.version)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"Full-deck QA packet prepared; human review pending: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
