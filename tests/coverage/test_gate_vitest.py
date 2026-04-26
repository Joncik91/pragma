"""Tests for tier-2 vitest gate orchestration.

All subprocess calls are monkeypatched — CI must not require Node.
These tests exercise gate.classify_file's vitest dispatch path:
  - routing into _run_vitest_tier2
  - production_target_vitest resolution
  - _vitest_symbol_lines lookup
  - cache hit/miss logic
  - result broadcast (aggregate V8 → all verified tests)
  - cleanup of coverage dir
  - exception resilience
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pragma.coverage import cache as cache_module
from pragma.coverage import gate
from pragma.verdict import Verdict

# ---------------------------------------------------------------------------
# Language stub
# ---------------------------------------------------------------------------


class _VitestLang:
    LANGUAGE = "vitest"

    def matches(self, path: Path) -> bool:
        return path.suffix in {".ts", ".tsx", ".js", ".jsx"}


class _PythonLang:
    LANGUAGE = "python"

    def matches(self, path: Path) -> bool:
        return path.suffix == ".py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verified(test_name: str) -> Verdict:
    return Verdict(kind="vitest.verified", evidence="tier1", test_name=test_name)


def _blocking(test_name: str) -> Verdict:
    return Verdict(kind="vitest.mocked-away", evidence="tier1", test_name=test_name)


VITEST_LANG = _VitestLang()
PYTHON_LANG = _PythonLang()


def _write_vitest_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Write minimal vitest test + production file. Returns (test_file, prod_file)."""
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(json.dumps({"name": "t", "devDependencies": {"vitest": "^1.0.0"}}))
    prod = tmp_path / "src" / "charge.ts"
    prod.parent.mkdir(parents=True, exist_ok=True)
    prod.write_text(
        "export function chargeCard(token: string, amount: number): boolean {\n"
        "  return amount > 0;\n"
        "}\n"
    )
    test_file = tmp_path / "tests" / "charge_real.test.ts"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        'import { it, expect } from "vitest";\n'
        'import { chargeCard } from "../src/charge";\n'
        "\n"
        'it("charges", () => {\n'
        '  expect(chargeCard("tok", 10)).toBe(true);\n'
        "});\n"
    )
    return test_file, prod


# ---------------------------------------------------------------------------
# Basic contract tests
# ---------------------------------------------------------------------------


def test_empty_prior_returns_empty(tmp_path: Path) -> None:
    """Empty prior_verdicts → empty result immediately."""
    test_file, _ = _write_vitest_fixture(tmp_path)
    result = gate.classify_file(test_file, [], VITEST_LANG)
    assert result == []


def test_only_blocking_verdicts_returns_prior_unchanged(tmp_path: Path) -> None:
    """Only blocking verdicts — tier 2 has nothing to augment."""
    test_file, _ = _write_vitest_fixture(tmp_path)
    prior = [_blocking("test_charges"), _blocking("test_other")]
    result = gate.classify_file(test_file, prior, VITEST_LANG)
    assert result == prior


def test_python_lang_not_dispatched_to_vitest_path(tmp_path: Path) -> None:
    """Python language → Python path; vitest branch is not taken."""
    # Create a Python test file; we patch infer_target to avoid needing a
    # real Python module.
    test_file = tmp_path / "test_foo.py"
    test_file.write_text("def test_foo(): pass\n")
    prior = [Verdict(kind="python.verified", evidence="tier1", test_name="test_foo")]

    with patch("pragma.languages.python.inference.infer_target", return_value=(None, None)):
        result = gate.classify_file(test_file, prior, PYTHON_LANG)
    # Python path ran (infer_target was called), not vitest path
    assert result == prior


# ---------------------------------------------------------------------------
# production_target_vitest returns None
# ---------------------------------------------------------------------------


def test_no_production_target_returns_prior_unchanged(tmp_path: Path) -> None:
    """production_target_vitest returns None → prior unchanged."""
    test_file, _ = _write_vitest_fixture(tmp_path)
    prior = [_verified("test_charges")]

    with patch("pragma.coverage.gate.production_target_vitest", return_value=None):
        result = gate.classify_file(test_file, prior, VITEST_LANG)
    assert result == prior


