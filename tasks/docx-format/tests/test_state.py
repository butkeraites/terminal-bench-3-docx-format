"""Grade the produced document by looking at the rendered page.

Every assertion is arithmetic over pixels of the rendering: which colours appear,
where their connected components sit, which box contains which. Nothing judges
appearance and nothing inspects the OOXML — a document that renders correctly
passes however it was built.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from style import Profile  # noqa: E402
from visual import GREEN, ORANGE, RED, Page, Region  # noqa: E402

OUTPUT = Path("/app/output.docx")
RENDER_DIR = Path("/tmp/render")
SLACK = 10  # pixels; the two renderer versions tested agree to within 3


@pytest.fixture(scope="session")
def page() -> Page:
    if not OUTPUT.exists():
        pytest.fail("/app/output.docx was never written")
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf",
         "--outdir", str(RENDER_DIR), str(OUTPUT)],
        capture_output=True, timeout=900,
    )
    pdf = RENDER_DIR / "output.pdf"
    if not pdf.exists():
        pytest.fail(f"the document did not render: {result.stderr.decode()[:400]}")
    try:
        return Page(pdf)
    except ValueError as error:
        pytest.fail(str(error))


# --------------------------------------------------------------------------
# what the page says
# --------------------------------------------------------------------------

@pytest.mark.parametrize("phrase", [
    "Evidências de ocorrencia",
    "Usuário 123.3345",
    "Print da falha",
    "Evidência do tempo",
    "Reconhecimento de Fala (Detalhe A)",
    "hora 6pm (mostrada no Detalhe B)",
])
def test_required_text_is_present(page, phrase):
    assert phrase in page.text(), f"not on the rendered page: {phrase!r}"


def test_the_name_reaches_the_footer(page):
    footer = [t for r, t in page.text_boxes() if r.y0 > 0.92 * page.height]
    assert any("Usuário 123.3345" in t for t in footer), (
        f"the footer still carries the placeholder; it reads {footer}"
    )


def test_the_placeholders_are_gone(page):
    body = page.text()
    for leftover in ("<Nome>", "Titulo do documento", "Documento 1", "Documento 2"):
        assert leftover not in body, f"placeholder left in place: {leftover!r}"


# --------------------------------------------------------------------------
# the template's visual language, read off the template itself
#
# Nothing below is a constant chosen by hand. The same profile is extracted from
# the input template and from the output, and the two are compared. Swap the
# template and the expectations swap with it — which is the whole point, since
# the feature has to work for any template a user uploads.
# --------------------------------------------------------------------------

TEMPLATE_PDF = Path(__file__).parent / "template.pdf"


@pytest.fixture(scope="session")
def template():
    return Profile.read(Page(TEMPLATE_PDF))


@pytest.fixture(scope="session")
def produced(page):
    return Profile.read(page)


# A palette comparison was tried here and removed. Ranking colours by area picks
# up the placeholder photographs' own blues and greys — content, not identity —
# and no legitimate output reproduces the palette of pictures it was told to
# replace. Narrowing to large flat blocks did not separate them either: a laptop
# screen is large and flat. The one accent that genuinely carries the identity is
# the one the page furniture is made of, and the next test already checks it.


def test_the_page_furniture_is_placed_as_in_the_template(template, produced):
    want, got = template.furniture, produced.furniture
    assert got.left_bar is not None, "the bar down the left margin is missing"
    assert got.footer_bar is not None, "the footer bar is missing"

    faults = []
    if abs(got.left_bar.x1 - want.left_bar.x1) > 12:
        faults.append(f"left bar is {got.left_bar.width}px wide, template has {want.left_bar.width}px")
    if abs(got.left_bar.y0 - want.left_bar.y0) > 12:
        faults.append(
            f"left bar starts at y={got.left_bar.y0}, template starts at y={want.left_bar.y0}"
        )
    if abs(got.footer_bar.y0 - want.footer_bar.y0) > 12:
        faults.append(
            f"footer bar starts at y={got.footer_bar.y0}, template has y={want.footer_bar.y0}"
        )
    assert not faults, "; ".join(faults)


def test_the_left_bar_starts_below_the_banner(produced):
    """It runs from the foot of the banner to the footer, and overlaps neither."""
    bar, end = produced.furniture.left_bar, produced.furniture.banner_end
    assert bar is not None, "the bar down the left margin is missing"
    assert bar.y0 >= end - 12, (
        f"the left bar starts at y={bar.y0} and runs {end - bar.y0}px up into the "
        f"banner, which ends at y={end}"
    )
    footer = produced.furniture.footer_bar
    if footer is not None:
        gap = footer.y0 - bar.y1
        assert 0 <= gap <= 40, (
            f"there is a {gap}px gap between the foot of the left bar and the footer bar"
        )


def test_headings_are_dressed_like_the_template(template, produced):
    assert produced.headings, "no heading plates found in the output"
    assert len(produced.headings) >= len(template.headings), (
        f"the template dresses {len(template.headings)} headings, "
        f"the output has {len(produced.headings)}"
    )
    reference = template.headings[0]
    for number, heading in enumerate(produced.headings[: len(template.headings)], 1):
        assert heading.ink_is_dark == reference.ink_is_dark, (
            f"heading {number} is set in "
            f"{'light' if not heading.ink_is_dark else 'dark'} ink on its plate; "
            f"the template sets it in {'dark' if reference.ink_is_dark else 'light'}"
        )
        assert abs(heading.height - reference.height) <= 10, (
            f"heading {number}'s plate is {heading.height}px tall, "
            f"the template's is {reference.height}px"
        )
        assert abs(heading.left_inset - reference.left_inset) <= 15, (
            f"heading {number}'s plate is inset {heading.left_inset}px, "
            f"the template's is {reference.left_inset}px"
        )


def test_the_banner_survived(page):
    top = page.pixels[: int(0.06 * page.height)]
    assert float(top.std()) > 0.05, "the top of the page is flat — the banner is gone"


# --------------------------------------------------------------------------
# the two replacement images
# --------------------------------------------------------------------------

@pytest.fixture(scope="session")
def figures(page):
    found = page.body_images()
    assert len(found) >= 2, f"expected two images in the body, found {len(found)}"
    return found[:2]


@pytest.mark.parametrize("index,aspect", [(0, 262 / 178), (1, 150 / 39)])
def test_each_image_keeps_its_aspect_ratio(figures, index, aspect):
    region = figures[index]
    drawn = region.width / region.height
    assert abs(drawn - aspect) / aspect < 0.06, (
        f"image {index + 1} drawn at aspect {drawn:.3f}, the source is {aspect:.3f} — distorted"
    )


def test_a_red_rectangle_marks_a_detail_on_each_image(page, figures):
    reds = page.regions(RED)
    assert len(reds) >= 2, f"expected a red detail rectangle on each image, found {len(reds)}"
    for number, figure in enumerate(figures, 1):
        marks = [r for r in reds if figure.contains(r, SLACK)]
        assert marks, (
            f"no red rectangle lies on image {number} at {figure}; "
            f"the red rectangles are at {reds}"
        )


def test_an_orange_arrow_runs_from_each_mark_towards_its_letter(page, figures):
    oranges = page.regions(ORANGE)
    reds = page.regions(RED)
    letters = {t: r for r, t in page.text_boxes() if t in ("A", "B")}
    assert set(letters) == {"A", "B"}, f"letters A and B are not both present: {sorted(letters)}"

    for letter, figure in zip(("A", "B"), figures):
        target = letters[letter]
        mark = next((r for r in reds if figure.contains(r, SLACK)), None)
        assert mark is not None, f"no red mark on the image belonging to letter {letter}"

        # The arrow lives in the corridor between the mark and the letter.
        lo_x, hi_x = sorted((mark.centre()[0], target.centre()[0]))
        lo_y, hi_y = sorted((mark.centre()[1], target.centre()[1]))
        margin = 60
        linked = [
            o for o in oranges
            if lo_x - margin <= o.centre()[0] <= hi_x + margin
            and lo_y - margin <= o.centre()[1] <= hi_y + margin
        ]
        assert linked, (
            f"no orange arrow between the red mark {mark} and letter {letter} at {target}; "
            f"orange regions are at {oranges}"
        )


# --------------------------------------------------------------------------
# legibility — the thing the template itself gets wrong
# --------------------------------------------------------------------------

# What separates "covered" from "set alongside" is how far the figure reaches
# into the LINE, not how much area it shares. Measured on the two reference
# documents, whose overlaps have almost identical area:
#
#     laid out correctly : 285 x  6 px   wide and shallow — the text clears it
#     laid out wrongly   :  91 x 23 px   narrow and deep  — the line is eaten
#
# 1710 vs 2093 px², so any area threshold confuses them; 6 px is half a leading
# gap while 23 px is a whole glyph height. An earlier version thresholded on the
# fraction of the block and scored the broken template at 14.7% against a 15%
# limit — the defect was measured and then rounded away.
MAX_VERTICAL_BITE = 12  # pixels at 150 dpi; body text here is ~23 px tall


def test_no_body_text_is_covered_by_an_image(page, figures):
    covered = []
    for box, label in page.text_boxes():
        if box.y0 < 0.14 * page.height or box.y0 > 0.92 * page.height:
            continue  # banner and footer bands
        for figure in figures:
            ox0, oy0 = max(box.x0, figure.x0), max(box.y0, figure.y0)
            ox1, oy1 = min(box.x1, figure.x1), min(box.y1, figure.y1)
            if (ox1 - ox0) > 0 and (oy1 - oy0) > MAX_VERTICAL_BITE:
                covered.append(
                    f"{label[:44]!r} overlapped {ox1 - ox0}x{oy1 - oy0}px by {figure}"
                )
    assert not covered, (
        "an image is covering body text — the very fault the template has:\n  "
        + "\n  ".join(covered)
    )


# --------------------------------------------------------------------------
# composition — what a designer objects to after the specification is met
#
# The first agent output satisfied every requirement above and still looked
# wrong. Both faults it had are measurable, and on the two reference documents
# they separate by an order of magnitude:
#
#   frame padding, top/bottom : 20-22 px laid out well | 191-192 px laid out badly
#   letter to image, x gap    : letter within the image's span | 218 and 438 px away
# --------------------------------------------------------------------------

MAX_FRAME_PADDING = 70   # px at 150 dpi
MAX_LETTER_GAP = 90      # px from the letter to the image it annotates


def test_the_frame_hugs_the_image_it_borders(page, figures):
    """The green rule is the image's border, not a box it floats inside."""
    frames = [g for g in page.regions(GREEN) if g.contains(figures[0], 60)]
    assert frames, "the green border around the first image is gone"
    frame = min(frames, key=lambda g: g.width * g.height)
    figure = figures[0]
    padding = {
        "left": figure.x0 - frame.x0,
        "right": frame.x1 - figure.x1,
        "top": figure.y0 - frame.y0,
        "bottom": frame.y1 - figure.y1,
    }
    loose = {k: v for k, v in padding.items() if v > MAX_FRAME_PADDING}
    assert not loose, (
        f"the image does not fill its border — {loose} px of white space "
        f"(image {figure}, border {frame})"
    )


