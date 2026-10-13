"""Copy the current approved slide artifacts into a three-folder PPTX handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from agent_qa import validate_agent_qa
from project_snapshot import assert_current, document_snapshot, publish_new_directory
from validate_project import ProjectValidator


FOLDERS = ("确定概念图", "组件", "PPT成稿")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def source_file(project: Path, relative: str, expected_hash: str) -> Path:
    path = (project / relative).resolve()
    if not path.is_relative_to(project) or not path.is_file():
        raise ValueError(f"Missing or unsafe source path: {relative}")
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError(f"Source hash mismatch: {relative}")
    return path


def qualify(project: Path) -> ProjectValidator:
    state = read_json(project / "run-state.json")
    qa_path = project / "qa-report.json"
    qa = read_json(qa_path) if qa_path.is_file() else {}
    released = state.get("gates", {}).get("release", {}).get("status") == "approved"
    stage = "release" if released else "qa" if qa.get("status") == "passed" else "assembly"
    validator = ProjectValidator(project, stage)
    errors = validator.run()
    if errors:
        raise ValueError("delivery preflight failed: " + "; ".join(errors[:5]))
    current_release = validator.docs["run-state.json"].get("gates", {}).get("release", {}).get("status") == "approved"
    if current_release != released:
        raise ValueError("delivery authority changed during preflight; retry against current inputs")
    if stage == "assembly":
        try:
            validate_agent_qa(validator)
        except OSError as exc:
            raise ValueError("local draft requires current prepared QA and agent-qa-report.json") from exc
    return validator


def qualification_snapshot(validator: ProjectValidator) -> dict[Path, str]:
    return document_snapshot(validator.root, validator.docs)


def verify_files(output: Path, copies: list[tuple[Path, Path]], expected_dirs: set[Path]) -> None:
    actual_paths = list(output.rglob("*"))
    if any(path.is_symlink() for path in actual_paths):
        raise ValueError("Delivery package contains a symlink")
    actual_dirs = {path.relative_to(output) for path in actual_paths if path.is_dir()}
    actual_files = {path.relative_to(output) for path in actual_paths if path.is_file()}
    if actual_dirs != expected_dirs or actual_files != {dest for _, dest in copies}:
        raise ValueError("Delivery package folders or files differ from the current project")
    for src, dest in copies:
        if hashlib.sha256(src.read_bytes()).digest() != hashlib.sha256((output / dest).read_bytes()).digest():
            raise ValueError(f"Delivery file hash mismatch: {dest}")


def export(
    project: Path, output: Path, pptx_name: str | None = None, *, verify_only: bool = False
) -> tuple[int, int, Path]:
    project = project.resolve()
    output = output.resolve()
    if not project.is_dir():
        raise ValueError(f"Project directory does not exist: {project}")
    if verify_only and not output.is_dir():
        raise ValueError(f"Delivery package does not exist: {output}")
    if not verify_only and output.exists():
        raise ValueError(f"Output already exists; choose a new version: {output}")

    kind_path = project / "project-kind.json"
    if kind_path.exists() or kind_path.is_symlink():
        from showcase_contract import export_showcase

        result = export_showcase(project, output, verify_only=verify_only, pptx_name=pptx_name)
        if not result.get("ok"):
            raise ValueError("Showcase export failed: " + "; ".join(result.get("errors", [])))
        return result["concept_count"], result["asset_count"], Path(result["pptx_path"])

    validator = qualify(project)
    snapshot = qualification_snapshot(validator)
    deck = validator.docs["deck-spec.json"]
    manifest = validator.docs["asset-manifest.json"]
    scene = validator.docs["scene-graph.json"]
    assembly = validator.docs["assembly-map.json"]
    state = validator.docs["run-state.json"]
    gate = state.get("gates", {}).get("concept_contact_sheet", {})
    if gate.get("status") != "approved":
        raise ValueError("Current concept gate is not approved")
    concept_hashes = (
        gate.get("approval_packet", {})
        .get("decisions", {})
        .get("full_deck_contact_sheet", {})
        .get("value", {})
        .get("contentful_image_sha256", {})
    )
    slides = deck.get("slides", [])
    if not concept_hashes:
        approved = gate.get("approved_artifacts", {})
        concept_hashes = {slide.get("id"): approved.get(slide.get("concept_path")) for slide in slides}
    if not concept_hashes or any(not digest for digest in concept_hashes.values()):
        raise ValueError("Approved concept hashes are missing")
    ids = [slide.get("id") for slide in slides]
    if not ids or len(set(ids)) != len(ids) or any(not re.fullmatch(r"S\d+", sid or "") for sid in ids):
        raise ValueError("Deck has missing, duplicate, or unsafe slide IDs")
    if set(concept_hashes) != set(ids):
        raise ValueError("Approved concept list differs from the current deck")

    copies: list[tuple[Path, Path]] = []
    for slide in slides:
        sid = slide["id"]
        src = source_file(project, slide["concept_path"], concept_hashes[sid])
        copies.append((src, Path(FOLDERS[0]) / f"{sid}-确定概念图{src.suffix.lower()}"))

    assets = manifest.get("assets", [])
    if not assets:
        raise ValueError("Current asset manifest is empty")
    asset_by_id = {asset["id"]: asset for asset in assets}
    if len(asset_by_id) != len(assets):
        raise ValueError("Current asset manifest has duplicate IDs")
    for asset in assets:
        if asset.get("status") != "approved":
            raise ValueError(f"Component is not approved: {asset.get('id')}")
    scene_slides = scene.get("slides", [])
    if [slide.get("slide_id") for slide in scene_slides] != ids:
        raise ValueError("Scene slides differ from the current deck")
    component_count = 0
    for slide in scene_slides:
        sid = slide["slide_id"]
        used_ids = {item["component_id"] for item in slide.get("elements", []) if item.get("component_id")}
        for component_id in sorted(used_ids):
            if component_id not in asset_by_id:
                raise ValueError(f"Scene uses an unknown component: {component_id}")
            asset = asset_by_id[component_id]
            src = source_file(project, asset["output"], asset["sha256"])
            copies.append((src, Path(FOLDERS[1]) / sid / src.name))
            component_count += 1

    pptx_src = source_file(project, assembly["output"], assembly["sha256"])
    if pptx_src.suffix.lower() != ".pptx":
        raise ValueError("Current assembly output is not a PPTX")
    if [slide.get("slide_id") for slide in assembly.get("slides", [])] != ids:
        raise ValueError("Assembly slides differ from the current deck")
    name = pptx_name or pptx_src.name
    if Path(name).name != name or not name.lower().endswith(".pptx"):
        raise ValueError("PPTX name must be a plain .pptx filename")
    if state.get("gates", {}).get("release", {}).get("status") != "approved" and "草稿" not in name and "draft" not in name.lower():
        raise ValueError("Pending G5 release requires a draft-labeled PPTX filename")
    pptx_dest = Path(FOLDERS[2]) / name
    copies.append((pptx_src, pptx_dest))

    destinations = [dest for _, dest in copies]
    if len(destinations) != len(set(destinations)):
        raise ValueError("Two source files would overwrite the same delivery file")
    expected_dirs = {Path(folder) for folder in FOLDERS}
    expected_dirs.update(Path(FOLDERS[1]) / sid for sid in ids)
    if verify_only:
        verify_files(output, copies, expected_dirs)
        assert_current(snapshot)
        return len(slides), component_count, output / pptx_dest

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-staging-", dir=output.parent)).resolve()
    try:
        for directory in expected_dirs:
            (staging / directory).mkdir(parents=True, exist_ok=True)
        for src, dest in copies:
            shutil.copy2(src, staging / dest)
        verify_files(staging, copies, expected_dirs)
        assert_current(snapshot)
        if output.exists():
            raise ValueError("Output already exists; a competing delivery will not be replaced")
        publish_new_directory(staging, output)
        return len(slides), component_count, output / pptx_dest
    finally:
        if staging.exists():
            if staging.parent != output.parent or not staging.name.startswith(f".{output.name}-staging-") or staging.is_symlink():
                raise ValueError("refusing unsafe staging cleanup")
            shutil.rmtree(staging)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--output", type=Path, help="New package directory; showcase defaults to sibling <project-name>-交付包; production defaults to <project>/交付包")
    parser.add_argument("--pptx-name", help="Destination .pptx filename")
    parser.add_argument("--verify", action="store_true", help="Verify an existing package against current approved sources")
    args = parser.parse_args()
    kind_path = args.project / "project-kind.json"
    showcase = False
    if kind_path.exists() or kind_path.is_symlink():
        try:
            showcase = read_json(kind_path) == {"contract_version": "showcase-v1", "purpose": "showcase"}
        except (OSError, ValueError, TypeError) as exc:
            parser.exit(1, f"FAIL: invalid project-kind.json: {exc}\n")
        if not showcase:
            parser.exit(1, "FAIL: unknown project-kind.json; refusing legacy fallback\n")
    default_output = args.project.resolve().parent / f"{args.project.name}-交付包" if showcase else args.project / "交付包"
    output = args.output or default_output
    mode_path = args.project / "delivery-mode.json"
    if showcase and (mode_path.exists() or mode_path.is_symlink()):
        from delivery_modes import read_delivery_mode
        try:
            mode = read_delivery_mode(args.project.resolve())
        except (OSError, ValueError) as exc:
            parser.exit(1, f"FAIL: {exc}\n")
        if mode != "assembly":
            from apw import export_project
            report = export_project(args.project, output, verify_only=args.verify, pptx_name=args.pptx_name)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            if not report["ok"]:
                raise SystemExit(1)
            return
    pptx_name = args.pptx_name
    if args.verify and pptx_name is None:
        pptx_files = list((output / FOLDERS[2]).glob("*.pptx"))
        if len(pptx_files) != 1:
            parser.error("Verification requires exactly one PPTX or an explicit --pptx-name")
        pptx_name = pptx_files[0].name
    try:
        concepts, assets, pptx = export(args.project, output, pptx_name, verify_only=args.verify)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    verb = "Verified" if args.verify else "Exported and verified"
    print(f"{verb} {concepts} concepts, {assets} components, and PPTX: {pptx}")
    if (args.project / "project-kind.json").exists():
        print("Local showcase draft: technical contract and current agent review checked; formal human gates and user visual acceptance are separate.")
        print(f"Review record: {(args.project / 'showcase-review.json').resolve()}")
        return
    state = read_json(args.project / "run-state.json")
    if state.get("gates", {}).get("release", {}).get("status") == "approved":
        print("Current formal QA and G5 release validated.")
    elif read_json(args.project / "qa-report.json").get("status") == "passed":
        print("Draft: formal QA passed; G5 release pending.")
    else:
        problem_record = (args.project / "agent-qa-report.json").resolve()
        record = read_json(problem_record)
        print(f"Local draft: agent QA outcome={record['outcome']}; formal human QA and G5 release pending.")
        print(f"QA/problem record: {problem_record}")


if __name__ == "__main__":
    main()
