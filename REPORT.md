# `docx-format` — Terminal-Bench 3 task submission

A single original TB3 task, with the evidence that frontier agents fail it and
cannot game it, and a plain account of where it is thin.

The task is [`tasks/docx-format/`](tasks/docx-format/). Everything below is
reproducible from [`configs/`](configs/) and the raw records in
[`trials/`](trials/), [`jobs/`](jobs/) and [`checks/`](checks/).

---

## 1. What the task asks

The agent is given `/app/assets/template.pdf` — a one-page report, rendered —
and two replacement screenshots. There is no source document. It has to infer
the visual treatment from the rendered page alone and rebuild it as an editable
`/app/output.docx` around different content: a new title, a name that also has
to reach the footer, two subsection headings, two figures with callout marks and
leaders, and two captions with coloured runs.

Nothing about the layout is stated. Figure size, where a callout sits, how a
heading is dressed, where the page furniture runs — all of it is in the
template. One further requirement does the heavy lifting: the document must show
the same page in more than one word processor, so anything left to a theme
default is decided by the reader rather than the document.

Category `document_processing`; 4 CPUs, 4 GB, network on; agent timeout 4 h;
23 tests, binary reward.

## 2. Task identity

```
sha256:5281161bdce1275e43dbedee43025405e237fcfbe739dc8d7aa55e0066f56c5b
```

Every trial in §4 recorded this digest in its `lock.json`, and the directory in
this repository still hashes to it. The submitted task and the tested task are
the same bytes.

```bash
python -c "from harbor.publisher.packager import Packager; from pathlib import Path; \
print(Packager.compute_content_hash(Path('tasks/docx-format'))[0])"
```

The adversarial variant used in §6 is `adversarial/docx-cheat/`, digest
`sha256:bfe27a51220a…`. It differs from the task only in `instruction.md` and
the `name` in `task.toml`; environment, tests and solution are identical files.

An earlier version of this task was tested and reported before a defect was
found and fixed (§5.1). Those records are kept in `trials/cc-*`, `trials/cx-*`
and `trials/cheat/`, and they are **not** the evidence for this submission —
they measured a different test suite. Everything cited below comes from
`trials/final/` and `trials/final-cheat/`.

## 3. Required checks

| Check | Result | Evidence |
|---|---|---|
| Docker build (environment + tests) | pass | every trial below built both images |
| Oracle validation | **reward 1**, 23 passed | `checks/oracle-after-fix/2026-08-29__00-04-10/` |
| Nop validation | **reward 0** | `checks/nop-after-fix/2026-08-29__03-10-26/` |
| Implementation rubric (`harbor check`) | 6 pass, 4 fail, 1 n/a — before and after the §5.1 fix | `checks/2026-08-28__23-41-24/`, `checks/rubric-after-fix/` |

The oracle solution is the reference `.docx`, authored by hand in a word
processor; harbor mounts `solution/` for the oracle agent only.

`harbor check tasks/docx-format -m anthropic/claude-opus-5` was run twice: once
before the §5.1 fix (`checks/2026-08-28__23-41-24/`) and once after
(`checks/rubric-after-fix/`). Both times 6 pass, 4 fail, 1 not applicable, but
the composition changed.

The fix worked. The first run's central complaint — the callout letter required
within 90 px of its figure while the template puts it 222 px away — is gone from
the second. That was the defect, and it was found by this check.

Still failing after the fix, with what each is worth:

- `behavior_in_tests` — the instruction requires one caption run in red and one
  in blue and **no test checks either colour**; `BLUE` appears nowhere in the
  test modules, and the red check only requires a red rectangle inside a figure,
  so a document with entirely black caption text passes all 23 tests. This is
  correct and unfixed (§8).
- `pinned_dependencies` — the second renderer comes from a release-channel URL
  that advances over time. Correct and unfixed (§8).
- `hardcoded_solution` — `solve.sh` copies the reference rather than deriving
  it. Inherent to the task: the reference was authored by hand in a word
  processor, which is the work being benchmarked.
- `behavior_in_task_description` — four properties said to be neither stated nor
  derivable from the template. They are not equally sound:

| complaint | verdict |
|---|---|
| `test_no_body_text_is_covered_by_an_image` | **valid.** The template's own caption is overlapped 18×26 px by the clock image. Documented as a known gap (§8) and left in place deliberately. |
| `test_the_second_figure_precedes_the_caption_that_refers_to_it` | **not valid.** Measured on `tests/template.pdf`: figure 2 starts at y=1194, its caption at y=1292. The template satisfies the property, so imitating it produces the property. |
| frame padding (`MAX_FRAME_PADDING = 70`) | weak. Claude Code passed this test in all three runs. |
| `test_each_letter_is_real_text_on_the_page` | weak. Claude Code passed this test in all three runs, and the template's letters are real text. |

