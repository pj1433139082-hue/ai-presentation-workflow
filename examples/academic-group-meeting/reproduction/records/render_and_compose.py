"""Deterministically compose the 11 concept pages and original paper panels.

All concept backgrounds are fresh image_gen outputs or their recorded local
revisions. Original evidence panels are inserted only after generation/editing.
The script never sends composed pages or original data panels to image_gen.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CANVAS = (1672, 941)

BACKGROUND = {
    "S01": "records/revisions/S01-edit-01.png",
    "S02": "concepts/base/S02.png",
    "S03": "records/revisions/S03-edit-02.png",
    "S04": "concepts/base/S04.png",
    "S05": "records/revisions/S05-edit-01.png",
    "S06": "concepts/base/S06.png",
    "S07": "records/revisions/S07-edit-03.png",
    "S08": "records/revisions/S08-edit-02.png",
    "S09": "records/revisions/S09-edit-02.png",
    "S10": "concepts/base/S10.png",
    "S11": "concepts/base/S11.png",
}

# Bounding boxes of redundant far-right page indices; the source footer row
# already carries each page number, so this removes only the duplicate glyph.
PAGE_INDEX_BOXES = {
    "S01": [1578, 891, 1637, 908], "S02": [1590, 913, 1640, 926],
    "S03": [1585, 906, 1637, 921], "S04": [1591, 909, 1650, 924],
    "S05": [1591, 906, 1644, 921], "S06": [1587, 904, 1638, 917],
    "S07": [1589, 910, 1641, 926], "S08": [1583, 910, 1635, 927],
    "S09": [1586, 915, 1641, 933], "S10": [1589, 906, 1640, 919],
    "S11": [1593, 915, 1643, 932],
}

# Target rectangles use half-open canvas pixel coordinates. Panels are fitted
# with contain, preserving their aspect ratio and all source axes/labels.
INSERTIONS = {
    "S04": [{"panel": "fig2d", "rect": [1188, 202, 1626, 753]}],
    "S05": [{"panel": "fig2f", "rect": [80, 574, 760, 875]}],
    "S06": [{"panel": "fig2g", "rect": [1292, 168, 1633, 516]}],
    "S07": [{"panel": "fig2i", "rect": [625, 548, 1017, 819]}],
    "S08": [
        {"panel": "fig3c", "rect": [38, 218, 445, 541]},
        {"panel": "fig3h", "rect": [889, 219, 1309, 542]},
    ],
    "S09": [{"panel": "fig4f", "rect": [1155, 214, 1630, 616]}],
    "S10": [
        {"panel": "fig5d", "rect": [78, 252, 741, 438]},
        {"panel": "fig5f", "rect": [960, 171, 1637, 437]},
    ],
}

# These masks clear generated placeholders or invented chart/schematic content
# from the page background only. The original-paper panels are never modified.
BACKGROUND_MASKS = {
    "S04": [[1180, 193, 1634, 760]],
    "S05": [[80, 575, 760, 874]],
    "S06": [[1293, 169, 1634, 515]],
    "S07": [[625, 550, 1017, 819]],
    "S08": [[38, 218, 445, 541], [889, 219, 1309, 542]],
    "S09": [[1155, 214, 1630, 616]],
    # Keep the verified text above Fig.5d, remove the placeholder and fake bars.
    "S10": [[60, 172, 387, 436], [398, 267, 740, 436], [958, 170, 1638, 438]],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def panel_index() -> dict[str, dict]:
    data = json.loads((ROOT / "sources" / "figure-panel-map.json").read_text(encoding="utf-8-sig"))
    source_pdf = ROOT / data["source_pdf"]
    if sha256(source_pdf) != data["source_sha256"]:
        raise SystemExit("Source PDF changed since panel rendering")
    index = {item["panel_id"]: item for item in data["panels"]}
    for panel_id, item in index.items():
        path = ROOT / item["output_path"]
        if sha256(path) != item["output_sha256"]:
            raise SystemExit(f"Panel hash mismatch: {panel_id}")
    return index


def contain(source: Image.Image, rect: list[int]) -> tuple[Image.Image, tuple[int, int]]:
    x0, y0, x1, y1 = rect
    target_w, target_h = x1 - x0, y1 - y0
    scale = min(target_w / source.width, target_h / source.height)
    size = (max(1, round(source.width * scale)), max(1, round(source.height * scale)))
    resized = source.resize(size, Image.Resampling.LANCZOS)
    place = (x0 + (target_w - size[0]) // 2, y0 + (target_h - size[1]) // 2)
    return resized, place


def main() -> None:
    panels = panel_index()
    page_records = []
    for slide_id, background_rel in BACKGROUND.items():
        background_path = ROOT / background_rel
        bg_hash = sha256(background_path)
        with Image.open(background_path) as opened:
            page = opened.convert("RGB")
        if page.size != CANVAS:
            raise SystemExit(f"Unexpected canvas for {slide_id}: {page.size}")

        page_draw = ImageDraw.Draw(page)
        page_no_box = PAGE_INDEX_BOXES[slide_id]
        page_draw.rectangle((page_no_box[0] - 2, page_no_box[1] - 2,
                             page_no_box[2] + 2, page_no_box[3] + 2), fill="white")

        masks = BACKGROUND_MASKS.get(slide_id, [])
        for x0, y0, x1, y1 in masks:
            page_draw.rectangle((x0, y0, x1, y1), fill="white")

        panel_records = []
        for placement in INSERTIONS.get(slide_id, []):
            item = panels[placement["panel"]]
            source_path = ROOT / item["output_path"]
            with Image.open(source_path) as opened:
                source = opened.convert("RGB")
            fitted, (x, y) = contain(source, placement["rect"])
            page.paste(fitted, (x, y))
            panel_records.append({
                "panel_id": placement["panel"],
                "source_path": item["output_path"],
                "source_sha256": item["output_sha256"],
                "source_page": item["source_page"],
                "source_box_on_2x_render_px": item["crop_box_on_2x_page_render_px"],
                "source_pdf_clip_points": [round(v / 2, 3) for v in item["crop_box_on_2x_page_render_px"]],
                "target_contain_rect_px": placement["rect"],
                "actual_placement_px": [x, y, x + fitted.width, y + fitted.height],
                "aspect_ratio_preserved": True,
            })

        out_path = ROOT / "concepts" / f"{slide_id}.png"
        page.save(out_path, format="PNG", optimize=False, compress_level=6)
        page_records.append({
            "slide": slide_id,
            "background_path": background_rel,
            "background_sha256": bg_hash,
            "canvas_px": list(CANVAS),
            "duplicate_page_index_removed_px": page_no_box,
            "background_placeholder_masks_px": masks,
            "source_panels_inserted": panel_records,
            "output_path": f"concepts/{slide_id}.png",
            "output_sha256": sha256(out_path),
            "output_size_px": list(page.size),
        })
        print(f"{slide_id}: {sha256(out_path)}")

    spec = {
        "method": "Pillow deterministic contain composition; evidence panels inserted after all image_gen work",
        "canvas_px": list(CANVAS),
        "source_pdf": "sources/paper.pdf",
        "source_pdf_sha256": panels["fig2d"]["source_sha256"],
        "source_panels_unmodified": True,
        "generated_page_as_input_to_image_gen": False,
        "slides": page_records,
    }
    (ROOT / "records" / "composition-map.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
