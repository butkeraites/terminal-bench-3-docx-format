#!/usr/bin/env python3
"""Controlled comparison of verification strategies on the graded stream.

This replaces a series of ad-hoc timing scripts that produced numbers which did
not survive scrutiny. Three rules, each fixing a specific mistake those scripts
made:

  1. **Correctness gates timing.** Every exact backend must reproduce the
     reference verdict on every submission before any of its timings are
     reported. A backend that short-circuits differently is not a faster
     implementation of the same function, it is a different function.
  2. **Short-circuit depth is reported, not averaged away.** A rejected
     submission stops early, and how early depends on which check rejected it.
     Aggregating over a mixed stream without showing that breakdown hides the
     effect and produced two contradictory results earlier.
  3. **Per-submission minimum over repeats.** The minimum is the least
     noise-contaminated estimator of the underlying cost; means over a shared
     machine drift with whatever else is running.

Usage:
    PYTHONPATH=src python scripts/benchmark_paths.py --vars 200 --constraints 150
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from certverify.application.hybrid import verify_hybrid  # noqa: E402
from certverify.application.stream import StreamConfig, generate_run  # noqa: E402
from certverify.application.verify import verify  # noqa: E402
from certverify.domain.milp import Certificate, MilpInstance, Verdict  # noqa: E402

SECRET = b"benchmark-harness"


def reference(instance: dict, certificate: dict) -> Verdict:
    """The specification, timed with its parsing included like every other path."""
    try:
        return verify(
            MilpInstance.from_payload(instance), Certificate.from_payload(certificate)
        )
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        from certverify.domain.milp import Rejection

        return Verdict.reject(Rejection.DIMENSION_MISMATCH)


def _load_backends() -> dict[str, tuple[Callable, bool]]:
    """name -> (callable, must_match_reference)."""
    backends: dict[str, tuple[Callable, bool]] = {
        "exact/Fraction": (reference, True),
        "hybrid": (verify_hybrid, True),
    }

    try:
        from certverify.infrastructure.mpq_verify import verify_mpq

        backends["exact/gmpy2"] = (verify_mpq, True)
    except ImportError:
        print("  (gmpy2 not installed — skipping that baseline)", file=sys.stderr)

    service = ROOT.parent / "tasks/certificate-verifier-slo/environment/service"
    if service.is_dir():
        sys.path.insert(0, str(service))
        try:
            from verifier import Submission, judge  # type: ignore

            def float_only(instance: dict, certificate: dict) -> Verdict:
                from certverify.domain.milp import Rejection

                try:
                    accepted, reason = judge(
                        Submission(
                            submission_id="bench",
                            instance=instance,
                            certificate=certificate,
                        )
                    )
                except Exception:
                    return Verdict.reject(Rejection.DIMENSION_MISMATCH)
                return (
                    Verdict.accept()
                    if accepted
                    else Verdict.reject(Rejection(reason))
                )

            # Expected to disagree: that disagreement is the reason the task exists.
            backends["float-only (starting service)"] = (float_only, False)
        except ImportError:
            pass

    return backends


def measure(
    fn: Callable, payloads: list[tuple[dict, dict]], repeats: int
) -> tuple[list[float], list[Verdict]]:
    """Per-submission minimum over `repeats`, in milliseconds."""
    for instance, certificate in payloads[: min(3, len(payloads))]:
        fn(instance, certificate)  # warm caches and imports

    timings: list[float] = []
    verdicts: list[Verdict] = []
    for instance, certificate in payloads:
        best = float("inf")
        verdict = None
        for _ in range(repeats):
            start = time.perf_counter()
            verdict = fn(instance, certificate)
            best = min(best, (time.perf_counter() - start) * 1000.0)
        timings.append(best)
        verdicts.append(verdict)
    return timings, verdicts


def _decision_point(verdict: Verdict) -> str:
    return "accepted (full path)" if verdict.accepted else verdict.reason.value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--vars", type=int, default=200)
    parser.add_argument("--constraints", type=int, default=150)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--run-index", type=int, default=1)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    config = StreamConfig(
        count=args.count, num_vars=args.vars, num_constraints=args.constraints
    )
    stream = generate_run(SECRET, args.run_index, config)
    payloads = [(s.payload["instance"], s.payload["certificate"]) for s in stream]

    print(
        f"stream: {args.count} submissions at {args.vars}x{args.constraints}, "
        f"{sum(s.adversarial for s in stream)} adversarial, "
        f"{args.repeats} repeats (per-submission minimum)\n"
    )

    backends = _load_backends()
    truth = [reference(i, c) for i, c in payloads]

    results: dict[str, Any] = {}
    for name, (fn, must_match) in backends.items():
        timings, verdicts = measure(fn, payloads, args.repeats)
        mismatches = [
            i for i, (a, b) in enumerate(zip(verdicts, truth)) if a != b
        ]

        if must_match and mismatches:
            kinds = Counter(stream[i].kind.name for i in mismatches)
            print(f"  !! {name} disagrees with the reference on "
                  f"{len(mismatches)}/{len(truth)} submissions: {dict(kinds)}")
            print("     timings withheld — this is a different function.\n")
            continue

        results[name] = {
            "timings": timings,
            "verdicts": verdicts,
            "mismatches": len(mismatches),
        }

    # ---- headline
    print(f"  {'backend':<32} {'median ms':>10} {'IQR':>16} {'per second':>11} {'wrong':>7}")
    print("  " + "-" * 82)
    baseline = None
    for name, data in results.items():
        t = sorted(data["timings"])
        median = statistics.median(t)
        q1, q3 = t[len(t) // 4], t[(3 * len(t)) // 4]
        if name == "hybrid":
            baseline = median
        print(f"  {name:<32} {median:>10.3f} {f'{q1:.3f}-{q3:.3f}':>16} "
              f"{1000 / median:>11.0f} {data['mismatches']:>7}")

    # ---- the number the SLO depends on
    if baseline and "exact/gmpy2" in results:
        exact = statistics.median(results["exact/gmpy2"]["timings"])
        print(f"\n  design window (exact/gmpy2 vs hybrid): {exact / baseline:.2f}x")

    # ---- short-circuit depth, which averaging hides
    print(f"\n  by decision point (median ms):")
    points = sorted({_decision_point(v) for v in truth})
    header = "  " + f"{'decision point':<32}" + "".join(
        f"{n.split('/')[-1][:11]:>13}" for n in results
    ) + f"{'n':>6}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for point in points:
        indices = [i for i, v in enumerate(truth) if _decision_point(v) == point]
        row = f"  {point:<32}"
        for name, data in results.items():
            row += f"{statistics.median([data['timings'][i] for i in indices]):>13.3f}"
        print(row + f"{len(indices):>6}")

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "config": {"count": args.count, "vars": args.vars,
                               "constraints": args.constraints,
                               "repeats": args.repeats},
                    "backends": {
                        name: {
                            "median_ms": statistics.median(d["timings"]),
                            "timings_ms": d["timings"],
                            "mismatches": d["mismatches"],
                        }
                        for name, d in results.items()
                    },
                },
                indent=2,
            )
        )
        print(f"\n  -> {args.json}")


if __name__ == "__main__":
    main()
