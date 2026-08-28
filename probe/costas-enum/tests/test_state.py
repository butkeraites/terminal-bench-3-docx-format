"""Grade an exhaustive enumeration of the Costas arrays of order 19.

Validity is checked from the definition, independently of how the arrays were
produced. Completeness is checked against a count computed offline by an
independent exhaustive search.
"""
from pathlib import Path
import pytest

N = 19
OUTPUT = Path("/app/costas19.txt")
GROUND_TRUTH = Path("/tests/ground_truth.txt")


def is_costas(perm):
    if sorted(perm) != list(range(1, N + 1)):
        return False
    for h in range(1, N):
        seen = set()
        for i in range(N - h):
            d = perm[i + h] - perm[i]
            if d in seen:
                return False
            seen.add(d)
    return True


@pytest.fixture(scope="session")
def arrays():
    if not OUTPUT.exists():
        pytest.fail(f"{OUTPUT} was never written")
    out = []
    for lineno, line in enumerate(OUTPUT.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(tuple(int(v) for v in line.split()))
        except ValueError:
            pytest.fail(f"line {lineno} is not a list of integers: {line[:60]!r}")
    return out


def test_every_array_is_a_costas_array(arrays):
    bad = [i for i, a in enumerate(arrays) if not is_costas(a)]
    assert not bad, f"{len(bad)} of {len(arrays)} lines are not Costas arrays of order {N}"


def test_no_array_appears_twice(arrays):
    assert len(set(arrays)) == len(arrays), (
        f"{len(arrays) - len(set(arrays))} duplicate lines"
    )


def test_the_enumeration_is_complete(arrays):
    expected = int(GROUND_TRUTH.read_text().strip())
    assert len(set(arrays)) == expected, (
        f"found {len(set(arrays))} distinct arrays, expected {expected}"
    )
