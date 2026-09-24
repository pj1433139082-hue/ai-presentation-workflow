import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "compare_installation.py"
MODULE_SPEC = importlib.util.spec_from_file_location("compare_installation", SCRIPT)
COMPARE_MODULE = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(COMPARE_MODULE)


class CompareInstallationTests(unittest.TestCase):
    def test_matching_trees_have_no_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            installed = root / "installed"
            source.mkdir()
            installed.mkdir()
            (source / "SKILL.md").write_text("same", encoding="utf-8")
            (installed / "SKILL.md").write_text("same", encoding="utf-8")

            report = COMPARE_MODULE.compare_trees(source, installed)

            self.assertTrue(report.is_clean)
            self.assertEqual(report.missing, ())
            self.assertEqual(report.extra, ())
            self.assertEqual(report.changed, ())

    def test_missing_extra_and_changed_files_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            installed = root / "installed"
            source.mkdir()
            installed.mkdir()
            (source / "missing.md").write_text("source", encoding="utf-8")
            (source / "changed.md").write_text("source", encoding="utf-8")
            (installed / "changed.md").write_text("installed", encoding="utf-8")
            (installed / "extra.md").write_text("extra", encoding="utf-8")

            report = COMPARE_MODULE.compare_trees(source, installed)

            self.assertFalse(report.is_clean)
            self.assertEqual(report.missing, ("missing.md",))
            self.assertEqual(report.extra, ("extra.md",))
            self.assertEqual(report.changed, ("changed.md",))

    def test_generated_python_cache_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            installed = root / "installed"
            source.mkdir()
            installed.mkdir()
            cache = installed / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "validator.pyc").write_bytes(b"generated")

            report = COMPARE_MODULE.compare_trees(source, installed)

            self.assertTrue(report.is_clean)


if __name__ == "__main__":
    unittest.main()
