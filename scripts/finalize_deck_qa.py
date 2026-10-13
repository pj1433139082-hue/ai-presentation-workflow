#!/usr/bin/env python3
"""Finalize already-reviewed slide QA; this does not approve the G5 release gate."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from validate_project import ProjectValidator


def encode(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def finalize(root: Path) -> Path:
    root = root.resolve()
    preflight = ProjectValidator(root, "assembly")
    errors = preflight.run()
    if errors:
        raise ValueError("assembly preflight failed: " + "; ".join(errors[:5]))
    report_path = root / "qa-report.json"
    map_path = root / "assembly-map.json"
    if not report_path.resolve().is_relative_to(root) or not map_path.resolve().is_relative_to(root):
        raise ValueError("QA or assembly map path must stay inside the project")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assembly = json.loads(map_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not isinstance(assembly, dict):
        raise ValueError("QA report and assembly map must be JSON objects")
    if report.get("status") != "pending-human" or assembly.get("status") != "structure-assembled-visual-review-pending":
        raise ValueError("QA packet and assembly must still be pending visual review")
    if not isinstance(report.get("final_reviewer"), str) or not report["final_reviewer"].strip():
        raise ValueError("final_reviewer must identify the human who checked the whole-deck contact sheet")
    deck_checks = report.get("deck_checks")
    if not isinstance(deck_checks, dict) or any(deck_checks.get(key) is not True for key in
                                                ("reference_transfer", "composition_richness", "readability_full_size", "visual_coherence", "truth_consistency")):
        raise ValueError("all five human whole-deck checks must pass")
    if not isinstance(report.get("slides"), list) or not report["slides"] or any(not isinstance(row, dict) for row in report["slides"]):
        raise ValueError("all slide review records are required")
    version = report.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", version):
        raise ValueError("QA version must be a safe identifier")
    expected_exceptions = f"reviews/qa/{version}/exception-register.json"
    expected_index = f"reviews/qa/{version}/deliverable-index.json"
    if report.get("exception_register") != expected_exceptions or report.get("deliverable_index") != expected_index:
        raise ValueError("QA index paths must belong to the current version")
    # The reviewer edits each slide's decision, checkboxes, timestamp, and issues.
    # This operation only promotes that recorded decision after the contract passes.
    report["status"] = "passed"
    report["checks_performed"] = list(dict.fromkeys([*report.get("checks_performed", []),
                                                      "reference-transfer", "composition-richness", "readability-full-size"]))
    assembly["status"] = "visual-review-passed"
    exception_path = root / expected_exceptions
    index_path = root / expected_index
    if not exception_path.resolve().is_relative_to(root) or not index_path.resolve().is_relative_to(root):
        raise ValueError("QA index paths must stay inside the project")
    exceptions = {"status": "reviewed", "issues": report.get("exceptions", [])}
    index = {
        "status": "ready", "pptx": {"path": assembly["output"], "sha256": assembly["sha256"]},
        "contact_sheet": {"path": report["final_contact_sheet"], "sha256": report["contact_sheet_sha256"]},
        "slides": [{"slide_id": row.get("slide_id"), "status": row.get("status")} for row in report["slides"]],
    }
    updates = {report_path: encode(report), map_path: encode(assembly),
               exception_path: encode(exceptions), index_path: encode(index)}
    backups = {path: path.read_bytes() for path in updates}
    try:
        for path, data in updates.items():
            path.write_bytes(data)
        errors = ProjectValidator(root, "qa").run()
        if errors:
            raise ValueError("full-deck QA did not pass: " + "; ".join(errors[:8]))
    except Exception:
        for path, data in backups.items():
            path.write_bytes(data)
        raise
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    args = parser.parse_args()
    try:
        output = finalize(args.project_dir)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"Full-deck visual QA passed: {output}")
    print("G5 release is still pending the user's separate exact approval: 确认发布")
    return 0


if __name__ == "__main__":
    sys.exit(main())
