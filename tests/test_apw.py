"""Regression tests for public showcase entry points and a reported CLI bug."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_final_package
from apw import build_project, _route
from test_showcase_contract import valid_concept, _write_json

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class PublicEntryTests(unittest.TestCase):
    def test_dangling_kind_marker_does_not_fall_back_to_production(self):
        with patch.object(Path, "exists", return_value=False), patch.object(Path, "is_symlink", return_value=True), patch.object(Path, "is_file", return_value=False):
            route, error = _route(Path("synthetic-marker-test"))
        self.assertEqual(route, "invalid")
        self.assertIn("regular file", error)

    def test_existing_validator_cli_uses_current_showcase_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = valid_concept(Path(temp) / "project")
            result = subprocess.run([sys.executable, str(SCRIPTS / "validate_project.py"), str(root), "--stage", "concept"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            _write_json(root, "project-kind.json", {"contract_version": "unknown", "purpose": "showcase"})
            result = subprocess.run([sys.executable, str(SCRIPTS / "validate_project.py"), str(root), "--stage", "concept"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 1)
            self.assertIn("project-kind.json", result.stdout)

    def test_exporter_default_and_verify_select_showcase_sibling_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = valid_concept(Path(temp) / "project")
            expected = root.parent / "project-交付包"
            expected.mkdir()
            (expected / "PPT成稿").mkdir()
            pptx = expected / "PPT成稿" / "deck-草稿.pptx"
            pptx.write_bytes(b"test CLI selection only")
            for verify in (False, True):
                argv = ["export_final_package.py", str(root)] + (["--verify"] if verify else [])
                with patch.object(sys, "argv", argv), patch.object(export_final_package, "export", return_value=(1, 0, pptx)) as call, contextlib.redirect_stdout(io.StringIO()):
                    export_final_package.main()
                self.assertEqual(call.call_args.args[1], expected)
                self.assertEqual(call.call_args.kwargs["verify_only"], verify)
            self.assertEqual(pptx.read_bytes(), b"test CLI selection only")

    def test_exporter_surfaces_contract_errors_and_build_does_not_emit_bad_deck(self):
        with tempfile.TemporaryDirectory() as temp:
            root = valid_concept(Path(temp) / "project")
            (root / "concepts/S01.png").write_bytes(b"changed concept")
            result = build_project(root, "v1")
            self.assertFalse(result["ok"])
            self.assertEqual(result["phase"], "concept-preflight")
            self.assertFalse((root / "assembly").exists())
            with self.assertRaisesRegex(ValueError, "Showcase export failed"):
                export_final_package.export(root, root.parent / "delivery")
            self.assertFalse((root.parent / "delivery").exists())


if __name__ == "__main__":
    unittest.main()
