"""Tests for the optional, source-bound full-slide reconstruction asset profile."""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

SKILL_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
sys.path.insert(0, str(TESTS_ROOT))

from delivery_export import export_delivery
from delivery_modes import validate_delivery
from test_delivery_modes import (
    _write_json,
    digest,
    load,
    make_concept_project,
    refresh_concept_input_hashes,
    write_asset_package,
    write_delivery_mode,
)


def _write_text(root: Path, relative: str, value: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def _add_asset(root: Path, manifest: dict, asset_id: str, locator: str) -> None:
    row = dict(manifest["assets"][0])
    row["id"] = asset_id
    row["source_locator"] = locator
    manifest["assets"].append(row)
    manifest["coverage"][0]["asset_ids"].append(asset_id)


def _make_full_slide_project(
    root: Path,
    *,
    include_connector_asset: bool = False,
    include_opaque_background: bool = False,
    canvas_width: int = 1672,
    canvas_height: int = 941,
    outcome: str = "agent-reviewed",
) -> Path:
    root = make_concept_project(root)
    write_delivery_mode(root, "assets")
    write_asset_package(root)

    brief = load(root, "brief.json")
    brief["delivery"] = {"asset_scope": "full-slide"}
    _write_json(root, "brief.json", brief)

    concept = root / "concepts/S01.png"
    render_path = root / "reconstruction/render-S01.png"
    render_path.parent.mkdir(parents=True, exist_ok=True)
    render = Image.new("RGB", (canvas_width, canvas_height), "#f0ece5")
    draw = ImageDraw.Draw(render)
    draw.rectangle((90, 70, 880, 190), fill="#16344c")
    draw.line((180, 460, 930, 460), fill="#2b8293", width=12)
    render.save(render_path)

    files = {
        "reconstruction/background.json": '{"type":"linear-gradient","colors":["#f0ece5","#ffffff"]}\n',
        "reconstruction/connector.svg": '<svg xmlns="http://www.w3.org/2000/svg"><path d="M10 10L80 80"/></svg>\n',
        "reconstruction/arrow.svg": '<svg xmlns="http://www.w3.org/2000/svg"><path d="M5 15H90" marker-end="url(#arrow)"/></svg>\n',
        "reconstruction/title.json": '{"text":"示例页面","font":"Local-display-serif","tracking":-0.02}\n',
        "reconstruction/renderer.html": "<!doctype html><script src='renderer.js'></script>\n",
        "reconstruction/renderer.js": "renderReconstruction();\n",
        "reconstruction/shared.css": "@font-face { font-family: Local-display-serif; src: url(display.woff2); }\n",
        "reconstruction/license.txt": "Example font license record for the local contract test.\n",
        "reconstruction/display.woff2": "test font bytes\n",
    }
    for relative, content in files.items():
        _write_text(root, relative, content)

    asset_manifest = load(root, "asset-manifest.json")
    items = [
        {
            "id": "background-main",
            "role": "background",
            "bbox": [0, 0, canvas_width, canvas_height],
            "z": 0,
            "representation": "native",
            "source_path": "reconstruction/background.json",
            "source_sha256": digest(root / "reconstruction/background.json"),
        },
        {
            "id": "illustration-main",
            "role": "illustration",
            "bbox": [1060, 230, 430, 460],
            "z": 4,
            "representation": "asset",
            "asset_id": "A-S01-01",
        },
        {
            "id": "connector-main",
            "role": "connector",
            "bbox": [100, 390, 820, 160],
            "z": 2,
            "representation": "native",
            "source_path": "reconstruction/connector.svg",
            "source_sha256": digest(root / "reconstruction/connector.svg"),
        },
        {
            "id": "arrow-main",
            "role": "arrow",
            "bbox": [120, 430, 760, 60],
            "z": 3,
            "representation": "native",
            "source_path": "reconstruction/arrow.svg",
            "source_sha256": digest(root / "reconstruction/arrow.svg"),
        },
        {
            "id": "title-main",
            "role": "special-typography",
            "bbox": [90, 70, 790, 130],
            "z": 5,
            "representation": "native",
            "source_path": "reconstruction/title.json",
            "source_sha256": digest(root / "reconstruction/title.json"),
        },
    ]
    if include_connector_asset:
        _add_asset(root, asset_manifest, "A-S01-CONNECTOR", "concepts/S01.png#connector")
        items.append({
            "id": "connector-asset",
            "role": "connector",
            "bbox": [90, 600, 260, 130],
            "z": 6,
            "representation": "asset",
            "asset_id": "A-S01-CONNECTOR",
        })
    if include_opaque_background:
        opaque_path = root / "assets/opaque-background.png"
        opaque_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (canvas_width, canvas_height), "#e7e3da").save(opaque_path)
        opaque_record = _write_text(
            root,
            "generation/opaque-background.md",
            "Local contract-test record for the intentionally opaque full-page background.\n",
        )
        opaque_asset = dict(asset_manifest["assets"][0])
        opaque_generation = dict(opaque_asset["generation"])
        opaque_generation.update({
            "method": "local contract-test asset",
            "prompt": "Create one intentionally opaque full-slide background asset.",
            "record_path": "generation/opaque-background.md",
            "record_sha256": digest(opaque_record),
        })
        opaque_asset.update({
            "id": "A-S01-BG",
            "path": "assets/opaque-background.png",
            "sha256": digest(opaque_path),
            "source_locator": "concepts/S01.png#full-slide-background",
            "requires_transparency": False,
            "opaque_reason": "An opaque full-page background is intentionally kept as one independent image asset.",
            "generation": opaque_generation,
        })
        asset_manifest["assets"].append(opaque_asset)
        asset_manifest["coverage"][0]["asset_ids"].append("A-S01-BG")
        items.append({
            "id": "background-asset",
            "role": "background",
            "bbox": [0, 0, canvas_width, canvas_height],
            "z": -1,
            "representation": "asset",
            "asset_id": "A-S01-BG",
        })

    concept_hash = digest(concept)
    render_hash = digest(render_path)
    reconstruction_map = {
        "version": "apw-reconstruction-v1",
        "canvas": {"width": canvas_width, "height": canvas_height},
        "slides": [{
            "slide_id": "S01",
            "concept_path": "concepts/S01.png",
            "concept_sha256": concept_hash,
            "items": items,
            "render_path": "reconstruction/render-S01.png",
            "render_sha256": render_hash,
            "renderer_path": "reconstruction/renderer.html",
            "renderer_sha256": digest(root / "reconstruction/renderer.html"),
            "review": {
                "actor": "agent",
                "concept_sha256": concept_hash,
                "render_sha256": render_hash,
                "coverage": "all-inventoried-elements",
                "outcome": outcome,
                "user_acceptance": "not-recorded",
            },
        }],
        "dependency_files": [
            {"path": "reconstruction/shared.css", "sha256": digest(root / "reconstruction/shared.css")},
            {"path": "reconstruction/renderer.js", "sha256": digest(root / "reconstruction/renderer.js")},
            {"path": "reconstruction/display.woff2", "sha256": digest(root / "reconstruction/display.woff2")},
            {"path": "reconstruction/license.txt", "sha256": digest(root / "reconstruction/license.txt")},
        ],
    }
    map_path = "reconstruction/reconstruction-map.json"
    _write_json(root, map_path, reconstruction_map)
    asset_manifest["reconstruction"] = {
        "contract_version": "apw-reconstruction-v1",
        "map_path": map_path,
        "map_sha256": digest(root / map_path),
    }
    _write_json(root, "asset-manifest.json", asset_manifest)
    refresh_concept_input_hashes(root)
    return root


