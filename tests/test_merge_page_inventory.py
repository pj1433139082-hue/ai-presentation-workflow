import copy
import hashlib
import json
import sys
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import merge_page_inventory as inventory
from test_validate_project import (ProjectValidator, gate_decision_values, make_valid_project,
                                  promote_fixture_to_production, value_sha256, write_json)


def read(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory_fixture(root):
    """Two-page production-contract mock; no claim of real visual approval."""
    make_valid_project(root)
    promote_fixture_to_production(root)
    deck = read(root, "deck-spec.json")
    second = copy.deepcopy(deck["slides"][0])
    second.update(id="S02", concept_path="concepts/S02.png")
    second["composition"]["layout_archetype"] = "comparison"
    (root / second["concept_path"]).write_bytes((root / deck["slides"][0]["concept_path"]).read_bytes())
    second["readability"]["full_size_review"]["path"] = second["concept_path"]
    deck["slides"].append(second)
    write_json(root, "deck-spec.json", deck)
    story = read(root, "storyboard.json")
    second_story = copy.deepcopy(story["slides"][0])
    second_story["id"] = "S02"
    story["slides"].append(second_story)
    write_json(root, "storyboard.json", story)
    calibration = read(root, "concept-calibration.json")
    for source in calibration["source_lineage"]:
        source["sha256"] = digest(root / source["path"])
    write_json(root, "concept-calibration.json", calibration)
    log = read(root, "concept-generation-log.json")
    second_log = copy.deepcopy(log["slides"][0])
    second_log.update(slide_id="S02", output_path=second["concept_path"])
    log["slides"].append(second_log)
    for record in log["slides"]:
        for source in record["source_lineage"]:
            source["sha256"] = digest(root / source["path"])
    write_json(root, "concept-generation-log.json", log)
    manifest = read(root, "asset-manifest.json")
    for asset in manifest["assets"]:
        asset["slide_ids"] = ["S01", "S02"]
        extra = copy.deepcopy(asset["references"][0])
        extra["path"] = second["concept_path"]
        asset["references"].append(extra)
    write_json(root, "asset-manifest.json", manifest)
    masters = read(root, "component-master-manifest.json")
    master = copy.deepcopy(masters["slides"][0])
    master.update(slide_id="S02", approved_contentful_path=second["concept_path"],
                  component_master_path="components/masters/S02-v1.png")
    (root / master["component_master_path"]).write_bytes((root / masters["slides"][0]["component_master_path"]).read_bytes())
    master["geometry_review"]["comparison_path"] = "reviews/S02-master-geometry.png"
    (root / master["geometry_review"]["comparison_path"]).write_bytes((root / masters["slides"][0]["geometry_review"]["comparison_path"]).read_bytes())
    masters["slides"].append(master)
    for row in masters["slides"]:
        row["concept_generation_log_sha256"] = digest(root / "concept-generation-log.json")
        row["preserved_fill_slots"] = [{key: slot[key] for key in ("id", "kind", "bbox")} for slot in second["fill_slots"]]
    write_json(root, "component-master-manifest.json", masters)
    scene = read(root, "scene-graph.json")
    second_scene = copy.deepcopy(scene["slides"][0])
    second_scene["slide_id"] = "S02"
    second_scene["elements"][0]["instance_id"] = "I02"
    scene["slides"].append(second_scene)
    write_json(root, "scene-graph.json", scene)
    decomposition = read(root, "decomposition-map.json")
    second_map = copy.deepcopy(decomposition["slides"][0])
    second_map.update(slide_id="S02", concept_path=second["concept_path"], master_path=master["component_master_path"])
    for item in second_map["items"]:
        if item.get("instance_id") == "I01":
            item["instance_id"] = "I02"
    decomposition["slides"].append(second_map)
    write_json(root, "decomposition-map.json", decomposition)
    state = read(root, "run-state.json")
    state["stage"] = "inventory"
    state["gates"]["decomposition"]["status"] = "pending"
    state["gates"]["release"]["status"] = "pending"
    g4 = state["gates"]["concept_contact_sheet"]
    g4["approved_artifacts"][second["concept_path"]] = digest(root / second["concept_path"])
    for gate_name in ("brief_authority", "story", "style_anchors", "concept_contact_sheet"):
        gate = state["gates"][gate_name]
        for name in gate["approved_artifacts"]:
            gate["approved_artifacts"][name] = digest(root / name)
        if gate_name != "brief_authority":
            for key, value in gate_decision_values(root, gate_name).items():
                gate["approval_packet"]["decisions"][key].update(value=value, value_sha256=value_sha256(value))
        if gate_name == "style_anchors":
            for name in gate["calibration_selection"]["approved_artifacts"]:
                gate["calibration_selection"]["approved_artifacts"][name] = digest(root / name)
    write_json(root, "run-state.json", state)
    for slide, master, mapped, placed in zip(deck["slides"], masters["slides"], decomposition["slides"], scene["slides"]):
        mapped = {key: value for key, value in mapped.items() if key not in {"review_image", "review_packet", "coverage_review"}}
        fragment = {"schema_version": 1, "slide_id": slide["id"],
                    "bindings": inventory.shard_bindings(root, slide, read(root, "style-contract.json"), state),
                    "master": master, "decomposition": mapped, "scene": placed}
        path = root / f"page-shards/batch-v1/{slide['id']}/inventory.fragment.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fragment), encoding="utf-8")


def canonical_bytes(root):
    return {name: (root / name).read_bytes() for name in inventory.TARGETS}


def test_two_page_merge_preserves_local_ids_reuse_and_pending_human_review(tmp_path):
    inventory_fixture(tmp_path)
    assert inventory.merge(tmp_path, "batch-v1") == 2
    for name in inventory.TARGETS:
        assert [row["slide_id"] for row in read(tmp_path, name)["slides"]] == ["S01", "S02"]
    rows = read(tmp_path, "decomposition-map.json")["slides"]
    assert rows[0]["items"][0]["id"] == rows[1]["items"][0]["id"]
    assert rows[0]["items"][0]["component_id"] == rows[1]["items"][0]["component_id"]
    assert all("coverage_review" not in row for row in rows)
    assert any("review evidence" in e or "coverage reviewer" in e for e in ProjectValidator(tmp_path, "inventory").run())
    assert read(tmp_path, "run-state.json")["gates"]["decomposition"]["status"] == "pending"
    assert inventory.merge(tmp_path, "batch-v1") == 2


@pytest.mark.parametrize("case", ["missing", "duplicate", "stale", "instance", "reuse", "coverage", "approved"])
def test_invalid_shards_never_change_canonical_files(tmp_path, case):
    inventory_fixture(tmp_path)
    path = tmp_path / "page-shards/batch-v1/S02/inventory.fragment.json"
    fragment = json.loads(path.read_text(encoding="utf-8"))
    if case == "missing":
        path.unlink()
    elif case == "duplicate":
        duplicate = path.parent / "nested/inventory.fragment.json"
        duplicate.parent.mkdir()
        duplicate.write_bytes(path.read_bytes())
    elif case == "approved":
        state = read(tmp_path, "run-state.json")
        state["gates"]["decomposition"]["status"] = "approved"
        write_json(tmp_path, "run-state.json", state)
    else:
        if case == "stale":
            fragment["bindings"]["deck_slide_sha256"] = "0" * 64
        elif case == "instance":
            fragment["scene"]["elements"][0]["instance_id"] = "I01"
            fragment["decomposition"]["items"][0]["instance_id"] = "I01"
        elif case == "reuse":
            fragment["scene"]["elements"][0]["component_id"] = "C-unknown"
        else:
            fragment["decomposition"]["coverage_review"] = {"reviewer": "pretend-human"}
        path.write_text(json.dumps(fragment), encoding="utf-8")
    original = canonical_bytes(tmp_path)
    with pytest.raises(ValueError):
        inventory.merge(tmp_path, "batch-v1")
    assert canonical_bytes(tmp_path) == original
    assert not (tmp_path / ".inventory-merge").exists()


def test_manifest_change_after_last_binding_is_rejected(tmp_path, monkeypatch):
    inventory_fixture(tmp_path)
    original = canonical_bytes(tmp_path)
    real_bindings = inventory.shard_bindings
    def change_after_binding(root, slide, style, state):
        result = real_bindings(root, slide, style, state)
        if slide["id"] == "S02":
            manifest = read(root, "asset-manifest.json")
            manifest["race_probe"] = "changed after shard binding"
            write_json(root, "asset-manifest.json", manifest)
        return result
    monkeypatch.setattr(inventory, "shard_bindings", change_after_binding)
    with pytest.raises(ValueError, match="bound input changed"):
        inventory.merge(tmp_path, "batch-v1")
    assert canonical_bytes(tmp_path) == original
    assert not (tmp_path / ".inventory-merge").exists()


def test_interrupted_write_rolls_back_and_same_batch_can_retry(tmp_path, monkeypatch):
    inventory_fixture(tmp_path)
    original = canonical_bytes(tmp_path)
    real_replace = inventory.os.replace
    calls = 0
    def fail_second(src, dest):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected inventory interruption")
        return real_replace(src, dest)
    with monkeypatch.context() as context:
        context.setattr(inventory.os, "replace", fail_second)
        with pytest.raises(OSError, match="injected"):
            inventory.merge(tmp_path, "batch-v1")
    assert canonical_bytes(tmp_path) == original
    assert not (tmp_path / ".inventory-merge").exists()
    assert inventory.merge(tmp_path, "batch-v1") == 2


def test_failed_rollback_keeps_guard_until_explicit_recovery(tmp_path, monkeypatch):
    inventory_fixture(tmp_path)
    original = canonical_bytes(tmp_path)
    real_replace = inventory.os.replace
    calls = 0
    def fail_write_and_restore(src, dest):
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise OSError("injected stopped transaction")
        return real_replace(src, dest)
    with monkeypatch.context() as context:
        context.setattr(inventory.os, "replace", fail_write_and_restore)
        with pytest.raises(OSError):
            inventory.merge(tmp_path, "batch-v1")
    assert (tmp_path / ".inventory-merge").exists()
    assert any("interrupted" in e for e in ProjectValidator(tmp_path, "inventory").run())
    inventory.recover(tmp_path)
    assert canonical_bytes(tmp_path) == original
    assert inventory.merge(tmp_path, "batch-v1") == 2


def test_hard_process_exit_keeps_a_complete_recovery_journal(tmp_path):
    inventory_fixture(tmp_path)
    original = canonical_bytes(tmp_path)
    script = "\n".join([
        "import os, sys", f"sys.path.insert(0, {str(Path(inventory.__file__).parent)!r})",
        "import merge_page_inventory as m", "from pathlib import Path", "original = m.os.replace",
        "def stop(src, dest):", "    original(src, dest)", "    os._exit(77)",
        "m.os.replace = stop", f"m.merge(Path({str(tmp_path)!r}), 'batch-v1')",
    ])
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=30)
    assert result.returncode == 77, result.stderr
    assert (tmp_path / ".inventory-merge/journal.json").is_file()
    assert any("interrupted" in e for e in ProjectValidator(tmp_path, "concept").run())
    inventory.recover(tmp_path)
    assert canonical_bytes(tmp_path) == original
    assert inventory.merge(tmp_path, "batch-v1") == 2


def test_shard_change_during_preflight_is_rejected(tmp_path, monkeypatch):
    inventory_fixture(tmp_path)
    original = canonical_bytes(tmp_path)
    real_validate = inventory.ProjectValidator.validate_inventory_candidate
    path = tmp_path / "page-shards/batch-v1/S01/inventory.fragment.json"
    def change_after_read(self, documents):
        errors = real_validate(self, documents)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["scene"]["elements"][0]["bbox"][0] += 0.01
        path.write_text(json.dumps(payload), encoding="utf-8")
        return errors
    monkeypatch.setattr(inventory.ProjectValidator, "validate_inventory_candidate", change_after_read)
    with pytest.raises(ValueError, match="input changed"):
        inventory.merge(tmp_path, "batch-v1")
    assert canonical_bytes(tmp_path) == original
