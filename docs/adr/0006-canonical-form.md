# ADR-0006 — Canonical form and drift detection

- **Status:** Accepted
- **Date:** 8 October 2026
- **Step:** S2

## Context

The source lock ([ADR-0010](0010-cache-and-lock.md)) records the SHA-256 of each
payload. A changed hash says the bytes changed. It does not say whether the law
did.

Cellar changes bytes for reasons unrelated to the law. It regenerated the
consolidated manifestations on 11 August 2026 (`Last-Modified` in the lock)
with no new amending act. A drift detector that compares bytes raises an alarm
on every such regeneration. It gets switched off within a month, and then it
misses the change that matters.

Three later steps need the same distinction: drift detection (S9) to decide
whether to break the build, the node hashes (S3), and the amendment diff (S8).
They need one definition of "the content" — written down, versioned, and
tested in both directions: presentation must not change it, content must.

## Decision

**Every payload has a canonical form: a sequence of JSON lines, one per block of
content, in document order, preceded by a header that names the version of the
rules. The canonical hash is the SHA-256 of that text.** The form is
line-oriented on purpose: two forms can be diffed, so a reported change can be
shown, not just signalled.

### Governing rule: in doubt, it is content

Only what is *known* to be presentation or publication metadata is discarded,
by explicit lists. An element, attribute or processing instruction that nobody
has classified is kept. A false alarm costs a review; a missed change defeats
the purpose of the project.

### Text

Applied to every piece of text, in both manifestations:

1. Unicode NFC.
2. Remove invisible characters: soft hyphen, zero-width space, zero-width
   (non-)joiner, word joiner, byte-order mark.
3. Fold typographic variants: single quotes and apostrophes to `'`; double
   quotes and guillemets to `"`; hyphen and dash variants (including the minus
   sign) to `-`; the ellipsis to `...`.
4. Collapse every run of whitespace — including no-break, thin and figure
   spaces — to one space; trim.
5. No space before closing punctuation (`, . ; : ! ? ) ]`) or after an opening
   bracket.

Case is kept.

### Formex

- **One logical document per bundle.** Documents are read in the order of the
  descriptor (`DOC.MAIN.PUB`, then each `DOC.SUB.PUB`); a file referenced by
  `INCL.ELEMENT` is read where the reference stands. File names, the number of
  files, member order and every zip-level detail are therefore not in the form.
  An XML file that is neither listed nor included is kept, at the end, as
  `unreferenced`.
- **Discarded subtrees** — publication and production metadata:
  `BIB.INSTANCE`, `INFO.CONSLEG`, `INFO.PROD`; the descriptor and the table of
  contents.
- **Inline elements**, whose text joins the enclosing block: `HT`, `DATE`,
  `REF.DOC`, `REF.DOC.OJ`, `LINK`, `FT`, `IE`, `NO.P`, `NO.PARAG`, `TXT`. Their
  attributes either repeat the text (`DATE@ISO`) or are presentation
  (`HT@TYPE`). Labels (`NO.P`, `NO.PARAG`) are followed by a space.
- **Superscript and subscript are content.** `HT TYPE="SUP"` and `"SUB"` are
  kept as `^{…}` and `_{…}`: "10²⁵" is not "1025".
- **Quotation boundaries** (`QUOT.START`, `QUOT.END`) become `"`, whatever
  character the source declares.
- **Discarded attributes** — generated numbering, cross-file links, schema
  location: `xsi:noNamespaceSchemaLocation`, `ID.TITLE`, `REF.TITLE`, `NO.SEQ`,
  `NOTE.ID`, `NUMBERING`, `NUMBERING.CONTINUED`, `NUMBER.ORG`, `FILEREF`.
  Every other attribute is kept.
- **Processing instructions** — `PAGE` (page breaks) is discarded. Every other
  one is kept as a record with its pseudo-attributes. This matters: the
  consolidated text records each amendment as a `CLG.MDFO`/`CLG.MDFC` pair
  ([ADR-0001](0001-source-format.md)).
