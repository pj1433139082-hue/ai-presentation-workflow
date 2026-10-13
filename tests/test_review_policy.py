import copy
import json
from pathlib import Path

import pytest

from test_validate_project import VALIDATOR_MODULE, ProjectValidator, make_valid_project, promote_fixture_to_production, write_json


def test_historical_local_actor_mode_keeps_authorization_and_human_boundaries():
    review_actor_error = VALIDATOR_MODULE.REVIEW_POLICY.review_actor_error
    state = {"local_review_policy": {"mode": "continuous-local", "authorized_by": "user"}}
    review = {"review_mode": "user-authorized-continuous-local", "reviewed_at": "2026-09-28T13:19:32+08:00"}
    assert review_actor_error(state, review) is None
    assert review_actor_error({}, review)
    assert review_actor_error(state, review, human_only=True)
    assert review_actor_error(state, {**review, "actor": "human"})
    assert review_actor_error(state, {**review, "reviewed_at": "2026-09-28T13:19:32"})
    assert review_actor_error(state, {**review, "review_mode": []})


def state_for(root):
    return json.loads((root / "run-state.json").read_text(encoding="utf-8"))


def test_local_affirmative_is_scoped_and_strict_default_is_preserved(tmp_path):
    make_valid_project(tmp_path)
    state = state_for(tmp_path)
    state["gates"]["story"].update(approval_mode="local-affirmative", approval_phrase="同意")
    write_json(tmp_path, "run-state.json", state)
    assert any("user-authorized" in e for e in ProjectValidator(tmp_path, "assets").run())
    state["local_review_policy"] = {"mode": "continuous-local", "authorized_by": "user"}
    write_json(tmp_path, "run-state.json", state)
    assert ProjectValidator(tmp_path, "assets").run() == []
    for mutate, expected in (
        (lambda s: s["local_review_policy"].update(authorized_by="agent"), "user-authorized"),
        (lambda s: s["gates"]["story"].update(approval_phrase="继续"), "continuation"),
        (lambda s: s["gates"]["story"].update(approval_phrase="好的，但把第二页改红"), "correction"),
        (lambda s: s["gates"]["story"].update(approval_phrase="两个都行吧"), "ambiguous"),
        (lambda s: s["gates"]["story"]["approval_packet"].update(gate="concept_contact_sheet"), "gate"),
        (lambda s: s["gates"]["story"].update(artifact_version="old"), "version"),
        (lambda s: s["gates"]["story"]["approved_artifacts"].update({"storyboard.json": "0" * 64}), "stale"),
    ):
        altered = copy.deepcopy(state)
        mutate(altered)
        write_json(tmp_path, "run-state.json", altered)
        errors = ProjectValidator(tmp_path, "assets").run()
        assert errors and any(expected.lower() in e.lower() for e in errors), errors


def test_local_policy_does_not_authorize_release(tmp_path):
    make_valid_project(tmp_path)
    state = state_for(tmp_path)
    state["local_review_policy"] = {"mode": "continuous-local", "authorized_by": "user"}
    state["gates"]["release"].update(approval_mode="explicit", approval_phrase="同意")
    write_json(tmp_path, "run-state.json", state)
    assert any("确认发布" in e for e in ProjectValidator(tmp_path, "release").run())


def test_local_g1_requires_the_full_current_packet_and_handles_malformed_scope(tmp_path):
    make_valid_project(tmp_path)
    state = state_for(tmp_path)
    state["local_review_policy"] = {"mode": "continuous-local", "authorized_by": "user"}
    state["gates"]["brief_authority"].update(approval_mode="local-affirmative", approval_phrase="同意")
    write_json(tmp_path, "run-state.json", state)
    assert ProjectValidator(tmp_path, "assets").run() == []
    alignment = json.loads((tmp_path / "alignment.json").read_text(encoding="utf-8"))
    for ids in (None, ["audience"], [{"id": "audience"}]):
        altered = copy.deepcopy(alignment)
        altered["approval_packet"]["decision_ids"] = ids
        write_json(tmp_path, "alignment.json", altered)
        errors = ProjectValidator(tmp_path, "assets").run()
        assert any("full current brief_authority" in e for e in errors), errors


