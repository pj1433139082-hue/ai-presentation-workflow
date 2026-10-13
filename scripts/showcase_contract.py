"""Validation and local-draft packaging for the explicit showcase-v1 route.

This contract is deliberately separate from the strict human-gated production
validator. It checks declared files, hashes, editable object mappings, real
PPTX/render artifacts, and recorded agent QA. It does not authenticate who
wrote a JSON record, prove when a concept was created, grade aesthetics, or
approve a human gate.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import posixpath
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from PIL import Image, ImageChops

try:
    from project_snapshot import assert_current, document_snapshot, publish_new_directory
    from agent_qa import DECK_CHECKS, PAGE_CHECKS, evidence_file, review_findings, review_identity
    from deck_qa_evidence import contact_sheet
except ImportError:  # import when this module is loaded as scripts.showcase_contract
    from .project_snapshot import assert_current, document_snapshot, publish_new_directory
    from .agent_qa import DECK_CHECKS, PAGE_CHECKS, evidence_file, review_findings, review_identity
    from .deck_qa_evidence import contact_sheet


CONTRACT_VERSION = "showcase-v1"
STAGES = ("concept", "assembly", "qa", "export")
BASE_DOCS = (
    "project-kind.json",
    "brief.json",
    "deck-spec.json",
    "reference-study.json",
    "style-contract.json",
    "concept-generation-log.json",
    "scene-graph.json",
    "asset-manifest.json",
    "run-state.json",
)
ASSEMBLY_DOCS = ("assembly-map.json",)
QA_DOCS = ("showcase-review.json",)
IMAGE_TYPES = {"picture", "source-evidence"}
ELEMENT_TYPES = {"text", "shape", "connector", "table", "chart", *IMAGE_TYPES}
TRUTH_STATES = {"verified", "illustrative", "hypothetical", "pending", "not-applicable"}
ILLUSTRATIVE_LABELS = ("示意", "示例", "虚构", "仅作演示")
HYPOTHETICAL_LABELS = ("假设场景", "情景假设", "假设数据")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
CONCEPT_INPUT_DOCS = (
    "project-kind.json",
    "brief.json",
    "deck-spec.json",
    "reference-study.json",
    "style-contract.json",
    "concept-generation-log.json",
    "run-state.json",
)
HUMAN_GATE_NOT_CLAIMED = {f"G{number}": "not-claimed" for number in range(1, 6)}

_NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
_SLIDE_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(encoded)


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _load_json(root: Path, relative: str, errors: list[str], required: bool = True) -> dict[str, Any] | None:
    path = root / relative
    if not path.is_file():
        if required:
            errors.append(f"{relative}: required canonical file is missing")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{relative}: cannot read valid UTF-8 JSON ({exc})")
        return None
    if not isinstance(value, dict):
        errors.append(f"{relative}: top-level value must be an object")
        return None
    return value


def _safe_file(root: Path, relative: Any, errors: list[str], location: str) -> Path | None:
    if not isinstance(relative, str) or not relative.strip():
        errors.append(f"{location}: project-relative path is required")
        return None
    candidate = Path(relative)
    if candidate.is_absolute() or any(part in {"..", ""} for part in candidate.parts):
        errors.append(f"{location}: path must stay inside the project")
        return None
    try:
        resolved_root = root.resolve()
        resolved = (root / candidate).resolve()
        if not resolved.is_relative_to(resolved_root):
            errors.append(f"{location}: path resolves outside the project")
            return None
    except (OSError, RuntimeError, ValueError):
        errors.append(f"{location}: unsafe project-relative path")
        return None
    if not resolved.is_file():
        errors.append(f"{location}: file does not exist: {relative}")
        return None
    return resolved


def _digest_matches(root: Path, relative: Any, expected: Any, errors: list[str], location: str) -> Path | None:
    path = _safe_file(root, relative, errors, location)
    if path is None:
        return None
    if not _is_sha(expected):
        errors.append(f"{location}: SHA-256 digest is missing or malformed")
    elif _sha256_file(path).lower() != expected.lower():
        errors.append(f"{location}: SHA-256 does not match the current file")
    return path


def _is_png(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            return stream.read(8) == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


def _is_supported_image(path: Path) -> bool:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.format in {"PNG", "JPEG", "WEBP"} and image.width > 0 and image.height > 0
    except (ImportError, OSError, ValueError):
        return False


def _image_size(path: Path) -> tuple[int, int] | None:
    if not _is_png(path):
        return None
    try:
        with path.open("rb") as stream:
            header = stream.read(24)
        if len(header) < 24:
            return None
        return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")
    except OSError:
        return None


def _has_real_alpha(path: Path) -> bool:
    try:
        from PIL import Image

        with Image.open(path) as image:
            if image.mode not in {"RGBA", "LA", "PA"}:
                return False
            alpha = image.getchannel("A")
            low, high = alpha.getextrema()
            return low < 255 and high > 0
    except (ImportError, OSError, ValueError):
        return False


def _is_full_concept(path: Path) -> bool:
    """Keep the declared widescreen composition, not a generator's pixel size."""
    size = _image_size(path)
    return bool(_is_png(path) and _is_supported_image(path) and size and size[0] > 0 and size[1] > 0 and abs(size[0] / size[1] - 16 / 9) <= 0.02)


