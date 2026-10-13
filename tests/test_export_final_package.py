import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_final_package import export


@pytest.fixture(autouse=True)
def copying_contract_only(monkeypatch):
    """These byte fixtures cover copying; test_agent_qa exercises real preflight."""
    def fixture_qualification(project):
        names = ("deck-spec.json", "asset-manifest.json", "scene-graph.json", "assembly-map.json", "run-state.json")
        return SimpleNamespace(root=project, docs={name: json.loads((project / name).read_text(encoding="utf-8")) for name in names})
    monkeypatch.setattr("export_final_package.qualify", fixture_qualification)


def put(project: Path, name: str, content: bytes) -> str:
    path = project / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def fixture_project(project: Path) -> None:
    concepts = {}
    assets = []
    slides = []
    assembly_slides = []
    scene_slides = []
    for sid in ("S01", "S02"):
        concept = f"concepts/{sid}.png"
        component = f"assets/{sid}/C-{sid}.png"
        concepts[sid] = put(project, concept, f"concept-{sid}".encode())
        component_hash = put(project, component, f"component-{sid}".encode())
        slides.append({"id": sid, "concept_path": concept})
        assets.append({"id": f"C-{sid}", "slide_id": sid, "output": component, "sha256": component_hash, "status": "approved"})
        assembly_slides.append({"slide_id": sid})
        scene_slides.append({"slide_id": sid, "elements": [{"component_id": f"C-{sid}"}]})
    pptx_hash = put(project, "assembly/draft.pptx", b"pptx")
    data = {
        "deck-spec.json": {"slides": slides},
        "asset-manifest.json": {"assets": assets},
        "scene-graph.json": {"slides": scene_slides},
        "assembly-map.json": {"output": "assembly/draft.pptx", "sha256": pptx_hash, "slides": assembly_slides},
        "run-state.json": {"gates": {
            "concept_contact_sheet": {"status": "approved", "approval_packet": {"decisions": {
                "full_deck_contact_sheet": {"value": {"contentful_image_sha256": concepts}}
            }}},
            "release": {"status": "pending"},
        }},
    }
    for name, value in data.items():
        (project / name).write_text(json.dumps(value), encoding="utf-8")


def test_export_uses_current_approved_files_and_refuses_overwrite(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    fixture_project(project)
    output = project / "交付包"
    assert export(project, output) == (2, 2, output / "PPT成稿/draft.pptx")
    assert {path.name for path in output.iterdir()} == {"确定概念图", "组件", "PPT成稿"}
    assert {path.name for path in (output / "组件").iterdir()} == {"S01", "S02"}
    assert len(list((output / "确定概念图").glob("*.png"))) == 2
    assert (output / "组件/S01/C-S01.png").read_bytes() == b"component-S01"
    with pytest.raises(ValueError, match="already exists"):
        export(project, output)


def test_export_rejects_changed_approved_concept(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    fixture_project(project)
    (project / "concepts/S02.png").write_bytes(b"changed")
    output = project / "交付包"
    with pytest.raises(ValueError, match="hash mismatch"):
        export(project, output)
    assert not output.exists()


def test_export_places_reused_component_in_each_slide_folder(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    fixture_project(project)
    scene_path = project / "scene-graph.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    scene["slides"][1]["elements"].append({"component_id": "C-S01"})
    scene_path.write_text(json.dumps(scene), encoding="utf-8")
    output = project / "交付包"
    assert export(project, output)[1] == 3
    assert (output / "组件/S02/C-S01.png").read_bytes() == b"component-S01"


def test_verify_rejects_extra_files_and_changed_delivery_bytes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    fixture_project(project)
    output = project / "交付包"
    export(project, output)
    assert export(project, output, verify_only=True)[1] == 2
    extra = output / "组件/S01/unapproved.png"
    extra.write_bytes(b"extra")
    with pytest.raises(ValueError, match="folders or files differ"):
        export(project, output, verify_only=True)
    extra.unlink()
    (output / "组件/S01/C-S01.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Delivery file hash mismatch"):
        export(project, output, verify_only=True)