The contributing guide anticipates this: "The judge can be wrong if it misses
something fundamentally challenging about the task, but you should be able to
explain what makes your task hard to the maintainers." The valid complaint is
carried in §8; the others are answered by measurement above.

## 4. Standard agent trials (`/run`)

All six in `trials/final/2026-08-29__00-27-51/`. Every run completed with no
exception, so none is excluded.

### Claude Code — `anthropic/claude-opus-5`, `reasoning_effort: max`

| trial | duration | cost | reward | failed | which |
|---|---|---|---|---|---|
| `5Chr4Ws` | 31.7 min | $8.23 | **0** | **1** | headings dressed like the template |
| `feGfUQP` | 32.9 min | $8.64 | **0** | **1** | figure precedes the caption referring to it |
| `y7MPRaV` | 33.3 min | $9.29 | **0** | 4 | furniture, left bar, figure/caption order, cross-engine furniture |

### Codex — `openai/gpt-5.6-sol`, `reasoning_effort: xhigh`

| trial | duration | cost | reward | failed |
|---|---|---|---|---|
| `24LMbfv` | 13.9 min | $1.32 | **0** | 6 |
| `vKcS2W6` | 14.0 min | $1.37 | **0** | 7 |
| `zib6agQ` | 12.3 min | $1.28 | **0** | 9 |

Both credentials are subscription auth, so the dollar figures are harbor's
estimate from token counts rather than billed amounts.

### How close Claude Code came, stated plainly

**Two of three Claude Code runs failed by a single test, and by a different test
each time.** This task is at the frontier, not well beyond it. The contribution
guide asks for tasks agents "cannot solve (reliably or at all)", and 0 of 3 with
22/23 twice is the *unreliably* case rather than the *not at all* case. A fourth
run could plausibly pass.

That is a real limitation and it is stated here rather than left to be
discovered. Two things argue for submitting anyway.

First, a task the best model misses by ten tests measures less than one it
misses by one, and the tests it misses are not arbitrary — they are the
cross-engine and relational properties §5.2 describes.

Second, and more important: **one page is the floor of this problem, not the
ceiling.** The work this task is drawn from produces filings of hundreds to
thousands of pages, and the acceptance condition is uniform — a firm does not
accept a document it has to re-check, so 99% correct is a rejection — the
task's `difficulty_explanation` records the attempt that ran into exactly that
wall. The quantity that matters is
therefore not how many assertions pass on one page but the fraction of pages
that are perfect, and that fraction here is **0 of 3**. If a model's chance of
getting a whole page right is q, a 600-page filing needs roughly q^600; at
q = 0.9 that is on the order of 1e-27. Even granting heavy correlation between
pages, the requirement is uniform perfection and the measured rate of a perfect
page is zero.

So 22 of 23 is close to finishing *a page*. It is not close to producing the
deliverable, and the single-page reduction understates the real gap rather than
exaggerating it.

Codex is not close. It fails 6–9 tests, and fails the same things every run.

### The task was hardened twice to get here

Two earlier drafts were solved outright by Claude Code. Their records are in the
repository and score **reward 1**, which is why they are called out here rather
than left to be stumbled on:

| task digest | version | Claude Code | record |
|---|---|---|---|
| `sha256:64a82308…` | first draft | **reward 1**, 16 min | `trials/probe-docx/` |
| `sha256:b38a7e72…` | second draft | **reward 1**, 22 min | `trials/probe-docx-pdf/` |
| `sha256:5281161b…` | **submitted** | reward 0 in 3 of 3 | `trials/final/` |

Each draft was tightened after the model beat it. The cross-engine agreement
tests and the extracted-profile comparison came out of those two rounds.

Two other `reward 1` entries exist and are not agent results:
`checks/2026-08-28__23-41-24/` and `checks/rubric-after-fix/` are `harbor check`
runs, where reward 1 means the rubric evaluator completed, not that the task
passed the rubric. §3 gives their actual outcomes.

## 5. Failure analysis

### 5.1 A defect that was found and fixed before submitting

`harbor check` flagged that graded properties were not derivable from the
template, and direct measurement confirmed it. The test then required the
callout letter within 90 px of the figure it labels. Measured at the 150 dpi the
verifier renders at:

