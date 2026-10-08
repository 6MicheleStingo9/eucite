# ADR-0002 — Inherited and derived identifiers

- **Status:** Accepted
- **Date:** 8 October 2026
- **Step:** S4 (gate before the sub-paragraph parser)

## Context

Every node of the dataset needs an identifier that is:

1. **the same in every language** — the Italian and English versions of a
   provision are one node in two expressions;
2. **the same in every version of the act**, as long as the provision is the
   same — this is what makes the amendment diff possible;
3. **honest about how far it can be trusted** — a consumer must be able to tell
   an identifier the source gives from one this project computes.

[ADR-0001](0001-source-format.md) established that Formex provides identifiers
down to paragraph level, and explicit markup without identifiers below it. S4 is
the gate that measures whether the levels below paragraph can be identified
deterministically, before any parser is written for them.

## Measurement

Run on 8 October 2026 against the Formex manifestations, with a throwaway
prototype that applies the scheme decided below.

**Consolidated text, articles down to points:**

| | English | Italian |
|---|---|---|
| Nodes | 1 866 | 1 866 |
| Unique identifiers | 1 866 | 1 866 |
| Articles · paragraphs · subparagraphs · points | 119 · 553 · 667 · 527 | 119 · 553 · 667 · 527 |
| Point labels: letters · numbers · roman · other | 395 · 76 · 56 · 0 | 392 · 74 · 56 · 5 |
| Deepest list nesting | 3 | 3 |

Findings:

1. **Articles and paragraphs are fully deterministic.** Their identifiers come
   from the source.
2. **Points are deterministic from their printed labels, with one
   language-specific convention.** The five points inserted by the Omnibus are
   labelled `(14a)`, `(14b)`, `(ba)`, `(bb)`, `(da)` in English and `14 bis`,
   `14 ter`, `b bis`, `b ter`, `d bis` in Italian. Without normalisation they are
   the only English/Italian divergences out of 1 866 nodes. The source already
   resolves the same case: EUR-Lex identifies "Articolo 4 bis" as `art_4a`, and
   Formex writes inserted paragraphs as `006.001A` in every language. Applying
   the same mapping removes every divergence.
3. **Subparagraphs are positional by nature.** They carry no number in the text,
   and the law cites them by position ("the second subparagraph"). 509 of 553
   paragraphs have a single subparagraph; 44 have between 2 and 7.
4. **The number of subparagraphs changes between versions.** From the base act to
   the consolidated text, six paragraphs went from one subparagraph to several or
   back — Article 25(2) went from one to four. A scheme that omitted the
   subparagraph when there is only one would change the identifier of every
   point in those paragraphs, although the points themselves did not change.
5. **Identity across versions holds.** Of the 1 665 nodes of the base act,
   1 663 keep the same identifier in the consolidated text; 203 nodes exist only
   in the consolidated text. The two that disappear are real structural changes:
   Article 4, a single unnumbered paragraph in 2024 that the Omnibus split into
   numbered paragraphs, and the second subparagraph of Article 56(6).
