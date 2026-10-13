import json
import sys
from pathlib import Path

import pytest

from test_validate_project import make_valid_project

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from render_asset_isolation_review import render_asset


def test_page_fragment_isolation_leaves_global_manifest_unchanged(tmp_path: Path) -> None:
    make_valid_project(tmp_path)
    global_path = tmp_path / "asset-manifest.json"
    asset = json.loads(global_path.read_text(encoding="utf-8"))["assets"][0]
    global_path.write_text('{"assets": []}\n', encoding="utf-8")
    global_before = global_path.read_bytes()
    asset.pop("isolation_review", None)
    fragment = Path("page-shards/batch-v1/S01/asset-manifest.fragment.json")
    fragment_path = tmp_path / fragment
    fragment_path.parent.mkdir(parents=True)
    fragment_path.write_text(json.dumps({"slide_id": "S01", "assets": [asset]}), encoding="utf-8")

    image_path, packet_path = render_asset(tmp_path, asset["id"], fragment)

    assert image_path.is_file() and packet_path.is_file()
    assert global_path.read_bytes() == global_before
    updated = json.loads(fragment_path.read_text(encoding="utf-8"))
    assert updated["assets"][0]["isolation_review"]["status"] == "pending"


def test_page_fragment_rejects_wrong_owner_and_global_path(tmp_path: Path) -> None:
    make_valid_project(tmp_path)
    asset = json.loads((tmp_path / "asset-manifest.json").read_text(encoding="utf-8"))["assets"][0]
    fragment = Path("page-shards/batch-v1/S02/asset-manifest.fragment.json")
    fragment_path = tmp_path / fragment
    fragment_path.parent.mkdir(parents=True)
    fragment_path.write_text(json.dumps({"slide_id": "S02", "assets": [asset]}), encoding="utf-8")
    with pytest.raises(ValueError, match="not an approved owner"):
        render_asset(tmp_path, asset["id"], fragment)
    with pytest.raises(ValueError, match="under page-shards"):
        render_asset(tmp_path, asset["id"], Path("asset-manifest.json"))
