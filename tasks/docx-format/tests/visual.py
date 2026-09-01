"""Measure a rendered page the way a reader sees it.

Everything here works on the raster, not on the PDF object model. That choice is
not cosmetic: the same document rendered by LibreOffice 7.4 and 26.2 disagrees
about whether the footer ornament is an image or a vector path, so any assertion
counting objects is version-dependent. The two renderings agree on *appearance*
to within 3 pixels out of 1754, so colour masks over pixels are both closer to
what is being judged and markedly more stable.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pymupdf
from scipy import ndimage

DPI = 150
PT_PER_PX = 72.0 / DPI

# Palette of the template's visual identity, in rendered sRGB.
RED = (0.93, 0.00, 0.00)
ORANGE = (0.93, 0.49, 0.19)
GREEN = (0.44, 0.68, 0.28)
COLOUR_TOL = 0.10


@dataclass(frozen=True, slots=True)
class Region:
    x0: int
    y0: int
    x1: int
    y1: int
    pixels: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    def contains(self, other: "Region", slack: int = 8) -> bool:
        return (
            self.x0 - slack <= other.x0
            and other.x1 <= self.x1 + slack
            and self.y0 - slack <= other.y0
            and other.y1 <= self.y1 + slack
        )

    def centre(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)

    def __repr__(self) -> str:
        return f"({self.x0},{self.y0})-({self.x1},{self.y1})"


class Page:
    """One rendered page: its pixels, its colour regions, and its text."""

    def __init__(self, pdf_path):
        doc = pymupdf.open(pdf_path)
        if len(doc) != 1:
            raise ValueError(f"expected a single page, got {len(doc)}")
        self.pdf_page = doc[0]
        pixmap = self.pdf_page.get_pixmap(dpi=DPI)
        raw = np.frombuffer(pixmap.samples, dtype=np.uint8)
        self.pixels = (
            raw.reshape(pixmap.height, pixmap.width, pixmap.n)[:, :, :3].astype(np.float32)
            / 255.0
        )
        self.height, self.width = self.pixels.shape[:2]

    def regions(self, colour, min_pixels: int = 60) -> list[Region]:
        """Connected components of pixels matching `colour`, largest first."""
        mask = np.all(np.abs(self.pixels - np.array(colour)) <= COLOUR_TOL, axis=-1)
        labelled, count = ndimage.label(mask)
        found = []
        for index in range(1, count + 1):
            ys, xs = np.where(labelled == index)
            if len(ys) < min_pixels:
                continue
            found.append(Region(int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()), len(ys)))
        return sorted(found, key=lambda r: -r.pixels)

    def text(self) -> str:
        return self.pdf_page.get_text()

    def span_color(self, substring: str) -> tuple[float, float, float] | None:
        """The rendered colour of the first text span that contains `substring`.

        Read off the text layer so the accent of a specific run can be compared
        between the template and the output without hunting its glyph pixels out
        of a caption that also carries black text. Returns sRGB in 0..1, or None
        if no span contains the substring.
        """
        for block in self.pdf_page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if substring in span["text"]:
                        c = int(span["color"])
                        return ((c >> 16 & 255) / 255.0,
                                (c >> 8 & 255) / 255.0,
                                (c & 255) / 255.0)
        return None

    def text_boxes(self) -> list[tuple[Region, str]]:
        out = []
        for block in self.pdf_page.get_text("blocks"):
            label = block[4].strip()
            if not label:
                continue
            out.append((
                Region(*(int(v / PT_PER_PX) for v in block[:4]), 0),
                label,
            ))
        return out

    def body_images(self) -> list[Region]:
        """Placed images inside the body band.

        Position, not object identity: the band excludes the banner at the top
        and the footer ornament at the bottom, both of which differ in kind
        between renderer versions while sitting in the same place.
        """
        band_top = 0.14 * self.height
        band_bottom = 0.92 * self.height
        out = []
        for image in self.pdf_page.get_images(full=True):
            for rect in self.pdf_page.get_image_rects(image[0]):
                region = Region(
                    int(rect.x0 / PT_PER_PX), int(rect.y0 / PT_PER_PX),
                    int(rect.x1 / PT_PER_PX), int(rect.y1 / PT_PER_PX), 0,
                )
                if band_top <= region.y0 and region.y1 <= band_bottom:
                    out.append(region)
        return sorted(out, key=lambda r: r.y0)
