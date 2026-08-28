#!/usr/bin/env python3
"""Why the task has a crux: exact arithmetic is correct and far too slow.

Measures the full verification path (no early exit) under three arithmetics:

  numpy float64   fast, and demonstrably wrong on adversarial submissions
  gmpy2 mpq       exact, GMP-backed, the fastest exact option a solver will reach for
  fractions       exact, stdlib

The agent has open internet and will install gmpy2, so the service-level
objective must be sized against mpq, not against the stdlib.

Run:  PYTHONPATH=src python scripts/benchmark_arithmetic.py
"""

from __future__ import annotations

import random
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from certverify.application.verify import verify  # noqa: E402
from certverify.domain.milp import Certificate, MilpInstance  # noqa: E402
from certverify.domain.rational import exact_dot, to_decimal_string  # noqa: E402

SIZES = ((50, 40), (200, 150), (400, 300))


def build_accepted(n: int, m: int, seed: int = 0) -> tuple[MilpInstance, Certificate]:
    """An instance/certificate pair that exercises EVERY check to completion.

    A rejected submission short-circuits, so benchmarking one measures nothing.
    """
    rng = random.Random(seed)
    primes = (3, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    positive = lambda: f"{rng.randint(1, 100)}/{rng.choice(primes)}"  # noqa: E731

    base = {
        "objective": [positive() for _ in range(n)],  # c >= 0 makes y = w = 0 dual feasible
        "matrix": [[positive() for _ in range(n)] for _ in range(m)],
        "rhs": ["0"] * m,
        "upper_bounds": ["1000"] * n,
        "integer_indices": list(range(0, n, 2)),
    }
    ones = tuple(Fraction(1) for _ in range(n))
    partial = MilpInstance.from_payload(base)
    base["rhs"] = [to_decimal_string(exact_dot(row, ones) - Fraction(1)) for row in partial.matrix]

    instance = MilpInstance.from_payload(base)
    certificate = Certificate.from_payload(
        {
            "primal": ["1"] * n,
            "dual": ["0"] * m,
            "bound_dual": ["0"] * n,
            "claimed_objective": to_decimal_string(exact_dot(instance.objective, ones)),
            "claimed_bound": "0",
            "claims_optimal": False,
        }
    )
    assert verify(instance, certificate).accepted, "benchmark must run the full path"
    return instance, certificate


def time_float(instance: MilpInstance, certificate: Certificate, reps: int) -> float:
    A = np.array([[float(v) for v in row] for row in instance.matrix])
    c = np.array([float(v) for v in instance.objective])
    b = np.array([float(v) for v in instance.rhs])
    u = np.array([float(v) for v in instance.upper_bounds])
    x = np.array([float(v) for v in certificate.primal])
    y = np.array([float(v) for v in certificate.dual])
    w = np.array([float(v) for v in certificate.bound_dual])

    start = time.perf_counter()
    for _ in range(reps):
        bool((A @ x >= b).all() and (x >= 0).all() and (x <= u).all())
        float(c @ x)
        bool((A.T @ y - w <= c).all())
        float(b @ y - u @ w)
    return (time.perf_counter() - start) / reps * 1000.0


def time_exact(instance: MilpInstance, certificate: Certificate, reps: int) -> float:
    start = time.perf_counter()
    for _ in range(reps):
        verify(instance, certificate)
    return (time.perf_counter() - start) / reps * 1000.0


def main() -> None:
    try:
        import gmpy2

        header = f"gmpy2 {gmpy2.version()} (GMP {gmpy2.mp_version()})"
    except ImportError:
        header = "gmpy2 not installed — stdlib Fraction only"
    print(header)
    print(f"\n{'size':>11} {'float ms':>10} {'exact ms':>10} {'ratio':>8} {'exact/s':>9}")
    print("-" * 52)

    for n, m in SIZES:
        instance, certificate = build_accepted(n, m)
        reps = 20 if n <= 200 else 5
        exact_ms = time_exact(instance, certificate, reps)
        float_ms = time_float(instance, certificate, reps)
        print(
            f"{f'{n}x{m}':>11} {float_ms:>10.3f} {exact_ms:>10.2f} "
            f"{exact_ms / float_ms:>7.0f}x {1000 / exact_ms:>9.0f}"
        )


if __name__ == "__main__":
    main()
