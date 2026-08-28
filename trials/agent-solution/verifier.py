"""Certificate verification service.

Answers POST /verify with a verdict on a submitted MILP optimality certificate.
See /app/SPEC.md for the verdict semantics this is meant to implement.

Every check is carried out in exact rational arithmetic: wire values are
parsed into integer numerator/denominator pairs, vectors are scaled onto a
common denominator, and each comparison becomes an integer comparison.  There
is no tolerance anywhere.
"""

from __future__ import annotations

import math
import os
from typing import Any

from exact import (
    Malformed,
    build_matrix,
    cache_values,
    choose_limb_bits,
    common_scale,
    matvec,
    maybe_trim_cache,
    parse_scalar,
    parse_vector,
    vecmat,
)

try:  # pragma: no cover - depends on what is installed
    import orjson

    _loads = orjson.loads

    def _dumps(payload: Any) -> bytes:
        return orjson.dumps(payload)

except ImportError:  # pragma: no cover
    import json

    _loads = json.loads

    def _dumps(payload: Any) -> bytes:
        return json.dumps(payload).encode()


DIMENSION_MISMATCH = "dimension_mismatch"
PRIMAL_INFEASIBLE = "primal_infeasible"
INTEGRALITY_VIOLATED = "integrality_violated"
OBJECTIVE_MISMATCH = "objective_mismatch"
DUAL_INFEASIBLE = "dual_infeasible"
BOUND_MISMATCH = "bound_mismatch"
OPTIMALITY_CLAIM_UNSUPPORTED = "optimality_claim_unsupported"


def judge(payload: Any) -> tuple[bool, str | None]:
    """Return ``(accepted, reason)`` for one submission payload."""
    try:
        instance = payload["instance"]
        certificate = payload["certificate"]
        objective = instance["objective"]
        matrix = instance["matrix"]
        rhs = instance["rhs"]
        upper = instance["upper_bounds"]
        integer_indices = instance["integer_indices"]
        primal = certificate["primal"]
        dual = certificate["dual"]
        bound_dual = certificate["bound_dual"]
        claimed_objective = certificate["claimed_objective"]
        claimed_bound = certificate["claimed_bound"]
        claims_optimal = certificate["claims_optimal"]
    except (KeyError, TypeError, IndexError):
        return False, DIMENSION_MISMATCH

    # ---- 1. shapes ------------------------------------------------------
    for sequence in (
        objective,
        matrix,
        rhs,
        upper,
        integer_indices,
        primal,
        dual,
        bound_dual,
    ):
        if type(sequence) is not list:
            return False, DIMENSION_MISMATCH

    n = len(objective)
    m = len(rhs)
    if (
        len(upper) != n
        or len(matrix) != m
        or len(primal) != n
        or len(bound_dual) != n
        or len(dual) != m
    ):
        return False, DIMENSION_MISMATCH
    for row in matrix:
        if type(row) is not list or len(row) != n:
            return False, DIMENSION_MISMATCH
    for index in integer_indices:
        if type(index) is not int or index < 0 or index >= n:
            return False, DIMENSION_MISMATCH

    # A wire value that matches no accepted numeric form is a dimension
    # mismatch too, so everything is parsed before any other check runs.
    try:
        c_num, c_den = parse_vector(objective)
        b_num, b_den = parse_vector(rhs)
        u_num, u_den = parse_vector(upper)
        x_num, x_den = parse_vector(primal)
        y_num, y_den = parse_vector(dual)
        w_num, w_den = parse_vector(bound_dual)
        obj_num, obj_den = parse_scalar(claimed_objective)
        bound_num, bound_den = parse_scalar(claimed_bound)
        a_scaled = build_matrix(matrix, m, n, choose_limb_bits(max(m, n)))
    except Malformed:
        return False, DIMENSION_MISMATCH

    # ---- 2. primal feasibility -----------------------------------------
    for xn, xd, un, ud in zip(x_num, x_den, u_num, u_den):
        if xn < 0 or xn * ud > un * xd:
            return False, PRIMAL_INFEASIBLE

    x_vec, x_scale = common_scale(x_num, x_den)
    row_activity = matvec(a_scaled, x_vec)
    activity_scale = a_scaled.denom * x_scale
    for activity, bn, bd in zip(row_activity, b_num, b_den):
        if activity * bd < bn * activity_scale:
            return False, PRIMAL_INFEASIBLE

    # ---- 3. integrality -------------------------------------------------
    for index in integer_indices:
        if x_den[index] != 1:
            return False, INTEGRALITY_VIOLATED

    # ---- 4. claimed objective ------------------------------------------
    c_vec, c_scale = common_scale(c_num, c_den)
    objective_value = math.sumprod(c_vec, x_vec)
    if objective_value * obj_den != obj_num * (c_scale * x_scale):
        return False, OBJECTIVE_MISMATCH

    # ---- 5. dual feasibility -------------------------------------------
    for value in y_num:
        if value < 0:
            return False, DUAL_INFEASIBLE
    for value in w_num:
        if value < 0:
            return False, DUAL_INFEASIBLE

    y_vec, y_scale = common_scale(y_num, y_den)
    w_vec, w_scale = common_scale(w_num, w_den)
    column_activity = vecmat(y_vec, a_scaled)
    dual_scale = a_scaled.denom * y_scale
    left = w_scale * c_scale
    middle = dual_scale * c_scale
    right = dual_scale * w_scale
    for activity, wv, cv in zip(column_activity, w_vec, c_vec):
        if activity * left - wv * middle > cv * right:
            return False, DUAL_INFEASIBLE

    # ---- 6. claimed bound ----------------------------------------------
    b_vec, b_scale = common_scale(b_num, b_den)
    u_vec, u_scale = common_scale(u_num, u_den)
    by = math.sumprod(b_vec, y_vec)
    uw = math.sumprod(u_vec, w_vec)
    by_scale = b_scale * y_scale
    uw_scale = u_scale * w_scale
    if (by * uw_scale - uw * by_scale) * bound_den != bound_num * (
        by_scale * uw_scale
    ):
        return False, BOUND_MISMATCH

    # ---- 7. optimality claim -------------------------------------------
    if claims_optimal:
        if obj_num * bound_den != bound_num * obj_den:
            return False, OPTIMALITY_CLAIM_UNSUPPORTED

    return True, None


