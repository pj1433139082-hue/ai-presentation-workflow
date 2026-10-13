"""Validation helpers for concept, transparent-asset, and assembly deliveries.

The mode selector is intentionally separate from ``project-kind.json``. Older
showcase projects without ``delivery-mode.json`` retain the complete assembly
route. New projects can opt into a lighter concept or asset delivery without
creating placeholder scene graphs or PPTX files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import showcase_contract as _showcase
    import reconstruction_contract as _reconstruction
except ImportError:  # import when loaded as scripts.delivery_modes
    from . import showcase_contract as _showcase
    from . import reconstruction_contract as _reconstruction


DELIVERY_MODE_FILE = "delivery-mode.json"
ASSET_MANIFEST_FILE = "asset-manifest.json"
ASSET_CONTRACT_VERSION = "showcase-assets-v1"
DELIVERY_MODES = ("concept", "assets", "assembly")
MODE_STAGES = {
    "concept": ("concept", "export"),
    "assets": ("concept", "assets", "export"),
    "assembly": ("concept", "assets", "assembly", "qa", "export"),
}


def read_delivery_mode(root: Path) -> str:
    """Read the project's selected mode; absent settings preserve legacy assembly."""
    root = Path(root)
    path = root / DELIVERY_MODE_FILE
    if not path.exists() and not path.is_symlink():
        return "assembly"
    if not path.is_file():
        raise ValueError(f"{DELIVERY_MODE_FILE}: selector exists but is not a regular file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{DELIVERY_MODE_FILE}: cannot read valid UTF-8 JSON ({exc})") from exc
    if not isinstance(value, dict) or set(value) != {"mode"}:
        raise ValueError(f"{DELIVERY_MODE_FILE}: must contain exactly one field, 'mode'")
    mode = value.get("mode")
    if not isinstance(mode, str) or mode not in DELIVERY_MODES:
        raise ValueError(f"{DELIVERY_MODE_FILE}.mode: expected one of {', '.join(DELIVERY_MODES)}")
    return mode


def _report(stage: str, mode: str | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "errors": [],
        "warnings": [],
        "stage": stage,
        "facts": {"delivery_mode": mode} if mode else {},
    }


def _load_contract_json(root: Path, name: str, errors: list[str]) -> dict[str, Any] | None:
    loader = getattr(_showcase, "_load_json", None)
    if not callable(loader):
        errors.append("showcase_contract._load_json: required shared loader is unavailable")
        return None
    return loader(root, name, errors)


