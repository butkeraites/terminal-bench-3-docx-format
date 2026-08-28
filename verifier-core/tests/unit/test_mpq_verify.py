"""The gmpy2 exact backend must be the same function as the reference.

It exists only as a benchmark baseline: it is the fastest exact route an agent
with open internet will reach for, so the design window has to be measured
against it rather than against the standard library. A baseline that quietly
skips a check would make every timing meaningless, which is exactly the mistake
this test exists to prevent.
"""

import pytest

from certverify.application.stream import StreamConfig, generate_run
from certverify.application.verify import verify

gmpy2 = pytest.importorskip("gmpy2")

from certverify.infrastructure.mpq_verify import verify_mpq  # noqa: E402

SECRET = b"mpq-test-secret"


@pytest.mark.parametrize("run", [1, 2, 3])
def test_mpq_backend_matches_the_reference_on_every_submission(run):
    config = StreamConfig(count=120, num_vars=10, num_constraints=7)

    for submission in generate_run(SECRET, run, config):
        expected = verify(submission.instance, submission.certificate)
        actual = verify_mpq(
            submission.payload["instance"], submission.payload["certificate"]
        )

        assert actual == expected, (
            f"{submission.submission_id} ({submission.kind.name}): "
            f"mpq {actual} vs reference {expected}"
        )


def test_mpq_backend_matches_on_larger_instances():
    config = StreamConfig(count=30, num_vars=60, num_constraints=45)

    for submission in generate_run(SECRET, 4, config):
        expected = verify(submission.instance, submission.certificate)
        actual = verify_mpq(
            submission.payload["instance"], submission.payload["certificate"]
        )

        assert actual == expected, submission.kind.name


def test_mpq_backend_handles_malformed_input_without_raising():
    verdict = verify_mpq(
        {"objective": ["nonsense"], "matrix": [["1"]], "rhs": ["0"],
         "upper_bounds": ["1"], "integer_indices": []},
        {"primal": ["0"], "dual": ["0"], "bound_dual": ["0"],
         "claimed_objective": "0", "claimed_bound": "0", "claims_optimal": False},
    )

    assert not verdict.accepted