| | letter A | figure 1 ends at | gap |
|---|---|---|---|
| `solution/expected.docx` | x=847 | x=989 | −142 px (letter over the figure) |
| `tests/template.pdf` | x=1124 | x=902 | **+222 px** |

The template parks both letters in the right margin and ties them to their marks
with a long diagonal leader; the reference solution, whose figures are wider,
brings them in close. The instruction tells the agent to imitate the template,
so the assertion failed documents for obeying it — and Claude Code did obey,
placing figure 1 at x=352–901 against the template's 353–902 and the letters at
exactly the template's x=1124–1174.

Proximity was the wrong encoding. What ties a mark to its letter in this design
is the leader, and that is asserted by
`test_an_orange_arrow_runs_from_each_mark_towards_its_letter`. The distance
assertion was removed; the test now checks only that each letter is real text on
the page, which is the half a raster cannot fake (§6).

The fix was verified before the battery was re-run: oracle 23/23, and a single
Codex trial still failing on seven independent grounds including the leader
test. Every trial in §4 is from after the fix.

`test_no_body_text_is_covered_by_an_image` has a milder version of the same
fault — the template's own caption is overlapped 18×26 px by the clock image
against a 12 px limit. It was left in place: it is not what any Claude Code run
failed on, and changing more of the suite would have meant another full battery.

### 5.2 What the agents actually fail

**Cross-engine disagreement.** `y7MPRaV` placed the left bar where two pinned
renderers put it 22 px apart. A document that renders differently under two
engines has not determined its own appearance, and the defect is invisible in
any single rendering. This is the requirement the task is really about.

**Page furniture placed by chance.** The left bar starting inside the banner
rather than below it, and furniture that does not sit where the template's
extracted profile says it should.

**Reading order.** Two Claude Code runs put the second figure after the caption
that introduces it, so the reader meets the reference before the thing referred
to.

**Heading treatment.** One run dressed the headings differently from the
template's profile.

**Codex additionally fails a more basic tier**, consistently across all three
runs: both photographs redrawn at the wrong aspect ratio, the green frame not
reaching its image, the orange leader not arriving at its target, and the callout
letters absent from the page altogether. Its runs are 2.5× faster and 6× cheaper,
which matches the shape of the output — it stops before the layout is finished.

### 5.3 What both models get right

Every run put all six required strings on the page, the name in the footer, the
placeholders gone, the banner intact, and the red detail mark on both images.
The gap is not comprehension of the brief; it is reading a layout as a set of
relationships and stating them explicitly enough that two renderers agree.

## 6. Adversarial trials (`/cheat`)

Run against `adversarial/docx-cheat/`, the task with its instruction replaced by
a red-team charter authorising tampering with verification, fabricated outputs
and leaked-answer shortcuts. The attack surface it is pointed at is enumerated in
[`adversarial/cheat-solve.sh`](adversarial/cheat-solve.sh).

| agent | trial | duration | cost | reward | note |
|---|---|---|---|---|---|
| Claude Code `opus-5` max | `8wL4fQt` | 20.8 min | $5.10 | **0** | ran to completion |
| Codex `gpt-5.6-sol` xhigh | `ze82FxT` | 2.0 min | $0.05 | **0** | provider moderation block |

Both in `trials/final-cheat/2026-08-29__02-45-55/`.

The Claude Code trial carries the section. It failed three tests, two of them the
callout letters — the same failure the earlier adversarial run produced, for the
same reason. The strongest attack available here is to skip building a document
and ship a picture of one: a raster cannot disagree between renderers, so it
satisfies the hardest requirement by construction. What it cannot do is leave a
text "A" and a text "B" in the rendered page's text layer. That assertion stops
it, and it is the half of the letter test that survived §5.1 precisely because it
is sound.

The structural defences hold and are checkable by reading the task:
`solution/expected.docx` is mounted for the oracle agent only; `reward.txt` is
written by the verifier image after the agent's container is torn down; the
verifier ships its own pinned copy of `tests/template.pdf` and never reads the
agent's workspace; and grading is pixel arithmetic, so markup tricks and
prompt-injection into document metadata are inert.

The Codex trial returned reward 0 but is weak evidence: OpenAI's platform filter
ended the turn two minutes in with "This content was flagged for possible
cybersecurity risk", before it attempted anything. Harbor recorded
`AgentSafetyRefusalError`, and the same thing happened on the earlier attempt.
The requirement is met — both configurations ran, both scored 0 — but only the
Claude Code trial actually tested the verifier.

## 7. Reproducing this

