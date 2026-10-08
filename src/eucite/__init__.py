"""Versioned, traceable, machine-readable representation of the EU AI Act.

This package provides a structured representation of a legal text. It is not
legal advice, it expresses no judgement about anyone's obligations, and it does
not replace the official sources. Only the text published in the Official
Journal of the European Union is authentic; consolidated texts are documentation
tools and have no legal value.

The package is deliberately thin. The value is in the dataset it reads: every
node carries its provenance, and every identifier declares whether it was
inherited from the source or derived by this project's parser.
"""

from __future__ import annotations

__all__ = ["DISCLAIMER", "__version__"]

__version__ = "0.0.1"

DISCLAIMER = (
    "This project provides a structured representation of a legal text. "
    "It is not legal advice, it expresses no judgement about anyone's "
    "obligations, and it does not replace the official sources. Only the text "
    "published in the Official Journal of the European Union is authentic. "
    "Consolidated texts are documentation tools and have no legal value."
)
