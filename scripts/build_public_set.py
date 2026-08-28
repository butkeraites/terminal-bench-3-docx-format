#!/usr/bin/env python3
"""Build the public submission set shipped to the agent.

Same distribution as the graded stream, drawn under its own fixed nonce so it
reveals nothing about any graded run, and shipped *with* the correct verdicts so
the agent can measure itself.

What is deliberately not shipped: the generator. The agent gets samples and
answers, not the taxonomy of what makes a submission adversarial. Discovering
that a naive float verifier disagrees with exact arithmetic, and on which inputs,
is the work.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verifier-core" / "src"))

from certverify.application.stream import (  # noqa: E402
    StreamConfig,
    plan_for_run,
    submission_at,
)
from certverify.application.verify import verify  # noqa: E402

TASK = ROOT / "tasks/certificate-verifier-slo"
PUBLIC_NONCE = "public-set-v1"
PUBLIC_COUNT = 80


def main() -> None:
    sys.path.insert(0, str(TASK))
    from graded import CONFIG as graded, SECRET as secret_text

    secret = secret_text.encode()

    config = StreamConfig(
        count=PUBLIC_COUNT,
        num_vars=graded["num_vars"],
        num_constraints=graded["num_constraints"],
    )
    plan = plan_for_run(secret, 0, config, PUBLIC_NONCE)

    submissions, answers = [], []
    for position, kind in enumerate(plan):
        s = submission_at(secret, 0, config, position, kind, PUBLIC_NONCE)
        verdict = verify(s.instance, s.certificate)
        submissions.append(s.payload)
        answers.append(
            {
                "submission_id": s.submission_id,
                "accepted": verdict.accepted,
                "reason": verdict.reason.value if verdict.reason else None,
            }
        )

    out = TASK / "environment/public"
    out.mkdir(parents=True, exist_ok=True)
    (out / "submissions.json").write_text(
        json.dumps({"submissions": submissions}, separators=(",", ":"))
    )
    (out / "answers.json").write_text(json.dumps({"answers": answers}, indent=1))

    accepted = sum(a["accepted"] for a in answers)
    print(f"  {PUBLIC_COUNT} submissions at "
          f"{config.num_vars}x{config.num_constraints}: "
          f"{accepted} accepted, {PUBLIC_COUNT - accepted} rejected")
    for path in (out / "submissions.json", out / "answers.json"):
        print(f"  {path.relative_to(ROOT)}: {path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
