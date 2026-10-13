import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from agent_qa import DECK_CHECKS, PAGE_CHECKS
from assemble_editable_pptx import assemble
from deck_qa_evidence import contact_sheet
from export_final_package import export, main, qualify
from prepare_deck_qa import prepare
from review_policy import LOCAL_REVIEW_MODE
from test_deck_qa import two_page_fixture
from test_validate_project import ProjectValidator, write_json


def read(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_deck(root):
    """Actual assembly contracts; concept copies are explicitly fixture render pixels."""
    two_page_fixture(root)
    assemble(root, "agent-fixture", render=False)
    assembly = read(root, "assembly-map.json")
    assembly["renders"] = []
    for index, slide in enumerate(read(root, "deck-spec.json")["slides"], 1):
        path = root / f"reviews/assembly/agent-fixture/slide-{index:02d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(root / slide["concept_path"]) as image:
            image.save(path)
        assembly["renders"].append({"path": path.relative_to(root).as_posix(), "sha256": digest(path), "pptx_sha256": assembly["sha256"]})
    write_json(root, "assembly-map.json", assembly)
    prepare(root, "agent-fixture")
    prepared = read(root, "qa-report.json")
    state = read(root, "run-state.json")
    state["local_review_policy"] = {"mode": "continuous-local", "authorized_by": "user"}
    write_json(root, "run-state.json", state)
    identity = {"reviewer": "fixture-agent", "reviewed_at": "2026-10-01T12:00:00+08:00", "findings": []}
    report = {
        "schema_version": 1, "review_mode": LOCAL_REVIEW_MODE, "review_state": "complete", "outcome": "pass",
        "qa_version": prepared["version"], "pptx_sha256": assembly["sha256"],
        "contact_sheet": {"path": prepared["final_contact_sheet"], "sha256": prepared["contact_sheet_sha256"]},
        "slides": [{"slide_id": row["slide_id"], **copy.deepcopy(identity), "checks_performed": sorted(PAGE_CHECKS),
                    "bindings": row["bindings"], "evidence": row["evidence"]} for row in prepared["slides"]],
        "whole_deck_review": {**copy.deepcopy(identity), "checks_performed": sorted(DECK_CHECKS),
                              "contact_sheet_sha256": prepared["contact_sheet_sha256"], "bindings": prepared["deck_bindings"]},
    }
    write_json(root, "agent-qa-report.json", report)
    return report


def finding(report, severity="P1"):
    return {"slide_id": "S01", "severity": severity, "description": "Fixture readability finding",
            "owner_stage": "assembly", "repair_entry": "enlarge F01", "repair_attempts": 1,
            "evidence": report["slides"][0]["evidence"]["overlay"]}


def test_complete_p1_local_draft_exports_without_passing_human_qa(tmp_path, monkeypatch, capsys):
    report = local_deck(tmp_path)
    before = (tmp_path / "qa-report.json").read_bytes()
    report["slides"][0]["findings"] = [finding(report)]
    report["outcome"] = "issues"
    write_json(tmp_path, "agent-qa-report.json", report)
    output = tmp_path / "交付包"
    monkeypatch.setattr(sys, "argv", ["export_final_package.py", str(tmp_path), "--output", str(output), "--pptx-name", "draft.pptx"])
    main()
    message = capsys.readouterr().out
    assert "outcome=issues" in message and "formal human QA and G5 release pending" in message
    assert str((tmp_path / "agent-qa-report.json").resolve()) in message
    assert export(tmp_path, output, "draft.pptx", verify_only=True)[:2] == (2, 4)
    assert (tmp_path / "qa-report.json").read_bytes() == before
    assert ProjectValidator(tmp_path, "qa").run()
    assert read(tmp_path, "run-state.json")["gates"]["release"]["status"] == "pending"
    deck = read(tmp_path, "deck-spec.json")
    deck["slides"][0]["title"] = "Changed after assembly"
    write_json(tmp_path, "deck-spec.json", deck)
    with pytest.raises(ValueError, match="preflight"):
        export(tmp_path, output, "draft.pptx", verify_only=True)


@pytest.mark.parametrize("case", ["P0", "missing_page", "duplicate_page", "missing_check", "reviewer", "time", "binding", "false_outcome", "missing_opt_in", "missing_report", "release", "garbage_qa", "unprepared_qa"])
def test_incomplete_stale_or_unauthorized_review_blocks_export(tmp_path, case):
    report = local_deck(tmp_path)
    if case == "P0":
        report["slides"][0]["findings"] = [finding(report, "P0")]
        report["outcome"] = "issues"
    elif case == "missing_page":
        report["slides"].pop()
    elif case == "duplicate_page":
        report["slides"][1] = copy.deepcopy(report["slides"][0])
    elif case == "missing_check":
        report["slides"][0]["checks_performed"].pop()
    elif case == "reviewer":
        report["whole_deck_review"]["reviewer"] = ""
    elif case == "time":
        report["slides"][0]["reviewed_at"] = "2026-10-01T12:00:00"
    elif case == "binding":
        report["slides"][0]["bindings"]["render_sha256"] = "0" * 64
    elif case == "false_outcome":
        report["slides"][0]["findings"] = [finding(report)]
    elif case in {"garbage_qa", "unprepared_qa"}:
        prepared = read(tmp_path, "qa-report.json")
        prepared["status"] = "garbage" if case == "garbage_qa" else "pending"
        write_json(tmp_path, "qa-report.json", prepared)
    elif case in {"missing_opt_in", "release"}:
        state = read(tmp_path, "run-state.json")
        if case == "missing_opt_in":
            state.pop("local_review_policy")
        else:
            state["gates"]["release"]["status"] = "approved"
        write_json(tmp_path, "run-state.json", state)
    write_json(tmp_path, "agent-qa-report.json", report)
    if case == "missing_report":
        (tmp_path / "agent-qa-report.json").unlink()
    with pytest.raises(ValueError):
        export(tmp_path, tmp_path / "交付包", "draft.pptx")
    assert not (tmp_path / "交付包").exists()


def test_forged_contact_sheet_fails_even_with_refreshed_hashes(tmp_path):
    report = local_deck(tmp_path)
    assembly = read(tmp_path, "assembly-map.json")
    images = [(sid, Image.open(tmp_path / row["path"])) for sid, row in zip(("S01", "S02"), assembly["renders"])]
    path = tmp_path / report["contact_sheet"]["path"]
    contact_sheet(list(reversed(images))).save(path)
    for _, image in images:
        image.close()
    new_hash = digest(path)
    report["contact_sheet"]["sha256"] = new_hash
    report["whole_deck_review"]["contact_sheet_sha256"] = new_hash
    report["whole_deck_review"]["bindings"]["contact_sheet_sha256"] = new_hash
    prepared = read(tmp_path, "qa-report.json")
    prepared["contact_sheet_sha256"] = new_hash
    prepared["deck_bindings"]["contact_sheet_sha256"] = new_hash
    write_json(tmp_path, "qa-report.json", prepared)
    write_json(tmp_path, "agent-qa-report.json", report)
    with pytest.raises(ValueError, match="contact sheet pixels"):
        qualify(tmp_path)


def test_copy_failure_retry_and_competing_output_are_safe(tmp_path, monkeypatch):
    local_deck(tmp_path)
    import export_final_package as delivery
    real_copy = delivery.shutil.copy2
    calls = 0
    def fail_second(src, dest):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected copy interruption")
        return real_copy(src, dest)
    output = tmp_path / "交付包"
    with monkeypatch.context() as context:
        context.setattr(delivery.shutil, "copy2", fail_second)
        with pytest.raises(OSError, match="injected"):
            export(tmp_path, output, "draft.pptx")
    assert not output.exists()
    assert not list(tmp_path.glob(".交付包-staging-*"))
    export(tmp_path, output, "draft.pptx")
    original = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="already exists"):
        export(tmp_path, output, "draft.pptx")
    assert original == {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    competing = tmp_path / "competing"
    real_verify = delivery.verify_files
    def create_competing(*args):
        real_verify(*args)
        competing.mkdir()
        (competing / "keep.txt").write_text("existing", encoding="utf-8")
    with monkeypatch.context() as context:
        context.setattr(delivery, "verify_files", create_competing)
        with pytest.raises(ValueError, match="competing"):
            export(tmp_path, competing, "draft.pptx")
    assert (competing / "keep.txt").read_text(encoding="utf-8") == "existing"


def test_source_change_while_copying_refuses_promotion(tmp_path, monkeypatch):
    local_deck(tmp_path)
    import export_final_package as delivery
    real_copy = delivery.shutil.copy2
    changed = False
    def change_validated_inputs(src, dest):
        nonlocal changed
        result = real_copy(src, dest)
        if not changed:
            changed = True
            style = read(tmp_path, "style-contract.json")
            style["version"] = "changed-during-copy"
            write_json(tmp_path, "style-contract.json", style)
        return result
    monkeypatch.setattr(delivery.shutil, "copy2", change_validated_inputs)
    output = tmp_path / "交付包"
    with pytest.raises(ValueError, match="input changed"):
        export(tmp_path, output, "draft.pptx")
    assert not output.exists()
    assert not list(tmp_path.glob(".交付包-staging-*"))
