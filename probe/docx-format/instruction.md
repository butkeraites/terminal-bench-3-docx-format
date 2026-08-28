`/app/assets/template.pdf` is a one-page report, rendered. It is the only
specification of the layout you have: there is no source document to copy from,
so everything about how it looks has to be inferred from the page itself and
rebuilt.

Its body carries placeholder content — a title, a name, two numbered
subsections, two photographs, and, over each photograph, a mark calling out a
detail, a leader pointing from that mark to a large letter, and a caption
referring to it.

Produce `/app/output.docx`: an editable Word document that **applies the same
visual treatment** to this content instead.

- Title: `Evidências de ocorrencia`
- The name, in the body **and** in the footer: `Usuário 123.3345`
- First subsection heading: `Print da falha`
- Second subsection heading: `Evidência do tempo`
- First caption: `Reconhecimento de Fala (Detalhe A) é importante e foi o que
  bloqueou a reunião.` — with `Reconhecimento de Fala (Detalhe A)` in red.
- Second caption: `A hora 6pm (mostrada no Detalhe B) marca o acontecimento do
  evento` — with `hora 6pm (mostrada no Detalhe B)` in blue.

The first photograph is replaced by `/app/assets/Picture1.png`, a screenshot of
a Windows error dialog; the detail it calls out is the dialog's title text
`Reconhecimento de Fala`. The second is replaced by `/app/assets/Picture2.png`,
a screenshot of a clock; the detail it calls out is the time `6:00 PM`.

Nothing else is specified. How large a figure is, where its callout sits, where
its letter goes, how a heading is dressed, where the page furniture runs — all of
it is in the template, and your output is judged on whether a reader would take
the two pages as the work of the same hand.

Your document must also be unambiguous: it will be opened by more than one word
processor, and every one of them must show the same page.

You have 4 CPUs. You have network access.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
