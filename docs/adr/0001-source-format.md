# ADR-0001 — Source format for acquisition

- **Status:** Accepted
- **Date:** 8 October 2026
- **Step:** S0
- **Revisions:**
  - Replaces an unpublished draft of 8 August 2026, which chose XHTML because
    Formex appeared to be unavailable. That conclusion came from a malformed
    request (Evidence §1).
  - Revised again on 8 October 2026, during S2. The first version of this record
    stated that Formex carries no per-block amendment markers. It does, as
    processing instructions (Evidence §3); the analysis had looked only at
    elements. With the markers in Formex, the role of the XHTML changes.

  Both mistakes are recorded because both are easy to repeat.

## Context

The project needs the text of Regulation (EU) 2024/1689 in a form from which the
structure — chapters, articles, paragraphs, subparagraphs, points, annexes,
recitals — can be rebuilt reproducibly. It needs it for three works:

| Work | CELEX |
|---|---|
| Base act, as published in the Official Journal | `32024R1689` |
| Consolidated text in force | `02024R1689-20260727` |
| Digital Omnibus on AI, the amending act | `32026R1744` |

It also needs the amendment markers that tell which block of the consolidated
text comes from which act. Those markers are the ground truth used to validate
the amendment diff (S8).

## Evidence

All requests were made against `publications.europa.eu` on 8 October 2026.
Content negotiation on Cellar requires **both** `Accept` **and**
`Accept-Language`: omitting the latter returns `HTTP 400`.

### 1. Formex is available, as a bundle

```bash
B=http://publications.europa.eu/resource/celex/02024R1689-20260727

curl -s -o /dev/null -w "%{http_code}\n" -L \
  -H "Accept: application/xml;type=fmx4" -H "Accept-Language: eng" "$B"
# 404

curl -s -o fmx.zip -w "%{http_code} %{content_type}\n" -L \
  -H "Accept: application/zip;mtype=fmx4" -H "Accept-Language: eng" "$B"
# 200 application/zip — about 108 KB, two files: the act and its descriptor
```

A Formex manifestation is a bundle of files, so it is negotiated as a zip
(`application/zip;mtype=fmx4`; `application/list;mtype=fmx4` lists the files).
The bundle's size depends on the work: the consolidated text has 2 files (the
act and its descriptor), the Omnibus 4, and the base act 16 — the enacting
terms, one file per annex, a table of contents and a descriptor
(`*.doc.xml` or `*.doc.fmx.xml`) that lists the others. A reader that opens
only the largest file silently loses the annexes of the base act.
The single-document form `application/xml;type=fmx4` returns 404. The August
draft tried only the latter and concluded that Formex did not exist for this
act. The Cellar branch notice of the consolidated text lists `fmx4` among its
manifestations in every language: reading the notice first would have caught
the error.

Same result for `32024R1689` and `32026R1744`, in English and in Italian. The
files declare the Formex schema 06.02.1 (`formex-06.02.1-20231031`).

### 2. Formex carries identifiers down to paragraph level

| | Consolidated | Base act | Omnibus |
|---|---|---|---|
| `ARTICLE` with `IDENTIFIER` | 119 (`006`, `004A`) | 113 | 11 |
| `PARAG` with `IDENTIFIER` | 562 (`006.003`, `006.001A`) | 509 | 98 |
| Recitals (`CONSID`) | 0 | 180 | 47 |

Paragraphs inserted by the Omnibus carry a letter suffix (`006.001A`,
`006.001B`), the same convention EUR-Lex uses for inserted articles (`art_4a`).

Below paragraph level the structure is **explicit in the markup** but carries no
identifier: subparagraphs are `ALINEA` elements, lists are `LIST` with a `TYPE`
(`alpha`, `ARAB`, `DASH`, …), points are `ITEM` with their label in `NO.P`.

Nine `PARAG` elements sit inside quoted text (`QUOT.S`) in Articles 107–109,
which amend other regulations. They reuse the identifiers of those regulations
and produce six apparent duplicates. Excluding quoted text, the consolidated
act has 553 paragraph identifiers, all unique.

The identifier sets are identical in English and Italian for all three works.

### 3. Formex marks every amendment, as processing instructions

The consolidated Formex (root `CONS.ACT`) wraps each amended block in a pair of
processing instructions:

```xml
<?CLG.MDFO ID="O001001M013000" IDREF="C001001M013000" ACTION="DELETED"
  LEVEL="STRUCTURE" COMMAND="EXPLICIT" ACTIVE.DOC="32026R1744"
  ACTIVE.LOC="AR:1;PT:9;PT:b" MOD.LEVEL="1"?>
<PARAG IDENTIFIER="010.005"> … </PARAG>
<?CLG.MDFC ID="C001001M013000" IDREF="O001001M013000"?>
```

There are 77 such pairs in each language: 48 `REPLACED`, 25 `INSERTED`,
4 `DELETED`, all from `32026R1744`. Each names the exact provision of the
amending act that made the change: `AR:1;PT:9;PT:b` is Article 1, point (9)(b)
of the Omnibus, which reads "paragraph 5 is deleted".

Two properties matter:

- **Deleted text stays in place, marked.** Article 10(5), point 1 of Annex I
  Section A, and points 7 and 9 of Annex VIII Section B are present in the
  consolidated Formex with their 2024 text, each after a `DELETED` marker.
  Reading the Formex without the markers yields provisions that are no longer in
  force.
