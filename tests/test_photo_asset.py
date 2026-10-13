import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from test_validate_project import (
    SCRIPT as VALIDATOR_SCRIPT,
    gate_decision_values,
    make_valid_project,
    refresh_fixture_decomposition_review,
    refresh_fixture_isolation_review,
    transparent_png,
    value_sha256,
    write_json,
)


REVIEW_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "render_photo_review.py"
SPEC = importlib.util.spec_from_file_location("ai_presentation_photo_test", REVIEW_SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def photo_project(root: Path, *, cutout: bool = False, processed_rectangle: bool = False) -> None:
    make_valid_project(root)
    processed = cutout or processed_rectangle
    source = root / "sources" / "ordinary-photo.png"
    source.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (10, 10), (24, 72, 112)).save(source)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    rights = root / "rights" / "ordinary-photo.json"
    rights.parent.mkdir(parents=True, exist_ok=True)
    rights.write_text(json.dumps({
        "status": "confirmed", "approval_phrase": "确认素材使用权",
        "confirmed_by": "fixture-human", "source_path": "sources/ordinary-photo.png",
        "source_sha256": source_sha, "media_class": "ordinary-photo",
        "truth_sensitive": False, "classification_phrase": "确认普通照片",
        "classified_by": "fixture-human",
        "excluded_types": {"product_screenshot": True, "data_figure": True, "report": True},
    }), encoding="utf-8")
    rights_sha = hashlib.sha256(rights.read_bytes()).hexdigest()

    decomposition = json.loads((root / "decomposition-map.json").read_text(encoding="utf-8"))
    item = decomposition["slides"][0]["items"][0]
    item["role"] = "photo-cutout" if cutout else "ordinary-photo"
    item["source_class"] = "ordinary-photo"
    item["treatment"] = "photo-adjust" if processed else "preserve-source"
    item["label"] = "one independent ordinary photo"
    write_json(root, "decomposition-map.json", decomposition)
    refresh_fixture_decomposition_review(root)

    state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
    state["gates"]["brief_authority"]["approved_artifacts"]["rights/ordinary-photo.json"] = rights_sha
    gate = state["gates"]["decomposition"]
    for relative in gate["approved_artifacts"]:
        gate["approved_artifacts"][relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    for key, value in gate_decision_values(root, "decomposition").items():
        gate["approval_packet"]["decisions"][key]["value"] = value
        gate["approval_packet"]["decisions"][key]["value_sha256"] = value_sha256(value)
    write_json(root, "run-state.json", state)

    output = source
    if processed:
        output = root / "assets" / "S01" / "C01-photo-v1.png"
        if cutout:
            output.write_bytes(transparent_png())
        else:
            Image.new("RGB", (10, 10), (31, 78, 116)).save(output)
    output_sha = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
    asset = manifest["assets"][0]
    asset.update({
        "role": "photo-cutout" if cutout else "ordinary-photo",
        "page_role": "ordinary-photo", "provider_id": "photo-postprocess-coach",
        "adapter_id": "photo-postprocess-v1", "source_kind": "ordinary-photo",
        "truth_sensitive": False, "source_rights_confirmation": {
            "path": "rights/ordinary-photo.json", "sha256": rights_sha,
        },
        "source_photo": {"path": "sources/ordinary-photo.png", "sha256": source_sha},
        "photo_output_mode": "cutout" if cutout else "rectangle",
        "strategy": "postprocessed-transparent-png" if cutout else ("postprocessed-photo-rectangle" if processed else "preserved-photo-rectangle"),
        "content_policy": "preserve-source-photo",
        "background_requirement": "transparent" if cutout else "opaque-rectangle",
        "output_class": "transparent-photo-cutout" if cutout else "opaque-photo-rectangle",
        "provider_transparency_behavior": "optional-subject-cutout",
        "provider_aspect_ratio_behavior": "preserve-subject-with-approved-crop",
        "output": "assets/S01/C01-photo-v1.png" if processed else "sources/ordinary-photo.png",
        "sha256": output_sha,
        "alpha": {"has_alpha": True, "transparent_pixel_ratio": 8 / 9} if cutout else None,
        "generation_attempts": 0, "generation_history": [],
        "extraction": {"route": "photo-adjust" if processed else "preserve-source"},
        "status": "approved",
    })
    if processed:
        diagnosis = root / "reviews" / "photos" / "C01-diagnosis.json"
        diagnosis.parent.mkdir(parents=True, exist_ok=True)
        diagnosis.write_text(json.dumps({
            "source_sha256": source_sha,
            "measurements": {"luminance": {"mean": 60}, "clipping": {"shadow_pct": 0},
                             "noise": {"luma_std": 1}, "sharpness": {"laplacian_var": 12},
                             "photo_type": "other"},
        }), encoding="utf-8")
        preservation_recipe = "Preserve identity, scene, architecture, and perspective."
        diagnosis_sha = hashlib.sha256(diagnosis.read_bytes()).hexdigest()
        asset["photo_processing"] = {
            "confirmation": {"approval_phrase": "确认照片后期方案", "approved_by": "fixture-human", "approved_at": "2026-09-26T10:00:00+08:00", "source_sha256": source_sha, "direction": "natural subject isolation", "diagnosis_sha256": diagnosis_sha, "preservation_prompt_sha256": hashlib.sha256(preservation_recipe.encode("utf-8")).hexdigest()},
            "diagnosis": {"path": "reviews/photos/C01-diagnosis.json", "sha256": diagnosis_sha},
            "direction": "natural subject isolation", "preservation_prompt": preservation_recipe,
            "attempts": [{
                "call_id": "photo-C01-v1", "component_id": "C01", "source_sha256": source_sha,
                "output_path": "assets/S01/C01-photo-v1.png", "sha256": output_sha,
                "tool": "codex-image_gen", "prompt_or_recipe": preservation_recipe,
                "status": "accepted",
            }],
        }
    else:
        asset.pop("photo_processing", None)
    write_json(root, "asset-manifest.json", manifest)
    refresh_fixture_isolation_review(root)
    if processed:
        MODULE.render(root, "C01")
        manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
        review = manifest["assets"][0]["photo_review"]
        review["status"] = "passed"
        review["reviewer"] = "fixture-human"
        review["checks"] = {key: True for key in review["checks"]}
        write_json(root, "asset-manifest.json", manifest)


def validate(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), str(root), "--stage", "assets"],
        capture_output=True, text=True, check=False,
    )


