# Certificate verification service — technical specification

Source material for `instruction.md`. **Do not paste this into the task**: the
contributing guide, the PR template and the `instruction_concision` rubric all
require the instruction to be written by hand. Translate it.

---

## 1. Problem family

Every submission refers to a mixed-integer linear program in the fixed form

```
minimise    c'x
subject to  Ax >= b
            0 <= x <= u
            x_j integer  for j in I
```

with `A` an `m x n` rational matrix, `c, u` in `Q^n`, `b` in `Q^m`, and
`I ⊆ {0, …, n-1}`. All bounds are finite.

The dual of the continuous relaxation is

```
maximise    b'y - u'w
subject to  A'y - w <= c
            y >= 0,  w >= 0
```

For any primal feasible `x` and any dual feasible `(y, w)`:

```
c'x  >=  (A'y - w)'x  =  y'Ax - w'x  >=  y'b - w'u  =  b'y - u'w
```

so `b'y - u'w` is a valid lower bound. It is valid for the integer problem as
well, because every integer feasible point is relaxation feasible. A certificate
is therefore the triple `(x, y, w)` plus the claims made about it.

## 2. Number representation

**Every numeric quantity in every payload is a JSON string, never a JSON number.**

Accepted syntax:

| form | example | value |
|---|---|---|
| integer | `"42"`, `"-7"` | 42, −7 |
| decimal | `"0.1"`, `"-0.25"` | 1/10, −1/4 |
| scientific | `"1e3"`, `"1.5e-2"` | 1000, 3/200 |
| fraction | `"1/3"`, `"-2/6"` | 1/3, −1/3 |

Each is parsed to an exact rational. This is not a formatting preference:
`float("0.1")` is `3602879701896397/36028797018963968`, so a parser that goes
through binary floating point has already lost the value before any arithmetic
happens. Malformed literals are a `dimension_mismatch`-class input error and the
submission is rejected.

## 3. Verdict semantics

A submission is **accepted** if and only if every condition below holds **in
exact rational arithmetic**. There is no tolerance parameter anywhere in this
specification, by design: a constraint violated by one part in a billion is
violated.

1. **Well-formedness.** `len(u) == len(c) == n`; `A` has `m` rows each of length
   `n`; every index in `I` lies in `[0, n)`; `len(x) == len(w) == n`;
   `len(y) == m`.
2. **Primal feasibility.** `0 <= x_j <= u_j` for every `j`, and
   `(Ax)_i >= b_i` for every `i`.
3. **Integrality.** `x_j` has denominator 1 for every `j` in `I`.
4. **Objective consistency.** `claimed_objective == c'x`.
5. **Dual feasibility.** `y >= 0`, `w >= 0`, and `(A'y - w)_j <= c_j` for every `j`.
6. **Bound consistency.** `claimed_bound == b'y - u'w`.
7. **Optimality claim.** If `claims_optimal` is true, then
   `claimed_objective == claimed_bound`.

### Rejection precedence

When more than one condition fails, the reported reason is the **first** failing
condition in this order. The verdict is thereby a deterministic function of the
submission, not an artefact of evaluation order:

```
dimension_mismatch
primal_infeasible
integrality_violated
objective_mismatch
dual_infeasible
bound_mismatch
optimality_claim_unsupported
```

## 4. Wire format

### Request — `POST /verify`

```json
{
  "submission_id": "sub-00042",
  "instance": {
    "objective":       ["1", "1"],
    "matrix":          [["1", "1"]],
    "rhs":             ["1"],
    "upper_bounds":    ["10", "10"],
    "integer_indices": [0, 1]
  },
  "certificate": {
    "primal":            ["1", "0"],
    "dual":              ["1"],
    "bound_dual":        ["0", "0"],
    "claimed_objective": "1",
    "claimed_bound":     "1",
    "claims_optimal":    true
  }
}
```

### Response — 200

```json
{ "submission_id": "sub-00042", "accepted": true,  "reason": null }
{ "submission_id": "sub-00043", "accepted": false, "reason": "primal_infeasible" }
```

`reason` is `null` exactly when `accepted` is true, and otherwise one of the
seven strings above. `submission_id` must echo the request.

## 5. Service-level requirements

The graded run is a fixed stream of submissions replayed by the judge sidecar at
a target rate. A run passes only if **all** of the following hold:

- **Every verdict is correct.** Both `accepted` and `reason` must match. One
  wrong verdict fails the run — a verifier that is right 99% of the time is
  worthless as a trust layer, which is the entire premise.
- **No submission is dropped.** Every `submission_id` in the stream appears
  exactly once in the log, with no duplicates.
- **Latency.** p99 per-submission latency stays within the declared budget.
- **Restart durability.** The judge sends `SIGKILL` to a service worker partway
  through the stream. Submissions in flight at that moment must still be answered
  correctly and exactly once.

### Why both pure strategies fail

Measured on this hardware (`verifier-core/scripts/benchmark_arithmetic.py`),
full verification path, 400x300 instances:

| arithmetic | per submission | throughput, 4 CPUs |
|---|---|---|
| numpy float64 | 0.071 ms | ~56,000/s — **but wrong on adversarial submissions** |
| gmpy2 `mpq` (exact) | ~35 ms | ~112/s |
| stdlib `Fraction` (exact) | 190 ms | ~21/s |

The environment has open internet, so the agent will reach for `gmpy2`; the
budget is sized against `mpq`, not against the stdlib. Exact-everywhere misses
the rate; float-everywhere misses the verdicts. The intended solution is a float
screen carrying a **certified running error bound**, escalating to exact
arithmetic only when that bound straddles the decision boundary.

## 6. Adversarial content of the stream

The graded stream mixes ordinary submissions with ones engineered against a
careless verifier:

- Constraint violations of `1e-9` — inside any plausible float tolerance.
- Integer variables at `2.000000001`.
- Dual feasibility violated in the last representable digit.
- Objectives where float and exact arithmetic genuinely disagree, in **both**
  directions: certificates only exact arithmetic accepts, and certificates only
  float arithmetic accepts.
- Ill-conditioned rows where the order of summation changes the float answer.
- Submissions failing several conditions at once, to test precedence.

## 7. What the agent is given

- `/app/service/` — a working service that is correct on well-conditioned input
  and fails on all three axes: it parses to float, runs a single worker, and
  keeps no durable state across a restart.
- `/app/public/` — a public submission set with the correct verdicts, drawn from
  the same distribution as the graded stream, for self-measurement.
- The judge at `http://localhost:9000`; `POST /grade` starts a graded run.

The graded stream and its correct verdicts are not on the machine.