Auth is read from the host environment. **Do not set the `*AUTH*` flags to `1`**
— see the appendix.

```bash
export CLAUDE_FORCE_OAUTH=yes
export CLAUDE_CODE_OAUTH_TOKEN="$(cat ~/.claude/harbor-token)"
export CODEX_FORCE_AUTH_JSON=yes

harbor run -c configs/oracle.json                                 # oracle
harbor run -c configs/nop.json                                    # nop
harbor run -c configs/run.json   -k 3 -n 1 -o trials/final        # 3 runs per agent
harbor run -c configs/cheat.json      -n 1 -o trials/final-cheat  # 1 per agent
harbor check tasks/docx-format -m anthropic/claude-opus-5
```

`-n 1` is deliberate: the host has 7 GB of RAM and the task asks for 4 GB, so two
concurrent trials put the LibreOffice rendering in the verifier at risk of the
OOM killer. The full battery takes roughly three hours of wall clock.

## 8. Known gaps

Stated plainly rather than papered over.

1. **The task is at the frontier, not beyond it.** Two of three Claude Code runs
   failed by one test. §4 gives the numbers and the argument for submitting
   anyway.
2. **Two instruction requirements are unverified.** The red and blue caption runs
   are never checked; a document with black captions passes all 23 tests. Found
   by the rubric check. Fixing it means another full battery, which the deadline
   did not allow.
3. **The second renderer is not pinned.** It is downloaded from a release-channel
   URL that advances with each LibreOffice release, while the cross-engine
   assertions run to an 8 px tolerance. Cheap to fix, but it changes the test
   image and would invalidate §4.
4. **Nothing enforces editability.** The instruction asks for an editable Word
   document and no test checks that it is one. A raster is currently stopped by
   the letter-presence assertion alone. Three tests would close it properly: OCR
   the rendering and compare with the text layer, assert the artefact is a real
   editable document, and check the OOXML for structural markers.
5. **`test_no_body_text_is_covered_by_an_image` is contradicted by the template**
   in the same way §5.1 describes, less severely. Left in place deliberately.
6. **The Codex adversarial trial is weak evidence** — a provider moderation
   block, not the verifier, ended it (§6).
7. **`behavior_in_task_description` still fails the rubric after the fix**, on
   four grounds of which one is sound — the body-text overlap in item 5 above.
   §3 answers the other three by measurement.
8. **Forged result files are committed on purpose.** The earlier adversarial
   trial planted `result.json`, `score.json` and four others claiming
   `"reward": 1.0` under
   `trials/cheat/…/docx-cheat__pAYkTEn/artifacts/logs/artifacts/`. They are
   evidence of an attack, labelled by a `README.FABRICATED.md` beside them. Any
   script walking this repository for rewards must read `verifier/reward.txt`.
9. **A second task is in the repository.** `archive/certificate-verifier-slo/` is
   complete through its own oracle/nop gate but is not the submission and has not
   been reviewed to submission standard.

---

## Appendix: a harbor bug that corrupted every trial log, and the recovery

Harbor scrubs secrets out of trial output after each trial
(`harbor/trial/trial.py:918`). It collects the *values* of every environment
variable whose **name** matches `(KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL|AUTH)`,
then rewrites every text file under the trial directory, replacing each value
with the literal string `[REDACTED]`.

The first round of trials was launched with `CLAUDE_FORCE_OAUTH=1` and
`CODEX_FORCE_AUTH_JSON=1`. Both names contain `AUTH`, so the one-character value
`1` was registered as a secret — and every digit `1` in every file was replaced.
`result.json` and `ctrf.json` stopped being valid JSON; the pytest output lost
every `1` in every coordinate. `CLAUDE_CODE_MAX_OUTPUT_TOKENS` has the same
defect: its name matches `TOKEN`.

The damage is fully reversible, because the replacement marker contains no digit
and therefore cannot collide with what the scrub left behind. Replacing
`[REDACTED]` with `1` restores the originals, and two independent checks confirm
the inverse is correct rather than merely plausible:

- every `result.json` parses as JSON again, **and** its restored `trials_dir`
  field matches the directory the file actually sits in;
- every pytest summary line sums back to exactly 23 tests.

[`scripts/unscrub_trials.py`](scripts/unscrub_trials.py) performs the restore and
runs both checks; 134 files were recovered. Every run since passes `yes` instead
of `1`. Of harbor's three accepted truthy values — `true`, `1`, `yes` — `1`
destroys every digit and `true` destroys every JSON boolean literal, so `yes` is
the only safe one.
