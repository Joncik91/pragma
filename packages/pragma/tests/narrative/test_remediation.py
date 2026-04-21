from __future__ import annotations

from pragma.narrative.remediation import get_remediation


def test_known_rule_returns_remediation() -> None:
    result = get_remediation("complexity", budget=10, got=15)
    assert "10" in result
    assert "15" in result


def test_unknown_rule_returns_generic() -> None:
    result = get_remediation("nonexistent_rule", budget=0, got=0)
    assert result


def test_nesting_depth_remediation() -> None:
    result = get_remediation("nesting_depth", budget=3, got=5)
    assert "3" in result
