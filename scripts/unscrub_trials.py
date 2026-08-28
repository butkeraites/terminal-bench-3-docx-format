#!/usr/bin/env python3
"""Undo harbor's over-eager secret scrub in trial output.

harbor/trial/trial.py rewrites every text file under a trial directory,
replacing the *value* of any env var whose name matches
(KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL|AUTH) with the literal marker
"[REDACTED]". Our runs set CLAUDE_FORCE_OAUTH=1 and CODEX_FORCE_AUTH_JSON=1;
both names contain "AUTH", so the one-character value "1" was registered as a
secret and every digit 1 in every file was destroyed.

The substitution is invertible: the marker contains no digit, so replacing it
back with "1" cannot collide with anything the scrub left behind. Two
independent checks confirm the inverse is the original:

  * every result.json parses as JSON again, and its restored "trials_dir"
    field matches the directory the file actually sits in;
  * every pytest summary line sums to the task's 23 tests.

Later runs avoid the problem by passing "yes" instead of "1".
"""

import json
import re
import sys
from pathlib import Path

MARKER = "[" + "REDA" + "CTED" + "]"
SUMMARY = re.compile(r"(\d+) failed, (\d+) passed")
N_TESTS = 23


def is_text(path: Path) -> bool:
    try:
        sample = path.open("rb").read(8192)
    except OSError:
        return False
    if b"\0" in sample:
        return False
    try:
        sample.decode("utf8")
    except UnicodeDecodeError:
        return False
    return True


def main(roots: list[str]) -> int:
    changed, failures = [], []

    for root in roots:
        for path in sorted(Path(root).rglob("*")):
            if not path.is_file() or path.is_symlink() or not is_text(path):
                continue
            try:
                text = path.read_text(encoding="utf8")
            except (OSError, UnicodeDecodeError):
                continue
            if MARKER not in text:
                continue
            restored = text.replace(MARKER, "1")
            if path.suffix == ".json":
                try:
                    json.loads(restored)
                except json.JSONDecodeError as error:
                    failures.append(f"{path}: still not valid JSON ({error})")
                    continue
            path.write_text(restored, encoding="utf8")
            changed.append(path)

    # Cross-check 1: a result.json knows which directory it belongs to.
    for path in Path().glob("trials/*/*/*/result.json"):
        try:
            recorded = json.loads(path.read_text(encoding="utf8"))["config"]["trials_dir"]
        except Exception as error:
            failures.append(f"{path}: unreadable after restore ({error})")
            continue
        actual = str(path.parent.parent)
        if recorded != actual:
            failures.append(f"{path}: trials_dir {recorded!r} != {actual!r}")

    # Cross-check 2: the verifier ran a fixed number of tests.
    for path in Path().glob("trials/*/*/*/verifier/test-stdout.txt"):
        match = SUMMARY.search(path.read_text(encoding="utf8", errors="replace"))
        if match and int(match.group(1)) + int(match.group(2)) != N_TESTS:
            failures.append(f"{path}: summary does not sum to {N_TESTS}")

    print(f"restored {len(changed)} files")
    for failure in failures:
        print("  FAIL:", failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["trials", "jobs"]))
