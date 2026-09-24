import json
import hashlib
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
import zipfile
from pathlib import Path
from types import SimpleNamespace


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_project.py"
MODULE_SPEC = importlib.util.spec_from_file_location("ai_presentation_validator", SCRIPT)
VALIDATOR_MODULE = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(VALIDATOR_MODULE)
ProjectValidator = VALIDATOR_MODULE.ProjectValidator
build_material_prompt = VALIDATOR_MODULE.VISUAL_ADAPTERS.build_material_prompt
REGISTRY_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "project-template"
    / "visual-provider-registry.json"
)


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def transparent_png() -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 3, 3, 8, 6, 0, 0, 0)
    transparent = [0, 0, 0, 0]
    visible = [0, 180, 255, 255]
    rows = [
        bytes([0] + transparent * 3),
        bytes([0] + transparent + visible + transparent),
        bytes([0] + transparent * 3),
    ]
    image_data = b"".join(rows)
    return signature + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", zlib.compress(image_data)) + png_chunk(b"IEND", b"")


def write_json(root: Path, name: str, payload: dict) -> None:
    (root / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def value_sha256(value: object) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def gate_decision_values(root: Path, gate: str) -> dict[str, object]:
    storyboard = json.loads((root / "storyboard.json").read_text(encoding="utf-8"))
    style = json.loads((root / "style-contract.json").read_text(encoding="utf-8"))
    deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
    assembly = json.loads((root / "assembly-map.json").read_text(encoding="utf-8"))
    qa = json.loads((root / "qa-report.json").read_text(encoding="utf-8"))
    concept_log = json.loads(
        (root / "concept-generation-log.json").read_text(encoding="utf-8")
    )
    if gate == "story":
        slides = storyboard["slides"]
        return {
            "slide_sequence": [slide["id"] for slide in slides],
            "action_titles": {slide["id"]: slide["title"] for slide in slides},
            "slide_messages": {slide["id"]: slide["message"] for slide in slides},
            "evidence_mapping": {
                slide["id"]: slide.get("evidence_ids", []) for slide in slides
            },
            "appendix_boundary": {
                "slide_ids": [
                    slide["id"]
                    for slide in slides
                    if slide.get("narrative_role") == "appendix"
                ],
                "policy": "declared",
            },
        }
    if gate == "style_anchors":
        anchors = {anchor["role"]: anchor for anchor in style["anchor_concepts"]}
        reference_study = json.loads(
            (root / "reference-study.json").read_text(encoding="utf-8")
        )
        calibration = json.loads(
            (root / "concept-calibration.json").read_text(encoding="utf-8")
        )
        return {
            "reference_selection": {
                "selected_reference_ids": reference_study.get(
                    "selected_reference_ids", []
                ),
                "reference_contact_sheet": reference_study.get(
                    "reference_contact_sheet"
                ),
            },
            "concept_calibration": {
                "selected_variant_id": style.get("selected_calibration_variant_id"),
                "selected_direction_id": style.get("selected_direction_id"),
                "style_strength": style.get("style_strength"),
                "layout_density": style.get("layout_density"),
                "calibration_version": calibration.get("version"),
            } if calibration.get("status") == "generated" else {
                "status": "not-required",
                "reason": calibration.get("reason"),
            },
            "composition_profile": style["composition_profile"],
            "readability_profile": style.get("readability_profile"),
            "visual_direction": style["direction"],
            "style_rules": style["rules"],
            "anchor_opening": anchors["opening"],
            "anchor_typical": anchors["typical"],
            "anchor_highest_risk": anchors["highest-risk"],
        }
    if gate == "concept_contact_sheet":
        concept_records = {
            record["slide_id"]: record
            for record in concept_log.get("slides", [])
            if isinstance(record, dict) and record.get("slide_id")
        }
        if concept_log.get("status") == "generated":
            contentful_review: dict[str, object] = {
                "slides": {
                    slide_id: {
                        "version": record.get("version"),
                        "copy_map_sha256": value_sha256(record.get("copy_map")),
                        "source_lineage": {
                            source["id"]: source.get("sha256")
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
            full_contact_sheet: dict[str, object] = {
                "concept_paths": [slide["concept_path"] for slide in deck["slides"]],
                "contentful_image_sha256": {
                    slide_id: record.get("output_sha256")
                    for slide_id, record in concept_records.items()
                },
                "review_contact_sheet": concept_log.get("review_contact_sheet"),
                "concept_generation_log_sha256": hashlib.sha256(
                    (root / "concept-generation-log.json").read_bytes()
                ).hexdigest(),
            }
        else:
            contentful_review = {
                "status": "not-required",
                "reason": concept_log.get("reason"),
            }
            full_contact_sheet = {
                "concept_paths": [slide["concept_path"] for slide in deck["slides"]]
            }
        return {
            "full_deck_contact_sheet": full_contact_sheet,
            "contentful_copy_source_review": contentful_review,
            "readability_review": {
                "policy": "full-size-human-review",
                "profile": style.get("readability_profile"),
                "slides": {
                    slide["id"]: slide.get("readability") for slide in deck["slides"]
                },
            },
            "layout_richness_review": {
                "slides": {
                    slide["id"]: {
                        "layout_archetype": slide["composition"]["layout_archetype"],
                        "complexity": slide["composition"]["complexity"],
                        "information_unit_count": len(
                            slide["composition"]["information_units"]
                        ),
                        "visual_layer_count": len(
                            slide["composition"]["visual_layers"]
                        ),
                    }
                    for slide in deck["slides"]
                },
                "policy": "review-rendered-contact-sheet",
            },
            "blank_table_chart_regions": {
                "fill_slot_ids": [
                    slot["id"]
                    for slide in deck["slides"]
                    for slot in slide.get("fill_slots", [])
                    if slot.get("kind") in {"table", "chart", "data"}
                ],
                "policy": "blank-fill-slots",
            },
            "special_typography_exceptions": {
                "asset_ids": [
                    asset["id"]
                    for asset in manifest["assets"]
                    if asset.get("role") == "special-typography"
                ],
                "policy": "explicit-only",
            },
            "slide_specific_deviations": {"items": [], "policy": "declared"},
        }
    if gate == "release":
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
                slide["slide_id"]: {
                    "component_ids": slide["component_ids"],
                    "fill_slot_ids": slide["fill_slot_ids"],
                }
                for slide in assembly["slides"]
            },
            "deliverable_index": {
                "path": qa.get("deliverable_index"),
                "asset_outputs": [asset["output"] for asset in manifest["assets"]],
            },
        }
    raise AssertionError(f"unknown gate: {gate}")


def make_valid_project(root: Path) -> None:
    capability_sample = root / "capability" / "transparent-sample.png"
    capability_sample.parent.mkdir(parents=True)
    capability_sample.write_bytes(transparent_png())
    write_json(
        root,
        "brief.json",
        {
            "project_id": "demo-deck",
            "audience": "department leaders",
            "goal": "approve the proposed workflow",
            "quality_profile": "validation-fixture",
            "delivery": {"formats": ["component-library"], "aspect_ratio": "16:9"},
            "editability": {
                "ordinary_text": "native-editable",
                "data": "native-editable",
                "visual_components": "component-editable",
                "internal_vector_paths": False
            },
            "capacity_budget": {
                "component_limit": 40,
                "generation_call_limit": 10,
                "retry_limit_per_asset": 3,
                "deadline": None,
                "fallback_delivery": "component-library"
            }
        },
    )
    critical_decisions = {
        "audience": "department leaders",
        "decision_goal": "approve the proposed workflow",
        "source_authority": ["brief.json", "research-bundle.json"],
        "truth_boundaries": ["source screenshots and figures stay exact"],
        "research_permission": "external-search-approved",
        "delivery_form": ["component-library"],
        "editability_commitment": {
            "ordinary_text": "native-editable",
            "data": "native-editable",
            "visual_components": "component-editable",
            "internal_vector_paths": False,
        },
    }
    write_json(
        root,
        "alignment.json",
        {
            "version": "v1",
            "material_review": {
                "status": "completed",
                "source_material_provided": True,
                "inspected_sources": [
                    {
                        "path": "brief.json",
                        "sha256": hashlib.sha256((root / "brief.json").read_bytes()).hexdigest(),
                    }
                ],
                "inspection_notes": "Existing brief inspected before questions.",
            },
            "discovered_facts": [
                {
                    "id": "F01",
                    "decision_id": "audience",
                    "value": "department leaders",
                    "source_refs": ["brief.json"],
                }
            ],
            "decisions": [
                {
                    "id": decision_id,
                    "status": "resolved",
                    "value": value,
                    "basis": "user-confirmed",
                }
                for decision_id, value in critical_decisions.items()
            ],
            "question_frontier": {"round": 1, "decision_ids": []},
            "approval_packet": {
                "gate": "brief_authority",
                "version": "v1",
                "decision_ids": list(critical_decisions),
                "recommendations_visible": False,
            },
        },
    )
    write_json(
        root,
        "capability-report.json",
        {
            "probed_at": "2026-09-23T11:00:00+08:00",
            "image_generation": {"status": "verified", "provider": "codex-image_gen"},
            "transparent_output": {
                "status": "verified",
                "sample_path": "capability/transparent-sample.png"
            },
            "assembly": {"status": "not-requested", "backend": None},
            "render_inspection": {"status": "verified"}
        },
    )
    write_json(
        root,
        "research-bundle.json",
        {
            "mode": "external",
            "query_log": [{"query": "example", "engine": "exa", "searched_at": "2026-09-23"}],
            "sources": [{"id": "SRC01", "url": "https://example.com", "kind": "primary"}],
            "claims": [{"id": "E01", "claim": "Example claim", "source_ids": ["SRC01"]}],
            "gaps": [],
            "assumptions": [],
            "rejected_sources": [],
        },
    )
    write_json(
        root,
        "storyboard.json",
        {
            "slides": [
                {
                    "id": "S01",
                    "title": "A decision-ready workflow",
                    "message": "Concept images become reusable components.",
                    "narrative_role": "mechanism",
                    "evidence_policy": "required",
                    "evidence_ids": ["E01"],
                    "visual_intent": "left-to-right transformation",
                }
            ]
        },
    )
    write_json(
        root,
        "reference-study.json",
        {
            "version": "v1",
            "status": "not-required",
            "reason": "validator fixture does not claim production visual quality",
        },
    )
    write_json(
        root,
        "concept-calibration.json",
        {
            "status": "not-required",
            "reason": "validator fixture does not claim visual calibration",
        },
    )
    write_json(
        root,
        "style-contract.json",
        {
            "version": "v1",
            "direction": "editorial technical",
            "primary_visual_family": "guizang-material-illustration",
            "secondary_provider_roles": {
                "photo-postprocess-coach": ["ordinary-photo"],
                "scene-distillation-zine-v1-3": ["opening"],
            },
            "explicit_visual_opt_ins": [],
            "palette": ["#0F172A", "#38BDF8"],
            "selected_reference_ids": ["awesome-gpt-image-2:charts-infographics"],
            "concept_reference_mode": "analysis-only",
            "pass_selected_images_to_image_gen": False,
            "composition_profile": {
                "quality_profile": "validation-fixture",
                "visual_richness": "restrained",
                "layout_archetype_minimum": 1,
                "max_consecutive_same_archetype": 1,
                "min_information_units_per_content_slide": 1,
                "min_visual_layers_per_content_slide": 1,
                "sparse_allowed_roles": ["opening", "transition", "closing"],
            },
            "readability_profile": {
                "action_title_min_pt": 32,
                "body_min_pt": 20,
                "key_caption_min_pt": 18,
                "source_qualifier_min_pt": 16,
                "evidence_min_width": 0.42,
                "evidence_min_height": 0.43,
                "fine_ui_preferred_width": 0.50,
                "fine_ui_preferred_height": 0.46,
                "illustration_min_width": 0.30,
                "illustration_min_height": 0.25,
            },
            "rules": ["structure before decoration", "ordinary copy stays editable"],
            "anchor_concepts": [
                {"role": "opening", "slide_id": "S01", "path": "concepts/S01.png"},
                {"role": "typical", "slide_id": "S01", "path": "concepts/S01.png"},
                {"role": "highest-risk", "slide_id": "S01", "path": "concepts/S01.png"}
            ],
        },
    )
    write_json(
        root,
        "visual-provider-registry.json",
        json.loads(REGISTRY_TEMPLATE.read_text(encoding="utf-8")),
    )
    write_json(
        root,
        "deck-spec.json",
        {
            "production_estimate": {
                "unique_components": 1,
                "planned_generation_calls": 1,
                "reserved_retries": 3,
                "estimated_completion": None
            },
            "slides": [
                {
                    "id": "S01",
                    "title": "A decision-ready workflow",
                    "message": "Concept images become reusable components.",
                    "concept_path": "concepts/S01.png",
                    "components": ["C01"],
                    "composition": {
                        "layout_archetype": "fixture-flow",
                        "complexity": "standard",
                        "information_units": [{"id": "U01", "role": "claim"}],
                        "visual_layers": [{"id": "L01", "role": "arrow"}],
                        "reference_ids": [],
                        "variation_from_previous": "opening",
                    },
                    "fill_slots": [
                        {"id": "F01", "kind": "ordinary-text", "bbox": [0.1, 0.1, 0.3, 0.1]}
                    ],
                    "readability": {
                        "text_regions": [
                            {"fill_slot_id": "F01", "role": "action-title", "planned_font_pt": 34, "line_count": 1}
                        ],
                        "main_visual": {"kind": "illustration", "bbox": [0.45, 0.25, 0.40, 0.50]},
                        "exception": None,
                        "full_size_review": {
                            "status": "passed",
                            "display_scale_percent": 100,
                            "reviewer": "fixture-reviewer",
                            "path": "concepts/S01.png",
                            "sha256": hashlib.sha256(b"placeholder-concept").hexdigest(),
                            "reviewed_concept_sha256": hashlib.sha256(b"placeholder-concept").hexdigest(),
                        },
                    },
                }
            ]
        },
    )
    concept = root / "concepts" / "S01.png"
    concept.parent.mkdir(parents=True)
    concept.write_bytes(b"placeholder-concept")
    write_json(
        root,
        "concept-generation-log.json",
        {
            "status": "not-required",
            "reason": "validator fixture does not claim production concept provenance",
        },
    )
    write_json(
        root,
        "scene-graph.json",
        {
            "slides": [
                {
                    "slide_id": "S01",
                    "canvas": {"width": 1920, "height": 1080},
                    "elements": [{"instance_id": "I01", "component_id": "C01", "bbox": [0.1, 0.3, 0.25, 0.2], "z": 1}],
                }
            ]
        },
    )
    output = root / "assets" / "S01" / "C01.png"
    output.parent.mkdir(parents=True)
    output_bytes = transparent_png()
    output.write_bytes(output_bytes)
    write_json(
        root,
        "asset-manifest.json",
        {
            "assets": [
                {
                    "id": "C01",
                    "slide_id": "S01",
                    "role": "arrow",
                    "page_role": "structural-diagram",
                    "provider_id": "guizang-material-illustration",
                    "adapter_id": "material-illustration-v1",
                    "style_contract_version": "v1",
                    "style_contract_sha256": hashlib.sha256(
                        (root / "style-contract.json").read_bytes()
                    ).hexdigest(),
                    "source_kind": "approved-concept-render",
                    "truth_sensitive": False,
                    "deliverable_role": "slide-asset",
                    "strategy": "generated-transparent-png",
                    "editability": "component-editable",
                    "content_policy": "no-text-or-data",
                    "contains_text": False,
                    "contains_data": False,
                    "contains_data_encoding_marks": False,
                    "background_requirement": "transparent",
                    "output_class": "transparent-png-component",
                    "provider_transparency_behavior": "required-real-alpha",
                    "provider_aspect_ratio_behavior": "one-component-per-transparent-canvas",
                    "reference_bbox": [0.1, 0.3, 0.25, 0.2],
                    "prompt": build_material_prompt("arrow", [0.1, 0.3, 0.25, 0.2]),
                    "prompt_language": "en",
                    "references": [
                        {
                            "path": "concepts/S01.png",
                            "sha256": hashlib.sha256(concept.read_bytes()).hexdigest(),
                            "approval_gate": "concept_contact_sheet",
                        }
                    ],
                    "output": "assets/S01/C01.png",
                    "sha256": hashlib.sha256(output_bytes).hexdigest(),
                    "alpha": {"has_alpha": True, "transparent_pixel_ratio": 8 / 9},
                    "generation_attempts": 1,
                    "status": "approved",
                }
            ]
        },
    )
    qa_evidence = root / "qa" / "S01-overlay.png"
    qa_evidence.parent.mkdir(parents=True)
    qa_evidence.write_bytes(transparent_png())
    final_contact_sheet = root / "qa" / "final-contact-sheet.png"
    final_contact_sheet.write_bytes(transparent_png())
    write_json(root, "qa/exception-register.json", {"exceptions": []})
    write_json(
        root,
        "qa/deliverable-index.json",
        {"assets": ["assets/S01/C01.png"], "assembly": "assembly-map.json"},
    )
    write_json(
        root,
        "qa-report.json",
        {
            "status": "passed",
            "checks_performed": ["contract", "alpha", "inventory", "overlay"],
            "evidence_files": ["qa/S01-overlay.png"],
            "final_contact_sheet": "qa/final-contact-sheet.png",
            "exception_register": "qa/exception-register.json",
            "deliverable_index": "qa/deliverable-index.json",
            "differences": [],
            "exceptions": [],
            "slides": [
                {
                    "slide_id": "S01",
                    "status": "passed",
                    "issues": [],
                    "evidence_files": ["qa/S01-overlay.png"],
                }
            ],
        },
    )
    write_json(
        root,
        "assembly-map.json",
        {
            "slides": [
                {
                    "slide_id": "S01",
                    "component_ids": ["C01"],
                    "fill_slot_ids": ["F01"],
                    "flattened_concept_used": False,
                    "output_index": 1,
                }
            ]
        },
    )
    gate_files = {
        "brief_authority": ["brief.json", "alignment.json", "research-bundle.json"],
        "story": ["storyboard.json"],
        "style_anchors": [
            "reference-study.json",
            "concept-calibration.json",
            "style-contract.json",
            "capability-report.json",
            "concepts/S01.png",
        ],
        "concept_contact_sheet": ["concepts/S01.png", "concept-generation-log.json", "deck-spec.json"],
        "release": [
            "asset-manifest.json",
            "assembly-map.json",
            "qa-report.json",
            "qa/S01-overlay.png",
            "qa/final-contact-sheet.png",
            "qa/exception-register.json",
            "qa/deliverable-index.json",
        ],
    }
    gates = {}
    for gate, paths in gate_files.items():
        gates[gate] = {
            "status": "approved",
            "approver": "owner@example",
            "approved_at": "2026-09-23T12:00:00+08:00",
            "artifact_version": "v1",
            "approved_artifacts": {
                path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths
            },
        }
    gates["brief_authority"].update(
        {
            "approval_mode": "explicit",
            "approval_phrase": "确认 G1 对齐包",
            "decision_approvals": {
                decision_id: {
                    "status": "approved",
                    "value_sha256": value_sha256(value),
                }
                for decision_id, value in critical_decisions.items()
            },
        }
    )
    for gate in ("story", "style_anchors", "concept_contact_sheet", "release"):
        decision_values = gate_decision_values(root, gate)
        approval_mode = "release" if gate == "release" else "explicit"
        approval_phrase = "确认发布" if gate == "release" else f"确认 {gate} 审批包"
        gates[gate].update(
            {
                "approval_mode": approval_mode,
                "approval_phrase": approval_phrase,
                "approval_packet": {
                    "gate": gate,
                    "version": "v1",
                    "recommendations_visible": False,
                    "decisions": {
                        decision_id: {
                            "status": "approved",
                            "value": value,
                            "value_sha256": value_sha256(value),
                        }
                        for decision_id, value in decision_values.items()
                    },
                },
            }
        )
    write_json(
        root,
        "run-state.json",
        {
            "stage": "released",
            "fixture_only": True,
            "production_route": {
                "mode": "full-tracked",
                "planning_artifacts": "required",
                "basis": "multi-stage tracked production",
            },
            "artifact_versions": {gate: "v1" for gate in gate_files},
            "gates": gates,
        },
    )


def promote_fixture_to_production(root: Path) -> None:
    brief = json.loads((root / "brief.json").read_text(encoding="utf-8"))
    brief["quality_profile"] = "production"
    write_json(root, "brief.json", brief)

    alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
    alignment["material_review"]["inspected_sources"][0]["sha256"] = hashlib.sha256(
        (root / "brief.json").read_bytes()
    ).hexdigest()
    write_json(root, "alignment.json", alignment)

    reference_dir = root / "references"
    reference_dir.mkdir(parents=True, exist_ok=True)
    reference_ids = ["REF01", "REF02", "REF03"]
    references = []
    for index, reference_id in enumerate(reference_ids, start=1):
        path = reference_dir / f"{reference_id}.png"
        path.write_bytes(transparent_png())
        references.append(
            {
                "id": reference_id,
                "source_kind": "local-style-library",
                "source_locator": f"awesome-gpt-image-2:case-{index}",
                "image_path": f"references/{reference_id}.png",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "usage_note": "design grammar only",
                "status": "analyzed",
                "observations": {
                    "composition": ["asymmetric reading path"],
                    "hierarchy": ["one dominant focal point"],
                    "density": ["layered but readable"],
                    "image_treatment": ["isolated material forms"],
                },
                "transferable_rules": ["use one dominant visual system"],
                "project_translation": ["apply the system to an editable process slide"],
                "do_not_copy": ["source text, logos, characters, exact composition"],
                "target_slide_roles": ["mechanism"],
            }
        )
    reference_contact_sheet = reference_dir / "reference-contact-sheet.png"
    reference_contact_sheet.write_bytes(transparent_png())
    write_json(
        root,
        "reference-study.json",
        {
            "version": "v1",
            "status": "analyzed",
            "reference_contact_sheet": {
                "path": "references/reference-contact-sheet.png",
                "sha256": hashlib.sha256(reference_contact_sheet.read_bytes()).hexdigest(),
            },
            "references": references,
            "direction_options": [
                {
                    "id": "D1",
                    "name": "layered editorial",
                    "reference_ids": reference_ids,
                    "structure": "asymmetric hierarchy",
                    "palette": "dark neutral with cyan accent",
                    "density": "balanced-rich",
                    "imagery": "isolated material illustration",
                    "tradeoffs": ["more production effort"],
                },
                {
                    "id": "D2",
                    "name": "diagram-led",
                    "reference_ids": reference_ids[:2],
                    "structure": "centered system map",
                    "palette": "light neutral with blue accent",
                    "density": "balanced",
                    "imagery": "structural diagram",
                    "tradeoffs": ["less atmospheric"],
                },
            ],
            "recommended_direction_id": "D1",
            "selected_reference_ids": reference_ids,
        },
    )

    calibration_dir = root / "calibration"
    calibration_dir.mkdir(parents=True, exist_ok=True)
    variants = []
    for variant_id, direction_id, strength, density in (
        ("V01", "D1", "balanced", "standard"),
        ("V02", "D2", "expressive", "dense"),
    ):
        image_path = calibration_dir / f"{variant_id}.png"
        image_path.write_bytes(transparent_png())  # contract test-double, not visual evidence
        variants.append(
            {
                "id": variant_id,
                "direction_id": direction_id,
                "style_strength": strength,
                "layout_density": density,
                "tool": "codex-image_gen",
                "model": "test-double",
                "prompt": f"Create one same-content 16:9 calibration concept for S01 in {direction_id}, {strength} strength and {density} density; keep the approved title, message, evidence, visual intent, and blank editable fields identical.",
                "generated_at": "2026-09-23T11:00:00+08:00",
                "reference_images": [
                    {"reference_id": reference["id"], "path": reference["image_path"], "sha256": reference["sha256"]}
                    for reference in references
                ],
                "output_path": f"calibration/{variant_id}.png",
                "output_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            }
        )
    board = calibration_dir / "contact-sheet.png"
    board.write_bytes(transparent_png())
    write_json(
        root,
        "concept-calibration.json",
        {
            "version": "v1",
            "status": "generated",
            "slide_id": "S01",
            "fixed_content": {
                "title": "A decision-ready workflow",
                "message": "Concept images become reusable components.",
                "evidence_ids": ["E01"],
                "visual_intent": "left-to-right transformation",
            },
            "fixed_fill_slots": [
                {"id": "F01", "kind": "ordinary-text", "purpose": "editable claim"}
            ],
            "contact_sheet": {"path": "calibration/contact-sheet.png", "sha256": hashlib.sha256(board.read_bytes()).hexdigest()},
            "variants": variants,
            "recommended_variant_id": "V01",
            "recommendation": {"reason": "balanced hierarchy reads clearly", "impact": "moderate production effort"},
        },
    )

    style = json.loads((root / "style-contract.json").read_text(encoding="utf-8"))
    style["selected_reference_ids"] = reference_ids
    style["selected_calibration_variant_id"] = "V01"
    style["selected_direction_id"] = "D1"
    style["style_strength"] = "balanced"
    style["layout_density"] = "standard"
    style["concept_reference_mode"] = "image-and-analysis"
    style["pass_selected_images_to_image_gen"] = True
    style["composition_profile"] = {
        "quality_profile": "production",
        "visual_richness": "balanced-rich",
        "layout_archetype_minimum": 3,
        "max_consecutive_same_archetype": 2,
        "min_information_units_per_content_slide": 3,
        "min_visual_layers_per_content_slide": 2,
        "sparse_allowed_roles": ["opening", "transition", "closing"],
    }
    write_json(root, "style-contract.json", style)

    deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
    deck["slides"][0]["composition"] = {
        "layout_archetype": "process-journey",
        "complexity": "rich",
        "information_units": [
            {"id": "U01", "role": "claim"},
            {"id": "U02", "role": "mechanism"},
            {"id": "U03", "role": "decision"},
        ],
        "visual_layers": [
            {"id": "L01", "role": "primary-process"},
            {"id": "L02", "role": "annotation-system"},
        ],
        "reference_ids": reference_ids,
        "variation_from_previous": "opening slide",
    }
    write_json(root, "deck-spec.json", deck)

    qa = json.loads((root / "qa-report.json").read_text(encoding="utf-8"))
    qa["checks_performed"].extend(["reference-transfer", "composition-richness", "readability-full-size"])
    write_json(root, "qa-report.json", qa)

    concept_path = root / "concepts" / "S01.png"
    source_dir = root / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_path = source_dir / "approved-outline.md"
    storyboard = json.loads((root / "storyboard.json").read_text(encoding="utf-8"))
    story_slide = storyboard["slides"][0]
    source_path.write_text(
        f"# Approved outline\n\n{story_slide['title']}\n\n{story_slide['message']}\n",
        encoding="utf-8",
    )
    copy_map = [
        {
            "id": "COPY-TITLE",
            "role": "title",
            "text": story_slide["title"],
            "truth_status": "not-applicable",
            "storyboard_field": "title",
            "sources": [
                {
                    "source_id": "STORY01",
                    "locator": "slides[S01].title",
                    "quote": story_slide["title"],
                    "mode": "storyboard-exact",
                }
            ],
        },
        {
            "id": "COPY-BODY",
            "role": "body",
            "text": story_slide["message"],
            "truth_status": "verified",
            "status_label": "已验证",
            "storyboard_field": "message",
            "sources": [
                {
                    "source_id": "STORY01",
                    "locator": "slides[S01].message",
                    "quote": story_slide["message"],
                    "mode": "storyboard-exact",
                },
                {
                    "source_id": "SRC01",
                    "locator": "# Approved outline",
                    "quote": story_slide["message"],
                    "mode": "source-exact",
                },
            ],
        },
    ]
    transcript_path = root / "text-review" / "S01-v1.txt"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        "\n".join(
            "\n".join(
                value
                for value in (item["text"], item.get("status_label"))
                if value
            )
            for item in copy_map
        )
        + "\n",
        encoding="utf-8",
    )
    source_lineage = [
        {
            "id": "STORY01",
            "kind": "approved-storyboard",
            "path": "storyboard.json",
            "sha256": hashlib.sha256((root / "storyboard.json").read_bytes()).hexdigest(),
            "locator": "slides[S01].title and slides[S01].message",
            "status": "approved",
        },
        {
            "id": "SRC01",
            "kind": "authoritative-source",
            "path": "sources/approved-outline.md",
            "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "locator": "# Approved outline",
            "status": "verified",
        },
    ]
    calibration = json.loads(
        (root / "concept-calibration.json").read_text(encoding="utf-8")
    )
    calibration["copy_map"] = copy_map
    calibration["source_lineage"] = source_lineage
    for variant in calibration["variants"]:
        variant_transcript = root / "text-review" / f"{variant['id']}-v1.txt"
        variant_transcript.write_text(
            "\n".join(
                "\n".join(
                    value
                    for value in (item["text"], item.get("status_label"))
                    if value
                )
                for item in copy_map
            )
            + "\n",
            encoding="utf-8",
        )
        variant["image_inventory"] = [
            {
                "id": f"IMG-{variant['id']}",
                "visual_role": "representative",
                "classification": "illustrative",
                "label": "示意",
                "evidence_role": "illustration-only",
            }
        ]
        variant["text_review"] = {
            "method": "human-transcription",
            "copy_map_sha256": value_sha256(copy_map),
            "transcript_path": f"text-review/{variant['id']}-v1.txt",
            "transcript_sha256": hashlib.sha256(
                variant_transcript.read_bytes()
            ).hexdigest(),
            "observations": [
                {
                    "copy_id": item["id"],
                    "observed_text": item["text"],
                    **(
                        {"observed_status_label": item["status_label"]}
                        if item.get("status_label")
                        else {}
                    ),
                }
                for item in copy_map
            ],
            "repair": None,
        }
    write_json(root, "concept-calibration.json", calibration)

    contact_sheet_path = root / "concepts" / "contact-sheet-v1.png"
    contact_sheet_path.write_bytes(transparent_png())
    write_json(
        root,
        "concept-generation-log.json",
        {
            "status": "generated",
            "version": "v1",
            "review_contact_sheet": {
                "path": "concepts/contact-sheet-v1.png",
                "sha256": hashlib.sha256(contact_sheet_path.read_bytes()).hexdigest(),
            },
            "slides": [
                {
                    "slide_id": "S01",
                    "tool": "codex-image_gen",
                    "model": "test-double",
                    "prompt": "Create a 16:9 production concept using the approved process journey, three information units, two visual layers, transferable rules, and explicit do-not-copy boundaries.",
                    "reference_images": [
                        {
                            "reference_id": reference["id"],
                            "path": reference["image_path"],
                            "sha256": reference["sha256"],
                        }
                        for reference in references
                    ],
                    "output_path": "concepts/S01.png",
                    "output_sha256": hashlib.sha256(concept_path.read_bytes()).hexdigest(),
                    "status": "generated",
                    "version": "v1",
                    "copy_map": copy_map,
                    "source_lineage": source_lineage,
                    "image_inventory": [
                        {
                            "id": "IMG01",
                            "visual_role": "representative",
                            "classification": "illustrative",
                            "label": "示意",
                            "evidence_role": "illustration-only",
                        }
                    ],
                    "text_review": {
                        "method": "human-transcription",
                        "copy_map_sha256": value_sha256(copy_map),
                        "transcript_path": "text-review/S01-v1.txt",
                        "transcript_sha256": hashlib.sha256(
                            transcript_path.read_bytes()
                        ).hexdigest(),
                        "observations": [
                            {
                                "copy_id": item["id"],
                                "observed_text": item["text"],
                                **(
                                    {"observed_status_label": item["status_label"]}
                                    if item.get("status_label")
                                    else {}
                                ),
                            }
                            for item in copy_map
                        ],
                        "repair": None,
                    },
                    "selected_calibration_variant_id": "V01",
                    "style_strength": "balanced",
                    "layout_density": "standard",
                }
            ],
        },
    )

    component_master_path = root / "components" / "masters" / "S01-v1.png"
    component_master_path.parent.mkdir(parents=True, exist_ok=True)
    component_master_path.write_bytes(transparent_png())
    geometry_comparison_path = root / "reviews" / "S01-master-geometry.png"
    geometry_comparison_path.parent.mkdir(parents=True, exist_ok=True)
    geometry_comparison_path.write_bytes(transparent_png())
    concept_log_path = root / "concept-generation-log.json"
    deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
    deck_slide = deck["slides"][0]
    write_json(
        root,
        "component-master-manifest.json",
        {
            "status": "generated",
            "slides": [
                {
                    "slide_id": "S01",
                    "version": "v1",
                    "approved_contentful_path": deck_slide["concept_path"],
                    "approved_contentful_sha256": hashlib.sha256(
                        concept_path.read_bytes()
                    ).hexdigest(),
                    "concept_generation_log_sha256": hashlib.sha256(
                        concept_log_path.read_bytes()
                    ).hexdigest(),
                    "component_master_path": "components/masters/S01-v1.png",
                    "component_master_sha256": hashlib.sha256(
                        component_master_path.read_bytes()
                    ).hexdigest(),
                    "text_policy": "textless",
                    "ordinary_text_removed": True,
                    "contains_ordinary_text": False,
                    "preserved_fill_slots": [
                        {
                            "id": slot["id"],
                            "kind": slot["kind"],
                            "bbox": slot["bbox"],
                        }
                        for slot in deck_slide["fill_slots"]
                    ],
                    "geometry_review": {
                        "status": "passed",
                        "reviewer": "owner@example",
                        "display_scale_percent": 100,
                        "comparison_path": "reviews/S01-master-geometry.png",
                        "comparison_sha256": hashlib.sha256(
                            geometry_comparison_path.read_bytes()
                        ).hexdigest(),
                        "reviewed_contentful_sha256": hashlib.sha256(
                            concept_path.read_bytes()
                        ).hexdigest(),
                        "reviewed_master_sha256": hashlib.sha256(
                            component_master_path.read_bytes()
                        ).hexdigest(),
                        "checks": {
                            "composition_preserved": True,
                            "fill_slots_preserved": True,
                            "ordinary_text_removed": True,
                        },
                    },
                }
            ],
        },
    )

    manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
    manifest["assets"][0]["style_contract_sha256"] = hashlib.sha256(
        (root / "style-contract.json").read_bytes()
    ).hexdigest()
    write_json(root, "asset-manifest.json", manifest)

    state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
    state.pop("fixture_only", None)
    state["production_route"]["basis"] = "production reference-first contract test"
    gate_paths = {
        "brief_authority": ["brief.json", "alignment.json", "research-bundle.json"],
        "story": ["storyboard.json"],
        "style_anchors": [
            "reference-study.json",
            "references/reference-contact-sheet.png",
            "concept-calibration.json",
            "calibration/contact-sheet.png",
            "calibration/V01.png",
            "calibration/V02.png",
            "style-contract.json",
            "capability-report.json",
            "concepts/S01.png",
            "storyboard.json",
            "sources/approved-outline.md",
            "text-review/V01-v1.txt",
            "text-review/V02-v1.txt",
        ],
        "concept_contact_sheet": [
            "concepts/S01.png",
            "concepts/contact-sheet-v1.png",
            "concept-generation-log.json",
            "deck-spec.json",
            "storyboard.json",
            "sources/approved-outline.md",
            "text-review/S01-v1.txt",
            "text-review/V01-v1.txt",
            "text-review/V02-v1.txt",
        ],
        "release": list(state["gates"]["release"]["approved_artifacts"]),
    }
    for gate, paths in gate_paths.items():
        state["gates"][gate]["approved_artifacts"] = {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths
        }
    calibration_paths = [
        "concept-calibration.json",
        "calibration/contact-sheet.png",
        "calibration/V01.png",
        "calibration/V02.png",
        "sources/approved-outline.md",
        "storyboard.json",
        "text-review/V01-v1.txt",
        "text-review/V02-v1.txt",
    ]
    state["gates"]["style_anchors"]["calibration_selection"] = {
        "status": "approved",
        "selected_variant_id": "V01",
        "approver": "owner@example",
        "approved_at": "2026-09-23T12:00:00+08:00",
        "artifact_version": "v1",
        "approval_mode": "explicit",
        "approval_phrase": "确认概念图 V01，平衡表现、标准密度",
        "approved_artifacts": {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest()
            for path in calibration_paths
        },
    }
    for gate in ("story", "style_anchors", "concept_contact_sheet", "release"):
        values = gate_decision_values(root, gate)
        state["gates"][gate]["approval_packet"]["decisions"] = {
            decision_id: {
                "status": "approved",
                "value": value,
                "value_sha256": value_sha256(value),
            }
            for decision_id, value in values.items()
        }
    write_json(root, "run-state.json", state)


class ValidateProjectTests(unittest.TestCase):
    def run_validator(self, root: Path, stage: str = "release") -> SimpleNamespace:
        errors = ProjectValidator(root.resolve(), stage).run()
        if errors:
            output = f"FAIL: {len(errors)} contract issue(s)\n" + "\n".join(
                f"- {issue}" for issue in errors
            )
            return SimpleNamespace(returncode=1, stdout=output, stderr="")
        return SimpleNamespace(
            returncode=0,
            stdout=f"PASS: project contract is valid through stage '{stage}'",
            stderr="",
        )

    def run_public_validator(self, root: Path, stage: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(root.resolve()), "--stage", stage],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_template_placeholders_do_not_pass_intake(self):
        template = Path(__file__).resolve().parents[1] / "assets" / "project-template"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("brief.json", "run-state.json"):
                write_json(root, name, json.loads((template / name).read_text(encoding="utf-8")))

            result = self.run_public_validator(root, "intake")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("template placeholder", result.stdout)

    def test_valid_release_project_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS", result.stdout)

    def test_valid_production_reference_first_project_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_public_concept_entry_accepts_contentful_copy_and_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)

            result = self.run_public_validator(root, "concept")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS", result.stdout)

    def test_public_concept_entry_rejects_missing_copy_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            log = json.loads((root / "concept-generation-log.json").read_text(encoding="utf-8"))
            log["slides"][0].pop("copy_map")
            write_json(root, "concept-generation-log.json", log)

            result = self.run_public_validator(root, "concept")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("copy_map must contain", result.stdout)

    def test_public_concept_entry_rejects_stale_authoritative_source_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            (root / "sources" / "approved-outline.md").write_text(
                "# Changed after concept generation\n", encoding="utf-8"
            )

            result = self.run_public_validator(root, "concept")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source_lineage sha256 does not match file", result.stdout)

    def test_public_concept_entry_rejects_unverified_rendered_glyphs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            log = json.loads((root / "concept-generation-log.json").read_text(encoding="utf-8"))
            log["slides"][0]["text_review"]["observations"][0]["observed_text"] = "wrong title"
            write_json(root, "concept-generation-log.json", log)

            result = self.run_public_validator(root, "concept")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("observed_text must exactly match copy_map", result.stdout)

    def test_public_concept_entry_blocks_pending_style_rebaseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["current_style_rebaseline"] = {"status": "pending_user_selection"}
            write_json(root, "run-state.json", state)

            result = self.run_public_validator(root, "concept")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("style rebaseline is pending user selection", result.stdout)

    def test_public_inventory_entry_rejects_master_without_current_g4_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["concept_contact_sheet"]["approved_artifacts"].pop(
                "concept-generation-log.json"
            )
            write_json(root, "run-state.json", state)

            result = self.run_public_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("approved_artifacts missing", result.stdout)

    def test_public_inventory_entry_accepts_g4_linked_textless_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)

            result = self.run_public_validator(root, "inventory")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS", result.stdout)

    def test_public_inventory_entry_rejects_copy_log_changed_after_g4(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            log = json.loads((root / "concept-generation-log.json").read_text(encoding="utf-8"))
            log["slides"][0]["copy_map"][1]["sources"][1]["quote"] = "Changed source quote"
            write_json(root, "concept-generation-log.json", log)

            result = self.run_public_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("approved artifact hash is stale: concept-generation-log.json", result.stdout)

    def test_public_inventory_entry_rejects_changed_fill_slot_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            manifest = json.loads(
                (root / "component-master-manifest.json").read_text(encoding="utf-8")
            )
            manifest["slides"][0]["preserved_fill_slots"][0]["bbox"] = [0.1, 0.1, 0.2, 0.1]
            write_json(root, "component-master-manifest.json", manifest)

            result = self.run_public_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("preserved_fill_slots must preserve deck-spec geometry", result.stdout)

    def test_public_inventory_entry_requires_full_size_master_geometry_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            manifest = json.loads((root / "component-master-manifest.json").read_text(encoding="utf-8"))
            manifest["slides"][0].pop("geometry_review", None)
            write_json(root, "component-master-manifest.json", manifest)

            result = self.run_public_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("geometry_review is required", result.stdout)

    def test_public_inventory_entry_rejects_stale_master_geometry_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            manifest = json.loads((root / "component-master-manifest.json").read_text(encoding="utf-8"))
            manifest["slides"][0]["geometry_review"]["reviewed_master_sha256"] = "0" * 64
            write_json(root, "component-master-manifest.json", manifest)

            result = self.run_public_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("geometry_review must bind the current contentful and master images", result.stdout)

    def test_calibration_requires_human_selection_before_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["style_anchors"].pop("calibration_selection")
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, "style")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("human calibration selection must be approved before anchors", result.stdout)

    def test_calibration_rejects_stale_image_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            (root / "calibration" / "V01.png").write_bytes(b"changed-image")

            result = self.run_validator(root, "style")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output_sha256 does not match concept image", result.stdout)
            self.assertIn("approved artifact hash is stale", result.stdout)

    def test_calibration_rejects_unapproved_style_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            style = json.loads((root / "style-contract.json").read_text(encoding="utf-8"))
            style["selected_calibration_variant_id"] = "V02"
            write_json(root, "style-contract.json", style)

            result = self.run_validator(root, "style")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("selected variant differs from style-contract", result.stdout)

    def test_concept_generation_inherits_calibrated_strength(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            log = json.loads((root / "concept-generation-log.json").read_text(encoding="utf-8"))
            log["slides"][0]["style_strength"] = "expressive"
            write_json(root, "concept-generation-log.json", log)

            result = self.run_validator(root, "concept")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("style_strength must match approved style-contract", result.stdout)

    def test_production_rejects_underfilled_content_slide(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
            deck["slides"][0]["composition"]["information_units"] = [
                {"id": "U01", "role": "claim"}
            ]
            write_json(root, "deck-spec.json", deck)

            result = self.run_validator(root, "spec")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires at least 3 information units", result.stdout)

    def test_production_rejects_repeated_layout_across_five_slides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
            first = deck["slides"][0]
            for number in range(2, 6):
                slide = json.loads(json.dumps(first))
                slide["id"] = f"S{number:02d}"
                slide["composition"]["variation_from_previous"] = "new content"
                deck["slides"].append(slide)
            write_json(root, "deck-spec.json", deck)

            result = self.run_validator(root, "spec")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("deck requires at least 3 layout archetypes", result.stdout)
            self.assertIn("layout archetype repeats more often", result.stdout)

    def test_production_rejects_concept_without_all_attached_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            log = json.loads(
                (root / "concept-generation-log.json").read_text(encoding="utf-8")
            )
            log["slides"][0]["reference_images"].pop()
            write_json(root, "concept-generation-log.json", log)

            result = self.run_validator(root, "concept")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("attached reference IDs must match", result.stdout)

    def test_manifest_provider_and_adapter_must_match_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0]["provider_id"] = "unknown-provider"
            manifest["assets"][0]["adapter_id"] = "invented-adapter"
            write_json(root, "asset-manifest.json", manifest)

            result = self.run_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown visual provider", result.stdout)

    def test_manifest_provider_must_obey_page_role_and_style_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0]["page_role"] = "opening"
            write_json(root, "asset-manifest.json", manifest)

            result = self.run_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not support page role", result.stdout)

    def test_manifest_provider_must_support_the_component_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0]["role"] = "photo-cutout"
            write_json(root, "asset-manifest.json", manifest)

            result = self.run_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not support component role", result.stdout)

    def test_photo_provider_requires_verified_source_rights(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            style = json.loads((root / "style-contract.json").read_text(encoding="utf-8"))
            style["primary_visual_family"] = "photo-postprocess-coach"
            style["secondary_provider_roles"].pop("photo-postprocess-coach", None)
            write_json(root, "style-contract.json", style)
            style_sha = hashlib.sha256((root / "style-contract.json").read_bytes()).hexdigest()
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["style_anchors"]["approved_artifacts"][
                "style-contract.json"
            ] = style_sha
            write_json(root, "run-state.json", state)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0].update(
                {
                    "role": "photo-cutout",
                    "page_role": "ordinary-photo",
                    "provider_id": "photo-postprocess-coach",
                    "adapter_id": "photo-postprocess-v1",
                    "style_contract_sha256": style_sha,
                    "source_kind": "ordinary-photo",
                    "output_class": "photo-or-transparent-cutout",
                    "provider_transparency_behavior": "optional-subject-cutout",
                    "provider_aspect_ratio_behavior": "preserve-subject-with-approved-crop",
                }
            )
            write_json(root, "asset-manifest.json", manifest)

            result = self.run_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source_rights_confirmation must be an object", result.stdout)

    def test_explicit_style_provider_requires_approved_g4_special_page_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            provider_id = "gc-minimal-zine-poster-v0-3"
            style = json.loads((root / "style-contract.json").read_text(encoding="utf-8"))
            style["secondary_provider_roles"][provider_id] = ["special-poster"]
            style["explicit_visual_opt_ins"] = [provider_id]
            write_json(root, "style-contract.json", style)
            style_sha = hashlib.sha256((root / "style-contract.json").read_bytes()).hexdigest()
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["style_anchors"]["approved_artifacts"][
                "style-contract.json"
            ] = style_sha
            write_json(root, "run-state.json", state)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0].update(
                {
                    "role": "illustration",
                    "page_role": "special-poster",
                    "provider_id": provider_id,
                    "adapter_id": "minimal-zine-v1",
                    "style_contract_sha256": style_sha,
                    "source_kind": "approved-source-image",
                    "output_class": "special-page-art",
                    "provider_transparency_behavior": "transparent-elements-or-approved-page-art",
                    "provider_aspect_ratio_behavior": "compose-for-approved-special-page",
                }
            )
            write_json(root, "asset-manifest.json", manifest)

            result = self.run_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("special_page_approval must be an object", result.stdout)

    def test_non_material_manifest_must_match_registered_output_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            provider_id = "gc-minimal-zine-poster-v0-3"
            style = json.loads((root / "style-contract.json").read_text(encoding="utf-8"))
            style["secondary_provider_roles"][provider_id] = ["special-poster"]
            style["explicit_visual_opt_ins"] = [provider_id]
            write_json(root, "style-contract.json", style)
            style_sha = hashlib.sha256((root / "style-contract.json").read_bytes()).hexdigest()

            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["style_anchors"]["approved_artifacts"][
                "style-contract.json"
            ] = style_sha
            write_json(root, "run-state.json", state)

            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            asset = manifest["assets"][0]
            asset.update(
                {
                    "role": "illustration",
                    "page_role": "special-poster",
                    "provider_id": provider_id,
                    "adapter_id": "minimal-zine-v1",
                    "source_kind": "approved-source-image",
                    "style_contract_sha256": style_sha,
                    "output_class": "post-release-social-card",
                    "provider_transparency_behavior": "required-real-alpha",
                    "provider_aspect_ratio_behavior": "one-component-per-transparent-canvas",
                }
            )
            write_json(root, "asset-manifest.json", manifest)

            result = self.run_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output_class does not match", result.stdout)
            self.assertIn("provider_transparency_behavior does not match", result.stdout)
            self.assertIn("provider_aspect_ratio_behavior does not match", result.stdout)

    def test_manifest_shell_fill_slots_must_be_safe_and_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            asset = manifest["assets"][0]
            asset.update(
                {
                    "role": "table-shell",
                    "content_policy": "blank-fill-slots",
                    "fill_slot_ids": [{"bad": "type"}, "F01", "F01"],
                    "prompt": build_material_prompt(
                        "table-shell", asset["reference_bbox"]
                    ),
                }
            )
            write_json(root, "asset-manifest.json", manifest)

            result = self.run_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("fill_slot_ids must be safe string ids", result.stdout)

            asset["fill_slot_ids"] = ["F01", "F01"]
            write_json(root, "asset-manifest.json", manifest)
            duplicate_result = self.run_validator(root, "inventory")
            self.assertIn("fill_slot_ids must be unique", duplicate_result.stdout)

    def test_manifest_provider_provenance_must_match_approved_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            asset = manifest["assets"][0]
            asset["style_contract_sha256"] = "c" * 64
            asset["references"][0]["sha256"] = "d" * 64
            write_json(root, "asset-manifest.json", manifest)

            result = self.run_validator(root, "inventory")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("style contract SHA-256", result.stdout)
            self.assertIn("approved reference SHA-256", result.stdout)

    def test_preserved_truth_sensitive_asset_does_not_require_visual_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            source = root / "sources" / "figure.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"approved-source-figure")
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            asset = manifest["assets"][0]
            for field in (
                "provider_id",
                "adapter_id",
                "page_role",
                "style_contract_version",
                "style_contract_sha256",
                "source_kind",
                "truth_sensitive",
                "deliverable_role",
                "prompt",
                "prompt_language",
                "references",
            ):
                asset.pop(field, None)
            asset.update(
                {
                    "role": "source-figure",
                    "strategy": "preserved-raster",
                    "editability": "fixed-evidence",
                    "source": "sources/figure.png",
                    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                }
            )
            write_json(root, "asset-manifest.json", manifest)

            result = self.run_validator(root, "inventory")

            self.assertEqual(result.returncode, 0, result.stdout)

    def test_story_stage_requires_alignment_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            (root / "alignment.json").unlink()

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn("alignment.json: required artifact is missing", result.stdout)

    def test_fast_route_requires_explicit_eligibility_and_current_g1_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["production_route"] = {
                "mode": "fast",
                "planning_artifacts": "skipped",
                "approval_phrase": "确认快速路线",
                "eligibility": {
                    "consequential_decisions_approved": False,
                    "high_stakes": False,
                    "multi_session": False,
                },
            }
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, "story")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("consequential decisions", result.stdout)

            state["production_route"]["eligibility"][
                "consequential_decisions_approved"
            ] = True
            state["gates"]["brief_authority"]["status"] = "pending"
            write_json(root, "run-state.json", state)
            pending_g1 = self.run_validator(root, "story")
            self.assertIn("current G1 approval", pending_g1.stdout)

    def test_fast_route_never_skips_human_gates_or_stage_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["production_route"] = {
                "mode": "fast",
                "planning_artifacts": "skipped",
                "approval_phrase": "确认快速路线",
                "eligibility": {
                    "consequential_decisions_approved": True,
                    "high_stakes": False,
                    "multi_session": False,
                },
            }
            write_json(root, "run-state.json", state)

            valid_fast = self.run_validator(root)
            self.assertEqual(valid_fast.returncode, 0, valid_fast.stdout)

            (root / "storyboard.json").unlink()
            missing_stage_artifact = self.run_validator(root, "story")
            self.assertIn("storyboard.json: required artifact is missing", missing_stage_artifact.stdout)

    def test_unresolved_critical_decision_blocks_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
            audience = next(item for item in alignment["decisions"] if item["id"] == "audience")
            audience.update(
                {
                    "status": "open",
                    "value": None,
                    "basis": None,
                    "independent": True,
                    "recommendation": {
                        "value": "department leaders",
                        "reason": "They approve the workflow.",
                        "impact": "The deck will emphasize decision evidence.",
                    },
                }
            )
            alignment["question_frontier"]["decision_ids"] = ["audience"]
            write_json(root, "alignment.json", alignment)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn("critical decision 'audience' is not resolved", result.stdout)

    def test_empty_critical_collection_blocks_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
            source_authority = next(
                item for item in alignment["decisions"] if item["id"] == "source_authority"
            )
            source_authority["value"] = []
            write_json(root, "alignment.json", alignment)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            gate = state["gates"]["brief_authority"]
            gate["approved_artifacts"]["alignment.json"] = hashlib.sha256(
                (root / "alignment.json").read_bytes()
            ).hexdigest()
            gate["decision_approvals"]["source_authority"]["value_sha256"] = value_sha256([])
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn("critical decision 'source_authority' is not resolved", result.stdout)

    def test_null_decision_list_reports_contract_errors_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
            alignment["decisions"] = None
            write_json(root, "alignment.json", alignment)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn("alignment decisions must be a list", result.stdout)

    def test_material_review_must_finish_before_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
            alignment["material_review"]["status"] = "pending"
            write_json(root, "alignment.json", alignment)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn("material_review.status must be 'completed'", result.stdout)

    def test_discovered_fact_is_not_reasked_on_question_frontier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
            alignment["question_frontier"]["decision_ids"] = ["audience"]
            write_json(root, "alignment.json", alignment)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn("discovered fact 'audience' cannot remain in question_frontier", result.stdout)

    def test_vague_batch_approval_phrase_does_not_approve_g1(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
            for decision in alignment["decisions"]:
                decision["basis"] = "recommended"
                decision["recommendation"] = {
                    "value": decision["value"],
                    "reason": f"Recommended for {decision['id']}.",
                    "impact": f"Sets the approved {decision['id']} boundary.",
                }
            alignment["approval_packet"]["recommendations_visible"] = True
            write_json(root, "alignment.json", alignment)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            gate = state["gates"]["brief_authority"]
            gate["approval_mode"] = "batch-recommendations"
            gate["approval_phrase"] = "按推荐"
            gate["approved_artifacts"]["alignment.json"] = hashlib.sha256(
                (root / "alignment.json").read_bytes()
            ).hexdigest()
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn("batch approval requires the exact phrase '全部按推荐'", result.stdout)

    def test_vague_recommendation_phrase_cannot_hide_in_explicit_mode(self):
        for phrase in ("按推荐", "全部按推荐"):
            with self.subTest(phrase=phrase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                make_valid_project(root)
                state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
                gate = state["gates"]["brief_authority"]
                gate["approval_mode"] = "explicit"
                gate["approval_phrase"] = phrase
                write_json(root, "run-state.json", state)

                result = self.run_validator(root, stage="story")

                self.assertEqual(result.returncode, 1)
                self.assertIn(
                    "explicit approval cannot use a recommendation shortcut", result.stdout
                )

    def test_complete_batch_recommendation_approval_advances_to_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
            for decision in alignment["decisions"]:
                decision["basis"] = "recommended"
                decision["recommendation"] = {
                    "value": decision["value"],
                    "reason": f"Recommended for {decision['id']}.",
                    "impact": f"Sets the approved {decision['id']} boundary.",
                }
            alignment["approval_packet"]["recommendations_visible"] = True
            write_json(root, "alignment.json", alignment)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            gate = state["gates"]["brief_authority"]
            gate["approval_mode"] = "batch-recommendations"
            gate["approval_phrase"] = "全部按推荐"
            gate["approved_artifacts"]["alignment.json"] = hashlib.sha256(
                (root / "alignment.json").read_bytes()
            ).hexdigest()
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_frontier_question_requires_recommendation_impact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
            decision = next(
                item for item in alignment["decisions"] if item["id"] == "delivery_form"
            )
            decision.update(
                {
                    "status": "ambiguous",
                    "value": None,
                    "basis": None,
                    "independent": True,
                    "recommendation": {
                        "value": ["component-library"],
                        "reason": "It preserves recombination.",
                        "impact": None,
                    },
                }
            )
            alignment["question_frontier"]["decision_ids"] = ["delivery_form"]
            write_json(root, "alignment.json", alignment)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "question_frontier decision 'delivery_form' needs recommendation impact",
                result.stdout,
            )

    def test_question_frontier_is_limited_to_five_independent_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
            selected = [
                "decision_goal",
                "source_authority",
                "truth_boundaries",
                "research_permission",
                "delivery_form",
                "editability_commitment",
            ]
            for decision in alignment["decisions"]:
                if decision["id"] not in selected:
                    continue
                decision.update(
                    {
                        "status": "open",
                        "value": None,
                        "basis": None,
                        "independent": True,
                        "recommendation": {
                            "value": "recommended-value",
                            "reason": "A bounded recommendation.",
                            "impact": "A declared consequence.",
                        },
                    }
                )
            alignment["question_frontier"]["decision_ids"] = selected
            write_json(root, "alignment.json", alignment)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn("question_frontier cannot contain more than 5 decisions", result.stdout)

    def test_question_frontier_uses_at_least_three_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
            selected = ["decision_goal", "source_authority", "truth_boundaries"]
            for decision in alignment["decisions"]:
                if decision["id"] not in selected:
                    continue
                decision.update(
                    {
                        "status": "open",
                        "value": None,
                        "basis": None,
                        "independent": True,
                        "recommendation": {
                            "value": "recommended-value",
                            "reason": "A bounded recommendation.",
                            "impact": "A declared consequence.",
                        },
                    }
                )
            alignment["question_frontier"]["decision_ids"] = ["decision_goal"]
            write_json(root, "alignment.json", alignment)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn("question_frontier must include at least 3 available decisions", result.stdout)

    def test_unresolved_low_risk_mechanic_does_not_block_story(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            alignment = json.loads((root / "alignment.json").read_text(encoding="utf-8"))
            alignment["decisions"].append(
                {
                    "id": "asset_file_naming",
                    "status": "open",
                    "value": None,
                    "basis": "agent-default",
                }
            )
            write_json(root, "alignment.json", alignment)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["brief_authority"]["approved_artifacts"]["alignment.json"] = (
                hashlib.sha256((root / "alignment.json").read_bytes()).hexdigest()
            )
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_table_or_chart_shell_cannot_embed_text_or_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0].update(
                {"role": "chart-shell", "content_policy": "embedded-data", "contains_text": True}
            )
            write_json(root, "asset-manifest.json", manifest)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("blank-fill-slots", result.stdout)

    def test_arrow_and_basic_shape_must_be_transparent_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0]["background_requirement"] = "opaque"
            write_json(root, "asset-manifest.json", manifest)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("transparent", result.stdout)

    def test_special_typography_requires_exact_text_and_human_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0].update({"role": "special-typography"})
            write_json(root, "asset-manifest.json", manifest)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("exact_text", result.stdout)
            self.assertIn("human_approved", result.stdout)

    def test_duplicate_ids_and_invalid_bbox_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            scene = json.loads((root / "scene-graph.json").read_text(encoding="utf-8"))
            scene["slides"][0]["elements"].append(
                {"instance_id": "I01", "component_id": "C01", "bbox": [0.9, 0.9, 0.2, 0.2], "z": 2}
            )
            write_json(root, "scene-graph.json", scene)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate instance_id", result.stdout)
            self.assertIn("bbox", result.stdout)

    def test_non_string_component_ids_report_error_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
            deck["slides"][0]["components"] = [{"id": "C01"}]
            write_json(root, "deck-spec.json", deck)

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("component IDs must be non-empty strings", result.stdout)

    def test_non_string_record_id_reports_error_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            scene = json.loads((root / "scene-graph.json").read_text(encoding="utf-8"))
            scene["slides"][0]["elements"][0]["instance_id"] = ["I01"]
            write_json(root, "scene-graph.json", scene)

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("instance_id must be a non-empty string", result.stdout)

    def test_asset_hash_and_png_content_are_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            (root / "assets" / "S01" / "C01.png").write_bytes(b"not-a-png")
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("SHA-256", result.stdout)
            self.assertIn("valid PNG", result.stdout)

    def test_drive_relative_path_cannot_escape_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0]["output"] = "D:outside.png"
            write_json(root, "asset-manifest.json", manifest)

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("must stay inside the project directory", result.stdout)

    def test_special_typography_requires_language_and_passed_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0].update(
                {
                    "role": "special-typography",
                    "exact_text": "精确文字",
                    "human_approved": True,
                }
            )
            write_json(root, "asset-manifest.json", manifest)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("language", result.stdout)
            self.assertIn("ocr_result", result.stdout)

    def test_table_shell_requires_explicit_false_content_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0].update(
                {"role": "table-shell", "content_policy": "blank-fill-slots"}
            )
            manifest["assets"][0].pop("contains_text", None)
            manifest["assets"][0].pop("contains_data", None)
            write_json(root, "asset-manifest.json", manifest)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("contains_text=false", result.stdout)
            self.assertIn("contains_data=false", result.stdout)

    def test_chart_shell_cannot_contain_data_encoding_marks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0].update(
                {
                    "role": "chart-shell",
                    "content_policy": "blank-fill-slots",
                    "contains_text": False,
                    "contains_data": False,
                    "contains_data_encoding_marks": True,
                    "fill_slot_ids": ["F01"],
                }
            )
            write_json(root, "asset-manifest.json", manifest)

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("contains_data_encoding_marks=false", result.stdout)

    def test_assembly_must_cover_every_component_and_fill_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            assembly = json.loads((root / "assembly-map.json").read_text(encoding="utf-8"))
            assembly["slides"][0]["fill_slot_ids"] = []
            write_json(root, "assembly-map.json", assembly)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("fill_slot", result.stdout)

    def test_release_gates_require_approval_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["release"] = "approved"
            write_json(root, "run-state.json", state)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("approver", result.stdout)
            self.assertIn("approved_at", result.stdout)

    def test_g2_requires_complete_story_approval_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["story"].pop("approval_packet")
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="style")

            self.assertEqual(result.returncode, 1)
            self.assertIn("story approval_packet must be an object", result.stdout)

    def test_g2_batch_approval_requires_exact_phrase_and_visible_recommendations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            gate = state["gates"]["story"]
            gate["approval_mode"] = "batch-recommendations"
            gate["approval_phrase"] = "按推荐"
            gate["approval_packet"]["recommendations_visible"] = True
            for decision in gate["approval_packet"]["decisions"].values():
                decision["recommendation"] = {
                    "value": decision["value"],
                    "reason": "Recommended story decision.",
                    "impact": "Locks the corresponding narrative choice.",
                }
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="style")

            self.assertEqual(result.returncode, 1)
            self.assertIn("batch approval requires the exact phrase '全部按推荐'", result.stdout)

    def test_g2_batch_approval_requires_current_value_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            gate = state["gates"]["story"]
            gate["approval_mode"] = "batch-recommendations"
            gate["approval_phrase"] = "全部按推荐"
            gate["approval_packet"]["recommendations_visible"] = True
            for decision in gate["approval_packet"]["decisions"].values():
                decision.pop("value_sha256")
                decision["recommendation"] = {
                    "value": decision["value"],
                    "reason": "Recommended story decision.",
                    "impact": "Locks the corresponding narrative choice.",
                }
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="style")

            self.assertEqual(result.returncode, 1)
            self.assertIn("approval value hash is stale", result.stdout)

    def test_g2_packet_values_must_match_storyboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            decision = state["gates"]["story"]["approval_packet"]["decisions"][
                "action_titles"
            ]
            decision["value"] = {"S01": "Invented title"}
            decision["value_sha256"] = value_sha256(decision["value"])
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="style")

            self.assertEqual(result.returncode, 1)
            self.assertIn("approval_packet value differs from current artifacts", result.stdout)

    def test_g2_to_g4_packets_must_cover_every_stage_decision(self):
        cases = (
            ("story", "style", "slide_sequence"),
            ("style_anchors", "concept", "visual_direction"),
            ("concept_contact_sheet", "inventory", "full_deck_contact_sheet"),
        )
        for gate_name, stage, removed_decision in cases:
            with self.subTest(gate=gate_name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                make_valid_project(root)
                state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
                state["gates"][gate_name]["approval_packet"]["decisions"].pop(
                    removed_decision
                )
                write_json(root, "run-state.json", state)

                result = self.run_validator(root, stage=stage)

                self.assertEqual(result.returncode, 1)
                self.assertIn("approval_packet must cover", result.stdout)

    def test_g5_does_not_inherit_batch_recommendation_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            release = state["gates"]["release"]
            release["approval_mode"] = "batch-recommendations"
            release["approval_phrase"] = "全部按推荐"
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="release")

            self.assertEqual(result.returncode, 1)
            self.assertIn("release approval_mode must be 'release'", result.stdout)
            self.assertIn("release requires the exact phrase '确认发布'", result.stdout)

    def test_g5_requires_hashes_for_every_presented_release_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            approved = state["gates"]["release"]["approved_artifacts"]
            for path in (
                "qa/S01-overlay.png",
                "qa/final-contact-sheet.png",
                "qa/exception-register.json",
                "qa/deliverable-index.json",
            ):
                approved.pop(path)
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="release")

            self.assertEqual(result.returncode, 1)
            self.assertIn("qa/final-contact-sheet.png", result.stdout)

    def test_qa_defect_cannot_roll_back_to_unrelated_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["stage"] = "intake"
            state["rollback"] = {
                "trigger": "qa-defect",
                "defect_class": "asset",
                "owner_stage": "intake",
                "reason": "Transparent asset alpha check failed.",
            }
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="assets")

            self.assertEqual(result.returncode, 1)
            self.assertIn("rollback owner_stage must be 'assets'", result.stdout)

    def test_rejected_gate_requires_rollback_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["stage"] = "style"
            state["gates"]["concept_contact_sheet"]["status"] = "rejected"
            state["rollback"] = None
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="style")

            self.assertEqual(result.returncode, 1)
            self.assertIn("rejected gate requires a rollback record", result.stdout)

    def test_rejection_rolls_back_only_to_gate_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["stage"] = "story"
            rejected_gate = state["gates"]["story"]
            rejected_gate["status"] = "rejected"
            rejected_gate["artifact_version"] = None
            rejected_gate["approved_artifacts"] = {}
            rejected_gate["approval_packet"] = None
            state["artifact_versions"].pop("story")
            state["rollback"] = {
                "trigger": "rejection",
                "source_gate": "story",
                "owner_stage": "story",
                "reason": "Slide sequence needs revision.",
            }
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejection_cannot_retain_an_approved_gate_epoch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["stage"] = "story"
            state["gates"]["story"]["status"] = "rejected"
            state["rollback"] = {
                "trigger": "rejection",
                "source_gate": "story",
                "owner_stage": "story",
                "reason": "Slide sequence needs revision.",
            }
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn("rejected gate must clear its prior approval epoch", result.stdout)

    def test_rejected_gate_cannot_use_qa_defect_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["stage"] = "story"
            rejected_gate = state["gates"]["story"]
            rejected_gate["status"] = "rejected"
            rejected_gate["artifact_version"] = None
            rejected_gate["approved_artifacts"] = {}
            rejected_gate["approval_packet"] = None
            state["artifact_versions"].pop("story")
            state["rollback"] = {
                "trigger": "qa-defect",
                "defect_class": "story",
                "owner_stage": "story",
                "reason": "This is a gate rejection, not a QA defect.",
            }
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="story")

            self.assertEqual(result.returncode, 1)
            self.assertIn("rejected gates require trigger 'rejection'", result.stdout)

    def test_malformed_rollback_fields_report_errors_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["stage"] = "assets"
            state["rollback"] = {
                "trigger": "qa-defect",
                "defect_class": ["asset"],
                "owner_stage": "assets",
                "reason": "Bad alpha.",
            }
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="assets")

            self.assertEqual(result.returncode, 1)
            self.assertIn("defect_class must be a non-empty string", result.stdout)

    def test_failed_qa_requires_qa_defect_rollback_even_after_stage_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            qa = json.loads((root / "qa-report.json").read_text(encoding="utf-8"))
            qa["status"] = "failed"
            qa["slides"][0]["status"] = "failed"
            write_json(root, "qa-report.json", qa)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["stage"] = "assets"
            state["rollback"] = None
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="assets")

            self.assertEqual(result.returncode, 1)
            self.assertIn("failed QA requires a rollback record", result.stdout)

    def test_approval_metadata_requires_iso_time_and_string_phrase(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            story = state["gates"]["story"]
            story["approved_at"] = "not-a-time"
            story["approval_phrase"] = {"status": "approved"}
            write_json(root, "run-state.json", state)

            result = self.run_validator(root, stage="style")

            self.assertEqual(result.returncode, 1)
            self.assertIn("approved_at must be ISO-8601", result.stdout)
            self.assertIn("approval_phrase must be a non-empty string", result.stdout)

    def test_story_change_invalidates_g2_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            storyboard = json.loads((root / "storyboard.json").read_text(encoding="utf-8"))
            storyboard["slides"][0]["title"] = "A changed action title"
            write_json(root, "storyboard.json", storyboard)

            result = self.run_validator(root, stage="style")

            self.assertEqual(result.returncode, 1)
            self.assertIn("approved artifact hash is stale: storyboard.json", result.stdout)

    def test_qa_requires_named_checks_and_evidence_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            qa = json.loads((root / "qa-report.json").read_text(encoding="utf-8"))
            qa.pop("checks_performed")
            qa.pop("evidence_files")
            write_json(root, "qa-report.json", qa)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("checks_performed", result.stdout)
            self.assertIn("evidence_files", result.stdout)

    def test_asset_stage_requires_verified_transparency_capability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            report = json.loads((root / "capability-report.json").read_text(encoding="utf-8"))
            report["transparent_output"]["status"] = "unverified"
            write_json(root, "capability-report.json", report)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("transparent_output.status", result.stdout)

    def test_component_estimate_must_stay_within_approved_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
            deck["production_estimate"]["unique_components"] = 50
            write_json(root, "deck-spec.json", deck)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("component_limit", result.stdout)

    def test_mixed_timezone_deadline_reports_error_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            brief = json.loads((root / "brief.json").read_text(encoding="utf-8"))
            brief["capacity_budget"]["deadline"] = "2026-09-24T18:00:00+08:00"
            write_json(root, "brief.json", brief)
            deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
            deck["production_estimate"]["estimated_completion"] = "2026-09-24T12:00:00"
            write_json(root, "deck-spec.json", deck)

            result = self.run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("same timezone-awareness policy", result.stdout)

    def test_pptx_delivery_requires_a_real_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            brief = json.loads((root / "brief.json").read_text(encoding="utf-8"))
            brief["delivery"]["formats"].append("pptx")
            write_json(root, "brief.json", brief)
            capability = json.loads((root / "capability-report.json").read_text(encoding="utf-8"))
            capability["assembly"] = {"status": "verified", "backend": "presentations"}
            write_json(root, "capability-report.json", capability)
            assembly = json.loads((root / "assembly-map.json").read_text(encoding="utf-8"))
            assembly["backend"] = "presentations"
            write_json(root, "assembly-map.json", assembly)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("PPTX output", result.stdout)

    def test_pptx_cannot_embed_the_concept_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            brief = json.loads((root / "brief.json").read_text(encoding="utf-8"))
            brief["delivery"]["formats"].append("pptx")
            write_json(root, "brief.json", brief)
            capability = json.loads((root / "capability-report.json").read_text(encoding="utf-8"))
            capability["assembly"] = {"status": "verified", "backend": "presentations"}
            write_json(root, "capability-report.json", capability)
            pptx = root / "release" / "deck.pptx"
            pptx.parent.mkdir(parents=True)
            with zipfile.ZipFile(pptx, "w") as archive:
                archive.writestr("ppt/slides/slide1.xml", "<p:sld/>")
                archive.write(root / "concepts" / "S01.png", "ppt/media/image1.png")
            pptx_sha = hashlib.sha256(pptx.read_bytes()).hexdigest()
            assembly = json.loads((root / "assembly-map.json").read_text(encoding="utf-8"))
            assembly.update({"backend": "presentations", "output": "release/deck.pptx", "sha256": pptx_sha})
            write_json(root, "assembly-map.json", assembly)
            qa = json.loads((root / "qa-report.json").read_text(encoding="utf-8"))
            qa["subject_sha256"] = pptx_sha
            write_json(root, "qa-report.json", qa)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("concept render", result.stdout)

    def test_story_evidence_ids_must_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            story = json.loads((root / "storyboard.json").read_text(encoding="utf-8"))
            story["slides"][0]["evidence_ids"] = ["UNKNOWN"]
            write_json(root, "storyboard.json", story)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown evidence_id", result.stdout)

    def test_fixed_evidence_must_match_its_source_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            source = root / "sources" / "figure.png"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"original-factual-image")
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0].update(
                {
                    "role": "source-figure",
                    "strategy": "preserved-raster",
                    "editability": "fixed-evidence",
                    "source": "sources/figure.png",
                    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                }
            )
            write_json(root, "asset-manifest.json", manifest)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("preserved output must match", result.stdout)

    def test_png_route_cannot_claim_internal_vector_editability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            brief = json.loads((root / "brief.json").read_text(encoding="utf-8"))
            brief["editability"]["internal_vector_paths"] = True
            write_json(root, "brief.json", brief)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("internal_vector_paths", result.stdout)

    def test_approval_is_invalidated_when_an_artifact_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            story = json.loads((root / "storyboard.json").read_text(encoding="utf-8"))
            story["slides"][0]["title"] = "Changed after approval"
            write_json(root, "storyboard.json", story)
            result = self.run_validator(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("approved artifact hash", result.stdout)

    def test_public_style_entry_requires_readability_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            style = json.loads((root / "style-contract.json").read_text(encoding="utf-8"))
            style.pop("readability_profile")
            write_json(root, "style-contract.json", style)
            result = self.run_public_validator(root, "style")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("readability_profile", result.stdout)

    def test_public_spec_entry_requires_per_slide_readability_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
            deck["slides"][0].pop("readability")
            write_json(root, "deck-spec.json", deck)
            result = self.run_public_validator(root, "spec")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("readability", result.stdout)

    def test_public_spec_entry_rejects_small_title_without_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
            deck["slides"][0]["readability"]["text_regions"][0]["planned_font_pt"] = 18
            write_json(root, "deck-spec.json", deck)
            result = self.run_public_validator(root, "spec")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("font:F01", result.stdout)

    def test_public_spec_entry_rejects_tiny_main_picture_without_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
            deck["slides"][0]["readability"]["main_visual"]["bbox"] = [0.7, 0.7, 0.1, 0.1]
            write_json(root, "deck-spec.json", deck)
            result = self.run_public_validator(root, "spec")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("visual:main", result.stdout)

    def test_public_spec_entry_rejects_unbacked_evidence_area(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
            deck["slides"][0]["fill_slots"].append(
                {"id": "F-EVIDENCE", "kind": "fixed-evidence", "bbox": [0.50, 0.25, 0.20, 0.20]}
            )
            deck["slides"][0]["readability"]["main_visual"] = {
                "kind": "evidence", "bbox": [0.45, 0.25, 0.45, 0.50]
            }
            write_json(root, "deck-spec.json", deck)
            result = self.run_public_validator(root, "spec")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("fixed-evidence fill slot", result.stdout)

    def test_public_spec_entry_accepts_specific_readability_exception_for_planning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
            plan = deck["slides"][0]["readability"]
            plan["text_regions"][0]["planned_font_pt"] = 18
            plan["exception"] = {
                "violations": ["font:F01"],
                "reason": "A legacy title must be quoted without changing its wording.",
                "alternative_viewing_route": "Show the full-size handout before the slide.",
            }
            write_json(root, "deck-spec.json", deck)
            result = self.run_public_validator(root, "spec")
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_public_concept_entry_requires_full_size_review_bound_to_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            deck = json.loads((root / "deck-spec.json").read_text(encoding="utf-8"))
            deck["slides"][0]["readability"]["full_size_review"] = None
            write_json(root, "deck-spec.json", deck)
            result = self.run_public_validator(root, "concept")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("full_size_review", result.stdout)

    def test_public_inventory_entry_requires_g4_readability_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["concept_contact_sheet"]["approval_packet"]["decisions"].pop("readability_review")
            write_json(root, "run-state.json", state)
            result = self.run_public_validator(root, "inventory")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("readability_review", result.stdout)

    def test_public_concept_entry_requires_g3_readability_profile_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["style_anchors"]["approval_packet"]["decisions"].pop("readability_profile", None)
            write_json(root, "run-state.json", state)
            result = self.run_public_validator(root, "concept")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("readability_profile", result.stdout)

    def test_production_release_requires_full_size_readability_qa(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            qa = json.loads((root / "qa-report.json").read_text(encoding="utf-8"))
            qa["checks_performed"].remove("readability-full-size")
            write_json(root, "qa-report.json", qa)
            result = self.run_public_validator(root, "release")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("readability-full-size", result.stdout)


if __name__ == "__main__":
    unittest.main()
