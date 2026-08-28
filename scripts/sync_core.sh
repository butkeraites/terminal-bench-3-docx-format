#!/bin/bash
# Vendor the executable specification into the images that need it.
#
# A Terminal-Bench task directory must be self-contained, so `certverify` is
# copied into the judge and verifier build contexts rather than installed from
# outside the task. verifier-core/ stays the single source of truth, and
# tests/unit/test_vendored_core.py fails if a copy drifts from it.
#
# The agent image never receives this package: environment/Dockerfile copies
# only service/ and public/. certverify holds the ground-truth verdict logic,
# so that boundary is the whole game.
set -euo pipefail
cd "$(dirname "$0")/.."

SOURCE="verifier-core/src/certverify"
TASK="tasks/certificate-verifier-slo"

for destination in "$TASK/environment/judge/_core" "$TASK/tests/_core"; do
    mkdir -p "$destination"
    rm -rf "${destination:?}/certverify"
    cp -r "$SOURCE" "$destination/certverify"
    # The graded parameters and the HMAC secret must be byte-identical in both
    # images: the verifier regenerates the graded stream from them, so any
    # divergence would silently grade a different run than the one that was sent.
    cp "$TASK/graded.py" "$destination/graded.py"
    find "$destination" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
    echo "  -> $destination/{certverify,graded.py}"
done