def _keyed_rows(rows: Any, key: str, location: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    helper = getattr(_showcase, "_keyed_rows", None)
    if not callable(helper):
        errors.append("showcase_contract._keyed_rows: required shared validator is unavailable")
        return {}
    return helper(rows, key, location, errors)


def _asset_file(root: Path, row: dict[str, Any], errors: list[str], location: str) -> Path | None:
    checker = getattr(_showcase, "_digest_matches", None)
    if not callable(checker):
        errors.append("showcase_contract._digest_matches: required shared hash checker is unavailable")
        return None
    return checker(root, row.get("path"), row.get("sha256"), errors, f"{location}.path")


def _validate_assets(root: Path, errors: list[str], facts: dict[str, Any]) -> None:
    """Validate delivered assets without claiming complete visual decomposition."""
    manifest = _load_contract_json(root, ASSET_MANIFEST_FILE, errors)
    deck = _load_contract_json(root, "deck-spec.json", errors)
    brief = _load_contract_json(root, "brief.json", errors)
    if manifest is None or deck is None or brief is None:
        return

    if manifest.get("contract_version") != ASSET_CONTRACT_VERSION:
        errors.append(f"{ASSET_MANIFEST_FILE}.contract_version: must be {ASSET_CONTRACT_VERSION!r} for assets delivery")
    reject_fixtures = getattr(_showcase, "_reject_fixtures", None)
    reject_human_gates = getattr(_showcase, "_reject_human_gate_claims", None)
    if callable(reject_fixtures):
        reject_fixtures(manifest, ASSET_MANIFEST_FILE, errors)
    else:
        errors.append("showcase_contract._reject_fixtures: required shared fixture checker is unavailable")
    if callable(reject_human_gates):
        reject_human_gates(manifest, ASSET_MANIFEST_FILE, errors)
    else:
        errors.append("showcase_contract._reject_human_gate_claims: required shared gate checker is unavailable")
    _reject_asset_approval_status(manifest, ASSET_MANIFEST_FILE, errors)

    deck_slides = _keyed_rows(deck.get("slides"), "id", "deck-spec.json.slides", errors)
    source_rows = _keyed_rows(brief.get("source_map"), "id", "brief.json.source_map", errors)
    asset_rows = _keyed_rows(manifest.get("assets"), "id", f"{ASSET_MANIFEST_FILE}.assets", errors)
    coverage_rows = _keyed_rows(manifest.get("coverage"), "slide_id", f"{ASSET_MANIFEST_FILE}.coverage", errors)

    if not deck_slides:
        errors.append("deck-spec.json.slides: at least one slide is required")
    if set(coverage_rows) != set(deck_slides):
        errors.append(f"{ASSET_MANIFEST_FILE}.coverage: every deck slide must have exactly one coverage record")

    image_types = getattr(_showcase, "IMAGE_TYPES", {"picture", "source-evidence"})
    truth_states = getattr(_showcase, "TRUTH_STATES", {"verified", "illustrative", "hypothetical", "pending", "not-applicable"})
    safe_file = getattr(_showcase, "_safe_file", None)
    is_png = getattr(_showcase, "_is_png", None)
    has_real_alpha = getattr(_showcase, "_has_real_alpha", None)
    is_supported_image = getattr(_showcase, "_is_supported_image", None)
    if not all(callable(value) for value in (safe_file, is_png, has_real_alpha, is_supported_image)):
        errors.append("showcase_contract: shared image/path validators are unavailable")
        return

    assets_by_slide: dict[str, set[str]] = {slide_id: set() for slide_id in deck_slides}
    for asset_id, asset in asset_rows.items():
        where = f"{ASSET_MANIFEST_FILE}.assets[{asset_id}]"
        slide_id = asset.get("slide_id")
        if not isinstance(slide_id, str) or slide_id not in deck_slides:
            errors.append(f"{where}.slide_id: must identify a current deck slide")
        else:
            assets_by_slide[slide_id].add(asset_id)
        if not isinstance(asset.get("kind"), str) or asset["kind"] not in image_types:
            errors.append(f"{where}.kind: image assets must be picture or source-evidence")
        if not isinstance(asset.get("truth_status"), str) or asset["truth_status"] not in truth_states:
            errors.append(f"{where}.truth_status: unsupported truth status")
        if not isinstance(asset.get("source_locator"), str) or not asset["source_locator"].strip():
            errors.append(f"{where}.source_locator: provenance locator is required")

        media = _asset_file(root, asset, errors, where)
        requires_transparency = asset.get("requires_transparency", True)
        if not isinstance(requires_transparency, bool):
            errors.append(f"{where}.requires_transparency: boolean required when present")
            requires_transparency = True
        if media is not None and not is_supported_image(media):
            errors.append(f"{where}.path: asset must be a readable supported image")
        if not requires_transparency:
            if not isinstance(asset.get("opaque_reason"), str) or not asset["opaque_reason"].strip():
                errors.append(f"{where}.opaque_reason: non-empty explanation is required for an intentionally opaque asset")
        elif media is not None and (not is_png(media) or not has_real_alpha(media)):
            errors.append(f"{where}.path: requires_transparency needs a PNG with real transparent pixels")

        source_id = asset.get("source_id")
        if source_id is not None and (not isinstance(source_id, str) or source_id not in source_rows):
            errors.append(f"{where}.source_id: must identify a current brief.source_map record")
        if asset.get("truth_status") == "verified":
            source = source_rows.get(source_id) if isinstance(source_id, str) else None
            if source is None:
                errors.append(f"{where}.source_id: verified evidence must reference a brief.source_map record")
            else:
                if source.get("truth_status") != "verified":
                    errors.append(f"{where}.source_id: source_map record must also be verified")
                if asset.get("source_locator") != source.get("locator"):
                    errors.append(f"{where}.source_locator: must match its brief.source_map locator")
        else:
            generation = asset.get("generation")
            if not isinstance(generation, dict):
                errors.append(f"{where}.generation: generation provenance object is required")
                continue
            for field in ("method", "prompt"):
                if not isinstance(generation.get(field), str) or not generation[field].strip():
                    errors.append(f"{where}.generation.{field}: non-empty string required")
            concept_path = generation.get("source_concept_path")
            concept_hash = generation.get("source_concept_sha256")
            slide = deck_slides.get(slide_id, {})
            if concept_path != slide.get("concept_path"):
                errors.append(f"{where}.generation.source_concept_path: must match this slide's current deck concept")
            concept_check = getattr(_showcase, "_digest_matches", None)
            if callable(concept_check):
                concept_check(root, concept_path, concept_hash, errors, f"{where}.generation.source_concept_path")
            for field in ("record_path", "record_sha256"):
                if not isinstance(generation.get(field), str) or not generation[field].strip():
                    errors.append(f"{where}.generation.{field}: non-empty generation record binding is required")
            if isinstance(generation.get("record_path"), str) and isinstance(generation.get("record_sha256"), str):
                if callable(concept_check):
                    concept_check(root, generation["record_path"], generation["record_sha256"], errors, f"{where}.generation.record_path")

    for slide_id, coverage in coverage_rows.items():
        where = f"{ASSET_MANIFEST_FILE}.coverage[{slide_id}]"
        status = coverage.get("status")
        asset_ids = coverage.get("asset_ids")
        if not isinstance(asset_ids, list) or any(not isinstance(asset_id, str) for asset_id in asset_ids):
            errors.append(f"{where}.asset_ids: list of asset IDs is required")
            asset_ids = []
        elif len(set(asset_ids)) != len(asset_ids):
            errors.append(f"{where}.asset_ids: duplicate asset IDs are not allowed")
        if set(asset_ids) != assets_by_slide.get(slide_id, set()):
            errors.append(f"{where}.asset_ids: must exactly cover the current assets assigned to this slide")
        if status == "complete":
            if not asset_ids:
                errors.append(f"{where}: complete coverage requires at least one asset")
            if "no_assets_reason" in coverage:
                errors.append(f"{where}.no_assets_reason: only valid when status is no-assets")
        elif status == "no-assets":
            if asset_ids:
                errors.append(f"{where}: no-assets coverage cannot list assets")
            if not isinstance(coverage.get("no_assets_reason"), str) or not coverage["no_assets_reason"].strip():
                errors.append(f"{where}.no_assets_reason: explanation is required")
        else:
            errors.append(f"{where}.status: must be complete or no-assets")

    facts["asset_ids"] = list(asset_rows)
    facts["slide_ids"] = list(deck_slides)
    facts["asset_status"] = "ready" if asset_rows else "no-assets"
    facts["asset_coverage_scope"] = "manifest-declared assets per slide; not a full visual decomposition"
    facts["asset_review"] = "not-claimed"
    facts["visual_acceptance"] = "not-claimed"

    delivery = brief.get("delivery")
    asset_scope = delivery.get("asset_scope") if isinstance(delivery, dict) else None
    if asset_scope == "full-slide" or "reconstruction" in manifest:
        _reconstruction.validate_full_slide_reconstruction(root, brief, deck, manifest, errors, facts)


def _reject_asset_approval_status(value: Any, location: str, errors: list[str]) -> None:
    """Disallow approval-like status fields while allowing coverage='complete'."""
    forbidden = {"approved", "accepted", "passed", "released"}
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() == "status" and isinstance(child, str) and child.lower() in forbidden:
                errors.append(f"{location}.{key}: asset delivery cannot claim human review or approval")
            _reject_asset_approval_status(child, f"{location}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_asset_approval_status(child, f"{location}[{index}]", errors)


def _concept_input_report(root: Path) -> dict[str, Any]:
    validator = getattr(_showcase, "validate_concept_inputs", None)
    if not callable(validator):
        return {
            "ok": False,
            "errors": ["showcase_contract.validate_concept_inputs: shared concept-only validator is not available yet"],
            "warnings": [],
            "facts": {},
        }
    return validator(root)


def validate_delivery(root: Path, mode: str | None = None, stage: str | None = None) -> dict[str, Any]:
    """Validate one delivery mode and stage without implying human approval.

    ``ok`` means only that the files required for the selected technical
    contract are internally consistent. It does not mean a package has been
    written, visuals were accepted, or a human gate was approved.
    """
    root = Path(root).resolve()
    try:
        declared_mode = read_delivery_mode(root)
    except ValueError as exc:
        report = _report(stage or "concept")
        report["errors"].append(str(exc))
        return report

    selected_mode = declared_mode if mode is None else mode
    requested_stage = stage or "concept"
    report = _report(requested_stage, selected_mode if isinstance(selected_mode, str) else None)
    if selected_mode not in DELIVERY_MODES:
        report["errors"].append(f"mode: expected one of {', '.join(DELIVERY_MODES)}")
        return report
    if selected_mode != declared_mode:
        report["errors"].append(f"mode: requested {selected_mode!r} does not match {DELIVERY_MODE_FILE} selection {declared_mode!r}")
        return report
    if requested_stage not in MODE_STAGES[selected_mode]:
        report["errors"].append(f"stage: {requested_stage!r} is not available for mode {selected_mode!r}; expected one of {', '.join(MODE_STAGES[selected_mode])}")
        return report
    if not root.is_dir():
        report["errors"].append(f"project: directory does not exist: {root}")
        return report

    has_mode_selector = (root / DELIVERY_MODE_FILE).exists() or (root / DELIVERY_MODE_FILE).is_symlink()
    if selected_mode == "assembly" and not has_mode_selector:
        # Preserve the original four-stage contract for legacy projects.
        contract_stage = "concept" if requested_stage == "assets" else requested_stage
        delegated = _showcase.validate_showcase(root, contract_stage)
        report["errors"].extend(delegated.get("errors", []))
        report["warnings"].extend(delegated.get("warnings", []))
        report["facts"].update(delegated.get("facts", {}))
        report["facts"]["contract_stage"] = contract_stage
        report["facts"]["mode_source"] = "legacy-default"
    elif selected_mode == "assembly" and requested_stage in {"assembly", "qa", "export"}:
        delegated = _showcase.validate_showcase(root, requested_stage)
        report["errors"].extend(delegated.get("errors", []))
        report["warnings"].extend(delegated.get("warnings", []))
        report["facts"].update(delegated.get("facts", {}))
        report["facts"]["contract_stage"] = requested_stage
        report["facts"]["mode_source"] = "project-setting"
    else:
        concepts = _concept_input_report(root)
        report["errors"].extend(concepts.get("errors", []))
        report["warnings"].extend(concepts.get("warnings", []))
        report["facts"].update(concepts.get("facts", {}))
        report["facts"]["mode_source"] = "project-setting" if has_mode_selector else "legacy-default"
        report["facts"]["human_gates"] = "not-claimed"
        report["facts"]["formal_release"] = "not-claimed"
        if (selected_mode == "assets" and requested_stage in {"assets", "export"}) or (selected_mode == "assembly" and requested_stage == "assets"):
            _validate_assets(root, report["errors"], report["facts"])
    report["ok"] = not report["errors"]
    return report
