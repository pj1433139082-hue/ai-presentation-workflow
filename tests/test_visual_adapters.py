import importlib.util
import io
import json
import sys
import tempfile
import unittest
import hashlib
import zipfile
from contextlib import contextmanager, redirect_stderr
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "visual_adapters.py"
MODULE_SPEC = importlib.util.spec_from_file_location("visual_adapters", SCRIPT)
ADAPTERS = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(ADAPTERS)

REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "project-template"
    / "visual-provider-registry.json"
)


def value_sha256(value):
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def write_minimal_pptx(path, slide_relationship_type="slide", target_mode=None):
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>"""
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>"""
    presentation = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
</p:presentation>"""
    target_mode_attribute = f' TargetMode="{target_mode}"' if target_mode else ""
    presentation_rels = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{slide_relationship_type}" Target="slides/slide1.xml"{target_mode_attribute}/>
</Relationships>"""
    slide = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", presentation_rels)
        archive.writestr("ppt/slides/slide1.xml", slide)
STYLE_SHA = "a" * 64
REFERENCE_SHA = "b" * 64


def approved_context(reference_path):
    return {
        "style_contract_version": "v3",
        "approved_style_contract": {
            "artifact": "style-contract.json",
            "version": "v3",
            "sha256": STYLE_SHA,
            "approval_gate": "style_anchors",
        },
        "approved_references": [
            {
                "path": reference_path,
                "sha256": REFERENCE_SHA,
                "approval_gate": "concept_contact_sheet",
            }
        ],
    }


