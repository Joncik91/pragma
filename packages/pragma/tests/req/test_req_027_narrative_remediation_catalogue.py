"""Red tests for REQ-027 — narrative remediation covers real error codes.

BUG-028. The pragma.narrative.remediation catalogue only had entries
for three discipline AST rules. Every user-facing error code fell
through to a generic "Rule X triggered: got N budget M" placeholder
that carried no useful signal. Fix adds specific entries for the
error codes a user hits under pre-commit / pre-push / CI.
"""

from __future__ import annotations

from pragma_sdk import set_permutation, trace

from pragma.narrative.remediation import get_remediation


@trace("REQ-027")
def _assert_known_discipline_rule_is_specific() -> None:
    text = get_remediation("complexity", budget=10, got=15)
    # The existing specific template should still win.
    assert "complexity" in text.lower()
    assert "extract" in text.lower() or "split" in text.lower() or "smaller" in text.lower()


@trace("REQ-027")
def _assert_known_error_code_is_specific() -> None:
    text = get_remediation("commit_shape_violation", budget=0, got=0)
    # Must name the actual concepts — WHY, Co-Authored-By, subject-length —
    # rather than "Rule X triggered: got ..." boilerplate.
    lower = text.lower()
    assert "why" in lower, (
        f"remediation must mention WHY line for commit_shape_violation; got: {text!r}"
    )
    assert "co-authored-by" in lower or "trailer" in lower or "subject" in lower, (
        f"remediation must point at trailer / subject shape rules; got: {text!r}"
    )
    assert "Rule 'commit_shape_violation' triggered" not in text, (
        f"must not fall back to placeholder; got: {text!r}"
    )


@trace("REQ-027")
def _assert_unknown_rule_falls_back_to_generic() -> None:
    text = get_remediation("totally_unknown_rule_xyz", budget=7, got=9)
    # Must still return a non-empty string — generic fallback is fine,
    # but the CLI must not crash or return "".
    assert text
    assert "totally_unknown_rule_xyz" in text or "rule" in text.lower()


def test_req_027_known_discipline_rule_is_specific() -> None:
    with set_permutation("known_discipline_rule_is_specific"):
        _assert_known_discipline_rule_is_specific()


def test_req_027_known_error_code_is_specific() -> None:
    with set_permutation("known_error_code_is_specific"):
        _assert_known_error_code_is_specific()


def test_req_027_unknown_rule_falls_back_to_generic() -> None:
    with set_permutation("unknown_rule_falls_back_to_generic"):
        _assert_unknown_rule_falls_back_to_generic()
