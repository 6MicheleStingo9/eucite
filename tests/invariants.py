"""Invariants every parsed document satisfies, generated or real (ADR-0012)."""

from __future__ import annotations

from eucite.nodes import Document


def assert_tree(doc: Document) -> None:
    """Unique identifiers; one root; every parent present and earlier in order."""
    seen: set[str] = set()
    for position, node in enumerate(doc.nodes):
        assert node.id not in seen, f"duplicate {node.id}"
        assert node.order == position
        if position == 0:
            assert node.parent is None and node.id == doc.act
        else:
            assert node.parent in seen, f"{node.id}: parent {node.parent} missing or later"
            assert node.id.startswith(f"{doc.act}/")
        if node.deleted:
            assert node.text is None and not doc.children(node.id)
        seen.add(node.id)


def assert_composition(doc: Document) -> None:
    """The block of each child is a run of lines of its parent's text, in order."""
    for node in doc.nodes:
        if node.text is None:
            continue
        lines, position = node.text.split("\n"), 0
        for child in doc.children(node.id):
            block = child.block()
            if not block:
                continue
            for start in range(position, len(lines) - len(block) + 1):
                if lines[start : start + len(block)] == block:
                    position = start + len(block)
                    break
            else:
                raise AssertionError(f"{child.id} is not a block of {node.id}")
