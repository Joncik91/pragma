"""Per-file orchestrator: dispatch to the right language module."""

from __future__ import annotations

from pathlib import Path

from pragma.blocking import is_blocking_kind
from pragma.languages import REGISTRY
from pragma.verdict import Verdict


def verify_file(path: Path) -> list[Verdict]:
    """Classify every test function in `path` using the matching language module."""
    for lang in REGISTRY:
        if lang.matches(path):
            return lang.classify_file(path)
    return []


def is_blocking(verdicts: list[Verdict]) -> bool:
    """True when any verdict's kind is in the blocking suffix set."""
    return any(is_blocking_kind(v.kind) for v in verdicts)
