# Architecture Decision Records

Lightweight format: **context, decision, consequences**. An ADR is written when a
choice is expensive to reverse, or when its rationale cannot be reconstructed
from the code.

These are part of the artefact, not paperwork. A project meant to be
infrastructure for others has to say what it is betting on — several of these
records describe properties of the *data* that anyone depending on it needs to
know before depending on it.

| ADR | Title | Status | Step |
|---|---|---|---|
| [0001](0001-source-format.md) | Source format for acquisition | Accepted | S0 |
| [0002](0002-identifiers.md) | Inherited and derived identifiers | Accepted | S4 |
| 0003 | Node identity across versions | To write | S8 |
| 0004 | Edge stratification by guarantee | To write | S10 |
| 0005 | Multi-source composition and recitals | To write | S8 |
| [0006](0006-canonical-form.md) | Canonical form and drift detection | Accepted | S2 |
| 0007 | Three axes of versioning | To write | S11 |
| 0008 | No LLM on the critical path | To write | S11 |
| 0009 | Choice of demonstrator application | To write | S11 |
| [0010](0010-cache-and-lock.md) | Immutable cache and source lock | Accepted | S1 |
| 0011 | Supported citation syntax | To write | S7b |
| [0012](0012-node-model.md) | Node model: structure, text and amendments | Accepted | S3 |
| [0013](0013-dataset-format.md) | Dataset format and release | Accepted | S7 |