# ---------------------------------------------------------------------------
# _vitest_symbol_lines returns None
# ---------------------------------------------------------------------------


def test_symbol_lines_none_returns_prior_unchanged(tmp_path: Path) -> None:
    """_vitest_symbol_lines returns None → prior unchanged."""
    test_file, prod = _write_vitest_fixture(tmp_path)
    prior = [_verified("test_charges")]

    with (
        patch(
            "pragma.coverage.gate.production_target_vitest",
            return_value=(prod, "chargeCard"),
        ),
        patch("pragma.coverage.gate._vitest_symbol_lines", return_value=None),
    ):
        result = gate.classify_file(test_file, prior, VITEST_LANG)
    assert result == prior


# ---------------------------------------------------------------------------
# Cache hit tests
# ---------------------------------------------------------------------------


def test_cache_hit_none_keeps_verified(tmp_path: Path) -> None:
    """Cache hit with None (covered) → all verified verdicts stay verified."""
    test_file, prod = _write_vitest_fixture(tmp_path)
    prior = [_verified("test_charges"), _verified("test_other")]

    with (
        patch(
            "pragma.coverage.gate.production_target_vitest",
            return_value=(prod, "chargeCard"),
        ),
        patch("pragma.coverage.gate._vitest_symbol_lines", return_value=range(1, 4)),
        patch("pragma.coverage.gate.lookup", return_value=None),
    ):
        result = gate.classify_file(test_file, prior, VITEST_LANG)

    assert len(result) == 2
    assert all(v.kind == "vitest.verified" for v in result)


def test_cache_hit_target_not_covered_broadcasts_to_all_verified(tmp_path: Path) -> None:
    """Cache hit with target_not_covered verdict → broadcast to all verified tests."""
    test_file, prod = _write_vitest_fixture(tmp_path)
    prior = [
        _verified("test_alice"),
        _blocking("test_blocked"),
        _verified("test_bob"),
    ]

    cached_verdict = Verdict(
        kind="vitest.target_not_covered",
        evidence=(
            "vitest run completed but chargeCard (in charge.ts, lines 1-3)"
            " had 0 hits in this run's V8 coverage"
        ),
        test_name="test_alice",  # stored with first test name
    )

    with (
        patch(
            "pragma.coverage.gate.production_target_vitest",
            return_value=(prod, "chargeCard"),
        ),
        patch("pragma.coverage.gate._vitest_symbol_lines", return_value=range(1, 4)),
        patch("pragma.coverage.gate.lookup", return_value=cached_verdict),
    ):
        result = gate.classify_file(test_file, prior, VITEST_LANG)

    assert len(result) == 3

    # Blocking verdict preserved
    blocked = result[1]
    assert blocked.kind == "vitest.mocked-away"
    assert blocked.test_name == "test_blocked"

    # Both verified tests get target_not_covered with their OWN test_name
    alice_v = result[0]
    assert alice_v.kind == "vitest.target_not_covered"
    assert alice_v.test_name == "test_alice"
    assert "chargeCard" in alice_v.evidence

    bob_v = result[2]
    assert bob_v.kind == "vitest.target_not_covered"
    assert bob_v.test_name == "test_bob"
    assert "chargeCard" in bob_v.evidence


# ---------------------------------------------------------------------------
# Cache miss — runner returns None
# ---------------------------------------------------------------------------


