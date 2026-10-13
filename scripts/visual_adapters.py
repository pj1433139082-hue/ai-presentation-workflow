#!/usr/bin/env python3
"""Validate visual providers and adapt provider-native plans for PPT components."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import posixpath
import re
import sys
import zipfile
from datetime import datetime
from xml.etree import ElementTree
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


REQUIRED_PROVIDER_FIELDS = {
    "id",
    "skill_name",
    "tier",
    "auto_route",
    "supported_page_roles",
    "supported_component_roles",
    "source_requirements",
    "truth_policy",
    "text_policy",
    "aspect_ratio_behavior",
    "transparency_behavior",
    "approval_requirements",
    "output_class",
    "adapter",
}

STRING_PROVIDER_FIELDS = {
    "id",
    "skill_name",
    "tier",
    "truth_policy",
    "text_policy",
    "aspect_ratio_behavior",
    "transparency_behavior",
    "output_class",
    "adapter",
}

LIST_PROVIDER_FIELDS = {
    "supported_page_roles",
    "supported_component_roles",
    "source_requirements",
    "approval_requirements",
}

SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")
SAFE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

ALLOWED_PROVIDER_VALUES = {
    "tier": {"core-auto", "explicit-style", "post-release-derivative"},
    "truth_policy": {
        "reject-truth-sensitive",
        "preserve-source-truth",
        "derive-only-from-released-deck",
    },
    "text_policy": {
        "no-ordinary-text-or-data",
        "preserve-source-text-without-reconstruction",
        "derivative-copy-must-match-released-deck",
    },
    "aspect_ratio_behavior": {
        "one-component-per-transparent-canvas",
        "preserve-subject-with-approved-crop",
        "distill-to-slide-anchor",
        "compose-for-approved-special-page",
        "gather-scenes-for-approved-special-page",
        "adapt-to-approved-social-format",
    },
    "transparency_behavior": {
        "required-real-alpha",
        "optional-subject-cutout",
        "transparent-subject-preferred",
        "transparent-elements-or-approved-page-art",
        "not-required-for-final-card",
    },
    "output_class": {
        "transparent-png-component",
        "photo-or-transparent-cutout",
        "special-page-art",
        "post-release-social-card",
    },
    "adapter": {
        "material-illustration-v1",
        "photo-postprocess-v1",
        "scene-distillation-v1",
        "minimal-zine-v1",
        "gathered-scenes-v1",
        "surreal-pop-v1",
        "social-card-derivative-v1",
    },
}

MATERIAL_COMPONENT_ROLES = {
    "illustration",
    "icon",
    "arrow",
    "basic-shape",
    "decorative-shape",
    "panel",
    "table-shell",
    "chart-shell",
    "diagram-node",
}

ALLOWED_SOURCE_KINDS_BY_PROVIDER = {
    "guizang-material-illustration": {"approved-concept-render"},
    "photo-postprocess-coach": {"ordinary-photo"},
    "scene-distillation-zine-v1-3": {"approved-source-scene"},
    "gc-minimal-zine-poster-v0-3": {"approved-source-image"},
    "scenes-gathered-zine-v1-3": {"approved-source-scenes"},
    "surreal-pop-collage": {"approved-source-image"},
    "guizang-social-card-skill": {"released-deck"},
}

CANONICAL_PROVIDER_CONTRACTS = {
    "guizang-material-illustration": {
        "tier": "core-auto",
        "auto_route": True,
        "truth_policy": "reject-truth-sensitive",
        "text_policy": "no-ordinary-text-or-data",
        "aspect_ratio_behavior": "one-component-per-transparent-canvas",
        "transparency_behavior": "required-real-alpha",
        "output_class": "transparent-png-component",
        "adapter": "material-illustration-v1",
        "supported_page_roles": {
            "conceptual-illustration", "structural-diagram", "process", "mechanism"
        },
        "supported_component_roles": MATERIAL_COMPONENT_ROLES,
        "source_requirements": {"approved-concept-render", "approved-style-contract"},
        "approval_requirements": {"G3-style-anchors", "G4-concept-contact-sheet"},
    },
    "photo-postprocess-coach": {
        "tier": "core-auto",
        "auto_route": True,
        "truth_policy": "preserve-source-truth",
        "text_policy": "preserve-source-text-without-reconstruction",
        "aspect_ratio_behavior": "preserve-subject-with-approved-crop",
        "transparency_behavior": "optional-subject-cutout",
        "output_class": "photo-or-transparent-cutout",
        "adapter": "photo-postprocess-v1",
        "supported_page_roles": {"ordinary-photo", "portrait-cutout", "atmosphere-photo"},
        "supported_component_roles": {"ordinary-photo", "photo-cutout"},
        "source_requirements": {"user-supplied-ordinary-photo", "approved-style-contract"},
        "approval_requirements": {"G3-style-anchors", "source-rights-confirmed"},
    },
    "scene-distillation-zine-v1-3": {
        "tier": "core-auto",
        "auto_route": True,
        "truth_policy": "reject-truth-sensitive",
        "text_policy": "no-ordinary-text-or-data",
        "aspect_ratio_behavior": "distill-to-slide-anchor",
        "transparency_behavior": "transparent-subject-preferred",
        "output_class": "transparent-png-component",
        "adapter": "scene-distillation-v1",
        "supported_page_roles": {"opening", "transition", "closing", "abstract-metaphor"},
        "supported_component_roles": {"illustration"},
        "source_requirements": {"approved-source-scene", "approved-style-contract"},
        "approval_requirements": {"G3-style-anchors", "G4-concept-contact-sheet"},
    },
    "gc-minimal-zine-poster-v0-3": {
        "tier": "explicit-style",
        "auto_route": False,
        "truth_policy": "reject-truth-sensitive",
        "text_policy": "no-ordinary-text-or-data",
        "aspect_ratio_behavior": "compose-for-approved-special-page",
        "transparency_behavior": "transparent-elements-or-approved-page-art",
        "output_class": "special-page-art",
        "adapter": "minimal-zine-v1",
        "supported_page_roles": {"cover", "section-opener", "special-poster"},
        "supported_component_roles": {"illustration", "decorative-shape", "special-typography"},
        "source_requirements": {"explicit-provider-opt-in", "approved-style-contract"},
        "approval_requirements": {"G3-style-anchors", "G4-explicit-special-page-approval"},
    },
    "scenes-gathered-zine-v1-3": {
        "tier": "explicit-style",
        "auto_route": False,
        "truth_policy": "reject-truth-sensitive",
        "text_policy": "no-ordinary-text-or-data",
        "aspect_ratio_behavior": "gather-scenes-for-approved-special-page",
        "transparency_behavior": "transparent-elements-or-approved-page-art",
        "output_class": "special-page-art",
        "adapter": "gathered-scenes-v1",
        "supported_page_roles": {"editorial-montage", "section-opener", "narrative-collage"},
        "supported_component_roles": {"illustration", "decorative-shape"},
        "source_requirements": {"explicit-provider-opt-in", "approved-source-scenes"},
        "approval_requirements": {"G3-style-anchors", "G4-explicit-special-page-approval"},
    },
    "surreal-pop-collage": {
        "tier": "explicit-style",
        "auto_route": False,
        "truth_policy": "reject-truth-sensitive",
        "text_policy": "no-ordinary-text-or-data",
        "aspect_ratio_behavior": "compose-for-approved-special-page",
        "transparency_behavior": "transparent-elements-or-approved-page-art",
        "output_class": "special-page-art",
        "adapter": "surreal-pop-v1",
        "supported_page_roles": {"campaign-opener", "creative-opener", "closing"},
        "supported_component_roles": {"illustration", "decorative-shape"},
        "source_requirements": {"explicit-provider-opt-in", "approved-source-image"},
        "approval_requirements": {"G3-style-anchors", "G4-explicit-special-page-approval"},
    },
    "guizang-social-card-skill": {
        "tier": "post-release-derivative",
        "auto_route": False,
        "truth_policy": "derive-only-from-released-deck",
        "text_policy": "derivative-copy-must-match-released-deck",
        "aspect_ratio_behavior": "adapt-to-approved-social-format",
        "transparency_behavior": "not-required-for-final-card",
        "output_class": "post-release-social-card",
        "adapter": "social-card-derivative-v1",
        "supported_page_roles": {"post-release-social-card"},
        "supported_component_roles": {"post-release-social-card"},
        "source_requirements": {"released-deck", "approved-derivative-brief"},
        "approval_requirements": {"G5-release-approval", "post-release-derivative-approval"},
    },
}


class AdapterError(ValueError):
    """Raised when a provider or requested output violates the PPT adapter contract."""


def validate_reference_bbox(value: Any, location: str) -> list[float | int]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value)
    ):
        raise AdapterError(f"{location} must be [x, y, width, height] numbers")
    x, y, width, height = value
    if any(not math.isfinite(float(item)) for item in value):
        raise AdapterError(f"{location} values must be finite")
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
        raise AdapterError(f"{location} must stay within normalized 0..1 bounds")
    return value


def build_material_prompt(role: str, reference_bbox: list[float | int], prompt_profile: str = "v1") -> str:
    reference_bbox = validate_reference_bbox(reference_bbox, "reference_bbox")
    if not isinstance(prompt_profile, str):
        raise AdapterError("material prompt_profile must be a string")
    if prompt_profile == "v6":
        if role not in MATERIAL_COMPONENT_ROLES:
            raise AdapterError(f"material adapter does not support component role '{role}'")
        role_instruction = {
            "panel": (
                "Keep only the empty outer container surface and border. Clear every "
                "nested card, icon, illustration and connector from its interior."
            ),
            "diagram-node": (
                "Keep only the empty node body and outline. Clear its internal icon and "
                "label, and separate all incoming and outgoing connectors."
            ),
            "table-shell": (
                "Keep the outer frame, empty cell grid, non-data fills and blank header bands. "
                "Every cell stays empty for editable text and data added later."
            ),
            "chart-shell": (
                "Keep only the non-data frame, blank plotting region and structural grid. "
                "Clear ticks, series, bars, lines, points, areas, legends and any mark "
                "whose geometry or color communicates data."
            ),
            "arrow": (
                "Keep this one arrow's approved path, direction and arrowhead geometry. "
                "Separate it from the nodes, panels and other arrows it connects."
            ),
            "basic-shape": "Keep only this one approved basic shape, with its exact silhouette.",
            "decorative-shape": "Keep only this one approved decorative shape, with its exact silhouette.",
            "icon": (
                "Keep the constituent parts that belong to this one icon; separate "
                "unrelated surrounding objects and any container behind it."
            ),
            "illustration": (
                "Keep the constituent parts of this one approved illustration as a "
                "single object; separate unrelated surrounding objects and containers."
            ),
        }[role]
        return (
            "TASK\n"
            f"Reconstruct exactly one approved {role} component for an editable slide.\n\n"
            "REFERENCE AND TARGET\n"
            "Identify the target inside this normalized region of the original 16:9 slide: "
            f"{json.dumps(reference_bbox, separators=(',', ':'), allow_nan=False)}. "
            "Use the approved concept and its crop as the sole appearance source, "
            "rather than creating a new design.\n\n"
            "PRESERVE\n"
            "Match the target's silhouette, width-to-height proportions, orientation, "
            "palette, surface texture, lighting direction, edge treatment and approved "
            "detail. Do not stretch it to fill the output canvas or add a new material.\n\n"
            "ROLE-SPECIFIC CONTENT\n"
            f"{role_instruction}\n\n"
            "CANVAS AND OUTPUT\n"
            "Return one isolated PNG on a real transparent RGBA canvas. Center the "
            "complete object with clear alpha padding on all sides, including its "
            "approved shadow or glow. Keep intentional interior fills opaque where "
            "shown in the reference; transparency applies to the surrounding canvas.\n\n"
            "EXCLUDE\n"
            "Remove ordinary words, letters, numbers, labels, values and data marks. "
            "Remove the slide background and every neighboring object. No white matte, "
            "painted checkerboard, watermark, mockup, contact sheet or alternate versions."
        )
    if prompt_profile == "v5" and role == "panel":
        return (
            "From the attached approved reference crop, reconstruct ONLY the single empty "
            "rounded rectangular panel frame. Preserve its wide proportions, dark navy "
            "interior fill, thin cyan outline, corner radius and restrained glow. Place this "
            "one frame on a real transparent PNG with a small clear border. Remove incoming "
            "arrows, neighboring frames, icons, text, labels and the slide background."
        )
    if prompt_profile == "v5" and role == "diagram-node":
        return (
            "From the attached approved reference crop, reconstruct ONLY the empty "
            "gold-outlined diamond decision node centered in the crop. Preserve its four "
            "corners, dark navy interior and thin luminous gold edge. Put this one diamond "
            "on a real transparent PNG with a small clear border. Remove every cyan arrow, "
            "connector, neighboring panel, icon, text, label and slide background."
        )
    if prompt_profile == "v4" and role == "decorative-shape":
        return (
            "From the attached approved reference crop, reconstruct ONLY the low, wide "
            "elliptical display platform running across the crop. Keep its navy-blue body, "
            "thin cyan elliptical outline and subtle cyan glow along the front lower edge. "
            "Preserve the platform's very wide, shallow proportions. Put this single platform "
            "on a real transparent PNG with a small clear border. Remove any people, phones, "
            "documents, chat bubbles, arrows, panels, text, labels and slide background."
        )
    if prompt_profile == "v4" and role == "illustration":
        return (
            "From the attached approved reference crop, reconstruct exactly ONE speech bubble "
            "icon with its three round dots, matching the reference silhouette, blue palette, "
            "highlight and outline. Preserve its tail direction and scale. Put it alone on a "
            "real transparent PNG with a small clear border. Remove the platform ellipse, "
            "other bubbles, lines, panels, text, labels and slide background."
        )
    if prompt_profile == "v3" and role == "panel":
        aspect = reference_bbox[2] * 16 / 9 / reference_bbox[3]
        return (
            "From the attached approved reference crop, isolate ONLY the largest outer "
            "chamfered rectangular container frame that runs close to the crop perimeter. "
            f"It has width-to-height ratio about {aspect:.2f}:1. Reconstruct that one empty "
            "outer panel with its subtle dark navy fill and thin cyan edge, preserving its "
            "approved corner cut and line weight. The panel should occupy roughly 90% of "
            "the canvas width and height with a truly transparent alpha border. "
            "Do not select the smaller inset card. Remove the ellipse, icons, arrow, "
            "nested card, text, numbers, labels, all other contents and the slide background."
        )
    if prompt_profile == "v2":
        prompt = (
            "The attached approved reference is a tight crop around normalized slide region "
            f"{json.dumps(reference_bbox, separators=(',', ':'), allow_nan=False)}. "
            f"Isolate exactly ONE outer {role} object visible in that region. "
            "Reconstruct its silhouette, palette, material and edge treatment on a real transparent PNG. "
            "Leave a small completely transparent border on every side. "
            "Remove all neighboring, nested or foreground objects, arrows, icons, illustrations, "
            "letters, words, numbers, labels, data and watermarks."
        )
        if role == "panel":
            prompt += (
                " A panel means ONLY its empty outer container surface and border; "
                "remove every item inside the container, even when those items overlap its surface."
            )
        elif role == "diagram-node":
            prompt += " A diagram node means ONLY the empty node body and outline, without its icon or label."
        return prompt
    if prompt_profile != "v1":
        raise AdapterError(f"unknown material prompt profile: {prompt_profile}")
    prompt = (
        "Using only the approved concept reference and normalized crop "
        f"{json.dumps(reference_bbox, separators=(',', ':'), allow_nan=False)}, reconstruct exactly one "
        f"{role} component as an isolated transparent PNG with generous alpha padding. "
        "Preserve the approved visual style. Include no background, neighboring objects, "
        "labels, words, letters, numbers, values, axes, legends, watermarks, or invented data."
    )
    if role in {"table-shell", "chart-shell"}:
        prompt += (
            " Keep only the empty visual shell and blank content regions; remove ticks, "
            "bars, lines, points, icons, and every other data-encoding mark."
        )
    return prompt


def load_registry(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0":
        raise AdapterError("visual provider registry schema_version must be '1.0'")
    providers = payload.get("providers") if isinstance(payload, dict) else None
    if not isinstance(providers, list) or not providers:
        raise AdapterError("visual provider registry must contain providers")
    registry: dict[str, dict[str, Any]] = {}
    for index, provider in enumerate(providers):
        if not isinstance(provider, dict):
            raise AdapterError(f"provider[{index}] must be an object")
        missing = REQUIRED_PROVIDER_FIELDS - set(provider)
        if missing:
            raise AdapterError(f"provider[{index}] missing fields: {sorted(missing)}")
        for field in STRING_PROVIDER_FIELDS:
            value = provider.get(field)
            if not isinstance(value, str) or not value.strip():
                raise AdapterError(
                    f"provider[{index}] {field} must be a non-empty string"
                )
        provider_id = provider["id"]
        if provider_id in registry:
            raise AdapterError(f"duplicate provider id: {provider_id}")
        if not isinstance(provider.get("auto_route"), bool):
            raise AdapterError(f"provider '{provider_id}' auto_route must be boolean")
        for field, allowed in ALLOWED_PROVIDER_VALUES.items():
            if provider[field] not in allowed:
                raise AdapterError(
                    f"provider '{provider_id}' has unsupported {field}: {provider[field]!r}"
                )
        expected_auto_route = provider["tier"] == "core-auto"
        if provider["auto_route"] is not expected_auto_route:
            raise AdapterError(
                f"provider '{provider_id}' auto_route conflicts with tier '{provider['tier']}'"
            )
        for field in LIST_PROVIDER_FIELDS:
            values = provider.get(field)
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(value, str) or not value.strip() for value in values)
            ):
                raise AdapterError(f"provider '{provider_id}' {field} must be a non-empty list")
            if len(set(values)) != len(values):
                raise AdapterError(f"provider '{provider_id}' {field} contains duplicates")
        registry[provider_id] = provider
    if set(registry) != set(CANONICAL_PROVIDER_CONTRACTS):
        raise AdapterError("visual provider registry must contain the canonical seven providers")
    for provider_id, expected in CANONICAL_PROVIDER_CONTRACTS.items():
        provider = registry[provider_id]
        if provider.get("skill_name") != provider_id:
            raise AdapterError(
                f"provider '{provider_id}' skill_name violates canonical contract"
            )
        for field, expected_value in expected.items():
            actual_value = provider.get(field)
            if isinstance(expected_value, set):
                actual_value = set(actual_value) if isinstance(actual_value, list) else actual_value
            if actual_value != expected_value:
                raise AdapterError(
                    f"provider '{provider_id}' {field} violates canonical contract"
                )
    return registry


def validate_style_policy(
    registry: dict[str, dict[str, Any]], style_contract: dict[str, Any]
) -> tuple[str, dict[str, list[str]], set[str]]:
    if not isinstance(style_contract, dict):
        raise AdapterError("style contract must be an object")
    primary = style_contract.get("primary_visual_family")
    if not isinstance(primary, str) or primary not in registry:
        raise AdapterError("style contract must name one registered primary visual family")
    if registry[primary].get("tier") == "post-release-derivative":
        raise AdapterError("post-release derivative cannot be the primary visual family")

    secondary = style_contract.get("secondary_provider_roles")
    if not isinstance(secondary, dict):
        raise AdapterError("secondary_provider_roles must be an object")
    normalized_secondary: dict[str, list[str]] = {}
    for provider_id, roles in secondary.items():
        if provider_id not in registry:
            raise AdapterError(f"unknown secondary provider: {provider_id}")
        if provider_id == primary:
            raise AdapterError("primary visual family cannot also be a secondary provider")
        if registry[provider_id].get("tier") == "post-release-derivative":
            raise AdapterError("post-release derivative cannot be a slide-level secondary provider")
        if (
            not isinstance(roles, list)
            or not roles
            or any(not isinstance(role, str) or not role for role in roles)
        ):
            raise AdapterError(
                f"secondary provider '{provider_id}' must declare non-empty page roles"
            )
        if len(set(roles)) != len(roles):
            raise AdapterError(f"secondary provider '{provider_id}' has duplicate page roles")
        unsupported = set(roles) - set(
            registry[provider_id].get("supported_page_roles", [])
        )
        if unsupported:
            raise AdapterError(
                f"secondary provider '{provider_id}' declares unsupported page roles: "
                f"{sorted(unsupported)}"
            )
        normalized_secondary[provider_id] = roles

    opt_ins = style_contract.get("explicit_visual_opt_ins")
    if (
        not isinstance(opt_ins, list)
        or any(not isinstance(provider_id, str) or not provider_id for provider_id in opt_ins)
    ):
        raise AdapterError("explicit_visual_opt_ins must be a list of provider ids")
    if len(set(opt_ins)) != len(opt_ins):
        raise AdapterError("explicit_visual_opt_ins contains duplicate provider ids")
    unknown_opt_ins = set(opt_ins) - set(registry)
    if unknown_opt_ins:
        raise AdapterError(f"unknown explicit visual opt-ins: {sorted(unknown_opt_ins)}")
    return primary, normalized_secondary, set(opt_ins)


def provider_matches_auto_request(
    provider: dict[str, Any],
    page_role: str,
    source_kind: str,
    truth_sensitive: bool,
    deliverable_role: str,
) -> bool:
    provider_id = provider.get("id")
    return (
        provider.get("auto_route") is True
        and deliverable_role == "slide-asset"
        and page_role in provider.get("supported_page_roles", [])
        and isinstance(provider_id, str)
        and source_kind in ALLOWED_SOURCE_KINDS_BY_PROVIDER.get(provider_id, set())
        and not (
            truth_sensitive
            and provider.get("truth_policy") == "reject-truth-sensitive"
        )
    )


def _safe_project_file(
    project_root: Path,
    record: Any,
    label: str,
) -> tuple[str, str, Path]:
    if not isinstance(record, dict):
        raise AdapterError(f"{label} must be an object")
    relative_path = record.get("path")
    declared_sha256 = record.get("sha256")
    if not isinstance(relative_path, str) or not relative_path:
        raise AdapterError(f"{label}.path must be a non-empty string")
    relative = PurePosixPath(relative_path)
    if (
        relative.is_absolute()
        or "\\" in relative_path
        or ":" in relative_path
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise AdapterError(f"{label}.path is unsafe: {relative_path}")
    if not isinstance(declared_sha256, str) or not SHA256_PATTERN.fullmatch(
        declared_sha256
    ):
        raise AdapterError(f"{label}.sha256 must be 64 hexadecimal characters")
    root = project_root.resolve()
    resolved = (root / Path(*relative.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise AdapterError(f"{label}.path escapes project: {relative_path}") from error
    try:
        actual_sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
    except OSError as error:
        raise AdapterError(f"cannot read {label} '{relative_path}': {error}") from error
    if declared_sha256.lower() != actual_sha256:
        raise AdapterError(f"{label} SHA-256 is stale: {relative_path}")
    return relative_path, actual_sha256, resolved


def _read_evidence_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AdapterError(f"cannot read {label}: {error}") from error
    if not isinstance(payload, dict):
        raise AdapterError(f"{label} must contain a JSON object")
    return payload


def _value_sha256(value: Any) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def _require_approval_identity(record: dict[str, Any], label: str) -> None:
    approver = record.get("approver")
    approved_at = record.get("approved_at")
    if not isinstance(approver, str) or not approver.strip():
        raise AdapterError(f"{label} requires a non-empty approver")
    if not isinstance(approved_at, str) or not approved_at.strip():
        raise AdapterError(f"{label} requires an ISO-8601 approved_at")
    try:
        approval_time = datetime.fromisoformat(approved_at)
    except ValueError as error:
        raise AdapterError(f"{label} approved_at must be ISO-8601") from error
    if approval_time.utcoffset() is None:
        raise AdapterError(f"{label} approved_at must include a timezone offset")


def _verify_pptx_package(path: Path) -> int:
    if path.suffix.lower() != ".pptx" or not zipfile.is_zipfile(path):
        raise AdapterError("released_deck must be a valid PPTX package")
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            required_parts = {
                "[Content_Types].xml",
                "_rels/.rels",
                "ppt/presentation.xml",
                "ppt/_rels/presentation.xml.rels",
            }
            missing = required_parts - names
            if missing:
                raise AdapterError(
                    f"released_deck PPTX is missing required Office parts: {sorted(missing)}"
                )
            parsed: dict[str, ElementTree.Element] = {}
            for part in required_parts:
                try:
                    parsed[part] = ElementTree.fromstring(archive.read(part))
                except ElementTree.ParseError as error:
                    raise AdapterError(
                        f"released_deck PPTX part is not valid XML: {part}"
                    ) from error
            content_types = parsed["[Content_Types].xml"]
            overrides = {
                node.attrib.get("PartName"): node.attrib.get("ContentType")
                for node in content_types
                if node.tag.endswith("Override")
            }
            main_type = (
                "application/vnd.openxmlformats-officedocument."
                "presentationml.presentation.main+xml"
            )
            if overrides.get("/ppt/presentation.xml") != main_type:
                raise AdapterError(
                    "released_deck PPTX does not declare a presentation main part"
                )
            office_targets = {
                node.attrib.get("Target")
                for node in parsed["_rels/.rels"]
                if node.attrib.get("Type", "").endswith("/officeDocument")
            }
            if "ppt/presentation.xml" not in office_targets:
                raise AdapterError(
                    "released_deck PPTX root relationship does not target the presentation"
                )
            slide_names = {
                name
                for name in names
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            }
            if not slide_names:
                raise AdapterError("released_deck PPTX contains no slides")
            presentation = parsed["ppt/presentation.xml"]
            slide_size = presentation.find(
                ".//{http://schemas.openxmlformats.org/presentationml/2006/main}sldSz"
            )
            try:
                if slide_size is None:
                    raise ValueError
                int(slide_size.attrib["cx"])
                int(slide_size.attrib["cy"])
            except (KeyError, ValueError) as error:
                raise AdapterError(
                    "released_deck PPTX presentation is missing a valid slide size"
                ) from error
            rel_targets = {
                node.attrib["Id"]: posixpath.normpath(
                    posixpath.join("ppt", node.attrib["Target"])
                )
                for node in parsed["ppt/_rels/presentation.xml.rels"]
                if node.attrib.get("Id")
                and node.attrib.get("Target")
                and node.attrib.get("Type", "").endswith("/slide")
                and node.attrib.get("TargetMode", "Internal") == "Internal"
            }
            relationship_attribute = (
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            linked_slides = [
                rel_targets.get(node.attrib.get(relationship_attribute, ""))
                for node in presentation.findall(
                    ".//{http://schemas.openxmlformats.org/presentationml/2006/main}sldId"
                )
            ]
            if (
                None in linked_slides
                or len(linked_slides) != len(slide_names)
                or set(linked_slides) != slide_names
            ):
                raise AdapterError(
                    "released_deck PPTX presentation-to-slide relationship is incomplete"
                )
            slide_type = (
                "application/vnd.openxmlformats-officedocument."
                "presentationml.slide+xml"
            )
            for slide_name in slide_names:
                try:
                    ElementTree.fromstring(archive.read(slide_name))
                except ElementTree.ParseError as error:
                    raise AdapterError(
                        f"released_deck slide is not valid XML: {slide_name}"
                    ) from error
                if overrides.get(f"/{slide_name}") != slide_type:
                    raise AdapterError(
                        f"released_deck content types do not declare slide: {slide_name}"
                    )
            return len(slide_names)
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise AdapterError(f"cannot inspect released_deck PPTX: {error}") from error


def verify_photo_rights(project_root: Path | None, request: dict[str, Any]) -> dict[str, Any]:
    if project_root is None:
        raise AdapterError("photo provider requires verified source-rights evidence")
    rights_record_path, rights_sha256, rights_path = _safe_project_file(
        project_root,
        request.get("source_rights_confirmation"),
        "source_rights_confirmation",
    )
    rights = _read_evidence_json(rights_path, "source-rights confirmation")
    if (
        rights.get("status") != "confirmed"
        or rights.get("approval_phrase") != "确认素材使用权"
        or not isinstance(rights.get("confirmed_by"), str)
        or not rights["confirmed_by"].strip()
    ):
        raise AdapterError("source-rights confirmation lacks explicit human confirmation")
    if (
        rights.get("media_class") != "ordinary-photo"
        or rights.get("truth_sensitive") is not False
        or rights.get("classification_phrase") != "确认普通照片"
        or not isinstance(rights.get("classified_by"), str)
        or not rights["classified_by"].strip()
        or rights.get("excluded_types") != {
            "product_screenshot": True, "data_figure": True, "report": True,
        }
    ):
        raise AdapterError("photo source lacks explicit ordinary-photo classification; screenshots, data figures, and reports are excluded")
    source_record = {
        "path": rights.get("source_path"),
        "sha256": rights.get("source_sha256"),
    }
    source_relative, source_sha256, source_path = _safe_project_file(project_root, source_record, "source-rights source")
    try:
        from PIL import Image
        with Image.open(source_path) as source_image:
            if source_image.format not in {"PNG", "JPEG"} or source_image.width < 3 or source_image.height < 3:
                raise AdapterError("ordinary photo source must be a readable PNG or JPEG")
            source_image.verify()
        with Image.open(source_path) as source_image:
            if looks_like_flat_graphic(source_image):
                raise AdapterError("photo source resembles a flat graphic, screenshot, or report; use the truth-sensitive preservation route")
    except (ImportError, OSError, ValueError) as error:
        raise AdapterError(f"ordinary photo source is not a readable image: {error}") from error
    if request.get("truth_sensitive") is not False:
        raise AdapterError("photo provider cannot postprocess truth-sensitive material")
    requested_source = request.get("source_photo")
    if not isinstance(requested_source, dict) or requested_source.get("path") != source_relative or requested_source.get("sha256") != source_sha256:
        raise AdapterError("requested photo must match the classified, rights-confirmed source")
    try:
        state = json.loads((project_root / "run-state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AdapterError(f"cannot read source-rights approval ledger: {error}") from error
    gates = state.get("gates") if isinstance(state, dict) else None
    gate = gates.get("brief_authority") if isinstance(gates, dict) else None
    artifact_versions = state.get("artifact_versions") if isinstance(state, dict) else None
    approved_artifacts = gate.get("approved_artifacts") if isinstance(gate, dict) else None
    if (
        not isinstance(gate, dict)
        or gate.get("status") != "approved"
        or not isinstance(artifact_versions, dict)
        or gate.get("artifact_version") != artifact_versions.get("brief_authority")
        or not isinstance(approved_artifacts, dict)
        or approved_artifacts.get(rights_record_path) != rights_sha256
    ):
        raise AdapterError("source-rights confirmation is not a current G1-approved artifact")
    return rights


def looks_like_flat_graphic(image: Any) -> bool:
    """Conservative raster tripwire; semantic source classification remains human."""
    from PIL import Image

    if image.width * image.height < 32_768:
        return False
    sample = image.convert("RGB")
    sample.thumbnail((192, 192), Image.Resampling.NEAREST)
    width, height = sample.size
    pixels = list(sample.getdata())
    if not pixels:
        return False
    unique_ratio = len(set(pixels)) / len(pixels)
    if unique_ratio > 0.12:
        return False
    flat_pairs = 0
    pairs = 0
    for y in range(height):
        for x in range(width):
            current = pixels[y * width + x]
            for other_index in ((y * width + x + 1) if x + 1 < width else None,
                                ((y + 1) * width + x) if y + 1 < height else None):
                if other_index is None:
                    continue
                other = pixels[other_index]
                pairs += 1
                if max(abs(current[channel] - other[channel]) for channel in range(3)) <= 2:
                    flat_pairs += 1
    return pairs > 0 and flat_pairs / pairs >= 0.82


def verify_special_page_approval(
    project_root: Path | None,
    request: dict[str, Any],
    provider_id: str,
    page_role: str,
) -> None:
    if project_root is None:
        raise AdapterError("explicit-style provider requires verified G4 special-page approval")
    slide_id = request.get("slide_id")
    if not isinstance(slide_id, str) or not SAFE_ID_PATTERN.fullmatch(slide_id):
        raise AdapterError("explicit-style provider requires a safe non-empty slide_id")
    approval_path, approval_sha256, resolved = _safe_project_file(
        project_root,
        request.get("special_page_approval"),
        "special_page_approval",
    )
    approval = _read_evidence_json(resolved, "special-page approval")
    if (
        approval.get("status") != "approved"
        or approval.get("approval_phrase") != "确认特殊页面风格"
        or approval.get("provider_id") != provider_id
        or approval.get("page_role") != page_role
        or not isinstance(approval.get("slide_id"), str)
        or approval.get("slide_id") != slide_id
    ):
        raise AdapterError("special-page approval does not match the routing request")
    try:
        state = json.loads((project_root / "run-state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AdapterError(f"cannot read G4 approval ledger: {error}") from error
    gates = state.get("gates") if isinstance(state, dict) else None
    gate = gates.get("concept_contact_sheet") if isinstance(gates, dict) else None
    artifact_versions = state.get("artifact_versions") if isinstance(state, dict) else None
    approved_artifacts = gate.get("approved_artifacts") if isinstance(gate, dict) else None
    if (
        not isinstance(gate, dict)
        or gate.get("status") != "approved"
        or not isinstance(artifact_versions, dict)
        or gate.get("artifact_version") != artifact_versions.get(
            "concept_contact_sheet"
        )
        or not isinstance(approved_artifacts, dict)
        or approved_artifacts.get(approval_path) != approval_sha256
    ):
        raise AdapterError("special-page approval is not an approved G4 artifact")


def route_provider(
    registry: dict[str, dict[str, Any]],
    request: dict[str, Any],
    style_contract: dict[str, Any],
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Select one provider while enforcing truth, style, and release boundaries."""
    if not isinstance(request, dict):
        raise AdapterError("routing request must be an object")
    primary, secondary, opt_ins = validate_style_policy(registry, style_contract)
    page_role = request.get("page_role")
    source_kind = request.get("source_kind")
    deliverable_role = request.get("deliverable_role")
    truth_sensitive = request.get("truth_sensitive")
    if not isinstance(page_role, str) or not page_role:
        raise AdapterError("page_role must be a non-empty string")
    if not isinstance(source_kind, str) or not source_kind:
        raise AdapterError("source_kind must be a non-empty string")
    if deliverable_role not in {"slide-asset", "post-release-derivative"}:
        raise AdapterError(
            "deliverable_role must be 'slide-asset' or 'post-release-derivative'"
        )
    if not isinstance(truth_sensitive, bool):
        raise AdapterError("truth_sensitive must be boolean")

    requested_id = request.get("provider_id")
    if requested_id is not None and (
        not isinstance(requested_id, str) or requested_id not in registry
    ):
        raise AdapterError(f"unknown visual provider: {requested_id}")

    social_id = "guizang-social-card-skill"
    if requested_id == social_id or deliverable_role == "post-release-derivative":
        if requested_id != social_id:
            raise AdapterError("post-release derivative requires explicit social-card provider")
        if deliverable_role != "post-release-derivative":
            raise AdapterError("social card is a post-release derivative, not a slide renderer")
        if request.get("deck_released") is not True:
            raise AdapterError("social card requires a released deck")
        if project_root is None:
            raise AdapterError("social card requires verified G5 project state")
        verify_release_approval(project_root, request)
        provider = registry[social_id]
        if source_kind not in ALLOWED_SOURCE_KINDS_BY_PROVIDER[social_id]:
            raise AdapterError(
                f"provider '{social_id}' cannot process source kind '{source_kind}'"
            )
        if page_role not in provider.get("supported_page_roles", []):
            raise AdapterError(
                f"provider '{social_id}' does not support page role '{page_role}'"
            )
        return provider

    if requested_id is None:
        candidates = [
            provider
            for provider in registry.values()
            if provider_matches_auto_request(
                provider,
                page_role,
                source_kind,
                truth_sensitive,
                deliverable_role,
            )
        ]
        if not candidates:
            raise AdapterError(
                f"no compatible auto-route provider for page role '{page_role}'; "
                "select and approve an explicit provider"
            )
        primary_candidates = [provider for provider in candidates if provider["id"] == primary]
        if len(primary_candidates) == 1:
            provider = primary_candidates[0]
        elif len(candidates) == 1:
            provider = candidates[0]
        else:
            raise AdapterError(
                f"ambiguous auto-route providers for page role '{page_role}'"
            )
    else:
        provider = registry[requested_id]

    provider_id = provider["id"]
    if provider.get("tier") == "post-release-derivative":
        raise AdapterError("post-release derivative cannot render slide assets")
    if page_role not in provider.get("supported_page_roles", []):
        raise AdapterError(
            f"provider '{provider_id}' does not support page role '{page_role}'"
        )
    if provider.get("truth_policy") == "reject-truth-sensitive" and truth_sensitive:
        raise AdapterError(f"provider '{provider_id}' rejects truth-sensitive visuals")
    allowed_source_kinds = ALLOWED_SOURCE_KINDS_BY_PROVIDER.get(provider_id, set())
    if source_kind not in allowed_source_kinds:
        raise AdapterError(
            f"provider '{provider_id}' cannot process source kind '{source_kind}'"
        )
    if provider.get("tier") == "explicit-style" and provider_id not in opt_ins:
        raise AdapterError(f"provider '{provider_id}' requires explicit opt-in")

    if provider_id != primary:
        allowed_roles = secondary.get(provider_id, [])
        if page_role not in allowed_roles:
            raise AdapterError(
                f"secondary provider role '{page_role}' is not declared for '{provider_id}'"
            )
    if provider_id == "photo-postprocess-coach":
        verify_photo_rights(project_root, request)
    if provider.get("tier") == "explicit-style":
        verify_special_page_approval(project_root, request, provider_id, page_role)
    return provider