def _hex_color(value: Any) -> tuple[int, int, int] | None:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return None
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb:
        srgb = value / 255.0
        channels.append(srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(foreground: str, background: str) -> float | None:
    fg, bg = _hex_color(foreground), _hex_color(background)
    if fg is None or bg is None:
        return None
    first, second = sorted((_relative_luminance(fg), _relative_luminance(bg)), reverse=True)
    return (first + 0.05) / (second + 0.05)


def _reject_fixtures(value: Any, location: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        if value.get("quality_profile") == "validation-fixture" or value.get("fixture_only") is True:
            errors.append(f"{location}: validation-fixture data cannot qualify as a showcase")
        for key, item in value.items():
            _reject_fixtures(item, f"{location}.{key}", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_fixtures(item, f"{location}[{index}]", errors)


def _keyed_rows(rows: Any, key: str, location: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        errors.append(f"{location}: must be a list")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        where = f"{location}[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{where}: must be an object")
            continue
        value = row.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"{where}.{key}: non-empty string required")
        elif value in result:
            errors.append(f"{where}.{key}: duplicate identifier {value!r}")
        else:
            result[value] = row
    return result


def _load_contract_docs(root: Path, stage: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    names = list(BASE_DOCS)
    if stage in {"assembly", "qa", "export"}:
        names.extend(ASSEMBLY_DOCS)
    if stage in {"qa", "export"}:
        names.extend(QA_DOCS)
    documents: dict[str, dict[str, Any]] = {}
    for name in names:
        document = _load_json(root, name, errors)
        if document is not None:
            documents[name] = document
    return documents


def _validate_kind_and_mode(documents: dict[str, dict[str, Any]], errors: list[str]) -> None:
    kind = documents.get("project-kind.json")
    if kind is not None and kind != {"contract_version": CONTRACT_VERSION, "purpose": "showcase"}:
        errors.append("project-kind.json: must be exactly {'contract_version':'showcase-v1','purpose':'showcase'}")
    brief = documents.get("brief.json")
    if brief is not None:
        if brief.get("quality_profile") != "draft":
            errors.append("brief.json.quality_profile: must be 'draft'; project purpose is declared separately by project-kind.json")
        if not isinstance(brief.get("audience"), str) or not brief["audience"].strip():
            errors.append("brief.json.audience: non-empty intended audience is required")
        if not isinstance(brief.get("goal"), str) or not brief["goal"].strip():
            errors.append("brief.json.goal: non-empty presentation goal is required")
        sources = brief.get("source_map")
        if not isinstance(sources, list):
            errors.append("brief.json.source_map: must be a list of content-source records")
        elif not sources:
            errors.append("brief.json.source_map: at least one content source or explicit example-source note is required")
    state = documents.get("run-state.json")
    if state is not None:
        if state.get("mode") != "showcase-local-draft":
            errors.append("run-state.json.mode: must be 'showcase-local-draft'")
        _reject_human_gate_claims(state, "run-state.json", errors)


def _reject_human_gate_claims(value: Any, location: str, errors: list[str]) -> None:
    forbidden = {"approved", "accepted", "passed", "complete", "released"}
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {"g1", "g2", "g3", "g4", "g5", "release"} and isinstance(child, dict):
                status = child.get("status")
                if isinstance(status, str) and status.lower() in forbidden:
                    errors.append(f"{location}.{key}: showcase route must not claim a human G1-G5/release approval")
            if key.lower() in {"human_gates", "gates"} and isinstance(child, dict):
                for gate, record in child.items():
                    if isinstance(record, dict) and isinstance(record.get("status"), str) and record["status"].lower() in forbidden:
                        errors.append(f"{location}.{key}.{gate}: showcase route must not claim a human gate approval")
                    elif isinstance(record, str) and record.lower() in forbidden:
                        errors.append(f"{location}.{key}.{gate}: showcase route must not claim a human gate approval")
            _reject_human_gate_claims(child, f"{location}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_human_gate_claims(child, f"{location}[{index}]", errors)


def _validate_sources_and_references(root: Path, docs: dict[str, dict[str, Any]], errors: list[str]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    brief = docs.get("brief.json", {})
    source_rows = _keyed_rows(brief.get("source_map"), "id", "brief.json.source_map", errors)
    for source_id, source in source_rows.items():
        if source.get("truth_status") not in TRUTH_STATES:
            errors.append(f"brief.json.source_map[{source_id}].truth_status: unsupported truth status")
        if not isinstance(source.get("kind"), str) or not source["kind"].strip():
            errors.append(f"brief.json.source_map[{source_id}].kind: non-empty string required")
        if not isinstance(source.get("locator"), str) or not source["locator"].strip():
            errors.append(f"brief.json.source_map[{source_id}].locator: non-empty locator required")
        if source.get("path") is not None:
            _digest_matches(root, source.get("path"), source.get("sha256"), errors, f"brief.json.source_map[{source_id}].path")
        elif source.get("truth_status") == "verified":
            errors.append(f"brief.json.source_map[{source_id}]: verified source must bind a local path and SHA-256")
        elif source.get("truth_status") == "illustrative" and not source.get("locator", "").strip():
            errors.append(f"brief.json.source_map[{source_id}]: illustrative example source needs an explicit explanation")

    reference = docs.get("reference-study.json", {})
    references = _keyed_rows(reference.get("references", []), "id", "reference-study.json.references", errors)
    if not references:
        errors.append("reference-study.json.references: at least one analyzed local design reference is required")
    for reference_id, row in references.items():
        if row.get("status") != "analyzed":
            errors.append(f"reference-study.json.references[{reference_id}].status: must be analyzed")
        image = _digest_matches(root, row.get("image_path"), row.get("sha256"), errors, f"reference-study.json.references[{reference_id}].image_path")
        if not isinstance(row.get("source_locator"), str) or not row["source_locator"].strip():
            errors.append(f"reference-study.json.references[{reference_id}].source_locator: source URL or local catalog locator is required")
        for field in ("usage_note", "transferable_rules", "project_translation", "do_not_copy"):
            item = row.get(field)
            if field in {"transferable_rules", "project_translation", "do_not_copy"}:
                if not isinstance(item, list) or not item or any(not isinstance(entry, str) or not entry.strip() for entry in item):
                    errors.append(f"reference-study.json.references[{reference_id}].{field}: non-empty explanatory list required")
            elif not isinstance(item, str) or not item.strip():
                errors.append(f"reference-study.json.references[{reference_id}].{field}: non-empty explanation required")
        if image is not None and not _is_supported_image(image):
            errors.append(f"reference-study.json.references[{reference_id}].image_path: PNG, JPEG, or WebP reference image is required")
    selected = docs.get("style-contract.json", {}).get("selected_reference_ids")
    if not isinstance(selected, list) or not selected or any(value not in references for value in selected):
        errors.append("style-contract.json.selected_reference_ids: must identify existing analyzed references")
    if reference.get("selected_reference_ids") != selected:
        errors.append("reference-study.json.selected_reference_ids: must match the project's selected references")
    return source_rows, references


def _copy_rows(slide: dict[str, Any], where: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    rows = _keyed_rows(slide.get("copy"), "id", f"{where}.copy", errors)
    if not rows:
        errors.append(f"{where}.copy: at least one exact visible-copy record is required")
    for copy_id, row in rows.items():
        if row.get("truth_status") not in TRUTH_STATES:
            errors.append(f"{where}.copy[{copy_id}].truth_status: unsupported truth status")
        if not isinstance(row.get("role"), str) or not row["role"].strip():
            errors.append(f"{where}.copy[{copy_id}].role: non-empty string required")
        if not isinstance(row.get("text"), str) or not row["text"].strip():
            errors.append(f"{where}.copy[{copy_id}].text: non-empty exact visible text required")
        sources = row.get("source_ids", [])
        if not isinstance(sources, list) or any(not isinstance(source_id, str) for source_id in sources):
            errors.append(f"{where}.copy[{copy_id}].source_ids: must be a list of source IDs")
    title_rows = [row for row in rows.values() if row.get("role") == "title"]
    message_rows = [row for row in rows.values() if row.get("role") == "key-takeaway"]
    if len(title_rows) != 1 or title_rows[0].get("text") != slide.get("title"):
        errors.append(f"{where}: exactly one title copy item must match deck-spec.title")
    if len(message_rows) != 1 or message_rows[0].get("text") != slide.get("message"):
        errors.append(f"{where}: exactly one key-takeaway copy item must match deck-spec.message")
    return rows


def _validate_concepts(root: Path, docs: dict[str, dict[str, Any]], errors: list[str], facts: dict[str, Any], *, include_assembly: bool = True) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    deck = docs.get("deck-spec.json", {})
    deck_slides = _keyed_rows(deck.get("slides"), "id", "deck-spec.json.slides", errors)
    if not deck_slides:
        errors.append("deck-spec.json.slides: at least one slide is required")
    delivery = docs.get("brief.json", {}).get("delivery")
    if isinstance(delivery, dict) and "expected_slide_ids" in delivery:
        expected_slide_ids = delivery.get("expected_slide_ids")
        location = "brief.json.delivery.expected_slide_ids"
        if not isinstance(expected_slide_ids, list) or not expected_slide_ids:
            errors.append(f"{location}: must be a non-empty list of unique slide ID strings")
        elif any(not isinstance(slide_id, str) or not slide_id.strip() for slide_id in expected_slide_ids):
            errors.append(f"{location}: every entry must be a non-empty slide ID string")
        elif len(set(expected_slide_ids)) != len(expected_slide_ids):
            errors.append(f"{location}: duplicate slide IDs are not allowed")
        elif expected_slide_ids != list(deck_slides):
            errors.append(f"{location}: must match deck-spec.json slide IDs in the same order")
    scene_slides = _keyed_rows(docs.get("scene-graph.json", {}).get("slides"), "slide_id", "scene-graph.json.slides", errors) if include_assembly else {}
    log_slides = _keyed_rows(docs.get("concept-generation-log.json", {}).get("slides"), "slide_id", "concept-generation-log.json.slides", errors)
    if include_assembly and set(deck_slides) != set(scene_slides):
        errors.append("scene-graph.json: slide coverage must exactly match deck-spec.json")
    if set(deck_slides) != set(log_slides):
        errors.append("concept-generation-log.json: every deck slide needs exactly one full concept record")
    if docs.get("concept-generation-log.json", {}).get("status") not in {"complete", "generated"}:
        errors.append("concept-generation-log.json.status: must state that all contentful concepts were generated")

    style = docs.get("style-contract.json", {})
    if include_assembly:
        profile = style.get("readability_profile")
        if not isinstance(profile, dict):
            errors.append("style-contract.json.readability_profile: explicit project-selected readability floors are required")
            profile = {}
        floors = profile.get("font_floors_pt")
        if not isinstance(floors, dict) or not floors:
            errors.append("style-contract.json.readability_profile.font_floors_pt: role-to-minimum-point-size map is required")
            floors = {}
        else:
            for role, floor in floors.items():
                if not isinstance(role, str) or not _number(floor) or not 1 <= float(floor) <= 200:
                    errors.append("style-contract.json.readability_profile.font_floors_pt: roles need finite floors in 1..200 pt")
        minimum_contrast = profile.get("minimum_contrast_ratio")
        if not _number(minimum_contrast) or not 1 <= float(minimum_contrast) <= 21:
            errors.append("style-contract.json.readability_profile.minimum_contrast_ratio: explicit ratio in 1..21 is required")
            minimum_contrast = 1

    source_rows, reference_rows = _validate_sources_and_references(root, docs, errors)
    required_input_hashes = {
        "brief": "brief.json",
        "deck_spec": "deck-spec.json",
        "reference_study": "reference-study.json",
        "style_contract": "style-contract.json",
    }
    actual_input_hashes = {}
    for key, filename in required_input_hashes.items():
        try:
            actual_input_hashes[key] = _sha256_file(root / filename)
        except OSError:
            actual_input_hashes[key] = None
    selected_refs = style.get("selected_reference_ids", [])

    for slide_id, slide in deck_slides.items():
        where = f"deck-spec.json.slides[{slide_id}]"
        if not isinstance(slide.get("title"), str) or not slide["title"].strip() or not isinstance(slide.get("message"), str) or not slide["message"].strip():
            errors.append(f"{where}: title and message are required")
        concept_path = slide.get("concept_path")
        concept_file = _safe_file(root, concept_path, errors, f"{where}.concept_path")
        log = log_slides.get(slide_id)
        if log is not None:
            if log.get("output_path") != concept_path:
                errors.append(f"concept-generation-log.json.slides[{slide_id}].output_path: must match the current deck concept_path")
            output = _digest_matches(root, log.get("output_path"), log.get("output_sha256"), errors, f"concept-generation-log.json.slides[{slide_id}].output_path")
            if output is not None and not _is_full_concept(output):
                errors.append(f"concept-generation-log.json.slides[{slide_id}].output_path: full-slide contentful concept must be a widescreen PNG; generator resolution is unrestricted")
            if log.get("input_sha256") != actual_input_hashes:
                errors.append(f"concept-generation-log.json.slides[{slide_id}].input_sha256: current brief/deck/reference/style input hashes differ")
            expected_copy = slide.get("copy")
            if log.get("copy_map") != expected_copy:
                errors.append(f"concept-generation-log.json.slides[{slide_id}].copy_map: must bind the exact current deck copy")
            expected_refs = []
            slide_refs = slide.get("reference_ids", selected_refs)
            if not isinstance(slide_refs, list) or not slide_refs or any(ref not in selected_refs for ref in slide_refs):
                errors.append(f"{where}.reference_ids: must select analyzed references from this project's style contract")
                slide_refs = []
            for reference_id in slide_refs:
                row = reference_rows.get(reference_id, {})
                expected_refs.append({"reference_id": reference_id, "path": row.get("image_path"), "sha256": row.get("sha256")})
            if log.get("reference_images") != expected_refs:
                errors.append(f"concept-generation-log.json.slides[{slide_id}].reference_images: must bind every selected local reference and hash")
            if log.get("status") not in {"generated", "complete"}:
                errors.append(f"concept-generation-log.json.slides[{slide_id}].status: concept must be generated")
        copy_rows = _copy_rows(slide, where, errors)
        for copy_id, item in copy_rows.items():
            source_ids = item.get("source_ids", [])
            if item.get("truth_status") == "verified" and not source_ids:
                errors.append(f"{where}.copy[{copy_id}]: verified claims require source_ids")
            for source_id in source_ids if isinstance(source_ids, list) else []:
                if source_id not in source_rows:
                    errors.append(f"{where}.copy[{copy_id}]: unknown brief source_id {source_id!r}")
                elif item.get("truth_status") == "verified" and source_rows[source_id].get("truth_status") != "verified":
                    errors.append(
                        f"{where}.copy[{copy_id}].truth_status: verified copy cannot be supported by "
                        f"{source_rows[source_id].get('truth_status')!r} source {source_id!r}"
                    )
        if concept_file is not None and not _is_full_concept(concept_file):
            errors.append(f"{where}.concept_path: full-slide contentful concept must be a widescreen PNG; generator resolution is unrestricted")

    if not include_assembly:
        facts["slide_ids"] = list(deck_slides)
        facts["asset_ids"] = []
        facts["concept_input_sha256"] = actual_input_hashes
        return deck_slides, {}, {}

    scene = docs.get("scene-graph.json", {})
    if scene.get("contract_version") != CONTRACT_VERSION:
        errors.append("scene-graph.json.contract_version: must be showcase-v1")
    asset_rows = _keyed_rows(docs.get("asset-manifest.json", {}).get("assets"), "id", "asset-manifest.json.assets", errors)
    asset_slide_refs: dict[str, set[str]] = {slide_id: set() for slide_id in deck_slides}
    for asset_id, asset in asset_rows.items():
        where = f"asset-manifest.json.assets[{asset_id}]"
        if asset.get("kind") not in IMAGE_TYPES:
            errors.append(f"{where}.kind: image assets must be picture or source-evidence")
        if asset.get("slide_id") not in deck_slides:
            errors.append(f"{where}.slide_id: must identify a current deck slide")
        if asset.get("truth_status") not in TRUTH_STATES:
            errors.append(f"{where}.truth_status: unsupported truth status")
        if not isinstance(asset.get("source_locator"), str) or not asset["source_locator"].strip():
            errors.append(f"{where}.source_locator: provenance locator is required")
        path = _digest_matches(root, asset.get("path"), asset.get("sha256"), errors, f"{where}.path")
        if path is not None:
            try:
                with Image.open(path) as media:
                    supported = media.format in {"PNG", "JPEG"}
                    media.verify()
            except (OSError, ValueError):
                supported = False
            if not supported:
                errors.append(f"{where}.path: picture/evidence must be a readable PNG or JPEG supported by this backend")
            if asset.get("requires_transparency") is True and not _has_real_alpha(path):
                errors.append(f"{where}.path: this declared cutout requires real transparent pixels")
        if asset.get("truth_status") == "verified" and not asset.get("source_id"):
            errors.append(f"{where}: verified factual media requires source_id")
        if asset.get("source_id") and asset.get("source_id") not in source_rows:
            errors.append(f"{where}.source_id: must point to brief.source_map")

    for slide_id, slide in scene_slides.items():
        where = f"scene-graph.json.slides[{slide_id}]"
        elements = slide.get("elements")
        element_rows = _keyed_rows(elements, "instance_id", f"{where}.elements", errors)
        if not element_rows:
            errors.append(f"{where}.elements: at least one independent object is required")
        canvas = slide.get("canvas")
        if not isinstance(canvas, dict) or not _number(canvas.get("width")) or not _number(canvas.get("height")) or float(canvas.get("width", 0)) <= 0 or float(canvas.get("height", 0)) <= 0:
            errors.append(f"{where}.canvas: positive width and height are required")
        text_labels: list[str] = []
        visible_data_strings: list[str] = []
        for instance_id, element in element_rows.items():
            location = f"{where}.elements[{instance_id}]"
            element_type = element.get("type")
            if element_type not in ELEMENT_TYPES:
                errors.append(f"{location}.type: unsupported independent object type")
                continue
            bbox = element.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4 or any(not _number(number) for number in bbox):
                errors.append(f"{location}.bbox: normalized [x,y,w,h] is required")
            elif bbox[0] < 0 or bbox[1] < 0 or bbox[2] <= 0 or bbox[3] <= 0 or bbox[0] + bbox[2] > 1.000001 or bbox[1] + bbox[3] > 1.000001:
                errors.append(f"{location}.bbox: object must stay inside normalized slide bounds")
            if not _number(element.get("z")):
                errors.append(f"{location}.z: numeric stacking order is required")
            if element_type == "text":
                copy_id = element.get("copy_id")
                copy = copy_rows_for_slide(deck_slides.get(slide_id, {})).get(copy_id)
                if copy is None or element.get("text") != copy.get("text") or element.get("role") != copy.get("role"):
                    errors.append(f"{location}: copy_id/text/role must exactly match the deck-spec copy map")
                else:
                    text_labels.append(str(copy.get("text", "")))
                    visible_data_strings.append(str(copy.get("text", "")))
                style_row = element.get("style")
                if not isinstance(style_row, dict):
                    errors.append(f"{location}.style: font/color style object is required")
                    continue
                role = element.get("role")
                floor = floors.get(role) if isinstance(floors, dict) else None
                size = style_row.get("font_size_pt")
                if floor is None:
                    errors.append(f"{location}.role: must have a project-declared font floor")
                elif not _number(size) or float(size) < float(floor):
                    errors.append(f"{location}.style.font_size_pt: must meet the project-declared {role!r} floor ({floor} pt)")
                fg, bg = style_row.get("color"), style_row.get("background_color")
                ratio = contrast_ratio(fg, bg)
                if ratio is None:
                    errors.append(f"{location}.style: valid foreground and solid background hex colors are required for contrast checking")
                elif ratio + 1e-9 < float(minimum_contrast):
                    errors.append(f"{location}.style: declared foreground/background contrast {ratio:.2f}:1 is below project floor {minimum_contrast}:1")
                for required in ("font_family", "align", "valign"):
                    if not isinstance(style_row.get(required), str) or not style_row[required].strip():
                        errors.append(f"{location}.style.{required}: non-empty string required")
            elif element_type == "shape":
                if not isinstance(element.get("shape_kind"), str) or not element["shape_kind"].strip():
                    errors.append(f"{location}.shape_kind: native shape kind is required")
                _validate_paint(element.get("fill"), f"{location}.fill", errors, optional=True)
                _validate_paint(element.get("line"), f"{location}.line", errors, optional=True)
            elif element_type == "connector":
                _validate_point(element.get("from"), f"{location}.from", errors)
                _validate_point(element.get("to"), f"{location}.to", errors)
                if element.get("arrowhead", "none") not in {"none", "triangle"}:
                    errors.append(f"{location}.arrowhead: must be none or triangle")
                _validate_paint(element.get("line"), f"{location}.line", errors, optional=False)
            elif element_type == "table":
                _validate_data_object(element, location, source_rows, errors, expected_label_key="visible_label")
                columns, rows = element.get("columns"), element.get("rows")
                if isinstance(columns, list):
                    visible_data_strings.extend(str(column.get("label", "")) for column in columns if isinstance(column, dict))
                if isinstance(columns, list) and isinstance(rows, list):
                    column_count = len(columns)
                    if column_count < 1 or not rows:
                        errors.append(f"{location}: native table needs at least one column and one data row")
                    for row_index, row in enumerate(rows):
                        cells = row.get("cells") if isinstance(row, dict) else None
                        if not isinstance(cells, list) or len(cells) != column_count:
                            errors.append(f"{location}.rows[{row_index}].cells: must match the declared column count")
                        elif isinstance(cells, list):
                            visible_data_strings.extend(str(cell) for cell in cells)
                if isinstance(element.get("visible_label"), str):
                    visible_data_strings.append(element["visible_label"])
            elif element_type == "chart":
                _validate_data_object(element, location, source_rows, errors, expected_label_key="title")
                if isinstance(element.get("title"), str):
                    visible_data_strings.append(element["title"])
                if not isinstance(element.get("chart_type"), str) or not element["chart_type"].strip():
                    errors.append(f"{location}.chart_type: native chart type is required")
                categories, series = element.get("categories"), element.get("series")
                if not isinstance(categories, list) or not categories or not isinstance(series, list) or not series:
                    errors.append(f"{location}: native chart requires categories and series")
                else:
                    for series_index, row in enumerate(series):
                        values = row.get("values") if isinstance(row, dict) else None
                        if not isinstance(values, list) or len(values) != len(categories) or any(not _number(value) for value in values):
                            errors.append(f"{location}.series[{series_index}].values: finite numeric values must match category count")
            elif element_type in IMAGE_TYPES:
                asset_id = element.get("asset_id")
                asset = asset_rows.get(asset_id)
                if asset is None or asset.get("slide_id") != slide_id or asset.get("kind") != element_type:
                    errors.append(f"{location}.asset_id: must reference a matching slide-local image asset")
                else:
                    asset_slide_refs.setdefault(slide_id, set()).add(asset_id)
                if isinstance(bbox, list) and len(bbox) == 4 and _number(bbox[2]) and _number(bbox[3]) and bbox[2] * bbox[3] >= 0.90:
                    errors.append(f"{location}: near-full-slide image is forbidden; do not flatten the deck page")
        for instance_id, element in element_rows.items():
            if element.get("type") in {"table", "chart"}:
                units = element.get("units")
                if isinstance(units, str) and units.strip() and units != "无" and not any(units in value for value in visible_data_strings):
                    errors.append(f"{where}.elements[{instance_id}].units: exact unit token must be visible in a same-slide editable text, table label/cell, or chart title")
        _require_truth_labels(element_rows.values(), text_labels, where, errors)

    for asset_id, asset in asset_rows.items():
        slide_id = asset.get("slide_id")
        if asset_id not in asset_slide_refs.get(slide_id, set()):
            errors.append(f"asset-manifest.json.assets[{asset_id}]: image asset is not referenced by its slide scene")
    facts["slide_ids"] = list(deck_slides)
    facts["asset_ids"] = list(asset_rows)
    facts["concept_input_sha256"] = actual_input_hashes
    return deck_slides, scene_slides, asset_rows


def copy_rows_for_slide(slide: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = slide.get("copy")
    if not isinstance(rows, list):
        return {}
    return {row.get("id"): row for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)}


def _validate_paint(value: Any, location: str, errors: list[str], *, optional: bool) -> None:
    if value is None and optional:
        return
    if not isinstance(value, dict):
        errors.append(f"{location}: paint must be null or an object with color and transparency")
        return
    if _hex_color(value.get("color")) is None:
        errors.append(f"{location}.color: #RRGGBB is required")
    transparency = value.get("transparency", 0)
    if not _number(transparency) or not 0 <= float(transparency) <= 100:
        errors.append(f"{location}.transparency: finite value in 0..100 is required")


def _validate_point(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, dict) or not _number(value.get("x")) or not _number(value.get("y")):
        errors.append(f"{location}: normalized point object {{x,y}} is required")
        return
    if not 0 <= float(value["x"]) <= 1 or not 0 <= float(value["y"]) <= 1:
        errors.append(f"{location}: normalized coordinates must be in 0..1")


def _validate_data_object(element: dict[str, Any], location: str, sources: dict[str, dict[str, Any]], errors: list[str], *, expected_label_key: str) -> None:
    if element.get("truth_status") not in TRUTH_STATES:
        errors.append(f"{location}.truth_status: unsupported truth status")
    source_ids = element.get("source_ids")
    if not isinstance(source_ids, list) or any(not isinstance(source_id, str) for source_id in source_ids):
        errors.append(f"{location}.source_ids: list of brief source IDs is required")
    elif element.get("truth_status") == "verified" and not source_ids:
        errors.append(f"{location}: verified data requires source_ids")
    else:
        for source_id in source_ids or []:
            source = sources.get(source_id)
            if source is None:
                errors.append(f"{location}.source_ids: unknown brief source_id {source_id!r}")
            elif element.get("truth_status") == "verified" and source.get("truth_status") != "verified":
                errors.append(
                    f"{location}.truth_status: verified data cannot be supported by {source.get('truth_status')!r} source {source_id!r}"
                )
    if element.get("truth_status") in {"verified", "illustrative", "hypothetical"} and not source_ids:
        errors.append(f"{location}: verified, illustrative, and hypothetical data require source_ids")
    if not isinstance(element.get("units"), str) or not element["units"].strip():
        errors.append(f"{location}.units: explicit units or '无' are required")
    label = element.get(expected_label_key)
    if element.get("truth_status") == "illustrative" and (not isinstance(label, str) or not any(value in label for value in ILLUSTRATIVE_LABELS)):
        errors.append(f"{location}.{expected_label_key}: illustrative data needs a visible '示意/示例/虚构' label")
    if element.get("truth_status") == "hypothetical" and (not isinstance(label, str) or not any(value in label for value in HYPOTHETICAL_LABELS)):
        errors.append(f"{location}.{expected_label_key}: hypothetical data needs a visible scenario label")


def _require_truth_labels(elements: Any, text_labels: list[str], location: str, errors: list[str]) -> None:
    for element in elements:
        if not isinstance(element, dict) or element.get("type") not in {"table", "chart"}:
            continue
        status = element.get("truth_status")
        label = element.get("visible_label") if element.get("type") == "table" else element.get("title")
        if status in {"illustrative", "hypothetical"}:
            haystack = " ".join(text_labels + ([label] if isinstance(label, str) else []))
            choices = ILLUSTRATIVE_LABELS if status == "illustrative" else HYPOTHETICAL_LABELS
            if not any(tag in haystack for tag in choices):
                errors.append(f"{location}: illustrative/hypothetical data needs a visible truth label in this slide")


def _validate_assembly(root: Path, docs: dict[str, dict[str, Any]], deck_slides: dict[str, dict[str, Any]], scene_slides: dict[str, dict[str, Any]], errors: list[str], facts: dict[str, Any]) -> None:
    assembly = docs.get("assembly-map.json", {})
    if assembly.get("contract_version") != CONTRACT_VERSION or assembly.get("status") != "assembled":
        errors.append("assembly-map.json: current showcase assembly must declare contract_version showcase-v1 and status assembled")
    output_path = _digest_matches(root, assembly.get("output"), assembly.get("sha256"), errors, "assembly-map.json.output")
    if output_path is not None:
        if output_path.suffix.lower() != ".pptx" or not zipfile.is_zipfile(output_path):
            errors.append("assembly-map.json.output: must be a readable PPTX package")
    input_files = {
        "deck_spec": "deck-spec.json",
        "scene_graph": "scene-graph.json",
        "asset_manifest": "asset-manifest.json",
        "style_contract": "style-contract.json",
        "concept_log": "concept-generation-log.json",
    }
    expected_hashes = {key: _sha256_file(root / path) for key, path in input_files.items() if (root / path).is_file()}
    if assembly.get("input_sha256") != expected_hashes:
        errors.append("assembly-map.json.input_sha256: must bind current deck, scene, assets, style, and concept log")
    render_backend = assembly.get("render_backend")
    if not isinstance(render_backend, str) or not render_backend.strip() or render_backend.lower() in {"mock", "fixture", "synthetic", "placeholder"}:
        errors.append("assembly-map.json.render_backend: a real renderer must be identified")
    slides = _keyed_rows(assembly.get("slides"), "slide_id", "assembly-map.json.slides", errors)
    if set(slides) != set(deck_slides):
        errors.append("assembly-map.json.slides: assembled slide coverage must exactly match the deck")
    renders = assembly.get("renders")
    if not isinstance(renders, list):
        errors.append("assembly-map.json.renders: actual per-slide PNG render records are required")
        renders = []
    render_by_id = _keyed_rows(renders, "slide_id", "assembly-map.json.renders", errors)
    if set(render_by_id) != set(deck_slides):
        errors.append("assembly-map.json.renders: one current actual render is required per slide")
    for slide_id, row in render_by_id.items():
        render = _digest_matches(root, row.get("path"), row.get("sha256"), errors, f"assembly-map.json.renders[{slide_id}].path")
        if render is not None and not _is_png(render):
            errors.append(f"assembly-map.json.renders[{slide_id}].path: render must be PNG")
        canvas = scene_slides.get(slide_id, {}).get("canvas", {})
        if render is not None and (_image_size(render) != (canvas.get("width"), canvas.get("height")) or not _is_supported_image(render)):
            errors.append(f"assembly-map.json.renders[{slide_id}].path: readable render pixels must match the declared slide canvas")
        if row.get("pptx_sha256") != assembly.get("sha256"):
            errors.append(f"assembly-map.json.renders[{slide_id}].pptx_sha256: render must bind the current PPTX")
    _validate_pptx_objects(root, output_path, assembly, deck_slides, scene_slides, slides, errors)
    facts["pptx_sha256"] = assembly.get("sha256")
    facts["render_sha256"] = {slide_id: row.get("sha256") for slide_id, row in render_by_id.items()}
    facts["render_backend"] = render_backend


def _validate_pptx_objects(root: Path, pptx_path: Path | None, assembly: dict[str, Any], deck_slides: dict[str, dict[str, Any]], scene_slides: dict[str, dict[str, Any]], assembled_slides: dict[str, dict[str, Any]], errors: list[str]) -> None:
    if pptx_path is None:
        return
    try:
        archive = zipfile.ZipFile(pptx_path)
    except (OSError, zipfile.BadZipFile):
        errors.append("assembly-map.json.output: cannot open PPTX package")
        return
    with archive:
        names = set(archive.namelist())
        slide_parts = sorted(((int(match.group(1)), name) for name in names if (match := _SLIDE_RE.fullmatch(name))), key=lambda row: row[0])
        if len(slide_parts) != len(deck_slides):
            errors.append("PPTX: slide count does not match deck-spec")
            return
        ids_in_order = list(deck_slides)
        for order, (slide_index, part_name) in enumerate(slide_parts):
            slide_id = ids_in_order[order]
            scene_elements = scene_slides.get(slide_id, {}).get("elements", [])
            scene_by_id = {row.get("instance_id"): row for row in scene_elements if isinstance(row, dict)}
            map_row = assembled_slides.get(slide_id, {})
            object_rows = _keyed_rows(map_row.get("objects"), "instance_id", f"assembly-map.json.slides[{slide_id}].objects", errors)
            if set(object_rows) != set(scene_by_id):
                errors.append(f"assembly-map.json.slides[{slide_id}].objects: must map every scene element exactly once")
            try:
                xml_root = ElementTree.fromstring(archive.read(part_name))
            except (KeyError, ElementTree.ParseError):
                errors.append(f"PPTX: invalid slide XML for {slide_id}")
                continue
            actual: dict[str, tuple[str, list[str], ElementTree.Element]] = {}
            for tag_name in ("sp", "cxnSp", "pic", "graphicFrame"):
                for element in xml_root.findall(f".//p:{tag_name}", _NS):
                    name_path = {
                        "sp": "p:nvSpPr/p:cNvPr",
                        "cxnSp": "p:nvCxnSpPr/p:cNvPr",
                        "pic": "p:nvPicPr/p:cNvPr",
                        "graphicFrame": "p:nvGraphicFramePr/p:cNvPr",
                    }[tag_name]
                    property_node = element.find(name_path, _NS)
                    if property_node is None:
                        continue
                    object_name = property_node.attrib.get("name")
                    paragraphs = ["".join(text.text or "" for text in para.findall(".//a:t", _NS)) for para in element.findall(".//a:p", _NS)]
                    if not object_name:
                        errors.append(f"PPTX slide {slide_id}: independent object has no stable PowerPoint name")
                        continue
                    if object_name in actual:
                        errors.append(f"PPTX slide {slide_id}: duplicate PowerPoint object name {object_name!r}")
                    else:
                        actual[object_name] = (tag_name, [value for value in paragraphs if value], element)
            object_names_seen: set[str] = set()
            for instance_id, object_row in object_rows.items():
                object_name = object_row.get("object_name")
                if not isinstance(object_name, str) or not object_name:
                    errors.append(f"assembly-map.json.slides[{slide_id}].objects[{instance_id}].object_name: required")
                    continue
                if object_name in object_names_seen:
                    errors.append(f"assembly-map.json.slides[{slide_id}].objects: duplicate object_name {object_name!r}")
                object_names_seen.add(object_name)
                actual_row = actual.get(object_name)
                if actual_row is None:
                    errors.append(f"PPTX slide {slide_id}: mapped independent object {object_name!r} is absent")
                    continue
                scene_row = scene_by_id.get(instance_id, {})
                kind = scene_row.get("type")
                if object_row.get("type") != kind:
                    errors.append(f"assembly-map.json.slides[{slide_id}].objects[{instance_id}].type: differs from scene graph")
                tag_name, paragraphs, xml_element = actual_row
                if kind == "text":
                    if tag_name != "sp":
                        errors.append(f"PPTX slide {slide_id}: native text {instance_id} must be an independent PowerPoint shape")
                    expected_text = scene_row.get("text")
                    if "\n".join(paragraphs) != expected_text:
                        errors.append(f"PPTX slide {slide_id}: editable text of {instance_id} differs from scene graph")
                elif kind in {"shape", "connector"} and tag_name not in {"sp", "cxnSp"}:
                    errors.append(f"PPTX slide {slide_id}: {kind} {instance_id} must be a native PowerPoint shape/connector")
                elif kind == "table":
                    if tag_name != "graphicFrame" or xml_element.find(".//a:tbl", _NS) is None:
                        errors.append(f"PPTX slide {slide_id}: table {instance_id} must be an editable native table")
                    else:
                        actual_cells = [["".join(t.text or "" for t in cell.findall(".//a:t", _NS)) for cell in row.findall("a:tc", _NS)] for row in xml_element.findall(".//a:tbl/a:tr", _NS)]
                        expected_cells = [[str(column.get("label", "")) for column in scene_row.get("columns", [])]]
                        expected_cells.extend([[str(cell) for cell in row.get("cells", [])] for row in scene_row.get("rows", []) if isinstance(row, dict)])
                        visible_label = scene_row.get("visible_label")
                        if scene_row.get("truth_status") in {"illustrative", "hypothetical"}:
                            expected_cells.insert(0, [str(visible_label)] + [""] * max(0, len(scene_row.get("columns", [])) - 1))
                        if actual_cells != expected_cells:
                            errors.append(f"PPTX slide {slide_id}: native table {instance_id} cell data differs from scene graph")
                elif kind == "chart":
                    if tag_name != "graphicFrame" or xml_element.find(".//c:chart", _NS) is None:
                        errors.append(f"PPTX slide {slide_id}: chart {instance_id} must be a native editable PowerPoint chart")
                    else:
                        rel_id = xml_element.find(".//c:chart", _NS).attrib.get(f"{{{_NS['r']}}}id")
                        rels_part = f"ppt/slides/_rels/slide{slide_index}.xml.rels"
                        chart_part = _related_part(archive, names, rels_part, rel_id)
                        if not chart_part or chart_part not in names:
                            errors.append(f"PPTX slide {slide_id}: native chart {instance_id} has no chart part")
                        else:
                            chart_xml = ElementTree.fromstring(archive.read(chart_part))
                            chart_rels = str(Path(chart_part).parent / "_rels" / (Path(chart_part).name + ".rels")).replace("\\", "/")
                            embedded_workbook = False
                            if chart_rels in names:
                                try:
                                    chart_rel_root = ElementTree.fromstring(archive.read(chart_rels))
                                    embedded_workbook = _validate_embedded_chart_workbook(
                                        archive, names, chart_part, chart_rel_root, scene_row, slide_id, instance_id, errors
                                    )
                                except ElementTree.ParseError:
                                    errors.append(f"PPTX slide {slide_id}: chart {instance_id} relationships XML is unreadable")
                            else:
                                errors.append(f"PPTX slide {slide_id}: chart {instance_id} embedded workbook relationships are missing")
                            # Axis titles are separate labels; only the chart-level
                            # title carries this object's title/truth binding.
                            title_text = "".join(text.text or "" for text in chart_xml.findall("./c:chart/c:title//a:t", _NS))
                            if title_text != scene_row.get("title"):
                                errors.append(f"PPTX slide {slide_id}: native chart {instance_id} title/truth label differs from scene graph")
                            if not embedded_workbook:
                                errors.append(f"PPTX slide {slide_id}: editable chart {instance_id} has no embedded workbook")
                            _validate_chart_cache(chart_xml, scene_row, slide_id, instance_id, errors)
                elif kind in IMAGE_TYPES and tag_name != "pic":
                    errors.append(f"PPTX slide {slide_id}: image object {instance_id} must remain an independent PowerPoint picture")
            unmapped_names = set(actual) - object_names_seen
            for object_name in sorted(unmapped_names):
                errors.append(f"PPTX slide {slide_id}: unmapped PPTX object {object_name!r} is outside the scene graph contract")


def _related_part(archive: zipfile.ZipFile, names: set[str], rels_part: str, relationship_id: str | None) -> str | None:
    if not relationship_id or rels_part not in names:
        return None
    try:
        root = ElementTree.fromstring(archive.read(rels_part))
    except (KeyError, ElementTree.ParseError):
        return None
    rel_tag = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
    for relationship in root.findall(rel_tag):
        if relationship.attrib.get("Id") == relationship_id:
            target = relationship.attrib.get("Target", "")
            if target.startswith("/"):
                return target.lstrip("/")
            return posixpath.normpath(posixpath.join("ppt/slides", target))
    return None


def _resolve_opc_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def _validate_embedded_chart_workbook(
    archive: zipfile.ZipFile,
    names: set[str],
    chart_part: str,
    relationships: ElementTree.Element,
    scene_row: dict[str, Any],
    slide_id: str,
    instance_id: str,
    errors: list[str],
) -> bool:
    """Require the chart's embedded XLSX to be a readable source for its data."""
    rel_tag = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
    workbook_links = [
        relationship
        for relationship in relationships.findall(rel_tag)
        if relationship.attrib.get("Type", "").endswith("/package")
    ]
    where = f"PPTX slide {slide_id}: chart {instance_id} embedded workbook"
    if len(workbook_links) != 1:
        errors.append(f"{where} relationship must identify exactly one embedded package")
        return False
    link = workbook_links[0]
    target = link.attrib.get("Target", "")
    workbook_part = _resolve_opc_target(chart_part, target) if target else ""
    if link.attrib.get("TargetMode", "Internal").lower() == "external" or not workbook_part.startswith("ppt/embeddings/"):
        errors.append(f"{where} must be an internal embedded XLSX part")
        return False
    if workbook_part not in names:
        errors.append(f"{where} part is missing from the PPTX package")
        return False

    xlsx_main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    xlsx_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    ns = {"x": xlsx_main}
    try:
        workbook_bytes = archive.read(workbook_part)
        with zipfile.ZipFile(io.BytesIO(workbook_bytes), "r") as workbook:
            bad_member = workbook.testzip()
            if bad_member is not None:
                raise ValueError(f"corrupt XLSX member {bad_member}")
            required_parts = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
            if not required_parts.issubset(workbook.namelist()):
                raise ValueError("required workbook XML parts are missing")
            workbook_root = ElementTree.fromstring(workbook.read("xl/workbook.xml"))
            sheet_nodes = workbook_root.findall("./x:sheets/x:sheet", ns)
            if len(sheet_nodes) != 1:
                raise ValueError("exactly one worksheet is required for a bound native chart")
            sheet_relation_id = sheet_nodes[0].attrib.get(f"{{{xlsx_rel}}}id")
            rel_root = ElementTree.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
            worksheet_links = [
                relationship
                for relationship in rel_root.findall(f"{{{package_rel}}}Relationship")
                if relationship.attrib.get("Id") == sheet_relation_id
                and relationship.attrib.get("Type", "").endswith("/worksheet")
            ]
            if len(worksheet_links) != 1:
                raise ValueError("worksheet relationship is missing or ambiguous")
            sheet_part = _resolve_opc_target("xl/workbook.xml", worksheet_links[0].attrib.get("Target", ""))
            if sheet_part not in workbook.namelist():
                raise ValueError("worksheet part is missing")

            strings: list[str] = []
            string_links = [
                relationship
                for relationship in rel_root.findall(f"{{{package_rel}}}Relationship")
                if relationship.attrib.get("Type", "").endswith("/sharedStrings")
            ]
            if len(string_links) > 1:
                raise ValueError("shared-string relationship is ambiguous")
            if string_links:
                strings_part = _resolve_opc_target("xl/workbook.xml", string_links[0].attrib.get("Target", ""))
                if strings_part not in workbook.namelist():
                    raise ValueError("shared-string part is missing")
                strings_root = ElementTree.fromstring(workbook.read(strings_part))
                strings = ["".join(node.text or "" for node in item.findall(".//x:t", ns)) for item in strings_root.findall("x:si", ns)]

            sheet_root = ElementTree.fromstring(workbook.read(sheet_part))
            actual_cells: dict[str, str | float] = {}
            for cell in sheet_root.findall(".//x:sheetData/x:row/x:c", ns):
                address = cell.attrib.get("r")
                if not isinstance(address, str) or not re.fullmatch(r"[A-Z]+[1-9][0-9]*", address):
                    raise ValueError("worksheet contains a cell without a valid address")
                value_node = cell.find("x:v", ns)
                cell_type = cell.attrib.get("t")
                if cell_type == "s":
                    if value_node is None or value_node.text is None:
                        raise ValueError(f"shared-string cell {address} has no index")
                    index = int(value_node.text)
                    if index < 0 or index >= len(strings):
                        raise ValueError(f"shared-string cell {address} has an invalid index")
                    value: str | float = strings[index]
                elif cell_type == "inlineStr":
                    value = "".join(node.text or "" for node in cell.findall(".//x:is//x:t", ns))
                elif value_node is None or value_node.text is None:
                    continue
                elif cell_type == "str":
                    value = value_node.text
                else:
                    value = float(value_node.text)
                    if not math.isfinite(value):
                        raise ValueError(f"numeric cell {address} is not finite")
                if value != "":
                    actual_cells[address] = value

            expected_cells: dict[str, str | float] = {}
            categories = scene_row.get("categories", [])
            series_rows = scene_row.get("series", [])
            for row_index, category in enumerate(categories, start=2):
                expected_cells[f"A{row_index}"] = float(category) if _number(category) else str(category)
            for series_index, series in enumerate(series_rows):
                column_number = series_index + 2
                column_name = ""
                while column_number:
                    column_number, remainder = divmod(column_number - 1, 26)
                    column_name = chr(65 + remainder) + column_name
                series_name = series.get("name") if isinstance(series, dict) else None
                if isinstance(series_name, str) and series_name:
                    expected_cells[f"{column_name}1"] = series_name
                for row_index, value in enumerate(series.get("values", []) if isinstance(series, dict) else [], start=2):
                    expected_cells[f"{column_name}{row_index}"] = float(value)
            if actual_cells.keys() != expected_cells.keys():
                raise ValueError("worksheet cells do not match the declared chart data grid")
            for address, expected in expected_cells.items():
                actual = actual_cells[address]
                if isinstance(expected, float):
                    if not isinstance(actual, float) or not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9):
                        raise ValueError(f"worksheet numeric source differs at {address}")
                elif actual != expected:
                    raise ValueError(f"worksheet category/series source differs at {address}")
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError, ValueError, KeyError, TypeError, OverflowError) as exc:
        errors.append(f"{where} is missing, unreadable, or differs from the scene data: {exc}")
        return False
    return True


def _validate_chart_cache(chart_xml: ElementTree.Element, scene_row: dict[str, Any], slide_id: str, instance_id: str, errors: list[str]) -> None:
    chart_series = chart_xml.findall(".//c:ser", _NS)
    expected_series = scene_row.get("series", [])
    if len(chart_series) != len(expected_series):
        errors.append(f"PPTX slide {slide_id}: chart {instance_id} cached series count differs from scene graph")
    expected_categories = [str(value) for value in scene_row.get("categories", [])]
    for index, series_node in enumerate(chart_series):
        if index >= len(expected_series) or not isinstance(expected_series[index], dict):
            continue
        cached_categories: list[str] = []
        for point in series_node.findall(".//c:cat//c:pt", _NS):
            value = point.find("c:v", _NS)
            if value is not None and value.text is not None:
                cached_categories.append(value.text)
        cached_values: list[float] = []
        for point in series_node.findall(".//c:val//c:pt", _NS):
            value = point.find("c:v", _NS)
            if value is None or value.text is None:
                continue
            try:
                cached_values.append(float(value.text))
            except ValueError:
                errors.append(f"PPTX slide {slide_id}: chart {instance_id} contains nonnumeric cached data")
        expected_values = [float(value) for value in expected_series[index].get("values", []) if _number(value)]
        if cached_categories != expected_categories:
            errors.append(f"PPTX slide {slide_id}: chart {instance_id} series {index + 1} cached categories differ from scene graph")
        if len(cached_values) != len(expected_values) or any(not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9) for actual, expected in zip(cached_values, expected_values)):
            errors.append(f"PPTX slide {slide_id}: chart {instance_id} series {index + 1} cached values differ from scene graph")
        if not cached_categories or not cached_values:
            errors.append(f"PPTX slide {slide_id}: chart {instance_id} series {index + 1} is missing editable chart data caches")


def _validate_review(root: Path, docs: dict[str, dict[str, Any]], assembly: dict[str, Any], deck_slides: dict[str, dict[str, Any]], errors: list[str], warnings: list[str], facts: dict[str, Any]) -> None:
    review_doc = docs.get("showcase-review.json", {})
    review = review_doc.get("agent_review")
    if not isinstance(review, dict):
        errors.append("showcase-review.json.agent_review: real current-version agent visual review is required")
        return
    if review.get("actor") != "agent" or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
        errors.append("showcase-review.json.agent_review: actor='agent' and actual reviewer name are required")
    if not _timezone_aware(review.get("reviewed_at")):
        errors.append("showcase-review.json.agent_review.reviewed_at: timezone-aware ISO-8601 is required")
    if review.get("status") != "complete":
        errors.append("showcase-review.json.agent_review.status: review must cover all current pages")
    if review.get("pptx_sha256") != assembly.get("sha256"):
        errors.append("showcase-review.json.agent_review.pptx_sha256: review must bind current PPTX")
    render_rows = {row.get("slide_id"): row for row in assembly.get("renders", []) if isinstance(row, dict)}
    reviewed_renders = review.get("renders")
    if not isinstance(reviewed_renders, list):
        errors.append("showcase-review.json.agent_review.renders: per-slide render bindings are required")
        reviewed_renders = []
    review_render_rows = _keyed_rows(reviewed_renders, "slide_id", "showcase-review.json.agent_review.renders", errors)
    if set(review_render_rows) != set(deck_slides):
        errors.append("showcase-review.json.agent_review.renders: every current slide render must be reviewed exactly once")
    for slide_id, render in render_rows.items():
        review_render = review_render_rows.get(slide_id, {})
        if review_render.get("path") != render.get("path") or review_render.get("sha256") != render.get("sha256"):
            errors.append(f"showcase-review.json.agent_review.renders[{slide_id}]: stale or mismatched render binding")
        if review_render.get("display_scale_percent") != 100:
            errors.append(f"showcase-review.json.agent_review.renders[{slide_id}]: actual full-size review at 100% is required")
    slide_reviews = _keyed_rows(review.get("slides"), "slide_id", "showcase-review.json.agent_review.slides", errors)
    if set(slide_reviews) != set(deck_slides):
        errors.append("showcase-review.json.agent_review.slides: every page must have one visual review")
    p0 = p1 = False
    allowed_evidence_by_slide: dict[str, set[str]] = {}
    for slide_id, render in render_rows.items():
        allowed_evidence_by_slide[slide_id] = {render["path"]}
    for slide_id, row in slide_reviews.items():
        location = f"showcase-review.json.agent_review.slides[{slide_id}]"
        try:
            review_identity(row, PAGE_CHECKS)
            p1 |= review_findings(root, row, allowed_evidence_by_slide.get(slide_id, set()), {slide_id})
        except ValueError as exc:
            errors.append(f"{location}: {exc}")
        findings = row.get("findings", [])
        if isinstance(findings, list):
            p0 |= any(isinstance(finding, dict) and finding.get("severity") == "P0" for finding in findings)
            p1 |= any(isinstance(finding, dict) and finding.get("severity") == "P1" for finding in findings)
    whole = review.get("whole_deck_review")
    if not isinstance(whole, dict) or not isinstance(whole.get("findings"), list):
        errors.append("showcase-review.json.agent_review.whole_deck_review: overall rhythm/consistency review with findings list is required")
    else:
        try:
            review_identity(whole, DECK_CHECKS)
            contact_record = whole.get("contact_sheet")
            if not isinstance(contact_record, dict):
                raise ValueError("whole-deck contact_sheet path and SHA-256 are required")
            if not isinstance(contact_record.get("path"), str):
                raise ValueError("whole-deck contact_sheet path is required")
            contact_path = evidence_file(root, contact_record, contact_record.get("path"))
            with Image.open(contact_path) as contact:
                renders_in_order = []
                for slide_id in deck_slides:
                    render_path = root / render_rows[slide_id]["path"]
                    with Image.open(render_path) as image:
                        renders_in_order.append((slide_id, image.copy()))
                expected = contact_sheet(renders_in_order)
                if contact.size != expected.size or ImageChops.difference(contact.convert("RGB"), expected.convert("RGB")).getbbox():
                    raise ValueError("whole-deck contact sheet pixels are stale against current renders")
                for _, image in renders_in_order:
                    image.close()
            allowed_all = {row["path"] for row in render_rows.values()} | {contact_record["path"]}
            p1 |= review_findings(root, whole, allowed_all, set(deck_slides))
        except (TypeError, ValueError, OSError) as exc:
            errors.append(f"showcase-review.json.agent_review.whole_deck_review: {exc}")
        findings = whole.get("findings", [])
        if isinstance(findings, list):
            p0 |= any(isinstance(finding, dict) and finding.get("severity") == "P0" for finding in findings)
            p1 |= any(isinstance(finding, dict) and finding.get("severity") == "P1" for finding in findings)
    if p0:
        errors.append("showcase-review.json.agent_review: P0 visual findings block local draft export")
    if p1:
        warnings.append("agent visual review has P1 findings; any export must remain an explicitly unpassed draft with findings")
    expected_outcome = "issues" if p1 else "pass"
    if review.get("outcome") != expected_outcome:
        errors.append(f"showcase-review.json.agent_review.outcome: must reflect current findings as {expected_outcome!r}")
    user_feedback = review_doc.get("user_feedback")
    if user_feedback is not None:
        if not isinstance(user_feedback, dict):
            errors.append("showcase-review.json.user_feedback: must be null or a separately recorded user response")
        elif user_feedback.get("status") not in {"not-recorded", "accepted", "rejected"}:
            errors.append("showcase-review.json.user_feedback.status: must be not-recorded, accepted, or rejected")
        elif user_feedback.get("status") in {"accepted", "rejected"}:
            if user_feedback.get("actor") != "user" or user_feedback.get("pptx_sha256") != assembly.get("sha256"):
                errors.append("showcase-review.json.user_feedback: actual user feedback must be recorded separately against current PPTX")
    facts["agent_visual_review"] = {
        "status": "complete",
        "outcome": review.get("outcome"),
        "reviewer": review.get("reviewer"),
        "p0": p0,
        "p1": p1,
    }
    facts["user_visual_feedback"] = user_feedback.get("status", "not-recorded") if isinstance(user_feedback, dict) else "not-recorded"
    facts["human_gates"] = "not-claimed"


def _timezone_aware(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.utcoffset() is not None


def validate_showcase(root: Path, stage: str) -> dict[str, Any]:
    """Return a JSON-serializable report for one showcase-v1 stage.

    `ok` means the declared contract for this stage is internally valid. It
    does not mean aesthetically accepted, human-approved, or production-ready.
    """
    root = Path(root).resolve()
    report: dict[str, Any] = {"ok": False, "stage": stage, "errors": [], "warnings": [], "facts": {}}
    errors: list[str] = report["errors"]
    warnings: list[str] = report["warnings"]
    facts: dict[str, Any] = report["facts"]
    if stage not in STAGES:
        errors.append(f"stage: expected one of {', '.join(STAGES)}")
        return report
    if not root.is_dir():
        errors.append(f"project: directory does not exist: {root}")
        return report
    docs = _load_contract_docs(root, stage, errors)
    for name, document in docs.items():
        _reject_fixtures(document, name, errors)
    _validate_kind_and_mode(docs, errors)
    deck_slides: dict[str, dict[str, Any]] = {}
    scene_slides: dict[str, dict[str, Any]] = {}
    asset_rows: dict[str, dict[str, Any]] = {}
    if all(name in docs for name in BASE_DOCS):
        deck_slides, scene_slides, asset_rows = _validate_concepts(root, docs, errors, facts)
    if stage in {"assembly", "qa", "export"} and "assembly-map.json" in docs:
        _validate_assembly(root, docs, deck_slides, scene_slides, errors, facts)
    if stage in {"qa", "export"} and "showcase-review.json" in docs and "assembly-map.json" in docs:
        _validate_review(root, docs, docs["assembly-map.json"], deck_slides, errors, warnings, facts)
    if stage == "export":
        if not facts.get("agent_visual_review", {}).get("status") == "complete":
            errors.append("export: a current complete agent visual review is required")
        if not facts.get("pptx_sha256"):
            errors.append("export: current real PPTX and per-slide renders are required")
        facts["delivery_label"] = "local-showcase-draft"
        facts["formal_release"] = "not-claimed"
        facts["g5"] = "not-claimed"
    report["ok"] = not errors
    return report


def validate_concept_inputs(root: Path) -> dict[str, Any]:
    """Validate source-bound contentful concepts before native scene assembly.

    This intentionally reads only the seven concept-stage documents. It does
    not require a scene graph or image-asset manifest and does not apply native
    PowerPoint readability or contrast checks to a full-slide concept image.
    """
    root = Path(root).resolve()
    report: dict[str, Any] = {"ok": False, "stage": "concept-inputs", "errors": [], "warnings": [], "facts": {}}
    errors: list[str] = report["errors"]
    if not root.is_dir():
        errors.append(f"project: directory does not exist: {root}")
        return report
    documents: dict[str, dict[str, Any]] = {}
    for name in CONCEPT_INPUT_DOCS:
        document = _load_json(root, name, errors)
        if document is not None:
            documents[name] = document
            _reject_fixtures(document, name, errors)
    _validate_kind_and_mode(documents, errors)
    if all(name in documents for name in CONCEPT_INPUT_DOCS):
        _validate_concepts(root, documents, errors, report["facts"], include_assembly=False)
    report["ok"] = not errors
    return report


def derive_receipt(root: Path) -> dict[str, Any]:
    """Derive separate technical, agent-review, and user-feedback facts.

    The receipt deliberately has no aggregate PASS and is not hashed into
    itself. It is a summary of current files, not a trusted event log.
    """
    root = Path(root).resolve()
    report = validate_showcase(root, "export")
    inputs: dict[str, str] = {}
    for relative in (*BASE_DOCS, *ASSEMBLY_DOCS, *QA_DOCS):
        candidate = root / relative
        if candidate.is_file():
            inputs[relative] = _sha256_file(candidate)
    concepts = _load_json(root, "deck-spec.json", [], required=False) or {}
    for slide in concepts.get("slides", []) if isinstance(concepts.get("slides"), list) else []:
        if isinstance(slide, dict) and isinstance(slide.get("concept_path"), str):
            path = _safe_file(root, slide["concept_path"], [], "concept")
            if path is not None:
                inputs[path.relative_to(root).as_posix()] = _sha256_file(path)
    for name, field in (("asset-manifest.json", "assets"), ("reference-study.json", "references")):
        document = _load_json(root, name, [], required=False) or {}
        rows = document.get(field, [])
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    relative = row.get("path", row.get("image_path"))
                    path = _safe_file(root, relative, [], name)
                    if path is not None:
                        inputs[path.relative_to(root).as_posix()] = _sha256_file(path)
    assembly = _load_json(root, "assembly-map.json", [], required=False) or {}
    for row in assembly.get("renders", []) if isinstance(assembly.get("renders"), list) else []:
        if isinstance(row, dict) and isinstance(row.get("path"), str):
            path = _safe_file(root, row["path"], [], "render")
            if path is not None:
                inputs[path.relative_to(root).as_posix()] = _sha256_file(path)
    if isinstance(assembly.get("output"), str):
        path = _safe_file(root, assembly["output"], [], "PPTX")
        if path is not None:
            inputs[path.relative_to(root).as_posix()] = _sha256_file(path)
    review = _load_json(root, "showcase-review.json", [], required=False) or {}
    agent_review = review.get("agent_review") if isinstance(review.get("agent_review"), dict) else {}
    user_feedback = review.get("user_feedback") if isinstance(review.get("user_feedback"), dict) else {"status": "not-recorded"}
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "technical_validation": {"stage": "export", "ok": report["ok"], "errors": report["errors"], "warnings": report["warnings"]},
        "current_artifact_sha256": inputs,
        "agent_visual_review": {
            "status": agent_review.get("status", "not-recorded"),
            "outcome": agent_review.get("outcome", "not-recorded"),
            "reviewer": agent_review.get("reviewer"),
        },
        "user_visual_feedback": {"status": user_feedback.get("status", "not-recorded")},
        "human_gates": {"G1": "not-claimed", "G2": "not-claimed", "G3": "not-claimed", "G4": "not-claimed", "G5": "not-claimed"},
        "provenance_limit": "Current hashes and declared bindings do not prove creation order or authenticate record authorship.",
    }


def _package_safe_stem(value: str) -> str:
    if SAFE_NAME_RE.fullmatch(value) and value not in {".", ".."}:
        return value
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _showcase_package_sources(root: Path, documents: dict[str, dict[str, Any]], pptx_name: str | None) -> tuple[list[tuple[Path, str, str]], str]:
    """Return (source, package-relative path, source-relative path) entries."""
    deck_spec = documents["deck-spec.json"]
    concept_log = documents["concept-generation-log.json"]
    log_by_slide = {row.get("slide_id"): row for row in concept_log.get("slides", []) if isinstance(row, dict)}
    assembly = documents["assembly-map.json"]
    source_pptx = _safe_file(root, assembly.get("output"), [], "assembly-map.json.output")
    if source_pptx is None:
        raise ValueError("assembly-map.json.output is missing or unsafe")
    name = pptx_name or f"{source_pptx.stem}-草稿.pptx"
    if Path(name).name != name or not name.lower().endswith(".pptx") or not ("草稿" in name or "draft" in name.lower()):
        raise ValueError("showcase PPTX name must be a plain .pptx filename containing 草稿 or draft")
    copies: list[tuple[Path, str, str]] = []
    for index, slide in enumerate(deck_spec.get("slides", []), start=1):
        slide_id = slide["id"]
        record = log_by_slide.get(slide_id, {})
        source_relative = record.get("output_path")
        source = _safe_file(root, source_relative, [], f"concept {slide_id}")
        if source is None:
            raise ValueError(f"concept image for {slide_id} is missing or unsafe")
        copies.append((source, f"确定概念图/{index:02d}-{_package_safe_stem(slide_id)}-确定概念图.png", source_relative))
    for asset in documents["asset-manifest.json"].get("assets", []):
        if not isinstance(asset, dict):
            continue
        source_relative = asset.get("path")
        source = _safe_file(root, source_relative, [], f"asset {asset.get('id')}")
        if source is None:
            raise ValueError(f"image asset {asset.get('id')} is missing or unsafe")
        suffix = source.suffix.lower() or ".png"
        copies.append((source, f"组件/素材-{_package_safe_stem(str(asset.get('id', 'asset')))}{suffix}", source_relative))
    references = documents["reference-study.json"].get("references", [])
    selected_ids = set(documents["style-contract.json"].get("selected_reference_ids", []))
    for reference in references:
        if not isinstance(reference, dict) or reference.get("id") not in selected_ids:
            continue
        source_relative = reference.get("image_path")
        source = _safe_file(root, source_relative, [], f"reference {reference.get('id')}")
        if source is None:
            raise ValueError(f"selected reference {reference.get('id')} is missing or unsafe")
        copies.append((source, f"组件/参考-{_package_safe_stem(str(reference.get('id', 'reference')))}{source.suffix.lower()}", source_relative))
    copies.append((source_pptx, f"PPT成稿/{name}", str(assembly.get("output"))))
    for render in assembly.get("renders", []):
        if not isinstance(render, dict):
            continue
        source_relative = render.get("path")
        source = _safe_file(root, source_relative, [], f"render {render.get('slide_id')}")
        if source is None:
            raise ValueError(f"render for {render.get('slide_id')} is missing or unsafe")
        copies.append((source, f"PPT成稿/预览渲染/{_package_safe_stem(str(render.get('slide_id', 'slide')))}.png", source_relative))
    for name_in in documents:
        copies.append((root / name_in, f"PPT成稿/项目证据/{name_in}", name_in))
    return copies, name


def _verify_showcase_package(root: Path, output: Path, documents: dict[str, dict[str, Any]], *, pptx_name: str | None) -> dict[str, Any]:
    manifest_path = output / "PPT成稿" / "package-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"package manifest is missing or invalid: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("contract_version") != CONTRACT_VERSION or manifest.get("delivery_label") != "local-showcase-draft":
        raise ValueError("package manifest does not identify a showcase-v1 local draft")
    expected_manifest_keys = {
        "contract_version", "delivery_label", "pptx_name", "pptx_source_path",
        "source_files", "files", "human_gates", "user_visual_feedback",
    }
    if set(manifest) != expected_manifest_keys:
        raise ValueError("package manifest has missing or unsupported semantic claim fields")
    if manifest.get("human_gates") != HUMAN_GATE_NOT_CLAIMED:
        raise ValueError("package manifest must leave every human G1-G5 gate not-claimed")
    current_receipt = derive_receipt(root)
    if manifest.get("user_visual_feedback") != current_receipt.get("user_visual_feedback", {}).get("status"):
        raise ValueError("package manifest user visual feedback differs from the current source receipt")
    source_pptx = documents["assembly-map.json"].get("output")
    name = pptx_name or manifest.get("pptx_name")
    if not isinstance(name, str) or (pptx_name and pptx_name != manifest.get("pptx_name")):
        raise ValueError("requested PPTX name differs from the exported package")
    expected_copies, expected_name = _showcase_package_sources(root, documents, name)
    if expected_name != name or manifest.get("pptx_source_path") != source_pptx:
        raise ValueError("package manifest PPTX source is stale")
    expected_sources = {relative: _sha256_file(source) for source, relative, source_relative in expected_copies}
    if manifest.get("source_files") != [
        {"path": relative, "source_path": source_relative, "source_sha256": _sha256_file(source)}
        for source, relative, source_relative in expected_copies
    ]:
        raise ValueError("package manifest source hashes or mappings differ from the current project")
    file_rows = manifest.get("files")
    if not isinstance(file_rows, list):
        raise ValueError("package manifest files must be a list")
    listed: dict[str, str] = {}
    for row in file_rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"} or not isinstance(row.get("path"), str) or not _is_sha(row.get("sha256")):
            raise ValueError("package manifest contains an invalid file record")
        relative = row["path"]
        if relative in listed:
            raise ValueError(f"package manifest contains a duplicate file record: {relative}")
        candidate = (output / relative).resolve()
        if not candidate.is_relative_to(output) or not candidate.is_file() or candidate.is_symlink():
            raise ValueError(f"package file is missing or unsafe: {relative}")
        if _sha256_file(candidate) != row["sha256"]:
            raise ValueError(f"package file hash differs from manifest: {relative}")
        listed[relative] = row["sha256"]
    for relative, expected in expected_sources.items():
        if listed.get(relative) != expected:
            raise ValueError(f"package source copy is missing or stale: {relative}")
    actual_files = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
    if any(path.is_symlink() for path in output.rglob("*")):
        raise ValueError("package contains a symbolic link")
    expected_file_set = set(listed) | {"PPT成稿/package-manifest.json"}
    if actual_files != expected_file_set:
        raise ValueError("package contains missing or unexpected files")
    expected_dirs = {"确定概念图", "组件", "PPT成稿", "PPT成稿/预览渲染", "PPT成稿/项目证据"}
    actual_dirs = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_dir()}
    if actual_dirs != expected_dirs:
        raise ValueError("package folders differ from the three-folder local showcase layout")
    receipt_path = output / "PPT成稿" / "execution-receipt.json"
    try:
        packaged_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"packaged execution receipt is missing or invalid: {exc}") from exc
    receipt_keys = {
        "contract_version", "generated_at", "technical_validation", "current_artifact_sha256",
        "agent_visual_review", "user_visual_feedback", "human_gates", "provenance_limit",
    }
    if not isinstance(packaged_receipt, dict) or set(packaged_receipt) != receipt_keys:
        raise ValueError("packaged execution receipt has missing or unsupported semantic claim fields")
    if not _timezone_aware(packaged_receipt.get("generated_at")):
        raise ValueError("packaged execution receipt generated_at must be timezone-aware")
    if packaged_receipt.get("human_gates") != HUMAN_GATE_NOT_CLAIMED:
        raise ValueError("packaged execution receipt must leave every human G1-G5 gate not-claimed")
    for field in receipt_keys - {"generated_at"}:
        if packaged_receipt.get(field) != current_receipt.get(field):
            raise ValueError(f"packaged execution receipt {field} differs from current source evidence")
    readme_path = output / "PPT成稿" / "README.md"
    try:
        packaged_readme = readme_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"packaged draft README is missing or unreadable: {exc}") from exc
    review_outcome = current_receipt.get("agent_visual_review", {}).get("outcome", "unknown")
    review_label = "存在代理复核发现；保持未通过本地草稿" if review_outcome == "issues" else "存在代理复核记录；仍是未接受的本地草稿"
    expected_readme = (
        f"# 本地展示草稿\n\n{review_label}。此包不代表用户视觉接受、human G1–G5 批准、正式生产发布或对外发布授权。\n\n"
        f"代理复核 outcome：`{review_outcome}`。原生可编辑对象由 `项目证据/scene-graph.json` 与 `项目证据/asset-manifest.json` 描述；组件文件夹仅存图片素材与所选参考图。\n\n"
        "本地校验与代理检查是不同事实；查看 `execution-receipt.json` 和 `项目证据/showcase-review.json`。\n"
    )
    if packaged_readme != expected_readme:
        raise ValueError("packaged README semantic claims differ from the current source receipt")
    return {
        "ok": True,
        "errors": [],
        "warnings": [],
        "output": str(output),
        "pptx_path": str(output / "PPT成稿" / name),
        "pptx_name": name,
        "concept_count": len(documents["deck-spec.json"].get("slides", [])),
        "asset_count": len(documents["asset-manifest.json"].get("assets", [])),
        "verify_only": True,
        "delivery_label": "local-showcase-draft",
    }


