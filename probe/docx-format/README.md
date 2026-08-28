# docx-format

## Difficulty explanation

The agent is given a rendered page and no source document, and has to rebuild
the page's visual treatment around different content. Every quantity it needs —
figure size, where a callout mark sits, how far its letter stands from the
figure, how a heading is dressed, where the page furniture runs — exists only as
pixels in `template.pdf`. Measuring them is mechanical; the difficulty is that
several of them are *relationships*, not coordinates, and a layout engine
reproduces whichever of the two the author encoded.

That is where both frontier agents fail, and they fail differently. Claude Code
measures the callout letter's position in the template and reproduces it as an
absolute coordinate: across three runs it parked both letters in the same
right-margin column, x = 1124–1174, while its own figures landed elsewhere,
leaving the letter 119–230 px from the picture it labels against a 90 px
tolerance. Vertical alignment was exact in every case, so the geometry is
understood and only the anchor is wrong. Codex does not place the letters at
all, and additionally squares both photographs, drops the frame around the first
one, and in one run lays a figure over body text.

The second source of difficulty is the requirement that the document render the
same in more than one word processor. Output that relies on a theme default
looks correct in whatever the agent tested with and changes appearance in the
reader's. Two of five runs produced exactly that: a left bar starting 22 px
apart under two engines, and a heading set in dark ink by one and light by the
other because the document never states the colour.

Measured: reward 0 in 3 of 3 Claude Code runs (`claude-opus-5`, effort max) and
2 of 2 Codex runs (`gpt-5.6-sol`, xhigh). Every run got all six required strings
onto the page, the name into the footer, the placeholders removed and the
figure/caption ordering right, so the failures are not comprehension of the
brief. Two earlier drafts of this task were solved outright by Claude Code; the
tests below are what closed them.

## Solution explanation

Read the layout off the template rather than eyeballing it: extract the text
boxes and the connected colour components from `template.pdf`, which yields the
banner, the left bar, the footer bar, the frame around each figure, the red
detail mark, the orange leader and the letter box, each as a rectangle.

Then encode the relationships those rectangles express, not the coordinates they
happen to have. The letter belongs beside the figure it labels, so it has to be
anchored to the figure — placing it at the template's absolute x is the trap.
The frame hugs the image, so it is a border on the picture, not a separate
floating box. The left bar starts below the banner. Each photograph keeps its
source aspect ratio; the replacements have different aspect ratios from the
placeholders, so the box has to be recomputed rather than reused.

Finally, state everything the renderer would otherwise choose. Every colour,
every font size, every position that matters must be written into the document,
because anything left to a theme default is decided by the reader's word
processor and the two engines disagree. The reference document is built by hand
this way; `solution/solve.sh` copies it into place.

Estimated at 6 hours for an expert.

## Verification explanation

`tests/test_state.py` grades the rendered page, never the OOXML. It converts
`/app/output.docx` to PDF and does arithmetic over pixels — which colours
appear, where their connected components sit, which box contains which — so a
document that renders correctly passes however it was built. There is no credit
for structure that a reader would not see, and no penalty for building it with
an unusual toolchain.

None of the expectations are hand-written constants. The same profile extractor
runs against the input template and against the submitted output, and the two
are compared. Swapping the template swaps the expectations with it, which is
what makes the task about reading a layout rather than about matching numbers
someone typed into a test file.

The verifier image installs **two independent, pinned renderers**: Debian's
`libreoffice-writer` and a self-contained AppImage build of a much later
version. Several assertions run under both and require them to agree. A document
whose appearance changes between engines has not determined its own appearance,
and that property is invisible from a single rendering — it is the failure this
domain is actually about.

23 tests; the reward is binary and all 23 must pass. `solution/` is mounted only
for the oracle agent, and the verifier runs in a separate environment after the
agent's container is torn down, so neither the reference document nor the reward
file is reachable from the agent's workspace.

## Relevant experience

I build and ship LLM systems for legal research, contract review and document
analysis at SG LAW LLP, over confidential material. A formatted evidence
report — a title, a name that has to appear in the footer as well as the body,
numbered subsections, screenshots with callouts pointing at the detail that
matters — is an ordinary deliverable there, not a synthetic exercise. This task
is that document, and its placeholder content is deliberately the real thing:
`Evidências de ocorrencia`, `Print da falha`, a dialog title and a clock face
called out as Detalhe A and Detalhe B.

That work is also where the verification stance comes from. Model output in that
setting is checked against counsel review, so the question is never "does this
look plausible" but "does a deterministic check confirm it". The same discipline
shapes the tests here: nothing in `test_state.py` judges appearance and nothing
inspects the OOXML; every assertion is arithmetic over the pixels of the
rendered page, and the expectations are extracted from the template rather than
typed in by hand, so the grader cannot be argued with and does not encode my
own idea of what the layout should be.

The two-renderer requirement comes from the same place. A document that only
looks right in the word processor its author happened to open is a defect that
surfaces at the reader, which is a failure mode I have had to care about with
documents that get filed.

Background: PhD in Operations Research (UNIFESP/ITA, 2021) and production Python
since 2019 — optimization engines at Nitryx/Progress Rail, backend team lead at
Optibus, modelling at Banco Safra and Porto Seguro. The measurement habit the
tests rely on is from that side of the work.