def _rewrite_map(root: Path, map_doc: dict) -> None:
    map_path = "reconstruction/reconstruction-map.json"
    _write_json(root, map_path, map_doc)
    manifest = load(root, "asset-manifest.json")
    manifest["reconstruction"]["map_sha256"] = digest(root / map_path)
    _write_json(root, "asset-manifest.json", manifest)


def _set_renderer_html(root: Path, html: str) -> dict:
    renderer = _write_text(root, "reconstruction/renderer.html", html)
    map_doc = load(root, "reconstruction/reconstruction-map.json")
    map_doc["slides"][0]["renderer_sha256"] = digest(renderer)
    _rewrite_map(root, map_doc)
    refresh_concept_input_hashes(root)
    return map_doc


class ReconstructionContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = _make_full_slide_project(Path(self.temp.name) / "full-slide")

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_full_slide_profile_binds_native_sources_and_separate_render(self):
        report = validate_delivery(self.root, "assets", "assets")
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["facts"]["reconstruction_status"], "agent-reviewed")
        self.assertEqual(report["facts"]["reconstruction_user_acceptance"], "not-recorded")
        self.assertIn("cannot detect unlisted pixels", report["facts"]["asset_coverage_scope"])
        self.assertFalse((self.root / "scene-graph.json").exists())

    def test_project_can_choose_a_different_positive_integer_canvas(self):
        root = _make_full_slide_project(
            Path(self.temp.name) / "wide-canvas",
            canvas_width=1920,
            canvas_height=1080,
        )
        report = validate_delivery(root, "assets", "assets")
        self.assertTrue(report["ok"], report["errors"])

        map_doc = load(root, "reconstruction/reconstruction-map.json")
        map_doc["canvas"] = {"width": 1920.0, "height": 1080.5}
        _rewrite_map(root, map_doc)
        invalid = validate_delivery(root, "assets", "assets")
        self.assertFalse(invalid["ok"])
        self.assertTrue(any("canvas.width: positive finite integer required" in error for error in invalid["errors"]))
        self.assertTrue(any("canvas.height: positive finite integer required" in error for error in invalid["errors"]))

        map_doc["canvas"] = {"width": 0, "height": 1080}
        _rewrite_map(root, map_doc)
        zero = validate_delivery(root, "assets", "assets")
        self.assertFalse(zero["ok"])
        self.assertTrue(any("canvas.width: positive finite integer required" in error for error in zero["errors"]))

        map_doc["canvas"] = {"width": 1920, "height": True}
        _rewrite_map(root, map_doc)
        boolean = validate_delivery(root, "assets", "assets")
        self.assertFalse(boolean["ok"])
        self.assertTrue(any("canvas.height: positive finite integer required" in error for error in boolean["errors"]))

    def test_full_slide_scope_requires_the_reconstruction_profile(self):
        manifest = load(self.root, "asset-manifest.json")
        manifest.pop("reconstruction")
        _write_json(self.root, "asset-manifest.json", manifest)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("required object for full-slide scope" in error for error in report["errors"]))

    def test_declared_connector_asset_cannot_be_omitted_from_inventory(self):
        root = _make_full_slide_project(Path(self.temp.name) / "connector", include_connector_asset=True)
        map_doc = load(root, "reconstruction/reconstruction-map.json")
        map_doc["slides"][0]["items"] = [row for row in map_doc["slides"][0]["items"] if row["id"] != "connector-asset"]
        _rewrite_map(root, map_doc)
        report = validate_delivery(root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("asset row is not covered" in error and "A-S01-CONNECTOR" in error for error in report["errors"]))

    def test_native_source_must_exist_and_match_its_declared_hash(self):
        map_doc = load(self.root, "reconstruction/reconstruction-map.json")
        map_doc["slides"][0]["items"][0]["source_path"] = "reconstruction/missing-background.json"
        _rewrite_map(self.root, map_doc)
        missing = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(missing["ok"])
        self.assertTrue(any("file does not exist" in error and "source_path" in error for error in missing["errors"]))

        map_doc["slides"][0]["items"][0]["source_path"] = "reconstruction/background.json"
        map_doc["slides"][0]["items"][0]["source_sha256"] = "0" * 64
        _rewrite_map(self.root, map_doc)
        stale = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(stale["ok"])
        self.assertTrue(any("SHA-256 does not match" in error and "source_path" in error for error in stale["errors"]))

    def test_slide_coverage_must_match_the_current_deck_exactly(self):
        concept = self.root / "concepts/S02.png"
        Image.new("RGB", (1672, 941), "#e8e6df").save(concept)
        deck = load(self.root, "deck-spec.json")
        deck["slides"].append({
            "id": "S02",
            "title": "第二页",
            "message": "新增的第二页",
            "concept_path": "concepts/S02.png",
            "reference_ids": ["R1"],
            "copy": [{"id": "C2", "role": "title", "text": "第二页", "truth_status": "illustrative", "source_ids": []}],
        })
        _write_json(self.root, "deck-spec.json", deck)
        refresh_concept_input_hashes(self.root)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("must cover every current deck slide exactly once" in error for error in report["errors"]))

    def test_review_hashes_bind_the_current_reconstruction_render(self):
        map_doc = load(self.root, "reconstruction/reconstruction-map.json")
        map_doc["slides"][0]["review"]["render_sha256"] = "0" * 64
        _rewrite_map(self.root, map_doc)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("review.render_sha256" in error for error in report["errors"]))

        map_doc["slides"][0]["render_path"] = "concepts/S01.png"
        map_doc["slides"][0]["render_sha256"] = digest(self.root / "concepts/S01.png")
        map_doc["slides"][0]["review"]["render_sha256"] = digest(self.root / "concepts/S01.png")
        _rewrite_map(self.root, map_doc)
        flattened = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(flattened["ok"])
        self.assertTrue(any("must be a separate artifact from its concept" in error for error in flattened["errors"]))

    def test_full_canvas_background_cannot_reuse_the_exact_concept_image(self):
        map_doc = load(self.root, "reconstruction/reconstruction-map.json")
        concept_hash = digest(self.root / "concepts/S01.png")
        background = map_doc["slides"][0]["items"][0]
        background["source_path"] = "concepts/S01.png"
        background["source_sha256"] = concept_hash
        _rewrite_map(self.root, map_doc)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("current full-page concept image cannot be reused" in error for error in report["errors"]))

    def test_concept_image_cannot_be_reused_as_a_scaled_illustration_asset(self):
        manifest = load(self.root, "asset-manifest.json")
        concept = self.root / "concepts/S01.png"
        asset = manifest["assets"][0]
        asset.update({
            "path": "concepts/S01.png",
            "sha256": digest(concept),
            "requires_transparency": False,
            "opaque_reason": "The concept image is retained as one intact raster object.",
        })
        _write_json(self.root, "asset-manifest.json", manifest)
        map_doc = load(self.root, "reconstruction/reconstruction-map.json")
        illustration = next(item for item in map_doc["slides"][0]["items"] if item["id"] == "illustration-main")
        illustration["bbox"] = [1060, 230, 430, 460]
        _rewrite_map(self.root, map_doc)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("current full-page concept image cannot be reused" in error for error in report["errors"]))

    def test_concept_image_cannot_be_reused_as_a_non_background_native_source(self):
        concept = self.root / "concepts/S01.png"
        map_doc = load(self.root, "reconstruction/reconstruction-map.json")
        illustration = next(item for item in map_doc["slides"][0]["items"] if item["id"] == "arrow-main")
        illustration.update({
            "role": "illustration",
            "bbox": [1060, 230, 430, 460],
            "source_path": "concepts/S01.png",
            "source_sha256": digest(concept),
        })
        _rewrite_map(self.root, map_doc)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("current full-page concept image cannot be reused as a native reconstruction source" in error for error in report["errors"]))

    def test_known_native_source_formats_must_parse(self):
        cases = (
            ("svg", "arrow-main", "reconstruction/arrow.svg", "not an SVG file", "not valid SVG"),
            ("json", "title-main", "reconstruction/title.json", "{not json", "not valid JSON"),
            ("xml", "connector-main", "reconstruction/bad.xml", "<broken", "not valid XML"),
        )
        for suffix, item_id, source_path, content, expected in cases:
            with self.subTest(suffix=suffix):
                root = _make_full_slide_project(Path(self.temp.name) / f"invalid-native-{suffix}")
                source = _write_text(root, source_path, content)
                map_doc = load(root, "reconstruction/reconstruction-map.json")
                item = next(row for row in map_doc["slides"][0]["items"] if row["id"] == item_id)
                item["source_path"] = source_path
                item["source_sha256"] = digest(source)
                _rewrite_map(root, map_doc)
                report = validate_delivery(root, "assets", "assets")
                self.assertFalse(report["ok"])
                self.assertTrue(any(expected in error for error in report["errors"]), report["errors"])

    def test_renderer_html_missing_or_unbundled_static_reference_blocks_export(self):
        root = _make_full_slide_project(Path(self.temp.name) / "missing-html-reference")
        _set_renderer_html(root, "<script src='missing.js'></script>\n")
        report = validate_delivery(root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("file does not exist" in error and "missing.js" in error for error in report["errors"]))
        self.assertFalse(export_delivery(root, root.parent / "must-not-export-missing-js", "assets")["ok"])

        root = _make_full_slide_project(Path(self.temp.name) / "unbundled-html-reference")
        _set_renderer_html(root, "<link rel='stylesheet' href='shared.css'>\n")
        map_doc = load(root, "reconstruction/reconstruction-map.json")
        map_doc["dependency_files"] = [row for row in map_doc["dependency_files"] if row["path"] != "reconstruction/shared.css"]
        _rewrite_map(root, map_doc)
        report = validate_delivery(root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("must be a current concept, asset, native source, renderer, or declared map dependency" in error for error in report["errors"]))

    def test_renderer_css_urls_must_be_present_and_packaged(self):
        root = _make_full_slide_project(Path(self.temp.name) / "missing-css-url")
        _set_renderer_html(root, "<link rel='stylesheet' href='shared.css'>\n")
        _write_text(root, "reconstruction/shared.css", "@font-face { src: url(missing.woff2); }\n")
        report = validate_delivery(root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("missing.woff2" in error for error in report["errors"]), report["errors"])

    def test_renderer_rejects_external_runtime_but_allows_external_navigation(self):
        root = _make_full_slide_project(Path(self.temp.name) / "external-renderer-link")
        _set_renderer_html(root, "<a href='https://example.org/manual'>Manual</a>\n")
        report = validate_delivery(root, "assets", "assets")
        self.assertTrue(report["ok"], report["errors"])
        self.assertIn("JavaScript imports and runtime-generated requests are not inspected", report["facts"]["renderer_dependency_scope"])
        exported = export_delivery(root, root.parent / "external-navigation-package", "assets")
        self.assertTrue(exported["ok"], exported["errors"])
        readme = (root.parent / "external-navigation-package" / "README.md").read_text(encoding="utf-8")
        self.assertIn("JavaScript import 与运行时生成的请求不在此检查范围内", readme)

        _set_renderer_html(root, "<script src='https://cdn.example.org/renderer.js'></script>\n")
        report = validate_delivery(root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("external runtime resource is not portable" in error for error in report["errors"]))

    def test_renderer_can_reference_an_asset_already_in_the_export_union(self):
        root = _make_full_slide_project(Path(self.temp.name) / "asset-union-reference")
        _set_renderer_html(root, "<img src='../assets/component.png' alt='component'>\n")
        report = validate_delivery(root, "assets", "assets")
        self.assertTrue(report["ok"], report["errors"])

    def test_renderer_cannot_embed_a_current_concept_image(self):
        root = _make_full_slide_project(Path(self.temp.name) / "concept-renderer-reference")
        _set_renderer_html(root, "<img src='../concepts/S01.png' alt='concept'>\n")
        report = validate_delivery(root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("full-page concept image cannot be embedded" in error for error in report["errors"]))

        root = _make_full_slide_project(Path(self.temp.name) / "concept-data-url")
        concept_bytes = (root / "concepts/S01.png").read_bytes()
        data_url = "data:image/png;base64," + base64.b64encode(concept_bytes).decode("ascii")
        _set_renderer_html(root, f"<img src='{data_url}' alt='concept'>\n")
        report = validate_delivery(root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("full-page concept image cannot be embedded" in error for error in report["errors"]))

    def test_comparison_html_dependency_may_show_the_original_concept(self):
        root = _make_full_slide_project(Path(self.temp.name) / "comparison-html-concept-overlay")
        comparison = _write_text(
            root,
            "reconstruction/rebuild-S01.html",
            "<img src='../concepts/S01.png' alt='original concept overlay'>\n",
        )
        map_doc = load(root, "reconstruction/reconstruction-map.json")
        map_doc["dependency_files"].append({
            "path": "reconstruction/rebuild-S01.html",
            "sha256": digest(comparison),
        })
        _rewrite_map(root, map_doc)

        report = validate_delivery(root, "assets", "assets")
        self.assertTrue(report["ok"], report["errors"])
        exported = export_delivery(root, root.parent / "comparison-html-package", "assets")
        self.assertTrue(exported["ok"], exported["errors"])
        self.assertTrue((root.parent / "comparison-html-package" / "项目证据" / "reconstruction" / "rebuild-S01.html").is_file())

    def test_reconstruction_paths_reject_traversal_and_case_collisions(self):
        map_doc = load(self.root, "reconstruction/reconstruction-map.json")
        map_doc["slides"][0]["items"][0]["source_path"] = "../outside-background.json"
        _rewrite_map(self.root, map_doc)
        traversal = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(traversal["ok"])
        self.assertTrue(any("path must stay inside the project" in error for error in traversal["errors"]))

        map_doc["slides"][0]["items"][0]["source_path"] = "reconstruction/background.json"
        map_doc["dependency_files"].append({
            "path": "Reconstruction/background.json",
            "sha256": digest(self.root / "reconstruction/background.json"),
        })
        _rewrite_map(self.root, map_doc)
        collision = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(collision["ok"])
        self.assertTrue(any("collides with" in error for error in collision["errors"]))

    def test_reconstruction_paths_reject_symlink_components_when_supported(self):
        link = self.root / "reconstruction/background-link.json"
        try:
            link.symlink_to(self.root / "reconstruction/background.json")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation is unavailable: {exc}")
        map_doc = load(self.root, "reconstruction/reconstruction-map.json")
        map_doc["slides"][0]["items"][0]["source_path"] = "reconstruction/background-link.json"
        map_doc["slides"][0]["items"][0]["source_sha256"] = digest(link.resolve())
        _rewrite_map(self.root, map_doc)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("symbolic links are not allowed" in error for error in report["errors"]))

    def test_needs_repair_keeps_full_slide_delivery_incomplete(self):
        map_doc = load(self.root, "reconstruction/reconstruction-map.json")
        map_doc["slides"][0]["review"]["outcome"] = "needs-repair"
        _rewrite_map(self.root, map_doc)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertFalse(report["ok"])
        self.assertTrue(any("needs-repair means full-slide delivery is incomplete" in error for error in report["errors"]))
        self.assertFalse(export_delivery(self.root, self.root.parent / "must-not-export", "assets")["ok"])

    def test_project_selected_role_inventory_has_no_required_connector_count(self):
        map_doc = load(self.root, "reconstruction/reconstruction-map.json")
        map_doc["slides"][0]["items"] = [row for row in map_doc["slides"][0]["items"] if row["role"] not in {"connector", "arrow"}]
        _rewrite_map(self.root, map_doc)
        report = validate_delivery(self.root, "assets", "assets")
        self.assertTrue(report["ok"], report["errors"])

    def test_export_keeps_map_and_all_reconstruction_paths_reloadable(self):
        root = _make_full_slide_project(
            Path(self.temp.name) / "portable-source",
            include_opaque_background=True,
        )
        output = root.parent / "portable-reconstruction"
        exported = export_delivery(root, output, "assets")
        self.assertTrue(exported["ok"], exported["errors"])
        self.assertEqual(exported["delivery_label"], "local-full-slide-reconstruction-delivery")
        self.assertIn("每个映射原生对象源文件", (output / "README.md").read_text(encoding="utf-8"))
        self.assertTrue((output / "项目证据/reconstruction/reconstruction-map.json").is_file())
        self.assertTrue((output / "项目证据/reconstruction/background.json").is_file())
        self.assertTrue((output / "项目证据/reconstruction/render-S01.png").is_file())
        self.assertTrue((output / "项目证据/reconstruction/renderer.html").is_file())
        self.assertTrue((output / "项目证据/reconstruction/shared.css").is_file())
        self.assertTrue((output / "项目证据/reconstruction/license.txt").is_file())
        self.assertTrue((output / "独立素材/A-S01-01.png").is_file())
        self.assertTrue((output / "独立素材/A-S01-BG.png").is_file())
        native_copies = {
            "S01-background-main.json": "reconstruction/background.json",
            "S01-connector-main.svg": "reconstruction/connector.svg",
            "S01-arrow-main.svg": "reconstruction/arrow.svg",
            "S01-title-main.json": "reconstruction/title.json",
        }
        for package_name, source_path in native_copies.items():
            package_path = output / "独立素材" / package_name
            self.assertTrue(package_path.is_file(), package_name)
            self.assertEqual(package_path.read_bytes(), (root / source_path).read_bytes())
            evidence_path = output / "项目证据" / source_path
            self.assertTrue(evidence_path.is_file(), source_path)
            self.assertEqual(evidence_path.read_bytes(), (root / source_path).read_bytes())
        self.assertFalse((output / "透明资产/A-S01-01.png").exists())
        self.assertFalse(list(output.rglob("*.pptx")))

        package_manifest = load(output, "package-manifest.json")
        for package_name, source_path in native_copies.items():
            self.assertEqual(package_manifest["source_files"][f"独立素材/{package_name}"], source_path)
            self.assertEqual(package_manifest["files"][f"独立素材/{package_name}"], digest(root / source_path))
        for relative in (
            "reconstruction/reconstruction-map.json",
            "reconstruction/background.json",
            "reconstruction/render-S01.png",
            "reconstruction/renderer.html",
            "reconstruction/shared.css",
            "reconstruction/renderer.js",
            "reconstruction/display.woff2",
            "reconstruction/license.txt",
        ):
            self.assertEqual(package_manifest["source_files"][f"项目证据/{relative}"], relative)
            self.assertEqual(package_manifest["source_sha256"][relative], digest(root / relative))

        evidence_root = output / "项目证据"
        reload_report = validate_delivery(evidence_root, "assets", "export")
        self.assertTrue(reload_report["ok"], reload_report["errors"])
        verified = export_delivery(root, output, "assets", verify_only=True)
        self.assertTrue(verified["ok"], verified["errors"])

    def test_selected_assets_without_full_slide_profile_keep_the_existing_contract(self):
        root = Path(self.temp.name) / "selected-assets"
        root = make_concept_project(root)
        write_delivery_mode(root, "assets")
        write_asset_package(root)
        report = validate_delivery(root, "assets", "assets")
        self.assertTrue(report["ok"], report["errors"])
        self.assertNotIn("reconstruction_status", report["facts"])
        self.assertIn("not a full visual decomposition", report["facts"]["asset_coverage_scope"])


if __name__ == "__main__":
    unittest.main()
