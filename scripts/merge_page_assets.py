"""Merge approved page-local asset fragments into the single canonical manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def merge(root: Path, batch: str) -> int:
    root = root.resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", batch):
        raise ValueError("batch must be a safe short identifier")
    deck_ids = [slide["id"] for slide in read_json(root / "deck-spec.json")["slides"]]
    if not deck_ids or len(set(deck_ids)) != len(deck_ids) or any(not isinstance(sid, str) or not re.fullmatch(r"S\d+", sid) for sid in deck_ids):
        raise ValueError("deck has missing, duplicate, or unsafe slide IDs")
    scene_slides = read_json(root / "scene-graph.json")["slides"]
    if [slide.get("slide_id") for slide in scene_slides] != deck_ids:
        raise ValueError("scene slides differ from deck order")
    used_by_slide = {
        slide["slide_id"]: {element["component_id"] for element in slide.get("elements", []) if element.get("component_id")}
        for slide in scene_slides
    }
    manifest_path = root / "asset-manifest.json"
    manifest = read_json(manifest_path)
    original = manifest_path.read_bytes()
    existing = manifest.get("assets", [])
    if not isinstance(existing, list):
        raise ValueError("asset manifest needs an assets array")
    by_id = {asset.get("id"): asset for asset in existing if isinstance(asset, dict)}
    if len(by_id) != len(existing) or any(not isinstance(aid, str) for aid in by_id):
        raise ValueError("asset manifest has duplicate or invalid records")
    added = 0
    for sid in deck_ids:
        fragment_path = root / "page-shards" / batch / sid / "asset-manifest.fragment.json"
        if not fragment_path.is_file():
            if used_by_slide[sid].issubset(by_id):
                continue  # The already-merged pilot page needs no duplicate fragment.
            raise ValueError(f"missing asset fragment for {sid}")
        fragment = read_json(fragment_path)
        if fragment.get("slide_id") != sid or not isinstance(fragment.get("assets"), list):
            raise ValueError(f"fragment has wrong slide ID or assets array: {sid}")
        seen: set[str] = set()
        for asset in fragment["assets"]:
            if not isinstance(asset, dict) or not isinstance(asset.get("id"), str):
                raise ValueError(f"invalid asset record in {sid}")
            aid = asset["id"]
            if aid in seen or aid not in used_by_slide[sid]:
                raise ValueError(f"duplicate or unused asset in {sid}: {aid}")
            seen.add(aid)
            if sid not in asset.get("slide_ids", [asset.get("slide_id")]):
                raise ValueError(f"asset does not belong to {sid}: {aid}")
            review = asset.get("isolation_review")
            if asset.get("status") != "approved" or not isinstance(review, dict) or review.get("status") != "passed":
                raise ValueError(f"asset lacks passed review: {aid}")
            source = (root / asset["output"]).resolve()
            if not source.is_relative_to(root) or not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != asset.get("sha256"):
                raise ValueError(f"asset source is missing or stale: {aid}")
            prior = by_id.get(aid)
            if prior is not None and prior != asset:
                raise ValueError(f"fragment conflicts with canonical asset: {aid}")
            if prior is None:
                by_id[aid] = asset
                added += 1
    used_ids = set().union(*used_by_slide.values())
    if not used_ids.issubset(by_id):
        raise ValueError(f"scene has unmerged assets: {sorted(used_ids - by_id.keys())}")
    outputs: dict[str, str] = {}
    for aid, asset in by_id.items():
        output = asset.get("output")
        if not isinstance(output, str):
            raise ValueError(f"asset output path is missing: {aid}")
        owner = outputs.setdefault(output, aid)
        if owner != aid:
            raise ValueError(f"two asset IDs share one output path: {owner}, {aid}")
    if not added:
        return 0
    manifest["assets"] = list(by_id.values())
    payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=root, prefix="asset-manifest-merge-", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    try:
        if manifest_path.read_bytes() != original:
            raise ValueError("canonical manifest changed during merge")
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--batch", required=True)
    args = parser.parse_args()
    print(f"Merged {merge(args.project, args.batch)} page assets into the canonical manifest")


if __name__ == "__main__":
    main()
