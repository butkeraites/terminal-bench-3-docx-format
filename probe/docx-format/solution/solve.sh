#!/bin/bash
# Oracle: the reference document the author produced by hand. Never visible to
# the agent — harbor mounts solution/ only for the oracle agent.
set -euo pipefail
cp /solution/expected.docx /app/output.docx
