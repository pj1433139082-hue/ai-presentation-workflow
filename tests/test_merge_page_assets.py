import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from merge_page_assets import merge


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def asset(root: Path, sid: str, aid: str) -> dict:
    output = f"assets/{sid}/{aid}.png"
    path = root / output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(aid.encode())
    return {
        "id": aid, "slide_id": sid, "output": output,
        "sha256": hashlib.sha256(aid.encode()).hexdigest(),
        "status": "approved", "isolation_review": {"status": "passed"},
    }


def fixture(root: Path) -> None:
    write_json(root / "deck-spec.json", {"slides": [{"id": "S01"}, {"id": "S02"}]})
    write_json(root / "scene-graph.json", {"slides": [
        {"slide_id": "S01", "elements": [{"component_id": "C01"}]},
        {"slide_id": "S02", "elements": [{"component_id": "C02"}]},
    ]})
    write_json(root / "asset-manifest.json", {"assets": [asset(root, "S01", "C01")]})
    write_json(root / "page-shards/batch-v1/S02/asset-manifest.fragment.json", {
        "slide_id": "S02", "assets": [asset(root, "S02", "C02")],
    })


def test_merge_adds_page_assets_once_and_preserves_pilot(tmp_path: Path) -> None:
    fixture(tmp_path)
    assert merge(tmp_path, "batch-v1") == 1
    merged = json.loads((tmp_path / "asset-manifest.json").read_text(encoding="utf-8"))
    assert [entry["id"] for entry in merged["assets"]] == ["C01", "C02"]
    before = (tmp_path / "asset-manifest.json").read_bytes()
    assert merge(tmp_path, "batch-v1") == 0
    assert (tmp_path / "asset-manifest.json").read_bytes() == before


def test_merge_rejects_stale_asset_without_changing_manifest(tmp_path: Path) -> None:
    fixture(tmp_path)
    manifest_path = tmp_path / "asset-manifest.json"
    before = manifest_path.read_bytes()
    (tmp_path / "assets/S02/C02.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="missing or stale"):
        merge(tmp_path, "batch-v1")
    assert manifest_path.read_bytes() == before
