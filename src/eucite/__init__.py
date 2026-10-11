"""Versioned, traceable, machine-readable representation of the EU AI Act.

This package provides a structured representation of a legal text. It is not
legal advice, it expresses no judgement about anyone's obligations, and it does
not replace the official sources. Only the text published in the Official
Journal of the European Union is authentic; consolidated texts are documentation
tools and have no legal value.

The package is deliberately thin. The value is in the dataset it builds and
reads: every node can be traced to its source, and every identifier declares
whether it was inherited from the source or derived by this project's parser.
"""

from __future__ import annotations

__all__ = ["DISCLAIMER", "DISCLAIMER_IT", "__version__"]

__version__ = "0.0.1"

DISCLAIMER = (
    "This project provides a structured representation of a legal text. "
    "It is not legal advice, it expresses no judgement about anyone's "
    "obligations, and it does not replace the official sources. Only the text "
    "published in the Official Journal of the European Union is authentic. "
    "Consolidated texts are documentation tools and have no legal value."
)

DISCLAIMER_IT = (
    "Questo progetto fornisce una rappresentazione strutturata del testo normativo. "
    "Non costituisce consulenza legale, non esprime valutazioni sugli obblighi di "
    "alcuno e non sostituisce le fonti ufficiali. Fa fede esclusivamente il testo "
    "pubblicato nella Gazzetta ufficiale dell'Unione europea. Le versioni consolidate "
    "sono strumenti di documentazione privi di valore giuridico."
)