class PhotoAssetTests(unittest.TestCase):
    def test_rights_confirmed_opaque_photo_is_one_independent_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo_project(root)
            result = validate(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_confirmed_photo_adjustment_remains_an_opaque_rectangle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo_project(root, processed_rectangle=True)
            result = validate(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_source_rights_rejects_photo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo_project(root)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0].pop("source_rights_confirmation")
            write_json(root, "asset-manifest.json", manifest)
            result = validate(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source_rights_confirmation must be an object", result.stdout)

    def test_processed_cutout_requires_real_alpha_and_human_source_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo_project(root, cutout=True)
            accepted = validate(root)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0]["photo_review"]["checks"]["subject_identity"] = False
            write_json(root, "asset-manifest.json", manifest)
            rejected = validate(root)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("photo preservation check must pass: subject_identity", rejected.stdout)

    def test_photo_recipe_change_invalidates_human_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo_project(root, processed_rectangle=True)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            processing = manifest["assets"][0]["photo_processing"]
            processing["preservation_prompt"] = "Replace the scene with another building."
            processing["attempts"][0]["prompt_or_recipe"] = processing["preservation_prompt"]
            write_json(root, "asset-manifest.json", manifest)
            rejected = validate(root)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("recipe lack explicit source-bound human confirmation", rejected.stdout)

    def test_opaque_pixels_cannot_masquerade_as_transparent_cutout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo_project(root, cutout=True)
            output = root / "assets" / "S01" / "C01-photo-v1.png"
            Image.new("RGB", (10, 10), (5, 20, 40)).save(output)
            new_sha = hashlib.sha256(output.read_bytes()).hexdigest()
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            asset = manifest["assets"][0]
            asset["sha256"] = new_sha
            asset["photo_processing"]["attempts"][0]["sha256"] = new_sha
            asset["photo_review"]["output_sha256"] = new_sha
            asset["isolation_review"]["asset_sha256"] = new_sha
            write_json(root, "asset-manifest.json", manifest)
            result = validate(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("meaningful transparent padding", result.stdout)

    def test_fact_sensitive_source_must_not_be_relabelled_as_photo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo_project(root)
            rights_path = root / "rights" / "ordinary-photo.json"
            rights = json.loads(rights_path.read_text(encoding="utf-8"))
            rights["media_class"] = "product-screenshot"
            rights_path.write_text(json.dumps(rights), encoding="utf-8")
            new_sha = hashlib.sha256(rights_path.read_bytes()).hexdigest()
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            manifest["assets"][0]["source_rights_confirmation"]["sha256"] = new_sha
            write_json(root, "asset-manifest.json", manifest)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["brief_authority"]["approved_artifacts"]["rights/ordinary-photo.json"] = new_sha
            write_json(root, "run-state.json", state)
            result = validate(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ordinary-photo classification", result.stdout)

    def test_flat_ui_screenshot_is_rejected_even_with_ordinary_photo_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo_project(root)
            source = root / "sources" / "ordinary-photo.png"
            screenshot = Image.new("RGB", (320, 180), "white")
            draw = ImageDraw.Draw(screenshot)
            draw.rectangle((0, 0, 319, 26), fill=(45, 80, 120))
            draw.text((8, 7), "App Settings", fill="white")
            draw.rectangle((16, 50, 180, 88), fill=(225, 235, 245), outline=(80, 100, 120))
            draw.text((24, 62), "Account", fill=(20, 30, 45))
            draw.rectangle((16, 105, 130, 145), fill=(50, 110, 190))
            draw.text((45, 118), "Save", fill="white")
            screenshot.save(source)
            source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            rights_path = root / "rights" / "ordinary-photo.json"
            rights = json.loads(rights_path.read_text(encoding="utf-8"))
            rights["source_sha256"] = source_sha
            rights_path.write_text(json.dumps(rights), encoding="utf-8")
            rights_sha = hashlib.sha256(rights_path.read_bytes()).hexdigest()
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            state["gates"]["brief_authority"]["approved_artifacts"]["rights/ordinary-photo.json"] = rights_sha
            write_json(root, "run-state.json", state)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            asset = manifest["assets"][0]
            asset["source_photo"]["sha256"] = source_sha
            asset["source_rights_confirmation"]["sha256"] = rights_sha
            asset["sha256"] = source_sha
            write_json(root, "asset-manifest.json", manifest)
            result = validate(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("resembles a flat graphic", result.stdout)


if __name__ == "__main__":
    unittest.main()
