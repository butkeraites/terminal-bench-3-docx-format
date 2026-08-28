"""Deterministic graded-stream generation.

The agent SEES every submission — they arrive at its service — so the stream
cannot be secret. What must not leak is the correct verdicts, and what must not
be reusable is the stream itself: an agent that recorded run 1, solved it
offline with slow exact arithmetic, and replayed a cache would defeat the
latency requirement entirely.

So each run derives from HMAC(secret, run_index). The secret lives only in the
judge and verifier images, so the verifier can regenerate and grade any run
while the agent cannot predict the next one.
"""

from collections import Counter

import pytest

from certverify.application.stream import (
    StreamConfig,
    generate_run,
    ground_truth,
)
from certverify.application.verify import verify
from certverify.domain.milp import Rejection

SECRET = b"test-secret-not-the-real-one"
SMALL = StreamConfig(count=60, num_vars=8, num_constraints=5)


# --------------------------------------------------------------------------
# determinism and unpredictability
# --------------------------------------------------------------------------


def test_the_same_secret_and_run_index_reproduce_the_stream():
    a = generate_run(SECRET, 1, SMALL)
    b = generate_run(SECRET, 1, SMALL)

    assert [s.submission_id for s in a] == [s.submission_id for s in b]
    assert [s.payload for s in a] == [s.payload for s in b]


def test_consecutive_runs_differ():
    """Otherwise a cache built during run 1 answers run 2 for free."""
    a = generate_run(SECRET, 1, SMALL)
    b = generate_run(SECRET, 2, SMALL)

    assert [s.payload for s in a] != [s.payload for s in b]


def test_a_different_secret_gives_a_different_stream():
    a = generate_run(SECRET, 1, SMALL)
    b = generate_run(b"another-secret", 1, SMALL)

    assert [s.payload for s in a] != [s.payload for s in b]


def test_submission_ids_are_unique_within_a_run():
    ids = [s.submission_id for s in generate_run(SECRET, 3, SMALL)]

    assert len(ids) == len(set(ids)) == SMALL.count


def test_submission_ids_are_namespaced_by_run():
    a = {s.submission_id for s in generate_run(SECRET, 1, SMALL)}
    b = {s.submission_id for s in generate_run(SECRET, 2, SMALL)}

    assert not (a & b)


# --------------------------------------------------------------------------
# payload shape — must be wire-ready and free of JSON numbers
# --------------------------------------------------------------------------


def test_every_numeric_field_is_a_string():
    """A JSON number would let a parser reach float without noticing."""
    submission = generate_run(SECRET, 1, SMALL)[0]
    inst = submission.payload["instance"]
    cert = submission.payload["certificate"]

    assert all(isinstance(v, str) for v in inst["objective"])
    assert all(isinstance(v, str) for row in inst["matrix"] for v in row)
    assert all(isinstance(v, str) for v in inst["rhs"])
    assert all(isinstance(v, str) for v in inst["upper_bounds"])
    assert all(isinstance(i, int) for i in inst["integer_indices"])
    assert all(isinstance(v, str) for v in cert["primal"])
    assert isinstance(cert["claimed_objective"], str)
    assert isinstance(cert["claims_optimal"], bool)


def test_payload_dimensions_are_consistent_with_the_config():
    inst = generate_run(SECRET, 1, SMALL)[0].payload["instance"]

    assert len(inst["objective"]) == SMALL.num_vars
    assert len(inst["rhs"]) == SMALL.num_constraints
    assert all(len(row) == SMALL.num_vars for row in inst["matrix"])


# --------------------------------------------------------------------------
# coverage — the stream must exercise the whole verdict vocabulary
# --------------------------------------------------------------------------


def test_ground_truth_agrees_with_the_reference_verifier():
    """ground_truth is a lookup; verify() is the definition. They must match."""
    run = generate_run(SECRET, 7, SMALL)
    truth = ground_truth(SECRET, 7, SMALL)

    for submission in run:
        expected = truth[submission.submission_id]
        actual = verify(submission.instance, submission.certificate)

        assert actual.accepted == expected.accepted
        assert actual.reason == expected.reason


def test_the_stream_contains_both_accepted_and_rejected_submissions():
    truth = ground_truth(SECRET, 4, SMALL)
    accepted = sum(1 for v in truth.values() if v.accepted)

    assert 0 < accepted < len(truth)