def test_local_calibration_keeps_current_candidate_binding(tmp_path):
    make_valid_project(tmp_path)
    promote_fixture_to_production(tmp_path)
    state = state_for(tmp_path)
    state["local_review_policy"] = {"mode": "continuous-local", "authorized_by": "user"}
    selection = state["gates"]["style_anchors"]["calibration_selection"]
    selection.update(approval_mode="local-affirmative", approval_phrase="好的")
    write_json(tmp_path, "run-state.json", state)
    assert ProjectValidator(tmp_path, "inventory").run() == []
    selection["selected_variant_id"] = "missing"
    write_json(tmp_path, "run-state.json", state)
    assert any("selected_variant_id" in e for e in ProjectValidator(tmp_path, "inventory").run())


def test_local_agent_geometry_and_isolation_preserve_human_coverage(tmp_path):
    make_valid_project(tmp_path)
    promote_fixture_to_production(tmp_path)
    state = state_for(tmp_path)
    masters = json.loads((tmp_path / "component-master-manifest.json").read_text(encoding="utf-8"))
    geometry = masters["slides"][0]["geometry_review"]
    geometry.update(actor="agent", review_mode="agent-QA-user-authorized-continuous-local", reviewed_at="2026-10-01T12:00:00+08:00")
    write_json(tmp_path, "component-master-manifest.json", masters)
    assert any("review must declare" in e for e in ProjectValidator(tmp_path, "inventory").run())
    state["local_review_policy"] = {"mode": "continuous-local", "authorized_by": "user"}
    write_json(tmp_path, "run-state.json", state)
    assert ProjectValidator(tmp_path, "inventory").run() == []
    manifest = json.loads((tmp_path / "asset-manifest.json").read_text(encoding="utf-8"))
    manifest["assets"][0]["isolation_review"].update(actor="agent", review_mode="agent-QA-user-authorized-continuous-local", reviewed_at="2026-10-01T12:00:00+08:00")
    write_json(tmp_path, "asset-manifest.json", manifest)
    validator = ProjectValidator(tmp_path, "assets")
    validator.load_required_documents()
    validator.validate_asset_isolation(manifest["assets"][0], "asset", tmp_path / manifest["assets"][0]["output"])
    assert validator.errors == []
    state.pop("local_review_policy")
    write_json(tmp_path, "run-state.json", state)
    validator = ProjectValidator(tmp_path, "assets")
    validator.load_required_documents()
    validator.validate_asset_isolation(manifest["assets"][0], "asset", tmp_path / manifest["assets"][0]["output"])
    assert any("review must declare" in e for e in validator.errors)
    state["local_review_policy"] = {"mode": "continuous-local", "authorized_by": "user"}
    write_json(tmp_path, "run-state.json", state)
    mapped = json.loads((tmp_path / "decomposition-map.json").read_text(encoding="utf-8"))
    mapped["slides"][0]["coverage_review"].update(actor="agent", review_mode="agent-QA-user-authorized-continuous-local")
    write_json(tmp_path, "decomposition-map.json", mapped)
    assert any("review must declare" in e for e in ProjectValidator(tmp_path, "inventory").run())


def test_pilot_requires_honest_actor_and_local_authorization(tmp_path):
    from test_pilot_review import approve, make_pilot
    make_pilot(tmp_path)
    approve(tmp_path)
    review = json.loads((tmp_path / "pilot-review.json").read_text(encoding="utf-8"))
    review["actor"] = "agent"
    write_json(tmp_path, "pilot-review.json", review)
    assert any("review must declare" in e for e in ProjectValidator(tmp_path, "pilot").run())
    state = state_for(tmp_path)
    state["local_review_policy"] = {"mode": "continuous-local", "authorized_by": "user"}
    write_json(tmp_path, "run-state.json", state)
    review.update(status="agent-verified-local", review_mode="agent-QA-user-authorized-continuous-local")
    write_json(tmp_path, "pilot-review.json", review)
    assert ProjectValidator(tmp_path, "pilot").run() == []
    review["bindings"]["concept_sha256"] = "0" * 64
    write_json(tmp_path, "pilot-review.json", review)
    assert any("stale" in e for e in ProjectValidator(tmp_path, "pilot").run())