- **Records** carry the depth, the tag, the kept attributes and the text that
  belongs to the element itself. Text that follows a nested block is emitted
  after it (`#tail`), so document order is preserved.
- **The schema** declared by the main document is recorded next to the form but
  not hashed: a schema upgrade that changes nothing else is presentation.

### XHTML

This manifestation is used for EUR-Lex identifiers and as an independent
rendering ([ADR-0001](0001-source-format.md)). Its nesting and classes are
layout, so the form is flat:

- `head`, `script`, `style`, `noscript`, `template` are discarded.
- `id` records for structural identifiers only — EUR-Lex subdivisions
  (`art_6`, `cpt_III.sct_1`, `rct_58`) and Formex paragraph numbers
  (`006.003`). Generated identifiers (`id-<uuid>`, `d1e123-1-1`, anchors
  derived from file names) are not kept.
- `marker` records for amendment markers (`class="modref"`).
- `text` records for the text of each block, with the same normalisation.

### Versioning and storage

- `CANONICAL_VERSION` (currently 1) is part of the hashed header. Any change to
  the rules above bumps it; hashes of different versions are never compared.
- The lock records `canonical_sha256` and `canonical_version` for each source.
  A fetch fills in a missing or outdated canonical hash from the object store,
  without network.
- A refresh that brings different bytes with an unchanged canonical hash is
  reported as *presentation only*. The three outcomes of drift detection follow
  directly: same bytes → `unchanged`; different bytes, same canonical hash →
  `presentation-drift`; different canonical hash → `normative-change`. What S9
  does with each is decided there.

## Evidence

Measured on 8 October 2026 on the twelve sources in the lock:

- Each form is computed in under 200 ms. The consolidated text yields 4 102
  lines in both English and Italian, with the same 154 amendment instructions:
  structural parity is visible at this level already.
- **Formex and XHTML of the same work agree.** They are two independent
  renderings by the Publications Office. After canonicalisation, the words of
  the enacting terms and annexes line up for 97.2 % (English) and 98.4 %
  (Italian) of the consolidated text, and 94.8 % / 95.9 % of the base act. The
  differences examined all fall into five known categories, none of them a
  normalisation gap: the quotation style of definitions (`"` in Formex, `'` in
  the English XHTML); text deleted by an amendment, kept and marked in Formex,
  removed in XHTML; the position of footnotes; superscripts, which the XHTML
  text loses; digit grouping (`35000000` against `35 000 000`).
- The canonical hashes in the lock match what Cellar serves on the same day for
  all twelve sources (test marked `network`).
- Presentation variants that leave the hash unchanged, and content variants
  that change it, are listed in `tests/test_canonical.py`: 17 and 12 for Formex,
  9 and 5 for XHTML.

## Consequences

**Positive**

- Drift detection can tell a regeneration from an amendment, so it can stay
  switched on.
- A reported change can be shown as a diff of two forms.
- The Formex and XHTML agreement is a check this project can keep running: a
  disagreement outside the known categories points to a problem in one of the
  two renderings or in the parser.

**Negative**

- The lists of what is presentation are maintained by hand. A new kind of
  metadata upstream shows up as a false `normative-change` until it is
  classified. That is the intended failure mode, but it costs a review.
- The XHTML form ignores nesting: a block moved from one container to another
  is not detected there. Acceptable, because the XHTML is not the source of
  structure.
- Typographic folding is deliberate and lossy: a change from `"` to `'`, or from
  an en dash to a hyphen, is not detected. No such change can alter the meaning
  of a legal provision.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| Compare raw bytes | Alarms on every regeneration (11 August 2026) |
| Hash the text only, without structure | Moving a paragraph, changing an identifier or an amendment marker would go unnoticed |
| XML canonicalisation (C14N) | Normalises syntax, not presentation: italics, page breaks, note numbering and metadata would still count as changes |
| Allow-list of content elements | An unknown element would be ignored: the silent failure mode this project exists to avoid |
| Compare the parsed dataset instead | Ties drift detection to the parser: a parser bug and a change in the law would look the same |
