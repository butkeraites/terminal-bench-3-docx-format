"""Verdict logic — the specification of correctness for the whole task.

Problem family:

    minimise    c'x
    subject to  Ax >= b
                0 <= x <= u
                x_j integer for j in I

Certificate: a primal point x, dual multipliers y for the rows, and w for the
upper bounds. Weak duality gives the bound b'y - u'w <= c'x for any dual
feasible (y, w), so the pair certifies both a solution and a lower bound.

A submission is ACCEPTED iff every condition below holds in EXACT arithmetic.
Rejection reasons are ordered: when several conditions fail, the first in this
list is reported, so the verdict is a deterministic function of the input.
"""

from fractions import Fraction

import pytest

from certverify.application.verify import verify
from certverify.domain.milp import Certificate, MilpInstance, Rejection


# --------------------------------------------------------------------------
# fixtures: a tiny MILP whose optimum is known by hand
#
#   min x0 + x1   s.t.  x0 + x1 >= 1,  0 <= x <= 10,  x0, x1 integer
#   optimum 1 at x = (1, 0); dual y = 1, w = 0 gives bound 1
# --------------------------------------------------------------------------


def _instance(**overrides) -> MilpInstance:
    payload = {
        "objective": ["1", "1"],
        "matrix": [["1", "1"]],
        "rhs": ["1"],
        "upper_bounds": ["10", "10"],
        "integer_indices": [0, 1],
    }
    payload.update(overrides)
    return MilpInstance.from_payload(payload)


def _certificate(**overrides) -> Certificate:
    payload = {
        "primal": ["1", "0"],
        "dual": ["1"],
        "bound_dual": ["0", "0"],
        "claimed_objective": "1",
        "claimed_bound": "1",
        "claims_optimal": True,
    }
    payload.update(overrides)
    return Certificate.from_payload(payload)


# --------------------------------------------------------------------------
# the happy path
# --------------------------------------------------------------------------


def test_a_correct_optimality_certificate_is_accepted():
    verdict = verify(_instance(), _certificate())

    assert verdict.accepted
    assert verdict.reason is None


def test_a_feasible_solution_without_an_optimality_claim_is_accepted():
    """A weak but honest bound is fine as long as nothing is misclaimed."""
    verdict = verify(
        _instance(),
        _certificate(
            primal=["5", "5"],
            claimed_objective="10",
            dual=["0"],
            claimed_bound="0",
            claims_optimal=False,
        ),
    )

    assert verdict.accepted


# --------------------------------------------------------------------------
# each rejection reason, in isolation
# --------------------------------------------------------------------------


def test_dimension_mismatch_is_rejected():
    verdict = verify(_instance(), _certificate(primal=["1", "0", "0"]))
    assert verdict.reason is Rejection.DIMENSION_MISMATCH


def test_primal_infeasibility_is_rejected():
    """x = (0, 0) violates x0 + x1 >= 1."""
    verdict = verify(
        _instance(),
        _certificate(primal=["0", "0"], claimed_objective="0", claims_optimal=False),
    )
    assert verdict.reason is Rejection.PRIMAL_INFEASIBLE


def test_exceeding_an_upper_bound_is_rejected():
    verdict = verify(
        _instance(),
        _certificate(primal=["11", "0"], claimed_objective="11", claims_optimal=False),
    )
    assert verdict.reason is Rejection.PRIMAL_INFEASIBLE


def test_negative_variable_is_rejected():
    verdict = verify(
        _instance(),
        _certificate(primal=["-1", "2"], claimed_objective="1"),
    )
    assert verdict.reason is Rejection.PRIMAL_INFEASIBLE


def test_fractional_value_on_an_integer_variable_is_rejected():
    verdict = verify(
        _instance(),
        _certificate(
            primal=["0.5", "0.5"], claimed_objective="1", claims_optimal=True
        ),
    )
    assert verdict.reason is Rejection.INTEGRALITY_VIOLATED


def test_continuous_variables_may_be_fractional():
    verdict = verify(
        _instance(integer_indices=[]),
        _certificate(primal=["0.5", "0.5"], claimed_objective="1"),
    )
    assert verdict.accepted


def test_objective_mismatch_is_rejected():
    verdict = verify(_instance(), _certificate(claimed_objective="0.9"))
    assert verdict.reason is Rejection.OBJECTIVE_MISMATCH


def test_negative_row_dual_is_rejected():
    verdict = verify(
        _instance(), _certificate(dual=["-1"], claimed_bound="-1", claims_optimal=False)
    )
    assert verdict.reason is Rejection.DUAL_INFEASIBLE


def test_dual_violating_the_reduced_cost_condition_is_rejected():
    """y = 2 gives A'y = (2, 2), which exceeds c = (1, 1)."""
    verdict = verify(
        _instance(), _certificate(dual=["2"], claimed_bound="2", claims_optimal=False)
    )
    assert verdict.reason is Rejection.DUAL_INFEASIBLE


