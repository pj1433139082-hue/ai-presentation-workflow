"""Reconcile current page shards into canonical inventory drafts; never approve them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from project_snapshot import assert_current, document_snapshot, publish_new_directory
from validate_project import ProjectValidator, value_sha256

TARGETS = ("component-master-manifest.json", "decomposition-map.json", "scene-graph.json")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON must be an object: {path.name}")
    return value


def sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def shard_bindings(root: Path, slide: dict, style: dict, state: dict) -> dict:
    concept = (root / slide["concept_path"]).resolve()
    if not concept.is_relative_to(root) or not concept.is_file():
        raise ValueError("shard concept must be a current project file")
    return {
        "concept_path": slide["concept_path"], "concept_sha256": sha(concept),
        "deck_slide_sha256": value_sha256(slide), "fill_slots_sha256": value_sha256(slide.get("fill_slots", [])),
        "style_version": style.get("version"), "style_sha256": sha(root / "style-contract.json"),
        "g4_artifact_version": state.get("artifact_versions", {}).get("concept_contact_sheet"),
        "asset_manifest_sha256": sha(root / "asset-manifest.json"),
    }


def transaction_dir(root: Path) -> Path:
    path = root / ".inventory-merge"
    if path.is_symlink() or path.resolve() != path or not path.is_relative_to(root):
        raise ValueError("unsafe inventory transaction path")
    return path


def recover(root: Path) -> None:
    root = root.resolve()
    work = transaction_dir(root)
    journal = read(work / "journal.json")
    before, after = journal.get("before"), journal.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict) or set(before) != set(TARGETS) or set(after) != set(TARGETS):
        raise ValueError("invalid inventory recovery journal; preserve it for inspection")
    allowed = {Path("journal.json"), Path("before"), Path("after")}
    allowed.update(Path(area) / name for area in ("before", "after") for name in TARGETS)
    allowed.update(Path(f"restore-{name}") for name in TARGETS)
    if any(path.is_symlink() or path.relative_to(work) not in allowed for path in work.rglob("*")):
        raise ValueError("unexpected recovery files; preserve the transaction")
    for name in TARGETS:
        if before[name] is not None and sha(work / "before" / name) != before[name] or sha(work / "after" / name) != after[name]:
            raise ValueError("inventory recovery backup hash mismatch")
        target = root / name
        if target.is_symlink() or sha(target) not in {before[name], after[name]}:
            raise ValueError("inventory recovery would overwrite an unrelated change")
    for name in TARGETS:
        target = root / name
        if before[name] is None:
            if target.exists():
                target.unlink()
        else:
            restore = work / f"restore-{name}"
            restore.write_bytes((work / "before" / name).read_bytes())
            os.replace(restore, target)
    if any(sha(root / name) != before[name] for name in TARGETS):
        raise ValueError("inventory recovery is incomplete")
    shutil.rmtree(work)  # fixed, resolved, project-owned transaction only


def merge(root: Path, batch: str, version: str | None = None) -> int:
    root = root.resolve()
    version = version or batch
    if not SAFE_ID.fullmatch(batch) or not SAFE_ID.fullmatch(version):
        raise ValueError("batch and version must be safe short identifiers")
    work = transaction_dir(root)
    if work.exists():
        raise ValueError("inventory merge is interrupted or active; use --recover after its writer has stopped")
    state, deck, style = (read(root / name) for name in ("run-state.json", "deck-spec.json", "style-contract.json"))
    if state.get("gates", {}).get("decomposition", {}).get("status") == "approved":
        raise ValueError("approved decomposition is immutable; create an explicit inventory revision first")
    if state.get("gates", {}).get("concept_contact_sheet", {}).get("status") != "approved":
        raise ValueError("current full-deck G4 approval is required")
    slides = deck.get("slides")
    if not isinstance(slides, list) or not slides or any(not isinstance(slide, dict) for slide in slides):
        raise ValueError("deck must contain slide records")
    ids = [slide.get("id") for slide in slides]
    if len(set(ids)) != len(ids) or any(not isinstance(sid, str) or not re.fullmatch(r"S\d+", sid) for sid in ids):
        raise ValueError("deck slide IDs are invalid or duplicated")
    shard_root = (root / "page-shards" / batch).resolve()
    if not shard_root.is_relative_to(root) or not shard_root.is_dir():
        raise ValueError("batch must be an existing project-local shard directory")
    expected = {shard_root / sid / "inventory.fragment.json" for sid in ids}
    actual = set(shard_root.rglob("inventory.fragment.json"))
    if actual != expected:
        raise ValueError("inventory shards must cover every deck slide exactly once")
    documents = {
        TARGETS[0]: {"status": "generated", "version": version, "slides": []},
        TARGETS[1]: {"version": version, "slides": []},
        TARGETS[2]: {"version": version, "slides": []},
    }
    shard_hashes = {}
    bound_files = {}
    for slide in slides:
        path = shard_root / slide["id"] / "inventory.fragment.json"
        if path.is_symlink() or not path.resolve().is_relative_to(shard_root):
            raise ValueError("inventory shard path is unsafe")
        raw = path.read_bytes()
        fragment = json.loads(raw)
        if not isinstance(fragment, dict):
            raise ValueError("inventory fragment must be an object")
        shard_hashes[path] = hashlib.sha256(raw).hexdigest()
        if set(fragment) != {"schema_version", "slide_id", "bindings", "master", "decomposition", "scene"} or type(fragment.get("schema_version")) is not int or fragment["schema_version"] != 1 or fragment.get("slide_id") != slide["id"]:
            raise ValueError("inventory shard schema or slide owner is invalid")
        if fragment.get("bindings") != shard_bindings(root, slide, style, state):
            raise ValueError("inventory shard input binding is stale")
        bindings = fragment["bindings"]
        for relative, digest in ((slide["concept_path"], bindings["concept_sha256"]),
                                 ("style-contract.json", bindings["style_sha256"]),
                                 ("asset-manifest.json", bindings["asset_manifest_sha256"])):
            source = (root / relative).resolve()
            if source in bound_files and bound_files[source] != digest:
                raise ValueError("inventory shards bind different versions of a shared input")
            bound_files[source] = digest
        for name, field in zip(TARGETS, ("master", "decomposition", "scene")):
            row = fragment.get(field)
            if not isinstance(row, dict) or row.get("slide_id") != slide["id"]:
                raise ValueError("inventory records must belong to the shard slide")
            if field == "decomposition" and any(key in row for key in ("review_image", "review_packet", "coverage_review")):
                raise ValueError("worker shard must not claim canonical review evidence or human coverage")
            documents[name]["slides"].append(row)
    validator = ProjectValidator(root, "inventory")
    errors = validator.validate_inventory_candidate(documents)
    if errors:
        raise ValueError("inventory draft preflight failed: " + "; ".join(errors[:5]))
    if any(validator.docs[name] != value for name, value in (("run-state.json", state), ("deck-spec.json", deck), ("style-contract.json", style))):
        raise ValueError("shard inputs changed during preflight")
    snapshot = document_snapshot(root, validator.docs, virtual_documents=set(TARGETS))
    if any(snapshot.get(path) != digest for path, digest in bound_files.items()):
        raise ValueError("inventory shard bound input changed during preflight")
    snapshot.update(shard_hashes)
    payloads = {name: (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8") for name, value in documents.items()}
    history = root / "reviews" / "inventory-merges" / version
    if not history.resolve().is_relative_to(root) or history.is_symlink():
        raise ValueError("unsafe inventory history path")
    if history.exists():
        if all((root / name).is_file() and (root / name).read_bytes() == payloads[name] for name in TARGETS):
            return len(ids)
        raise ValueError("inventory version already committed; retain its review/history and choose a new version")
    for name in TARGETS:
        target = root / name
        if target.is_symlink() or target.resolve().parent != root:
            raise ValueError("unsafe canonical inventory path")
    assert_current(snapshot)
    preparing = Path(tempfile.mkdtemp(prefix=".inventory-merge-preparing-", dir=root)).resolve()
    try:
        (preparing / "before").mkdir()
        (preparing / "after").mkdir()
        before = {}
        for name in TARGETS:
            previous = (root / name).read_bytes() if (root / name).is_file() else None
            before[name] = hashlib.sha256(previous).hexdigest() if previous is not None else None
            if previous is not None:
                (preparing / "before" / name).write_bytes(previous)
            (preparing / "after" / name).write_bytes(payloads[name])
        journal = {"version": version, "before": before,
                   "after": {name: hashlib.sha256(payloads[name]).hexdigest() for name in TARGETS}}
        (preparing / "journal.json").write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")
        assert_current(snapshot)
        if any(sha(root / name) != before[name] for name in TARGETS):
            raise ValueError("canonical inventory changed while preparing its transaction")
        # The public guard appears atomically with a complete recovery journal.
        publish_new_directory(preparing, work)
        for name in TARGETS:
            replacement = work / f"restore-{name}"
            replacement.write_bytes(payloads[name])
            os.replace(replacement, root / name)
        if any(sha(root / name) != journal["after"][name] for name in TARGETS):
            raise ValueError("inventory canonical write verification failed")
        assert_current(snapshot)
        history.parent.mkdir(parents=True, exist_ok=True)
        publish_new_directory(work, history)
    except BaseException:
        if not preparing.exists() and (work / "journal.json").is_file():
            recover(root)
        elif preparing.exists() and not preparing.is_symlink() and preparing.parent == root and preparing.name.startswith(".inventory-merge-preparing-"):
            shutil.rmtree(preparing)
        raise
    return len(ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--batch")
    parser.add_argument("--version")
    parser.add_argument("--recover", action="store_true", help="Restore a stopped writer's interrupted transaction before retrying")
    args = parser.parse_args()
    try:
        if args.recover:
            recover(args.project)
        if args.batch:
            count = merge(args.project, args.batch, args.version)
            print(f"Merged {count} current inventory drafts. Render numbered reviews serially; human coverage and decomposition approval remain pending.")
        elif not args.recover:
            parser.error("--batch or --recover is required")
        else:
            print("Inventory transaction restored; rerun the same batch.")
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")


if __name__ == "__main__":
    main()
