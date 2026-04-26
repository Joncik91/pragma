"""The Verdict dataclass — single source of truth for classifier output."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    """One classification outcome per test function.

    `kind` is language-prefixed (`python.tautological`, `vitest.tautological`).
    """

    kind: str
    evidence: str
    test_name: str

    def __repr__(self) -> str:
        return f"Verdict(kind={self.kind!r}, evidence={self.evidence!r}, test={self.test_name!r})"