def test_bound_mismatch_is_rejected():
    verdict = verify(_instance(), _certificate(claimed_bound="0.5", claims_optimal=False))
    assert verdict.reason is Rejection.BOUND_MISMATCH


def test_unsupported_optimality_claim_is_rejected():
    """Objective 1 with an honest bound of 0 does not prove optimality."""
    verdict = verify(
        _instance(),
        _certificate(dual=["0"], claimed_bound="0", claims_optimal=True),
    )
    assert verdict.reason is Rejection.OPTIMALITY_CLAIM_UNSUPPORTED


# --------------------------------------------------------------------------
# adversarial: violations engineered to sit inside a float tolerance
# --------------------------------------------------------------------------


def test_primal_violation_of_one_part_in_a_billion_is_still_rejected():
    """Exact means exact. A naive checker with atol=1e-6 accepts this."""
    verdict = verify(
        _instance(integer_indices=[]),
        _certificate(
            primal=["0.999999999", "0"],
            claimed_objective="0.999999999",
            claims_optimal=False,
            dual=["0"],
            claimed_bound="0",
        ),
    )
    assert verdict.reason is Rejection.PRIMAL_INFEASIBLE


def test_integrality_off_by_a_nanounit_is_still_rejected():
    verdict = verify(
        _instance(),
        _certificate(
            primal=["1.000000001", "0"],
            claimed_objective="1.000000001",
            claims_optimal=False,
            dual=["0"],
            claimed_bound="0",
        ),
    )
    assert verdict.reason is Rejection.INTEGRALITY_VIOLATED


def test_dual_feasibility_off_by_a_nanounit_is_still_rejected():
    verdict = verify(
        _instance(),
        _certificate(
            dual=["1.000000001"],
            claimed_bound="1.000000001",
            claims_optimal=False,
        ),
    )
    assert verdict.reason is Rejection.DUAL_INFEASIBLE


# --------------------------------------------------------------------------
# adversarial: float and exact arithmetic disagree about the objective
# --------------------------------------------------------------------------


def _cancellation_instance() -> MilpInstance:
    """c'x is 2 exactly, but numpy.dot returns 1.0 by pairwise summation."""
    return MilpInstance.from_payload(
        {
            "objective": ["1e16", "1", "-1e16", "1"],
            "matrix": [["0", "0", "0", "0"]],
            "rhs": ["0"],
            "upper_bounds": ["10", "10", "10", "10"],
            "integer_indices": [0, 1, 2, 3],
        }
    )


def _cancellation_certificate(**overrides) -> Certificate:
    payload = {
        "primal": ["1", "1", "1", "1"],
        "dual": ["0"],
        "bound_dual": ["0", "0", "1e16", "0"],
        "claimed_objective": "2",
        "claimed_bound": "-1e17",
        "claims_optimal": False,
    }
    payload.update(overrides)
    return Certificate.from_payload(payload)


def test_objective_that_only_exact_arithmetic_confirms_is_accepted():
    """A float verifier using numpy.dot computes 1.0 and wrongly rejects this."""
    import numpy as np

    assert float(np.dot([1e16, 1.0, -1e16, 1.0], [1.0, 1.0, 1.0, 1.0])) == 1.0

    verdict = verify(_cancellation_instance(), _cancellation_certificate())

    assert verdict.accepted


def test_objective_that_only_float_arithmetic_confirms_is_rejected():
    """The mirror image: numpy agrees with a claim of 1, exact arithmetic does not."""
    verdict = verify(
        _cancellation_instance(), _cancellation_certificate(claimed_objective="1")
    )

    assert verdict.reason is Rejection.OBJECTIVE_MISMATCH


# --------------------------------------------------------------------------
# determinism of the verdict when several conditions fail at once
# --------------------------------------------------------------------------


def test_rejection_reasons_follow_the_declared_precedence():
    """Infeasible AND fractional AND wrong objective: primal wins."""
    verdict = verify(
        _instance(),
        _certificate(primal=["0.5", "0"], claimed_objective="99"),
    )
    assert verdict.reason is Rejection.PRIMAL_INFEASIBLE


def test_integrality_outranks_objective_mismatch():
    verdict = verify(
        _instance(),
        _certificate(primal=["1.5", "0"], claimed_objective="99"),
    )
    assert verdict.reason is Rejection.INTEGRALITY_VIOLATED


def test_objective_mismatch_outranks_dual_infeasibility():
    verdict = verify(
        _instance(),
        _certificate(claimed_objective="99", dual=["7"], claimed_bound="7"),
    )
    assert verdict.reason is Rejection.OBJECTIVE_MISMATCH


def test_verify_is_a_pure_function_of_its_inputs():
    instance, certificate = _instance(), _certificate()

    first = verify(instance, certificate)
    second = verify(instance, certificate)

    assert first == second
