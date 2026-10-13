"""Deterministic, full-size visual evidence for an assembled editable deck."""

from __future__ import annotations

from PIL import Image, ImageDraw


def side_by_side(concept: Image.Image, render: Image.Image) -> Image.Image:
    left = concept.convert("RGB")
    right = render.convert("RGB")
    if left.size != (1920, 1080) or right.size != (1920, 1080):
        raise ValueError("concept and PPTX render must both be 1920x1080")
    canvas = Image.new("RGB", (3840, 1080))
    canvas.paste(left, (0, 0))
    canvas.paste(right, (1920, 0))
    return canvas


def overlay(concept: Image.Image, render: Image.Image) -> Image.Image:
    if concept.size != (1920, 1080) or render.size != (1920, 1080):
        raise ValueError("concept and PPTX render must both be 1920x1080")
    return Image.blend(concept.convert("RGB"), render.convert("RGB"), 0.5)


def contact_sheet(slides: list[tuple[str, Image.Image]]) -> Image.Image:
    """Compose actual PPTX renders in output order, never concept thumbnails."""
    if not slides:
        raise ValueError("contact sheet needs at least one rendered slide")
    width, height, margin, label_height = 640, 360, 20, 42
    columns = 2
    rows = (len(slides) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * (width + margin) + margin,
                              rows * (height + label_height + margin) + margin), "#F1F5F9")
    draw = ImageDraw.Draw(sheet)
    for index, (slide_id, source) in enumerate(slides):
        if source.size != (1920, 1080):
            raise ValueError(f"{slide_id} render must be 1920x1080")
        x = margin + (index % columns) * (width + margin)
        y = margin + (index // columns) * (height + label_height + margin)
        sheet.paste(source.convert("RGB").resize((width, height), Image.Resampling.LANCZOS), (x, y))
        draw.text((x, y + height + 8), f"{index + 1:02d}  {slide_id}", fill="#0F172A")
    return sheet