def verdict_for(payload: Any) -> dict[str, Any]:
    submission_id = None
    if type(payload) is dict:
        submission_id = payload.get("submission_id")
    try:
        accepted, reason = judge(payload)
    except Exception:  # a malformed submission must still get an answer
        accepted, reason = False, DIMENSION_MISMATCH
    return {
        "submission_id": submission_id,
        "accepted": accepted,
        "reason": reason,
    }


# --------------------------------------------------------------------------
# ASGI application
# --------------------------------------------------------------------------

_JSON_HEADERS = [(b"content-type", b"application/json")]
_HEALTH_BODY = b'{"status":"ok"}'
_BAD_REQUEST = _dumps(
    {"submission_id": None, "accepted": False, "reason": DIMENSION_MISMATCH}
)
_NOT_FOUND = b'{"detail":"Not Found"}'


async def _send_json(send, status: int, body: bytes) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": _JSON_HEADERS
            + [(b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _read_body(receive) -> bytes | None:
    chunks = []
    while True:
        message = await receive()
        kind = message["type"]
        if kind == "http.request":
            chunk = message.get("body", b"")
            if chunk:
                chunks.append(chunk)
            if not message.get("more_body", False):
                break
        elif kind == "http.disconnect":
            return None
    if not chunks:
        return b""
    if len(chunks) == 1:
        return chunks[0]
    return b"".join(chunks)


async def app(scope, receive, send):
    kind = scope["type"]
    if kind == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                _warm_up()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
        return

    if kind != "http":
        return

    path = scope["path"]
    method = scope["method"]

    if path == "/verify" and method == "POST":
        body = await _read_body(receive)
        if body is None:
            return
        maybe_trim_cache()
        try:
            payload = _loads(body)
        except Exception:
            await _send_json(send, 200, _BAD_REQUEST)
            return
        await _send_json(send, 200, _dumps(verdict_for(payload)))
        return

    if path == "/healthz" and method in ("GET", "HEAD"):
        await _send_json(send, 200, _HEALTH_BODY)
        return

    await _send_json(send, 404, _NOT_FOUND)


# --------------------------------------------------------------------------
# warm-up
#
# The value cache and numpy's matmul dispatch are both cold in a fresh worker.
# Replaying a few stored submissions pays that cost before the first graded
# request arrives instead of inside its latency budget.
# --------------------------------------------------------------------------

_WARMUP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "warmup.json")


def _warm_up() -> None:
    try:
        with open(_WARMUP_PATH, "rb") as handle:
            warm = _loads(handle.read())
        cache_values(warm.get("values", ()))
        for payload in warm.get("submissions", ()):
            for _ in range(3):
                judge(payload)
    except Exception:
        pass
