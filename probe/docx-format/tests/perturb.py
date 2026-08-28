"""Ask whether a document determines its own appearance.

A .docx may leave a property unstated and inherit it — from the document
defaults, from the theme, from whatever the renderer decides. Such a document
looks correct wherever it was made and can look different anywhere else; one
output here rendered its heading ink black under LibreOffice 7.4 and white under
26.2, from the same bytes.

Rather than install a second engine and compare, perturb what the document would
inherit *from* and re-render with the same engine. Anything that moves was not
the document's own: it was borrowed. Anything pinned is unmoved.
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

# A colour nothing would choose on purpose, so any appearance of it is inherited.
LOUD = "FF00FF"

DEFAULTS_WITH_COLOUR = re.compile(
    r"(<w:docDefaults>.*?<w:rPr>)(.*?)(</w:rPr>)", re.S
)


def perturbed_copy(source: Path, destination: Path) -> bool:
    """Rewrite the document's inherited defaults. True if anything was changed."""
    shutil.copy(source, destination)
    with zipfile.ZipFile(source) as bundle:
        names = bundle.namelist()
        payload = {name: bundle.read(name) for name in names}

    if "word/styles.xml" not in payload:
        return False

    styles = payload["word/styles.xml"].decode("utf8")
    changed = False

    def rewrite(match):
        nonlocal changed
        head, body, tail = match.groups()
        body = re.sub(r'<w:color\s+w:val="[^"]*"\s*/>', "", body)
        changed = True
        return f'{head}<w:color w:val="{LOUD}"/>{body}{tail}'

    patched = DEFAULTS_WITH_COLOUR.sub(rewrite, styles, count=1)
    if not changed:
        # No run defaults at all: introduce them, so inheritance has a source.
        patched = styles.replace(
            "<w:docDefaults>",
            f'<w:docDefaults><w:rPrDefault><w:rPr>'
            f'<w:color w:val="{LOUD}"/></w:rPr></w:rPrDefault>',
            1,
        )
        changed = patched != styles

    if not changed:
        return False

    payload["word/styles.xml"] = patched.encode("utf8")
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as out:
        for name in names:
            out.writestr(name, payload[name])
    return True
