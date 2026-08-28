# Terminal-Bench 3 task submission

One original TB3 task — **[`probe/docx-format/`](probe/docx-format/)** — with
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

[`probe/docx-format/README.md`](probe/docx-format/README.md) is the TB3 task
write-up: why it is hard, how it is solved, how it is verified.

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

## Layout

```
probe/docx-format/     the submitted task
probe/docx-cheat/      same task, red-team instruction, for the /cheat trials
configs/               job configs for oracle, nop, /run and /cheat
trials/  jobs/         raw harbor records for every run cited in the report
scripts/               utilities, incl. the trial-log recovery in REPORT.md's appendix
tasks/certificate-verifier-slo/   a second, complete task — NOT the submission
```

`tasks/certificate-verifier-slo/` is a different task that was built first and
taken as far as its own oracle/nop gate. It is kept because the work is real,
but the submission is `probe/docx-format/`.
