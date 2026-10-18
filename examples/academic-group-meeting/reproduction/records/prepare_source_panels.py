"""Render the selected source-PDF panels at 4x from verified 2x page coordinates.

The crop boxes are pixel rectangles on the recorded 2x page render.  They are
converted back to PDF points by dividing by two, then rasterized directly from
the original PDF at 4x.  This preserves the source figure and axis labels.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "sources" / "figure-panel-map.json"
COORDS_2X = {
    "fig2d": [940, 88, 1088, 322],
    "fig2f": [410, 330, 1090, 566],
    "fig2i": [755, 560, 1095, 808],
    "fig3c": [134, 450, 449, 701],
    "fig3h": [767, 713.1, 1090, 970],
    "fig5d": [620, 372, 1080, 520],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    data = json.loads(MAP_PATH.read_text(encoding="utf-8-sig"))
    pdf_path = ROOT / data["source_pdf"]
    actual_pdf_hash = sha256(pdf_path)
    if actual_pdf_hash != data["source_sha256"]:
        raise SystemExit(f"Source PDF hash mismatch: {actual_pdf_hash}")

    doc = fitz.open(pdf_path)
    out_dir = ROOT / "sources" / "figure-panels"
    out_dir.mkdir(parents=True, exist_ok=True)
    audit = []
    for item in data["panels"]:
        box = COORDS_2X.get(item["panel_id"], item["crop_box_on_2x_page_render_px"])
        page_no = int(item["source_page"])
        page = doc[page_no - 1]
        clip = fitz.Rect(*(value / 2 for value in box))
        if not page.rect.contains(clip):
            raise ValueError(f"{item['panel_id']} crop outside page: {clip} vs {page.rect}")
        pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=clip, alpha=False)
        out_path = ROOT / item["output_path"]
        pix.save(out_path)
        with Image.open(out_path) as image:
            size = list(image.size)
        item["crop_box_on_2x_page_render_px"] = box
        item["page_render_size_px_at_2x"] = [1191, 1582] if page_no in (4, 6, 9) else None
        item["output_size_px"] = size
        item["output_sha256"] = sha256(out_path)
        item["render_method"] = "direct 4x PDF clip; 2x inspected-page pixel coordinates divided by 2 to PDF points"
        if item["panel_id"] in {"fig3c", "fig3h"}:
            item["coordinate_source"] = "ai-presentation-workflow/examples/academic-group-meeting/composition-map.json; matched source PDF SHA256"
        else:
            item["coordinate_source"] = "independent visual review of supplied PDF page render at 2x"
        item["visual_review_status"] = "pending individual visual check"
        audit.append({
            "panel_id": item["panel_id"],
            "source_page": page_no,
            "crop_box_on_2x_page_render_px": box,
            "pdf_clip_points": [round(v / 2, 2) for v in box],
            "output_size_px": size,
            "output_sha256": item["output_sha256"],
            "path": item["output_path"],
            "coordinate_source": item["coordinate_source"],
        })

    doc.close()
    data["crop_coordinates"] = "pixel coordinates on 1191x1582 inspected 2x render for PDF pages 4/9; direct 4x PDF clip after coordinate /2 to points"
    MAP_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_path = ROOT / "records" / "source-panel-render-log.json"
    review_path.write_text(json.dumps({
        "source_pdf": data["source_pdf"],
        "source_sha256": actual_pdf_hash,
        "page_render_sizes_px_at_2x": {"PDF p.4": [1191, 1582], "PDF p.9": [1191, 1582]},
        "scale": 4,
        "panels": audit,
        "visual_review_status": "pending individual visual check",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {len(audit)} panels from PDF SHA256 {actual_pdf_hash}")
    for entry in audit:
        print(f"{entry['panel_id']}: {entry['output_size_px']} {entry['output_sha256']}")


if __name__ == "__main__":
    main()
