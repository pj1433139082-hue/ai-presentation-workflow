#!/usr/bin/env python3
"""Validate the public project contract for ai-presentation-workflow."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import posixpath
import re
import sys
import zlib
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


VISUAL_ADAPTER_PATH = Path(__file__).resolve().with_name("visual_adapters.py")
VISUAL_ADAPTER_SPEC = importlib.util.spec_from_file_location(
    "ai_presentation_visual_adapters", VISUAL_ADAPTER_PATH
)
if VISUAL_ADAPTER_SPEC is None or VISUAL_ADAPTER_SPEC.loader is None:
    raise RuntimeError("cannot load visual adapter contract")
VISUAL_ADAPTERS = importlib.util.module_from_spec(VISUAL_ADAPTER_SPEC)
VISUAL_ADAPTER_SPEC.loader.exec_module(VISUAL_ADAPTERS)


STAGES = [
    "intake",
    "research",
    "story",
    "style",
    "spec",
    "concept",
    "inventory",
    "assets",
    "assembly",
    "qa",
    "release",
]

REQUIRED_BY_STAGE = {
    "intake": ["brief.json", "run-state.json"],
    "research": ["research-bundle.json"],
    "story": ["alignment.json", "storyboard.json"],
    "style": [
        "reference-study.json",
        "concept-calibration.json",
        "style-contract.json",
        "capability-report.json",
        "visual-provider-registry.json",
    ],
    "spec": ["deck-spec.json"],
    "concept": ["concept-generation-log.json"],
    "inventory": [
        "scene-graph.json",
        "asset-manifest.json",
        "component-master-manifest.json",
    ],
    "assets": [],
    "assembly": ["assembly-map.json"],
    "qa": ["qa-report.json"],
    "release": [],
}

VISUAL_ROLES = {
    "illustration",
    "photo-cutout",
    "icon",
    "arrow",
    "basic-shape",
    "decorative-shape",
    "panel",
    "table-shell",
    "chart-shell",
    "diagram-node",
    "special-typography",
}

TRUTH_SENSITIVE_ROLES = {
    "source-screenshot",
    "source-figure",
    "equation",
    "brand-mark",
}

GATES = [
    "brief_authority",
    "story",
    "style_anchors",
    "concept_contact_sheet",
    "release",
]

CRITICAL_G1_DECISIONS = {
    "audience",
    "decision_goal",
    "source_authority",
    "truth_boundaries",
    "research_permission",
    "delivery_form",
    "editability_commitment",
}

GATE_REQUIRED_DECISIONS = {
    "story": {
        "slide_sequence",
        "action_titles",
        "slide_messages",
        "evidence_mapping",
        "appendix_boundary",
    },
    "style_anchors": {
        "reference_selection",
        "concept_calibration",
        "composition_profile",
        "readability_profile",
        "visual_direction",
        "style_rules",
        "anchor_opening",
        "anchor_typical",
        "anchor_highest_risk",
    },
    "concept_contact_sheet": {
        "full_deck_contact_sheet",
        "contentful_copy_source_review",
        "readability_review",
        "layout_richness_review",
        "blank_table_chart_regions",
        "special_typography_exceptions",
        "slide_specific_deviations",
    },
    "release": {
        "final_render",
        "concept_differences",
        "qa_exceptions",
        "component_usability",
        "deliverable_index",
    },
}

DEFECT_STAGE_OWNERS = {
    "research": "research",
    "story": "story",
    "style": "style",
    "concept": "concept",
    "inventory": "inventory",
    "asset": "assets",
    "assembly": "assembly",
    "qa": "qa",
}

GATE_ROLLBACK_OWNERS = {
    "brief_authority": "intake",
    "story": "story",
    "style_anchors": "style",
    "concept_contact_sheet": "concept",
    "release": "qa",
}

VAGUE_APPROVAL_PHRASES = {"按推荐", "全部按推荐", "推荐", "同意", "可以", "好的", "ok"}

QUALITY_PROFILES = {"production", "draft", "validation-fixture"}
READABILITY_FONT_FLOORS = {
    "action-title": ("action_title_min_pt", 32),
    "body": ("body_min_pt", 20),
    "key-caption": ("key_caption_min_pt", 18),
    "source-qualifier": ("source_qualifier_min_pt", 16),
}
READABILITY_VISUAL_FLOORS = {
    "evidence_min_width": 0.42,
    "evidence_min_height": 0.43,
    "fine_ui_preferred_width": 0.50,
    "fine_ui_preferred_height": 0.46,
    "illustration_min_width": 0.30,
    "illustration_min_height": 0.25,
}
REFERENCE_OBSERVATION_FIELDS = {
    "composition",
    "hierarchy",
    "density",
    "image_treatment",
}
SPARSE_DEFAULT_ROLES = {"opening", "transition", "closing"}
COPY_SOURCE_MODES = {"storyboard-exact", "source-exact", "approved-paraphrase"}
CONCEPT_IMAGE_CLASSIFICATIONS = {
    "illustrative",
    "verified-source",
    "pending-placeholder",
}
NARRATIVE_ROLES = {
    "opening",
    "context",
    "tension",
    "evidence",
    "mechanism",
    "proposal",
    "decision",
    "next-step",
    "transition",
    "closing",
    "appendix",
}


def value_sha256(value: Any) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def positive_int_or(value: Any, fallback: int) -> int:
    return value if type(value) is int and value > 0 else fallback


class ProjectValidator:
    def __init__(self, root: Path, stage: str) -> None:
        self.root = root
        self.stage = stage
        self.stage_index = STAGES.index(stage)
        self.errors: list[str] = []
        self.docs: dict[str, Any] = {}
        self.visual_registry: dict[str, dict[str, Any]] = {}

    def reaches(self, stage: str) -> bool:
        return self.stage_index >= STAGES.index(stage)

    def quality_profile(self) -> str | None:
        brief = self.docs.get("brief.json")
        if isinstance(brief, dict):
            value = brief.get("quality_profile")
            if isinstance(value, str):
                return value
        return None

    def is_fixture_profile(self) -> bool:
        return self.quality_profile() == "validation-fixture"

    def error(self, location: str, message: str) -> None:
        self.errors.append(f"{location}: {message}")

    def load_required_documents(self) -> None:
        names: list[str] = []
        for stage in STAGES[: self.stage_index + 1]:
            names.extend(REQUIRED_BY_STAGE[stage])
        for name in dict.fromkeys(names):
            if name == "component-master-manifest.json" and self.is_fixture_profile():
                continue
            path = self.root / name
            if not path.is_file():
                self.error(name, "required artifact is missing")
                continue
            try:
                self.docs[name] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                self.error(name, f"cannot read valid UTF-8 JSON ({exc})")

    def require_fields(self, doc_name: str, fields: list[str]) -> None:
        doc = self.docs.get(doc_name)
        if not isinstance(doc, dict):
            return
        for field in fields:
            if field not in doc or doc[field] in (None, "", [], {}):
                self.error(doc_name, f"missing non-empty field '{field}'")

    def validate_brief(self) -> None:
        self.require_fields(
            "brief.json",
            [
                "project_id",
                "audience",
                "goal",
                "quality_profile",
                "delivery",
                "editability",
                "capacity_budget",
            ],
        )
        doc = self.docs.get("brief.json")
        if not isinstance(doc, dict):
            return
        template_placeholders = {
            "project_id": "replace-with-project-id",
            "audience": "replace with the primary audience",
            "goal": "replace with the decision or change this deck should produce",
        }
        for field, placeholder in template_placeholders.items():
            if doc.get(field) == placeholder:
                self.error("brief.json", f"{field} still contains a template placeholder")
        quality_profile = doc.get("quality_profile")
        if quality_profile not in QUALITY_PROFILES:
            self.error(
                "brief.json",
                f"quality_profile must be one of {sorted(QUALITY_PROFILES)}",
            )
        state = self.docs.get("run-state.json", {})
        fixture_only = state.get("fixture_only") if isinstance(state, dict) else None
        if quality_profile == "validation-fixture" and fixture_only is not True:
            self.error(
                "run-state.json",
                "validation-fixture quality_profile requires fixture_only=true",
            )
        if fixture_only is True and quality_profile != "validation-fixture":
            self.error(
                "brief.json",
                "fixture_only=true requires quality_profile='validation-fixture'",
            )
        editability = doc.get("editability")
        if isinstance(editability, dict):
            expected = {
                "ordinary_text": "native-editable",
                "data": "native-editable",
                "visual_components": "component-editable",
            }
            for field, value in expected.items():
                if editability.get(field) != value:
                    self.error("brief.json", f"editability.{field} must be '{value}' for this workflow")
            if not isinstance(editability.get("internal_vector_paths"), bool):
                self.error("brief.json", "editability.internal_vector_paths must be boolean")
            elif editability.get("internal_vector_paths"):
                self.error(
                    "brief.json",
                    "editability.internal_vector_paths must be false for transparent PNG components",
                )
        budget = doc.get("capacity_budget")
        if isinstance(budget, dict):
            for field in ("component_limit", "generation_call_limit", "retry_limit_per_asset"):
                value = budget.get(field)
                if not isinstance(value, int) or value <= 0:
                    self.error("brief.json", f"capacity_budget.{field} must be a positive integer")
            if budget.get("retry_limit_per_asset", 99) > 3:
                self.error("brief.json", "capacity_budget.retry_limit_per_asset cannot exceed 3")
            if "deadline" not in budget:
                self.error("brief.json", "capacity_budget.deadline must be present, using null when open")
            deadline = budget.get("deadline")
            if deadline is not None:
                try:
                    datetime.fromisoformat(str(deadline))
                except ValueError:
                    self.error("brief.json", "capacity_budget.deadline must be ISO-8601 or null")
            if budget.get("fallback_delivery") not in {
                "component-library",
                "pptx",
                "pdf",
                "contact-sheet",
            }:
                self.error("brief.json", "capacity_budget.fallback_delivery is required")

    def validate_research(self) -> None:
        name = "research-bundle.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        mode = doc.get("mode")
        if mode not in {"external", "source-only", "not-required"}:
            self.error(name, "mode must be 'external', 'source-only', or 'not-required'")
        if mode == "external":
            self.require_fields(name, ["query_log", "sources", "claims"])
        elif mode == "source-only":
            self.require_fields(name, ["sources", "claims"])
        elif mode == "not-required" and not doc.get("reason"):
            self.error(name, "not-required mode requires a reason")
        source_ids = {
            source.get("id")
            for source in doc.get("sources", [])
            if isinstance(source, dict) and source.get("id")
        }
        self.check_unique(doc.get("sources", []), "id", f"{name}.sources")
        self.check_unique(doc.get("claims", []), "id", f"{name}.claims")
        for index, claim in enumerate(doc.get("claims", [])):
            if not isinstance(claim, dict):
                self.error(f"{name}.claims[{index}]", "must be an object")
                continue
            refs = claim.get("source_ids", [])
            if not refs:
                self.error(f"{name}.claims[{index}]", "claim requires source_ids")
            for source_id in refs:
                if source_id not in source_ids:
                    self.error(f"{name}.claims[{index}]", f"unknown source_id '{source_id}'")

    def validate_alignment(self) -> None:
        name = "alignment.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        material_review = doc.get("material_review")
        if not isinstance(material_review, dict):
            self.error(name, "material_review must be an object")
        else:
            if material_review.get("status") != "completed":
                self.error(name, "material_review.status must be 'completed'")
            source_material_provided = material_review.get("source_material_provided")
            if not isinstance(source_material_provided, bool):
                self.error(name, "material_review.source_material_provided must be boolean")
            inspected_sources = material_review.get("inspected_sources")
            if not isinstance(inspected_sources, list):
                self.error(name, "material_review.inspected_sources must be a list")
            elif source_material_provided and not inspected_sources:
                self.error(name, "material_review.inspected_sources must list supplied material")
            else:
                for index, source in enumerate(inspected_sources):
                    location = f"{name}.material_review.inspected_sources[{index}]"
                    if not isinstance(source, dict):
                        self.error(location, "must be an object")
                        continue
                    path = self.validate_relative_file(source.get("path"), f"{location}.path")
                    if path and source.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
                        self.error(location, "sha256 is stale or missing")
            if source_material_provided is False and not material_review.get("inspection_notes"):
                self.error(name, "material_review.inspection_notes must explain that no material was supplied")
        decisions = doc.get("decisions")
        if not isinstance(decisions, list):
            self.error(name, "decisions must be a list")
            return
        self.check_unique(decisions, "id", f"{name}.decisions")
        decision_map = {
            decision.get("id"): decision
            for decision in decisions
            if isinstance(decision, dict)
            and isinstance(decision.get("id"), str)
            and decision.get("id")
        }
        discovered_facts = doc.get("discovered_facts")
        discovered_decision_ids: set[str] = set()
        if not isinstance(discovered_facts, list):
            self.error(name, "discovered_facts must be a list")
        else:
            self.check_unique(discovered_facts, "id", f"{name}.discovered_facts")
            for index, fact in enumerate(discovered_facts):
                location = f"{name}.discovered_facts[{index}]"
                if not isinstance(fact, dict):
                    self.error(location, "must be an object")
                    continue
                decision_id = fact.get("decision_id")
                if not isinstance(decision_id, str) or not decision_id:
                    self.error(location, "decision_id must be a non-empty string")
                else:
                    discovered_decision_ids.add(decision_id)
                if "value" not in fact:
                    self.error(location, "value is required")
                if not isinstance(fact.get("source_refs"), list) or not fact.get("source_refs"):
                    self.error(location, "source_refs must be a non-empty list")
        frontier = doc.get("question_frontier")
        frontier_ids: list[str] = []
        if not isinstance(frontier, dict):
            self.error(name, "question_frontier must be an object")
        else:
            raw_frontier_ids = frontier.get("decision_ids")
            if not isinstance(raw_frontier_ids, list):
                self.error(name, "question_frontier.decision_ids must be a list")
            else:
                frontier_ids = [
                    decision_id
                    for decision_id in raw_frontier_ids
                    if isinstance(decision_id, str) and decision_id
                ]
                if len(frontier_ids) != len(raw_frontier_ids):
                    self.error(name, "question_frontier decision IDs must be non-empty strings")
                if len(frontier_ids) != len(set(frontier_ids)):
                    self.error(name, "question_frontier decision IDs must be unique")
                if len(frontier_ids) > 5:
                    self.error(name, "question_frontier cannot contain more than 5 decisions")
                available_frontier = [
                    decision.get("id")
                    for decision in decisions
                    if isinstance(decision, dict)
                    and isinstance(decision.get("id"), str)
                    and decision.get("id") not in discovered_decision_ids
                    and decision.get("status") in {"open", "ambiguous"}
                    and decision.get("independent") is True
                ]
                required_count = min(3, len(available_frontier))
                if len(frontier_ids) < required_count:
                    self.error(
                        name,
                        f"question_frontier must include at least {required_count} available decisions",
                    )
                expected_frontier = available_frontier[:5]
                if frontier_ids != expected_frontier:
                    self.error(
                        name,
                        "question_frontier must match the first up-to-five available decisions in ledger order",
                    )
                for decision_id in frontier_ids:
                    if decision_id in discovered_decision_ids:
                        self.error(
                            name,
                            f"discovered fact '{decision_id}' cannot remain in question_frontier",
                        )
                    decision = decision_map.get(decision_id)
                    if not isinstance(decision, dict):
                        self.error(name, f"question_frontier references unknown decision '{decision_id}'")
                        continue
                    if decision.get("status") not in {"open", "ambiguous"}:
                        self.error(name, f"question_frontier decision '{decision_id}' is not open")
                    if decision.get("independent") is not True:
                        self.error(name, f"question_frontier decision '{decision_id}' must be independent")
                    recommendation = decision.get("recommendation")
                    if not isinstance(recommendation, dict):
                        self.error(name, f"question_frontier decision '{decision_id}' needs a recommendation")
                    else:
                        if not has_meaningful_value(recommendation.get("value")):
                            self.error(name, f"question_frontier decision '{decision_id}' needs a recommended value")
                        for field in ("reason", "impact"):
                            if not recommendation.get(field):
                                self.error(
                                    name,
                                    f"question_frontier decision '{decision_id}' needs recommendation {field}",
                                )
        for decision_id in sorted(CRITICAL_G1_DECISIONS):
            decision = decision_map.get(decision_id)
            location = f"{name}.decisions.{decision_id}"
            if not isinstance(decision, dict):
                self.error(location, f"missing critical decision '{decision_id}'")
                continue
            value = decision.get("value")
            if decision.get("status") != "resolved" or not has_meaningful_value(value):
                self.error(location, f"critical decision '{decision_id}' is not resolved")

    def validate_capability_report(self) -> None:
        name = "capability-report.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        if not doc.get("probed_at"):
            self.error(name, "missing probed_at")
        if self.reaches("concept"):
            image_generation = doc.get("image_generation", {})
            if not isinstance(image_generation, dict) or image_generation.get("status") != "verified":
                self.error(name, "image_generation.status must be 'verified' before concept generation")
        if self.reaches("assets"):
            transparent_output = doc.get("transparent_output", {})
            if not isinstance(transparent_output, dict) or transparent_output.get("status") != "verified":
                self.error(name, "transparent_output.status must be 'verified' before asset generation")
            else:
                sample = self.validate_relative_file(
                    transparent_output.get("sample_path"),
                    f"{name}.transparent_output.sample_path",
                )
                if sample:
                    png_ok, ratio, clear_border, visible = self.inspect_png(sample)
                    if not png_ok or ratio < 0.05 or not clear_border or not visible:
                        self.error(name, "transparent output sample must have real transparent padding and visible content")
        if self.reaches("assembly"):
            brief = self.docs.get("brief.json", {})
            formats = brief.get("delivery", {}).get("formats", []) if isinstance(brief, dict) else []
            assembly = doc.get("assembly", {})
            if "pptx" in formats and (
                not isinstance(assembly, dict) or assembly.get("status") != "verified"
            ):
                self.error(name, "assembly.status must be 'verified' when PPTX is requested")

    def validate_storyboard(self) -> None:
        name = "storyboard.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        slides = doc.get("slides")
        if not isinstance(slides, list) or not slides:
            self.error(name, "slides must be a non-empty list")
            return
        self.check_unique(slides, "id", f"{name}.slides")
        research = self.docs.get("research-bundle.json", {})
        claims = research.get("claims", []) if isinstance(research, dict) else []
        self.check_unique(claims, "id", "research-bundle.json.claims")
        claim_ids = {
            claim.get("id") for claim in claims if isinstance(claim, dict) and claim.get("id")
        }
        for index, slide in enumerate(slides):
            if not isinstance(slide, dict):
                self.error(f"{name}.slides[{index}]", "must be an object")
                continue
            for field in ("id", "title", "message", "narrative_role", "visual_intent"):
                if not slide.get(field):
                    self.error(f"{name}.slides[{index}]", f"missing '{field}'")
            if slide.get("narrative_role") not in NARRATIVE_ROLES:
                self.error(
                    f"{name}.slides[{index}]",
                    f"narrative_role must be one of {sorted(NARRATIVE_ROLES)}",
                )
            policy = slide.get("evidence_policy")
            evidence_ids = slide.get("evidence_ids")
            if policy == "required":
                if not isinstance(evidence_ids, list) or not evidence_ids:
                    self.error(f"{name}.slides[{index}]", "evidence_policy required needs evidence_ids")
            elif policy == "not-applicable":
                if not slide.get("evidence_not_required_reason"):
                    self.error(f"{name}.slides[{index}]", "not-applicable evidence needs a reason")
            else:
                self.error(f"{name}.slides[{index}]", "evidence_policy must be required or not-applicable")
            if isinstance(evidence_ids, list):
                for evidence_id in evidence_ids:
                    if evidence_id not in claim_ids:
                        self.error(f"{name}.slides[{index}]", f"unknown evidence_id '{evidence_id}'")

    def validate_reference_study(self) -> None:
        name = "reference-study.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        profile = self.quality_profile()
        status = doc.get("status")
        if profile == "validation-fixture" and status == "not-required":
            if not doc.get("reason"):
                self.error(name, "not-required fixture study needs a reason")
            return
        if status != "analyzed":
            self.error(name, "status must be 'analyzed' before concept generation")

        contact_sheet = doc.get("reference_contact_sheet")
        if not isinstance(contact_sheet, dict):
            self.error(name, "reference_contact_sheet is required")
        else:
            sheet_path = self.validate_relative_file(
                contact_sheet.get("path"), f"{name}.reference_contact_sheet.path"
            )
            declared_sha = contact_sheet.get("sha256")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", str(declared_sha)):
                self.error(
                    f"{name}.reference_contact_sheet.sha256",
                    "must be a SHA-256 hex digest",
                )
            elif sheet_path and hashlib.sha256(sheet_path.read_bytes()).hexdigest() != str(
                declared_sha
            ).lower():
                self.error(
                    f"{name}.reference_contact_sheet.sha256",
                    "does not match the contact sheet",
                )

        references = doc.get("references")
        minimum = 3 if profile == "production" else 2
        if not isinstance(references, list) or not (minimum <= len(references) <= 6):
            self.error(
                name,
                f"{profile or 'unknown'} reference study requires {minimum}-6 references",
            )
            references = []
        self.check_unique(references, "id", f"{name}.references")
        reference_ids: set[str] = set()
        for index, reference in enumerate(references):
            location = f"{name}.references[{index}]"
            if not isinstance(reference, dict):
                self.error(location, "must be an object")
                continue
            reference_id = reference.get("id")
            if isinstance(reference_id, str) and reference_id:
                reference_ids.add(reference_id)
            for field in ("source_kind", "source_locator", "usage_note"):
                if not has_meaningful_value(reference.get(field)):
                    self.error(location, f"missing non-empty '{field}'")
            if reference.get("status") != "analyzed":
                self.error(location, "status must be 'analyzed'")
            image_path = self.validate_relative_file(
                reference.get("image_path"), f"{location}.image_path"
            )
            declared_sha = reference.get("sha256")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", str(declared_sha)):
                self.error(f"{location}.sha256", "must be a SHA-256 hex digest")
            elif image_path and hashlib.sha256(image_path.read_bytes()).hexdigest() != str(
                declared_sha
            ).lower():
                self.error(f"{location}.sha256", "does not match the reference image")
            observations = reference.get("observations")
            if not isinstance(observations, dict):
                self.error(location, "observations must be an object")
            else:
                for field in REFERENCE_OBSERVATION_FIELDS:
                    if not has_meaningful_value(observations.get(field)):
                        self.error(location, f"observations.{field} must not be empty")
            for field in (
                "transferable_rules",
                "project_translation",
                "do_not_copy",
                "target_slide_roles",
            ):
                value = reference.get(field)
                if not isinstance(value, list) or not value:
                    self.error(location, f"{field} must be a non-empty list")

        selected_ids = doc.get("selected_reference_ids")
        if not isinstance(selected_ids, list) or not selected_ids:
            self.error(name, "selected_reference_ids must be a non-empty list")
            selected_ids = []
        elif any(
            not isinstance(reference_id, str) or reference_id not in reference_ids
            for reference_id in selected_ids
        ):
            self.error(name, "selected_reference_ids contains an unknown reference")

        directions = doc.get("direction_options")
        if not isinstance(directions, list) or not (2 <= len(directions) <= 3):
            self.error(name, "direction_options must contain 2-3 directions")
            directions = []
        self.check_unique(directions, "id", f"{name}.direction_options")
        direction_ids: set[str] = set()
        for index, direction in enumerate(directions):
            location = f"{name}.direction_options[{index}]"
            if not isinstance(direction, dict):
                self.error(location, "must be an object")
                continue
            direction_id = direction.get("id")
            if isinstance(direction_id, str) and direction_id:
                direction_ids.add(direction_id)
            for field in ("name", "structure", "palette", "density", "imagery"):
                if not has_meaningful_value(direction.get(field)):
                    self.error(location, f"missing non-empty '{field}'")
            direction_refs = direction.get("reference_ids")
            if not isinstance(direction_refs, list) or not direction_refs:
                self.error(location, "reference_ids must be a non-empty list")
            elif any(
                not isinstance(reference_id, str) or reference_id not in reference_ids
                for reference_id in direction_refs
            ):
                self.error(location, "reference_ids contains an unknown reference")
            tradeoffs = direction.get("tradeoffs")
            if not isinstance(tradeoffs, list) or not tradeoffs:
                self.error(location, "tradeoffs must be a non-empty list")
        if not isinstance(doc.get("recommended_direction_id"), str) or doc.get(
            "recommended_direction_id"
        ) not in direction_ids:
            self.error(name, "recommended_direction_id must identify a direction option")

    def validate_content_source_lineage(
        self, records: Any, location: str
    ) -> dict[str, dict[str, Any]]:
        if not isinstance(records, list) or not records:
            self.error(location, "source_lineage must contain approved or verified sources")
            return {}
        self.check_unique(records, "id", location)
        sources: dict[str, dict[str, Any]] = {}
        for index, source in enumerate(records):
            source_location = f"{location}[{index}]"
            if not isinstance(source, dict):
                self.error(source_location, "must be an object")
                continue
            source_id = source.get("id")
            kind = source.get("kind")
            if not isinstance(source_id, str) or not source_id.strip():
                self.error(source_location, "id must be a non-empty string")
                continue
            if not isinstance(kind, str) or not kind.strip():
                self.error(source_location, "kind must identify the source authority")
            if source.get("status") not in {"approved", "verified"}:
                self.error(source_location, "status must be approved or verified")
            if not isinstance(source.get("locator"), str) or not source["locator"].strip():
                self.error(source_location, "locator must identify the relevant source passage or region")
            path_value = source.get("path")
            path = self.validate_relative_file(path_value, f"{source_location}.path")
            digest = source.get("sha256")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", str(digest)):
                self.error(source_location, "sha256 must be a SHA-256 hex digest")
            elif path and hashlib.sha256(path.read_bytes()).hexdigest() != str(digest).lower():
                self.error(source_location, "source_lineage sha256 does not match file")
            sources[source_id] = source
        return sources

    def validate_content_copy_map(
        self,
        copy_map: Any,
        sources: dict[str, dict[str, Any]],
        story_slide: Any,
        location: str,
    ) -> set[str]:
        if not isinstance(copy_map, list) or not copy_map:
            self.error(location, "copy_map must contain every visible text item")
            return set()
        self.check_unique(copy_map, "id", location)
        used_sources: set[str] = set()
        copy_by_story_field: dict[str, list[dict[str, Any]]] = {"title": [], "message": []}
        for index, item in enumerate(copy_map):
            item_location = f"{location}[{index}]"
            if not isinstance(item, dict):
                self.error(item_location, "must be an object")
                continue
            if not isinstance(item.get("id"), str) or not item["id"].strip():
                self.error(item_location, "id must be a non-empty string")
            if not isinstance(item.get("role"), str) or not item["role"].strip():
                self.error(item_location, "role must be a non-empty string")
            text_value = item.get("text")
            if not isinstance(text_value, str) or not text_value.strip():
                self.error(item_location, "text must be the exact visible wording")
                text_value = ""
            truth_status = item.get("truth_status")
            if truth_status not in {
                "verified",
                "planned",
                "pending",
                "unverified",
                "not-applicable",
            }:
                self.error(item_location, "truth_status must distinguish verified, planned, pending, or not-applicable copy")
            elif truth_status != "not-applicable" and (
                not isinstance(item.get("status_label"), str)
                or not item["status_label"].strip()
            ):
                self.error(item_location, "factual copy needs a visible status_label")
            story_field = item.get("storyboard_field")
            if story_field is not None:
                if story_field not in {"title", "message"}:
                    self.error(item_location, "storyboard_field must be title or message")
                elif isinstance(story_slide, dict):
                    copy_by_story_field[story_field].append(item)
                    if text_value != story_slide.get(story_field):
                        self.error(
                            item_location,
                            f"storyboard {story_field} must match the approved storyboard exactly",
                        )
            evidence = item.get("sources")
            if not isinstance(evidence, list) or not evidence:
                self.error(item_location, "every copy item needs source IDs, locators, and excerpts")
                continue
            for source_index, reference in enumerate(evidence):
                ref_location = f"{item_location}.sources[{source_index}]"
                if not isinstance(reference, dict):
                    self.error(ref_location, "must be an object")
                    continue
                source_id = reference.get("source_id")
                source = sources.get(source_id) if isinstance(source_id, str) else None
                if not isinstance(source, dict):
                    self.error(ref_location, "source_id must identify a source_lineage record")
                    continue
                used_sources.add(source_id)
                if not isinstance(reference.get("locator"), str) or not reference["locator"].strip():
                    self.error(ref_location, "locator must identify the quoted passage or visual region")
                quote = reference.get("quote")
                if not isinstance(quote, str) or not quote.strip():
                    self.error(ref_location, "quote must preserve the supporting source text")
                    continue
                mode = reference.get("mode")
                if mode not in COPY_SOURCE_MODES:
                    self.error(ref_location, "mode must be storyboard-exact, source-exact, or approved-paraphrase")
                    continue
                if mode == "storyboard-exact":
                    field = item.get("storyboard_field")
                    if (
                        source.get("kind") != "approved-storyboard"
                        or field not in {"title", "message"}
                        or source.get("path") != "storyboard.json"
                        or quote != text_value
                        or not isinstance(story_slide, dict)
                        or quote != story_slide.get(field)
                    ):
                        self.error(ref_location, "storyboard-exact evidence must match the approved storyboard field")
                else:
                    source_path = self.root / str(source.get("path", ""))
                    if mode == "source-exact" and quote != text_value:
                        self.error(ref_location, "source-exact quote must match visible copy")
                    if source_path.is_file():
                        try:
                            source_text = source_path.read_text(encoding="utf-8")
                        except (UnicodeError, OSError):
                            source_text = None
                        if source_text is not None and quote not in source_text:
                            self.error(ref_location, "quoted source text is not present at the recorded source path")
        if isinstance(story_slide, dict):
            for field in ("title", "message"):
                matching = copy_by_story_field[field]
                if len(matching) != 1:
                    self.error(location, f"copy_map must contain exactly one approved storyboard {field}")
        return used_sources

    def validate_concept_image_inventory(
        self,
        records: Any,
        sources: dict[str, dict[str, Any]],
        location: str,
    ) -> set[str]:
        if not isinstance(records, list) or not records:
            self.error(location, "image_inventory must identify representative imagery")
            return set()
        self.check_unique(records, "id", location)
        used_sources: set[str] = set()
        has_representative = False
        for index, visual in enumerate(records):
            visual_location = f"{location}[{index}]"
            if not isinstance(visual, dict):
                self.error(visual_location, "must be an object")
                continue
            if not isinstance(visual.get("id"), str) or not visual["id"].strip():
                self.error(visual_location, "id must be a non-empty string")
            if not isinstance(visual.get("visual_role"), str) or not visual["visual_role"].strip():
                self.error(visual_location, "visual_role must describe the image's role")
            has_representative = has_representative or visual.get("visual_role") == "representative"
            classification = visual.get("classification")
            if classification not in CONCEPT_IMAGE_CLASSIFICATIONS:
                self.error(visual_location, "classification must be illustrative, verified-source, or pending-placeholder")
                continue
            if classification == "illustrative":
                if not isinstance(visual.get("label"), str) or not visual["label"].strip():
                    self.error(visual_location, "illustrative images need an explicit illustrative label")
                if visual.get("evidence_role") != "illustration-only":
                    self.error(visual_location, "illustrative images cannot be presented as evidence")
            elif classification == "pending-placeholder":
                if not isinstance(visual.get("label"), str) or not visual["label"].strip():
                    self.error(visual_location, "pending imagery needs an explicit placeholder label")
                if visual.get("evidence_role") != "placeholder-only":
                    self.error(visual_location, "pending imagery must remain a placeholder")
            else:
                source_id = visual.get("source_id")
                source = sources.get(source_id) if isinstance(source_id, str) else None
                if not isinstance(source, dict) or source.get("kind") not in {
                    "verified-image",
                    "authoritative-image",
                }:
                    self.error(visual_location, "verified-source imagery must link a verified local image source")
                else:
                    used_sources.add(source_id)
                    if visual.get("source_sha256") != source.get("sha256"):
                        self.error(visual_location, "verified-source image hash must match source_lineage")
                    if visual.get("preservation") != "unchanged":
                        self.error(visual_location, "verified-source imagery must be preserved unchanged")
        if not has_representative:
            self.error(location, "image_inventory needs a representative visual")
        return used_sources

    def validate_content_text_review(
        self,
        review: Any,
        copy_map: Any,
        output_path: str | None,
        output_sha256: str | None,
        location: str,
    ) -> set[str]:
        if not isinstance(review, dict):
            self.error(location, "text_review must link exact text to a reviewed transcript")
            return set()
        if review.get("method") not in {"human-transcription", "ocr-transcript-reviewed"}:
            self.error(location, "method must identify a human-checked transcript")
        expected_copy_hash = value_sha256(copy_map)
        if review.get("copy_map_sha256") != expected_copy_hash:
            self.error(location, "copy_map_sha256 does not match the exact visible copy")
        transcript_path_value = review.get("transcript_path")
        transcript_path = self.validate_relative_file(
            transcript_path_value, f"{location}.transcript_path"
        )
        transcript_hash = review.get("transcript_sha256")
        transcript_text: str | None = None
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(transcript_hash)):
            self.error(location, "transcript_sha256 must be a SHA-256 hex digest")
        elif transcript_path:
            actual_hash = hashlib.sha256(transcript_path.read_bytes()).hexdigest()
            if actual_hash != str(transcript_hash).lower():
                self.error(location, "transcript_sha256 does not match transcript evidence")
            try:
                transcript_text = transcript_path.read_text(encoding="utf-8")
            except (UnicodeError, OSError):
                self.error(location, "transcript evidence must be readable UTF-8 text")
        copy_records = {
            item.get("id"): item
            for item in copy_map
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        } if isinstance(copy_map, list) else {}
        observations = review.get("observations")
        if not isinstance(observations, list):
            self.error(location, "observations must transcribe every copy_map item")
            observations = []
        self.check_unique(observations, "copy_id", f"{location}.observations")
        observed_ids: set[str] = set()
        for index, observation in enumerate(observations):
            observation_location = f"{location}.observations[{index}]"
            if not isinstance(observation, dict):
                self.error(observation_location, "must be an object")
                continue
            copy_id = observation.get("copy_id")
            expected = copy_records.get(copy_id)
            observed_text = observation.get("observed_text")
            if not isinstance(expected, dict):
                self.error(observation_location, "copy_id must identify a copy_map item")
                continue
            if observed_text != expected.get("text"):
                self.error(observation_location, "observed_text must exactly match copy_map")
            if isinstance(transcript_text, str) and isinstance(observed_text, str) and observed_text not in transcript_text:
                self.error(observation_location, "observed_text must appear in transcript evidence")
            status_label = expected.get("status_label")
            if status_label is not None:
                if observation.get("observed_status_label") != status_label:
                    self.error(observation_location, "observed_status_label must exactly match copy_map")
                if isinstance(transcript_text, str) and status_label not in transcript_text:
                    self.error(observation_location, "observed_status_label must appear in transcript evidence")
            if isinstance(copy_id, str):
                observed_ids.add(copy_id)
        if observed_ids != set(copy_records):
            self.error(location, "text_review observations must cover every copy_map item")
        evidence_paths = {transcript_path_value} if isinstance(transcript_path_value, str) else set()
        repair = review.get("repair")
        if repair is not None:
            repair_location = f"{location}.repair"
            if not isinstance(repair, dict) or repair.get("kind") != "deterministic-overlay":
                self.error(repair_location, "repair must record deterministic-overlay evidence")
                return evidence_paths
            if not isinstance(repair.get("tool"), str) or not repair["tool"].strip():
                self.error(repair_location, "tool must identify the deterministic overlay method")
            input_value = repair.get("input_path")
            input_path = self.validate_relative_file(input_value, f"{repair_location}.input_path")
            if input_value == output_path:
                self.error(repair_location, "input_path must preserve a prior image version")
            if input_path and hashlib.sha256(input_path.read_bytes()).hexdigest() != repair.get("input_sha256"):
                self.error(repair_location, "input_sha256 does not match preserved prior image")
            if repair.get("output_path") != output_path or repair.get("output_sha256") != output_sha256:
                self.error(repair_location, "overlay output must match the contentful concept image")
            evidence_value = repair.get("evidence_path")
            evidence_path = self.validate_relative_file(evidence_value, f"{repair_location}.evidence_path")
            if isinstance(evidence_value, str):
                evidence_paths.add(evidence_value)
            if evidence_path and hashlib.sha256(evidence_path.read_bytes()).hexdigest() != repair.get("evidence_sha256"):
                self.error(repair_location, "evidence_sha256 does not match overlay evidence")
        return evidence_paths

    def validate_concept_calibration(self) -> None:
        name = "concept-calibration.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        if self.is_fixture_profile() and doc.get("status") == "not-required":
            if not doc.get("reason"):
                self.error(name, "not-required fixture calibration needs a reason")
            return
        if doc.get("status") != "generated":
            self.error(name, "status must be 'generated'")
        storyboard = self.docs.get("storyboard.json", {})
        slides = storyboard.get("slides", []) if isinstance(storyboard, dict) else []
        slide = next(
            (item for item in slides if isinstance(item, dict) and item.get("id") == doc.get("slide_id")),
            None,
        )
        fixed_content = doc.get("fixed_content")
        if not isinstance(fixed_content, dict):
            self.error(name, "fixed_content must be an object")
            fixed_content = {}
        fixed_fill_slots = doc.get("fixed_fill_slots")
        if not isinstance(fixed_fill_slots, list) or not fixed_fill_slots:
            self.error(name, "fixed_fill_slots must list the shared editable blank regions")
        if slide is None:
            self.error(name, "slide_id must identify a storyboard slide")
        else:
            for field in ("title", "message", "evidence_ids", "visual_intent"):
                if fixed_content.get(field) != slide.get(field):
                    self.error(name, f"fixed_content.{field} must match the storyboard")
        study = self.docs.get("reference-study.json", {})
        direction_ids = {
            item.get("id") for item in study.get("direction_options", [])
            if isinstance(item, dict)
        } if isinstance(study, dict) else set()
        references = {
            item.get("id"): item for item in study.get("references", [])
            if isinstance(item, dict)
        } if isinstance(study, dict) else {}
        board = doc.get("contact_sheet")
        if not isinstance(board, dict):
            self.error(name, "contact_sheet is required")
            board = {}
        tracked_paths = [name]
        for location, item in [(f"{name}.contact_sheet", board)]:
            path = self.validate_relative_file(item.get("path"), f"{location}.path")
            if path:
                tracked_paths.append(item["path"])
                if item.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
                    self.error(location, "sha256 does not match file")
        source_records: dict[str, dict[str, Any]] = {}
        copy_map = doc.get("copy_map")
        if self.quality_profile() in {"production", "draft"}:
            source_records = self.validate_content_source_lineage(
                doc.get("source_lineage"), f"{name}.source_lineage"
            )
            self.validate_content_copy_map(
                copy_map, source_records, slide, f"{name}.copy_map"
            )
            for source in source_records.values():
                if isinstance(source.get("path"), str):
                    tracked_paths.append(source["path"])
        variants = doc.get("variants")
        if not isinstance(variants, list) or not 2 <= len(variants) <= 3:
            self.error(name, "variants must contain 2-3 real concept images")
            variants = []
        self.check_unique(variants, "id", f"{name}.variants")
        ids = set()
        comparisons = set()
        for index, variant in enumerate(variants):
            location = f"{name}.variants[{index}]"
            if not isinstance(variant, dict):
                self.error(location, "must be an object")
                continue
            variant_id = variant.get("id")
            if not isinstance(variant_id, str) or not variant_id:
                self.error(location, "id must be a non-empty string")
            else:
                ids.add(variant_id)
            if variant.get("direction_id") not in direction_ids:
                self.error(location, "direction_id must identify a reference-study direction")
            if variant.get("style_strength") not in {"restrained", "balanced", "expressive"}:
                self.error(location, "style_strength is invalid")
            if variant.get("layout_density") not in {"airy", "standard", "dense"}:
                self.error(location, "layout_density is invalid")
            comparisons.add((variant.get("direction_id"), variant.get("style_strength"), variant.get("layout_density")))
            if variant.get("tool") not in {"codex-image_gen", "image_gen"}:
                self.error(location, "tool must identify Codex image_gen")
            prompt = variant.get("prompt")
            if not isinstance(prompt, str) or len(prompt.strip()) < 80:
                self.error(location, "prompt must preserve the exact structured prompt")
            if not isinstance(variant.get("generated_at"), str) or not variant.get("generated_at"):
                self.error(location, "generated_at is required")
            attached = variant.get("reference_images")
            if not isinstance(attached, list) or not attached:
                self.error(location, "reference_images must be a non-empty list")
                attached = []
            for ref_index, ref in enumerate(attached):
                ref_location = f"{location}.reference_images[{ref_index}]"
                if not isinstance(ref, dict) or ref.get("reference_id") not in references:
                    self.error(ref_location, "unknown reference_id")
                    continue
                source = references[ref["reference_id"]]
                if ref.get("path") != source.get("image_path") or ref.get("sha256") != source.get("sha256"):
                    self.error(ref_location, "reference path/hash must match reference-study")
            path = self.validate_relative_file(variant.get("output_path"), f"{location}.output_path")
            if path:
                tracked_paths.append(variant["output_path"])
                if variant.get("output_sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
                    self.error(location, "output_sha256 does not match concept image")
            if self.quality_profile() in {"production", "draft"}:
                self.validate_concept_image_inventory(
                    variant.get("image_inventory"),
                    source_records,
                    f"{location}.image_inventory",
                )
                tracked_paths.extend(
                    self.validate_content_text_review(
                        variant.get("text_review"),
                        copy_map,
                        variant.get("output_path"),
                        variant.get("output_sha256"),
                        f"{location}.text_review",
                    )
                )
        if len(comparisons) < 2:
            self.error(name, "variants must visibly vary direction, strength, or density")
        if doc.get("recommended_variant_id") not in ids:
            self.error(name, "recommended_variant_id must identify a variant")
        recommendation = doc.get("recommendation")
        if not isinstance(recommendation, dict) or not recommendation.get("reason") or not recommendation.get("impact"):
            self.error(name, "recommendation needs reason and impact")
        state = self.docs.get("run-state.json", {})
        gate = state.get("gates", {}).get("style_anchors", {}) if isinstance(state, dict) else {}
        approval = gate.get("calibration_selection") if isinstance(gate, dict) else None
        location = "run-state.json.gates.style_anchors.calibration_selection"
        if not isinstance(approval, dict) or approval.get("status") != "approved":
            self.error(location, "human calibration selection must be approved before anchors")
            return
        if approval.get("selected_variant_id") not in ids:
            self.error(location, "selected_variant_id must identify a generated variant")
        style = self.docs.get("style-contract.json", {})
        if isinstance(style, dict) and approval.get("selected_variant_id") != style.get("selected_calibration_variant_id"):
            self.error(location, "selected variant differs from style-contract")
        for field in ("approver", "approved_at", "artifact_version", "approval_phrase"):
            if not isinstance(approval.get(field), str) or not approval.get(field).strip():
                self.error(location, f"{field} is required")
        try:
            approved_at = approval.get("approved_at")
            parsed_time = datetime.fromisoformat(approved_at) if isinstance(approved_at, str) else None
            if parsed_time is None or parsed_time.utcoffset() is None:
                self.error(location, "approved_at must include timezone offset")
        except ValueError:
            self.error(location, "approved_at must be ISO-8601")
        if approval.get("artifact_version") != doc.get("version"):
            self.error(location, "artifact_version differs from concept-calibration")
        mode = approval.get("approval_mode")
        phrase = approval.get("approval_phrase", "")
        if mode == "explicit":
            if phrase.strip().lower() in VAGUE_APPROVAL_PHRASES:
                self.error(location, "explicit approval cannot use a recommendation shortcut")
        elif mode == "batch-recommendations":
            if (phrase != "全部按推荐" or approval.get("selected_variant_id") != doc.get("recommended_variant_id") or approval.get("recommendations_visible") is not True):
                self.error(location, "batch approval must select the visible recommended variant")
        else:
            self.error(location, "approval_mode must be explicit or batch-recommendations")
        hashes = approval.get("approved_artifacts")
        if not isinstance(hashes, dict) or set(tracked_paths) - set(hashes):
            self.error(location, "approved_artifacts must include calibration, board, and every variant")
        else:
            for path_value in tracked_paths:
                path = self.validate_relative_file(path_value, f"{location}.approved_artifacts")
                if path and hashes.get(path_value) != hashlib.sha256(path.read_bytes()).hexdigest():
                    self.error(location, f"approved artifact hash is stale: {path_value}")

    def validate_readability_profile(self, profile: Any) -> None:
        location = "style-contract.json.readability_profile"
        if not isinstance(profile, dict):
            self.error(location, "readability_profile is required")
            return
        for field, floor in READABILITY_FONT_FLOORS.values():
            value = profile.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < floor:
                self.error(location, f"{field} must be at least {floor} pt")
        for field, floor in READABILITY_VISUAL_FLOORS.items():
            value = profile.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not floor <= value < 1:
                self.error(location, f"{field} must be at least {floor} and less than 1")

    def validate_slide_readability(
        self, slide: dict[str, Any], fill_slots: list[Any], profile: Any, location: str
    ) -> None:
        plan = slide.get("readability")
        review_location = f"{location}.readability"
        if not isinstance(plan, dict):
            self.error(review_location, "readability plan is required")
            return
        if not isinstance(profile, dict):
            return
        slots = {
            slot.get("id"): slot
            for slot in fill_slots
            if isinstance(slot, dict) and isinstance(slot.get("id"), str)
        }
        ordinary_ids = {
            slot_id for slot_id, slot in slots.items()
            if slot.get("kind") in {"ordinary-text", "ordinary-data"}
        }
        regions = plan.get("text_regions")
        if not isinstance(regions, list) or not regions:
            self.error(review_location, "text_regions must cover visible ordinary copy")
            regions = []
        self.check_unique(regions, "fill_slot_id", f"{review_location}.text_regions")
        represented: set[str] = set()
        violations: set[str] = set()
        for index, region in enumerate(regions):
            region_location = f"{review_location}.text_regions[{index}]"
            if not isinstance(region, dict):
                self.error(region_location, "must be an object")
                continue
            slot_id = region.get("fill_slot_id")
            if not isinstance(slot_id, str) or slot_id not in ordinary_ids:
                self.error(region_location, "fill_slot_id must identify an ordinary text/data fill slot")
                continue
            represented.add(slot_id)
            role = region.get("role")
            if role not in READABILITY_FONT_FLOORS:
                self.error(region_location, "role must be action-title, body, key-caption, or source-qualifier")
                continue
            font = region.get("planned_font_pt")
            floor_key, baseline = READABILITY_FONT_FLOORS[role]
            floor = profile.get(floor_key, baseline)
            if isinstance(font, bool) or not isinstance(font, (int, float)) or font <= 0:
                self.error(region_location, "planned_font_pt must be a positive number")
            elif isinstance(floor, (int, float)) and font < floor:
                violations.add(f"font:{slot_id}")
            line_count = region.get("line_count")
            if isinstance(line_count, bool) or not isinstance(line_count, int) or line_count < 1:
                self.error(region_location, "line_count must be a positive integer")
        if represented != ordinary_ids:
            self.error(review_location, f"text_regions must cover ordinary fill slots: {sorted(ordinary_ids - represented)}")
        visual = plan.get("main_visual")
        if not isinstance(visual, dict):
            self.error(review_location, "main_visual is required")
        else:
            kind = visual.get("kind")
            if kind not in {"evidence", "fine-ui", "illustration", "not-applicable"}:
                self.error(review_location, "main_visual.kind is invalid")
            elif kind == "not-applicable":
                if not isinstance(visual.get("reason"), str) or not visual["reason"].strip():
                    self.error(review_location, "not-applicable main_visual needs a reason")
            else:
                bbox = visual.get("bbox")
                self.validate_bbox(bbox, f"{review_location}.main_visual.bbox")
                if isinstance(bbox, list) and len(bbox) == 4 and all(
                    isinstance(value, (int, float)) and not isinstance(value, bool) for value in bbox
                ):
                    if kind in {"evidence", "fine-ui"} and not any(
                        isinstance(slot, dict)
                        and slot.get("kind") == "fixed-evidence"
                        and slot.get("bbox") == bbox
                        for slot in fill_slots
                    ):
                        self.error(review_location, "evidence main_visual bbox must match a fixed-evidence fill slot")
                    if kind == "illustration":
                        width_key, height_key = "illustration_min_width", "illustration_min_height"
                    elif kind == "fine-ui" and visual.get("detail_mode") == "full-interface":
                        width_key, height_key = "fine_ui_preferred_width", "fine_ui_preferred_height"
                    else:
                        width_key, height_key = "evidence_min_width", "evidence_min_height"
                    if kind == "fine-ui" and visual.get("detail_mode") not in {"full-interface", "focus-crop"}:
                        self.error(review_location, "fine-ui detail_mode must be full-interface or focus-crop")
                    width_floor = profile.get(width_key)
                    height_floor = profile.get(height_key)
                    if isinstance(width_floor, (int, float)) and isinstance(height_floor, (int, float)) and (
                        bbox[2] < width_floor or bbox[3] < height_floor
                    ):
                        violations.add("visual:main")
        exception = plan.get("exception")
        if exception is not None:
            if not isinstance(exception, dict):
                self.error(review_location, "exception must be an object or null")
            else:
                declared = exception.get("violations")
                if not isinstance(declared, list) or any(not isinstance(value, str) for value in declared):
                    self.error(review_location, "exception.violations must list exact floor IDs")
                    declared = []
                for field in ("reason", "alternative_viewing_route"):
                    if not isinstance(exception.get(field), str) or not exception[field].strip():
                        self.error(review_location, f"exception.{field} is required")
                if violations - set(declared):
                    self.error(review_location, f"underfloor regions need an explicit exception: {sorted(violations - set(declared))}")
        elif violations:
            self.error(review_location, f"underfloor regions need an explicit exception: {sorted(violations)}")
        if self.reaches("concept"):
            full_review = plan.get("full_size_review")
            full_location = f"{review_location}.full_size_review"
            if not isinstance(full_review, dict):
                self.error(full_location, "full_size_review is required for the current contentful concept")
                return
            if full_review.get("status") != "passed" or full_review.get("display_scale_percent") != 100:
                self.error(full_location, "full_size_review must pass at 100% display scale")
            if not isinstance(full_review.get("reviewer"), str) or not full_review["reviewer"].strip():
                self.error(full_location, "reviewer is required")
            evidence_path = self.validate_relative_file(full_review.get("path"), f"{full_location}.path")
            if evidence_path and full_review.get("sha256") != hashlib.sha256(evidence_path.read_bytes()).hexdigest():
                self.error(full_location, "full_size_review sha256 does not match evidence")
            concept_path_value = slide.get("concept_path")
            concept_path = self.root / concept_path_value if isinstance(concept_path_value, str) else None
            if concept_path and concept_path.is_file() and full_review.get("reviewed_concept_sha256") != hashlib.sha256(concept_path.read_bytes()).hexdigest():
                self.error(full_location, "full_size_review must bind the current contentful concept hash")

    def validate_style(self) -> None:
        self.require_fields(
            "style-contract.json",
            [
                "version",
                "direction",
                "primary_visual_family",
                "palette",
                "rules",
            ],
        )
        doc = self.docs.get("style-contract.json")
        if not isinstance(doc, dict):
            return
        reference_study = self.docs.get("reference-study.json", {})
        if isinstance(reference_study, dict) and reference_study.get("status") == "analyzed":
            if doc.get("selected_reference_ids") != reference_study.get(
                "selected_reference_ids"
            ):
                self.error(
                    "style-contract.json",
                    "selected_reference_ids must match reference-study.json",
                )
        calibration = self.docs.get("concept-calibration.json", {})
        if isinstance(calibration, dict) and calibration.get("status") == "generated":
            variants = calibration.get("variants", [])
            selected_id = doc.get("selected_calibration_variant_id")
            selected = next(
                (item for item in variants if isinstance(item, dict) and item.get("id") == selected_id),
                None,
            ) if isinstance(variants, list) else None
            if not isinstance(selected, dict):
                self.error("style-contract.json", "selected_calibration_variant_id must identify a generated variant")
            else:
                for field in ("direction_id", "style_strength", "layout_density"):
                    style_field = "selected_direction_id" if field == "direction_id" else field
                    if doc.get(style_field) != selected.get(field):
                        self.error("style-contract.json", f"{style_field} must match selected calibration variant")
        profile = self.quality_profile()
        self.validate_readability_profile(doc.get("readability_profile"))
        composition = doc.get("composition_profile")
        if not isinstance(composition, dict):
            self.error("style-contract.json", "composition_profile is required")
            composition = {}
        if composition.get("quality_profile") != profile:
            self.error(
                "style-contract.json",
                "composition_profile.quality_profile must match brief.json",
            )
        if composition.get("visual_richness") not in {
            "restrained",
            "balanced-rich",
            "editorial-rich",
        }:
            self.error(
                "style-contract.json",
                "composition_profile.visual_richness is invalid",
            )
        integer_fields = {
            "layout_archetype_minimum": 1,
            "max_consecutive_same_archetype": 1,
            "min_information_units_per_content_slide": 1,
            "min_visual_layers_per_content_slide": 1,
        }
        for field, minimum in integer_fields.items():
            value = composition.get(field)
            if not isinstance(value, int) or value < minimum:
                self.error(
                    "style-contract.json",
                    f"composition_profile.{field} must be an integer >= {minimum}",
                )
        sparse_roles = composition.get("sparse_allowed_roles")
        if not isinstance(sparse_roles, list) or not sparse_roles:
            self.error(
                "style-contract.json",
                "composition_profile.sparse_allowed_roles must be a non-empty list",
            )
        if profile == "production":
            if doc.get("concept_reference_mode") != "image-and-analysis":
                self.error(
                    "style-contract.json",
                    "production concepts require concept_reference_mode='image-and-analysis'",
                )
            if doc.get("pass_selected_images_to_image_gen") is not True:
                self.error(
                    "style-contract.json",
                    "production concepts must pass selected images to image_gen",
                )
            production_minima = {
                "layout_archetype_minimum": 3,
                "min_information_units_per_content_slide": 3,
                "min_visual_layers_per_content_slide": 2,
            }
            for field, minimum in production_minima.items():
                value = composition.get(field)
                if not isinstance(value, int) or value < minimum:
                    self.error(
                        "style-contract.json",
                        f"production composition_profile.{field} must be >= {minimum}",
                    )
            repeat_limit = composition.get("max_consecutive_same_archetype")
            if not isinstance(repeat_limit, int) or repeat_limit > 2:
                self.error(
                    "style-contract.json",
                    "production max_consecutive_same_archetype must be <= 2",
                )
        try:
            self.visual_registry = VISUAL_ADAPTERS.load_registry(
                self.root / "visual-provider-registry.json"
            )
            VISUAL_ADAPTERS.validate_style_policy(self.visual_registry, doc)
        except (VISUAL_ADAPTERS.AdapterError, OSError, json.JSONDecodeError) as error:
            self.error("visual-provider-registry.json", str(error))
        anchors = doc.get("anchor_concepts")
        required_roles = {"opening", "typical", "highest-risk"}
        if not isinstance(anchors, list) or len(anchors) != 3:
            self.error("style-contract.json", "anchor_concepts must contain exactly three records")
            return
        roles = {anchor.get("role") for anchor in anchors if isinstance(anchor, dict)}
        if roles != required_roles:
            self.error("style-contract.json", f"anchor roles must be {sorted(required_roles)}")
        for index, anchor in enumerate(anchors):
            if not isinstance(anchor, dict) or not anchor.get("slide_id"):
                self.error(f"style-contract.json.anchor_concepts[{index}]", "missing slide_id")
                continue
            if self.reaches("concept"):
                self.validate_relative_file(
                    anchor.get("path"), f"style-contract.json.anchor_concepts[{index}].path"
                )

    def validate_deck(self) -> None:
        name = "deck-spec.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        estimate = doc.get("production_estimate")
        if not isinstance(estimate, dict):
            self.error(name, "production_estimate is required")
        else:
            for field in ("unique_components", "planned_generation_calls", "reserved_retries"):
                value = estimate.get(field)
                if not isinstance(value, int) or value < 0:
                    self.error(name, f"production_estimate.{field} must be a non-negative integer")
            brief = self.docs.get("brief.json", {})
            budget = brief.get("capacity_budget", {}) if isinstance(brief, dict) else {}
            limit = budget.get("component_limit") if isinstance(budget, dict) else None
            if isinstance(limit, int) and estimate.get("unique_components", 0) > limit:
                self.error(name, "production_estimate.unique_components exceeds approved component_limit")
            call_limit = budget.get("generation_call_limit") if isinstance(budget, dict) else None
            planned_calls = estimate.get("planned_generation_calls", 0)
            reserved_retries = estimate.get("reserved_retries", 0)
            if isinstance(call_limit, int) and planned_calls + reserved_retries > call_limit:
                self.error(name, "production estimate exceeds approved generation_call_limit")
            retry_limit = budget.get("retry_limit_per_asset") if isinstance(budget, dict) else None
            unique_components = estimate.get("unique_components", 0)
            if (
                isinstance(retry_limit, int)
                and isinstance(unique_components, int)
                and reserved_retries > unique_components * retry_limit
            ):
                self.error(name, "reserved_retries exceeds retry_limit_per_asset budget")
            deadline = budget.get("deadline") if isinstance(budget, dict) else None
            if deadline is not None:
                estimated_completion = estimate.get("estimated_completion")
                if not estimated_completion:
                    self.error(name, "production_estimate.estimated_completion is required when deadline is set")
                else:
                    try:
                        completion_time = datetime.fromisoformat(str(estimated_completion))
                        deadline_time = datetime.fromisoformat(str(deadline))
                        completion_is_aware = completion_time.utcoffset() is not None
                        deadline_is_aware = deadline_time.utcoffset() is not None
                        if completion_is_aware != deadline_is_aware:
                            self.error(
                                name,
                                "estimated_completion and deadline must use the same timezone-awareness policy",
                            )
                        elif completion_time > deadline_time:
                            self.error(name, "estimated_completion exceeds approved deadline")
                    except (TypeError, ValueError):
                        self.error(name, "estimated_completion must be ISO-8601")
        slides = doc.get("slides")
        if not isinstance(slides, list) or not slides:
            self.error(name, "slides must be a non-empty list")
            return
        self.check_unique(slides, "id", f"{name}.slides")
        style = self.docs.get("style-contract.json", {})
        readability_profile = (
            style.get("readability_profile") if isinstance(style, dict) else None
        )
        composition_profile = (
            style.get("composition_profile", {}) if isinstance(style, dict) else {}
        )
        if not isinstance(composition_profile, dict):
            composition_profile = {}
        selected_reference_values = (
            style.get("selected_reference_ids", []) if isinstance(style, dict) else []
        )
        selected_reference_ids = {
            value for value in selected_reference_values if isinstance(value, str)
        } if isinstance(selected_reference_values, list) else set()
        storyboard = self.docs.get("storyboard.json", {})
        storyboard_slides = storyboard.get("slides", []) if isinstance(storyboard, dict) else []
        narrative_roles = {
            slide.get("id"): slide.get("narrative_role")
            for slide in storyboard_slides
            if isinstance(slide, dict)
        }
        sparse_values = composition_profile.get("sparse_allowed_roles")
        sparse_roles = {
            value for value in sparse_values if isinstance(value, str)
        } if isinstance(sparse_values, list) else SPARSE_DEFAULT_ROLES
        archetypes: list[str] = []
        rich_content_slide_count = 0
        for index, slide in enumerate(slides):
            location = f"{name}.slides[{index}]"
            if not isinstance(slide, dict):
                self.error(location, "must be an object")
                continue
            components = slide.get("components", [])
            if not isinstance(components, list):
                self.error(location, "components must be a list")
            elif any(not isinstance(component, str) or not component for component in components):
                self.error(location, "component IDs must be non-empty strings")
            elif len(components) != len(set(components)):
                self.error(location, "components must contain unique component IDs")
            composition = slide.get("composition")
            if not isinstance(composition, dict):
                self.error(location, "composition is required")
                composition = {}
            archetype = composition.get("layout_archetype")
            if not isinstance(archetype, str) or not archetype:
                self.error(location, "composition.layout_archetype is required")
            else:
                archetypes.append(archetype)
            complexity = composition.get("complexity")
            if complexity not in {"sparse", "standard", "rich"}:
                self.error(
                    location,
                    "composition.complexity must be sparse, standard, or rich",
                )
            information_units = composition.get("information_units")
            if not isinstance(information_units, list):
                self.error(location, "composition.information_units must be a list")
                information_units = []
            self.check_unique(
                information_units, "id", f"{location}.composition.information_units"
            )
            visual_layers = composition.get("visual_layers")
            if not isinstance(visual_layers, list):
                self.error(location, "composition.visual_layers must be a list")
                visual_layers = []
            self.check_unique(
                visual_layers, "id", f"{location}.composition.visual_layers"
            )
            for unit_kind, records in (
                ("information_units", information_units),
                ("visual_layers", visual_layers),
            ):
                for item_index, item in enumerate(records):
                    if not isinstance(item, dict) or not item.get("role"):
                        self.error(
                            f"{location}.composition.{unit_kind}[{item_index}]",
                            "must contain a non-empty role",
                        )
            slide_reference_ids = composition.get("reference_ids")
            if not isinstance(slide_reference_ids, list):
                self.error(location, "composition.reference_ids must be a list")
                slide_reference_ids = []
            if self.quality_profile() in {"production", "draft"} and not slide_reference_ids:
                self.error(location, "production/draft slides require reference_ids")
            if any(
                not isinstance(reference_id, str)
                or reference_id not in selected_reference_ids
                for reference_id in slide_reference_ids
            ):
                self.error(location, "composition.reference_ids contains an unselected reference")
            if index > 0 and self.quality_profile() in {"production", "draft"}:
                if not has_meaningful_value(composition.get("variation_from_previous")):
                    self.error(location, "composition.variation_from_previous is required")
            narrative_role = narrative_roles.get(slide.get("id"))
            if complexity == "sparse" and narrative_role not in sparse_roles:
                self.error(
                    location,
                    "sparse composition is not allowed for this narrative role",
                )
            is_content_slide = narrative_role not in sparse_roles
            if self.quality_profile() == "production" and is_content_slide:
                min_units = positive_int_or(
                    composition_profile.get("min_information_units_per_content_slide"), 3
                )
                min_layers = positive_int_or(
                    composition_profile.get("min_visual_layers_per_content_slide"), 2
                )
                if len(information_units) < min_units:
                    self.error(
                        location,
                        f"content slide requires at least {min_units} information units",
                    )
                if len(visual_layers) < min_layers:
                    self.error(
                        location,
                        f"content slide requires at least {min_layers} visual layers",
                    )
                if complexity == "rich":
                    rich_content_slide_count += 1
            fill_slots = slide.get("fill_slots", [])
            if not isinstance(fill_slots, list):
                self.error(location, "fill_slots must be a list")
                fill_slots = []
            self.check_unique(fill_slots, "id", f"{location}.fill_slots")
            for slot_index, slot in enumerate(fill_slots):
                if not isinstance(slot, dict):
                    self.error(f"{location}.fill_slots[{slot_index}]", "must be an object")
                    continue
                self.validate_bbox(slot.get("bbox"), f"{location}.fill_slots[{slot_index}].bbox")
            self.validate_slide_readability(slide, fill_slots, readability_profile, location)
            if self.reaches("concept"):
                concept_path = slide.get("concept_path")
                if not concept_path:
                    self.error(location, "concept_path is required from concept stage")
                else:
                    self.validate_relative_file(concept_path, f"{location}.concept_path")
        if self.quality_profile() in {"production", "draft"}:
            archetype_minimum = positive_int_or(
                composition_profile.get("layout_archetype_minimum"), 1
            )
            required_archetypes = min(archetype_minimum, len(slides))
            if len(set(archetypes)) < required_archetypes:
                self.error(
                    name,
                    f"deck requires at least {required_archetypes} layout archetypes",
                )
            repeat_limit = positive_int_or(
                composition_profile.get("max_consecutive_same_archetype"), len(slides)
            )
            run_length = 0
            previous: str | None = None
            for archetype in archetypes:
                run_length = run_length + 1 if archetype == previous else 1
                previous = archetype
                if run_length > repeat_limit:
                    self.error(
                        name,
                        "layout archetype repeats more often than composition_profile allows",
                    )
                    break
        if (
            self.quality_profile() == "production"
            and len(slides) >= 5
            and composition_profile.get("visual_richness") != "restrained"
            and rich_content_slide_count == 0
        ):
            self.error(name, "production deck needs at least one rich content slide")

    def validate_concept_generation_log(self) -> None:
        name = "concept-generation-log.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        if self.is_fixture_profile() and doc.get("status") == "not-required":
            if not doc.get("reason"):
                self.error(name, "not-required fixture log needs a reason")
            return
        if doc.get("status") != "generated":
            self.error(name, "status must be 'generated'")
        if self.quality_profile() in {"production", "draft"}:
            for artifact_name, artifact in self.docs.items():
                if not isinstance(artifact, dict):
                    continue
                baseline = artifact.get("current_style_rebaseline")
                if isinstance(baseline, dict) and baseline.get("status") == "pending_user_selection":
                    self.error(
                        f"{artifact_name}.current_style_rebaseline",
                        "style rebaseline is pending user selection; concepts cannot proceed on the old G3 approval",
                    )
            if not isinstance(doc.get("version"), str) or not doc["version"].strip():
                self.error(name, "version must identify the contentful concept set")
            contact_sheet = doc.get("review_contact_sheet")
            if not isinstance(contact_sheet, dict):
                self.error(name, "review_contact_sheet must bind the contentful contact sheet")
            else:
                contact_path = self.validate_relative_file(
                    contact_sheet.get("path"), f"{name}.review_contact_sheet.path"
                )
                if not re.fullmatch(r"[0-9a-fA-F]{64}", str(contact_sheet.get("sha256"))):
                    self.error(name, "review_contact_sheet.sha256 must be a SHA-256 hex digest")
                elif contact_path and hashlib.sha256(contact_path.read_bytes()).hexdigest() != str(
                    contact_sheet["sha256"]
                ).lower():
                    self.error(name, "review_contact_sheet hash does not match file")
        records = doc.get("slides")
        if not isinstance(records, list) or not records:
            self.error(name, "slides must be a non-empty list")
            return
        self.check_unique(records, "slide_id", f"{name}.slides")
        records_by_slide = {
            record.get("slide_id"): record
            for record in records
            if isinstance(record, dict) and record.get("slide_id")
        }
        deck = self.docs.get("deck-spec.json", {})
        deck_slides = deck.get("slides", []) if isinstance(deck, dict) else []
        expected_slide_ids = {
            slide.get("id") for slide in deck_slides if isinstance(slide, dict)
        }
        if set(records_by_slide) != expected_slide_ids:
            self.error(name, "slide coverage must match deck-spec.json")
        reference_study = self.docs.get("reference-study.json", {})
        reference_records = (
            reference_study.get("references", [])
            if isinstance(reference_study, dict)
            else []
        )
        reference_by_id = {
            reference.get("id"): reference
            for reference in reference_records
            if isinstance(reference, dict) and reference.get("id")
        }
        style = self.docs.get("style-contract.json", {})
        storyboard = self.docs.get("storyboard.json", {})
        storyboard_slides = {
            item.get("id"): item
            for item in storyboard.get("slides", [])
            if isinstance(item, dict) and item.get("id")
        } if isinstance(storyboard, dict) else {}
        output_paths: set[str] = set()
        for index, slide in enumerate(deck_slides):
            if not isinstance(slide, dict):
                continue
            slide_id = slide.get("id")
            record = records_by_slide.get(slide_id)
            location = f"{name}.slides[{index}]"
            if not isinstance(record, dict):
                continue
            if record.get("tool") not in {"codex-image_gen", "image_gen"}:
                self.error(location, "tool must identify Codex image_gen")
            prompt = record.get("prompt")
            if not isinstance(prompt, str) or len(prompt.strip()) < 80:
                self.error(location, "prompt must preserve the exact structured prompt")
            if record.get("status") not in {"generated", "approved"}:
                self.error(location, "status must be generated or approved")
            if isinstance(style, dict):
                for field in ("selected_calibration_variant_id", "style_strength", "layout_density"):
                    if record.get(field) != style.get(field):
                        self.error(location, f"{field} must match approved style-contract")
            expected_output = slide.get("concept_path")
            if record.get("output_path") != expected_output:
                self.error(location, "output_path must match deck-spec concept_path")
            if self.quality_profile() in {"production", "draft"}:
                version = record.get("version")
                if not isinstance(version, str) or not version.strip():
                    self.error(location, "version must identify this immutable contentful concept revision")
                if record.get("output_path") in output_paths:
                    self.error(location, "contentful concept output paths must be unique by slide revision")
                if isinstance(record.get("output_path"), str):
                    output_paths.add(record["output_path"])
            output_path = self.validate_relative_file(
                record.get("output_path"), f"{location}.output_path"
            )
            output_sha = record.get("output_sha256")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", str(output_sha)):
                self.error(location, "output_sha256 must be a SHA-256 hex digest")
            elif output_path and hashlib.sha256(output_path.read_bytes()).hexdigest() != str(
                output_sha
            ).lower():
                self.error(location, "output_sha256 does not match the concept file")
            if self.quality_profile() in {"production", "draft"}:
                source_records = self.validate_content_source_lineage(
                    record.get("source_lineage"), f"{location}.source_lineage"
                )
                copy_map = record.get("copy_map")
                self.validate_content_copy_map(
                    copy_map,
                    source_records,
                    storyboard_slides.get(slide_id),
                    f"{location}.copy_map",
                )
                self.validate_concept_image_inventory(
                    record.get("image_inventory"),
                    source_records,
                    f"{location}.image_inventory",
                )
                self.validate_content_text_review(
                    record.get("text_review"),
                    copy_map,
                    record.get("output_path"),
                    record.get("output_sha256"),
                    f"{location}.text_review",
                )
            expected_reference_ids = set(
                slide.get("composition", {}).get("reference_ids", [])
                if isinstance(slide.get("composition"), dict)
                else []
            )
            attached = record.get("reference_images")
            if not isinstance(attached, list) or not attached:
                self.error(location, "reference_images must be a non-empty list")
                attached = []
            attached_ids = {
                item.get("reference_id")
                for item in attached
                if isinstance(item, dict) and item.get("reference_id")
            }
            if attached_ids != expected_reference_ids:
                self.error(
                    location,
                    "attached reference IDs must match deck-spec composition.reference_ids",
                )
            for item_index, item in enumerate(attached):
                item_location = f"{location}.reference_images[{item_index}]"
                if not isinstance(item, dict):
                    self.error(item_location, "must be an object")
                    continue
                source = reference_by_id.get(item.get("reference_id"))
                if not isinstance(source, dict):
                    self.error(item_location, "unknown reference_id")
                    continue
                if item.get("path") != source.get("image_path"):
                    self.error(item_location, "path must match reference-study image_path")
                if str(item.get("sha256", "")).lower() != str(
                    source.get("sha256", "")
                ).lower():
                    self.error(item_location, "sha256 must match reference-study")

    def validate_component_master_manifest(self) -> None:
        name = "component-master-manifest.json"
        if self.is_fixture_profile():
            return
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            self.error(name, "is required before inventory can begin")
            return
        if doc.get("status") != "generated":
            self.error(name, "status must be generated after G4 approval")
        state = self.docs.get("run-state.json", {})
        gates = state.get("gates", {}) if isinstance(state, dict) else {}
        g4 = gates.get("concept_contact_sheet", {}) if isinstance(gates, dict) else {}
        if not isinstance(g4, dict) or g4.get("status") != "approved":
            self.error(name, "G4 contentful concept approval is required before component masters")
        approved_artifacts = g4.get("approved_artifacts", {}) if isinstance(g4, dict) else {}
        concept_log = self.docs.get("concept-generation-log.json", {})
        if not isinstance(concept_log, dict):
            self.error(name, "concept-generation-log.json must be present before component masters")
            concept_log = {}
        log_path = self.root / "concept-generation-log.json"
        log_sha256 = hashlib.sha256(log_path.read_bytes()).hexdigest() if log_path.is_file() else None
        if not isinstance(approved_artifacts, dict) or approved_artifacts.get(
            "concept-generation-log.json"
        ) != log_sha256:
            self.error(name, "component masters must link the current G4-approved concept-generation-log.json")
        deck = self.docs.get("deck-spec.json", {})
        slides = deck.get("slides", []) if isinstance(deck, dict) else []
        master_records = doc.get("slides")
        if not isinstance(master_records, list) or not master_records:
            self.error(name, "slides must contain one textless master per deck slide")
            return
        self.check_unique(master_records, "slide_id", f"{name}.slides")
        concepts_by_slide = {
            record.get("slide_id"): record
            for record in concept_log.get("slides", [])
            if isinstance(record, dict) and record.get("slide_id")
        } if isinstance(concept_log.get("slides"), list) else {}
        masters_by_slide = {
            record.get("slide_id"): record
            for record in master_records
            if isinstance(record, dict) and record.get("slide_id")
        }
        expected_ids = {slide.get("id") for slide in slides if isinstance(slide, dict)}
        if set(masters_by_slide) != expected_ids:
            self.error(name, "slide coverage must match deck-spec.json exactly")
        for index, slide in enumerate(slides):
            if not isinstance(slide, dict):
                continue
            slide_id = slide.get("id")
            record = masters_by_slide.get(slide_id)
            location = f"{name}.slides[{index}]"
            if not isinstance(record, dict):
                continue
            concept = concepts_by_slide.get(slide_id)
            if not isinstance(concept, dict):
                self.error(location, "must link an existing contentful concept record")
                continue
            concept_path = slide.get("concept_path")
            concept_sha256 = concept.get("output_sha256")
            approved_concept_sha256 = (
                approved_artifacts.get(concept_path)
                if isinstance(approved_artifacts, dict) and isinstance(concept_path, str)
                else None
            )
            if record.get("approved_contentful_path") != concept_path:
                self.error(location, "approved_contentful_path must match deck-spec concept_path")
            if record.get("approved_contentful_sha256") != concept_sha256:
                self.error(location, "approved_contentful_sha256 must match the contentful concept log")
            if record.get("approved_contentful_sha256") != approved_concept_sha256:
                self.error(location, "contentful concept hash is not approved by G4")
            if record.get("concept_generation_log_sha256") != log_sha256:
                self.error(location, "concept_generation_log_sha256 must match the current G4-approved log")
            if record.get("version") != concept.get("version"):
                self.error(location, "version must match the approved contentful concept")
            master_path_value = record.get("component_master_path")
            if master_path_value == concept_path:
                self.error(location, "component master cannot reuse the contentful full-slide image")
            master_path = self.validate_relative_file(
                master_path_value, f"{location}.component_master_path"
            )
            master_hash = record.get("component_master_sha256")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", str(master_hash)):
                self.error(location, "component_master_sha256 must be a SHA-256 hex digest")
            elif master_path and hashlib.sha256(master_path.read_bytes()).hexdigest() != str(
                master_hash
            ).lower():
                self.error(location, "component_master_sha256 does not match file")
            if record.get("text_policy") != "textless":
                self.error(location, "text_policy must be textless")
            if record.get("ordinary_text_removed") is not True:
                self.error(location, "ordinary_text_removed must be true")
            if record.get("contains_ordinary_text") is not False:
                self.error(location, "contains_ordinary_text must be false")
            expected_slots = [
                {"id": slot.get("id"), "kind": slot.get("kind"), "bbox": slot.get("bbox")}
                for slot in slide.get("fill_slots", [])
                if isinstance(slot, dict)
            ]
            preserved_slots = record.get("preserved_fill_slots")
            if preserved_slots != expected_slots:
                self.error(location, "preserved_fill_slots must preserve deck-spec geometry exactly")
            geometry_review = record.get("geometry_review")
            review_location = f"{location}.geometry_review"
            if not isinstance(geometry_review, dict):
                self.error(review_location, "geometry_review is required before component inventory")
                continue
            if geometry_review.get("status") != "passed" or geometry_review.get("display_scale_percent") != 100:
                self.error(review_location, "geometry_review must pass at 100% display scale")
            if not isinstance(geometry_review.get("reviewer"), str) or not geometry_review["reviewer"].strip():
                self.error(review_location, "geometry_review reviewer is required")
            comparison_value = geometry_review.get("comparison_path")
            if comparison_value in (concept_path, master_path_value):
                self.error(review_location, "geometry_review comparison_path must be a separate comparison image")
            comparison_path = self.validate_relative_file(comparison_value, f"{review_location}.comparison_path")
            if comparison_path and geometry_review.get("comparison_sha256") != hashlib.sha256(comparison_path.read_bytes()).hexdigest():
                self.error(review_location, "geometry_review comparison_sha256 does not match evidence")
            if (
                geometry_review.get("reviewed_contentful_sha256") != concept_sha256
                or geometry_review.get("reviewed_master_sha256") != master_hash
            ):
                self.error(review_location, "geometry_review must bind the current contentful and master images")
            checks = geometry_review.get("checks")
            if not isinstance(checks, dict) or any(
                checks.get(field) is not True
                for field in ("composition_preserved", "fill_slots_preserved", "ordinary_text_removed")
            ):
                self.error(review_location, "geometry_review checks must confirm composition, fill slots and text removal")

    def validate_scene_graph(self) -> None:
        name = "scene-graph.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        slides = doc.get("slides")
        if not isinstance(slides, list) or not slides:
            self.error(name, "slides must be a non-empty list")
            return
        self.check_unique(slides, "slide_id", f"{name}.slides")
        seen_instances: set[str] = set()
        for slide_index, slide in enumerate(slides):
            if not isinstance(slide, dict):
                self.error(f"{name}.slides[{slide_index}]", "must be an object")
                continue
            for element_index, element in enumerate(slide.get("elements", [])):
                location = f"{name}.slides[{slide_index}].elements[{element_index}]"
                if not isinstance(element, dict):
                    self.error(location, "must be an object")
                    continue
                component_id = element.get("component_id")
                if not isinstance(component_id, str) or not component_id:
                    self.error(location, "component_id must be a non-empty string")
                instance_id = element.get("instance_id")
                if not isinstance(instance_id, str) or not instance_id:
                    self.error(location, "instance_id must be a non-empty string")
                elif instance_id in seen_instances:
                    self.error(location, f"duplicate instance_id '{instance_id}'")
                else:
                    seen_instances.add(instance_id)
                self.validate_bbox(element.get("bbox"), f"{location}.bbox")

    def validate_visual_provider_provenance(
        self,
        asset: dict[str, Any],
        location: str,
        style: Any,
        style_gate: Any,
        concept_gate: Any,
        style_sha256: str | None,
    ) -> None:
        provider_id = asset.get("provider_id")
        provider = (
            self.visual_registry.get(provider_id)
            if isinstance(provider_id, str)
            else None
        )
        if provider is None:
            self.error(location, f"unknown visual provider: {provider_id!r}")
        else:
            role = asset.get("role")
            if role not in provider.get("supported_component_roles", []):
                self.error(
                    location,
                    f"provider '{provider_id}' does not support component role '{role}'",
                )
            if asset.get("output_class") != provider.get("output_class"):
                self.error(location, "output_class does not match registered provider")
            if asset.get("provider_transparency_behavior") != provider.get(
                "transparency_behavior"
            ):
                self.error(
                    location,
                    "provider_transparency_behavior does not match registered provider",
                )
            if asset.get("provider_aspect_ratio_behavior") != provider.get(
                "aspect_ratio_behavior"
            ):
                self.error(
                    location,
                    "provider_aspect_ratio_behavior does not match registered provider",
                )
            if asset.get("adapter_id") != provider.get("adapter"):
                self.error(location, "adapter_id does not match registered provider")
            try:
                VISUAL_ADAPTERS.route_provider(
                    self.visual_registry,
                    {
                        "provider_id": provider_id,
                        "page_role": asset.get("page_role"),
                        "source_kind": asset.get("source_kind"),
                        "truth_sensitive": asset.get("truth_sensitive"),
                        "deliverable_role": asset.get("deliverable_role"),
                        "deck_released": self.stage == "release",
                        "slide_id": asset.get("slide_id"),
                        "source_rights_confirmation": asset.get(
                            "source_rights_confirmation"
                        ),
                        "special_page_approval": asset.get(
                            "special_page_approval"
                        ),
                    },
                    style,
                    project_root=self.root,
                )
            except VISUAL_ADAPTERS.AdapterError as error:
                self.error(location, str(error))
            if provider.get("adapter") == "material-illustration-v1":
                try:
                    reference_bbox = VISUAL_ADAPTERS.validate_reference_bbox(
                        asset.get("reference_bbox"), f"{location}.reference_bbox"
                    )
                    expected_prompt = VISUAL_ADAPTERS.build_material_prompt(
                        str(role), reference_bbox
                    )
                    if asset.get("prompt") != expected_prompt:
                        self.error(
                            location,
                            "material prompt does not match the adapter-derived prompt",
                        )
                except VISUAL_ADAPTERS.AdapterError as error:
                    self.error(location, str(error))

        if isinstance(style, dict):
            if asset.get("style_contract_version") != style.get("version"):
                self.error(location, "style_contract_version does not match style contract")
            approved_style_artifacts = (
                style_gate.get("approved_artifacts", {})
                if isinstance(style_gate, dict)
                else {}
            )
            if (
                not isinstance(style_sha256, str)
                or asset.get("style_contract_sha256") != style_sha256
                or not isinstance(approved_style_artifacts, dict)
                or approved_style_artifacts.get("style-contract.json") != style_sha256
            ):
                self.error(location, "style contract SHA-256 is not the approved artifact")

        references = asset.get("references")
        if not isinstance(references, list) or not references:
            self.error(location, "generated visual requires approved references")
            return
        approved_concepts = (
            concept_gate.get("approved_artifacts", {})
            if isinstance(concept_gate, dict)
            else {}
        )
        for reference_index, reference in enumerate(references):
            reference_location = f"{location}.references[{reference_index}]"
            if not isinstance(reference, dict):
                self.error(reference_location, "must be an object")
                continue
            reference_path = reference.get("path")
            resolved_reference = self.validate_relative_file(
                reference_path, f"{reference_location}.path"
            )
            declared_reference_sha = reference.get("sha256")
            if reference.get("approval_gate") != "concept_contact_sheet":
                self.error(
                    reference_location,
                    "approval_gate must be concept_contact_sheet",
                )
            if not re.fullmatch(r"[0-9a-fA-F]{64}", str(declared_reference_sha)):
                self.error(
                    reference_location,
                    "sha256 must be 64 hexadecimal characters",
                )
            elif resolved_reference and resolved_reference.is_file():
                actual_reference_sha = hashlib.sha256(
                    resolved_reference.read_bytes()
                ).hexdigest()
                if declared_reference_sha.lower() != actual_reference_sha:
                    self.error(
                        reference_location,
                        "approved reference SHA-256 does not match file",
                    )
                if (
                    not isinstance(approved_concepts, dict)
                    or approved_concepts.get(reference_path) != actual_reference_sha
                ):
                    self.error(
                        reference_location,
                        "reference is not approved by concept_contact_sheet",
                    )

    def validate_manifest(self) -> None:
        name = "asset-manifest.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        assets = doc.get("assets")
        if not isinstance(assets, list):
            self.error(name, "assets must be a list")
            return
        self.check_unique(assets, "id", f"{name}.assets")
        brief = self.docs.get("brief.json", {})
        budget = brief.get("capacity_budget", {}) if isinstance(brief, dict) else {}
        limit = budget.get("component_limit") if isinstance(budget, dict) else None
        if isinstance(limit, int) and len(assets) > limit:
            self.error(name, "actual asset count exceeds approved component_limit")
        deck = self.docs.get("deck-spec.json", {})
        estimate = deck.get("production_estimate", {}) if isinstance(deck, dict) else {}
        if isinstance(estimate, dict) and estimate.get("unique_components") != len(assets):
            self.error(name, "production_estimate.unique_components must equal manifest asset count")
        generated_assets = [
            asset
            for asset in assets
            if isinstance(asset, dict) and str(asset.get("strategy", "")).startswith("generated-")
        ]
        if isinstance(estimate, dict) and estimate.get("planned_generation_calls", 0) < len(generated_assets):
            self.error(name, "planned_generation_calls is lower than generated asset count")
        actual_calls = 0
        style = self.docs.get("style-contract.json", {})
        run_state = self.docs.get("run-state.json", {})
        gates = run_state.get("gates", {}) if isinstance(run_state, dict) else {}
        style_gate = gates.get("style_anchors", {}) if isinstance(gates, dict) else {}
        concept_gate = (
            gates.get("concept_contact_sheet", {}) if isinstance(gates, dict) else {}
        )
        style_path = self.root / "style-contract.json"
        style_sha256 = (
            hashlib.sha256(style_path.read_bytes()).hexdigest()
            if style_path.is_file()
            else None
        )
        for index, asset in enumerate(assets):
            location = f"{name}.assets[{index}]"
            if not isinstance(asset, dict):
                self.error(location, "must be an object")
                continue
            role = asset.get("role")
            if role in VISUAL_ROLES:
                self.validate_visual_provider_provenance(
                    asset,
                    location,
                    style,
                    style_gate,
                    concept_gate,
                    style_sha256,
                )
            slide_ids = asset.get("slide_ids")
            if slide_ids is None:
                slide_ids = [asset.get("slide_id")] if asset.get("slide_id") else []
            if not isinstance(slide_ids, list) or not slide_ids or any(not value for value in slide_ids):
                self.error(location, "asset requires slide_id or non-empty slide_ids")
            elif len(slide_ids) != len(set(slide_ids)):
                self.error(location, "asset slide_ids must be unique")
            if role in {"ordinary-text", "data-value", "body-copy"}:
                self.error(location, f"'{role}' must be a fill slot, not a generated asset")
            if role not in VISUAL_ROLES | TRUTH_SENSITIVE_ROLES:
                self.error(location, f"unknown or missing visual role '{role}'")
            if role in VISUAL_ROLES:
                if role != "special-typography":
                    if asset.get("contains_text") is not False:
                        self.error(location, "visual asset requires explicit contains_text=false")
                    if asset.get("contains_data") is not False:
                        self.error(location, "visual asset requires explicit contains_data=false")
                    if asset.get("contains_data_encoding_marks") is not False:
                        self.error(
                            location,
                            "visual asset requires explicit contains_data_encoding_marks=false",
                        )
                if asset.get("editability") != "component-editable":
                    self.error(location, f"{role} requires editability 'component-editable'")
                if asset.get("background_requirement") != "transparent":
                    self.error(location, f"{role} must use a transparent background")
                strategy = asset.get("strategy", "")
                if not isinstance(strategy, str) or not strategy.endswith("transparent-png"):
                    self.error(location, f"{role} strategy must end with 'transparent-png'")
                if strategy.startswith("generated-") and self.reaches("assets"):
                    attempts = asset.get("generation_attempts")
                    if not isinstance(attempts, int) or attempts < 1:
                        self.error(location, "generated asset requires positive generation_attempts")
                    else:
                        actual_calls += attempts
                        retry_limit = budget.get("retry_limit_per_asset") if isinstance(budget, dict) else None
                        if isinstance(retry_limit, int) and attempts - 1 > retry_limit:
                            self.error(location, "generation_attempts exceeds retry_limit_per_asset")
            if role in {"table-shell", "chart-shell"}:
                if asset.get("content_policy") != "blank-fill-slots":
                    self.error(location, f"{role} requires content_policy 'blank-fill-slots'")
                if asset.get("contains_text") is not False:
                    self.error(location, f"{role} requires explicit contains_text=false")
                if asset.get("contains_data") is not False:
                    self.error(location, f"{role} requires explicit contains_data=false")
                if asset.get("contains_data_encoding_marks") is not False:
                    self.error(
                        location,
                        f"{role} requires explicit contains_data_encoding_marks=false",
                    )
                fill_slot_ids = asset.get("fill_slot_ids")
                if not isinstance(fill_slot_ids, list) or not fill_slot_ids:
                    self.error(location, f"{role} requires non-empty fill_slot_ids")
                elif any(
                    not isinstance(fill_slot_id, str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", fill_slot_id)
                    for fill_slot_id in fill_slot_ids
                ):
                    self.error(location, f"{role} fill_slot_ids must be safe string ids")
                elif len(set(fill_slot_ids)) != len(fill_slot_ids):
                    self.error(location, f"{role} fill_slot_ids must be unique")
            elif role != "special-typography" and asset.get("contains_text"):
                self.error(location, "ordinary text must remain a fill slot")
            if role == "special-typography":
                if not asset.get("exact_text"):
                    self.error(location, "special-typography requires exact_text")
                if not asset.get("language"):
                    self.error(location, "special-typography requires language")
                ocr_result = asset.get("ocr_result")
                if not isinstance(ocr_result, dict) or ocr_result.get("status") != "passed":
                    self.error(location, "special-typography requires ocr_result.status='passed'")
                elif ocr_result.get("text") != asset.get("exact_text"):
                    self.error(location, "ocr_result.text must exactly match exact_text")
                if self.reaches("release") and asset.get("human_approved") is not True:
                    self.error(location, "special-typography requires human_approved=true before release")
            if role in TRUTH_SENSITIVE_ROLES:
                if asset.get("editability") != "fixed-evidence":
                    self.error(location, f"{role} requires editability 'fixed-evidence'")
                if asset.get("strategy") not in {
                    "preserved-raster",
                    "preserved-vector",
                    "preserved-truth-sensitive",
                }:
                    self.error(location, f"{role} requires a non-generative preservation strategy")
                source_path = self.validate_relative_file(asset.get("source"), f"{location}.source")
                source_sha = asset.get("source_sha256", "")
                if not re.fullmatch(r"[0-9a-fA-F]{64}", str(source_sha)):
                    self.error(location, "source_sha256 must be 64 hexadecimal characters")
                elif source_path and source_path.is_file():
                    actual_source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
                    if actual_source_sha.lower() != str(source_sha).lower():
                        self.error(location, "declared source_sha256 does not match source file")
            else:
                source_path = None
            if self.reaches("assets"):
                required_fields = ["output", "sha256", "status"]
                if role in VISUAL_ROLES:
                    required_fields.extend(["prompt", "alpha"])
                for field in required_fields:
                    if not asset.get(field):
                        self.error(location, f"missing '{field}' from assets stage")
                output = asset.get("output")
                if output:
                    output_path = self.validate_relative_file(output, f"{location}.output")
                else:
                    output_path = None
                sha256 = asset.get("sha256", "")
                if not re.fullmatch(r"[0-9a-fA-F]{64}", str(sha256)):
                    self.error(location, "sha256 must be 64 hexadecimal characters")
                elif output_path and output_path.is_file():
                    actual_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
                    if actual_sha.lower() != str(sha256).lower():
                        self.error(location, "declared SHA-256 does not match the output file")
                if role in VISUAL_ROLES:
                    alpha = asset.get("alpha")
                    if not isinstance(alpha, dict) or alpha.get("has_alpha") is not True:
                        self.error(location, "alpha.has_alpha must be true")
                    if output_path and output_path.is_file():
                        png_ok, ratio, clear_border, visible = self.inspect_png(output_path)
                        if not png_ok:
                            self.error(location, "output must be a valid PNG file")
                        elif ratio < 0.05 or not clear_border or not visible:
                            self.error(location, "PNG must have meaningful transparent padding and visible content")
                        declared_ratio = alpha.get("transparent_pixel_ratio") if isinstance(alpha, dict) else None
                        if not isinstance(declared_ratio, (int, float)):
                            self.error(location, "alpha.transparent_pixel_ratio must be numeric")
                        elif abs(float(declared_ratio) - ratio) > 0.02:
                            self.error(location, "declared transparent_pixel_ratio differs from decoded pixels")
                if self.reaches("release") and asset.get("status") != "approved":
                    self.error(location, "asset status must be 'approved' before release")
                if role in TRUTH_SENSITIVE_ROLES and output_path and source_path:
                    if asset.get("strategy") in {
                        "preserved-raster",
                        "preserved-vector",
                        "preserved-truth-sensitive",
                    } and hashlib.sha256(output_path.read_bytes()).digest() != hashlib.sha256(
                        source_path.read_bytes()
                    ).digest():
                        self.error(location, "preserved output must match its approved source exactly")
        if self.reaches("assets"):
            call_limit = budget.get("generation_call_limit") if isinstance(budget, dict) else None
            if isinstance(call_limit, int) and actual_calls > call_limit:
                self.error(name, "actual generation calls exceed generation_call_limit")
            reserved_retries = estimate.get("reserved_retries", 0) if isinstance(estimate, dict) else 0
            actual_retries = actual_calls - len(generated_assets)
            if self.reaches("release") and actual_retries > reserved_retries:
                self.error(name, "actual retries exceed the approved reserved_retries")

    def validate_assembly(self) -> None:
        name = "assembly-map.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        slides = doc.get("slides")
        if not isinstance(slides, list) or not slides:
            self.error(name, "slides must be a non-empty list")
            return
        self.check_unique(slides, "slide_id", f"{name}.slides")
        output_indices = [slide.get("output_index") for slide in slides if isinstance(slide, dict)]
        expected_indices = list(range(1, len(slides) + 1))
        if any(not isinstance(value, int) for value in output_indices) or sorted(output_indices) != expected_indices:
            self.error(name, "output_index values must be unique and continuous from 1")
        deck = self.docs.get("deck-spec.json", {})
        deck_order = [slide.get("id") for slide in deck.get("slides", []) if isinstance(slide, dict)]
        assembly_order = []
        if all(isinstance(value, int) for value in output_indices):
            assembly_order = [
                slide.get("slide_id")
                for slide in sorted(
                    (slide for slide in slides if isinstance(slide, dict)),
                    key=lambda item: item.get("output_index", 0),
                )
            ]
        if assembly_order != deck_order:
            self.error(name, "output_index order must match deck-spec slide order")
        for index, slide in enumerate(slides):
            if not isinstance(slide, dict):
                self.error(f"{name}.slides[{index}]", "must be an object")
                continue
            if slide.get("flattened_concept_used") is not False:
                self.error(
                    f"{name}.slides[{index}]",
                    "flattened_concept_used must be false; concepts are references only",
                )

        brief = self.docs.get("brief.json", {})
        delivery = brief.get("delivery", {}) if isinstance(brief, dict) else {}
        if "pptx" in delivery.get("formats", []) and not doc.get("backend"):
            self.error(name, "backend is required when PPTX delivery is requested")
        if "pptx" in delivery.get("formats", []):
            pptx_parts = [slide.get("pptx_part") for slide in slides if isinstance(slide, dict)]
            if any(not value for value in pptx_parts) or len(pptx_parts) != len(set(pptx_parts)):
                self.error(name, "each PPTX slide requires a unique pptx_part")
            output_value = doc.get("output")
            if not output_value:
                self.error(name, "PPTX output path is required")
                return
            output_path = self.validate_relative_file(output_value, f"{name}.output")
            if not output_path:
                self.error(name, "PPTX output file is required")
                return
            if output_path.suffix.lower() != ".pptx":
                self.error(name, "PPTX output must use the .pptx extension")
            declared_sha = doc.get("sha256", "")
            actual_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
            if declared_sha != actual_sha:
                self.error(name, "PPTX SHA-256 does not match the output file")
            self.validate_pptx_content(output_path)

    def validate_qa(self) -> None:
        name = "qa-report.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        if doc.get("status") != "passed":
            self.error(name, "status must be 'passed'")
        checks = doc.get("checks_performed")
        if not isinstance(checks, list) or not checks:
            self.error(name, "checks_performed must be a non-empty list")
        elif self.reaches("release"):
            required_checks = {"contract", "alpha", "inventory", "overlay"}
            if self.quality_profile() == "production":
                required_checks.update({"reference-transfer", "composition-richness", "readability-full-size"})
            missing_checks = required_checks - {
                check for check in checks if isinstance(check, str)
            }
            if missing_checks:
                self.error(name, f"checks_performed missing: {sorted(missing_checks)}")
        evidence_files = doc.get("evidence_files")
        if not isinstance(evidence_files, list) or not evidence_files:
            self.error(name, "evidence_files must be a non-empty list")
        else:
            for index, evidence in enumerate(evidence_files):
                self.validate_relative_file(evidence, f"{name}.evidence_files[{index}]")
        if self.reaches("release"):
            for field in ("final_contact_sheet", "exception_register", "deliverable_index"):
                if not doc.get(field):
                    self.error(name, f"{field} is required for release")
                else:
                    self.validate_relative_file(doc.get(field), f"{name}.{field}")
            for field in ("differences", "exceptions"):
                if not isinstance(doc.get(field), list):
                    self.error(name, f"{field} must be a list")
        for index, slide in enumerate(doc.get("slides", [])):
            if isinstance(slide, dict) and slide.get("status") != "passed":
                self.error(f"{name}.slides[{index}]", "slide QA has not passed")
            if isinstance(slide, dict) and not slide.get("evidence_files"):
                self.error(f"{name}.slides[{index}]", "evidence_files must not be empty")
        brief = self.docs.get("brief.json", {})
        formats = brief.get("delivery", {}).get("formats", []) if isinstance(brief, dict) else []
        if "pptx" in formats:
            assembly = self.docs.get("assembly-map.json", {})
            if doc.get("subject_sha256") != assembly.get("sha256"):
                self.error(name, "subject_sha256 must match the assembled PPTX SHA-256")

    def expected_gate_decisions(self, gate: str) -> dict[str, Any]:
        storyboard = self.docs.get("storyboard.json", {})
        style = self.docs.get("style-contract.json", {})
        reference_study = self.docs.get("reference-study.json", {})
        calibration = self.docs.get("concept-calibration.json", {})
        concept_log = self.docs.get("concept-generation-log.json", {})
        deck = self.docs.get("deck-spec.json", {})
        manifest = self.docs.get("asset-manifest.json", {})
        assembly = self.docs.get("assembly-map.json", {})
        qa = self.docs.get("qa-report.json", {})
        if gate == "story" and isinstance(storyboard, dict):
            slides = [slide for slide in storyboard.get("slides", []) if isinstance(slide, dict)]
            return {
                "slide_sequence": [slide.get("id") for slide in slides],
                "action_titles": {slide.get("id"): slide.get("title") for slide in slides},
                "slide_messages": {slide.get("id"): slide.get("message") for slide in slides},
                "evidence_mapping": {
                    slide.get("id"): slide.get("evidence_ids", []) for slide in slides
                },
                "appendix_boundary": {
                    "slide_ids": [
                        slide.get("id")
                        for slide in slides
                        if slide.get("narrative_role") == "appendix"
                    ],
                    "policy": "declared",
                },
            }
        if gate == "style_anchors" and isinstance(style, dict):
            anchors = {
                anchor.get("role"): anchor
                for anchor in style.get("anchor_concepts", [])
                if isinstance(anchor, dict)
            }
            return {
                "reference_selection": {
                    "selected_reference_ids": reference_study.get(
                        "selected_reference_ids", []
                    )
                    if isinstance(reference_study, dict)
                    else [],
                    "reference_contact_sheet": reference_study.get(
                        "reference_contact_sheet"
                    )
                    if isinstance(reference_study, dict)
                    else None,
                },
                "concept_calibration": {
                    "selected_variant_id": style.get("selected_calibration_variant_id"),
                    "selected_direction_id": style.get("selected_direction_id"),
                    "style_strength": style.get("style_strength"),
                    "layout_density": style.get("layout_density"),
                    "calibration_version": calibration.get("version") if isinstance(calibration, dict) else None,
                } if isinstance(calibration, dict) and calibration.get("status") == "generated" else {
                    "status": "not-required",
                    "reason": calibration.get("reason") if isinstance(calibration, dict) else None,
                },
                "composition_profile": style.get("composition_profile"),
                "readability_profile": style.get("readability_profile"),
                "visual_direction": style.get("direction"),
                "style_rules": style.get("rules"),
                "anchor_opening": anchors.get("opening"),
                "anchor_typical": anchors.get("typical"),
                "anchor_highest_risk": anchors.get("highest-risk"),
            }
        if gate == "concept_contact_sheet" and all(
            isinstance(doc, dict) for doc in (deck, manifest, concept_log)
        ):
            slides = [slide for slide in deck.get("slides", []) if isinstance(slide, dict)]
            assets = [asset for asset in manifest.get("assets", []) if isinstance(asset, dict)]
            concept_records = {
                record.get("slide_id"): record
                for record in concept_log.get("slides", [])
                if isinstance(record, dict) and record.get("slide_id")
            } if isinstance(concept_log.get("slides"), list) else {}
            generated_contentful_log = concept_log.get("status") == "generated"
            if generated_contentful_log:
                copy_source_review: dict[str, Any] = {
                    "slides": {
                        slide_id: {
                            "version": record.get("version"),
                            "copy_map_sha256": value_sha256(record.get("copy_map")),
                            "source_lineage": {
                                source.get("id"): source.get("sha256")
                                for source in record.get("source_lineage", [])
                                if isinstance(source, dict) and source.get("id")
                            },
                            "text_review": {
                                "transcript_path": record.get("text_review", {}).get(
                                    "transcript_path"
                                ),
                                "transcript_sha256": record.get("text_review", {}).get(
                                    "transcript_sha256"
                                ),
                            },
                        }
                        for slide_id, record in concept_records.items()
                    }
                }
                contact_sheet_record = concept_log.get("review_contact_sheet")
                contact_path = (
                    self.root / contact_sheet_record["path"]
                    if isinstance(contact_sheet_record, dict)
                    and isinstance(contact_sheet_record.get("path"), str)
                    else None
                )
                full_deck_review = {
                    "concept_paths": [slide.get("concept_path") for slide in slides],
                    "contentful_image_sha256": {
                        slide_id: record.get("output_sha256")
                        for slide_id, record in concept_records.items()
                    },
                    "review_contact_sheet": contact_sheet_record,
                    "concept_generation_log_sha256": hashlib.sha256(
                        (self.root / "concept-generation-log.json").read_bytes()
                    ).hexdigest()
                    if (self.root / "concept-generation-log.json").is_file()
                    else None,
                }
            else:
                copy_source_review = {
                    "status": "not-required",
                    "reason": concept_log.get("reason"),
                }
                full_deck_review = {
                    "concept_paths": [slide.get("concept_path") for slide in slides]
                }
            expected_decisions = {
                "full_deck_contact_sheet": full_deck_review,
                "contentful_copy_source_review": copy_source_review,
                "readability_review": {
                    "policy": "full-size-human-review",
                    "profile": style.get("readability_profile") if isinstance(style, dict) else None,
                    "slides": {
                        slide.get("id"): slide.get("readability")
                        for slide in slides
                    },
                },
                "layout_richness_review": {
                    "slides": {
                        slide.get("id"): {
                            "layout_archetype": slide.get("composition", {}).get(
                                "layout_archetype"
                            ),
                            "complexity": slide.get("composition", {}).get("complexity"),
                            "information_unit_count": len(
                                slide.get("composition", {}).get("information_units", [])
                            ),
                            "visual_layer_count": len(
                                slide.get("composition", {}).get("visual_layers", [])
                            ),
                        }
                        for slide in slides
                        if isinstance(slide.get("composition"), dict)
                    },
                    "policy": "review-rendered-contact-sheet",
                },
                "blank_table_chart_regions": {
                    "fill_slot_ids": [
                        slot.get("id")
                        for slide in slides
                        for slot in slide.get("fill_slots", [])
                        if isinstance(slot, dict)
                        and slot.get("kind") in {"table", "chart", "data"}
                    ],
                    "policy": "blank-fill-slots",
                },
                "special_typography_exceptions": {
                    "asset_ids": [
                        asset.get("id")
                        for asset in assets
                        if asset.get("role") == "special-typography"
                    ],
                    "policy": "explicit-only",
                },
                "slide_specific_deviations": {"items": [], "policy": "declared"},
            }
            return expected_decisions
        if gate == "release" and all(
            isinstance(doc, dict) for doc in (manifest, assembly, qa)
        ):
            assets = [asset for asset in manifest.get("assets", []) if isinstance(asset, dict)]
            assembly_slides = [
                slide for slide in assembly.get("slides", []) if isinstance(slide, dict)
            ]
            return {
                "final_render": {
                    "contact_sheet": qa.get("final_contact_sheet"),
                    "evidence_files": qa.get("evidence_files", []),
                },
                "concept_differences": {"items": qa.get("differences", [])},
                "qa_exceptions": {
                    "items": qa.get("exceptions", []),
                    "register": qa.get("exception_register"),
                },
                "component_usability": {
                    slide.get("slide_id"): {
                        "component_ids": slide.get("component_ids", []),
                        "fill_slot_ids": slide.get("fill_slot_ids", []),
                    }
                    for slide in assembly_slides
                },
                "deliverable_index": {
                    "path": qa.get("deliverable_index"),
                    "asset_outputs": [asset.get("output") for asset in assets],
                },
            }
        return {}

    def validate_state(self) -> None:
        name = "run-state.json"
        doc = self.docs.get(name)
        if not isinstance(doc, dict):
            return
        declared_stage = doc.get("stage")
        if declared_stage not in STAGES and declared_stage != "released":
            self.error(name, f"unknown stage '{declared_stage}'")
        gates = doc.get("gates", {})
        if not isinstance(gates, dict):
            self.error(name, "gates must be an object")
            return
        route = doc.get("production_route")
        if not isinstance(route, dict):
            self.error(name, "production_route must be an object")
        else:
            mode = route.get("mode")
            planning_artifacts = route.get("planning_artifacts")
            if mode == "full-tracked":
                if planning_artifacts != "required":
                    self.error(
                        name,
                        "full-tracked route requires planning_artifacts='required'",
                    )
            elif mode == "fast":
                if planning_artifacts != "skipped":
                    self.error(name, "fast route requires planning_artifacts='skipped'")
                if route.get("approval_phrase") != "确认快速路线":
                    self.error(name, "fast route requires exact approval phrase '确认快速路线'")
                eligibility = route.get("eligibility")
                if not isinstance(eligibility, dict):
                    self.error(name, "fast route eligibility must be an object")
                else:
                    if eligibility.get("consequential_decisions_approved") is not True:
                        self.error(
                            name,
                            "fast route requires all consequential decisions to be approved",
                        )
                    if eligibility.get("high_stakes") is not False:
                        self.error(name, "fast route is forbidden for high-stakes work")
                    if eligibility.get("multi_session") is not False:
                        self.error(name, "fast route is forbidden for multi-session work")
                brief_gate = gates.get("brief_authority")
                if (
                    not isinstance(brief_gate, dict)
                    or brief_gate.get("status") != "approved"
                ):
                    self.error(name, "fast route requires a current G1 approval")
            else:
                self.error(name, f"unknown production_route mode '{mode}'")
        gate_stage = {
            "brief_authority": "story",
            "story": "style",
            "style_anchors": "concept",
            "concept_contact_sheet": "inventory",
            "release": "release",
        }
        deck = self.docs.get("deck-spec.json", {})
        concept_paths = {
            slide.get("concept_path")
            for slide in deck.get("slides", [])
            if isinstance(slide, dict) and slide.get("concept_path")
        } if isinstance(deck, dict) else set()
        style = self.docs.get("style-contract.json", {})
        anchor_paths = {
            anchor.get("path")
            for anchor in style.get("anchor_concepts", [])
            if isinstance(anchor, dict) and anchor.get("path")
        } if isinstance(style, dict) else set()
        required_gate_artifacts = {
            "brief_authority": {"brief.json", "alignment.json", "research-bundle.json"},
            "story": {"storyboard.json"},
            "style_anchors": {
                "reference-study.json",
                "style-contract.json",
                "capability-report.json",
            }
            | anchor_paths,
            "concept_contact_sheet": concept_paths | {"concept-generation-log.json", "deck-spec.json"},
            "release": {"asset-manifest.json", "assembly-map.json", "qa-report.json"},
        }
        concept_log = self.docs.get("concept-generation-log.json", {})
        if isinstance(deck, dict):
            for slide in deck.get("slides", []):
                if not isinstance(slide, dict):
                    continue
                readability = slide.get("readability")
                review = readability.get("full_size_review") if isinstance(readability, dict) else None
                if isinstance(review, dict) and isinstance(review.get("path"), str):
                    required_gate_artifacts["concept_contact_sheet"].add(review["path"])
        if isinstance(concept_log, dict) and concept_log.get("status") == "generated":
            review_contact_sheet = concept_log.get("review_contact_sheet")
            if isinstance(review_contact_sheet, dict):
                contact_path = review_contact_sheet.get("path")
                if isinstance(contact_path, str) and contact_path:
                    required_gate_artifacts["concept_contact_sheet"].add(contact_path)
            for record in concept_log.get("slides", []):
                if not isinstance(record, dict):
                    continue
                for source in record.get("source_lineage", []):
                    if isinstance(source, dict) and isinstance(source.get("path"), str):
                        required_gate_artifacts["concept_contact_sheet"].add(source["path"])
                review = record.get("text_review", {})
                if isinstance(review, dict):
                    for path_field in ("transcript_path",):
                        path_value = review.get(path_field)
                        if isinstance(path_value, str) and path_value:
                            required_gate_artifacts["concept_contact_sheet"].add(path_value)
                    repair = review.get("repair")
                    if isinstance(repair, dict):
                        for path_field in ("input_path", "evidence_path"):
                            path_value = repair.get(path_field)
                            if isinstance(path_value, str) and path_value:
                                required_gate_artifacts["concept_contact_sheet"].add(path_value)
        reference_study = self.docs.get("reference-study.json", {})
        if isinstance(reference_study, dict):
            contact_sheet = reference_study.get("reference_contact_sheet")
            if isinstance(contact_sheet, dict):
                path = contact_sheet.get("path")
                if isinstance(path, str) and path:
                    required_gate_artifacts["style_anchors"].add(path)
        calibration = self.docs.get("concept-calibration.json", {})
        if isinstance(calibration, dict) and calibration.get("status") == "generated":
            required_gate_artifacts["style_anchors"].add("concept-calibration.json")
            board = calibration.get("contact_sheet", {})
            if isinstance(board, dict) and isinstance(board.get("path"), str):
                required_gate_artifacts["style_anchors"].add(board["path"])
            for variant in calibration.get("variants", []):
                if isinstance(variant, dict) and isinstance(variant.get("output_path"), str):
                    required_gate_artifacts["style_anchors"].add(variant["output_path"])
                if isinstance(variant, dict):
                    text_review = variant.get("text_review", {})
                    if isinstance(text_review, dict):
                        for field in ("transcript_path",):
                            path_value = text_review.get(field)
                            if isinstance(path_value, str) and path_value:
                                required_gate_artifacts["style_anchors"].add(path_value)
                        repair = text_review.get("repair")
                        if isinstance(repair, dict):
                            for field in ("input_path", "evidence_path"):
                                path_value = repair.get(field)
                                if isinstance(path_value, str) and path_value:
                                    required_gate_artifacts["style_anchors"].add(path_value)
            for source in calibration.get("source_lineage", []):
                if isinstance(source, dict) and isinstance(source.get("path"), str):
                    required_gate_artifacts["style_anchors"].add(source["path"])
        qa = self.docs.get("qa-report.json", {})
        if isinstance(qa, dict):
            release_paths: set[str] = set()
            for field in ("final_contact_sheet", "exception_register", "deliverable_index"):
                value = qa.get(field)
                if isinstance(value, str) and value:
                    release_paths.add(value)
            evidence_files = qa.get("evidence_files", [])
            if isinstance(evidence_files, list):
                release_paths.update(
                    path for path in evidence_files if isinstance(path, str) and path
                )
            for slide in qa.get("slides", []):
                if not isinstance(slide, dict):
                    continue
                slide_evidence = slide.get("evidence_files", [])
                if isinstance(slide_evidence, list):
                    release_paths.update(
                        path for path in slide_evidence if isinstance(path, str) and path
                    )
            required_gate_artifacts["release"].update(release_paths)
        artifact_versions = doc.get("artifact_versions", {})
        if not isinstance(artifact_versions, dict):
            self.error(name, "artifact_versions must be an object")
            artifact_versions = {}
        for gate in GATES:
            if not self.reaches(gate_stage[gate]):
                continue
            gate_record = gates.get(gate)
            location = f"{name}.gates.{gate}"
            if not isinstance(gate_record, dict):
                self.error(location, "approval must be an object with evidence, not a bare status")
                self.error(location, "missing approver")
                self.error(location, "missing approved_at")
                continue
            if gate_record.get("status") != "approved":
                self.error(location, "status must be 'approved' by this stage")
            approver = gate_record.get("approver")
            if not isinstance(approver, str) or not approver.strip():
                self.error(location, "approver must be a non-empty string")
            approved_at = gate_record.get("approved_at")
            if not isinstance(approved_at, str) or not approved_at.strip():
                self.error(location, "approved_at must be a non-empty ISO-8601 string")
            else:
                try:
                    approval_time = datetime.fromisoformat(approved_at)
                    if approval_time.utcoffset() is None:
                        self.error(location, "approved_at must include a timezone offset")
                except ValueError:
                    self.error(location, "approved_at must be ISO-8601")
            artifact_version = gate_record.get("artifact_version")
            if not isinstance(artifact_version, str) or not artifact_version.strip():
                self.error(location, "artifact_version must be a non-empty string")
            if not isinstance(gate_record.get("approved_artifacts"), dict):
                self.error(location, "approved_artifacts must be an object")
            if gate_record.get("artifact_version") != artifact_versions.get(gate):
                self.error(location, "artifact_version does not match run-state artifact_versions")
            if gate == "brief_authority":
                approval_mode = gate_record.get("approval_mode")
                if approval_mode not in {"explicit", "batch-recommendations"}:
                    self.error(location, "approval_mode must be 'explicit' or 'batch-recommendations'")
                approval_phrase = gate_record.get("approval_phrase")
                if not isinstance(approval_phrase, str) or not approval_phrase.strip():
                    self.error(location, "approval_phrase must be a non-empty string")
                alignment = self.docs.get("alignment.json", {})
                raw_decisions = alignment.get("decisions") if isinstance(alignment, dict) else None
                if not isinstance(raw_decisions, list):
                    self.error(location, "alignment decisions must be a list")
                    decisions: list[Any] = []
                else:
                    decisions = raw_decisions
                decision_map = {
                    decision.get("id"): decision
                    for decision in decisions
                    if isinstance(decision, dict)
                    and isinstance(decision.get("id"), str)
                }
                if approval_mode == "explicit" and isinstance(approval_phrase, str):
                    normalized_phrase = approval_phrase.strip().lower()
                    if normalized_phrase in VAGUE_APPROVAL_PHRASES:
                        self.error(location, "explicit approval cannot use a recommendation shortcut")
                    decision_approvals = gate_record.get("decision_approvals")
                    if not isinstance(decision_approvals, dict):
                        self.error(location, "explicit approval requires per-decision approval evidence")
                    else:
                        if set(decision_approvals) != CRITICAL_G1_DECISIONS:
                            self.error(location, "explicit approval must cover every critical G1 decision")
                        for decision_id in sorted(CRITICAL_G1_DECISIONS):
                            approval = decision_approvals.get(decision_id)
                            decision = decision_map.get(decision_id, {})
                            if not isinstance(approval, dict) or approval.get("status") != "approved":
                                self.error(location, f"missing explicit approval for '{decision_id}'")
                            elif approval.get("value_sha256") != value_sha256(
                                decision.get("value") if isinstance(decision, dict) else None
                            ):
                                self.error(location, f"explicit approval value is stale for '{decision_id}'")
                if approval_mode == "batch-recommendations":
                    if gate_record.get("approval_phrase") != "全部按推荐":
                        self.error(location, "batch approval requires the exact phrase '全部按推荐'")
                    packet = alignment.get("approval_packet", {}) if isinstance(alignment, dict) else {}
                    if not isinstance(packet, dict):
                        self.error(location, "alignment approval_packet must be an object")
                    else:
                        if packet.get("gate") != "brief_authority":
                            self.error(location, "batch approval packet must target brief_authority")
                        if packet.get("version") != gate_record.get("artifact_version"):
                            self.error(location, "batch approval packet version is stale")
                        if packet.get("recommendations_visible") is not True:
                            self.error(location, "batch approval requires all recommendations to be visible")
                        packet_decisions = packet.get("decision_ids")
                        packet_ids_are_valid = (
                            isinstance(packet_decisions, list)
                            and all(
                                isinstance(decision_id, str) and decision_id
                                for decision_id in packet_decisions
                            )
                        )
                        if (
                            not packet_ids_are_valid
                            or set(packet_decisions) != CRITICAL_G1_DECISIONS
                        ):
                            self.error(location, "batch approval packet must cover every critical G1 decision")
                    for decision_id in sorted(CRITICAL_G1_DECISIONS):
                        decision = decision_map.get(decision_id, {})
                        recommendation = decision.get("recommendation", {}) if isinstance(decision, dict) else {}
                        if (
                            decision.get("basis") != "recommended"
                            or not isinstance(recommendation, dict)
                            or recommendation.get("value") != decision.get("value")
                            or not recommendation.get("reason")
                            or not recommendation.get("impact")
                        ):
                            self.error(
                                location,
                                f"batch approval lacks a complete accepted recommendation for '{decision_id}'",
                            )
            elif gate in GATE_REQUIRED_DECISIONS:
                packet = gate_record.get("approval_packet")
                packet_decisions: dict[str, Any] = {}
                if not isinstance(packet, dict):
                    self.error(location, f"{gate} approval_packet must be an object")
                else:
                    if packet.get("gate") != gate:
                        self.error(location, f"approval_packet must target '{gate}'")
                    if packet.get("version") != gate_record.get("artifact_version"):
                        self.error(location, "approval_packet version is stale")
                    raw_packet_decisions = packet.get("decisions")
                    if not isinstance(raw_packet_decisions, dict):
                        self.error(location, "approval_packet.decisions must be an object")
                    else:
                        packet_decisions = raw_packet_decisions
                        required_decisions = GATE_REQUIRED_DECISIONS[gate]
                        if set(packet_decisions) != required_decisions:
                            self.error(
                                location,
                                f"approval_packet must cover: {sorted(required_decisions)}",
                            )
                        for decision_id in sorted(required_decisions):
                            decision = packet_decisions.get(decision_id)
                            if (
                                not isinstance(decision, dict)
                                or decision.get("status") != "approved"
                                or not has_meaningful_value(decision.get("value"))
                            ):
                                self.error(
                                    location,
                                    f"approval_packet decision '{decision_id}' is not approved",
                                )
                            elif decision.get("value_sha256") != value_sha256(
                                decision.get("value")
                            ):
                                self.error(
                                    location,
                                    f"approval value hash is stale for '{decision_id}'",
                                )
                        expected_decisions = self.expected_gate_decisions(gate)
                        for decision_id in sorted(required_decisions):
                            decision = packet_decisions.get(decision_id)
                            if (
                                isinstance(decision, dict)
                                and decision.get("value") != expected_decisions.get(decision_id)
                            ):
                                self.error(
                                    location,
                                    f"approval_packet value differs from current artifacts for '{decision_id}'",
                                )
                approval_mode = gate_record.get("approval_mode")
                approval_phrase = gate_record.get("approval_phrase")
                if not isinstance(approval_phrase, str) or not approval_phrase.strip():
                    self.error(location, "approval_phrase must be a non-empty string")
                if gate == "release":
                    if approval_mode != "release":
                        self.error(location, "release approval_mode must be 'release'")
                    if approval_phrase != "确认发布":
                        self.error(location, "release requires the exact phrase '确认发布'")
                else:
                    if approval_mode not in {"explicit", "batch-recommendations"}:
                        self.error(
                            location,
                            "approval_mode must be 'explicit' or 'batch-recommendations'",
                        )
                    if approval_mode == "explicit" and isinstance(approval_phrase, str):
                        if approval_phrase.strip().lower() in VAGUE_APPROVAL_PHRASES:
                            self.error(
                                location,
                                "explicit approval cannot use a recommendation shortcut",
                            )
                        for decision_id in sorted(GATE_REQUIRED_DECISIONS[gate]):
                            decision = packet_decisions.get(decision_id, {})
                            if isinstance(decision, dict) and decision.get(
                                "value_sha256"
                            ) != value_sha256(decision.get("value")):
                                self.error(
                                    location,
                                    f"explicit approval value is stale for '{decision_id}'",
                                )
                    if approval_mode == "batch-recommendations":
                        if approval_phrase != "全部按推荐":
                            self.error(
                                location,
                                "batch approval requires the exact phrase '全部按推荐'",
                            )
                        if not isinstance(packet, dict) or packet.get(
                            "recommendations_visible"
                        ) is not True:
                            self.error(
                                location,
                                "batch approval requires all recommendations to be visible",
                            )
                        for decision_id in sorted(GATE_REQUIRED_DECISIONS[gate]):
                            decision = packet_decisions.get(decision_id, {})
                            recommendation = (
                                decision.get("recommendation", {})
                                if isinstance(decision, dict)
                                else {}
                            )
                            if (
                                not isinstance(recommendation, dict)
                                or recommendation.get("value") != decision.get("value")
                                or not recommendation.get("reason")
                                or not recommendation.get("impact")
                            ):
                                self.error(
                                    location,
                                    f"batch approval lacks a complete accepted recommendation for '{decision_id}'",
                                )
            approved_artifacts = gate_record.get("approved_artifacts")
            if not isinstance(approved_artifacts, dict):
                continue
            missing = required_gate_artifacts[gate] - set(approved_artifacts)
            if missing:
                self.error(location, f"approved_artifacts missing: {sorted(missing)}")
            for path_value, declared_sha in approved_artifacts.items():
                approved_path = self.validate_relative_file(
                    path_value, f"{location}.approved_artifacts.{path_value}"
                )
                if approved_path:
                    actual_sha = hashlib.sha256(approved_path.read_bytes()).hexdigest()
                    if actual_sha != declared_sha:
                        self.error(location, f"approved artifact hash is stale: {path_value}")
        rejected_gates = {
            gate_name
            for gate_name, gate_record in gates.items()
            if gate_name in GATES
            and isinstance(gate_record, dict)
            and gate_record.get("status") == "rejected"
        }
        qa_state = self.docs.get("qa-report.json")
        if not isinstance(qa_state, dict):
            optional_qa_path = self.root / "qa-report.json"
            if optional_qa_path.is_file():
                try:
                    optional_qa = json.loads(optional_qa_path.read_text(encoding="utf-8"))
                    if isinstance(optional_qa, dict):
                        qa_state = optional_qa
                except (OSError, UnicodeError, json.JSONDecodeError):
                    qa_state = None
        qa_failed = isinstance(qa_state, dict) and (
            qa_state.get("status") == "failed"
            or any(
                isinstance(slide, dict) and slide.get("status") == "failed"
                for slide in qa_state.get("slides", [])
            )
        )
        rollback = doc.get("rollback")
        if rejected_gates and not isinstance(rollback, dict):
            self.error(
                name,
                f"rejected gate requires a rollback record: {sorted(rejected_gates)}",
            )
        if qa_failed and not isinstance(rollback, dict):
            self.error(name, "failed QA requires a rollback record")
        if rollback is not None:
            rollback_location = f"{name}.rollback"
            if not isinstance(rollback, dict):
                self.error(rollback_location, "must be an object or null")
            else:
                trigger = rollback.get("trigger")
                if rejected_gates and trigger != "rejection":
                    self.error(rollback_location, "rejected gates require trigger 'rejection'")
                if qa_failed and not rejected_gates and trigger != "qa-defect":
                    self.error(rollback_location, "failed QA requires trigger 'qa-defect'")
                expected_owner: str | None = None
                if trigger == "qa-defect":
                    defect_class = rollback.get("defect_class")
                    if not isinstance(defect_class, str) or not defect_class:
                        self.error(rollback_location, "defect_class must be a non-empty string")
                    else:
                        expected_owner = DEFECT_STAGE_OWNERS.get(defect_class)
                    if isinstance(defect_class, str) and expected_owner is None:
                        self.error(rollback_location, "unknown defect_class")
                elif trigger == "rejection":
                    source_gate = rollback.get("source_gate")
                    if not isinstance(source_gate, str) or not source_gate:
                        self.error(rollback_location, "source_gate must be a non-empty string")
                    else:
                        expected_owner = GATE_ROLLBACK_OWNERS.get(source_gate)
                    if isinstance(source_gate, str) and expected_owner is None:
                        self.error(rollback_location, "unknown source_gate")
                    if isinstance(source_gate, str) and source_gate not in rejected_gates:
                        self.error(rollback_location, "source_gate status must be 'rejected'")
                    if rejected_gates and rejected_gates != {source_gate}:
                        self.error(
                            rollback_location,
                            "rollback source_gate must match the rejected gate",
                        )
                    source_record = gates.get(source_gate) if isinstance(source_gate, str) else None
                    if isinstance(source_record, dict):
                        retained_epoch = (
                            source_record.get("artifact_version") is not None
                            or bool(source_record.get("approved_artifacts"))
                            or source_record.get("approval_packet") is not None
                            or source_gate in artifact_versions
                        )
                        if retained_epoch:
                            self.error(
                                rollback_location,
                                "rejected gate must clear its prior approval epoch",
                            )
                else:
                    self.error(rollback_location, "trigger must be 'rejection' or 'qa-defect'")
                if not rollback.get("reason"):
                    self.error(rollback_location, "reason is required")
                if expected_owner is not None:
                    if rollback.get("owner_stage") != expected_owner:
                        self.error(
                            rollback_location,
                            f"rollback owner_stage must be '{expected_owner}'",
                        )
                    if declared_stage != expected_owner:
                        self.error(
                            rollback_location,
                            f"run-state stage must be rollback owner '{expected_owner}'",
                        )
        if self.reaches("release") and declared_stage != "released":
            self.error(name, "stage must be 'released' for release validation")

    def validate_cross_references(self) -> None:
        deck = self.docs.get("deck-spec.json", {})
        scene = self.docs.get("scene-graph.json", {})
        manifest = self.docs.get("asset-manifest.json", {})
        if not all(isinstance(doc, dict) for doc in (deck, scene, manifest)):
            return
        deck_records = {slide.get("id"): slide for slide in deck.get("slides", []) if isinstance(slide, dict)}
        scene_records = {slide.get("slide_id"): slide for slide in scene.get("slides", []) if isinstance(slide, dict)}
        deck_slides = set(deck_records)
        scene_slides = set(scene_records)
        asset_slides = {
            slide_id
            for asset in manifest.get("assets", [])
            if isinstance(asset, dict)
            for slide_id in (
                asset.get("slide_ids")
                if isinstance(asset.get("slide_ids"), list)
                else [asset.get("slide_id")]
            )
            if slide_id
        }
        for slide_id in (scene_slides | asset_slides) - deck_slides:
            self.error("cross-reference", f"unknown slide_id '{slide_id}'")
        scene_ids = {
            element.get("component_id")
            for slide in scene.get("slides", [])
            if isinstance(slide, dict)
            for element in slide.get("elements", [])
            if isinstance(element, dict)
        }
        manifest_ids = {
            asset.get("id") for asset in manifest.get("assets", []) if isinstance(asset, dict)
        }
        for component_id in scene_ids - manifest_ids:
            self.error("cross-reference", f"scene component '{component_id}' missing from asset-manifest")
        for component_id in manifest_ids - scene_ids:
            self.error("cross-reference", f"manifest asset '{component_id}' missing from scene-graph")

        manifest_by_slide: dict[Any, set[Any]] = {}
        for asset in manifest.get("assets", []):
            if isinstance(asset, dict):
                slide_ids = (
                    asset.get("slide_ids")
                    if isinstance(asset.get("slide_ids"), list)
                    else [asset.get("slide_id")]
                )
                for slide_id in slide_ids:
                    if slide_id:
                        manifest_by_slide.setdefault(slide_id, set()).add(asset.get("id"))
        for slide_id, deck_slide in deck_records.items():
            raw_components = deck_slide.get("components", [])
            deck_components = {
                component
                for component in raw_components
                if isinstance(component, str) and component
            } if isinstance(raw_components, list) else set()
            scene_components = {
                element.get("component_id")
                for element in scene_records.get(slide_id, {}).get("elements", [])
                if isinstance(element, dict)
            }
            if deck_components != scene_components:
                self.error("cross-reference", f"slide '{slide_id}' deck components differ from scene-graph")
            if deck_components != manifest_by_slide.get(slide_id, set()):
                self.error("cross-reference", f"slide '{slide_id}' deck components differ from asset-manifest")
            deck_slot_ids = {
                slot.get("id")
                for slot in deck_slide.get("fill_slots", [])
                if isinstance(slot, dict)
            }
            for asset in manifest.get("assets", []):
                if not isinstance(asset, dict):
                    continue
                asset_slide_ids = (
                    asset.get("slide_ids")
                    if isinstance(asset.get("slide_ids"), list)
                    else [asset.get("slide_id")]
                )
                if slide_id not in asset_slide_ids:
                    continue
                fill_slot_ids = asset.get("fill_slot_ids", [])
                if not isinstance(fill_slot_ids, list):
                    continue
                for slot_id in fill_slot_ids:
                    if not isinstance(slot_id, str):
                        continue
                    if slot_id not in deck_slot_ids:
                        self.error(
                            "cross-reference",
                            f"asset '{asset.get('id')}' references unknown fill_slot '{slot_id}'",
                        )

        if self.reaches("assembly"):
            assembly = self.docs.get("assembly-map.json", {})
            if isinstance(assembly, dict):
                assembly_records = {
                    slide.get("slide_id"): slide
                    for slide in assembly.get("slides", [])
                    if isinstance(slide, dict)
                }
                if set(assembly_records) != deck_slides:
                    self.error("cross-reference", "assembly-map slide coverage differs from deck-spec")
                for slide_id, deck_slide in deck_records.items():
                    assembled = assembly_records.get(slide_id, {})
                    assembled_components = {
                        component
                        for component in assembled.get("component_ids", [])
                        if isinstance(component, str) and component
                    }
                    deck_component_ids = {
                        component
                        for component in deck_slide.get("components", [])
                        if isinstance(component, str) and component
                    }
                    if assembled_components != deck_component_ids:
                        self.error("cross-reference", f"slide '{slide_id}' assembly component_ids are incomplete")
                    deck_slots = {
                        slot.get("id")
                        for slot in deck_slide.get("fill_slots", [])
                        if isinstance(slot, dict)
                    }
                    if set(assembled.get("fill_slot_ids", [])) != deck_slots:
                        self.error("cross-reference", f"slide '{slide_id}' assembly fill_slot_ids are incomplete")

        if self.reaches("qa"):
            qa = self.docs.get("qa-report.json", {})
            if isinstance(qa, dict):
                qa_slides = {
                    slide.get("slide_id") for slide in qa.get("slides", []) if isinstance(slide, dict)
                }
                if qa_slides != deck_slides:
                    self.error("cross-reference", "qa-report slide coverage differs from deck-spec")

    def validate_bbox(self, bbox: Any, location: str) -> None:
        if not isinstance(bbox, list) or len(bbox) != 4:
            self.error(location, "bbox must be [x, y, width, height]")
            return
        if any(not isinstance(value, (int, float)) for value in bbox):
            self.error(location, "bbox values must be numbers")
            return
        x, y, width, height = bbox
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
            self.error(location, "bbox must fit within normalized 0..1 canvas bounds")

    def validate_relative_file(self, value: Any, location: str) -> Path | None:
        if not isinstance(value, str):
            self.error(location, "must be a relative path string")
            return None
        relative = Path(value)
        if relative.drive or relative.anchor or relative.is_absolute() or ".." in relative.parts:
            self.error(location, "must stay inside the project directory")
            return None
        project_root = self.root.resolve()
        resolved = (project_root / relative).resolve()
        if not resolved.is_relative_to(project_root):
            self.error(location, "must stay inside the project directory")
            return None
        if not resolved.is_file():
            self.error(location, f"referenced file does not exist: {value}")
            return None
        return resolved

    def inspect_png(self, path: Path) -> tuple[bool, float, bool, bool]:
        try:
            data = path.read_bytes()
        except OSError:
            return False, 0.0, False, False
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return False, 0.0, False, False
        offset = 8
        width: int | None = None
        height: int | None = None
        bit_depth: int | None = None
        color_type: int | None = None
        interlace: int | None = None
        compressed = bytearray()
        saw_iend = False
        while offset + 12 <= len(data):
            length = int.from_bytes(data[offset : offset + 4], "big")
            chunk_type = data[offset + 4 : offset + 8]
            end = offset + 12 + length
            if end > len(data):
                return False, 0.0, False, False
            payload = data[offset + 8 : offset + 8 + length]
            expected_crc = int.from_bytes(data[offset + 8 + length : end], "big")
            if (zlib.crc32(chunk_type + payload) & 0xFFFFFFFF) != expected_crc:
                return False, 0.0, False, False
            if chunk_type == b"IHDR":
                if length != 13:
                    return False, 0.0, False, False
                width = int.from_bytes(payload[0:4], "big")
                height = int.from_bytes(payload[4:8], "big")
                bit_depth = payload[8]
                color_type = payload[9]
                interlace = payload[12]
            elif chunk_type == b"IDAT":
                compressed.extend(payload)
            elif chunk_type == b"IEND":
                saw_iend = True
                break
            offset = end
        valid = all(value is not None for value in (width, height, bit_depth, color_type, interlace)) and saw_iend and bool(compressed)
        if not valid or bit_depth != 8 or color_type not in {4, 6} or interlace != 0:
            return bool(valid), 0.0, False, False
        channels = 2 if color_type == 4 else 4
        stride = int(width) * channels
        try:
            raw = zlib.decompress(bytes(compressed))
        except zlib.error:
            return False, 0.0, False, False
        expected_length = int(height) * (stride + 1)
        if len(raw) != expected_length:
            return False, 0.0, False, False
        previous = bytearray(stride)
        transparent_pixels = 0
        has_visible_pixel = False
        clear_border = True
        for row_index in range(int(height)):
            start = row_index * (stride + 1)
            filter_type = raw[start]
            source = raw[start + 1 : start + 1 + stride]
            recon = bytearray(stride)
            for index, value in enumerate(source):
                left = recon[index - channels] if index >= channels else 0
                up = previous[index]
                upper_left = previous[index - channels] if index >= channels else 0
                if filter_type == 0:
                    predictor = 0
                elif filter_type == 1:
                    predictor = left
                elif filter_type == 2:
                    predictor = up
                elif filter_type == 3:
                    predictor = (left + up) // 2
                elif filter_type == 4:
                    predictor = self.paeth(left, up, upper_left)
                else:
                    return False, 0.0, False, False
                recon[index] = (value + predictor) & 0xFF
            alpha_offset = 1 if color_type == 4 else 3
            alphas = [recon[index] for index in range(alpha_offset, stride, channels)]
            transparent_pixels += sum(alpha == 0 for alpha in alphas)
            has_visible_pixel = has_visible_pixel or any(alpha > 0 for alpha in alphas)
            if row_index in {0, int(height) - 1}:
                clear_border = clear_border and all(alpha == 0 for alpha in alphas)
            else:
                clear_border = clear_border and alphas[0] == 0 and alphas[-1] == 0
            previous = recon
        ratio = transparent_pixels / (int(width) * int(height))
        return True, ratio, clear_border, has_visible_pixel

    def validate_pptx_content(self, path: Path) -> None:
        location = "assembly-map.json.output"
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                required_parts = {
                    "[Content_Types].xml",
                    "_rels/.rels",
                    "ppt/presentation.xml",
                    "ppt/_rels/presentation.xml.rels",
                }
                missing_parts = required_parts - set(names)
                if missing_parts:
                    self.error(location, f"PPTX is missing required Office parts: {sorted(missing_parts)}")
                parsed_xml: dict[str, ElementTree.Element] = {}
                for part in required_parts & set(names):
                    try:
                        parsed_xml[part] = ElementTree.fromstring(archive.read(part))
                    except ElementTree.ParseError:
                        self.error(location, f"PPTX part is not valid XML: {part}")
                content_types = parsed_xml.get("[Content_Types].xml")
                if content_types is not None:
                    overrides = {
                        item.attrib.get("PartName"): item.attrib.get("ContentType")
                        for item in content_types
                        if item.tag.endswith("Override")
                    }
                    expected_presentation_type = (
                        "application/vnd.openxmlformats-officedocument."
                        "presentationml.presentation.main+xml"
                    )
                    if overrides.get("/ppt/presentation.xml") != expected_presentation_type:
                        self.error(location, "PPTX content types do not declare a presentation main part")
                root_relationships = parsed_xml.get("_rels/.rels")
                if root_relationships is not None:
                    office_targets = {
                        rel.attrib.get("Target")
                        for rel in root_relationships
                        if rel.attrib.get("Type", "").endswith("/officeDocument")
                    }
                    if "ppt/presentation.xml" not in office_targets:
                        self.error(location, "PPTX root relationships do not target ppt/presentation.xml")
                slide_names = [
                    name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
                ]
                deck = self.docs.get("deck-spec.json", {})
                expected_pages = len(deck.get("slides", [])) if isinstance(deck, dict) else 0
                if len(slide_names) != expected_pages:
                    self.error(location, "PPTX slide count differs from deck-spec")
                if content_types is not None:
                    slide_type = (
                        "application/vnd.openxmlformats-officedocument."
                        "presentationml.slide+xml"
                    )
                    for slide_name in slide_names:
                        if overrides.get(f"/{slide_name}") != slide_type:
                            self.error(location, f"PPTX content types do not declare slide: {slide_name}")
                presentation = parsed_xml.get("ppt/presentation.xml")
                slide_size = None
                if presentation is not None:
                    size = presentation.find(
                        ".//{http://schemas.openxmlformats.org/presentationml/2006/main}sldSz"
                    )
                    if size is not None:
                        try:
                            slide_size = (int(size.attrib["cx"]), int(size.attrib["cy"]))
                        except (KeyError, ValueError):
                            self.error(location, "PPTX slide size is invalid")
                    if slide_size is None:
                        self.error(location, "PPTX presentation is missing a valid slide size")
                    presentation_rels = parsed_xml.get("ppt/_rels/presentation.xml.rels")
                    rel_targets: dict[str, str] = {}
                    if presentation_rels is not None:
                        for rel in presentation_rels:
                            rel_id = rel.attrib.get("Id")
                            target = rel.attrib.get("Target")
                            if rel_id and target:
                                rel_targets[rel_id] = posixpath.normpath(posixpath.join("ppt", target))
                    relationship_attribute = (
                        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                    )
                    slide_ids = presentation.findall(
                        ".//{http://schemas.openxmlformats.org/presentationml/2006/main}sldId"
                    )
                    linked_slides = [
                        rel_targets.get(slide_id.attrib.get(relationship_attribute, ""))
                        for slide_id in slide_ids
                    ]
                    if None in linked_slides or set(linked_slides) != set(slide_names):
                        self.error(location, "PPTX presentation-to-slide relationship chain is incomplete")
                    assembly = self.docs.get("assembly-map.json", {})
                    expected_part_order = [
                        slide.get("pptx_part")
                        for slide in sorted(
                            (
                                slide
                                for slide in assembly.get("slides", [])
                                if isinstance(slide, dict)
                            ),
                            key=lambda item: item.get("output_index", 0),
                        )
                    ] if isinstance(assembly, dict) else []
                    if linked_slides != expected_part_order:
                        self.error(location, "PPTX slide relationship order differs from assembly-map")
                concept_hashes: set[str] = set()
                for slide in deck.get("slides", []):
                    if not isinstance(slide, dict) or not slide.get("concept_path"):
                        continue
                    concept = self.root / slide["concept_path"]
                    if concept.is_file():
                        concept_hashes.add(hashlib.sha256(concept.read_bytes()).hexdigest())
                manifest = self.docs.get("asset-manifest.json", {})
                approved_media_hashes = {
                    hashlib.sha256((self.root / asset["output"]).read_bytes()).hexdigest()
                    for asset in manifest.get("assets", [])
                    if isinstance(asset, dict)
                    and asset.get("status") == "approved"
                    and asset.get("output")
                    and (self.root / asset["output"]).is_file()
                } if isinstance(manifest, dict) else set()
                for name in names:
                    if name.startswith("ppt/media/"):
                        media_sha = hashlib.sha256(archive.read(name)).hexdigest()
                        if media_sha in concept_hashes:
                            self.error(location, "PPTX embeds an approved concept render as media")
                        if media_sha not in approved_media_hashes:
                            self.error(location, f"PPTX embeds unapproved raster media: {name}")
                visual_parts = slide_names + [
                    name
                    for name in names
                    if re.fullmatch(r"ppt/(slideLayouts|slideMasters)/[^/]+\.xml", name)
                ]
                for slide_name in visual_parts:
                    try:
                        slide_root = ElementTree.fromstring(archive.read(slide_name))
                    except ElementTree.ParseError:
                        self.error(location, f"PPTX slide is not valid XML: {slide_name}")
                        continue
                    if slide_size is None:
                        continue
                    self.validate_part_relationships(archive, set(names), slide_name, slide_root)
                    self.detect_full_slide_rasters(slide_root, slide_name, slide_size)
        except (OSError, zipfile.BadZipFile):
            self.error(location, "PPTX output is not a readable Office package")

    def detect_full_slide_rasters(
        self,
        xml_root: ElementTree.Element,
        part_name: str,
        slide_size: tuple[int, int],
    ) -> None:
        location = "assembly-map.json.output"
        p = "http://schemas.openxmlformats.org/presentationml/2006/main"
        a = "http://schemas.openxmlformats.org/drawingml/2006/main"
        if xml_root.find(f".//{{{p}}}bg//{{{a}}}blip") is not None:
            self.error(location, f"PPTX uses a raster slide background in {part_name}")
        containers = xml_root.findall(f".//{{{p}}}pic") + xml_root.findall(f".//{{{p}}}sp")
        slide_cx, slide_cy = slide_size
        for container in containers:
            if container.find(f".//{{{a}}}blip") is None:
                continue
            transform = container.find(f".//{{{a}}}xfrm")
            if transform is None:
                continue
            offset = transform.find(f"{{{a}}}off")
            extent = transform.find(f"{{{a}}}ext")
            if offset is None or extent is None:
                continue
            try:
                x, y = int(offset.attrib["x"]), int(offset.attrib["y"])
                cx, cy = int(extent.attrib["cx"]), int(extent.attrib["cy"])
            except (KeyError, ValueError):
                continue
            if (
                x <= slide_cx * 0.05
                and y <= slide_cy * 0.05
                and cx >= slide_cx * 0.9
                and cy >= slide_cy * 0.9
            ):
                self.error(
                    location,
                    f"PPTX contains a near-full-slide raster in {part_name}; flattened concepts are prohibited",
                )

    def validate_part_relationships(
        self,
        archive: zipfile.ZipFile,
        names: set[str],
        part_name: str,
        xml_root: ElementTree.Element,
    ) -> None:
        location = "assembly-map.json.output"
        a = "http://schemas.openxmlformats.org/drawingml/2006/main"
        relationship_attribute = (
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
        )
        blips = xml_root.findall(f".//{{{a}}}blip")
        if not blips:
            return
        directory = posixpath.dirname(part_name)
        rel_name = posixpath.join(directory, "_rels", posixpath.basename(part_name) + ".rels")
        if rel_name not in names:
            self.error(location, f"PPTX media relationships are missing for {part_name}")
            return
        try:
            rel_root = ElementTree.fromstring(archive.read(rel_name))
        except ElementTree.ParseError:
            self.error(location, f"PPTX relationships are invalid XML: {rel_name}")
            return
        targets: dict[str, str] = {}
        for rel in rel_root:
            rel_id = rel.attrib.get("Id")
            target = rel.attrib.get("Target")
            if rel_id and target:
                targets[rel_id] = posixpath.normpath(posixpath.join(directory, target))
        for blip in blips:
            rel_id = blip.attrib.get(relationship_attribute)
            if not rel_id or rel_id not in targets or targets[rel_id] not in names:
                self.error(location, f"PPTX media relationship is unresolved in {part_name}")

    @staticmethod
    def paeth(left: int, up: int, upper_left: int) -> int:
        estimate = left + up - upper_left
        distances = (abs(estimate - left), abs(estimate - up), abs(estimate - upper_left))
        if distances[0] <= distances[1] and distances[0] <= distances[2]:
            return left
        if distances[1] <= distances[2]:
            return up
        return upper_left

    def check_unique(self, records: list[Any], field: str, location: str) -> None:
        seen: set[Any] = set()
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            value = record.get(field)
            if not isinstance(value, str) or not value:
                self.error(f"{location}[{index}]", f"{field} must be a non-empty string")
            elif value in seen:
                self.error(f"{location}[{index}]", f"duplicate {field} '{value}'")
            else:
                seen.add(value)

    def run(self) -> list[str]:
        if not self.root.is_dir():
            return [f"project: directory does not exist: {self.root}"]
        self.load_required_documents()
        if self.reaches("intake"):
            self.validate_brief()
            self.validate_state()
        if self.reaches("research"):
            self.validate_research()
        if self.reaches("story"):
            self.validate_alignment()
            self.validate_storyboard()
        if self.reaches("style"):
            self.validate_reference_study()
            self.validate_concept_calibration()
            self.validate_style()
            self.validate_capability_report()
        if self.reaches("spec"):
            self.validate_deck()
        if self.reaches("concept"):
            self.validate_concept_generation_log()
        if self.reaches("inventory"):
            self.validate_scene_graph()
            self.validate_manifest()
            self.validate_cross_references()
            self.validate_component_master_manifest()
        if self.reaches("assembly"):
            self.validate_assembly()
        if self.reaches("qa"):
            self.validate_qa()
        return self.errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--stage", choices=STAGES, default="release")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validator = ProjectValidator(args.project_dir.resolve(), args.stage)
    errors = validator.run()
    if errors:
        print(f"FAIL: {len(errors)} contract issue(s)")
        for issue in errors:
            print(f"- {issue}")
        return 1
    print(f"PASS: project contract is valid through stage '{args.stage}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
