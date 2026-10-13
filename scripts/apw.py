"""Public entry point for strict production and local showcase projects.

The exact project-kind.json discriminator selects the showcase route. Projects
without that file continue through the existing strict production validator and
assembler. A present but invalid discriminator is an error, never a fallback.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from showcase_contract import STAGES as SHOWCASE_STAGES, export_showcase, validate_showcase
except ImportError:  # imported as scripts.apw
    from .showcase_contract import STAGES as SHOWCASE_STAGES, export_showcase, validate_showcase

try:
    from validate_project import ProjectValidator, STAGES as PRODUCTION_STAGES
except ImportError:  # imported as scripts.apw
    from .validate_project import ProjectValidator, STAGES as PRODUCTION_STAGES


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "showcase-template"
SHOWCASE_KIND = {"contract_version": "showcase-v1", "purpose": "showcase"}


def _delivery(root: Path) -> tuple[str, tuple[str, ...], bool]:
    """Missing mode means an existing assembly project, never a new default."""
    try:
        from delivery_modes import MODE_STAGES, read_delivery_mode
    except ImportError:
        from .delivery_modes import MODE_STAGES, read_delivery_mode
    mode = read_delivery_mode(root)
    selector = root / "delivery-mode.json"
    explicit = selector.exists() or selector.is_symlink()
    stages = MODE_STAGES[mode] if explicit else SHOWCASE_STAGES
    return mode, stages, explicit


def _delivery_check(root: Path, stage: str) -> dict[str, Any]:
    try:
        mode, _, explicit = _delivery(root)
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "stage": stage, "errors": [str(exc)], "warnings": []}
    if not explicit:
        return validate_showcase(root, stage)
    try:
        from delivery_modes import validate_delivery
    except ImportError:
        from .delivery_modes import validate_delivery
    return validate_delivery(root, mode, stage)


def _json_report(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _route(root: Path) -> tuple[str, str | None]:
    """Return (route, error); invalid present kinds never become production."""
    marker = root / "project-kind.json"
    if not marker.exists() and not marker.is_symlink():
        return "production", None
    if not marker.is_file():
        return "invalid", "project-kind.json exists but is not a regular file"
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return "invalid", f"project-kind.json cannot be read as UTF-8 JSON: {exc}"
    if value == SHOWCASE_KIND:
        return "showcase", None
    return "invalid", "project-kind.json is present but does not exactly select showcase-v1/showcase; refusing legacy fallback"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _production_report(root: Path, stage: str) -> dict[str, Any]:
    if stage not in PRODUCTION_STAGES:
        return {"ok": False, "route": "production", "stage": stage, "errors": [f"unknown production stage {stage!r}; expected one of {', '.join(PRODUCTION_STAGES)}"], "warnings": []}
    validator = ProjectValidator(root.resolve(), stage)
    errors = validator.run()
    return {"ok": not errors, "route": "production", "stage": stage, "errors": errors, "warnings": [], "facts": {"quality_profile": validator.quality_profile()}}


def check_project(root: Path, stage: str) -> dict[str, Any]:
    root = Path(root).resolve()
    if not root.is_dir():
        return {"ok": False, "route": "unknown", "stage": stage, "errors": [f"project directory does not exist: {root}"], "warnings": []}
    route, error = _route(root)
    if error:
        return {"ok": False, "route": "invalid", "stage": stage, "errors": [error], "warnings": []}
    if route == "showcase":
        return {"route": route, **_delivery_check(root, stage)}
    return _production_report(root, stage)


def status_project(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    if not root.is_dir():
        return {"ok": False, "route": "unknown", "errors": [f"project directory does not exist: {root}"]}
    route, error = _route(root)
    if error:
        return {"ok": False, "route": "invalid", "errors": [error]}
    if route == "showcase":
        try:
            mode, ordered_stages, explicit = _delivery(root)
        except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            return {"ok": False, "route": route, "errors": [str(exc)]}
        stages: dict[str, dict[str, Any]] = {}
        for stage in ordered_stages:
            stages[stage] = _delivery_check(root, stage)
        terminal = f"complete-{mode}" if explicit else "complete-local-draft"
        next_stage = next((stage for stage in ordered_stages if not stages[stage]["ok"]), terminal)
        ready = [stage for stage, report in stages.items() if report["ok"]]
        return {
            "ok": True,
            "route": "showcase",
            "project_kind": SHOWCASE_KIND,
            "delivery_mode": mode,
            "mode_origin": "explicit" if explicit else "legacy-assembly-compatibility",
            "quality_profile": (_read_json(root / "brief.json") or {}).get("quality_profile"),
            "ready_stages": ready,
            "next_stage": next_stage,
            "stages": stages,
            "human_gates": "not-claimed",
        }
    state = _read_json(root / "run-state.json") or {}
    declared = state.get("stage", "release")
    if declared == "released":
        declared = "release"
    stage = declared if declared in PRODUCTION_STAGES else "release"
    report = _production_report(root, stage)
    return {**report, "current_stage": stage, "quality_profile": report.get("facts", {}).get("quality_profile")}


def init_showcase(root: Path, project_id: str | None = None, mode: str = "concept") -> dict[str, Any]:
    """Create a new showcase scaffold without replacing any existing path."""
    target = Path(root).expanduser().resolve()
    if mode not in {"concept", "assets", "assembly"}:
        return {"ok": False, "errors": ["mode must be concept, assets, or assembly"], "root": str(target)}
    if target.exists():
        return {"ok": False, "errors": [f"target already exists; init never overwrites: {target}"], "root": str(target)}
    if not TEMPLATE_ROOT.is_dir():
        return {"ok": False, "errors": [f"showcase template is missing: {TEMPLATE_ROOT}"], "root": str(target)}
    if target == SKILL_ROOT or target in SKILL_ROOT.parents:
        return {"ok": False, "errors": ["refusing to initialize a project over the skill directory or its parent"], "root": str(target)}
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.apw-init-", dir=target.parent))
    try:
        # Copy template contents into our private staging directory, then publish
        # by rename so a competing existing target is never replaced.
        for item in TEMPLATE_ROOT.iterdir():
            destination = staging / item.name
            if item.is_dir():
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)
        (staging / "delivery-mode.json").write_text(json.dumps({"mode": mode}) + "\n", encoding="utf-8")
        # Early deliverables do not carry empty assembly/QA obligations.
        irrelevant = ["assembly-map.json", "showcase-review.json"]
        if mode in {"concept", "assets"}:
            irrelevant.append("scene-graph.json")
        if mode == "concept":
            irrelevant.append("asset-manifest.json")
        for filename in irrelevant:
            (staging / filename).unlink(missing_ok=True)
        brief_path = staging / "brief.json"
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        identifier = project_id or re.sub(r"[^A-Za-z0-9_.-]+", "-", target.name).strip("-.")
        brief["project_id"] = identifier or "showcase-project"
        brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if target.exists():
            return {"ok": False, "errors": [f"target appeared during init; refusing replacement: {target}"], "root": str(target)}
        staging.rename(target)
        return {
            "ok": True,
            "route": "showcase",
            "root": str(target),
            "project_id": brief["project_id"],
            "delivery_mode": mode,
            "delivery_label": "empty-local-draft-scaffold",
            "next_steps": [
                "Fill brief.json with the intended audience, goal, and hashed source_map.",
                "Analyze at least one local reference in reference-study.json and style-contract.json.",
                "Write deck-spec.json and full-page concepts, then bind concept-generation-log.json.",
                "Run apw status; a scaffold is not a quality or approval pass.",
            ],
            "human_gates": "not-claimed",
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        return {"ok": False, "errors": [f"could not initialize showcase scaffold: {exc}"], "root": str(target)}


def build_project(root: Path, version: str) -> dict[str, Any]:
    root = Path(root).resolve()
    if not root.is_dir():
        return {"ok": False, "errors": [f"project directory does not exist: {root}"]}
    route, error = _route(root)
    if error:
        return {"ok": False, "route": "invalid", "errors": [error]}
    if route == "showcase":
        try:
            mode, _, _ = _delivery(root)
        except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            return {"ok": False, "route": route, "errors": [str(exc)]}
        if mode != "assembly":
            return {"ok": False, "route": route, "delivery_mode": mode, "phase": "mode-boundary", "errors": [f"mode {mode!r} ends before PPTX assembly; select assembly explicitly to build"]}
        preflight = validate_showcase(root, "concept")
        if not preflight["ok"]:
            return {"ok": False, "route": route, "phase": "concept-preflight", "errors": preflight["errors"], "warnings": preflight["warnings"]}
        try:
            try:
                from assemble_editable_pptx import assemble_showcase
            except ImportError:
                from .assemble_editable_pptx import assemble_showcase
            assembly = assemble_showcase(root, version, render=True)
        except (ImportError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            return {"ok": False, "route": route, "phase": "assembly", "errors": [str(exc)]}
        post = validate_showcase(root, "assembly")
        return {"ok": post["ok"], "route": route, "phase": "assembly", "assembly": assembly, "errors": post["errors"], "warnings": post["warnings"], "delivery_label": "local-showcase-draft"}
    report = _production_report(root, "assets")
    if not report["ok"]:
        return {"ok": False, "route": route, "phase": "assets-preflight", "errors": report["errors"]}
    try:
        try:
            from assemble_editable_pptx import assemble
        except ImportError:
            from .assemble_editable_pptx import assemble
        output = assemble(root, version, render=True)
    except (ImportError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        return {"ok": False, "route": route, "phase": "assembly", "errors": [str(exc)]}
    post = _production_report(root, "assembly")
    return {"ok": post["ok"], "route": route, "phase": "assembly", "output": str(output), "errors": post["errors"], "warnings": []}


def export_project(root: Path, destination: Path | None = None, *, verify_only: bool = False, pptx_name: str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    if not root.is_dir():
        return {"ok": False, "errors": [f"project directory does not exist: {root}"]}
    route, error = _route(root)
    if error:
        return {"ok": False, "route": "invalid", "errors": [error]}
    default_output = root.parent / f"{root.name}-交付包" if route == "showcase" else root / "交付包"
    output = (Path(destination).expanduser() if destination else default_output).resolve()
    if route == "showcase":
        try:
            mode, _, _ = _delivery(root)
        except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            return {"ok": False, "route": route, "errors": [str(exc)]}
        if mode != "assembly":
            if pptx_name is not None:
                return {"ok": False, "errors": ["pptx_name is only valid for assembly mode"], "delivery_mode": mode}
            try:
                from delivery_export import export_delivery
            except ImportError:
                from .delivery_export import export_delivery
            return export_delivery(root, output, mode, verify_only=verify_only)
        return export_showcase(root, output, verify_only=verify_only, pptx_name=pptx_name)
    try:
        try:
            from export_final_package import export
        except ImportError:
            from .export_final_package import export
        count, assets, pptx = export(root, output, pptx_name=pptx_name, verify_only=verify_only)
        return {"ok": True, "route": route, "concept_count": count, "asset_count": assets, "pptx_path": str(pptx), "output": str(output), "verify_only": verify_only}
    except (ImportError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return {"ok": False, "route": route, "errors": [str(exc)], "output": str(output), "verify_only": verify_only}


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apw", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a new non-overwriting showcase scaffold")
    init_parser.add_argument("root", type=Path)
    init_parser.add_argument("--project-id")
    init_parser.add_argument("--mode", choices=["concept", "assets", "assembly"], default="concept", help="delivery endpoint; default stops after full concepts")

    status_parser = subparsers.add_parser("status", help="show route and currently checkable stages")
    status_parser.add_argument("root", type=Path)

    check_parser = subparsers.add_parser("check", help="validate one explicit contract stage")
    check_parser.add_argument("root", type=Path)
    check_parser.add_argument("--stage", required=True, choices=sorted(set(SHOWCASE_STAGES + tuple(PRODUCTION_STAGES))))

    build_parser = subparsers.add_parser("build", help="build using the selected existing assembler")
    build_parser.add_argument("root", type=Path)
    build_parser.add_argument("--version", required=True)

    export_parser = subparsers.add_parser("export", help="publish or verify a local package")
    export_parser.add_argument("root", type=Path)
    export_parser.add_argument("--output", type=Path)
    export_parser.add_argument("--pptx-name")
    export_parser.add_argument("--verify", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        report = init_showcase(args.root, args.project_id, args.mode)
        exit_code = 0 if report["ok"] else 1
    elif args.command == "status":
        report = status_project(args.root)
        exit_code = 0 if report["ok"] else 1
    elif args.command == "check":
        report = check_project(args.root, args.stage)
        exit_code = 0 if report["ok"] else 1
    elif args.command == "build":
        report = build_project(args.root, args.version)
        exit_code = 0 if report["ok"] else 1
    else:
        report = export_project(args.root, args.output, verify_only=args.verify, pptx_name=args.pptx_name)
        exit_code = 0 if report["ok"] else 1
    print(_json_report(report))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_project", "check_project", "export_project", "init_showcase", "main", "make_parser", "status_project"]