def test_cache_miss_runner_returns_none_keeps_prior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runner returns None → infrastructure failure; prior unchanged, no cache write."""
    test_file, prod = _write_vitest_fixture(tmp_path)
    prior = [_verified("test_charges")]

    monkeypatch.setenv("PRAGMA_NO_CACHE", "1")
    store_mock = MagicMock()

    with (
        patch(
            "pragma.coverage.gate.production_target_vitest",
            return_value=(prod, "chargeCard"),
        ),
        patch("pragma.coverage.gate._vitest_symbol_lines", return_value=range(1, 4)),
        patch("pragma.coverage.gate.lookup", return_value=cache_module.MISS),
        patch("pragma.coverage.gate.run_vitest_with_coverage", return_value=None),
        patch("pragma.coverage.gate.store", store_mock),
    ):
        result = gate.classify_file(test_file, prior, VITEST_LANG)

    assert result == prior
    store_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Cache miss — runner succeeds, query returns {"_aggregate": True}
# ---------------------------------------------------------------------------


def test_cache_miss_covered_keeps_verified_and_caches_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runner succeeds + query returns _aggregate=True → all stay verified, cache stores None."""
    test_file, prod = _write_vitest_fixture(tmp_path)
    prior = [_verified("test_charges"), _verified("test_other")]

    fake_coverage_dir = tmp_path / "fake-coverage"
    fake_coverage_dir.mkdir()
    fake_json = fake_coverage_dir / "coverage-final.json"
    fake_json.write_text("{}")

    store_mock = MagicMock()

    with (
        patch(
            "pragma.coverage.gate.production_target_vitest",
            return_value=(prod, "chargeCard"),
        ),
        patch("pragma.coverage.gate._vitest_symbol_lines", return_value=range(1, 4)),
        patch("pragma.coverage.gate.lookup", return_value=cache_module.MISS),
        patch("pragma.coverage.gate.run_vitest_with_coverage", return_value=fake_json),
        patch("pragma.coverage.gate.query_vitest_coverage", return_value={"_aggregate": True}),
        patch("pragma.coverage.gate.store", store_mock),
    ):
        result = gate.classify_file(test_file, prior, VITEST_LANG)

    assert len(result) == 2
    assert all(v.kind == "vitest.verified" for v in result)
    # cache stores None (covered) — one write per file (not per test)
    store_mock.assert_called_once()
    _, _, _, stored_verdict = store_mock.call_args.args
    assert stored_verdict is None


# ---------------------------------------------------------------------------
# Cache miss — runner succeeds, query returns {"_aggregate": False}
# ---------------------------------------------------------------------------


def test_cache_miss_not_covered_emits_target_not_covered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runner succeeds + query returns _aggregate=False → all replaced with target_not_covered."""
    test_file, prod = _write_vitest_fixture(tmp_path)
    prior = [_verified("test_charges"), _verified("test_other")]

    fake_coverage_dir = tmp_path / "fake-coverage"
    fake_coverage_dir.mkdir()
    fake_json = fake_coverage_dir / "coverage-final.json"
    fake_json.write_text("{}")

    store_mock = MagicMock()

    with (
        patch(
            "pragma.coverage.gate.production_target_vitest",
            return_value=(prod, "chargeCard"),
        ),
        patch("pragma.coverage.gate._vitest_symbol_lines", return_value=range(1, 4)),
        patch("pragma.coverage.gate.lookup", return_value=cache_module.MISS),
        patch("pragma.coverage.gate.run_vitest_with_coverage", return_value=fake_json),
        patch("pragma.coverage.gate.query_vitest_coverage", return_value={"_aggregate": False}),
        patch("pragma.coverage.gate.store", store_mock),
    ):
        result = gate.classify_file(test_file, prior, VITEST_LANG)

    assert len(result) == 2
    for v in result:
        assert v.kind == "vitest.target_not_covered"
        assert "chargeCard" in v.evidence
    # Each test gets its own test_name
    names = {v.test_name for v in result}
    assert names == {"test_charges", "test_other"}
    # Cache stores the verdict (one write for the file)
    store_mock.assert_called_once()
    _, _, _, stored_verdict = store_mock.call_args.args
    assert stored_verdict is not None
    assert stored_verdict.kind == "vitest.target_not_covered"


# ---------------------------------------------------------------------------
# Cache miss — runner succeeds, query returns {} (failure)
# ---------------------------------------------------------------------------


def test_cache_miss_query_empty_keeps_prior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runner succeeds + query returns {} → prior unchanged, no cache write."""
    test_file, prod = _write_vitest_fixture(tmp_path)
    prior = [_verified("test_charges")]

    fake_coverage_dir = tmp_path / "fake-coverage"
    fake_coverage_dir.mkdir()
    fake_json = fake_coverage_dir / "coverage-final.json"
    fake_json.write_text("{}")

    store_mock = MagicMock()

    with (
        patch(
            "pragma.coverage.gate.production_target_vitest",
            return_value=(prod, "chargeCard"),
        ),
        patch("pragma.coverage.gate._vitest_symbol_lines", return_value=range(1, 4)),
        patch("pragma.coverage.gate.lookup", return_value=cache_module.MISS),
        patch("pragma.coverage.gate.run_vitest_with_coverage", return_value=fake_json),
        patch("pragma.coverage.gate.query_vitest_coverage", return_value={}),
        patch("pragma.coverage.gate.store", store_mock),
    ):
        result = gate.classify_file(test_file, prior, VITEST_LANG)

    assert result == prior
    store_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Coverage dir cleanup
