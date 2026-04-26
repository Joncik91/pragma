"""Tier 3 public entry — orchestrates prompt, client, verdict emission."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pragma.verdict import Verdict


class _LanguageModule(Protocol):
    LANGUAGE: str


def classify_file(
    test_path: Path,
    prior_verdicts: list[Verdict],
    lang: _LanguageModule,
) -> list[Verdict]:
    """Run tier 3 on tests `prior_verdicts` classified as verified.

    Returns prior_verdicts plus any `<lang>.semantic_gaming` warning verdicts
    the LLM judge produces. Skips silently when API key missing or call fails.

    Step 11 implementation.
    """
    return prior_verdicts
