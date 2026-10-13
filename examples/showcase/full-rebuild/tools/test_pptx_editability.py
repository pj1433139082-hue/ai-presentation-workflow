#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe real PowerPoint text editing and picture move/undo on a copy."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import win32com.client

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "proof" / "independent-pptx" / "independent-reconstruction-proof-3pages.pptx"
COPY = ROOT / "proof" / "independent-pptx" / "experimental-editability-copy-final-source-paths.pptx"
REPORT = ROOT / "proof" / "independent-pptx" / "editability-test.json"
TEXT_SHAPE = "S02-text-title"
PICTURE_SHAPE = "S02-flow-orange-heat-production"
TEXT_PROBE = " [editable text probe]"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def shape(slide, name):
    for index in range(1, int(slide.Shapes.Count) + 1):
        candidate = slide.Shapes.Item(index)
        if str(candidate.Name) == name:
            return candidate
    raise RuntimeError(f"PowerPoint shape not found: {name}")


def main() -> int:
    if not ORIGINAL.is_file():
        raise FileNotFoundError(ORIGINAL)
    original_hash = sha256(ORIGINAL)
    shutil.copy2(ORIGINAL, COPY)
    app = presentation = None
    try:
        app = win32com.client.gencache.EnsureDispatch("PowerPoint.Application")
        app.DisplayAlerts = 0
        app.Visible = True
        version = str(app.Version)
        presentation = app.Presentations.Open(str(COPY), False, False, True)
        presentation.Windows.Item(1).Activate()
        slide = presentation.Slides.Item(2)
        text_box = shape(slide, TEXT_SHAPE)
        picture = shape(slide, PICTURE_SHAPE)
        original_text = str(text_box.TextFrame.TextRange.Text)
        original_left = float(picture.Left)
        original_top = float(picture.Top)
        original_width = float(picture.Width)
        original_height = float(picture.Height)

        picture.Left = original_left + 2.0
        if not app.CommandBars.GetEnabledMso("Undo"):
            raise RuntimeError("PowerPoint did not record the picture move in its Undo stack")
        app.CommandBars.ExecuteMso("Undo")
        moved_then_undone_left = float(picture.Left)
        if abs(moved_then_undone_left - original_left) > 0.05:
            raise RuntimeError(
                f"PowerPoint Undo did not restore picture position: {moved_then_undone_left} vs {original_left}"
            )

        text_box.TextFrame.TextRange.Text = original_text.rstrip("\r\n") + TEXT_PROBE
        presentation.Save()
        presentation.Close()
        presentation = None
        app.Quit()
        app = None

        app = win32com.client.gencache.EnsureDispatch("PowerPoint.Application")
        app.DisplayAlerts = 0
        app.Visible = True
        reopened = app.Presentations.Open(str(COPY), True, False, False)
        try:
            reopened_slide = reopened.Slides.Item(2)
            reopened_text = str(shape(reopened_slide, TEXT_SHAPE).TextFrame.TextRange.Text).rstrip("\r\n")
            reopened_picture = shape(reopened_slide, PICTURE_SHAPE)
            reopened_left = float(reopened_picture.Left)
            reopened_geometry = {
                "left_pt": reopened_left,
                "top_pt": float(reopened_picture.Top),
                "width_pt": float(reopened_picture.Width),
                "height_pt": float(reopened_picture.Height),
            }
            reopened_picture_type = int(reopened_picture.Type)
            if int(reopened.Slides.Count) != 3:
                raise RuntimeError("experimental copy no longer contains three slides")
            if TEXT_PROBE.strip() not in reopened_text:
                raise RuntimeError("edited native text did not persist after save/reopen")
            if abs(reopened_left - original_left) > 0.05:
                raise RuntimeError("picture position changed after move/undo/save/reopen")
        finally:
            reopened.Close()
        app.Quit()
        app = None

        if sha256(ORIGINAL) != original_hash:
            raise RuntimeError("the original proof deck changed during the copy-only editability probe")
        report = {
            "status": "passed",
            "test_scope": "copy-only PowerPoint COM experiment; not formal assembly acceptance",
            "powerpoint_version": version,
            "original_pptx": ORIGINAL.relative_to(ROOT).as_posix(),
            "source_pptx_sha256": original_hash,
            "original_sha256_before_and_after": original_hash,
            "original_unchanged": True,
            "experimental_copy": COPY.relative_to(ROOT).as_posix(),
            "experimental_copy_sha256": sha256(COPY),
            "page_count_after_reopen": 3,
            "editable_text_shape": TEXT_SHAPE,
            "edited_text_persisted_after_save_reopen": True,
            "picture_shape": PICTURE_SHAPE,
            "picture_type": reopened_picture_type,
            "move_delta_pt": 2.0,
            "undo_restored_left_pt": moved_then_undone_left,
            "undo_restored_position": True,
            "original_picture_geometry_pt": {
                "left": original_left, "top": original_top,
                "width": original_width, "height": original_height,
            },
            "reopened_picture_geometry_pt": reopened_geometry,
        }
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        proof_json_path = ROOT / "proof" / "independent-pptx" / "proof-evidence.json"
        proof_md_path = ROOT / "proof" / "independent-pptx" / "proof-evidence.md"
        if proof_json_path.is_file():
            proof = json.loads(proof_json_path.read_text(encoding="utf-8"))
            if proof.get("pptx", {}).get("pptx_sha256") == original_hash:
                proof["editability_experiment"] = {
                    "status": report["status"],
                    "powerpoint_version": report["powerpoint_version"],
                    "edited_text_persisted_after_save_reopen": report["edited_text_persisted_after_save_reopen"],
                    "undo_restored_position": report["undo_restored_position"],
                    "evidence_path": REPORT.relative_to(ROOT).as_posix(),
                    "evidence_sha256": sha256(REPORT),
                    "source_pptx_sha256": original_hash,
                }
                proof_json_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                from build_reconstruction_pptx import write_markdown
                write_markdown(proof, proof_md_path)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    finally:
        if presentation is not None:
            try:
                presentation.Close()
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