def verify_release_approval(project_root: Path, request: dict[str, Any]) -> None:
    root = project_root.resolve()
    if not root.is_dir():
        raise AdapterError(f"project_root is not a directory: {project_root}")
    try:
        state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdapterError(f"cannot read release approval ledger: {error}") from error
    if not isinstance(state, dict) or state.get("stage") != "released":
        raise AdapterError("social card requires project stage 'released'")
    gates = state.get("gates")
    release = gates.get("release") if isinstance(gates, dict) else None
    if (
        not isinstance(release, dict)
        or release.get("status") != "approved"
        or release.get("approval_mode") != "release"
        or release.get("approval_phrase") != "确认发布"
    ):
        raise AdapterError("social card requires an approved G5 release record")
    _require_approval_identity(release, "G5 release")
    release_version = release.get("artifact_version")
    artifact_versions = state.get("artifact_versions")
    if (
        not isinstance(release_version, str)
        or not isinstance(artifact_versions, dict)
        or artifact_versions.get("release") != release_version
    ):
        raise AdapterError("G5 release version is missing or stale")
    approved_artifacts = release.get("approved_artifacts")
    if not isinstance(approved_artifacts, dict) or not approved_artifacts:
        raise AdapterError("G5 release has no approved artifacts")
    approval_packet = release.get("approval_packet")
    required_release_decisions = {
        "final_render",
        "concept_differences",
        "qa_exceptions",
        "component_usability",
        "deliverable_index",
    }
    decisions = (
        approval_packet.get("decisions")
        if isinstance(approval_packet, dict)
        else None
    )
    if (
        not isinstance(approval_packet, dict)
        or approval_packet.get("gate") != "release"
        or approval_packet.get("version") != release_version
        or not isinstance(decisions, dict)
        or set(decisions) != required_release_decisions
    ):
        raise AdapterError("G5 release approval packet is incomplete")
    for decision_id, decision in decisions.items():
        if (
            not isinstance(decision, dict)
            or decision.get("status") != "approved"
            or not _has_meaningful_value(decision.get("value"))
            or decision.get("value_sha256") != _value_sha256(decision.get("value"))
        ):
            raise AdapterError(
                f"G5 release decision is not fully approved: {decision_id}"
            )

    try:
        qa_report = _read_evidence_json(root / "qa-report.json", "released QA report")
        manifest = _read_evidence_json(
            root / "asset-manifest.json", "released asset manifest"
        )
        assembly = _read_evidence_json(
            root / "assembly-map.json", "released assembly map"
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AdapterError(f"cannot read released G5 package: {error}") from error
    if not isinstance(qa_report, dict) or qa_report.get("status") != "passed":
        raise AdapterError("released QA report must have status 'passed'")
    manifest_assets = manifest.get("assets")
    assembly_slides = assembly.get("slides")
    if not isinstance(manifest_assets, list):
        raise AdapterError("released asset manifest requires an assets list")
    if not isinstance(assembly_slides, list) or not assembly_slides:
        raise AdapterError("released assembly map requires slide records")
    required_release_artifacts = {
        "asset-manifest.json",
        "assembly-map.json",
        "qa-report.json",
    }
    for field in ("final_contact_sheet", "exception_register", "deliverable_index"):
        value = qa_report.get(field)
        if not isinstance(value, str) or not value:
            raise AdapterError(f"released QA report is missing {field}")
        required_release_artifacts.add(value)
    evidence_files = qa_report.get("evidence_files")
    if (
        not isinstance(evidence_files, list)
        or not evidence_files
        or any(not isinstance(path, str) or not path for path in evidence_files)
    ):
        raise AdapterError("released QA report requires evidence_files")
    required_release_artifacts.update(evidence_files)
    checks_performed = qa_report.get("checks_performed")
    required_checks = {
        "contract",
        "inventory",
        "alpha",
        "overlay",
    }
    if not isinstance(checks_performed, list) or not required_checks.issubset(
        set(checks_performed)
    ):
        raise AdapterError("released QA report is missing mandatory checks")
    slides = qa_report.get("slides")
    if not isinstance(slides, list) or not slides:
        raise AdapterError("released QA report requires slide evidence records")
    qa_slide_ids: set[str] = set()
    for slide in slides:
        if not isinstance(slide, dict):
            raise AdapterError("released QA slide records must be objects")
        slide_id = slide.get("slide_id")
        if (
            not isinstance(slide_id, str)
            or not SAFE_ID_PATTERN.fullmatch(slide_id)
            or slide_id in qa_slide_ids
        ):
            raise AdapterError("released QA slide_id must be safe and unique")
        qa_slide_ids.add(slide_id)
        if slide.get("status") != "passed":
            raise AdapterError(f"released QA slide has not passed: {slide_id}")
        slide_evidence = slide.get("evidence_files")
        if (
            not isinstance(slide_evidence, list)
            or not slide_evidence
            or any(not isinstance(path, str) or not path for path in slide_evidence)
        ):
            raise AdapterError("released QA slide requires evidence_files")
        required_release_artifacts.update(slide_evidence)
    for field in ("differences", "exceptions"):
        if not isinstance(qa_report.get(field), list):
            raise AdapterError(f"released QA report requires {field} list")
    missing_release_artifacts = required_release_artifacts - set(approved_artifacts)
    if missing_release_artifacts:
        raise AdapterError(
            "G5 release is missing mandatory approved artifacts: "
            f"{sorted(missing_release_artifacts)}"
        )
    for relative_path, approved_sha256 in approved_artifacts.items():
        if not isinstance(relative_path, str):
            raise AdapterError("G5 approved artifact path must be a string")
        relative = PurePosixPath(relative_path)
        if (
            relative.is_absolute()
            or "\\" in relative_path
            or ":" in relative_path
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise AdapterError(f"G5 approved artifact path is unsafe: {relative_path}")
        resolved = (root / Path(*relative.parts)).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise AdapterError(
                f"G5 approved artifact escapes project: {relative_path}"
            ) from error
        try:
            actual_sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
        except OSError as error:
            raise AdapterError(
                f"cannot read G5 approved artifact '{relative_path}': {error}"
            ) from error
        if (
            not isinstance(approved_sha256, str)
            or not SHA256_PATTERN.fullmatch(approved_sha256)
            or approved_sha256.lower() != actual_sha256
        ):
            raise AdapterError(
                f"G5 approved artifact SHA-256 is stale: {relative_path}"
            )

    deck_path, deck_sha256, deck_file = _safe_project_file(
        root, request.get("released_deck"), "released_deck"
    )
    if approved_artifacts.get(deck_path) != deck_sha256:
        raise AdapterError("released_deck is not an approved G5 artifact")
    pptx_slide_count = _verify_pptx_package(deck_file)
    if assembly.get("output") != deck_path or assembly.get("sha256") != deck_sha256:
        raise AdapterError("released_deck does not match the approved assembly output")
    if qa_report.get("subject_sha256") != deck_sha256:
        raise AdapterError("released QA subject_sha256 does not match released_deck")
    assembly_slide_ids = {
        slide.get("slide_id")
        for slide in assembly_slides
        if isinstance(slide, dict)
        and isinstance(slide.get("slide_id"), str)
        and SAFE_ID_PATTERN.fullmatch(slide["slide_id"])
    }
    if (
        len(assembly_slide_ids) != len(assembly_slides)
        or assembly_slide_ids != qa_slide_ids
        or pptx_slide_count != len(assembly_slides)
    ):
        raise AdapterError(
            "released deck, assembly map, and QA slide inventory do not match"
        )

    expected_decisions = {
        "final_render": {
            "contact_sheet": qa_report.get("final_contact_sheet"),
            "evidence_files": qa_report.get("evidence_files", []),
        },
        "concept_differences": {"items": qa_report.get("differences", [])},
        "qa_exceptions": {
            "items": qa_report.get("exceptions", []),
            "register": qa_report.get("exception_register"),
        },
        "component_usability": {
            slide.get("slide_id"): {
                "component_ids": slide.get("component_ids", []),
                "fill_slot_ids": slide.get("fill_slot_ids", []),
            }
            for slide in assembly_slides
            if isinstance(slide, dict)
        },
        "deliverable_index": {
            "path": qa_report.get("deliverable_index"),
            "asset_outputs": [
                asset.get("output")
                for asset in manifest_assets
                if isinstance(asset, dict)
            ],
        },
    }
    for decision_id, expected_value in expected_decisions.items():
        if decisions[decision_id].get("value") != expected_value:
            raise AdapterError(
                f"G5 release decision differs from current artifacts: {decision_id}"
            )
    brief_path, brief_sha256, brief_file = _safe_project_file(
        root,
        request.get("approved_derivative_brief"),
        "approved_derivative_brief",
    )
    brief = _read_evidence_json(brief_file, "approved derivative brief")
    if brief.get("source_deck_sha256") != deck_sha256:
        raise AdapterError("approved derivative brief does not target the released deck")
    derivative_approvals = state.get("post_release_derivatives")
    derivative = (
        derivative_approvals.get("guizang-social-card-skill")
        if isinstance(derivative_approvals, dict)
        else None
    )
    derivative_artifacts = (
        derivative.get("approved_artifacts") if isinstance(derivative, dict) else None
    )
    if isinstance(derivative, dict):
        _require_approval_identity(derivative, "post-release derivative approval")
    if (
        not isinstance(derivative, dict)
        or derivative.get("status") != "approved"
        or derivative.get("approval_phrase") != "确认社交卡衍生"
        or derivative.get("source_deck_sha256") != deck_sha256
        or not isinstance(derivative_artifacts, dict)
        or derivative_artifacts.get(brief_path) != brief_sha256
    ):
        raise AdapterError("approved derivative brief lacks post-release human approval")


def _validated_approval_context(
    request: dict[str, Any], style_contract_version: str, project_root: Path
) -> tuple[str, dict[str, dict[str, str]]]:
    approved_style = request.get("approved_style_contract")
    if not isinstance(approved_style, dict):
        raise AdapterError("approved_style_contract must be an object")
    if approved_style.get("artifact") != "style-contract.json":
        raise AdapterError("approved_style_contract artifact must be style-contract.json")
    if approved_style.get("approval_gate") != "style_anchors":
        raise AdapterError("approved_style_contract must be approved at style_anchors")
    approved_version = approved_style.get("version")
    if approved_version != style_contract_version:
        raise AdapterError("style_contract_version does not match approved style")
    style_sha256 = approved_style.get("sha256")
    if not isinstance(style_sha256, str) or not SHA256_PATTERN.fullmatch(style_sha256):
        raise AdapterError("approved_style_contract sha256 must be 64 hexadecimal characters")

    records = request.get("approved_references")
    if not isinstance(records, list) or not records:
        raise AdapterError("approved_references must be a non-empty list")
    approved_references: dict[str, dict[str, str]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise AdapterError(f"approved_references[{index}] must be an object")
        path = record.get("path")
        sha256 = record.get("sha256")
        gate = record.get("approval_gate")
        if not isinstance(path, str) or not path.strip():
            raise AdapterError(
                f"approved_references[{index}].path must be a non-empty string"
            )
        if path in approved_references:
            raise AdapterError(f"duplicate approved reference path: {path}")
        if not isinstance(sha256, str) or not SHA256_PATTERN.fullmatch(sha256):
            raise AdapterError(
                f"approved_references[{index}].sha256 must be 64 hexadecimal characters"
            )
        if gate != "concept_contact_sheet":
            raise AdapterError(
                f"approved_references[{index}] must be approved at concept_contact_sheet"
            )
        approved_references[path] = {
            "path": path,
            "sha256": sha256,
            "approval_gate": gate,
        }
    root = project_root.resolve()
    if not root.is_dir():
        raise AdapterError(f"project_root is not a directory: {project_root}")
    run_state_path = root / "run-state.json"
    style_path = root / "style-contract.json"
    try:
        run_state = json.loads(run_state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdapterError(f"cannot read approval ledger: {error}") from error
    if not isinstance(run_state, dict) or not isinstance(run_state.get("gates"), dict):
        raise AdapterError("approval ledger must contain gates")

    style_gate = run_state["gates"].get("style_anchors")
    if not isinstance(style_gate, dict) or style_gate.get("status") != "approved":
        raise AdapterError("style_anchors gate is not approved")
    if style_gate.get("artifact_version") != style_contract_version:
        raise AdapterError("style contract version does not match the approval ledger")
    try:
        actual_style_sha256 = hashlib.sha256(style_path.read_bytes()).hexdigest()
    except OSError as error:
        raise AdapterError(f"cannot read approved style contract: {error}") from error
    style_ledger_hash = style_gate.get("approved_artifacts", {}).get(
        "style-contract.json"
    ) if isinstance(style_gate.get("approved_artifacts"), dict) else None
    if style_sha256.lower() != actual_style_sha256 or style_ledger_hash != actual_style_sha256:
        raise AdapterError("style contract SHA-256 does not match the approved artifact")

    concept_gate = run_state["gates"].get("concept_contact_sheet")
    if not isinstance(concept_gate, dict) or concept_gate.get("status") != "approved":
        raise AdapterError("concept_contact_sheet gate is not approved")
    concept_artifacts = concept_gate.get("approved_artifacts")
    if not isinstance(concept_artifacts, dict):
        raise AdapterError("concept_contact_sheet approval has no approved_artifacts")
    for path, record in approved_references.items():
        relative = PurePosixPath(path)
        if (
            relative.is_absolute()
            or "\\" in path
            or ":" in path
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise AdapterError(f"approved reference path is unsafe: {path}")
        resolved = (root / Path(*relative.parts)).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise AdapterError(f"approved reference path escapes project: {path}") from error
        try:
            actual_sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
        except OSError as error:
            raise AdapterError(f"cannot read approved reference '{path}': {error}") from error
        if record["sha256"].lower() != actual_sha256:
            raise AdapterError(f"approved reference SHA-256 does not match file: {path}")
        if concept_artifacts.get(path) != actual_sha256:
            raise AdapterError(f"reference is not approved by concept_contact_sheet: {path}")
    return actual_style_sha256, approved_references


def _approved_decomposition_items(project_root: Path, slide_id: str, approved_references: dict[str, dict[str, str]]) -> tuple[list[dict[str, Any]], str]:
    """Bind prompt-ready components to the current explicit post-G4 inventory gate."""
    root = project_root.resolve()
    try:
        state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
        map_path = root / "decomposition-map.json"
        decomposition = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdapterError(f"cannot read approved decomposition: {error}") from error
    gate = state.get("gates", {}).get("decomposition") if isinstance(state, dict) else None
    version = decomposition.get("version") if isinstance(decomposition, dict) else None
    approved_at = gate.get("approved_at") if isinstance(gate, dict) else None
    try:
        approval_time = datetime.fromisoformat(approved_at) if isinstance(approved_at, str) else None
    except ValueError:
        approval_time = None
    approval_phrase = gate.get("approval_phrase") if isinstance(gate, dict) else None
    if (
        not isinstance(gate, dict) or gate.get("status") != "approved"
        or gate.get("approval_mode") != "explicit"
        or not isinstance(gate.get("approver"), str) or not gate["approver"].strip()
        or approval_time is None or approval_time.utcoffset() is None
        or not isinstance(approval_phrase, str) or not approval_phrase.strip()
        or approval_phrase.strip().lower() in {"按推荐", "全部按推荐", "推荐", "同意", "可以", "好的", "ok"}
        or not isinstance(version, str) or not version
        or gate.get("artifact_version") != version
        or state.get("artifact_versions", {}).get("decomposition") != version
    ):
        raise AdapterError("decomposition gate lacks current explicit human approval")
    artifacts = gate.get("approved_artifacts")
    if not isinstance(artifacts, dict) or artifacts.get("decomposition-map.json") != hashlib.sha256(map_path.read_bytes()).hexdigest():
        raise AdapterError("decomposition map is not the approved current artifact")
    slides = decomposition.get("slides")
    if not isinstance(slides, list) or not slides:
        raise AdapterError("decomposition map has no slide inventory")
    expected: dict[str, dict[str, Any]] = {
        "object_inventory": {}, "coverage_review": {}, "review_evidence": {},
    }
    selected: list[dict[str, Any]] | None = None
    selected_concept: str | None = None
    for slide in slides:
        if not isinstance(slide, dict) or not isinstance(slide.get("slide_id"), str) or not isinstance(slide.get("items"), list):
            raise AdapterError("decomposition map contains an invalid slide inventory")
        sid = slide["slide_id"]
        if sid in expected["object_inventory"]:
            raise AdapterError("decomposition map repeats a slide")
        expected["object_inventory"][sid] = slide["items"]
        expected["coverage_review"][sid] = slide.get("coverage_review")
        expected["review_evidence"][sid] = {
            "review_image": slide.get("review_image"), "review_packet": slide.get("review_packet"),
        }
        coverage = slide.get("coverage_review")
        if not isinstance(coverage, dict) or any(coverage.get(key) is not True for key in ("semantic_passed", "residual_passed", "independence_passed")) or coverage.get("missing_items") != [] or not isinstance(coverage.get("reviewer"), str) or not coverage["reviewer"].strip():
            raise AdapterError(f"slide '{sid}' lacks passed human decomposition coverage review")
        for path_key, hash_key in (("concept_path", "concept_sha256"), ("master_path", "master_sha256")):
            relative = slide.get(path_key)
            if not isinstance(relative, str):
                raise AdapterError(f"decomposition {path_key} is missing")
            path = PurePosixPath(relative)
            if path.is_absolute() or "\\" in relative or ":" in relative or any(part in {"", ".", ".."} for part in path.parts):
                raise AdapterError(f"unsafe decomposition source path: {relative}")
            resolved = (root / Path(*path.parts)).resolve()
            if not resolved.is_relative_to(root):
                raise AdapterError(f"decomposition source escapes project: {relative}")
            try:
                actual_sha = hashlib.sha256(resolved.read_bytes()).hexdigest()
            except OSError as error:
                raise AdapterError(f"cannot read decomposition source: {relative}") from error
            if slide.get(hash_key) != actual_sha or artifacts.get(relative) != actual_sha:
                raise AdapterError(f"decomposition source is stale: {relative}")
        if sid == slide_id:
            selected = slide["items"]
            concept_relative = slide["concept_path"]
            selected_concept = concept_relative
            if concept_relative not in approved_references or approved_references[concept_relative]["sha256"] != slide["concept_sha256"]:
                raise AdapterError("selected decomposition concept is not an approved request reference")
        for field in ("review_image", "review_packet"):
            evidence = slide.get(field)
            if not isinstance(evidence, dict) or not isinstance(evidence.get("path"), str):
                raise AdapterError(f"slide '{sid}' lacks {field} evidence")
            path = evidence["path"]
            relative = PurePosixPath(path)
            if relative.is_absolute() or "\\" in path or ":" in path or any(part in {"", ".", ".."} for part in relative.parts):
                raise AdapterError(f"unsafe decomposition evidence path: {path}")
            resolved = (root / Path(*relative.parts)).resolve()
            if not resolved.is_relative_to(root):
                raise AdapterError(f"decomposition evidence escapes project: {path}")
            try:
                sha = hashlib.sha256(resolved.read_bytes()).hexdigest()
            except OSError as error:
                raise AdapterError(f"cannot read decomposition evidence: {path}") from error
            if evidence.get("sha256") != sha or artifacts.get(path) != sha:
                raise AdapterError(f"decomposition evidence is stale: {path}")
    packet = gate.get("approval_packet")
    decisions = packet.get("decisions") if isinstance(packet, dict) else None
    if not isinstance(packet, dict) or packet.get("gate") != "decomposition" or packet.get("version") != version or not isinstance(decisions, dict) or set(decisions) != set(expected):
        raise AdapterError("decomposition approval packet is missing or stale")
    for key, value in expected.items():
        decision = decisions[key]
        canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if not isinstance(decision, dict) or decision.get("status") != "approved" or decision.get("value") != value or decision.get("value_sha256") != hashlib.sha256(canonical).hexdigest():
            raise AdapterError(f"decomposition decision is not approved for current {key}")
    if selected is None or selected_concept is None:
        raise AdapterError(f"slide '{slide_id}' is absent from approved decomposition")
    return selected, selected_concept


def adapt_plan(
    registry: dict[str, dict[str, Any]], request: dict[str, Any], project_root: Path
) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise AdapterError("request must be a JSON object")
    provider_id = request.get("provider_id")
    if not isinstance(provider_id, str) or not provider_id:
        raise AdapterError("provider_id must be a non-empty string")
    provider = registry.get(provider_id)
    if provider is None:
        raise AdapterError(f"unknown visual provider: {provider_id}")
    if provider.get("adapter") != "material-illustration-v1":
        raise AdapterError(f"provider '{provider_id}' has no compatible PPT adapter")
    if (
        provider.get("transparency_behavior") != "required-real-alpha"
        or provider.get("output_class") != "transparent-png-component"
    ):
        raise AdapterError(f"provider '{provider_id}' has an incompatible transparency contract")
    if (
        provider.get("aspect_ratio_behavior")
        != "one-component-per-transparent-canvas"
    ):
        raise AdapterError(f"provider '{provider_id}' has an incompatible component-canvas contract")
    if provider.get("text_policy") != "no-ordinary-text-or-data":
        raise AdapterError(f"provider '{provider_id}' has an incompatible text contract")
    if provider.get("truth_policy") != "reject-truth-sensitive":
        raise AdapterError(f"provider '{provider_id}' has an incompatible truth contract")
    if set(provider.get("supported_component_roles", [])) != MATERIAL_COMPONENT_ROLES:
        raise AdapterError(
            f"provider '{provider_id}' has an incompatible component-role contract"
        )
    page_role = request.get("page_role")
    if page_role not in provider.get("supported_page_roles", []):
        raise AdapterError(
            f"provider '{provider_id}' does not support page role '{page_role}'"
        )
    if request.get("truth_sensitive") is not False:
        raise AdapterError(
            f"provider '{provider_id}' rejects truth-sensitive visual generation"
        )
    source_kind = request.get("source_kind")
    if source_kind != "approved-concept-render":
        raise AdapterError(
            "material adapter source_kind must be 'approved-concept-render'"
        )
    if request.get("deliverable_role") != "slide-asset":
        raise AdapterError("material adapter can produce only slide-asset components")
    slide_id = request.get("slide_id")
    if not isinstance(slide_id, str) or not SAFE_ID_PATTERN.fullmatch(slide_id):
        raise AdapterError("slide_id must be a safe identifier")
    style_contract_version = request.get("style_contract_version")
    if not isinstance(style_contract_version, str) or not style_contract_version.strip():
        raise AdapterError("style_contract_version must be a non-empty string")
    style_contract_sha256, approved_references = _validated_approval_context(
        request, style_contract_version, project_root
    )
    elements = request.get("elements")
    if not isinstance(elements, list) or not elements:
        raise AdapterError("elements must be a non-empty list")
    approved_items, selected_concept = _approved_decomposition_items(project_root, slide_id, approved_references)
    prompt_profile = request.get("prompt_profile", "v6")
    assets: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            raise AdapterError(f"element[{index}] must be an object")
        component_id = element.get("id")
        if not isinstance(component_id, str) or not SAFE_ID_PATTERN.fullmatch(component_id):
            raise AdapterError(f"element[{index}] id must be a safe identifier")
        if component_id in seen_ids:
            raise AdapterError(f"duplicate component id: {component_id}")
        seen_ids.add(component_id)
        role = element.get("role")
        if role not in MATERIAL_COMPONENT_ROLES:
            raise AdapterError(f"material adapter does not support component role '{role}'")
        is_shell = role in {"table-shell", "chart-shell"}
        fill_slot_ids = element.get("fill_slot_ids", [])
        if not isinstance(fill_slot_ids, list):
            raise AdapterError(f"element '{component_id}' fill_slot_ids must be a list")
        if is_shell and not fill_slot_ids:
            raise AdapterError(f"{role} '{component_id}' requires blank fill slots")
        if any(
            not isinstance(fill_slot_id, str)
            or not SAFE_ID_PATTERN.fullmatch(fill_slot_id)
            for fill_slot_id in fill_slot_ids
        ):
            raise AdapterError(
                f"element '{component_id}' fill_slot_ids must contain safe string ids"
            )
        if len(set(fill_slot_ids)) != len(fill_slot_ids):
            raise AdapterError(f"element '{component_id}' fill_slot_ids must be unique")
        for field in ("contains_text", "contains_data", "contains_data_encoding_marks"):
            value = element.get(field, False)
            if not isinstance(value, bool):
                raise AdapterError(f"element '{component_id}' {field} must be boolean")
            if value:
                raise AdapterError(
                    f"element '{component_id}' cannot request embedded text, data, or data-encoding marks"
                )
        if "prompt" in element or "prompt_language" in element:
            raise AdapterError(
                f"element '{component_id}' cannot supply a free-form prompt; "
                "the adapter derives it from approved visual structure"
            )
        reference_bbox = validate_reference_bbox(
            element.get("reference_bbox"), f"element '{component_id}' reference_bbox"
        )
        matches = [
            item for item in approved_items
            if isinstance(item, dict) and item.get("kind") == "visual" and item.get("component_id") == component_id
        ]
        if not matches or any(
            item.get("role") != role or item.get("treatment") != "reconstruct-single"
            or item.get("source_class") != "design-object"
            or not (
                item.get("contains_ordinary_text_or_data") is False
                or (
                    item.get("contains_ordinary_text_or_data") is True
                    and item.get("text_data_decision") == "blank-for-fill-slots"
                )
            )
            for item in matches
        ) or not any(item.get("bbox") == reference_bbox for item in matches):
            raise AdapterError(f"element '{component_id}' does not match one approved reconstruct-single decomposition object")
        references = element.get("references")
        if (
            not isinstance(references, list)
            or not references
            or any(not isinstance(reference, str) or not reference.strip() for reference in references)
        ):
            raise AdapterError(
                f"element '{component_id}' requires non-empty approved references"
            )
        unknown_references = [
            reference for reference in references if reference not in approved_references
        ]
        if unknown_references:
            raise AdapterError(
                f"element '{component_id}' reference is not in the approved reference set: "
                f"{unknown_references}"
            )
        if selected_concept not in references:
            raise AdapterError(f"element '{component_id}' must cite its own approved slide concept")
        content_policy = "blank-fill-slots" if is_shell else "no-text-or-data"
        adapted_prompt = build_material_prompt(role, reference_bbox, prompt_profile)
        assets.append(
            {
                "id": component_id,
                "slide_id": slide_id,
                "role": role,
                "page_role": page_role,
                "provider_id": provider_id,
                "adapter_id": provider["adapter"],
                "style_contract_version": style_contract_version,
                "style_contract_sha256": style_contract_sha256,
                "source_kind": source_kind,
                "truth_sensitive": False,
                "deliverable_role": "slide-asset",
                "strategy": "generated-transparent-png",
                "editability": "component-editable",
                "content_policy": content_policy,
                "background_requirement": "transparent",
                "output_class": "transparent-png-component",
                "provider_transparency_behavior": provider[
                    "transparency_behavior"
                ],
                "provider_aspect_ratio_behavior": provider[
                    "aspect_ratio_behavior"
                ],
                "contains_text": False,
                "contains_data": False,
                "contains_data_encoding_marks": False,
                "fill_slot_ids": fill_slot_ids,
                "reference_bbox": reference_bbox,
                "prompt_profile": prompt_profile,
                "prompt": adapted_prompt,
                "prompt_language": "en",
                "references": [approved_references[reference] for reference in references],
                "generation_tool": "codex-image_gen",
                "output": f"assets/{slide_id}/{component_id}.png",
                "sha256": None,
                "alpha": None,
                "generation_attempts": 0,
                "status": "planned",
                "review_evidence": [],
            }
        )
    return {
        "provider_id": provider_id,
        "adapter_id": provider["adapter"],
        "slide_id": slide_id,
        "page_role": page_role,
        "assets": assets,
    }


def adapt_photo_plan(
    registry: dict[str, dict[str, Any]], request: dict[str, Any], project_root: Path
) -> dict[str, Any]:
    """Plan one source-bound photo object; altered outputs still require coaching and review."""
    if not isinstance(request, dict):
        raise AdapterError("photo request must be a JSON object")
    provider = registry.get("photo-postprocess-coach")
    if provider is None or request.get("provider_id") != provider["id"]:
        raise AdapterError("photo plan requires photo-postprocess-coach")
    slide_id = request.get("slide_id")
    component_id = request.get("id")
    if not isinstance(slide_id, str) or not SAFE_ID_PATTERN.fullmatch(slide_id) or not isinstance(component_id, str) or not SAFE_ID_PATTERN.fullmatch(component_id):
        raise AdapterError("photo slide_id and component id must be safe")
    style_path = project_root / "style-contract.json"
    try:
        style = json.loads(style_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdapterError(f"cannot read photo style contract: {error}") from error
    route_provider(registry, request, style, project_root=project_root)
    style_version = request.get("style_contract_version")
    if not isinstance(style_version, str):
        raise AdapterError("photo style_contract_version is required")
    style_sha, references = _validated_approval_context(request, style_version, project_root)
    items, concept = _approved_decomposition_items(project_root, slide_id, references)
    mode = request.get("photo_output_mode")
    treatment = request.get("treatment")
    if mode == "rectangle":
        role = "ordinary-photo"
        if treatment not in {"preserve-source", "photo-adjust"}:
            raise AdapterError("rectangle photo treatment must preserve-source or photo-adjust")
    elif mode == "cutout":
        role = "photo-cutout"
        if treatment != "photo-adjust":
            raise AdapterError("transparent photo cutout requires an explicit photo-adjust decision")
    else:
        raise AdapterError("photo_output_mode must be rectangle or cutout")
    bbox = validate_reference_bbox(request.get("reference_bbox"), "photo reference_bbox")
    matched = [
        item for item in items if isinstance(item, dict)
        and item.get("kind") == "visual" and item.get("component_id") == component_id
    ]
    if not matched or any(
        item.get("role") != role or item.get("source_class") != "ordinary-photo"
        or item.get("treatment") != treatment or item.get("contains_ordinary_text_or_data") is not False
        for item in matched
    ) or not any(item.get("bbox") == bbox for item in matched):
        raise AdapterError("photo request does not match one approved ordinary-photo decomposition item")
    source = request["source_photo"]
    if treatment == "preserve-source":
        output = source["path"]
        output_sha = source["sha256"]
        strategy = "preserved-photo-rectangle"
        status = "needs-isolation-review"
    else:
        output = f"assets/{slide_id}/{component_id}-photo-v1.png"
        output_sha = None
        strategy = "postprocessed-photo-rectangle" if mode == "rectangle" else "postprocessed-transparent-png"
        status = "planned"
    return {
        "id": component_id, "slide_id": slide_id, "role": role,
        "page_role": request["page_role"], "provider_id": provider["id"],
        "adapter_id": provider["adapter"], "style_contract_version": style_version,
        "style_contract_sha256": style_sha, "source_kind": "ordinary-photo",
        "truth_sensitive": False, "deliverable_role": "slide-asset",
        "source_rights_confirmation": request["source_rights_confirmation"],
        "source_photo": source, "photo_output_mode": mode,
        "strategy": strategy, "editability": "component-editable",
        "content_policy": "preserve-source-photo", "contains_text": False,
        "contains_data": False, "contains_data_encoding_marks": False,
        "background_requirement": "opaque-rectangle" if mode == "rectangle" else "transparent",
        "output_class": "opaque-photo-rectangle" if mode == "rectangle" else "transparent-photo-cutout",
        "provider_transparency_behavior": provider["transparency_behavior"],
        "provider_aspect_ratio_behavior": provider["aspect_ratio_behavior"],
        "reference_bbox": bbox,
        "references": [references[concept]],
        "output": output, "sha256": output_sha, "alpha": None,
        "extraction": {"route": treatment}, "isolation_review": None,
        "photo_processing": None, "photo_review": None,
        "status": status,
        "next_action": "render-isolation-review" if treatment == "preserve-source" else "diagnose-photo-then-confirm-generation",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("adapt", "adapt-photo", "route"), default="adapt")
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--style-contract", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        registry = load_registry(args.registry)
        request = json.loads(args.request.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise AdapterError("request must be a JSON object")
        if args.mode == "route":
            if args.style_contract is None:
                raise AdapterError("--style-contract is required in route mode")
            style_contract = json.loads(
                args.style_contract.read_text(encoding="utf-8")
            )
            result = route_provider(
                registry, request, style_contract, project_root=args.project_root
            )
        else:
            if args.project_root is None:
                raise AdapterError("--project-root is required in adapt mode")
            result = adapt_photo_plan(registry, request, args.project_root) if args.mode == "adapt-photo" else adapt_plan(registry, request, args.project_root)
        rendered = json.dumps(
            result, ensure_ascii=False, indent=2, allow_nan=False
        ) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
    except (
        AdapterError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        TypeError,
    ) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
