import hashlib
import importlib.util
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

SPEC = importlib.util.spec_from_file_location("pixel_test_module", Path(__file__).resolve().parents[1] / "scripts/image_pixels.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ImagePixels = MODULE.ImagePixels


def png(color):
    buffer = BytesIO()
    Image.new("RGBA", (3, 3), color).save(buffer, format="PNG", compress_level=0)
    return buffer.getvalue()


def test_reuses_decodes_but_returned_pixels_are_independent():
    data = png((1, 2, 3, 255))
    cache = ImagePixels()
    with patch.object(Image, "_getdecoder", wraps=Image._getdecoder) as decoder:
        first = cache.decode(data)
        first.putpixel((0, 0), (9, 9, 9, 255))
        second = cache.decode(data, "RGBA")
        assert decoder.call_count == 1
    assert second.getpixel((0, 0)) == (1, 2, 3, 255)
    cache.clear()
    assert cache.retained_bytes == 0


def test_same_path_size_and_mtime_cannot_hide_changed_bytes(tmp_path):
    path = tmp_path / "image.png"
    first, second = png((1, 2, 3, 255)), png((3, 2, 1, 255))
    assert len(first) == len(second)
    path.write_bytes(first)
    stamp = path.stat().st_mtime_ns
    cache = ImagePixels()
    cache.read(path)
    path.write_bytes(second)
    os.utime(path, ns=(stamp, stamp))
    assert cache.read(path).getpixel((0, 0)) == (3, 2, 1, 255)
    with pytest.raises(ValueError, match="hash is stale"):
        cache.read(path, expected_sha256=hashlib.sha256(first).hexdigest())


def test_eviction_and_oversized_images_decode_safely():
    first, second = png((1, 2, 3, 255)), png((3, 2, 1, 255))
    cache = ImagePixels(max_bytes=36)
    with patch.object(Image, "_getdecoder", wraps=Image._getdecoder) as decoder:
        for data in (first, second, first):
            cache.decode(data)
        assert decoder.call_count == 3
    assert cache.retained_bytes == 36
    cache = ImagePixels(max_bytes=35)
    cache.decode(first)
    assert cache.retained_bytes == 0


def test_cache_hit_keeps_current_pillow_pixel_limit():
    data = png((1, 2, 3, 255))
    cache = ImagePixels()
    cache.decode(data)
    with patch.object(Image, "MAX_IMAGE_PIXELS", 4):
        with pytest.raises(Image.DecompressionBombError):
            cache.decode(data)


def test_validator_reuses_pixels_across_alpha_and_isolation_then_discards_them(tmp_path):
    from test_validate_project import ProjectValidator, make_valid_project
    make_valid_project(tmp_path)
    decodes = []
    for budget in (0, 128 * 1024 * 1024):
        validator = ProjectValidator(tmp_path, "assets")
        validator.pixel_cache = ImagePixels(budget)
        with patch.object(Image, "_getdecoder", wraps=Image._getdecoder) as decoder:
            assert validator.run() == []
            decodes.append(decoder.call_count)
        assert validator.pixel_cache.retained_bytes == 0
    assert decodes[1] < decodes[0]