@pytest.mark.parametrize("letter_name,index", [("A", 0), ("B", 1)])
def test_each_letter_sits_beside_the_image_it_labels(page, figures, letter_name, index):
    letters = {t: r for r, t in page.text_boxes() if t in ("A", "B")}
    assert letter_name in letters, f"letter {letter_name} is not on the page"
    letter, figure = letters[letter_name], figures[index]
    gap_x = max(0, letter.x0 - figure.x1, figure.x0 - letter.x1)
    gap_y = max(0, letter.y0 - figure.y1, figure.y0 - letter.y1)
    assert gap_x <= MAX_LETTER_GAP and gap_y <= MAX_LETTER_GAP, (
        f"letter {letter_name} at {letter} is {gap_x}px horizontally and {gap_y}px "
        f"vertically from the image it labels at {figure} — it reads as unrelated"
    )


def test_the_second_figure_precedes_the_caption_that_refers_to_it(page, figures):
    """A figure introduced by its caption has to appear first, or the reader
    meets the reference before the thing referred to.

    Measured on the references: -75 px laid out well, +96 px laid out badly.
    """
    caption = next((r for r, t in page.text_boxes() if "Detalhe B" in t), None)
    assert caption is not None, "the caption referring to Detalhe B is missing"
    figure = figures[1]
    assert figure.y0 < caption.y0, (
        f"the second figure starts at y={figure.y0} but its caption starts at "
        f"y={caption.y0} — the image is placed after the text that refers to it"
    )


