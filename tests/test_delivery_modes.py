"""Regression tests for the opt-in concept/assets delivery route."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from delivery_modes import MODE_STAGES, read_delivery_mode, validate_delivery


def _write_json(root: Path, relative: str, value: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(root: Path, name: str) -> dict:
    return json.loads((root / name).read_text(encoding="utf-8"))


def refresh_concept_input_hashes(root: Path) -> None:
    log = load(root, "concept-generation-log.json")
    files = {
        "brief": "brief.json",
        "deck_spec": "deck-spec.json",
        "reference_study": "reference-study.json",
        "style_contract": "style-contract.json",
    }
    for slide in log["slides"]:
        slide["input_sha256"] = {key: digest(root / relative) for key, relative in files.items()}
    _write_json(root, "concept-generation-log.json", log)


def make_concept_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    concept_path = root / "concepts/S01.png"
    concept_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1672, 941), "white").save(concept_path)
    reference_path = root / "references/reference.png"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (320, 200), "#56789A").save(reference_path)

    brief = {
        "quality_profile": "draft",
        "audience": "delivery-mode contract test",
        "goal": "verify concept-only routing",
        "source_map": [{"id": "EXAMPLE-1", "kind": "manual-example", "locator": "Synthetic explanatory copy for a unit test.", "truth_status": "illustrative"}],
    }
    deck = {
        "slides": [{
            "id": "S01",
            "title": "示例页面",
            "message": "本页用于验证概念交付模式",
            "concept_path": "concepts/S01.png",
            "reference_ids": ["R1"],
            "copy": [
                {"id": "C-TITLE", "role": "title", "text": "示例页面", "truth_status": "illustrative", "source_ids": []},
                {"id": "C-MESSAGE", "role": "key-takeaway", "text": "本页用于验证概念交付模式", "truth_status": "illustrative", "source_ids": []},
            ],
        }]
    }
    reference = {
        "selected_reference_ids": ["R1"],
        "references": [{
            "id": "R1",
            "status": "analyzed",
            "image_path": "references/reference.png",
            "sha256": digest(reference_path),
            "source_locator": "Synthetic local design reference used only in a unit test.",
            "usage_note": "Test of local reference binding.",
            "transferable_rules": ["clear hierarchy"],
            "project_translation": ["one readable title"],
            "do_not_copy": ["do not claim this is source artwork"],
        }],
    }
    style = {
        "selected_reference_ids": ["R1"],
        "readability_profile": {"font_floors_pt": {"title": 32, "key-takeaway": 20}, "minimum_contrast_ratio": 4.5},
    }
    for name, value in {
        "project-kind.json": {"contract_version": "showcase-v1", "purpose": "showcase"},
        "brief.json": brief,
        "deck-spec.json": deck,
        "reference-study.json": reference,
        "style-contract.json": style,
        "run-state.json": {"mode": "showcase-local-draft"},
    }.items():
        _write_json(root, name, value)
    input_files = {
        "brief": "brief.json",
        "deck_spec": "deck-spec.json",
        "reference_study": "reference-study.json",
        "style_contract": "style-contract.json",
    }
    log = {
        "status": "complete",
        "slides": [{
            "slide_id": "S01",
            "status": "generated",
            "output_path": "concepts/S01.png",
            "output_sha256": digest(concept_path),
            "input_sha256": {key: digest(root / relative) for key, relative in input_files.items()},
            "copy_map": deck["slides"][0]["copy"],
            "reference_images": [{"reference_id": "R1", "path": "references/reference.png", "sha256": digest(reference_path)}],
        }],
    }
    _write_json(root, "concept-generation-log.json", log)
    return root


def write_delivery_mode(root: Path, mode: str) -> None:
    _write_json(root, "delivery-mode.json", {"mode": mode})


def write_asset_package(root: Path, *, transparent: bool = True, opaque_reason: str | None = None) -> None:
    (root / "assets").mkdir(exist_ok=True)
    if transparent:
        image = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
        image.putpixel((5, 5), (18, 122, 164, 255))
    else:
        image = Image.new("RGB", (12, 12), (18, 122, 164))
    image.save(root / "assets/component.png")

    generation_record = root / "generation" / "asset-01.md"
    generation_record.parent.mkdir(exist_ok=True)
    generation_record.write_text("One isolated decorative component from concept S01.\n", encoding="utf-8")
    concept = root / "concepts/S01.png"
    asset = {
        "id": "A-S01-01",
        "slide_id": "S01",
        "kind": "picture",
        "path": "assets/component.png",
        "sha256": digest(root / "assets/component.png"),
        "truth_status": "illustrative",
        "source_locator": "concepts/S01.png#illustration",
        "requires_transparency": transparent,
        "generation": {
            "method": "Codex image_gen",
            "prompt": "One isolated transparent illustration component.",
            "source_concept_path": "concepts/S01.png",
            "source_concept_sha256": digest(concept),
            "record_path": "generation/asset-01.md",
            "record_sha256": digest(generation_record),
        },
    }
    if opaque_reason is not None:
        asset["opaque_reason"] = opaque_reason
    _write_json(
        root,
        "asset-manifest.json",
        {
            "contract_version": "showcase-assets-v1",
            "coverage": [{"slide_id": "S01", "asset_ids": ["A-S01-01"], "status": "complete"}],
            "assets": [asset],
        },
    )


class DeliveryModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = make_concept_project(Path(self.temp.name) / "project")

    def tearDown(self):
        self.temp.cleanup()

    def test_legacy_project_without_selector_keeps_assembly_mode(self):
        self.assertEqual(read_delivery_mode(self.root), "assembly")
        self.assertEqual(MODE_STAGES["concept"], ("concept", "export"))
        self.assertEqual(MODE_STAGES["assets"], ("concept", "assets", "export"))

    def test_mode_selector_requires_one_known_field(self):
        _write_json(self.root, "delivery-mode.json", {"mode": "concept", "reason": "extra"})
        with self.assertRaisesRegex(ValueError, "exactly one field"):
            read_delivery_mode(self.root)
        _write_json(self.root, "delivery-mode.json", {"mode": "unlisted"})
        with self.assertRaisesRegex(ValueError, "expected one of"):
            read_delivery_mode(self.root)

    def test_mode_selector_directory_is_not_treated_as_legacy_absence(self):
        (self.root / "delivery-mode.json").mkdir()
        with self.assertRaisesRegex(ValueError, "not a regular file"):
            read_delivery_mode(self.root)

    def test_concept_delivery_does_not_require_scene_asset_or_pptx_files(self):
        (self.root / "scene-graph.json").unlink(missing_ok=True)
        (self.root / "asset-manifest.json").unlink(missing_ok=True)
        write_delivery_mode(self.root, "concept")
        report = validate_delivery(self.root, "concept", "concept")
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["stage"], "concept")
        self.assertEqual(report["facts"]["delivery_mode"], "concept")
        export_report = validate_delivery(self.root, "concept", "export")
        self.assertTrue(export_report["ok"], export_report["errors"])

    def test_requested_mode_must_match_persisted_selection(self):
        write_delivery_mode(self.root, "concept")
        report = validate_delivery(self.root, "assets", "concept")
        self.assertFalse(report["ok"])
        self.assertTrue(any("does not match" in error for error in report["errors"]))

    def test_assets_mode_checks_alpha_hash_provenance_and_page_coverage(self):
        (self.root / "scene-graph.json").unlink(missing_ok=True)
        write_delivery_mode(self.root, "assets")
        write_asset_package(self.root)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["facts"]["asset_status"], "ready")
        self.assertEqual(report["facts"]["asset_ids"], ["A-S01-01"])
        self.assertEqual(report["facts"]["asset_review"], "not-claimed")
        self.assertIn("not a full visual decomposition", report["facts"]["asset_coverage_scope"])

    def test_explicit_assembly_concept_and_assets_stages_are_lightweight(self):
        write_delivery_mode(self.root, "assembly")
        with patch.object(_showcase_module(), "validate_showcase", side_effect=AssertionError("must not require scene/PPTX yet")):
            concept_report = validate_delivery(self.root, "assembly", "concept")
            self.assertTrue(concept_report["ok"], concept_report["errors"])

            write_asset_package(self.root)
            assets_report = validate_delivery(self.root, "assembly", "assets")
        self.assertTrue(assets_report["ok"], assets_report["errors"])
        self.assertEqual(assets_report["facts"]["asset_status"], "ready")

    def test_asset_manifest_rejects_fixtures_and_approval_claims(self):
        write_delivery_mode(self.root, "assets")
        write_asset_package(self.root)
        manifest = load(self.root, "asset-manifest.json")
        manifest["fixture_only"] = True
        manifest["human_gates"] = {"G5": "approved"}
        manifest["assets"][0]["status"] = "approved"
        _write_json(self.root, "asset-manifest.json", manifest)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("validation-fixture" in error for error in report["errors"]))
        self.assertTrue(any("must not claim" in error for error in report["errors"]))
        self.assertTrue(any("cannot claim human review or approval" in error for error in report["errors"]))

    def test_transparency_is_required_by_default_and_must_be_real_alpha(self):
        write_delivery_mode(self.root, "assets")
        write_asset_package(self.root, transparent=False)
        manifest = load(self.root, "asset-manifest.json")
        manifest["assets"][0].pop("requires_transparency")
        _write_json(self.root, "asset-manifest.json", manifest)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("real transparent pixels" in error for error in report["errors"]))

    def test_opaque_exception_requires_an_explanation(self):
        write_delivery_mode(self.root, "assets")
        write_asset_package(self.root, transparent=False)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("opaque_reason" in error for error in report["errors"]))

        write_asset_package(self.root, transparent=False, opaque_reason="A source photograph remains a single rectangular object.")
        report = validate_delivery(self.root, "assets", "assets")
        self.assertTrue(report["ok"], report["errors"])

    def test_no_assets_is_an_explicit_valid_status_not_a_fake_asset(self):
        write_delivery_mode(self.root, "assets")
        _write_json(
            self.root,
            "asset-manifest.json",
            {
                "contract_version": "showcase-assets-v1",
                "coverage": [{"slide_id": "S01", "asset_ids": [], "status": "no-assets", "no_assets_reason": "本页仅排版文字，无独立插画。"}],
                "assets": [],
            },
        )
        report = validate_delivery(self.root, "assets", "assets")
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["facts"]["asset_status"], "no-assets")

    def test_verified_source_asset_uses_brief_source_binding_without_generation(self):
        write_delivery_mode(self.root, "assets")
        write_asset_package(self.root, transparent=False, opaque_reason="")
        source_path = self.root / "source/evidence.png"
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes((self.root / "assets/component.png").read_bytes())
        brief = load(self.root, "brief.json")
        brief["source_map"] = [{
            "id": "SOURCE-REAL",
            "kind": "verified-evidence",
            "locator": "Local source image recorded for this contract test.",
            "truth_status": "verified",
            "path": "source/evidence.png",
            "sha256": digest(source_path),
        }]
        _write_json(self.root, "brief.json", brief)
        asset_path = self.root / "assets/component.png"
        manifest = {
            "contract_version": "showcase-assets-v1",
            "coverage": [{"slide_id": "S01", "asset_ids": ["A-S01-01"], "status": "complete"}],
            "assets": [{
                "id": "A-S01-01",
                "slide_id": "S01",
                "kind": "source-evidence",
                "path": "assets/component.png",
                "sha256": digest(asset_path),
                "truth_status": "verified",
                "source_id": "SOURCE-REAL",
                "source_locator": "Local source image recorded for this contract test.",
                "requires_transparency": False,
                "opaque_reason": "Source evidence remains an intact image rectangle.",
            }],
        }
        _write_json(self.root, "asset-manifest.json", manifest)
        refresh_concept_input_hashes(self.root)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertTrue(report["ok"], report["errors"])

    def test_coverage_must_account_for_every_deck_page_and_asset(self):
        write_delivery_mode(self.root, "assets")
        write_asset_package(self.root)
        manifest = load(self.root, "asset-manifest.json")
        manifest["coverage"] = []
        _write_json(self.root, "asset-manifest.json", manifest)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("every deck slide" in error for error in report["errors"]))

    def test_generation_and_concept_hashes_are_current(self):
        write_delivery_mode(self.root, "assets")
        write_asset_package(self.root)
        manifest = load(self.root, "asset-manifest.json")
        manifest["assets"][0]["generation"]["source_concept_sha256"] = "0" * 64
        _write_json(self.root, "asset-manifest.json", manifest)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("SHA-256 does not match" in error for error in report["errors"]))

        manifest["assets"][0]["generation"]["source_concept_sha256"] = digest(self.root / "concepts/S01.png")
        manifest["assets"][0]["generation"]["record_sha256"] = "0" * 64
        _write_json(self.root, "asset-manifest.json", manifest)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("SHA-256 does not match" in error for error in report["errors"]))

    def test_assembly_route_delegates_legacy_stages_to_showcase_validator(self):
        with patch.object(_showcase_module(), "validate_showcase", return_value={"ok": True, "errors": [], "warnings": [], "facts": {"slides": 1}}) as delegated:
            report = validate_delivery(self.root, "assembly", "assets")
        self.assertTrue(report["ok"], report["errors"])
        delegated.assert_called_once_with(self.root.resolve(), "concept")
        self.assertEqual(report["facts"]["contract_stage"], "concept")

    def test_explicit_assembly_final_stages_delegate_to_full_showcase_contract(self):
        write_delivery_mode(self.root, "assembly")
        result = {"ok": True, "errors": [], "warnings": [], "facts": {"pptx_sha256": "bound"}}
        for stage in ("assembly", "qa", "export"):
            with self.subTest(stage=stage), patch.object(_showcase_module(), "validate_showcase", return_value=result) as delegated:
                report = validate_delivery(self.root, "assembly", stage)
            self.assertTrue(report["ok"], report["errors"])
            delegated.assert_called_once_with(self.root.resolve(), stage)


def _showcase_module():
    import delivery_modes

    return delivery_modes._showcase


if __name__ == "__main__":
    unittest.main()
