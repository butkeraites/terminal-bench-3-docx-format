"""The vendored copies of certverify must not drift from the source.

A task directory has to be self-contained, so the package is copied into the
judge and verifier build contexts. Copies rot; this fails when they do.
"""

import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "verifier-core" / "src" / "certverify"
COPIES = (
    ROOT / "tasks/certificate-verifier-slo/environment/judge/_core/certverify",
    ROOT / "tasks/certificate-verifier-slo/tests/_core/certverify",
)


def _fingerprint(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*.py"))
        if "__pycache__" not in p.parts
    }


@pytest.mark.parametrize("copy", COPIES, ids=lambda p: p.parts[-3])
def test_vendored_copy_matches_the_source(copy):
    assert copy.is_dir(), "missing vendored copy: run scripts/sync_core.sh"
    assert _fingerprint(copy) == _fingerprint(SOURCE), (
        "vendored certverify has drifted; run scripts/sync_core.sh"
    )
