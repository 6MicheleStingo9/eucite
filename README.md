# EUCITE

*Read it as "you cite".*

**Citations to the EU AI Act, checked against the text in force — built on a versioned, traceable, machine-readable representation of Regulation (EU) 2024/1689, in Italian and English.**

> **Status: pre-alpha.** The corpus can be built: `eucite dump` writes the base act, the consolidated text and the Digital Omnibus as identified nodes in Italian and English, after checking every inherited identifier against EUR-Lex and the two languages against each other ([ADR-0012](docs/adr/0012-node-model.md), [ADR-0013](docs/adr/0013-dataset-format.md)). No dataset is published yet.

---

## The problem

On 24 July 2026 the Official Journal published **Regulation (EU) 2026/1744**, the
Digital Omnibus on AI. It amended the AI Act, inserted new articles, and moved
compliance deadlines. It entered into force three days later.

Most tools built on the AI Act did not notice. Two months later, most of the
open datasets of the AI Act we examined still ship the 2024 text.

They did not notice because of how they were built: each one extracted the text
once, hardcoded it, and shipped. There is no shared, verifiable representation
of the regulation that a tool can depend on, so every tool carries its own
private copy — and every private copy drifts, silently, the moment the law
changes. Nothing in those tools can tell you *which* version of the law they are
answering from, or whether that version is still current.

Reading the text is not the hard part. The Publications Office serves it, and
several excellent human-facing readers exist. What does not exist is an
**artefact**: something a program can depend on, cite, pin to a version, and
diff across amendments.

## What this is

A dataset, a thin library to read it, and a checker for citations to it.

- **Every node can be traced to its source.** Each names the work and language
  it was read from; the manifest of the dataset gives the URL, retrieval time
  and checksums of every source. You can always answer "where did this sentence
  come from, and when was it fetched" — and derive the dataset again from the
  same sources, byte for byte.
- **Every node declares how confident you may be in its identifier.** Identifiers
  down to paragraph level are *inherited* from the source and are verifiable
  against it. Subparagraphs and points are *derived* by this project's parser
  from the source's markup, and each says whether it rests on a printed label or
  on position. The dataset never blurs the two.
- **Amendments are structured, not narrated.** Each node carries the amendments
  the consolidated text records on it, with the provision of the amending act
  that made them. A deleted provision keeps its identifier, without text, so a
  citation of it is answered "deleted", not "not found". The diff between the
  original act and the consolidated text is data, with before/after and the
  method used to match each node.
- **Citations are checked, not trusted.** "Article 6(3)(a)" or "articolo 6,
  paragrafo 3, lettera a)" resolves to the provision it names, in the version in
  force, together with whether its text changed since an earlier version. The
  checker says whether a citation exists and what it points to — never whether
  it is the right one for an argument.
- **The source is watched.** A scheduled job re-fetches upstream and compares a
  canonical hash. A change in the law breaks the build. A change in EUR-Lex's
  whitespace does not.

## What this is not

This project provides *structure, text and provenance*. It does not provide
*conclusions*.

It will never classify the risk of an AI system, score anything as a percentage,
or tell you whether you meet an obligation. Those require legal interpretation
that a dataset cannot honestly automate — and, in the case of scoring, a
harmonised standard to measure against, which as of today has not been cited in
the Official Journal.

There is no LLM anywhere in the pipeline. The output is meant to be reproducible
byte-for-byte from the cached source.

## Sources

Each work is read in two manifestations served by Cellar: Formex for text,
structure and amendment markers, XHTML to check identifiers against EUR-Lex and
as an independent rendering of the same text
([ADR-0001](docs/adr/0001-source-format.md)). Every payload also has a canonical
form, so that a change in presentation is never mistaken for a change in the law
([ADR-0006](docs/adr/0006-canonical-form.md)).
Languages: Italian and English.

| Content | CELEX |
|---|---|
| Articles and annexes in force | `02024R1689-20260727` |
| Recitals 1–180 of the base act | `32024R1689` |
| Digital Omnibus on AI | `32026R1744` |

The consolidated text does not contain the preamble, so recitals are composed
from the base act. The base act's recitals are never updated by amending acts —
a reader using recital 58 to interpret an article the Omnibus rewrote is reading
a rationale written before the rewrite. The dataset makes that mismatch
queryable rather than hiding it.

## Licence

- **Code:** MIT — see [LICENSE](LICENSE)
- **Dataset:** CC BY 4.0 — see [LICENSE-DATA](LICENSE-DATA), which also carries
  the attribution notice you must retain downstream

## Disclaimer

<!-- disclaimer:start -->
This project provides a structured representation of a legal text. It is not
legal advice, it expresses no judgement about anyone's obligations, and it does
not replace the official sources. **Only the text published in the Official
Journal of the European Union is authentic. Consolidated texts are documentation
tools and have no legal value.**

*Questo progetto fornisce una rappresentazione strutturata del testo normativo.
Non costituisce consulenza legale, non esprime valutazioni sugli obblighi di
alcuno e non sostituisce le fonti ufficiali. **Fa fede esclusivamente il testo
pubblicato nella Gazzetta ufficiale dell'Unione europea. Le versioni consolidate
sono strumenti di documentazione privi di valore giuridico.***
<!-- disclaimer:end -->

## Development

```bash
uv sync                      # install, including dev dependencies
uv run pytest                # the whole suite runs offline
uv run pytest -m data        # the parser on the real sources, read from cache/
uv run pytest -m network     # the few checks against the real Cellar
uv run ruff check
uv run mypy

uv run eucite fetch          # acquire the sources into cache/ and sources.lock.json
uv run eucite fetch --frozen # restore exactly the locked sources, or fail
uv run eucite dump           # check and write the dataset into dist-data/
uv run eucite dump --check   # derive it again and compare with dist-data/
```

`fetch` keeps every payload it has ever retrieved in a write-once cache and
records the current one in `sources.lock.json`, which is committed: a change in
what the Publications Office serves shows up as a diff of that file
([ADR-0010](docs/adr/0010-cache-and-lock.md)). Tests on the real sources skip
when `cache/` lacks them; `fetch --frozen` restores them as the lock pins them.

Design decisions live in [`docs/adr/`](docs/adr/). They are part of the artefact,
not paperwork: a project meant to be infrastructure for others has to explain why
it is shaped the way it is.
