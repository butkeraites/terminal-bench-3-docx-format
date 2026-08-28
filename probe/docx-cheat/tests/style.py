"""A style profile read off a rendered page.

The point of the task is that the agent infers the template's visual language
from a PDF and reapplies it to new content. So the verifier must not carry that
language as constants written by hand — it reads the same profile from the
template and from the output and compares the two. Change the template and the
expectations change with it, which is what makes the check transfer to any
template a user uploads.

Only content-independent properties are compared. The output has different text
and different pictures, so its element positions cannot match the template's;
what must match is the treatment: which accent colours, how the page furniture
is laid out, how a heading is dressed, how a figure is framed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from visual import Page, Region


def dominant_accents(page: Page, top: int = 4, min_area: int = 3000) -> list:
    """The colours the page's *identity* is made of.

    Restricted to large flat regions. A first version simply ranked colours by
    pixel count and picked up the blues and greys of the placeholder photographs
    — content, not identity — so it demanded that every output reproduce the
    palette of pictures it had just been told to replace. Chrome is flat and
    wide; photographs are neither.
    """
    flat = page.pixels.reshape(-1, 3)
    luminance = flat.mean(axis=1)
    saturation = flat.max(axis=1) - flat.min(axis=1)
    keep = (luminance > 0.1) & (luminance < 0.95) & (saturation > 0.15)
    if not keep.any():
        return []
    quantised = np.round(flat[keep] * 12).astype(np.int16)
    keys, counts = np.unique(quantised, axis=0, return_counts=True)

    out = []
    for index in np.argsort(-counts):
        colour = tuple(float(v) / 12.0 for v in keys[index])
        # Keep it only if it forms one big solid block somewhere on the page.
        blocks = page.regions(colour, min_pixels=min_area)
        if blocks and blocks[0].pixels >= min_area:
            out.append(colour)
        if len(out) >= top:
            break
    return out


def banner_depth(page: Page) -> int:
    """Where the top banner ends: the first row whose middle is near-white."""
    middle = page.pixels[:, int(0.45 * page.width): int(0.55 * page.width)].mean(axis=(1, 2))
    below_top = np.where(middle[5:] > 0.93)[0]
    return int(below_top[0] + 5) if len(below_top) else 0


@dataclass(frozen=True, slots=True)
class Furniture:
    left_bar: Region | None
    footer_bar: Region | None
    banner_end: int


def furniture(page: Page, accent: tuple[float, float, float]) -> Furniture:
    """Locate the left bar and the footer bar by where their pixels are.

    Not by connected component: whether the two touch at the corner — and so
    arrive as one L-shaped blob or as two — varies by renderer. It did here,
    which made the footer vanish under one engine and look like a document
    defect. Column and row profiles of the accent mask do not care.
    """
    mask = np.all(np.abs(page.pixels - np.array(accent)) <= 0.10, axis=-1)
    rows = mask.sum(axis=1)

    # The footer first. The bar is then measured only above it: the two are the
    # same colour and meet at the corner, so a bar found without that limit runs
    # straight down through the footer and its foot lands below the footer's top.
    bottom = int(0.88 * page.height)
    foot_rows = np.where(rows[bottom:] > 0.4 * page.width)[0]
    footer_bar = None
    if len(foot_rows):
        y0, y1 = bottom + int(foot_rows.min()), bottom + int(foot_rows.max())
        band = mask[y0:y1 + 1]
        foot_cols = np.where(band.sum(axis=0) > 0.5 * (y1 - y0 + 1))[0]
        if len(foot_cols):
            footer_bar = Region(
                int(foot_cols.min()), y0, int(foot_cols.max()), y1, int(band.sum())
            )

    ceiling = footer_bar.y0 if footer_bar else page.height
    left_strip = mask[:ceiling, : int(0.12 * page.width)]
    # The bar is ~48 px inside a ~149 px strip, so a fraction-of-strip threshold
    # misses it entirely; count pixels.
    bar_rows = np.where(left_strip.sum(axis=1) > 15)[0]
    left_bar = None
    if len(bar_rows) > 0.3 * page.height:
        bar_cols = np.where(left_strip.sum(axis=0) > 0.3 * len(bar_rows))[0]
        if not len(bar_cols):
            bar_cols = np.array([0])
        left_bar = Region(
            int(bar_cols.min()), int(bar_rows.min()),
            int(bar_cols.max()), int(bar_rows.max()), int(left_strip.sum()),
        )

    return Furniture(left_bar=left_bar, footer_bar=footer_bar,
                     banner_end=banner_depth(page))


@dataclass(frozen=True, slots=True)
class HeadingStyle:
    height: int
    left_inset: int
    ink_is_dark: bool
    contrast: float


def heading_styles(page: Page, accent: tuple[float, float, float]) -> list[HeadingStyle]:
    """How a numbered heading is dressed: its plate, and the ink on it.

    The whole plate is sampled, not an inset crop. Diagnosing this by eye caught
    a bug where a four-pixel inset skipped the glyph band entirely on a 32 px
    plate and reported white text as black.
    """
    plates = [r for r in page.regions(accent) if 12 < r.height < 70 and 50 < r.width < 520]
    out = []
    for plate in sorted(plates, key=lambda r: r.y0):
        patch = page.pixels[plate.y0:plate.y1, plate.x0:plate.x1]
        if patch.size == 0:
            continue
        luminance = patch.mean(axis=-1)
        dark = int((luminance < 0.35).sum())
        light = int((luminance > 0.85).sum())
        if dark + light < 30:
            continue  # a plain bar, not a heading plate
        out.append(HeadingStyle(
            height=plate.height,
            left_inset=plate.x0,
            ink_is_dark=dark > light,
            contrast=abs(float(luminance.max()) - float(luminance.min())),
        ))
    return out


@dataclass(frozen=True, slots=True)
class Profile:
    accents: list = field(default_factory=list)
    furniture: Furniture | None = None
    headings: list = field(default_factory=list)

    @classmethod
    def read(cls, page: Page) -> "Profile":
        accents = dominant_accents(page)
        chrome = accents[0] if accents else (0, 0, 0)
        return cls(
            accents=accents,
            furniture=furniture(page, chrome),
            headings=heading_styles(page, chrome),
        )
