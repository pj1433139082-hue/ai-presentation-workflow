#!/usr/bin/env python3
"""Compare the canonical skill tree with an installed copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import NamedTuple


IGNORED_DIRECTORY_NAMES = {"__pycache__", ".pytest_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


class DriftReport(NamedTuple):
    missing: tuple[str, ...]
    extra: tuple[str, ...]
    changed: tuple[str, ...]

    @property
    def is_clean(self) -> bool:
        return not (self.missing or self.extra or self.changed)


def should_ignore(relative: Path) -> bool:
    return bool(IGNORED_DIRECTORY_NAMES.intersection(relative.parts)) or (
        relative.suffix.lower() in IGNORED_SUFFIXES
    )


def inventory(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise FileNotFoundError(f"directory does not exist: {root}")
    files: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if should_ignore(relative):
            continue
        normalized = relative.as_posix()
        files[normalized] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def compare_trees(source: Path, installed: Path) -> DriftReport:
    source_files = inventory(source.resolve())
    installed_files = inventory(installed.resolve())
    source_names = set(source_files)
    installed_names = set(installed_files)
    return DriftReport(
        missing=tuple(sorted(source_names - installed_names)),
        extra=tuple(sorted(installed_names - source_names)),
        changed=tuple(
            sorted(
                name
                for name in source_names & installed_names
                if source_files[name] != installed_files[name]
            )
        ),
    )


def parse_args() -> argparse.Namespace:
    canonical = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=canonical)
    parser.add_argument(
        "--installed",
        type=Path,
        default=Path.home() / ".agents" / "skills" / "ai-presentation-workflow",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = compare_trees(args.source, args.installed)
    except FileNotFoundError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    payload = {
        "source": str(args.source.resolve()),
        "installed": str(args.installed.resolve()),
        "clean": report.is_clean,
        "missing": list(report.missing),
        "extra": list(report.extra),
        "changed": list(report.changed),
    }
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif report.is_clean:
        print("PASS: installed skill matches the canonical source")
    else:
        print("FAIL: installed skill has drifted from the canonical source")
        for label in ("missing", "extra", "changed"):
            for path in payload[label]:
                print(f"- {label}: {path}")
    return 0 if report.is_clean else 1


if __name__ == "__main__":
    sys.exit(main())