6. **Annexes are less regular.** Most use numbered points (`1.`, `(a)`);
   Annex VII uses decimal labels (`3.1.`); Annex II is a list of dashes without
   numbers; Annex XIV contains tables. Annex groups ("Section A", "1.
   Introduction") are needed in the path: without them, point labels collide in
   5 of the 14 annexes.
7. **Short citations are almost always unambiguous.** Citations usually skip the
   subparagraph ("Article 6(3)(a)"). Within a paragraph, point labels are unique
   across subparagraphs everywhere except Article 43(1), where `(a)` and `(b)`
   occur in two subparagraphs.

**Outcome of the gate: positive.** The level below paragraph is in scope for v1.
Unnumbered annex content is identified by position, and says so.

## Decision

### Shape

```
<act>/<path>
```

- `<act>` is the CELEX number of the **act represented** — `32024R1689` — not
  of the manifestation it was read from. The same provision has the same
  identifier in the base act and in the consolidated text; the version is
  recorded in `provenance.source_work`. The language is not part of the
  identifier either.
- `<path>` is a sequence of segments joined by `.`, the separator EUR-Lex itself
  uses (`cpt_III.sct_2`, `art_1.tit_1`). Each segment is `<name>_<number>`.

```
32024R1689/cpt_III.sct_1                      inherited
32024R1689/art_6                              inherited
32024R1689/art_6.para_3                       inherited    source: 006.003
32024R1689/art_6.para_1a                      inherited    source: 006.001A
32024R1689/art_6.para_3.subpara_2             derived      position
32024R1689/art_6.para_3.subpara_2.point_a     derived      label
32024R1689/art_3.subpara_1.point_14a          derived      label   (IT: «14 bis»)
32024R1689/anx_VIII.sct_b.point_3             derived      label
32024R1689/anx_VII.sct_3.point_3-1            derived      label   («3.1.»)
32024R1689/anx_II.indent_3                    derived      position
32024R1689/rct_58                             inherited
32026R1744/rct_12                             inherited
```

### Segment names: nothing invented

- **Where EUR-Lex names a level, its name is used:** `art`, `cpt`, `sct`,
  `anx`, `rct`, `cit`. Annex groups headed "Section" are sections, so they are
  `sct` too.
- **Where EUR-Lex is silent, the Akoma Ntoso naming convention is used**
  (OASIS LegalDocML, the standard AKN4EU builds on): `para`, `subpara`,
  `point`, `indent`.

### Numbers

| Level | Number taken from | Basis |
|---|---|---|
| Article, chapter, section, annex, recital | EUR-Lex identifier | source |
| Paragraph | Last component of the Formex `IDENTIFIER`: `006.001A` → `1a` | source |
| Point | Printed label, punctuation stripped, lower case: `(a)` / `a)` → `a`; `(iv)` → `iv`; `3.1.` → `3-1` | label |
| Annex section | Label in the heading: "Section B" / "Sezione B" → `b`; "3. …" → `3` | label |
| Subparagraph, indent | Ordinal position among siblings, from 1 | position |

Italian multiplicatives are mapped to letters, as EUR-Lex does for articles:
`bis` → `a`, `ter` → `b`, `quater` → `c`, `quinquies` → `d`, and so on. So
`14 bis` → `14a` and `b ter` → `bb`.

A label that does not match any rule is never guessed: the build fails and names
the node.

### Rules

1. **The subparagraph segment is always present**, even when a paragraph has
   only one (Finding 4). An article without numbered paragraphs has its
   subparagraphs directly below it: `art_3.subpara_1`.
2. **Quoted text is never structure** ([ADR-0001](0001-source-format.md)):
   paragraphs and points inside `QUOT.S` belong to the text of the node that
   quotes them.
3. **Tables are a single node in v1.** Rows and cells are not identified.
4. **Language parity is a build invariant.** The identifier sets of every
   language must coincide; a divergence fails the build and is never corrected
   silently (S6).

### What each node declares

| Field | Values | Meaning |
|---|---|---|
| `id_provenance` | `inherited` | The identifier is a transcription of one the source provides. `source_ref` holds it literally (`006.001A`, `art_6`), so it can be checked against EUR-Lex. |
| | `derived` | Computed by this project from explicit markup. |
| `id_basis` | `label` | Derived from the number printed in the text. Stable when the law inserts a sibling, because the law keeps labels and inserts `14a` rather than renumbering. |
| | `position` | Derived from position. Shifts if a sibling is inserted before it. |

### Citations are not identifiers

A citation such as "Article 6(3)(a)" omits the subparagraph; its identifier is
`art_6.para_3.subpara_2.point_a`. Resolving citations to identifiers is a
library function, not a property of the identifier. Where a short citation
matches more than one node — today, only within Article 43(1) — the resolver
reports the ambiguity and returns every candidate; it never picks one.

## Consequences

**Positive**

- The dataset covers paragraphs, subparagraphs and points in v1, with a
  declared guarantee for each.
- 1 663 of 1 665 base act nodes match the consolidated text by identifier alone.
  The amendment diff (S8) only needs text similarity for the remainder.
- A consumer who needs only verifiable identifiers can filter on
  `id_provenance = inherited` and still get paragraph granularity.

**Negative**

- Readable identifiers are a transcription, not a copy: `art_6.para_1a` instead
  of `006.001A`. The mapping is one-to-one and `source_ref` keeps the original,
  but it is code that must be tested.
- Positional identifiers (subparagraphs, indents) change when the law inserts a
  sibling before them. `id_basis` makes this visible; it does not prevent it.
- The Italian multiplicative mapping is a rule this project applies, borrowed
  from the source's practice for articles. A future act that uses a convention
  outside the mapping fails the build until the rule is extended.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| Stop at article level (the "negative outcome" the plan allowed for) | The measurement does not justify it: sub-paragraph structure is explicit and deterministic |
| Formex identifiers verbatim (`006.001A`) as the public form | Verifiable but opaque to readers; kept as `source_ref` instead |
| Full Akoma Ntoso eIds (`art_6__para_3__point_a`, `rec_58`) | Would rename the levels EUR-Lex already names (`rct_` → `rec_`) and drop the separator EUR-Lex uses; adopted only for the levels EUR-Lex does not name |
| Omitting the subparagraph when there is only one | Breaks identity across versions (Finding 4) |
| Positional numbering for points | Labels exist and are what the law cites; position would shift on every insertion |

## References

- OASIS LegalDocML, Akoma Ntoso Naming Convention Version 1.0
- Formex 06.02.1 schema, Publications Office of the European Union
