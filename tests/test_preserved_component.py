import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from test_validate_project import (
    ISOLATION_SCRIPT,
    SCRIPT as VALIDATOR_SCRIPT,
    gate_decision_values,
    make_valid_project,
    promote_fixture_to_production,
    refresh_fixture_decomposition_review,
    value_sha256,
    write_json,
)


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_preserved_component.py"
SPEC = importlib.util.spec_from_file_location("ai_presentation_preserved_component", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PreservedComponentTests(unittest.TestCase):
    def test_approved_project_extracts_one_pixel_preserved_asset_then_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_valid_project(root)
            promote_fixture_to_production(root)
            bbox = [0.25, 0.25, 0.5, 0.5]
            scene = json.loads((root / "scene-graph.json").read_text(encoding="utf-8"))
            scene["slides"][0]["elements"][0]["bbox"] = bbox
            write_json(root, "scene-graph.json", scene)
            decomposition = json.loads((root / "decomposition-map.json").read_text(encoding="utf-8"))
            item = decomposition["slides"][0]["items"][0]
            item["bbox"] = bbox
            item["crop_padding"] = [0.2, 0.2, 0.2, 0.2]
            item["treatment"] = "preserve-pixels"
            write_json(root, "decomposition-map.json", decomposition)
            refresh_fixture_decomposition_review(root)
            state = json.loads((root / "run-state.json").read_text(encoding="utf-8"))
            gate = state["gates"]["decomposition"]
            for relative in gate["approved_artifacts"]:
                gate["approved_artifacts"][relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
            decisions = gate_decision_values(root, "decomposition")
            for key, value in decisions.items():
                gate["approval_packet"]["decisions"][key]["value"] = value
                gate["approval_packet"]["decisions"][key]["value_sha256"] = value_sha256(value)
            write_json(root, "run-state.json", state)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            asset = manifest["assets"][0]
            asset["strategy"] = "preserved-transparent-png"
            asset["output"] = "assets/S01/C01-preserved-v1.png"
            asset["generation_attempts"] = 0
            asset.pop("generation_history")
            write_json(root, "asset-manifest.json", manifest)
            mask_path = root / "masks" / "S01" / "C01.png"
            mask_path.parent.mkdir(parents=True)
            mask = Image.new("L", (3, 3), 0)
            mask.putpixel((1, 1), 255)
            mask.save(mask_path)

            extracted = subprocess.run(
                [sys.executable, str(SCRIPT), str(root), "--slide", "S01", "--item", "D01", "--mask", "masks/S01/C01.png"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(extracted.returncode, 0, extracted.stderr)
            output = root / "assets" / "S01" / "C01-preserved-v1.png"
            self.assertTrue(output.is_file())
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["assets"][0]["extraction"]["output_path"], "assets/S01/C01-preserved-v1.png")
            self.assertEqual(manifest["assets"][0]["extraction"]["output_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            pending = subprocess.run(
                [sys.executable, str(VALIDATOR_SCRIPT), str(root), "--stage", "assets"],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(pending.returncode, 0)
            self.assertIn("passed human isolation review is required", pending.stdout)

            review = subprocess.run(
                [sys.executable, str(ISOLATION_SCRIPT), str(root), "--asset", "C01"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(review.returncode, 0, review.stderr)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            asset = manifest["assets"][0]
            asset["isolation_review"]["status"] = "passed"
            asset["isolation_review"]["reviewer"] = "fixture-reviewer"
            asset["isolation_review"]["checks"] = {
                key: True for key in asset["isolation_review"]["checks"]
            }
            asset["status"] = "approved"
            write_json(root, "asset-manifest.json", manifest)
            accepted = subprocess.run(
                [sys.executable, str(VALIDATOR_SCRIPT), str(root), "--stage", "assets"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

            asset["output"] = "assets/S01/C01-preserved-v2.png"
            write_json(root, "asset-manifest.json", manifest)
            second = subprocess.run(
                [sys.executable, str(SCRIPT), str(root), "--slide", "S01", "--item", "D01", "--mask", "masks/S01/C01.png"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            asset = manifest["assets"][0]
            self.assertEqual(asset["extraction_history"][-1]["output_path"], "assets/S01/C01-preserved-v1.png")
            self.assertEqual(asset["extraction_history"][-1]["output_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(asset["extraction"]["output_path"], "assets/S01/C01-preserved-v2.png")
            second_review = subprocess.run(
                [sys.executable, str(ISOLATION_SCRIPT), str(root), "--asset", "C01"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(second_review.returncode, 0, second_review.stderr)
            manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
            asset = manifest["assets"][0]
            asset["isolation_review"]["status"] = "passed"
            asset["isolation_review"]["reviewer"] = "fixture-reviewer-v2"
            asset["isolation_review"]["checks"] = {
                key: True for key in asset["isolation_review"]["checks"]
            }
            asset["status"] = "approved"
            write_json(root, "asset-manifest.json", manifest)
            retained = subprocess.run(
                [sys.executable, str(VALIDATOR_SCRIPT), str(root), "--stage", "assets"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(retained.returncode, 0, retained.stdout + retained.stderr)
            output.write_bytes(b"tampered-old-output")
            stale = subprocess.run(
                [sys.executable, str(VALIDATOR_SCRIPT), str(root), "--stage", "assets"],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("historical output is reused or its hash is stale", stale.stdout)

    def test_exact_source_pixels_inside_one_mask_with_clear_padding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "master.png"
            mask_path = root / "mask.png"
            source = Image.new("RGB", (100, 100))
            source.putdata([(x, y, (x + y) % 256) for y in range(100) for x in range(100)])
            source.save(source_path)
            mask = Image.new("L", (100, 100), 0)
            ImageDraw.Draw(mask).rectangle((30, 30, 69, 69), fill=255)
            mask.save(mask_path)

            output, crop = MODULE.extract_pixels(
                source_path, mask_path, [0.25, 0.25, 0.5, 0.5], [0.1, 0.1, 0.1, 0.1]
            )

            self.assertEqual(crop, (15, 15, 85, 85))
            self.assertEqual(output.size, (70, 70))
            self.assertEqual(output.getpixel((15, 15)), (*source.getpixel((30, 30)), 255))
            self.assertEqual(output.getpixel((0, 0))[3], 0)
            self.assertEqual(output.getpixel((69, 69))[3], 0)

    def test_rejects_mask_material_outside_declared_crop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "master.png"
            mask_path = root / "mask.png"
            Image.new("RGB", (100, 100), (20, 40, 60)).save(source_path)
            mask = Image.new("L", (100, 100), 0)
            mask.putpixel((5, 5), 255)
            mask.putpixel((50, 50), 255)
            mask.save(mask_path)

            with self.assertRaisesRegex(ValueError, "mask extends outside declared crop"):
                MODULE.extract_pixels(
                    source_path, mask_path, [0.25, 0.25, 0.5, 0.5], [0.1, 0.1, 0.1, 0.1]
                )

    def test_rejects_cut_object_at_output_border(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "master.png"
            mask_path = root / "mask.png"
            Image.new("RGB", (100, 100), (20, 40, 60)).save(source_path)
            mask = Image.new("L", (100, 100), 0)
            ImageDraw.Draw(mask).rectangle((25, 25, 74, 74), fill=255)
            mask.save(mask_path)

            with self.assertRaisesRegex(ValueError, "mask touches output border"):
                MODULE.extract_pixels(
                    source_path, mask_path, [0.25, 0.25, 0.5, 0.5], [0, 0, 0, 0]
                )


if __name__ == "__main__":
    unittest.main()
