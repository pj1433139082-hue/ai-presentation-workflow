"""Atomic concept/asset deliveries with no scene, PPTX, or assembly obligation."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

try:
    from delivery_modes import validate_delivery
    from showcase_contract import CONCEPT_INPUT_DOCS, _package_safe_stem, _safe_file
    from project_snapshot import publish_new_directory
    import reconstruction_contract as _reconstruction
except ImportError:
    from .delivery_modes import validate_delivery
    from .showcase_contract import CONCEPT_INPUT_DOCS, _package_safe_stem, _safe_file
    from .project_snapshot import publish_new_directory
    from . import reconstruction_contract as _reconstruction


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sources(root: Path, mode: str) -> tuple[dict[str, str], int, int]:
    """Preserve reusable input paths inside the evidence project as well as art."""
    documents = {name: json.loads((root / name).read_text(encoding="utf-8")) for name in CONCEPT_INPUT_DOCS}
    files: dict[str, str] = {}
    destinations_by_casefold: dict[str, str] = {}

    def add(relative: str, target: str | None = None) -> None:
        errors: list[str] = []
        path = _safe_file(root, relative, errors, "delivery source")
        if path is None:
            raise ValueError("; ".join(errors))
        canonical = path.relative_to(root).as_posix()
        destination = target or f"项目证据/{relative}"
        collision_key = Path(destination).as_posix().casefold()
        previous_destination = destinations_by_casefold.get(collision_key)
        if previous_destination is not None and previous_destination != destination:
            raise ValueError(f"export paths collide on a case-insensitive filesystem: {previous_destination!r} and {destination!r}")
        destinations_by_casefold[collision_key] = destination
        if destination in files and files[destination] != canonical:
            raise ValueError(f"two sources claim the same destination: {destination}")
        files[destination] = canonical

    for name in (*CONCEPT_INPUT_DOCS, "delivery-mode.json"):
        add(name)
    deck = documents["deck-spec.json"]["slides"]
    for index, slide in enumerate(deck, 1):
        path = slide["concept_path"]
        add(path)
        add(path, f"概念图/{index:02d}-{_package_safe_stem(slide['id'])}.png")
    for source in documents["brief.json"].get("source_map", []):
        if source.get("path"):
            add(source["path"])
    selected = documents["style-contract.json"]["selected_reference_ids"]
    for reference in documents["reference-study.json"].get("references", []):
        if reference.get("id") in selected:
            add(reference["image_path"])
    # Original prompts/tool records are preserved, not rewritten as proof of
    # historical input consumption. Only the explicitly local provenance tree.
    provenance = root / "provenance"
    if provenance.is_dir():
        for path in sorted(provenance.rglob("*")):
            if path.is_file():
                add(path.relative_to(root).as_posix())
    assets = []
    if mode == "assets":
        add("asset-manifest.json")
        manifest = json.loads((root / "asset-manifest.json").read_text(encoding="utf-8"))
        assets = manifest.get("assets", [])
        brief_delivery = documents["brief.json"].get("delivery")
        full_slide_scope = isinstance(brief_delivery, dict) and brief_delivery.get("asset_scope") == "full-slide"
        asset_folder = "独立素材" if full_slide_scope else "透明资产"
        for asset in assets:
            add(asset["path"])
            add(asset["path"], f"{asset_folder}/{_package_safe_stem(asset['id'])}{Path(asset['path']).suffix.lower()}")
            record = asset.get("generation", {}).get("record_path")
            if record:
                add(record)
        if "reconstruction" in manifest:
            # Keep project-relative map/source paths intact under 项目证据 so
            # the copied asset-manifest and map can be reloaded together.
            for relative in _reconstruction.reconstruction_artifact_paths(root, manifest):
                add(relative)
            if full_slide_scope:
                reconstruction = manifest.get("reconstruction")
                map_path = reconstruction.get("map_path") if isinstance(reconstruction, dict) else None
                map_errors: list[str] = []
                map_file = _safe_file(root, map_path, map_errors, "reconstruction map")
                if map_file is None:
                    raise ValueError("; ".join(map_errors))
                reconstruction_map = json.loads(map_file.read_text(encoding="utf-8"))
                for slide in reconstruction_map.get("slides", []):
                    if not isinstance(slide, dict):
                        continue
                    slide_id = slide.get("slide_id")
                    for item in slide.get("items", []):
                        if not isinstance(item, dict) or item.get("representation") != "native":
                            continue
                        source_path = item.get("source_path")
                        item_id = item.get("id")
                        if not isinstance(source_path, str) or not isinstance(item_id, str) or not isinstance(slide_id, str):
                            raise ValueError("full-slide native items require string slide_id, id, and source_path")
                        native_name = (
                            f"{_package_safe_stem(slide_id)}-{_package_safe_stem(item_id)}"
                            f"{Path(source_path).suffix.lower()}"
                        )
                        add(source_path, f"独立素材/{native_name}")
    return files, len(deck), len(assets)


def export_delivery(root: Path, destination: Path, mode: str, *, verify_only: bool = False) -> dict[str, Any]:
    root, destination = Path(root).resolve(), Path(destination).resolve()
    report = validate_delivery(root, mode, "export")
    result = {"ok":False,"errors":[],"warnings":report.get("warnings",[]),"delivery_mode":mode,"output":str(destination),"verify_only":verify_only}
    if not report["ok"]:
        return {**result, "errors":report["errors"]}
    if mode not in {"concept", "assets"}:
        return {**result, "errors":["this exporter stops before assembly"]}
    if destination.is_relative_to(root):
        return {**result, "errors":["output must be outside the working project"]}
    staging: Path | None = None
    try:
        copies, concepts, assets = _sources(root, mode)
        source_snapshot = {rel:_hash((root / rel).read_bytes()) for rel in set(copies.values())}
        # Validate the same source snapshot that will be copied, rather than
        # trusting inputs read before the file inventory was collected.
        current = validate_delivery(root, mode, "export")
        if not current["ok"] or current != report:
            raise ValueError("delivery inputs changed after preflight")
        receipt = {"delivery_mode":mode,"technical_contract":report.get("facts",{}),"assembly":"not-requested","pptx":"not-produced","human_gates":"not-claimed","user_visual_feedback":"not-claimed"}
        full_slide = mode == "assets" and report.get("facts", {}).get("reconstruction_status") == "agent-reviewed"
        label = "完整概念图" if mode == "concept" else (
            "概念图、独立素材与全页重建证据" if full_slide and assets else
            "概念图与全页重建证据" if full_slide else
            "完整概念图与独立透明资产"
        )
        delivery_label = (
            "local-concept-delivery" if mode == "concept" else
            "local-full-slide-reconstruction-delivery" if full_slide else
            "local-concept-assets-delivery"
        )
        readme = (
            f"# {label}\n\n这是所选模式的完整本地交付。无需自动组装或 PPTX。\n\n"
            "概念图保留页面构图；图片素材内部像素不能逐点编辑。技术记录与用户视觉评价分开。\n\n"
            "项目证据保留可再次检查的原输入；其哈希绑定不证明历史生成工具读取过后来写入的 JSON。\n"
        )
        if full_slide:
            readme += (
                "\n全页 `独立素材/` 同时包含图片素材和每个映射原生对象源文件的可直接使用副本。"
                "\n重建地图、渲染结果、渲染器、原生对象源文件和声明的依赖均按项目相对路径保存在 `项目证据/`。"
                "静态 HTML src/href 与 CSS url/@import 依赖会检查其存在且可随包携带；JavaScript import 与运行时生成的请求不在此检查范围内。"
                "地图中的代理复核字段是代理记录，不证明没有遗漏元素或视觉忠实度；用户接受状态为未记录。\n"
            )
        generated = {"execution-receipt.json":_json_bytes(receipt),"README.md":readme.encode("utf-8")}
        expected_hashes = {dest:source_snapshot[source] for dest,source in copies.items()}
        expected_hashes.update({name:_hash(data) for name,data in generated.items()})
        manifest = {"contract_version":"apw-delivery-v1","delivery_mode":mode,"delivery_label":delivery_label,"concept_count":concepts,"asset_count":assets,"source_files":copies,"source_sha256":source_snapshot,"files":expected_hashes,"assembly":"not-requested","human_gates":"not-claimed","user_visual_feedback":"not-claimed"}
        if verify_only:
            if not destination.is_dir():
                raise ValueError("existing package does not exist")
            actual_manifest = json.loads((destination / "package-manifest.json").read_text(encoding="utf-8"))
            if actual_manifest != manifest:
                raise ValueError("package manifest differs from current inputs, mode, files or derived claims")
            actual_files = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
            if actual_files != set(expected_hashes) | {"package-manifest.json"}:
                raise ValueError("package file coverage differs from selected mode")
            for relative, sha in expected_hashes.items():
                path = (destination / relative).resolve()
                if not path.is_relative_to(destination) or _hash(path.read_bytes()) != sha:
                    raise ValueError(f"package file differs from current source: {relative}")
            if any(_hash((root / rel).read_bytes()) != sha for rel,sha in source_snapshot.items()):
                raise ValueError("source changed during verification")
        else:
            if destination.exists():
                raise ValueError("output already exists; choose a new destination")
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.mode-staging-",dir=destination.parent)).resolve()
            for target, source in copies.items():
                path = staging / target
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / source, path)
            for name, data in generated.items():
                (staging / name).write_bytes(data)
            (staging / "package-manifest.json").write_bytes(_json_bytes(manifest))
            for relative, sha in expected_hashes.items():
                if _hash((staging / relative).read_bytes()) != sha:
                    raise ValueError(f"source changed during copy: {relative}")
            if any(_hash((root / rel).read_bytes()) != sha for rel,sha in source_snapshot.items()):
                raise ValueError("source changed during export")
            publish_new_directory(staging, destination)
        return {**result,"ok":True,"concept_count":concepts,"asset_count":assets,"delivery_label":manifest["delivery_label"],"assembly":"not-requested"}
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        return {**result,"errors":[str(exc)]}
    finally:
        if staging is not None and staging.exists():
            # Owned staging directory, checked before recursive cleanup.
            if staging.parent != destination.parent or not staging.name.startswith(f".{destination.name}.mode-staging-") or staging.is_symlink():
                raise ValueError("refusing unsafe staging cleanup")
            shutil.rmtree(staging)