# --------------------------------------------------------------------------
# ambiguity — the document must determine its own appearance
#
# A .docx may leave a property unstated and let whatever opens it decide. Such a
# file is correct on the machine that made it and can be wrong anywhere else.
# One output here renders its heading ink dark under LibreOffice 7.4 and light
# under 25.8, and puts the left bar 20px further up in the second — same bytes,
# two appearances. The reference document renders identically under both.
#
# Two markup-level proxies were tried and discarded. The first asked whether the
# heading run pins its own colour: the reference fails that, because it inherits
# from a style that is itself explicit. The second perturbed the document
# defaults and measured what moved: the reference moves too, by 0.29%, because
# inheriting body-text colour from the defaults is normal and every engine
# agrees about it. Neither proxy separates "inherits" from "inherits something
# renderers disagree about", and only the second is a defect.
#
# So both engines are installed and both are asked.
# --------------------------------------------------------------------------

SECOND_ENGINE = "soffice2"


@pytest.fixture(scope="session")
def second_rendering():
    """The same document through an independently built, much later engine."""
    outdir = RENDER_DIR / "second"
    outdir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [SECOND_ENGINE, "--headless", "--convert-to", "pdf",
         "-env:UserInstallation=file:///tmp/lo2profile",
         "--outdir", str(outdir), str(OUTPUT)],
        capture_output=True, timeout=900,
    )
    pdf = outdir / "output.pdf"
    if not pdf.exists():
        pytest.fail(f"the second engine did not render: {result.stderr.decode()[:400]}")
    return Page(pdf)


