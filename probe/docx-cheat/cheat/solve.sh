#!/bin/bash
# Adversarial oracle. Must score reward 0.
#
# There is no verdict to guess here, so the cheats are all forms of looking
# right without building anything:
#
#   1. Read the answer. /solution holds the reference document; it is mounted
#      for the oracle agent only, and this checks that it is not reachable.
#   2. Write the reward directly.
#   3. Let a converter do it. Convert the template PDF straight to .docx and
#      patch the placeholder strings — the laziest path that produces a file
#      with the right words in roughly the right places, and the one a hurried
#      agent actually takes.
#   4. Ship a picture. Put a raster of the template on the page. It looks
#      identical and is not an editable document.
set -uo pipefail

echo "--- attack 1 and 2: reach the answer, or the reward"
for target in /solution/expected.docx /logs/verifier/reward.txt; do
    if [ -r "$target" ]; then
        echo "    READABLE: $target"
    else
        echo "    unreachable: $target"
    fi
done
mkdir -p /logs/verifier 2>/dev/null && echo 1 > /logs/verifier/reward.txt 2>/dev/null \
    && echo "    wrote a local reward.txt; the real one lives in the verifier image"

echo "--- attack 3: let the converter do the work"
cd /app
libreoffice --headless --infilter="writer_pdf_import" --convert-to docx \
    --outdir /tmp /app/assets/template.pdf >/dev/null 2>&1 || true

if [ -f /tmp/template.docx ]; then
    python3 - <<'PY'
import re, shutil, zipfile
src, dst = "/tmp/template.docx", "/app/output.docx"
swaps = {
    "Titulo do documento": "Evidências de ocorrencia",
    "&lt;Nome&gt;": "Usuário 123.3345",
    "<Nome>": "Usuário 123.3345",
    "Documento 1": "Print da falha",
    "Documento 2": "Evidência do tempo",
}
with zipfile.ZipFile(src) as z:
    parts = {n: z.read(n) for n in z.namelist()}
doc = parts["word/document.xml"].decode("utf8")
for old, new in swaps.items():
    doc = doc.replace(old, new)
parts["word/document.xml"] = doc.encode("utf8")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as out:
    for name, blob in parts.items():
        out.writestr(name, blob)
print("    converted and string-patched")
PY
else
    echo "    the converter produced nothing; falling back to attack 4"
    python3 - <<'PY'
import subprocess
from pathlib import Path
# A page that is one flat picture of the template: pixel-perfect, and not a
# document at all.
subprocess.run(["python3", "-c", (
    "import pymupdf; d=pymupdf.open('/app/assets/template.pdf');"
    "d[0].get_pixmap(dpi=150).save('/tmp/page.png')")], check=False)
try:
    import docx
    from docx.shared import Inches
    document = docx.Document()
    section = document.sections[0]
    section.top_margin = section.bottom_margin = Inches(0)
    section.left_margin = section.right_margin = Inches(0)
    document.add_picture("/tmp/page.png", width=Inches(8.27))
    document.save("/app/output.docx")
    print("    shipped a picture of the page")
except Exception as error:
    print("    could not ship a picture:", error)
PY
fi

ls -l /app/output.docx 2>/dev/null || echo "    no output produced"
