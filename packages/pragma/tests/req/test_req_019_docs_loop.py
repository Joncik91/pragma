"""Red tests for REQ-019 - docs describe the loop as it actually is.

The daily flow described across README / concepts.md / usage.md /
reference.md / claude.md.tpl shows activate → red tests → unlock →
implement → complete. After REQ-016 lands, that exact flow produces
junit + spans automatically. Docs must state that, including what
artifacts the PIL depends on, so a first-run user knows what to
expect.

These tests inspect the doc text for the expected guidance. Cheaper
than rendering the docs and semantic-matching; easier to maintain.
"""

from __future__ import annotations

from pathlib import Path

from pragma_sdk import set_permutation, trace

_REPO = Path(__file__).resolve().parents[4]
_README = _REPO / "README.md"
_CONCEPTS = _REPO / "docs" / "concepts.md"
_PRIMER_TPL = _REPO / "packages" / "pragma" / "src" / "pragma" / "templates" / "claude.md.tpl"


@trace("REQ-019")
def _assert_readme_describes_full_loop() -> None:
    text = _README.read_text(encoding="utf-8")
    # README Quick start should include the report step.
    assert "pragma report" in text, (
        "README must mention `pragma report` as part of the Quick start / Ship a slice flow"
    )


@trace("REQ-019")
def _assert_concepts_describes_artifacts() -> None:
    text = _CONCEPTS.read_text(encoding="utf-8")
    # concepts.md must state the PIL depends on both junit + spans,
    # and that Pragma's own flows produce both automatically.
    mentions_junit = "junit" in text.lower()
    mentions_spans = "span" in text.lower()
    mentions_automatic = (
        "automatically" in text.lower()
        or "produces both" in text.lower()
        or "emits" in text.lower()
    )
    assert mentions_junit and mentions_spans, (
        "concepts.md must describe the junit + spans cross-product the PIL relies on"
    )
    assert mentions_automatic, (
        "concepts.md must state that Pragma's own flows produce these "
        "artifacts automatically (so users don't need a separate pytest step)"
    )


@trace("REQ-019")
def _assert_primer_mentions_report_step() -> None:
    text = _PRIMER_TPL.read_text(encoding="utf-8")
    assert "Making the Post-Implementation Log useful" in text, (
        "greenfield primer template must end with a "
        '"Making the Post-Implementation Log useful" section'
    )
    assert "@trace" in text, "primer must show the @trace decorator example"
    assert "set_permutation" in text, "primer must show the set_permutation call"


def test_req_019_readme_describes_full_loop() -> None:
    with set_permutation("readme_describes_full_loop"):
        _assert_readme_describes_full_loop()


def test_req_019_concepts_describes_artifacts() -> None:
    with set_permutation("concepts_describes_artifacts"):
        _assert_concepts_describes_artifacts()


def test_req_019_primer_mentions_report_step() -> None:
    with set_permutation("primer_mentions_report_step"):
        _assert_primer_mentions_report_step()
