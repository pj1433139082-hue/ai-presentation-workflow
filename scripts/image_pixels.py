"""Bounded, byte-addressed decoded pixels for one validation run."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from io import BytesIO
from pathlib import Path

from PIL import Image


class ImagePixels:
    def __init__(self, max_bytes: int = 128 * 1024 * 1024) -> None:
        if max_bytes < 0:
            raise ValueError("pixel budget must be non-negative")
        self.max_bytes = max_bytes
        self.retained_bytes = 0
        self._images: OrderedDict[tuple[str, str], tuple[Image.Image, int]] = OrderedDict()

    def decode(self, data: bytes, mode: str | None = None) -> Image.Image:
        digest = hashlib.sha256(data).hexdigest()
        # Opening the header on hits retains Pillow's current pixel-limit guard.
        with Image.open(BytesIO(data)) as opened:
            target_mode = mode or opened.mode
            key = (digest, target_mode)
            prior = self._images.pop(key, None)
            if prior is not None:
                self._images[key] = prior
                return prior[0].copy()
            opened.load()
            pixels = opened.convert(target_mode)
        # Four bytes per pixel is conservative for the RGB/LA/RGBA callers.
        cost = pixels.width * pixels.height * max(4, len(pixels.getbands()))
        if cost > self.max_bytes:
            return pixels
        while self._images and self.retained_bytes + cost > self.max_bytes:
            _, (evicted, evicted_cost) = self._images.popitem(last=False)
            evicted.close()
            self.retained_bytes -= evicted_cost
        self._images[key] = (pixels, cost)
        self.retained_bytes += cost
        # Callers may crop/convert/mutate their copy without poisoning reuse.
        return pixels.copy()

    def read(self, path: Path, mode: str | None = None, *, expected_sha256: str | None = None) -> Image.Image:
        data = path.read_bytes()
        if expected_sha256 is not None and hashlib.sha256(data).hexdigest() != expected_sha256:
            raise ValueError("image source hash is stale")
        return self.decode(data, mode)

    def clear(self) -> None:
        for pixels, _ in self._images.values():
            pixels.close()
        self._images.clear()
        self.retained_bytes = 0