# ---------------------------------------------------------------------------


def test_coverage_dir_cleaned_up_after_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Coverage dir is rmtree'd after query (whether covered or not)."""
    test_file, prod = _write_vitest_fixture(tmp_path)
    prior = [_verified("test_charges")]

    fake_coverage_dir = tmp_path / "fake-coverage"
    fake_coverage_dir.mkdir()
    fake_json = fake_coverage_dir / "coverage-final.json"
    fake_json.write_text("{}")

    with (
        patch(
            "pragma.coverage.gate.production_target_vitest",
            return_value=(prod, "chargeCard"),
        ),
        patch("pragma.coverage.gate._vitest_symbol_lines", return_value=range(1, 4)),
        patch("pragma.coverage.gate.lookup", return_value=cache_module.MISS),
        patch("pragma.coverage.gate.run_vitest_with_coverage", return_value=fake_json),
        patch("pragma.coverage.gate.query_vitest_coverage", return_value={"_aggregate": True}),
        patch("pragma.coverage.gate.store"),
    ):
        gate.classify_file(test_file, prior, VITEST_LANG)

    # The coverage dir should be cleaned up
    assert not fake_coverage_dir.exists()


# ---------------------------------------------------------------------------
# Exception resilience
# ---------------------------------------------------------------------------


def test_unexpected_exception_returns_prior_unchanged(tmp_path: Path) -> None:
    """Unexpected exception inside _run_vitest_tier2 → caught, returns prior unchanged."""
    test_file, _ = _write_vitest_fixture(tmp_path)
    prior = [_verified("test_charges")]

    with patch(
        "pragma.coverage.gate.production_target_vitest",
        side_effect=RuntimeError("simulated crash"),
    ):
        result = gate.classify_file(test_file, prior, VITEST_LANG)
    assert result == prior


def test_unexpected_exception_logged_to_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Exception in vitest gate logs to stderr with [pragma:tier2] prefix."""
    test_file, _ = _write_vitest_fixture(tmp_path)
    prior = [_verified("test_charges")]

    with patch(
        "pragma.coverage.gate.production_target_vitest",
        side_effect=RuntimeError("vitest error"),
    ):
        gate.classify_file(test_file, prior, VITEST_LANG)
    captured = capsys.readouterr()
    assert "[pragma:tier2]" in captured.err


# ---------------------------------------------------------------------------
# Mixed blocking + verified in prior
# ---------------------------------------------------------------------------


def test_blocking_verdicts_preserved_when_vitest_not_covered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Blocking verdicts pass through; only verified tests get target_not_covered."""
    test_file, prod = _write_vitest_fixture(tmp_path)
    prior = [
        _blocking("test_gamed"),
        _verified("test_legit"),
    ]

    fake_coverage_dir = tmp_path / "fake-coverage"
    fake_coverage_dir.mkdir()
    fake_json = fake_coverage_dir / "coverage-final.json"
    fake_json.write_text("{}")

    with (
        patch(
            "pragma.coverage.gate.production_target_vitest",
            return_value=(prod, "chargeCard"),
        ),
        patch("pragma.coverage.gate._vitest_symbol_lines", return_value=range(1, 4)),
        patch("pragma.coverage.gate.lookup", return_value=cache_module.MISS),
        patch("pragma.coverage.gate.run_vitest_with_coverage", return_value=fake_json),
        patch("pragma.coverage.gate.query_vitest_coverage", return_value={"_aggregate": False}),
        patch("pragma.coverage.gate.store"),
    ):
        result = gate.classify_file(test_file, prior, VITEST_LANG)

    assert len(result) == 2
    assert result[0].kind == "vitest.mocked-away"
    assert result[0].test_name == "test_gamed"
    assert result[1].kind == "vitest.target_not_covered"
    assert result[1].test_name == "test_legit"
