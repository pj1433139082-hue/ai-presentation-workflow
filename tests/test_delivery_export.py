"""Integration coverage for concept and transparent-asset delivery modes."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import apw
import delivery_modes
import export_final_package


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _draw_png(path: Path, *, transparent: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "RGBA" if transparent else "RGB"
    background = (255, 255, 255, 0) if transparent else (248, 249, 252)
    image = Image.new(mode, (1600, 900) if not transparent else (320, 220), background)
    draw = ImageDraw.Draw(image)
    if transparent:
        draw.ellipse((36, 26, 282, 194), fill=(16, 139, 161, 210))
        draw.ellipse((130, 80, 210, 160), fill=(245, 185, 66, 255))
    else:
        draw.rectangle((80, 80, 740, 250), fill=(18, 48, 84))
        draw.rectangle((80, 300, 980, 650), fill=(222, 239, 238))
    image.save(path, format="PNG")


def _init_project(root: Path, mode: str | None = None) -> Path:
    args = ["init", str(root)]
    if mode is not None:
        args.extend(["--mode", mode])
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exit_code = apw.main(args)
    report = json.loads(stdout.getvalue())
    if exit_code != 0 or not report.get("ok"):
        raise AssertionError(f"APW init failed: {report}")
    return root


def _apw_report(args: list[str]) -> tuple[int, dict]:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exit_code = apw.main(args)
    return exit_code, json.loads(stdout.getvalue())


def _complete_inputs(root: Path) -> None:
    """Turn a real init scaffold into one valid source-bound concept page."""
    source_path = root / "source-notes" / "example-source.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        "这是用于展示版式的自拟示例，不代表真实数据或研究结论。\n",
        encoding="utf-8",
    )
    reference_path = root / "references" / "reference-layout.png"
    _draw_png(reference_path)
    concept_path = root / "concepts" / "S01.png"
    _draw_png(concept_path)
    prompt_path = root / "provenance" / "original-prompt.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(
        "Create a restrained editorial title page. Keep the Chinese headline exact.\n",
        encoding="utf-8",
    )

    source = {
        "id": "SRC-EXAMPLE",
        "kind": "explicit-example-note",
        "truth_status": "illustrative",
        "locator": "自拟示例说明；不是外部事实来源。",
        "path": "source-notes/example-source.md",
        "sha256": _sha(source_path),
    }
    _write_json(
        root / "brief.json",
        {
            "project_id": root.name,
            "audience": "需要快速理解主题的读者",
            "goal": "用一页概念展示清楚说明主题和关键信息",
            "quality_profile": "draft",
            "language": "zh-CN",
            "delivery": {"format": "concept-only", "aspect_ratio": "16:9", "scope": "local-showcase-only"},
            "source_map": [source],
        },
    )
    copy = [
        {"id": "C-TITLE", "role": "title", "text": "示例主题：把信息讲清楚", "truth_status": "illustrative", "source_ids": ["SRC-EXAMPLE"]},
        {"id": "C-TAKEAWAY", "role": "key-takeaway", "text": "先说明问题，再给出可讨论的线索。", "truth_status": "illustrative", "source_ids": ["SRC-EXAMPLE"]},
        {"id": "C-CAVEAT", "role": "caption", "text": "自拟示例内容", "truth_status": "illustrative", "source_ids": ["SRC-EXAMPLE"]},
    ]
    _write_json(
        root / "deck-spec.json",
        {
            "slides": [
                {
                    "id": "S01",
                    "title": copy[0]["text"],
                    "message": copy[1]["text"],
                    "concept_path": "concepts/S01.png",
                    "copy": copy,
                }
            ]
        },
    )
    reference = {
        "id": "REF-01",
        "status": "analyzed",
        "image_path": "references/reference-layout.png",
        "sha256": _sha(reference_path),
        "source_locator": "local://test-catalog/editorial-reference-01",
        "usage_note": "用于观察标题与留白关系。",
        "transferable_rules": ["标题层级明确", "留白集中于主标题周围"],
        "project_translation": ["使用本项目的中文文案和色彩"],
        "do_not_copy": ["不复制原图的品牌标记和装饰图形"],
    }
    _write_json(
        root / "reference-study.json",
        {"status": "analyzed", "references": [reference], "selected_reference_ids": ["REF-01"]},
    )
    _write_json(
        root / "style-contract.json",
        {
            "version": "draft",
            "selected_reference_ids": ["REF-01"],
            "readability_profile": {"font_floors_pt": {"title": 32, "body": 20}, "minimum_contrast_ratio": 4.5},
        },
    )
    input_hashes = {
        "brief": _sha(root / "brief.json"),
        "deck_spec": _sha(root / "deck-spec.json"),
        "reference_study": _sha(root / "reference-study.json"),
        "style_contract": _sha(root / "style-contract.json"),
    }
    _write_json(
        root / "concept-generation-log.json",
        {
            "status": "complete",
            "slides": [
                {
                    "slide_id": "S01",
                    "status": "generated",
                    "output_path": "concepts/S01.png",
                    "output_sha256": _sha(concept_path),
                    "input_sha256": input_hashes,
                    "copy_map": copy,
                    "reference_images": [
                        {"reference_id": "REF-01", "path": "references/reference-layout.png", "sha256": _sha(reference_path)}
                    ],
                }
            ],
        },
    )


def _add_transparent_asset(root: Path) -> None:
    asset_path = root / "assets" / "A-S01-01.png"
    _draw_png(asset_path, transparent=True)
    record_path = root / "provenance" / "asset-generation" / "A-S01-01.md"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(
        "本地展示素材记录：从当前 S01 概念提取的透明装饰插画。\n",
        encoding="utf-8",
    )
    _write_json(
        root / "asset-manifest.json",
        {
            "contract_version": "showcase-assets-v1",
            "coverage": [{"slide_id": "S01", "asset_ids": ["A-S01-01"], "status": "complete"}],
            "assets": [
                {
                    "id": "A-S01-01",
                    "slide_id": "S01",
                    "kind": "picture",
                    "path": "assets/A-S01-01.png",
                    "sha256": _sha(asset_path),
                    "truth_status": "illustrative",
                    "source_locator": "由当前概念图派生的本地展示插画",
                    "requires_transparency": True,
                    "generation": {
                        "method": "imagegen-edit",
                        "prompt": "Extract the small decorative illustration onto a transparent background.",
                        "source_concept_path": "concepts/S01.png",
                        "source_concept_sha256": _sha(root / "concepts" / "S01.png"),
                        "record_path": "provenance/asset-generation/A-S01-01.md",
                        "record_sha256": _sha(record_path),
                    },
                }
            ],
        },
    )


class DeliveryExportTests(unittest.TestCase):
    def test_default_init_concept_export_and_verify_preserve_evidence_without_pptx(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _init_project(Path(temp) / "concept-project")
            self.assertEqual(delivery_modes.read_delivery_mode(root), "concept")
            self.assertFalse((root / "scene-graph.json").exists())
            self.assertFalse((root / "asset-manifest.json").exists())
            _complete_inputs(root)

            status_code, status = _apw_report(["status", str(root)])
            self.assertEqual(status_code, 0, status)
            self.assertTrue(status["ok"], status)
            self.assertEqual(status["delivery_mode"], "concept")
            self.assertEqual(set(status["ready_stages"]), {"concept", "export"})
            check_code, checked = _apw_report(["check", str(root), "--stage", "concept"])
            self.assertEqual(check_code, 0, checked)
            self.assertTrue(checked["ok"], checked)
            validator_cli = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_project.py"), str(root), "--stage", "concept"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(validator_cli.returncode, 0, validator_cli.stdout + validator_cli.stderr)
            self.assertTrue(json.loads(validator_cli.stdout)["ok"])

            output = root.parent / "concept-project-delivery"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = apw.main(["export", str(root), "--output", str(output)])
            exported = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0, exported)
            self.assertTrue(exported["ok"], exported)
            self.assertEqual(exported["delivery_label"], "local-concept-delivery")
            self.assertTrue((output / "项目证据" / "brief.json").is_file())
            self.assertTrue((output / "项目证据" / "source-notes" / "example-source.md").is_file())
            self.assertTrue((output / "项目证据" / "references" / "reference-layout.png").is_file())
            self.assertTrue((output / "项目证据" / "provenance" / "original-prompt.md").is_file())
            self.assertTrue((output / "概念图" / "01-S01.png").is_file())
            receipt = json.loads((output / "execution-receipt.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["assembly"], "not-requested")
            self.assertEqual(receipt["pptx"], "not-produced")
            self.assertEqual(receipt["human_gates"], "not-claimed")
            self.assertFalse(list(output.rglob("*.pptx")))

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                verify_code = apw.main(["export", str(root), "--output", str(output), "--verify"])
            verified = json.loads(stdout.getvalue())
            self.assertEqual(verify_code, 0, verified)
            self.assertTrue(verified["ok"], verified)

            # The separate public exporter command must route this explicit
            # light mode through the same delivery contract, for both publish and verify.
            routed_output = root.parent / "exporter-cli-delivery"
            with patch.object(sys, "argv", ["export_final_package.py", str(root), "--output", str(routed_output)]), contextlib.redirect_stdout(io.StringIO()):
                export_final_package.main()
            self.assertTrue((routed_output / "package-manifest.json").is_file())
            with patch.object(sys, "argv", ["export_final_package.py", str(root), "--output", str(routed_output), "--verify"]), contextlib.redirect_stdout(io.StringIO()):
                export_final_package.main()
            self.assertFalse(list(routed_output.rglob("*.pptx")))

    def test_assets_export_includes_real_transparent_file_and_no_pptx(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _init_project(Path(temp) / "asset-project", "assets")
            _complete_inputs(root)
            _add_transparent_asset(root)
            report = delivery_modes.validate_delivery(root, "assets", "assets")
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["facts"]["asset_status"], "ready")
            self.assertFalse((root / "scene-graph.json").exists())

            output = root.parent / "asset-project-delivery"
            exported = apw.export_project(root, output)
            self.assertTrue(exported["ok"], exported)
            self.assertEqual(exported["asset_count"], 1)
            delivered_asset = output / "透明资产" / "A-S01-01.png"
            self.assertTrue(delivered_asset.is_file())
            with Image.open(delivered_asset) as image:
                self.assertEqual(image.mode, "RGBA")
                alpha = image.getchannel("A")
                self.assertLess(alpha.getextrema()[0], 255)
                self.assertGreater(alpha.getextrema()[1], 0)
            verify = apw.export_project(root, output, verify_only=True)
            self.assertTrue(verify["ok"], verify)
            self.assertFalse(list(output.rglob("*.pptx")))

    def test_forged_asset_approval_and_light_mode_build_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            concept_root = _init_project(base / "concept-project")
            _complete_inputs(concept_root)
            concept_code, concept_build = _apw_report(["build", str(concept_root), "--version", "v1"])
            self.assertEqual(concept_code, 1)
            self.assertFalse(concept_build["ok"])
            self.assertEqual(concept_build["phase"], "mode-boundary")
            self.assertFalse((concept_root / "assembly").exists())

            assets_root = _init_project(base / "asset-project", "assets")
            _complete_inputs(assets_root)
            _add_transparent_asset(assets_root)
            assets_code, assets_build = _apw_report(["build", str(assets_root), "--version", "v1"])
            self.assertEqual(assets_code, 1)
            self.assertFalse(assets_build["ok"])
            self.assertEqual(assets_build["phase"], "mode-boundary")
            self.assertFalse((assets_root / "assembly").exists())

            manifest_path = assets_root / "asset-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["status"] = "accepted"
            _write_json(manifest_path, manifest)
            rejected = delivery_modes.validate_delivery(assets_root, "assets", "assets")
            self.assertFalse(rejected["ok"])
            self.assertTrue(any("approval" in issue.lower() or "status" in issue.lower() for issue in rejected["errors"]))
            output = base / "forged-asset-package"
            self.assertFalse(apw.export_project(assets_root, output)["ok"])
            self.assertFalse(output.exists())

    def test_verify_rejects_forged_claims_extra_pptx_and_hash_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _init_project(Path(temp) / "concept-project")
            _complete_inputs(root)
            output = root.parent / "delivery"
            self.assertTrue(apw.export_project(root, output)["ok"])

            manifest_path = output / "package-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["human_gates"] = "approved"
            _write_json(manifest_path, manifest)
            forged_claim = apw.export_project(root, output, verify_only=True)
            self.assertFalse(forged_claim["ok"])
            self.assertTrue(any("manifest" in issue.lower() for issue in forged_claim["errors"]))

            # Restore the canonical manifest, then independently test exact file
            # coverage and copied-content hashes.
            self.assertTrue(apw.export_project(root, output.parent / "delivery-clean")["ok"])
            clean = output.parent / "delivery-clean"
            extra_pptx = clean / "PPT成稿" / "unexpected.pptx"
            extra_pptx.parent.mkdir(parents=True, exist_ok=True)
            extra_pptx.write_bytes(b"not a produced deck")
            extra_result = apw.export_project(root, clean, verify_only=True)
            self.assertFalse(extra_result["ok"])
            self.assertTrue(any("coverage" in issue.lower() for issue in extra_result["errors"]))
            extra_pptx.unlink()

            copied_concept = clean / "概念图" / "01-S01.png"
            copied_concept.write_bytes(copied_concept.read_bytes() + b"tampered")
            hash_result = apw.export_project(root, clean, verify_only=True)
            self.assertFalse(hash_result["ok"])
            self.assertTrue(any("differs" in issue.lower() or "hash" in issue.lower() for issue in hash_result["errors"]))

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = _init_project(Path(temp) / "concept-project")
            _complete_inputs(root)
            output = root.parent / "delivery"
            first = apw.export_project(root, output)
            self.assertTrue(first["ok"], first)
            sentinel = output / "reviewer-note.txt"
            sentinel.write_text("keep this existing output intact", encoding="utf-8")
            second = apw.export_project(root, output)
            self.assertFalse(second["ok"])
            self.assertIn("already exists", second["errors"][0])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep this existing output intact")


if __name__ == "__main__":
    unittest.main()