def export_showcase(root: Path, destination: Path, *, verify_only: bool = False, pptx_name: str | None = None) -> dict[str, Any]:
    """Publish or verify a three-folder local-only showcase draft package."""
    root, destination = Path(root).resolve(), Path(destination).resolve()
    report = validate_showcase(root, "export")
    if not report["ok"]:
        return {"ok": False, "errors": report["errors"], "warnings": report["warnings"], "output": str(destination), "verify_only": verify_only}
    if destination == root or root in destination.parents:
        return {"ok": False, "errors": ["output must be outside the working project directory"], "warnings": report["warnings"], "output": str(destination), "verify_only": verify_only}
    documents = {name: _load_json(root, name, [], required=False) or {} for name in (*BASE_DOCS, *ASSEMBLY_DOCS, *QA_DOCS)}
    try:
        if verify_only:
            if not destination.is_dir():
                raise ValueError(f"existing output package does not exist: {destination}")
            return {**_verify_showcase_package(root, destination, documents, pptx_name=pptx_name), "warnings": report["warnings"]}
        if destination.exists():
            raise ValueError(f"output already exists; choose a new destination: {destination}")
        copies, name = _showcase_package_sources(root, documents, pptx_name)
        source_snapshot = document_snapshot(root, documents)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": report["warnings"], "output": str(destination), "verify_only": verify_only}
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
    try:
        for folder in ("确定概念图", "组件", "PPT成稿/预览渲染", "PPT成稿/项目证据"):
            (staging / folder).mkdir(parents=True, exist_ok=True)
        source_files = []
        for source, relative, source_relative in copies:
            target = staging / relative
            shutil.copy2(source, target)
            source_files.append({"path": relative, "source_path": source_relative, "source_sha256": _sha256_file(source)})
        receipt = derive_receipt(root)
        (staging / "PPT成稿" / "execution-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        review_outcome = report["facts"].get("agent_visual_review", {}).get("outcome", "unknown")
        review_label = "存在代理复核发现；保持未通过本地草稿" if review_outcome == "issues" else "存在代理复核记录；仍是未接受的本地草稿"
        (staging / "PPT成稿" / "README.md").write_text(
            f"# 本地展示草稿\n\n{review_label}。此包不代表用户视觉接受、human G1–G5 批准、正式生产发布或对外发布授权。\n\n"
            f"代理复核 outcome：`{review_outcome}`。原生可编辑对象由 `项目证据/scene-graph.json` 与 `项目证据/asset-manifest.json` 描述；组件文件夹仅存图片素材与所选参考图。\n\n"
            "本地校验与代理检查是不同事实；查看 `execution-receipt.json` 和 `项目证据/showcase-review.json`。\n",
            encoding="utf-8",
        )
        package_files = []
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                package_files.append({"path": path.relative_to(staging).as_posix(), "sha256": _sha256_file(path)})
        manifest = {
            "contract_version": CONTRACT_VERSION,
            "delivery_label": "local-showcase-draft",
            "pptx_name": name,
            "pptx_source_path": documents["assembly-map.json"]["output"],
            "source_files": source_files,
            "files": package_files,
            "human_gates": {"G1": "not-claimed", "G2": "not-claimed", "G3": "not-claimed", "G4": "not-claimed", "G5": "not-claimed"},
            "user_visual_feedback": report["facts"].get("user_visual_feedback", "not-recorded"),
        }
        manifest_path = staging / "PPT成稿" / "package-manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        assert_current(source_snapshot)
        publish_new_directory(staging, destination)
        return {
            "ok": True,
            "errors": [],
            "warnings": report["warnings"],
            "output": str(destination),
            "pptx_path": str(destination / "PPT成稿" / name),
            "pptx_name": name,
            "concept_count": len(documents["deck-spec.json"].get("slides", [])),
            "asset_count": len(documents["asset-manifest.json"].get("assets", [])),
            "verify_only": False,
            "delivery_label": "local-showcase-draft",
        }
    except Exception as exc:
        shutil.rmtree(staging, ignore_errors=True)
        return {"ok": False, "errors": [f"showcase export failed before publication: {exc}"], "warnings": report["warnings"], "output": str(destination), "verify_only": False}


__all__ = ["CONTRACT_VERSION", "STAGES", "contrast_ratio", "derive_receipt", "export_showcase", "validate_concept_inputs", "validate_showcase"]
