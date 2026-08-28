"""Float screen with a certified error bound, escalating lazily to exact.

Neither pure strategy works: float alone gets adversarial verdicts wrong, exact
alone is two orders of magnitude too slow. The hybrid decides in floating point
whenever a certified error bound proves the decision cannot flip, and otherwise
falls back — parsing to exact rationals only the slice the ambiguous check
needs, because parsing dominates the exact path (68% of it at 400x300).

Correctness bar: identical verdicts to `verify()` on every submission. Not
"almost always" — the whole task exists because almost always is worthless.
"""

import pytest

from certverify.application.hybrid import (
    CertifiedSum,
    certified_dot,
    verify_hybrid,
)
from certverify.application.stream import StreamConfig, generate_run
from certverify.application.verify import verify
from certverify.domain.milp import Certificate, MilpInstance, Rejection

SECRET = b"hybrid-test-secret"


# --------------------------------------------------------------------------
# the certified bound
# --------------------------------------------------------------------------


def test_certified_sum_brackets_the_exact_value():
    result = certified_dot(["0.1", "0.2", "0.3"], ["1", "1", "1"])

    assert result.low <= 0.6 <= result.high


def test_the_bracket_is_tight_on_well_conditioned_input():
    """Small integers are exact in float64; the interval should be a point."""
    result = certified_dot(["1", "2", "3"], ["4", "5", "6"])

    assert result.low <= 32.0 <= result.high
    assert result.high - result.low < 1e-9


def test_the_bracket_widens_under_cancellation():
    """1e16 + 1 - 1e16 + 1 destroys the small terms; the bound must admit it."""
    result = certified_dot(["1e16", "1", "-1e16", "1"], ["1", "1", "1", "1"])

    assert result.low <= 2.0 <= result.high
    assert result.high - result.low > 1.0


def test_a_decided_comparison_reports_certainty():
    result = certified_dot(["1", "1"], ["1", "1"])

    assert result.definitely_at_least(1.5)
    assert not result.definitely_below(1.5)


def test_an_undecidable_comparison_reports_uncertainty():
    result = certified_dot(["1e16", "1", "-1e16", "1"], ["1", "1", "1", "1"])

    assert not result.definitely_at_least(2.0)
    assert not result.definitely_below(2.0)


def test_fraction_syntax_is_handled_on_the_fast_path():
    result = certified_dot(["1/4", "1/4"], ["1", "1"])

    assert result.low <= 0.5 <= result.high


# --------------------------------------------------------------------------
# end-to-end equivalence with the exact specification
# --------------------------------------------------------------------------


def _payloads(count: int, n: int, m: int, run: int = 1):
    config = StreamConfig(count=count, num_vars=n, num_constraints=m)
    return generate_run(SECRET, run, config)


@pytest.mark.parametrize("run", [1, 2, 3])
def test_hybrid_matches_exact_on_every_submission(run):
    for submission in _payloads(120, 10, 7, run=run):
        expected = verify(submission.instance, submission.certificate)
        actual = verify_hybrid(
            submission.payload["instance"], submission.payload["certificate"]
        )

        assert actual == expected, (
            f"{submission.submission_id} ({submission.kind.name}): "
            f"hybrid {actual} vs exact {expected}"
        )


def test_hybrid_matches_exact_on_larger_instances():
    for submission in _payloads(40, 60, 45):
        expected = verify(submission.instance, submission.certificate)
        actual = verify_hybrid(
            submission.payload["instance"], submission.payload["certificate"]
        )

        assert actual == expected, submission.kind.name


def test_hybrid_gets_the_adversarial_submissions_right():
    """These are exactly the ones a float-only verifier gets wrong."""
    adversarial = [s for s in _payloads(300, 12, 8) if s.adversarial]
    assert adversarial

    for submission in adversarial:
        expected = verify(submission.instance, submission.certificate)
        actual = verify_hybrid(
            submission.payload["instance"], submission.payload["certificate"]
        )

        assert actual == expected, submission.kind.name


# --------------------------------------------------------------------------
# the specific traps
# --------------------------------------------------------------------------


def _verdict(instance: dict, certificate: dict):
    return verify_hybrid(instance, certificate)


def test_violation_of_one_part_in_a_billion_is_rejected():
    verdict = _verdict(
        {"objective": ["1", "1"], "matrix": [["1", "1"]], "rhs": ["1"],
         "upper_bounds": ["10", "10"], "integer_indices": []},
        {"primal": ["0.999999999", "0"], "dual": ["0"], "bound_dual": ["0", "0"],
         "claimed_objective": "0.999999999", "claimed_bound": "0",
         "claims_optimal": False},
    )
    assert verdict.reason is Rejection.PRIMAL_INFEASIBLE


def test_cancellation_certificate_that_only_exact_arithmetic_accepts():
    verdict = _verdict(
        {"objective": ["1e16", "1", "-1e16", "1"], "matrix": [["0", "0", "0", "0"]],
         "rhs": ["0"], "upper_bounds": ["10", "10", "10", "10"],
         "integer_indices": [0, 1, 2, 3]},
        {"primal": ["1", "1", "1", "1"], "dual": ["0"],
         "bound_dual": ["0", "0", "1e16", "0"], "claimed_objective": "2",
         "claimed_bound": "-1e17", "claims_optimal": False},
    )
    assert verdict.accepted


def test_cancellation_certificate_that_only_float_accepts_is_rejected():
    verdict = _verdict(
        {"objective": ["1e16", "1", "-1e16", "1"], "matrix": [["0", "0", "0", "0"]],
         "rhs": ["0"], "upper_bounds": ["10", "10", "10", "10"],
         "integer_indices": [0, 1, 2, 3]},
        {"primal": ["1", "1", "1", "1"], "dual": ["0"],
         "bound_dual": ["0", "0", "1e16", "0"], "claimed_objective": "1",
         "claimed_bound": "-1e17", "claims_optimal": False},
    )
    assert verdict.reason is Rejection.OBJECTIVE_MISMATCH


def test_integrality_off_by_a_nanounit_is_rejected():
    verdict = _verdict(
        {"objective": ["1", "1"], "matrix": [["1", "1"]], "rhs": ["1"],
         "upper_bounds": ["10", "10"], "integer_indices": [0, 1]},
        {"primal": ["1.000000001", "0"], "dual": ["0"], "bound_dual": ["0", "0"],
         "claimed_objective": "1.000000001", "claimed_bound": "0",
         "claims_optimal": False},
    )
    assert verdict.reason is Rejection.INTEGRALITY_VIOLATED


def test_malformed_input_is_rejected_rather_than_raising():
    verdict = _verdict(
        {"objective": ["not-a-number"], "matrix": [["1"]], "rhs": ["0"],
         "upper_bounds": ["1"], "integer_indices": []},
        {"primal": ["0"], "dual": ["0"], "bound_dual": ["0"],
         "claimed_objective": "0", "claimed_bound": "0", "claims_optimal": False},
    )
    assert not verdict.accepted
