# ADR-0012 — Node model: structure, text and amendments

- **Status:** Accepted
- **Date:** 8 October 2026
- **Step:** S3

## Context

[ADR-0002](0002-identifiers.md) decided how nodes are identified.
[ADR-0001](0001-source-format.md) decided that Formex is the source of text,
structure and amendments. This record decides what a node *is*: which parts of
the act become nodes, what text each node carries, how the amendments the
consolidated text records are attached to nodes, and what happens to deleted
provisions.

Four properties of the source shape the decision:

1. **The consolidated text keeps deleted provisions.** Article 10(5), Annex I
   Section A point 1, Annex VIII Section B points 7 and 9 are still there, with
   their 2024 text, between a `DELETED` marker and its closing marker.
2. **Amendment markers are not aligned with elements.** They are processing
   instructions that may open in one element and close in another: in Article
   58(1) the marker covers the label of the paragraph and the introduction of
   its first subparagraph, not its points.
3. **Some amendments are implicit.** When the Omnibus inserts a point, the
   consolidation changes the punctuation of the point before it ("; and" to
   ";"). The amending act does not state this; the marker says `IMPLICIT`.
4. **Quoted provisions look like structure.** The Omnibus quotes whole articles
   and paragraphs, and an annex in a separate file, inside `QUOT.S`.

## Decision

### What becomes a node

| Formex | Node type | Segment | Identifier basis |
|---|---|---|---|
| the document | `act` | — (the CELEX number itself) | source |
| `DIVISION` | `chapter`, `section` | `cpt_`, `sct_` | source (label, checked against EUR-Lex) |
| `ARTICLE` | `article` | `art_` | source (`IDENTIFIER`, checked against the label) |
| `PARAG` | `paragraph` | `para_` | source (`IDENTIFIER`, checked against the label) |
| `ALINEA` | `subparagraph` | `subpara_` | position |
| `ITEM` with a label | `point` | `point_` | label |
| `ITEM` without a label | `indent` | `indent_` | position |
| `NP` directly in an annex or annex section | `point` | `point_` | label |
| `ANNEX`, `CONS.ANNEX` | `annex` | `anx_` | source (label, checked against EUR-Lex) |
| `GR.SEQ` | `section` | `sct_` | label |
| `TBL` | `table` | `table_` | position |
| `CONSID` | `recital` | `rct_` | source (label, checked against EUR-Lex) |
| `VISA` | `citation` | `cit_` | source (position, checked against EUR-Lex) |

This extends ADR-0002 with two things it left open: the root node, whose
identifier is the CELEX number of the act, and the `table` segment, named after
the Akoma Ntoso element.

The parent of an article is its chapter or section, although its identifier
does not include them (`art_6`, as in EUR-Lex). Everything else hangs from the
act.

