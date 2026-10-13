#!/usr/bin/env python3
"""Prepare, but never approve, a full-size one-slide trial comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

from validate_project import ProjectValidator


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root: Path, version: str) -> Path:
    root = root.resolve()
    validator = ProjectValidator(root, "pilot", require_pilot_review=False)
    errors = validator.run()
    if errors:
        raise ValueError("pilot preflight failed: " + "; ".join(errors[:5]))
    bindings = validator.pilot_bindings()
    if bindings is None:
        raise ValueError("pilot bindings are incomplete")
    review_path = root / "pilot-review.json"
    if review_path.exists():
        raise ValueError("pilot-review.json already exists; keep prior evidence and use a new project/version")
    map_relative = f"pilot/{version}/pilot-assembly-map.json"
    map_path = root / map_relative
    if not map_path.is_file():
        raise ValueError("trial PPTX is missing; run assemble_editable_pptx.py --pilot-slide first")
    assembly = json.loads(map_path.read_text(encoding="utf-8"))
    if not isinstance(assembly, dict) or assembly.get("pilot_bindings") != bindings:
        raise ValueError("trial PPTX was assembled from stale or different source objects")
    if len(assembly.get("renders", [])) != 1:
        raise ValueError("the actual PPTX must have exactly one 1920x1080 render")
    render_record = assembly["renders"][0]
    render_path = root / render_record["path"]
    if not render_path.is_file() or sha256(render_path) != render_record.get("sha256"):
        raise ValueError("actual PPTX render is absent or stale")
    plan = validator.docs["pilot-plan.json"]
    deck = validator.docs["deck-spec.json"]
    slide = next(item for item in deck["slides"] if item["id"] == plan["slide_id"])
    concept_path = root / slide["concept_path"]
    evidence_dir = root / "reviews" / "pilot" / version
    side_path = evidence_dir / "side-by-side.png"
    overlay_path = evidence_dir / "overlay.png"
    packet_path = evidence_dir / "review-packet.md"
    if any(path.exists() for path in (side_path, overlay_path, packet_path)):
        raise ValueError("review evidence exists; use an unused version")
    with Image.open(concept_path) as source, Image.open(render_path) as output:
        if output.size != (1920, 1080) or output.format != "PNG":
            raise ValueError("trial render must be a real 1920x1080 PNG")
        if validator.quality_profile() == "production" and (
            source.width < 1600 or source.height < 900
            or abs(source.width / source.height - 16 / 9) > 0.01
        ):
            raise ValueError("production concept must be a full-size 16:9 image of at least 1600x900")
        # Some approved image providers emit 1672x941. Keep that source
        # immutable and scale it only in this comparison to the PPTX render.
        concept = source.convert("RGB").resize((1920, 1080), Image.Resampling.LANCZOS)
        rendered = output.convert("RGB")
        side = Image.new("RGB", (3840, 1080))
        side.paste(concept, (0, 0))
        side.paste(rendered, (1920, 0))
        side.save(side_path)
        Image.blend(concept, rendered, 0.5).save(overlay_path)
    manifest = validator.docs["asset-manifest.json"]
    assets = {item["id"]: item for item in manifest["assets"] if isinstance(item, dict)}
    isolation: list[dict[str, Any]] = []
    for component_id in plan["component_ids"]:
        asset = assets[component_id]
        record = asset.get("isolation_review", {})
        isolation.append({
            "component_id": component_id,
            "image_path": record.get("image_path"),
            "image_sha256": record.get("image_sha256"),
            "packet_path": record.get("packet_path"),
            "packet_sha256": record.get("packet_sha256"),
        })
    packet = [
        f"# 单页试拼审图：{plan['slide_id']}", "",
        "左：获批完整概念图按比例缩放至 1920×1080；右：实际 PPTX 1920×1080 渲染。叠图仅用于定位偏差，不按像素级纹理一致判定。", "",
        f"- 概念图：`{slide['concept_path']}`", f"- PPTX：`{assembly['output']}`", f"- 实渲染：`{render_record['path']}`",
        "- 并排图：`side-by-side.png`", "- 叠图：`overlay.png`", "",
        "## 逐件隔离图", "",
    ]
    packet.extend(f"- {item['component_id']}: `{item['image_path']}`（清单 `{item['packet_path']}`）" for item in isolation)
    packet.extend(["", "## 人工检查", "", "- [ ] 每件仅含一个可独立移动对象；无粘连或邻件残留", "- [ ] 没有缺失箭头、图形或图文组件", "- [ ] 无明显偏位、接缝、颜色和层级漂移", "- [ ] 文字和主图保留了可读、可展示的空间", "- [ ] 事实标签与获批内容一致；数据留空可填", "", "拒绝时在 `pilot-review.json.defects` 逐条填写对象/页面、证据路径、严重度、所属阶段和局部修复入口。若改概念图，必须新版本并重获受影响审批。", ""])
    packet_path.write_text("\n".join(packet), encoding="utf-8")
    review = {
        "version": version,
        "slide_id": plan["slide_id"],
        "status": "pending-human",
        "approval_phrase": None,
        "reviewer": None,
        "reviewed_at": None,
        "bindings": bindings,
        "assembly_map_path": map_relative,
        "pptx_sha256": assembly["sha256"],
        "render_sha256": sha256(render_path),
        "evidence": {
            "concept": {"path": slide["concept_path"], "sha256": sha256(concept_path)},
            "render": {"path": render_record["path"], "sha256": sha256(render_path)},
            "side_by_side": {"path": side_path.relative_to(root).as_posix(), "sha256": sha256(side_path)},
            "overlay": {"path": overlay_path.relative_to(root).as_posix(), "sha256": sha256(overlay_path)},
            "packet": {"path": packet_path.relative_to(root).as_posix(), "sha256": sha256(packet_path)},
            "isolation": isolation,
        },
        "checks": {key: False for key in ("single_object", "no_missing_objects", "placement", "seams", "color_and_z", "text_and_image_space", "truth_labels")},
        "defects": [],
    }
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return review_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        output = prepare(args.project_dir, args.version)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"Review packet prepared, human approval pending: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
