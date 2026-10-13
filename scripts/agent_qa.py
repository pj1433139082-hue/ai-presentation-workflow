"""Validate recorded local agent inspection without approving human QA or G5."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops

from deck_qa_evidence import contact_sheet, overlay, side_by_side
from review_policy import LOCAL_REVIEW_MODE, local_authorized

PAGE_CHECKS = {
    "independent_objects", "geometry", "hierarchy", "color_and_z", "content_truth",
    "visual_relationships", "readability_full_size", "main_image_space", "editability",
}
DECK_CHECKS = {"reference_transfer", "composition_richness", "readability_full_size", "visual_coherence", "truth_consistency"}


def evidence_file(root: Path, record: object, expected_path: str) -> Path:
    if not isinstance(record, dict) or record.get("path") != expected_path:
        raise ValueError("agent QA evidence path is missing or from another packet")
    path = (root / expected_path).resolve()
    if not path.is_relative_to(root) or not path.is_file() or record.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError("agent QA evidence hash is stale or unsafe")
    return path


def review_identity(row: object, checks: set[str]) -> None:
    if not isinstance(row, dict) or not isinstance(row.get("reviewer"), str) or not row["reviewer"].strip():
        raise ValueError("agent QA requires an actual reviewer")
    try:
        stamp = datetime.fromisoformat(row.get("reviewed_at", ""))
        if stamp.utcoffset() is None:
            raise ValueError("timezone missing")
    except (TypeError, ValueError) as exc:
        raise ValueError("agent QA reviewed_at must be timezone-aware ISO-8601") from exc
    inspected = row.get("checks_performed")
    if not isinstance(inspected, list) or len(inspected) != len(checks) or any(not isinstance(check, str) for check in inspected) or set(inspected) != checks:
        raise ValueError("agent QA must record every required inspection exactly once")


def review_findings(root: Path, row: dict, allowed_evidence: set[str], slide_ids: set[str]) -> bool:
    findings = row.get("findings")
    if not isinstance(findings, list):
        raise ValueError("agent QA findings must be a list, including an empty list when clear")
    has_p1 = False
    for finding in findings:
        if not isinstance(finding, dict) or finding.get("severity") not in {"P0", "P1", "P2"}:
            raise ValueError("agent QA findings require P0/P1/P2 severity")
        if finding.get("slide_id") not in slide_ids or not isinstance(finding.get("description"), str) or not finding["description"].strip():
            raise ValueError("agent QA finding needs its slide and concrete description")
        if finding.get("owner_stage") not in {"concept", "inventory", "assets", "assembly", "qa"} or not isinstance(finding.get("repair_entry"), str) or not finding["repair_entry"].strip():
            raise ValueError("agent QA finding needs an owning stage and repair entry")
        attempts = finding.get("repair_attempts")
        if type(attempts) is not int or not 0 <= attempts <= 3:
            raise ValueError("agent QA repair_attempts must be 0..3")
        evidence = finding.get("evidence")
        if not isinstance(evidence, dict) or evidence.get("path") not in allowed_evidence:
            raise ValueError("agent QA finding must bind current reviewed evidence")
        evidence_file(root, evidence, evidence["path"])
        if finding["severity"] == "P0":
            raise ValueError("P0 agent QA finding blocks draft delivery")
        has_p1 |= finding["severity"] == "P1"
    return has_p1


def validate_agent_qa(validator) -> str:
    """Require a complete current recorded inspection; return pass or issues."""
    root = validator.root
    state = validator.docs["run-state.json"]
    if not local_authorized(state):
        raise ValueError("pending formal QA requires user-authorized local production")
    report = json.loads((root / "agent-qa-report.json").read_text(encoding="utf-8"))
    prepared = json.loads((root / "qa-report.json").read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not isinstance(prepared, dict):
        raise ValueError("agent QA and prepared QA must be objects")
    if prepared.get("status") != "pending-human":
        raise ValueError("local agent QA requires a prepared pending-human QA packet")
    if type(report.get("schema_version")) is not int or report["schema_version"] != 1 or report.get("review_mode") != LOCAL_REVIEW_MODE or report.get("review_state") != "complete" or report.get("actor", "agent") != "agent":
        raise ValueError("a complete separate agent QA record is required")
    assembly = validator.docs["assembly-map.json"]
    version = prepared.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", version) or report.get("qa_version") != version:
        raise ValueError("agent QA must identify the current prepared QA version")
    if report.get("pptx_sha256") != assembly["sha256"] or prepared.get("subject_sha256") != assembly["sha256"]:
        raise ValueError("agent QA PPTX binding is stale")
    deck = validator.docs["deck-spec.json"]["slides"]
    rows, prepared_rows = report.get("slides"), prepared.get("slides")
    ids = [slide["id"] for slide in deck]
    if not isinstance(rows, list) or not isinstance(prepared_rows, list) or any(not isinstance(row, dict) for row in rows + prepared_rows) or [row.get("slide_id") for row in rows] != ids or [row.get("slide_id") for row in prepared_rows] != ids:
        raise ValueError("agent QA must review every slide exactly once in deck order")
    renders, assembled = assembly.get("renders", []), assembly["slides"]
    if len(renders) != len(ids) or len(assembled) != len(ids):
        raise ValueError("agent QA requires every actual assembly render")
    thumbnails = []
    all_evidence: set[str] = set()
    has_p1 = False
    try:
        for slide, output, render, row, prepared_row in zip(deck, assembled, renders, rows, prepared_rows):
            review_identity(row, PAGE_CHECKS)
            bindings = validator.qa_slide_bindings(slide, output, render)
            if row.get("bindings") != bindings or prepared_row.get("bindings") != bindings:
                raise ValueError("agent QA slide binding is stale")
            if row.get("evidence") != prepared_row.get("evidence"):
                raise ValueError("agent QA evidence differs from its prepared packet")
            base = f"reviews/qa/{version}/{slide['id']}"
            evidence = row.get("evidence", {})
            side = evidence_file(root, evidence.get("side_by_side"), f"{base}-side-by-side.png")
            blend = evidence_file(root, evidence.get("overlay"), f"{base}-overlay.png")
            packet = evidence_file(root, evidence.get("packet"), f"{base}-review.md")
            allowed = {slide["concept_path"], render["path"], *(p.relative_to(root).as_posix() for p in (side, blend, packet))}
            has_p1 |= review_findings(root, row, allowed, {slide["id"]})
            all_evidence.update(allowed)
            with Image.open(root / slide["concept_path"]) as concept, Image.open(root / render["path"]) as actual, Image.open(side) as comparison, Image.open(blend) as overlay_image:
                expected_side, expected_blend = side_by_side(concept, actual), overlay(concept, actual)
                if comparison.size != expected_side.size or ImageChops.difference(comparison.convert("RGB"), expected_side).getbbox():
                    raise ValueError("agent QA side-by-side pixels are stale")
                if overlay_image.size != expected_blend.size or ImageChops.difference(overlay_image.convert("RGB"), expected_blend).getbbox():
                    raise ValueError("agent QA overlay pixels are stale")
                thumbnails.append((slide["id"], actual.copy()))
        contact_relative = f"reviews/qa/{version}/final-contact-sheet.png"
        contact = evidence_file(root, report.get("contact_sheet"), contact_relative)
        if prepared.get("final_contact_sheet") != contact_relative or prepared.get("contact_sheet_sha256") != report["contact_sheet"]["sha256"]:
            raise ValueError("agent QA contact sheet differs from its prepared packet")
        with Image.open(contact) as actual_contact:
            expected_contact = contact_sheet(thumbnails)
            if actual_contact.size != expected_contact.size or ImageChops.difference(actual_contact.convert("RGB"), expected_contact).getbbox():
                raise ValueError("agent QA contact sheet pixels differ from current renders in deck order")
        whole = report.get("whole_deck_review")
        review_identity(whole, DECK_CHECKS)
        if whole.get("contact_sheet_sha256") != report["contact_sheet"]["sha256"]:
            raise ValueError("agent QA whole-deck review is stale")
        deck_bindings = validator.qa_deck_bindings(report["contact_sheet"]["sha256"])
        if whole.get("bindings") != deck_bindings or prepared.get("deck_bindings") != deck_bindings:
            raise ValueError("agent QA whole-deck bindings are stale against current references, story, style, deck, or PPTX")
        if validator.quality_profile() == "production":
            verified = prepared.get("verified_renders")
            if not isinstance(verified, list) or len(verified) != len(renders):
                raise ValueError("production agent QA requires independent current PowerPoint render evidence")
            for record, render in zip(verified, renders):
                if not isinstance(record, dict) or record.get("pptx_sha256") != assembly["sha256"] or record.get("path") != f"reviews/qa/{version}/verified-renders/{Path(render['path']).name}":
                    raise ValueError("independent production render binding is invalid")
                verified_path = evidence_file(root, record, record["path"])
                with Image.open(verified_path) as checked, Image.open(root / render["path"]) as rendered:
                    if checked.size != rendered.size or ImageChops.difference(checked.convert("RGB"), rendered.convert("RGB")).getbbox():
                        raise ValueError("independent production render pixels are stale")
        has_p1 |= review_findings(root, whole, all_evidence | {contact_relative}, set(ids))
        outcome = "issues" if has_p1 else "pass"
        if report.get("outcome") != outcome:
            raise ValueError("agent QA outcome must honestly reflect its P1 findings")
        validator.docs["agent-qa-report.json"] = report
        validator.docs["qa-report.json"] = prepared
        return outcome
    finally:
        for _, pixels in thumbnails:
            pixels.close()
