# ADR-0013 — Dataset format and release

- **Status:** Accepted
- **Date:** 11 October 2026
- **Step:** S7 (with the language parity of S6)

## Context

The dataset is the artefact this project exists to produce: what a program
depends on, pins and cites. [ADR-0012](0012-node-model.md) decided what a node
is and left one question to this step: whether the provenance of the source is
repeated on every node. Four requirements shape the answer:

1. **Re-derivable.** The dataset must be a function of the locked sources
   ([ADR-0010](0010-cache-and-lock.md)) and of the version of this package,
   byte for byte, so that anyone with the lock can verify it.
2. **Readable diffs.** Between two versions of a file, a reader must see the
   provisions that changed and nothing else.
3. **Checked before published.** A dataset in which an identifier does not
   exist in EUR-Lex, or a citation resolves in one language and not the other,
   must not exist.
4. **Attributable.** CC BY 4.0 requires attribution and an indication of
   changes, and the project promises that attribution can be reconstructed per
   node.

## Decision

### Files

| File | Content |
|---|---|
| `<work>.<language>.jsonl` | The nodes of one work in one language: `32024R1689.ita.jsonl`, `02024R1689-20260727.eng.jsonl` |
| `manifest.json` | Format version, generator, dataset version, licence, attribution, every file with its SHA-256, the sources with URL, retrieval time and SHA-256, the checks passed |
| `sources.lock.json` | The lock entries of every source used, so that `eucite fetch --frozen --lock sources.lock.json` restores them |
| `README.md` | What the files are, the fields, how to derive the dataset again, the attribution notice, the disclaimer in English and Italian |
| `LICENSE` | The data licence, with the indication of changes |

### Lines

- One JSON object per line, one line per node, **in document order**. The line
  is the position: there is no `order` field.
- **Fields in a fixed order**, identifier first: `id`, `type`, `parent`,
  `label`, `heading`, `text`, `notes`, `amendments`, `deleted`,
  `id_provenance`, `id_basis`, `source_ref`, `text_sha256`, `work`, `language`.
  Every key is always present.
- UTF-8 without escapes, compact separators, `\n` after every line.
- **Provenance by reference.** Each line names its `work` (CELEX) and
  `language`; the URL, retrieval time and checksums of that source are in the
  manifest and the lock. Nothing on a line changes when the source is fetched
  again or another node changes.

The plan said "sorted by identifier, keys sorted". Both choices are only as
deterministic as the two adopted here, and worse for a reader: identifiers do
not sort in reading order (`art_10` before `art_2`), and sorted keys put
`amendments` before `id`.

### Checks before writing

`eucite dump` parses every language of every selected work, even when it
writes only one language, and writes nothing unless:

- every inherited identifier is found among the identifiers of the XHTML of the
  same work and language, and every EUR-Lex identifier of the levels this
  project inherits belongs to a node (`eucite.crosscheck`, ADR-0012);
- the languages are in **parity** (`eucite.parity`, S6): the same nodes in the
  same order, with the same type, parent, identifier provenance and basis,
  source reference, amendments, deletion, number of footnotes, and the same
  shape of text — label, heading and text present or absent alike, the same
  number of blocks. Labels, headings and texts are the only things allowed to
  differ. A divergence is reported with the node and the value in each
  language, never repaired.

The manifest records what was checked.

### Determinism and round trip

- Nothing in the output records when or where it was built. The same lock and
  the same version of the package give the same bytes; CI builds the dataset
  twice, in two processes with different hash seeds, and compares.
- `eucite dump --out DIR --check` derives the dataset again and reports any
  file that differs: the round trip from the locked sources to a published
  dataset. The README of the dataset gives the two commands, with the lock it
  ships.
- `read_dataset` and `read_nodes` read a dataset back into nodes, verifying the
  checksum of every file against the manifest and the text of every node
  against its `text_sha256`.

### Writing and archiving

- The dataset is written beside its destination and moved into place, so an
  interrupted write leaves the previous dataset intact. A directory that exists
  and holds no `manifest.json` is never overwritten.
- `--archive` writes a reproducible `.tar.gz`: entries sorted, no owner, the
  time of the latest source retrieval, no time in the gzip header.

### Versions

The three axes of the plan are each recorded: the version of the law is the
`work` of each file; the version of the dataset is `dataset_version` in the
manifest, given when a release is built; the version of the package is
`generator`. `format` (currently 1) changes when a line changes shape.

## Evidence

Measured on 11 October 2026 on the locked sources:

- Six files, 9.2 MB in all (2.0–2.2 MB for the base act and the consolidated
  text in each language, 0.4 MB for the Omnibus), built in under a second.
- 2 124 inherited identifiers found in EUR-Lex; 1 106 paragraph references not
  checkable, because the consolidated XHTML has no paragraph identifiers. The
  three works in parity: 2 119, 2 144 and 167 nodes in each language.
- Two builds in two processes with different hash seeds: identical files and an
  identical archive. Every file reads back to the nodes the parser produced.
- On generated sources: changing one word of a point changes the lines of that
  point and of its three ancestors, nothing else; inserting a point adds one
  line and changes its ancestors.
- One Italian point removed from the real consolidated text: the parity check
  fails and names it.

## Consequences

**Positive**

- A published dataset can be verified by anyone with the lock, and is known to
  have passed the cross-check with EUR-Lex and the language parity.
- Diffs show what changed, provision by provision.
- A consumer can load one file, or all of them, without the library: one JSON
  object per line, the same keys everywhere.

**Negative**

- A node taken alone carries its work and language but not the URL or the
  retrieval time of its source; those are one lookup away, in the manifest.
  The licence and the README say so.
- Because every node carries the text of what it contains, a change in a point
  also changes the lines of its paragraph, subparagraph and article.
- The archive is reproducible with the same compression library; the manifest
  checksums, which do not depend on it, are the reference.
- The data licence exists twice, at the root of the repository and inside the
  package that ships it; a test keeps them identical.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| A provenance block on every node (URL, retrieval time, checksums) | Every line would change whenever a source is fetched again, even when no word changed |
| Lines sorted by identifier | Not reading order; no more deterministic than document order |
| An `order` field | Inserting one node would change the line of every node after it |
| One file for the whole corpus | A consumer of one language or one version would have to filter; per-file checksums would say less |
| Parquet or a database | Not diffable, not readable without tools; can be derived from the JSON lines |
| Shipping the raw sources in the release | The lock and Cellar suffice today; reconsider if Cellar stops serving a version the dataset was built from |