def test_both_engines_dress_the_headings_alike(page, second_rendering):
    """Heading ink that differs between engines is ink the document never chose."""
    first = Profile.read(page).headings
    second = Profile.read(second_rendering).headings
    assert first and second, "no heading plates found in one of the renderings"

    for number, (a, b) in enumerate(zip(first, second), 1):
        assert a.ink_is_dark == b.ink_is_dark, (
            f"heading {number} is set in {'dark' if a.ink_is_dark else 'light'} ink "
            f"by one engine and {'dark' if b.ink_is_dark else 'light'} by another — "
            f"the document does not state the colour, so each reader gets its own"
        )


def test_both_engines_place_the_furniture_alike(page, second_rendering):
    """Page furniture that moves between engines is furniture placed by chance."""
    first = Profile.read(page).furniture
    second = Profile.read(second_rendering).furniture
    # Only the left bar's top edge. It butts against the banner, so a
    # disagreement there is visible. The footer bar's own position drifts ~12px
    # between these engines even for the reference document — they compute the
    # usable body height differently — and that drift is hidden under the bar
    # itself. Asserting on it would fail correct documents.
    for name in ("left_bar",):
        a, b = getattr(first, name), getattr(second, name)
        assert a is not None and b is not None, f"{name} was not found in one rendering"
        # Only the edge that has a visible relationship is compared. The left
        # bar's top butts against the banner and any disagreement there shows;
        # its foot runs under the footer bar, and the two engines put it at
        # y=1655 and y=1697 even for the reference, because they compute the
        # usable body height differently. That difference is invisible and is
        # not the document's fault.
        assert abs(a.y0 - b.y0) <= 8, (
            f"{name} starts at y={a.y0} under one engine and y={b.y0} under "
            f"another — where it begins is not fixed by the document"
        )
