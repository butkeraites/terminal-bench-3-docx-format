# Terminal-Bench 3 task submission

One original TB3 task — **[`tasks/docx-format/`](tasks/docx-format/)** — with
the evidence that frontier agents fail it and cannot game it.

**Start with [`REPORT.md`](REPORT.md).** It carries the task identity and its
content hashes, the oracle/nop results, every agent trial with its reward and
cost, the failure analysis, the exact commands to reproduce all of it, and a
plain statement of what is missing.

## The task in one paragraph

The agent gets a rendered one-page report as a PDF and no source document. It
has to infer the entire visual treatment from the page and rebuild it as an
editable `.docx` around different content — and the result must render the same
in more than one word processor. Grading is arithmetic over the pixels of the
rendered output; nothing inspects the OOXML, and the expectations are extracted
from the template itself rather than written into the tests by hand.

Why it is hard, how it is solved and how it is verified are stated by the task
author in the `[metadata]` block of
[`tasks/docx-format/task.toml`](tasks/docx-format/task.toml).

## Results

| | Claude Code `opus-5` max | Codex `gpt-5.6-sol` xhigh |
|---|---|---|
| Standard trials (`/run`) | 3 runs, **reward 0** in all 3 | 3 runs, **reward 0** in all 3 |
| Tests failed per run | 1, 1, 4 of 23 | 6, 7, 9 of 23 |
| Adversarial trials (`/cheat`) | **reward 0** | **reward 0** |

Two of the three Claude Code runs failed by a **single test**, and by a different
one each time — worth knowing, and `REPORT.md` §4 states it with the numbers.

It is also worth reading correctly. 22 of 23 is close to finishing *one page*.
The filings this task is drawn from run to hundreds of pages and are accepted
only if every page is right, so the quantity that matters is the fraction of
pages that come out perfect — and that is **0 of 3**. The single-page reduction
understates the real gap rather than flattering the models.

Oracle scores 1 with all 23 passing, nop scores 0. Two earlier drafts were
solved outright by Claude Code; the current tests are what closed them.

The adversarial trial is worth reading in full (`REPORT.md` §6). Claude Code
skipped building a document and shipped a **300 dpi picture** of the template
instead, with real text floated over it so extraction checks would pass. It
passed 20 of 23 tests — including both cross-engine agreement tests, since a
bitmap cannot disagree between renderers. It was stopped by the callout letters:
they had been drawn as pixels, so the rendered page contains no text "A" and no
text "B". The test it fell to has two halves; this is the sound one, and the
one an honest document satisfies without effort.

## One defect fixed, one still open

**Fixed before submitting.** `harbor check` found that a test required the
callout letter within 90 px of its figure, while `tests/template.pdf` puts it
222 px away and ties it to its mark with a long leader instead. The instruction
tells the agent to imitate the template, so the assertion failed documents for
obeying it. The distance assertion was removed — the leader is already asserted
by its own test — and the whole battery was re-run afterwards. Everything in the
results above is from the corrected suite. `REPORT.md` §5.1 has the measurements.

**Still open: nothing enforces editability.**

The instruction asks for an editable Word
document, but no test checks it. A flat 300 dpi raster of the template, with real text floated over
it, passes 20 of the 23 tests — including both cross-engine agreement tests,
because a bitmap cannot disagree between renderers. It is stopped only by the
callout letters, which were drawn as pixels and so leave no "A" or "B" in the
page's text layer. That assertion was written to check where a letter sits, not
to catch a raster; it happens to be the backstop.

Three tests would close it properly, and would be the next work on this task:
extract the text through OCR and compare it with the text layer, assert that the
artefact really is an editable Word document rather than a picture container,
and check the OOXML for the structural markers a genuine document must carry.

They are not in the submitted suite. Adding them now would mean the five
standard trials and the two adversarial trials had run against a different
verifier, and re-running them was out of budget. The suite here is exactly the
one every result in `REPORT.md` was measured against.

## Layout

```
tasks/docx-format/     the submitted task
adversarial/           red-team variant + scripted cheat, for the /cheat trials
configs/               job configs for oracle, nop, /run and /cheat
trials/final*/         the six standard trials and the two adversarial ones
trials/probe-docx*/    the two earlier drafts Claude Code solved — see REPORT.md §5
checks/                oracle, nop, and the rubric check before and after the fix
authoring/             the Word source the template PDF was rendered from
scripts/               the trial-log recovery described in REPORT.md's appendix
archive/certificate-verifier-slo/   a second, complete task — NOT the submission
```

Everything in this repository is either the task, the evidence cited in
`REPORT.md`, or what is needed to reproduce that evidence. Work that is not part
of this submission — an earlier unrelated task, superseded trial records — was
removed rather than left to be sifted; it remains in the git history.