- **Processing instructions are easy to lose.** A parser configured to drop
  them, or an analysis that iterates over elements only, sees no marker at all.
  That is how the first version of this record missed them.

The XHTML marks the same amendments at a coarser grain — 129
`<p class="modref">` elements: 65 `▼M1`, 60 `▼B`, and 4 `▼M1` followed by a
rule where text was deleted — and removes the deleted text.

### 4. XHTML identifiers stop at article level in the consolidated text

The consolidated XHTML exposes 284 structural identifiers — `art_` (including
`art_4a`, `art_60a`, `art_75a`–`art_75d`), `cpt_`, `cpt_*.sct_`, `anx_`,
`tit_`, `enc_`, `fnp_` — and none below article level. The base act XHTML also
exposes its 509 paragraphs, with the Formex identifiers as `id` (`006.003`).

The August draft counted 306 structural identifiers in the consolidated XHTML.
Cellar regenerated the consolidated manifestations on 11 August 2026; the cause
of the difference cannot be reconstructed, because the bytes measured in August
were not kept.

### 5. What EUR-Lex offers as "XML" is not the text

`https://eur-lex.europa.eu/legal-content/EN/TXT/XML/?uri=CELEX:32024R1689`
returns the Cellar metadata notice (`<NOTICE type="branch">`), not the normative
text.

## Decision

**Two manifestations are acquired for every work and language. Formex is the
source of everything published; XHTML is the independent check.**

1. **Formex is the primary source** — `Accept: application/zip;mtype=fmx4`. It
   provides the text, the whole structure (articles, paragraphs, subparagraphs,
   points, annexes, recitals) and the amendment markers, with the exact
   provision of the amending act behind each change.
2. **XHTML is the verification source** — `Accept: application/xhtml+xml`. It
   is used for:
   - the EUR-Lex fragment identifiers (`art_6`, `cpt_III`, `anx_III`,
     `rct_58`), to check that every identifier this project calls inherited
     exists in the source and resolves on EUR-Lex;
   - an independent rendering by the same publisher: its text, its `▼M1`/`▼B`
     markers and its deletions must agree with what is read from Formex.
3. **Languages are a request parameter**: `Accept-Language: ita` and `eng` in v1.

Direct consequences for the technical choices:

1. **Formex is parsed with `lxml` in XML mode**, with entity resolution and
   network access disabled and **processing instructions kept**. XHTML is parsed
   with `lxml` in HTML mode.
2. **Inherited identifiers reach paragraph level**, not article level. How
   identifiers are written, and how the levels below paragraph are identified,
   is the subject of [ADR-0002](0002-identifiers.md).
3. **Quoted text is never structure.** Text inside `QUOT.S` belongs to the node
   that quotes it.
4. **Deletions are applied, not ignored.** A block after a `DELETED` marker is
   not part of the text in force, though it remains in the source and in the
   diff.
5. **The cache keeps the raw payloads**, keyed by `(celex, lang, accept)`. The
   306 → 284 discrepancy above cannot be explained only because the August bytes
   were lost.
6. **Drift detection cannot compare response bytes** of either manifestation; a
   canonical form is required ([ADR-0006](0006-canonical-form.md)).

## Consequences

**Positive**

- The main technical risk of the plan — "everything below article level depends
  on our parsing" — shrinks. Paragraphs are inherited; subparagraphs and points
  are explicit elements, not inferred from text. ADR-0002 records the
  measurement.
- Amendments come with their source: every change in the consolidated text
  points to the provision of the Omnibus that made it.
- Text, structure and markers come from one manifestation, so nothing has to be
  aligned across manifestations to attach a marker to a paragraph.
- Two renderings from the same publisher allow cross-checks: the article sets
  must coincide, the texts must agree after canonicalisation (measured in
  ADR-0006), and the `▼M1` markers must fall where the Formex markers are.

**Negative**

- Two parsers and two payloads per work and language: twelve payloads for v1.
- The amendment markers are processing instructions, a mechanism the parser
  must preserve explicitly. A test asserts that they survive parsing, and the
  canonical form keeps them, so their disappearance upstream would be reported
  as a change.
- Deleted provisions are present in the source text. Every consumer of the
  consolidated Formex must honour the `DELETED` markers; this project does it
  once, in the parser.
- The Formex schema evolves. The parser checks the declared schema version and
  fails loudly on an unknown one, rather than parsing it on trust.
- If the Publications Office publishes this act in AKN4EU, this decision must be
  revisited.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| XHTML alone (the August draft) | No structure below article level in the consolidated text: paragraphs and points would have to be recovered from text and CSS classes |
| Formex alone | Would provide everything published, but would leave the inherited identifiers unchecked against EUR-Lex and remove the only independent check on the text |
| XML from EUR-Lex | Not the text — Cellar metadata |
| Official Journal PDF | The authentic manifestation, but structure would have to be recovered from layout |
| Scraping EUR-Lex HTML pages | Same content as the Cellar XHTML, wrapped in site chrome and without explicit content negotiation |
| Reusing a third-party dataset | The ones examined in October 2026 are built on the 2024 text only, without the Omnibus. Depending on someone else's copy would reintroduce the problem this project exists to solve |

## References

- Formex 06.02.1 schema, Publications Office of the European Union
- Commission Decision 2011/833/EU on the reuse of Commission documents
- EUR-Lex legal notice: consolidated texts are EU editorial content licensed
  under CC BY 4.0
