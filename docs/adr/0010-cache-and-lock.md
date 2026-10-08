# ADR-0010 — Immutable cache and source lock

- **Status:** Accepted
- **Date:** 8 October 2026
- **Step:** S1

## Context

Everything this project publishes is derived from twelve payloads served by
Cellar: three works, two languages, two manifestations
([ADR-0001](0001-source-format.md)). The dataset is meant to be reproducible
byte for byte from those payloads, and a change in what Cellar serves is
precisely the event this project exists to notice.

The first feasibility spike shows what happens otherwise. It counted 306
structural identifiers in the consolidated XHTML on 8 August 2026. Cellar
regenerated the manifestation on 11 August; today the count is 284. The cause
cannot be reconstructed, because the August bytes were not kept.

Two needs pull in different directions. The payloads must be kept, but they
weigh about 5.7 MB and change rarely: committing them would fill the history
with EUR-Lex documents. The record of *which* payload is current must be
reviewable, and a change to it must be visible in a diff.

## Evidence

Measured on 8 October 2026:

- Cellar serves identical bytes for identical requests: the twelve payloads
  fetched in the evening match, hash for hash, those fetched hours earlier. This
  holds for the Formex zips too, so the zip envelope does not change between
  requests.
- Cellar exposes `ETag` and `Last-Modified` on each manifestation. They date
  the regeneration of the consolidated text independently of this project:
  `Last-Modified: Tue, 11 Aug 2026 16:30:22 GMT` for the English Formex bundle.

## Decision

**Payloads go into a content-addressed, write-once object store that is not
committed. Which payload is current for each source goes into a lock file that
is committed.**

1. **Object store** — `cache/objects/<aa>/<sha256>`. An object is written once,
   atomically, made read-only, and never overwritten or deleted by the tool.
   Reading an object verifies its hash.
2. **Lock** — `sources.lock.json`, one entry per `(CELEX, language,
   manifestation)`, sorted, with the request URL, the final Cellar URL after
   redirects, media type, SHA-256, size, the time those bytes were first
   retrieved, and Cellar's `ETag` and `Last-Modified`.
3. **Fetch semantics** — a source in the lock whose object is in the store is
   not requested. `--refresh` requests it again: identical bytes write nothing;
   different bytes add a new object, keep the old one, and move the lock. A
   failure on one source does not stop the others.
4. **No judgement at this layer.** A changed hash says the bytes changed, not
   that the law did. That distinction needs the canonical form (ADR-0006) and is
   the job of drift detection (S9).

## Consequences

**Positive**

- A second `fetch` makes no request and writes nothing: the definition of done
  of S1, asserted by a test and checked against Cellar.
- Every change upstream leaves two traces: the old object, still in the store,
  and a diff of the lock in version control.
- A fresh clone has the lock but not the store. `fetch` restores the store and
  checks every payload against the locked hash; a mismatch is reported as
  `changed`, not hidden.
- The final Cellar URL records the manifestation identifier
  (`…/resource/cellar/<uuid>.0001.01/zip`), so provenance points to the exact
  manifestation, not only to the CELEX number.

**Negative**

- The store is local. Byte-for-byte reproduction on another machine needs the
  same payloads, and Cellar may no longer serve them. The release process (S7)
  must therefore publish the payloads alongside the dataset, not just their
  hashes.
- `retrieved_at` is the time the bytes were *first* seen. A consumer who wants
  to know when they were last checked must look at the drift-detection history,
  not at the lock.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| Commit the payloads | About 5.7 MB per snapshot of EUR-Lex documents in the history, for content that is re-derivable while upstream is stable and preserved by the release when it is not |
| Store payloads by key (`cache/<celex>/<lang>/…`) | A refresh overwrites the previous payload: the exact failure that lost the August bytes |
| Rely on HTTP caching (`ETag`, `If-None-Match`) alone | Useful to avoid downloads, and recorded for that purpose, but a validator is not a payload: it cannot be re-parsed |
| Hash only, no store | Detects a change but leaves nothing to explain it |
