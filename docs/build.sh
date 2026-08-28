#!/bin/bash
# Regenerate docs/design.pdf from docs/design.html.
# Chromium's headless print path is the only PDF renderer available here; it
# keeps the print CSS (A4, page-break-inside rules) that the layout relies on.
set -euo pipefail
cd "$(dirname "$0")"
chromium --headless --disable-gpu --no-sandbox --no-pdf-header-footer \
         --print-to-pdf=design.pdf design.html
echo "-> $(pwd)/design.pdf"