@contextmanager
def approved_project(request):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        approved_style = request["approved_style_contract"]
        style_payload = {
            "version": approved_style["version"],
            "direction": "approved test style",
        }
        style_path = root / "style-contract.json"
        style_path.write_text(json.dumps(style_payload), encoding="utf-8")
        style_sha = hashlib.sha256(style_path.read_bytes()).hexdigest()
        approved_style["sha256"] = style_sha

        concept_artifacts = {}
        for index, record in enumerate(request["approved_references"]):
            path = root / Path(*Path(record["path"]).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"approved-concept-{index}".encode("utf-8"))
            reference_sha = hashlib.sha256(path.read_bytes()).hexdigest()
            record["sha256"] = reference_sha
            concept_artifacts[record["path"]] = reference_sha
        (root / "run-state.json").write_text(
            json.dumps(
                {
                    "gates": {
                        "style_anchors": {
                            "status": "approved",
                            "artifact_version": approved_style["version"],
                            "approved_artifacts": {
                                "style-contract.json": style_sha
                            },
                        },
                        "concept_contact_sheet": {
                            "status": "approved",
                            "artifact_version": "v3",
                            "approved_artifacts": concept_artifacts,
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        yield root


@contextmanager
def photo_rights_project():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "sources" / "photo.png"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"ordinary-photo")
        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        rights = root / "rights" / "photo-rights.json"
        rights.parent.mkdir(parents=True, exist_ok=True)
        rights.write_text(
            json.dumps(
                {
                    "status": "confirmed",
                    "approval_phrase": "确认素材使用权",
                    "confirmed_by": "test-user",
                    "source_path": "sources/photo.png",
                    "source_sha256": source_sha,
                }
            ),
            encoding="utf-8",
        )
        rights_sha = hashlib.sha256(rights.read_bytes()).hexdigest()
        (root / "run-state.json").write_text(
            json.dumps(
                {
                    "artifact_versions": {"brief_authority": "v1"},
                    "gates": {
                        "brief_authority": {
                            "status": "approved",
                            "artifact_version": "v1",
                            "approved_artifacts": {
                                "rights/photo-rights.json": rights_sha
                            },
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        yield root, {
            "path": "rights/photo-rights.json",
            "sha256": rights_sha,
        }


@contextmanager
def special_page_project(provider_id, page_role, slide_id="S01"):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        approval = root / "approvals" / f"{slide_id}-special-page.json"
        approval.parent.mkdir(parents=True, exist_ok=True)
        approval.write_text(
            json.dumps(
                {
                    "status": "approved",
                    "approval_phrase": "确认特殊页面风格",
                    "provider_id": provider_id,
                    "page_role": page_role,
                    "slide_id": slide_id,
                }
            ),
            encoding="utf-8",
        )
        approval_sha = hashlib.sha256(approval.read_bytes()).hexdigest()
        (root / "run-state.json").write_text(
            json.dumps(
                {
                    "artifact_versions": {"concept_contact_sheet": "v4"},
                    "gates": {
                        "concept_contact_sheet": {
                            "status": "approved",
                            "artifact_version": "v4",
                            "approved_artifacts": {
                                f"approvals/{slide_id}-special-page.json": approval_sha
                            },
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        yield root, {
            "path": f"approvals/{slide_id}-special-page.json",
            "sha256": approval_sha,
        }


@contextmanager
def released_project():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        deck = root / "deliverables" / "deck.pptx"
        deck.parent.mkdir(parents=True, exist_ok=True)
        write_minimal_pptx(deck)
        deck_sha = hashlib.sha256(deck.read_bytes()).hexdigest()
        brief = root / "derivatives" / "social-card-brief.json"
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text(
            json.dumps(
                {
                    "source_deck_sha256": deck_sha,
                    "format": "approved-social-card",
                }
            ),
            encoding="utf-8",
        )
        brief_sha = hashlib.sha256(brief.read_bytes()).hexdigest()
        supporting = {
            "asset-manifest.json": b'{"assets":[]}',
            "qa/final-contact-sheet.png": b"contact-sheet",
            "qa/exception-register.json": b'{"exceptions":[]}',
            "qa/deliverable-index.json": b'{"status":"released"}',
            "qa/S01-overlay.png": b"overlay",
        }
        for relative_path, content in supporting.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        assembly = root / "assembly-map.json"
        assembly.write_text(
            json.dumps(
                {
                    "output": "deliverables/deck.pptx",
                    "sha256": deck_sha,
                    "slides": [
                        {
                            "slide_id": "S01",
                            "component_ids": [],
                            "fill_slot_ids": [],
                            "flattened_concept_used": False,
                            "output_index": 1,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        qa_report = root / "qa-report.json"
        qa_report.write_text(
            json.dumps(
                {
                    "status": "passed",
                    "checks_performed": [
                        "contract",
                        "inventory",
                        "alpha",
                        "overlay",
                    ],
                    "subject_sha256": deck_sha,
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
                            "evidence_files": ["qa/S01-overlay.png"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        approved_paths = [
            *supporting,
            "assembly-map.json",
            "qa-report.json",
            "deliverables/deck.pptx",
        ]
        approved_artifacts = {
            relative_path: hashlib.sha256((root / relative_path).read_bytes()).hexdigest()
            for relative_path in approved_paths
        }
        decision_values = {
            "final_render": {
                "contact_sheet": "qa/final-contact-sheet.png",
                "evidence_files": ["qa/S01-overlay.png"],
            },
            "concept_differences": {"items": []},
            "qa_exceptions": {
                "items": [],
                "register": "qa/exception-register.json",
            },
            "component_usability": {
                "S01": {"component_ids": [], "fill_slot_ids": []}
            },
            "deliverable_index": {
                "path": "qa/deliverable-index.json",
                "asset_outputs": [],
            },
        }
        decisions = {
            decision_id: {
                "status": "approved",
                "value": value,
                "value_sha256": value_sha256(value),
            }
            for decision_id, value in decision_values.items()
        }
        (root / "run-state.json").write_text(
            json.dumps(
                {
                    "stage": "released",
                    "artifact_versions": {"release": "v5"},
                    "gates": {
                        "release": {
                            "status": "approved",
                            "approval_mode": "release",
                            "approval_phrase": "确认发布",
                            "approver": "release-owner",
                            "approved_at": "2026-09-24T12:00:00+08:00",
                            "artifact_version": "v5",
                            "approval_packet": {
                                "gate": "release",
                                "version": "v5",
                                "decisions": decisions,
                            },
                            "approved_artifacts": approved_artifacts,
                        }
                    },
                    "post_release_derivatives": {
                        "guizang-social-card-skill": {
                            "status": "approved",
                            "approval_phrase": "确认社交卡衍生",
                            "approver": "release-owner",
                            "approved_at": "2026-09-24T12:30:00+08:00",
                            "source_deck_sha256": deck_sha,
                            "approved_artifacts": {
                                "derivatives/social-card-brief.json": brief_sha
                            },
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        yield root, {
            "released_deck": {
                "path": "deliverables/deck.pptx",
                "sha256": deck_sha,
            },
            "approved_derivative_brief": {
                "path": "derivatives/social-card-brief.json",
                "sha256": brief_sha,
            },
        }


class VisualAdapterTests(unittest.TestCase):
    def test_registry_exposes_seven_providers_and_only_three_auto_routes(self):
        registry = ADAPTERS.load_registry(REGISTRY)

        self.assertEqual(
            set(registry),
            {
                "guizang-material-illustration",
                "photo-postprocess-coach",
                "scene-distillation-zine-v1-3",
                "gc-minimal-zine-poster-v0-3",
                "scenes-gathered-zine-v1-3",
                "surreal-pop-collage",
                "guizang-social-card-skill",
            },
        )
        auto_routes = {
            provider_id
            for provider_id, provider in registry.items()
            if provider["auto_route"]
        }
        self.assertEqual(
            auto_routes,
            {
                "guizang-material-illustration",
                "photo-postprocess-coach",
                "scene-distillation-zine-v1-3",
            },
        )

    def test_auto_route_uses_only_role_compatible_core_providers(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        style = {
            "primary_visual_family": "guizang-material-illustration",
            "secondary_provider_roles": {
                "photo-postprocess-coach": ["ordinary-photo"],
                "scene-distillation-zine-v1-3": ["opening"],
            },
            "explicit_visual_opt_ins": [],
        }

        material = ADAPTERS.route_provider(
            registry,
            {
                "page_role": "structural-diagram",
                "source_kind": "approved-concept-render",
                "truth_sensitive": False,
                "deliverable_role": "slide-asset",
            },
            style,
        )
        with photo_rights_project() as (root, rights):
            photo = ADAPTERS.route_provider(
                registry,
                {
                    "page_role": "ordinary-photo",
                    "source_kind": "ordinary-photo",
                    "truth_sensitive": False,
                    "deliverable_role": "slide-asset",
                    "source_rights_confirmation": rights,
                },
                style,
                project_root=root,
            )
        scene = ADAPTERS.route_provider(
            registry,
            {
                "page_role": "opening",
                "source_kind": "approved-source-scene",
                "truth_sensitive": False,
                "deliverable_role": "slide-asset",
            },
            style,
        )

        self.assertEqual(material["id"], "guizang-material-illustration")
        self.assertEqual(photo["id"], "photo-postprocess-coach")
        self.assertEqual(scene["id"], "scene-distillation-zine-v1-3")

    def test_photo_route_rejects_product_screenshots_data_evidence_and_reports(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        style = {
            "primary_visual_family": "photo-postprocess-coach",
            "secondary_provider_roles": {},
            "explicit_visual_opt_ins": [],
        }
        base = {
            "provider_id": "photo-postprocess-coach",
            "page_role": "ordinary-photo",
            "truth_sensitive": True,
            "deliverable_role": "slide-asset",
        }

        for source_kind in ("product-screenshot", "data-evidence", "report"):
            with self.subTest(source_kind=source_kind):
                with self.assertRaisesRegex(ADAPTERS.AdapterError, "cannot process source kind"):
                    ADAPTERS.route_provider(
                        registry, dict(base, source_kind=source_kind), style
                    )

    def test_reinterpretive_provider_rejects_truth_sensitive_visuals(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        style = {
            "primary_visual_family": "scene-distillation-zine-v1-3",
            "secondary_provider_roles": {},
            "explicit_visual_opt_ins": [],
        }
        request = {
            "provider_id": "scene-distillation-zine-v1-3",
            "page_role": "opening",
            "source_kind": "approved-source-scene",
            "truth_sensitive": True,
            "deliverable_role": "slide-asset",
        }

        with self.assertRaisesRegex(ADAPTERS.AdapterError, "rejects truth-sensitive"):
            ADAPTERS.route_provider(registry, request, style)

    def test_strong_style_provider_requires_explicit_opt_in(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        cases = (
            (
                "gc-minimal-zine-poster-v0-3",
                "section-opener",
                "approved-source-image",
            ),
            (
                "scenes-gathered-zine-v1-3",
                "editorial-montage",
                "approved-source-scenes",
            ),
            ("surreal-pop-collage", "creative-opener", "approved-source-image"),
        )
        for provider_id, page_role, source_kind in cases:
            with self.subTest(provider_id=provider_id):
                request = {
                    "provider_id": provider_id,
                    "slide_id": "S01",
                    "page_role": page_role,
                    "source_kind": source_kind,
                    "truth_sensitive": False,
                    "deliverable_role": "slide-asset",
                }
                style = {
                    "primary_visual_family": "guizang-material-illustration",
                    "secondary_provider_roles": {provider_id: [page_role]},
                    "explicit_visual_opt_ins": [],
                }

                with self.assertRaisesRegex(ADAPTERS.AdapterError, "explicit opt-in"):
                    ADAPTERS.route_provider(registry, request, style)

                style["explicit_visual_opt_ins"] = [provider_id]
                with special_page_project(provider_id, page_role) as (root, approval):
                    request["special_page_approval"] = approval
                    selected = ADAPTERS.route_provider(
                        registry, request, style, project_root=root
                    )
                self.assertEqual(selected["id"], provider_id)

    def test_explicit_style_provider_requires_slide_bound_approval(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        provider_id = "gc-minimal-zine-poster-v0-3"
        page_role = "special-poster"
        style = {
            "primary_visual_family": "guizang-material-illustration",
            "secondary_provider_roles": {provider_id: [page_role]},
            "explicit_visual_opt_ins": [provider_id],
        }
        request = {
            "provider_id": provider_id,
            "page_role": page_role,
            "source_kind": "approved-source-image",
            "truth_sensitive": False,
            "deliverable_role": "slide-asset",
        }
        with special_page_project(provider_id, page_role) as (root, approval):
            request["special_page_approval"] = approval
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "safe non-empty slide_id"):
                ADAPTERS.route_provider(
                    registry, request, style, project_root=root
                )

    def test_social_card_is_release_only_derivative_not_slide_renderer(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        style = {
            "primary_visual_family": "guizang-material-illustration",
            "secondary_provider_roles": {},
            "explicit_visual_opt_ins": [],
        }
        base = {
            "provider_id": "guizang-social-card-skill",
            "page_role": "post-release-social-card",
            "source_kind": "released-deck",
            "truth_sensitive": False,
            "deck_released": True,
        }

        with self.assertRaisesRegex(ADAPTERS.AdapterError, "post-release derivative"):
            ADAPTERS.route_provider(
                registry, dict(base, deliverable_role="slide-asset"), style
            )
        with self.assertRaisesRegex(ADAPTERS.AdapterError, "released deck"):
            ADAPTERS.route_provider(
                registry,
                dict(base, deliverable_role="post-release-derivative", deck_released=False),
                style,
            )
        with self.assertRaisesRegex(ADAPTERS.AdapterError, "verified G5"):
            ADAPTERS.route_provider(
                registry, dict(base, deliverable_role="post-release-derivative"), style
            )
        with released_project() as (root, release_evidence):
            selected = ADAPTERS.route_provider(
                registry,
                dict(
                    base,
                    deliverable_role="post-release-derivative",
                    **release_evidence,
                ),
                style,
                project_root=root,
            )
        self.assertEqual(selected["id"], "guizang-social-card-skill")

    def test_social_card_requires_human_approved_derivative_brief(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        style = {
            "primary_visual_family": "guizang-material-illustration",
            "secondary_provider_roles": {},
            "explicit_visual_opt_ins": [],
        }
        with released_project() as (root, release_evidence):
            state_path = root / "run-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state.pop("post_release_derivatives")
            state_path.write_text(json.dumps(state), encoding="utf-8")
            request = {
                "provider_id": "guizang-social-card-skill",
                "page_role": "post-release-social-card",
                "source_kind": "released-deck",
                "truth_sensitive": False,
                "deck_released": True,
                "deliverable_role": "post-release-derivative",
                **release_evidence,
            }
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "human approval"):
                ADAPTERS.route_provider(
                    registry, request, style, project_root=root
                )

    def test_social_card_requires_release_identity_and_current_decision_values(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        style = {
            "primary_visual_family": "guizang-material-illustration",
            "secondary_provider_roles": {},
            "explicit_visual_opt_ins": [],
        }
        base = {
            "provider_id": "guizang-social-card-skill",
            "page_role": "post-release-social-card",
            "source_kind": "released-deck",
            "truth_sensitive": False,
            "deck_released": True,
            "deliverable_role": "post-release-derivative",
        }
        with released_project() as (root, release_evidence):
            state_path = root / "run-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["gates"]["release"].pop("approver")
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "non-empty approver"):
                ADAPTERS.route_provider(
                    registry,
                    dict(base, **release_evidence),
                    style,
                    project_root=root,
                )

        with released_project() as (root, release_evidence):
            state_path = root / "run-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            decision = state["gates"]["release"]["approval_packet"]["decisions"][
                "final_render"
            ]
            decision["value"] = {"contact_sheet": "invented.png"}
            decision["value_sha256"] = value_sha256(decision["value"])
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "differs from current artifacts"):
                ADAPTERS.route_provider(
                    registry,
                    dict(base, **release_evidence),
                    style,
                    project_root=root,
                )

    def test_social_card_binds_deck_to_assembly_and_qa_subject(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        style = {
            "primary_visual_family": "guizang-material-illustration",
            "secondary_provider_roles": {},
            "explicit_visual_opt_ins": [],
        }
        base = {
            "provider_id": "guizang-social-card-skill",
            "page_role": "post-release-social-card",
            "source_kind": "released-deck",
            "truth_sensitive": False,
            "deck_released": True,
            "deliverable_role": "post-release-derivative",
        }
        with released_project() as (root, release_evidence):
            alternate = root / "deliverables" / "alternate.pptx"
            alternate.write_bytes((root / "deliverables" / "deck.pptx").read_bytes())
            alternate_sha = hashlib.sha256(alternate.read_bytes()).hexdigest()
            state_path = root / "run-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["gates"]["release"]["approved_artifacts"][
                "deliverables/alternate.pptx"
            ] = alternate_sha
            state_path.write_text(json.dumps(state), encoding="utf-8")
            alternate_evidence = dict(release_evidence)
            alternate_evidence["released_deck"] = {
                "path": "deliverables/alternate.pptx",
                "sha256": alternate_sha,
            }
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "assembly output"):
                ADAPTERS.route_provider(
                    registry,
                    dict(base, **alternate_evidence),
                    style,
                    project_root=root,
                )

        with released_project() as (root, release_evidence):
            qa_path = root / "qa-report.json"
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            qa["subject_sha256"] = "0" * 64
            qa_path.write_text(json.dumps(qa), encoding="utf-8")
            state_path = root / "run-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["gates"]["release"]["approved_artifacts"][
                "qa-report.json"
            ] = hashlib.sha256(qa_path.read_bytes()).hexdigest()
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "subject_sha256"):
                ADAPTERS.route_provider(
                    registry,
                    dict(base, **release_evidence),
                    style,
                    project_root=root,
                )

    def test_social_card_rejects_non_pptx_release_subject(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        style = {
            "primary_visual_family": "guizang-material-illustration",
            "secondary_provider_roles": {},
            "explicit_visual_opt_ins": [],
        }
        with released_project() as (root, release_evidence):
            deck_path = root / "deliverables" / "deck.pptx"
            deck_path.write_bytes(b"not-an-office-package")
            deck_sha = hashlib.sha256(deck_path.read_bytes()).hexdigest()
            assembly_path = root / "assembly-map.json"
            assembly = json.loads(assembly_path.read_text(encoding="utf-8"))
            assembly["sha256"] = deck_sha
            assembly_path.write_text(json.dumps(assembly), encoding="utf-8")
            qa_path = root / "qa-report.json"
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            qa["subject_sha256"] = deck_sha
            qa_path.write_text(json.dumps(qa), encoding="utf-8")
            brief_path = root / "derivatives" / "social-card-brief.json"
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
            brief["source_deck_sha256"] = deck_sha
            brief_path.write_text(json.dumps(brief), encoding="utf-8")
            brief_sha = hashlib.sha256(brief_path.read_bytes()).hexdigest()
            state_path = root / "run-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            approved = state["gates"]["release"]["approved_artifacts"]
            approved["deliverables/deck.pptx"] = deck_sha
            approved["assembly-map.json"] = hashlib.sha256(
                assembly_path.read_bytes()
            ).hexdigest()
            approved["qa-report.json"] = hashlib.sha256(
                qa_path.read_bytes()
            ).hexdigest()
            derivative = state["post_release_derivatives"][
                "guizang-social-card-skill"
            ]
            derivative["source_deck_sha256"] = deck_sha
            derivative["approved_artifacts"][
                "derivatives/social-card-brief.json"
            ] = brief_sha
            state_path.write_text(json.dumps(state), encoding="utf-8")
            request = {
                "provider_id": "guizang-social-card-skill",
                "page_role": "post-release-social-card",
                "source_kind": "released-deck",
                "truth_sensitive": False,
                "deck_released": True,
                "deliverable_role": "post-release-derivative",
                "released_deck": {
                    "path": "deliverables/deck.pptx",
                    "sha256": deck_sha,
                },
                "approved_derivative_brief": {
                    "path": "derivatives/social-card-brief.json",
                    "sha256": brief_sha,
                },
            }
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "valid PPTX"):
                ADAPTERS.route_provider(
                    registry, request, style, project_root=root
                )

    def test_malformed_zip_like_pptx_is_normalized_to_adapter_error(self):
        payload = (
            b"PK\x05\x06"
            + b"\0" * 6
            + b"\x01\0\x01\0"
            + b"\xff\xff\xff\x7f"
            + b"\0" * 6
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "malformed.pptx"
            path.write_bytes(payload)
            with patch.object(ADAPTERS.zipfile, "is_zipfile", return_value=True), patch.object(
                ADAPTERS.zipfile,
                "ZipFile",
                side_effect=zipfile.BadZipFile("bad central directory"),
            ):
                with self.assertRaisesRegex(ADAPTERS.AdapterError, "cannot inspect"):
                    ADAPTERS._verify_pptx_package(path)

    def test_pptx_requires_internal_slide_relationship_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, relationship_type, target_mode in (
                ("wrong-type.pptx", "image", None),
                ("external-slide.pptx", "slide", "External"),
            ):
                with self.subTest(name=name):
                    path = root / name
                    write_minimal_pptx(path, relationship_type, target_mode)
                    with self.assertRaisesRegex(
                        ADAPTERS.AdapterError,
                        "presentation-to-slide relationship is incomplete",
                    ):
                        ADAPTERS._verify_pptx_package(path)

    def test_secondary_provider_requires_a_declared_limited_role(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        request = {
            "page_role": "ordinary-photo",
            "source_kind": "ordinary-photo",
            "truth_sensitive": False,
            "deliverable_role": "slide-asset",
        }
        style = {
            "primary_visual_family": "guizang-material-illustration",
            "secondary_provider_roles": {},
            "explicit_visual_opt_ins": [],
        }

        with self.assertRaisesRegex(ADAPTERS.AdapterError, "secondary provider role"):
            ADAPTERS.route_provider(registry, request, style)

    def test_material_adapter_creates_separate_transparent_component_records(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        request = {
            "provider_id": "guizang-material-illustration",
            "slide_id": "S03",
            "page_role": "structural-diagram",
            "truth_sensitive": False,
            "source_kind": "approved-concept-render",
            "deliverable_role": "slide-asset",
            **approved_context("concepts/S03-approved.png"),
            "elements": [
                {
                    "id": "C01",
                    "role": "arrow",
                    "reference_bbox": [0.1, 0.2, 0.2, 0.2],
                    "references": ["concepts/S03-approved.png"],
                },
                {
                    "id": "C02",
                    "role": "table-shell",
                    "reference_bbox": [0.4, 0.2, 0.4, 0.5],
                    "fill_slot_ids": ["F01", "F02", "F03"],
                    "references": ["concepts/S03-approved.png"],
                },
            ],
        }

        with approved_project(request) as root:
            result = ADAPTERS.adapt_plan(registry, request, root)

        self.assertEqual(len(result["assets"]), 2)
        self.assertEqual([asset["id"] for asset in result["assets"]], ["C01", "C02"])
        for asset in result["assets"]:
            self.assertEqual(asset["provider_id"], "guizang-material-illustration")
            self.assertEqual(asset["background_requirement"], "transparent")
            self.assertEqual(asset["output_class"], "transparent-png-component")
            self.assertFalse(asset["contains_text"])
            self.assertFalse(asset["contains_data"])
        table = result["assets"][1]
        self.assertEqual(table["content_policy"], "blank-fill-slots")
        self.assertFalse(table["contains_data_encoding_marks"])

    def test_material_adapter_rejects_requested_embedded_text_or_data_marks(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        request = {
            "provider_id": "guizang-material-illustration",
            "slide_id": "S04",
            "page_role": "structural-diagram",
            "truth_sensitive": False,
            "source_kind": "approved-concept-render",
            "deliverable_role": "slide-asset",
            **approved_context("concepts/S04-approved.png"),
            "elements": [
                {
                    "id": "C01",
                    "role": "chart-shell",
                    "prompt": "a chart with labels and bars",
                    "prompt_language": "en",
                    "fill_slot_ids": ["F01"],
                    "contains_text": True,
                    "contains_data_encoding_marks": True,
                    "references": ["concepts/S04-approved.png"],
                }
            ],
        }

        with self.assertRaisesRegex(
            ADAPTERS.AdapterError, "cannot request embedded text, data, or data-encoding marks"
        ):
            with approved_project(request) as root:
                ADAPTERS.adapt_plan(registry, request, root)

    def test_shell_fill_slot_ids_must_be_safe_unique_strings(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        request = {
            "provider_id": "guizang-material-illustration",
            "slide_id": "S04A",
            "page_role": "structural-diagram",
            "truth_sensitive": False,
            "source_kind": "approved-concept-render",
            "deliverable_role": "slide-asset",
            **approved_context("concepts/S04A-approved.png"),
            "elements": [
                {
                    "id": "C01",
                    "role": "table-shell",
                    "reference_bbox": [0.1, 0.1, 0.8, 0.7],
                    "fill_slot_ids": [{"bad": "type"}, "F01", "F01"],
                    "references": ["concepts/S04A-approved.png"],
                }
            ],
        }

        with approved_project(request) as root:
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "safe string ids"):
                ADAPTERS.adapt_plan(registry, request, root)

        request["elements"][0]["fill_slot_ids"] = ["F01", "F01"]
        with approved_project(request) as root:
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "must be unique"):
                ADAPTERS.adapt_plan(registry, request, root)

    def test_material_adapter_rejects_all_free_form_component_prompts(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        request = {
            "provider_id": "guizang-material-illustration",
            "slide_id": "S04B",
            "page_role": "structural-diagram",
            "truth_sensitive": False,
            "source_kind": "approved-concept-render",
            "deliverable_role": "slide-asset",
            **approved_context("concepts/S04B-approved.png"),
            "elements": [
                {
                    "id": "C01",
                    "role": "chart-shell",
                    "prompt": "three blue bars and a red line",
                    "reference_bbox": [0.1, 0.1, 0.8, 0.7],
                    "fill_slot_ids": ["F01"],
                    "references": ["concepts/S04B-approved.png"],
                }
            ],
        }

        for prompt in ("three blue bars and a red line", "a red line"):
            with self.subTest(prompt=prompt):
                request["elements"][0]["prompt"] = prompt
                with approved_project(request) as root:
                    with self.assertRaisesRegex(ADAPTERS.AdapterError, "free-form prompt"):
                        ADAPTERS.adapt_plan(registry, request, root)

    def test_material_adapter_rejects_incompatible_provider_contract(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        registry["guizang-material-illustration"]["transparency_behavior"] = "opaque"
        request = {
            "provider_id": "guizang-material-illustration",
            "slide_id": "S05",
            "page_role": "conceptual-illustration",
            "truth_sensitive": False,
            "source_kind": "approved-concept-render",
            "deliverable_role": "slide-asset",
            "elements": [
                {"id": "C01", "role": "illustration", "prompt": "one water droplet"}
            ],
        }

        with self.assertRaisesRegex(
            ADAPTERS.AdapterError, "incompatible transparency contract"
        ):
            ADAPTERS.adapt_plan(registry, request, Path("."))

    def test_material_adapter_rejects_truth_sensitive_and_unsupported_page_roles(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        base = {
            "provider_id": "guizang-material-illustration",
            "slide_id": "S06",
            "page_role": "structural-diagram",
            "truth_sensitive": False,
            "elements": [
                {"id": "C01", "role": "illustration", "prompt": "one process node"}
            ],
        }
        truth_request = dict(base, truth_sensitive=True)
        with self.assertRaisesRegex(ADAPTERS.AdapterError, "rejects truth-sensitive"):
            ADAPTERS.adapt_plan(registry, truth_request, Path("."))
        role_request = dict(base, page_role="evidence-screenshot")
        with self.assertRaisesRegex(ADAPTERS.AdapterError, "does not support page role"):
            ADAPTERS.adapt_plan(registry, role_request, Path("."))

    def test_registry_requires_complete_capability_metadata(self):
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        payload["providers"][0].pop("approval_requirements")
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "registry.json"
            broken.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "missing fields"):
                ADAPTERS.load_registry(broken)

    def test_registry_rejects_empty_or_wrong_type_capability_metadata(self):
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for field, invalid in (
            ("skill_name", ""),
            ("truth_policy", None),
            ("adapter", 7),
        ):
            with self.subTest(field=field):
                broken_payload = json.loads(json.dumps(payload))
                broken_payload["providers"][0][field] = invalid
                with tempfile.TemporaryDirectory() as tmp:
                    broken = Path(tmp) / "registry.json"
                    broken.write_text(json.dumps(broken_payload), encoding="utf-8")
                    with self.assertRaisesRegex(ADAPTERS.AdapterError, field):
                        ADAPTERS.load_registry(broken)

    def test_registry_rejects_unknown_enums_and_material_full_page_behavior(self):
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        payload["providers"][0]["tier"] = "typo-tier"
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "registry.json"
            broken.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "unsupported tier"):
                ADAPTERS.load_registry(broken)

        registry = ADAPTERS.load_registry(REGISTRY)
        registry["guizang-material-illustration"]["aspect_ratio_behavior"] = (
            "compose-for-approved-special-page"
        )
        request = {
            "provider_id": "guizang-material-illustration",
            "slide_id": "S09",
            "page_role": "conceptual-illustration",
            "truth_sensitive": False,
        }
        with self.assertRaisesRegex(ADAPTERS.AdapterError, "component-canvas contract"):
            ADAPTERS.adapt_plan(registry, request, Path("."))

    def test_registry_rejects_canonical_policy_drift_and_schema_drift(self):
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        payload["providers"][3]["tier"] = "core-auto"
        payload["providers"][3]["auto_route"] = True
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "registry.json"
            broken.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "canonical contract"):
                ADAPTERS.load_registry(broken)

        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        payload["providers"][2]["truth_policy"] = "preserve-source-truth"
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "registry.json"
            broken.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "canonical contract"):
                ADAPTERS.load_registry(broken)

        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        payload["schema_version"] = "2.0"
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "registry.json"
            broken.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "schema_version"):
                ADAPTERS.load_registry(broken)

        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        payload["providers"][1]["source_requirements"] = ["anything"]
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "registry.json"
            broken.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "canonical contract"):
                ADAPTERS.load_registry(broken)

        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        payload["providers"][1]["approval_requirements"] = ["G3-style-anchors"]
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "registry.json"
            broken.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "canonical contract"):
                ADAPTERS.load_registry(broken)

    def test_auto_route_filters_source_and_truth_before_primary_preference(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        registry["guizang-material-illustration"]["supported_page_roles"].append(
            "opening"
        )
        style = {
            "primary_visual_family": "guizang-material-illustration",
            "secondary_provider_roles": {
                "scene-distillation-zine-v1-3": ["opening"]
            },
            "explicit_visual_opt_ins": [],
        }
        selected = ADAPTERS.route_provider(
            registry,
            {
                "page_role": "opening",
                "source_kind": "approved-source-scene",
                "truth_sensitive": False,
                "deliverable_role": "slide-asset",
            },
            style,
        )

        self.assertEqual(selected["id"], "scene-distillation-zine-v1-3")

    def test_material_adapter_requires_style_version_and_approved_references(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        request = {
            "provider_id": "guizang-material-illustration",
            "slide_id": "S07",
            "page_role": "conceptual-illustration",
            "truth_sensitive": False,
            "source_kind": "approved-concept-render",
            "deliverable_role": "slide-asset",
            "elements": [
                {
                    "id": "C01",
                    "role": "illustration",
                    "reference_bbox": [0.1, 0.1, 0.5, 0.5],
                    "references": [],
                }
            ],
        }

        with self.assertRaisesRegex(ADAPTERS.AdapterError, "style_contract_version"):
            ADAPTERS.adapt_plan(registry, request, Path("."))
        request.update(approved_context("concepts/S07-approved.png"))
        with approved_project(request) as root:
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "approved references"):
                ADAPTERS.adapt_plan(registry, request, root)

        request["elements"][0]["references"] = ["drafts/unapproved.png"]
        with approved_project(request) as root:
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "not in the approved reference set"):
                ADAPTERS.adapt_plan(registry, request, root)

        request["elements"][0]["references"] = ["concepts/S07-approved.png"]
        request["style_contract_version"] = "not-the-approved-version"
        with approved_project(request) as root:
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "does not match approved style"):
                ADAPTERS.adapt_plan(registry, request, root)

    def test_material_adapter_rejects_malformed_flags_and_prompted_content(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        base = {
            "provider_id": "guizang-material-illustration",
            "slide_id": "S08",
            "page_role": "conceptual-illustration",
            "truth_sensitive": False,
            "source_kind": "approved-concept-render",
            "deliverable_role": "slide-asset",
            **approved_context("concepts/S08-approved.png"),
            "elements": [
                {
                    "id": "C01",
                    "role": "illustration",
                    "reference_bbox": [0.1, 0.1, 0.5, 0.5],
                    "references": ["concepts/S08-approved.png"],
                }
            ],
        }
        malformed = json.loads(json.dumps(base))
        malformed["elements"][0]["contains_text"] = "true"
        with approved_project(malformed) as root:
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "contains_text must be boolean"):
                ADAPTERS.adapt_plan(registry, malformed, root)

        conflicting = json.loads(json.dumps(base))
        conflicting["elements"][0]["prompt"] = "render the label Revenue 2026"
        with approved_project(conflicting) as root:
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "free-form prompt"):
                ADAPTERS.adapt_plan(registry, conflicting, root)

        chinese_conflict = json.loads(json.dumps(base))
        chinese_conflict["elements"][0]["prompt"] = "绘制标签和普通文字"
        chinese_conflict["elements"][0]["prompt_language"] = "zh"
        with approved_project(chinese_conflict) as root:
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "free-form prompt"):
                ADAPTERS.adapt_plan(registry, chinese_conflict, root)

        false_language = json.loads(json.dumps(base))
        false_language["elements"][0]["prompt"] = "绘制标签和普通文字"
        false_language["elements"][0]["prompt_language"] = "en"
        with approved_project(false_language) as root:
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "free-form prompt"):
                ADAPTERS.adapt_plan(registry, false_language, root)

        caption_conflict = json.loads(json.dumps(base))
        caption_conflict["elements"][0]["prompt"] = "write Revenue as a caption"
        with approved_project(caption_conflict) as root:
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "free-form prompt"):
                ADAPTERS.adapt_plan(registry, caption_conflict, root)

    def test_material_adapter_verifies_ledger_hashes_and_safe_ids(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        request = {
            "provider_id": "guizang-material-illustration",
            "slide_id": "S10",
            "page_role": "conceptual-illustration",
            "truth_sensitive": False,
            "source_kind": "approved-concept-render",
            "deliverable_role": "slide-asset",
            **approved_context("concepts/S10-approved.png"),
            "elements": [
                {
                    "id": "C01",
                    "role": "illustration",
                    "reference_bbox": [0.1, 0.1, 0.5, 0.5],
                    "references": ["concepts/S10-approved.png"],
                }
            ],
        }
        with approved_project(request) as root:
            request["approved_style_contract"]["sha256"] = "a" * 64
            with self.assertRaisesRegex(ADAPTERS.AdapterError, "approved artifact"):
                ADAPTERS.adapt_plan(registry, request, root)

        unsafe = json.loads(json.dumps(request))
        unsafe["slide_id"] = "../../escaped"
        unsafe["elements"][0]["id"] = "../evil"
        with self.assertRaisesRegex(ADAPTERS.AdapterError, "safe identifier"):
            ADAPTERS.adapt_plan(registry, unsafe, Path("."))

    def test_material_adapter_reports_malformed_request_as_contract_error(self):
        registry = ADAPTERS.load_registry(REGISTRY)
        with self.assertRaisesRegex(ADAPTERS.AdapterError, "JSON object"):
            ADAPTERS.adapt_plan(registry, [], Path("."))
        with self.assertRaisesRegex(ADAPTERS.AdapterError, "provider_id"):
            ADAPTERS.adapt_plan(registry, {"provider_id": []}, Path("."))
        with self.assertRaisesRegex(ADAPTERS.AdapterError, "finite"):
            ADAPTERS.validate_reference_bbox(
                [float("nan"), 0.3, 0.25, 0.2], "reference_bbox"
            )

    def test_cli_normalizes_invalid_utf8_as_fail_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            request = root / "request.json"
            request.write_bytes(b"\xff\xfe")
            stderr = io.StringIO()
            argv = [
                "visual_adapters.py",
                "--registry",
                str(REGISTRY),
                "--request",
                str(request),
                "--project-root",
                str(root),
            ]
            with patch.object(sys, "argv", argv), redirect_stderr(stderr):
                result = ADAPTERS.main()

            self.assertEqual(result, 1)
            self.assertIn("FAIL:", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
