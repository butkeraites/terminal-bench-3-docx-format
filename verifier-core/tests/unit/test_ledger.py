"""Tamper-evident verdict log.

The judge sidecar records what the agent's service answered, and Harbor hands
that record to the verifier. The agent has no filesystem path to it, but it does
share the judge's network namespace, so anything the judge exposes is reachable
from the agent's container. Chaining every record under HMAC makes forgery
detectable even if that boundary is ever weaker than intended: the verifier
recomputes the chain and rejects a log that does not reproduce its own digest.
"""

import pytest

from certverify.application.ledger import Ledger, Outcome, verify_chain

SECRET = b"ledger-test-secret"


def _ledger(n: int = 3) -> Ledger:
    ledger = Ledger(secret=SECRET, run_id="run-1", run_index=1)
    for i in range(n):
        ledger.append(
            submission_id=f"r1-s{i:05d}",
            accepted=(i % 2 == 0),
            reason=None if i % 2 == 0 else "primal_infeasible",
            latency_ms=1.5 + i,
            outcome=Outcome.OK,
        )
    return ledger


# --------------------------------------------------------------------------
# sealing
# --------------------------------------------------------------------------


def test_a_sealed_log_verifies_against_its_own_secret():
    sealed = _ledger().seal()

    assert verify_chain(SECRET, sealed)


def test_sealed_log_carries_every_record_in_order():
    sealed = _ledger(4).seal()

    assert [r["seq"] for r in sealed["records"]] == [0, 1, 2, 3]
    assert sealed["run_index"] == 1
    assert sealed["run_id"] == "run-1"


def test_an_empty_run_still_seals_and_verifies():
    sealed = Ledger(secret=SECRET, run_id="run-9", run_index=9).seal()

    assert sealed["records"] == []
    assert verify_chain(SECRET, sealed)


def test_the_digest_changes_with_the_content():
    a = _ledger(3).seal()
    b = _ledger(4).seal()

    assert a["digest"] != b["digest"]


def test_sealing_is_reproducible():
    assert _ledger().seal()["digest"] == _ledger().seal()["digest"]


# --------------------------------------------------------------------------
# tamper detection — each of these is a way to forge a passing run
# --------------------------------------------------------------------------


def test_flipping_a_verdict_is_detected():
    sealed = _ledger().seal()
    sealed["records"][1]["accepted"] = True

    assert not verify_chain(SECRET, sealed)


def test_rewriting_a_rejection_reason_is_detected():
    sealed = _ledger().seal()
    sealed["records"][1]["reason"] = "bound_mismatch"

    assert not verify_chain(SECRET, sealed)


def test_shrinking_a_latency_is_detected():
    """Otherwise a slow run could be edited into a fast one."""
    sealed = _ledger().seal()
    sealed["records"][2]["latency_ms"] = 0.001

    assert not verify_chain(SECRET, sealed)


def test_dropping_a_record_is_detected():
    sealed = _ledger(4).seal()
    del sealed["records"][2]

    assert not verify_chain(SECRET, sealed)


def test_inserting_a_record_is_detected():
    sealed = _ledger(3).seal()
    sealed["records"].append(dict(sealed["records"][0], seq=3, submission_id="r1-s00003"))

    assert not verify_chain(SECRET, sealed)


def test_reordering_records_is_detected():
    sealed = _ledger(3).seal()
    sealed["records"][0], sealed["records"][2] = sealed["records"][2], sealed["records"][0]

    assert not verify_chain(SECRET, sealed)


def test_renumbering_the_run_is_detected():
    """Run index is in the chain header, so a run cannot be relabelled."""
    sealed = _ledger().seal()
    sealed["run_index"] = 2

    assert not verify_chain(SECRET, sealed)


def test_a_forged_digest_is_detected():
    sealed = _ledger().seal()
    sealed["digest"] = "0" * 64

    assert not verify_chain(SECRET, sealed)


def test_a_log_sealed_with_another_secret_is_rejected():
    sealed = _ledger().seal()

    assert not verify_chain(b"not-the-secret", sealed)


def test_a_structurally_broken_log_is_rejected_rather_than_raising():
    for broken in ({}, {"records": []}, {"digest": "x", "records": "nope"}):
        assert not verify_chain(SECRET, broken)


# --------------------------------------------------------------------------
# outcomes other than a clean answer
# --------------------------------------------------------------------------


def test_a_failed_call_is_recorded_with_no_verdict():
    """A dropped or errored submission must be visible, not silently absent."""
    ledger = Ledger(secret=SECRET, run_id="run-2", run_index=2)
    ledger.append(
        submission_id="r2-s00000",
        accepted=None,
        reason=None,
        latency_ms=5000.0,
        outcome=Outcome.TIMEOUT,
    )
    sealed = ledger.seal()

    assert sealed["records"][0]["outcome"] == "timeout"
    assert sealed["records"][0]["accepted"] is None
    assert verify_chain(SECRET, sealed)


def test_outcome_is_part_of_the_chain():
    ledger = Ledger(secret=SECRET, run_id="run-2", run_index=2)
    ledger.append("r2-s00000", None, None, 5000.0, Outcome.TIMEOUT)
    sealed = ledger.seal()
    sealed["records"][0]["outcome"] = "ok"

    assert not verify_chain(SECRET, sealed)


def test_the_nonce_is_inside_the_chain():
    """The verifier regenerates the graded stream from the nonce, so it is an
    input to grading and must be authenticated like any record."""
    ledger = Ledger(secret=SECRET, run_id="run-3", run_index=3, nonce="deadbeef")
    ledger.append("r3-s00000", True, None, 1.0, Outcome.OK)
    sealed = ledger.seal()

    assert sealed["nonce"] == "deadbeef"
    assert verify_chain(SECRET, sealed)

    sealed["nonce"] = "00000000"
    assert not verify_chain(SECRET, sealed)


def test_a_log_without_a_nonce_still_verifies():
    """Backwards compatible with a ledger that never set one."""
    ledger = Ledger(secret=SECRET, run_id="run-4", run_index=4)
    sealed = ledger.seal()
    sealed.pop("nonce")

    assert verify_chain(SECRET, sealed)
