# ai-act-corpus

**A versioned, traceable, machine-readable representation of Regulation (EU) 2024/1689 — the EU AI Act.**

> **Status: pre-alpha.** The feasibility spike is done and the source format is settled ([ADR-0001](docs/adr/0001-source-format.md)). No corpus is published yet.

---

## The problem

On 24 July 2026 the Official Journal published **Regulation (EU) 2026/1744**, the
Digital Omnibus on AI. It amended the AI Act, inserted new articles, and moved
compliance deadlines. It entered into force three days later.

Most tools built on the AI Act did not notice.

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

A dataset, and a thin library to read it.

- **Every node carries its provenance** — source work, CELEX identifier, source
  URL, retrieval time, checksums. You can always answer "where did this sentence
  come from, and when did I fetch it".
- **Every node declares how confident you may be in its identifier.** Identifiers
  down to paragraph level are *inherited* from the source and are verifiable
  against it. Subparagraphs and points are *derived* by this project's parser
  from the source's markup, and each says whether it rests on a printed label or
  on position. The dataset never blurs the two.
- **Amendments are structured, not narrated.** The diff between the original act
  and the consolidated text is data, with before/after and the method used to
  match each node.
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

Each work is read in two manifestations served by Cellar: Formex for text and
structure, XHTML for the amendment markers ([ADR-0001](docs/adr/0001-source-format.md)).
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
uv sync            # install, including dev dependencies
uv run pytest      # the whole suite runs offline
uv run ruff check
uv run mypy
```

Design decisions live in [`docs/adr/`](docs/adr/). They are part of the artefact,
not paperwork: a project meant to be infrastructure for others has to explain why
it is shaped the way it is.
