"""Build an isolated full-size, contentful trial packet for manual visual QA."""

import argparse
import subprocess
import sys
from pathlib import Path

from test_pilot_review import SCRIPTS, make_contentful_pilot_fixture
from test_validate_project import write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    if root.exists():
        parser.error("output_dir already exists; use a new path to keep previous evidence")
    root.mkdir(parents=True)
    make_contentful_pilot_fixture(root)
    write_json(root, "pilot-plan.json", {
        "slide_id": "S01", "component_ids": ["C01", "C02"],
        "selection_rationale": "Synthetic contentful page with separate arrows, ordinary photo, native copy, and blank data.",
    })
    for script, args in (
        ("assemble_editable_pptx.py", ["--version", "contentful-v1", "--pilot-slide", "S01"]),
        ("render_pilot_review.py", ["--version", "contentful-v1"]),
    ):
        subprocess.run([sys.executable, str(SCRIPTS / script), str(root), *args], check=True)
    print(root / "pilot-review.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