def test_every_rejection_reason_appears_in_a_full_size_run():
    """A stream that never exercises a reason cannot detect getting it wrong."""
    config = StreamConfig(count=400, num_vars=8, num_constraints=5)
    reasons = Counter(
        v.reason for v in ground_truth(SECRET, 5, config).values() if not v.accepted
    )

    for reason in Rejection:
        assert reasons[reason] > 0, f"{reason.value} never appears in the stream"


def test_adversarial_share_is_a_minority_but_material():
    """Too few and a float-only service passes; too many and even the intended
    hybrid falls back to exact on everything and misses the rate."""
    config = StreamConfig(count=400, num_vars=8, num_constraints=5)
    run = generate_run(SECRET, 6, config)
    adversarial = sum(1 for s in run if s.adversarial)

    assert 0.02 <= adversarial / len(run) <= 0.25


def test_adversarial_submissions_are_flagged_only_internally():
    """The flag must never reach the wire, or the agent reads the answer off it."""
    submission = next(s for s in generate_run(SECRET, 1, SMALL) if s.adversarial)

    assert "adversarial" not in submission.payload
    assert set(submission.payload) == {"submission_id", "instance", "certificate"}


# --------------------------------------------------------------------------
# lazy generation
# --------------------------------------------------------------------------


def test_lazy_iteration_yields_the_same_run_as_the_eager_list():
    from certverify.application.stream import iter_run

    eager = generate_run(SECRET, 5, SMALL)
    lazy = list(iter_run(SECRET, 5, SMALL))

    assert [s.submission_id for s in eager] == [s.submission_id for s in lazy]
    assert [s.payload for s in eager] == [s.payload for s in lazy]


def test_a_submission_can_be_built_without_its_predecessors():
    """Position independence is what makes lazy generation possible at all."""
    from certverify.application.stream import plan_for_run, submission_at

    plan = plan_for_run(SECRET, 6, SMALL)
    position = 40

    direct = submission_at(SECRET, 6, SMALL, position, plan[position])
    from_run = generate_run(SECRET, 6, SMALL)[position]

    assert direct.payload == from_run.payload
    assert direct.kind is from_run.kind


def test_the_plan_is_cheap_and_covers_every_kind():
    from certverify.application.stream import Kind, plan_for_run

    plan = plan_for_run(SECRET, 7, StreamConfig(count=400, num_vars=8, num_constraints=5))

    assert len(plan) == 400
    assert set(plan) == set(Kind)


def test_iteration_does_not_hold_the_whole_run_in_memory():
    """A 400x300 payload is about 1 MB; a materialised run is hundreds of MB."""
    import sys

    from certverify.application.stream import iter_run

    stream = iter_run(SECRET, 8, StreamConfig(count=500, num_vars=40, num_constraints=30))
    first = next(stream)

    assert sys.getsizeof(stream) < 1024
    assert first.submission_id.endswith("s00000")


# --------------------------------------------------------------------------
# per-run nonce — the defence against a published secret
# --------------------------------------------------------------------------


def test_two_nonces_produce_different_streams():
    """A merged task is public, so the baked secret is public with it. Only a
    nonce drawn at run time keeps the stream unpredictable."""
    a = generate_run(SECRET, 1, SMALL, nonce="aaaa")
    b = generate_run(SECRET, 1, SMALL, nonce="bbbb")

    assert [s.payload for s in a] != [s.payload for s in b]


def test_the_same_nonce_reproduces_the_stream():
    """The verifier regenerates from the nonce recorded in the sealed log."""
    a = generate_run(SECRET, 1, SMALL, nonce="cafe")
    b = generate_run(SECRET, 1, SMALL, nonce="cafe")

    assert [s.payload for s in a] == [s.payload for s in b]


def test_the_nonce_changes_the_plan_as_well_as_the_payloads():
    """If only payloads varied, the sequence of verdict kinds would leak."""
    from certverify.application.stream import plan_for_run

    a = plan_for_run(SECRET, 1, StreamConfig(120, 8, 5), nonce="aaaa")
    b = plan_for_run(SECRET, 1, StreamConfig(120, 8, 5), nonce="bbbb")

    assert a != b


def test_ground_truth_follows_the_nonce():
    truth = ground_truth(SECRET, 1, SMALL, nonce="beef")
    run = generate_run(SECRET, 1, SMALL, nonce="beef")

    assert set(truth) == {s.submission_id for s in run}
