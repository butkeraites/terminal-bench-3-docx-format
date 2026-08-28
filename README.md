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
| Standard trials (`/run`) | 3 runs, **reward 0** in all 3 | 2 runs, **reward 0** in both |
| Adversarial trials (`/cheat`) | **reward 0** | **reward 0** |

Oracle scores 1, nop scores 0. Two earlier drafts of the task were solved
outright by Claude Code; the current tests are what closed them.

The adversarial trial is worth reading in full (`REPORT.md` §6). Claude Code
skipped building a document and shipped a **300 dpi picture** of the template
instead, with real text floated over it so extraction checks would pass. It
passed 20 of 23 tests — including both cross-engine agreement tests, since a
bitmap cannot disagree between renderers. It was stopped by the callout letters:
they had been drawn as pixels, so the rendered page contains no text "A" and no
text "B". The same assertion that no honest agent passes is what catches the
cheat.

## A known limit of the verifier

The adversarial trial measured where this task's verification is thin, and the
result is worth stating plainly rather than leaving for a reviewer to find.

The instruction asks for an *editable* Word document, but no test enforces
editability. A flat 300 dpi raster of the template, with real text floated over
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
adversarial/          red-team variant + scripted cheat, for the /cheat trials
  docx-cheat/          same task, red-team instruction, for the /cheat trials
configs/               job configs for oracle, nop, /run and /cheat
trials/  jobs/         raw harbor records for every run cited in the report
scripts/               utilities, incl. the trial-log recovery in REPORT.md's appendix
archive/certificate-verifier-slo/   a second, complete task — NOT the submission
```

`archive/certificate-verifier-slo/` is a different task that was built first and
taken as far as its own oracle/nop gate. It is kept because the work is real,
but the submission is `tasks/docx-format/`.