**Not modelled in v1:** the formulae of the preamble ("THE EUROPEAN PARLIAMENT
AND THE COUNCIL…", "Whereas:", "HAVE ADOPTED THIS REGULATION:"), the final part
(the binding clause, the place, the date, the signatures) and the publication
metadata. They identify no provision and are not cited.

### Text

- **Every node carries its full text**, children included: Article 6(3) is the
  whole paragraph, points and all, because that is what a citation of it refers
  to. The act, its chapters and its sections carry none: their text is that of
  their articles.
- **One block per line.** A child reads inside its parent's text as
  `compose_block` writes it: the label opens the first line (`(a) the AI system
  …`), or, when there is a heading, label and heading form a line of their own
  (`Section A List of Union harmonisation legislation`). The rule is a public
  function, and the tests check that every child's block is a run of lines of
  its parent's text.
- **Label and heading are separate fields**, as printed in the node's language
  (`Article 4a` / `Articolo 4 bis`; `(a)` / `a)`).
- **Footnotes are separate** (`notes`), in order, and not part of `text`.
- **Quoted provisions are text**, never structure, including an included file.
  A quoted paragraph keeps its label on the line of its text (`‘13. For
  high-risk AI systems …’;`).
- **Tables** are one node; each row is a line, cells separated by ` | `.
- **Rendering of Formex conventions**, as the Official Journal prints them:
  quotation marks from their declared `CODE`; numbers marked `FT TYPE="NUMBER"`
  grouped by thousands from five digits (`35 000 000`); superscript and
  subscript as `^25` and `_2`, because `1025` is not `10^25`.
- **Normalisation is minimal**: Unicode NFC, invisible characters removed,
  whitespace collapsed. Unlike the canonical form (ADR-0006), quotes, dashes and
  apostrophes are kept as printed: this is the text people read and quote. Typos
  of the source stay (`persona fisica,quali`).

### Amendments

- Read from the `CLG.MDFO`/`CLG.MDFC` markers only, never inferred.
- **Tracked on the text, not on elements.** Every piece of text carries the set
  of markers open where it stands. A node is amended:
  - **whole**, when the marker is open over all of its content: the inserted
    Article 4a and everything in it; the replaced first subparagraph of Article
    25(4);
  - **in part**, when the marker covers some of its *own* content — its label,
    its heading, or text that belongs to no child: Article 75, whose heading was
    replaced; Article 58(1), whose label and introduction were.

  A paragraph into which a point is inserted is not marked: the point is.
- Each amendment records the action (`replaced`, `inserted`, `deleted`), the
  amending act (`ACTIVE.DOC`), the location in it as the source writes it
  (`ACTIVE.LOC`, `AR:1;PT:23;PT:b`) and whether it is implicit.

### Deletions

- **A node wholly covered by a deletion is kept, without text**: same
  identifier, its printed label, the amendment, `deleted: true`. Its children
  are not emitted. A citation of Article 10(5) must be answered "deleted by
  Regulation (EU) 2026/1744", not "not found".
- **Its text is removed from its ancestors.** Article 10 reads 4, then 6.
- **Positional identifiers count it**: a deleted indent keeps its place, so the
  following ones keep their identifiers.
- Deleted text inside a node is removed from the text, and the node is amended
  in part. A node whose content was all deleted has an empty text; a node with
  no content in the source is an error.

### Refusals

The parser fails, naming the place in the source, on: an element where
structure is expected and no rule exists; text between structural elements; a
label no rule recognises (ADR-0002); a label that disagrees with the
`IDENTIFIER`; an unknown processing instruction; a marker with unknown
attributes or values, opened twice, closed without being open or never closed;
an amendment of an amendment (`MOD.LEVEL` other than 1); structure hidden inside
an inline element; a duplicate identifier; an unsupported Formex schema; a file
of the bundle no document refers to.

### Provenance

The parser is a function of the bytes. A document loaded from the cache
records where they came from (work, manifestation, URL, retrieval time, SHA-256
of the payload and of its canonical form, from the lock). Whether the export
repeats it on every node is decided in S7.

## Evidence

Measured on 8 October 2026 on the six locked Formex manifestations:

| Work | Nodes | Articles → points | Time |
|---|---|---|---|
| Consolidated text `02024R1689-20260727` | 2 144 | 1 859 | 0.12 s |
| Base act `32024R1689` | 2 119 | 1 665 | 0.15 s |
| Omnibus `32026R1744` | 167 | 109 | 0.03 s |

- **Counts match the S4 measurement.** 1 665 base act nodes from articles to
  points, as in ADR-0002. The consolidated text has 1 859: the 1 866 of
  ADR-0002, less the subparagraph and six points of the deleted Article 10(5).
- **English and Italian have identical structure**: identifiers, types,
  parents, amendments and order coincide in all three works.
- **Inherited identifiers exist in EUR-Lex, and EUR-Lex has no other**: 162
  checked for the consolidated text (its XHTML has no paragraph identifiers, so
  its 553 paragraph references cannot be checked there), 842 for the base act
  (paragraphs, recitals and citations included), 58 for the Omnibus.
- **No word is lost or added.** For every article, annex, recital and citation,
  the words of the node equal the words of the source element, extracted by an
  independent walk that only removes footnotes and deleted ranges: 359 039
  words.
- **All 77 markers of the consolidated text land on nodes**: 4 deletions
  (exactly the four provisions above), 310 nodes amended.
- **33 golden nodes** were read against the XHTML of the same work and
  language. The differences are those ADR-0006 lists: the XHTML loses the
  superscript of `10^25`, shows a deletion as its marker followed by a rule,
  and lays tables out differently.
- **Generated documents** (Hypothesis, 150 examples per property) keep the
  invariants: unique identifiers, parents before children, composition, no word
  lost, amendments on the nodes they wrap, deletions applied.

## Consequences

**Positive**

- A node is self-contained: a citation, a retrieval system or a diff can use
  one node without reassembling its subtree.
- Changes propagate: a changed point changes the text, and the hash, of every
  ancestor up to the article. "Has Article 6 changed?" has an answer.
- Deleted provisions can be cited and answered.
- The amendment attached to a node is the one the Publications Office recorded,
  with its location in the amending act.

**Negative**

- Text is repeated at every level: the dataset is several times the size of the
  act. Acceptable at this size (a few megabytes per language).
- `compose_block` loses the separator between an annex section label and its
  heading (`Section A — Information …` reads `Section A Information …` in the
  annex's text). It is presentation; the heading field keeps the words.
- "In part" depends on where the consolidation placed its markers. The Article
  25(4) marker starts before the paragraph number, so the paragraph is amended
  in part although only its first subparagraph was replaced. The model reports
  the source faithfully rather than second-guessing it; S8 verifies the markers
  against the XHTML.
- The list of what is not modelled is a choice. The binding clause of the final
  part is legal text that is not in the dataset.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| Only the node's own text (intro, own words), full text assembled by the reader | Every consumer would reimplement composition; a citation of a paragraph would not have its text |
| Drop deleted nodes | A citation of a deleted provision would look like a citation of nothing |
| Keep the deleted text, flagged | The consolidated text in force does not contain it; the base act already does |
| Attach markers to the elements they wrap | Wrong for markers that cross elements (Article 58(1)) and for implicit punctuation changes inside a text |
| Text from the XHTML | It loses superscripts and drops deleted labels; Formex is the source (ADR-0001) |
| Fold typography as the canonical form does | That form exists to compare; this text exists to be read and quoted |
