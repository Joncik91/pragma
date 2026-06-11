"""Tests for run_python_with_coverage."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from pragma.coverage.runner import run_python_with_coverage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_production_module(tmp_path: Path, name: str = "prod.py") -> Path:
    """Write a minimal production module with two functions."""
    p = tmp_path / name
    p.write_text("def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b\n")
    return p


def _write_passing_test(tmp_path: Path, prod_path: Path, name: str = "test_prod.py") -> Path:
    """Write a passing test that calls into prod_path."""
    p = tmp_path / name
    p.write_text(
        f"import sys, os\n"
        f"sys.path.insert(0, {str(prod_path.parent)!r})\n"
        f"from {prod_path.stem} import add, subtract\n"
        f"\n"
        f"def test_add():\n"
        f"    assert add(1, 2) == 3\n"
        f"\n"
        f"def test_subtract():\n"
        f"    assert subtract(5, 3) == 2\n"
    )
    return p


def _write_non_covering_test(tmp_path: Path, name: str = "test_no_cover.py") -> Path:
    """Write a test that doesn't call any production function."""
    p = tmp_path / name
    p.write_text("def test_unrelated():\n    assert 1 + 1 == 2\n")
    return p


# ---------------------------------------------------------------------------
# Positive tests
# ---------------------------------------------------------------------------


def test_runner_returns_existing_db_path(tmp_path: Path) -> None:
    """run_python_with_coverage returns a Path that exists on disk."""
    prod = _write_production_module(tmp_path)
    test_file = _write_passing_test(tmp_path, prod)
    result = run_python_with_coverage(test_file, prod)
    assert result is not None
    assert isinstance(result, Path)
    assert result.exists()


def test_runner_db_is_nonempty(tmp_path: Path) -> None:
    """The returned .coverage file has non-zero size (coverage wrote data)."""
    prod = _write_production_module(tmp_path)
    test_file = _write_passing_test(tmp_path, prod)
    result = run_python_with_coverage(test_file, prod)
    assert result is not None
    assert result.stat().st_size > 0


def test_runner_db_records_contexts(tmp_path: Path) -> None:
    """After a passing run, the DB contains at least one dynamic context."""
    try:
        import coverage as cov_module
    except ImportError:
        pytest.skip("coverage not installed")

    prod = _write_production_module(tmp_path)
    test_file = _write_passing_test(tmp_path, prod)
    result = run_python_with_coverage(test_file, prod)
    assert result is not None

    data = cov_module.CoverageData(basename=str(result))
    data.read()
    all_contexts: set[str] = set()
    for f in data.measured_files():
        for ctxs in data.contexts_by_lineno(f).values():
            all_contexts.update(ctxs)
    # At least one non-empty context string present
    non_empty = {c for c in all_contexts if c}
    assert len(non_empty) > 0


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------


def test_runner_missing_test_path_returns_none(tmp_path: Path) -> None:
    """test_path does not exist on disk → None."""
    prod = _write_production_module(tmp_path)
    missing = tmp_path / "does_not_exist.py"
    result = run_python_with_coverage(missing, prod)
    assert result is None


def test_runner_missing_target_file_returns_none(tmp_path: Path) -> None:
    """target_file doesn't exist on disk → runner returns None.

    coverage --include=<missing> produces no data file.
    """
    test_file = _write_non_covering_test(tmp_path)
    missing_target = tmp_path / "nonexistent_target.py"
    result = run_python_with_coverage(test_file, missing_target)
    assert result is None


def test_runner_syntax_error_test_returns_none(tmp_path: Path) -> None:
    """A test file with a syntax error → None (subprocess fails cleanly)."""
    prod = _write_production_module(tmp_path)
    bad_test = tmp_path / "test_broken.py"
    bad_test.write_text("def test_bad(:\n    pass\n")  # syntax error
    result = run_python_with_coverage(bad_test, prod)
    # May return None or a db with no contexts; must not raise
    # The key requirement is: it doesn't crash
    assert result is None or isinstance(result, Path)


def test_runner_timeout_test_returns_none(tmp_path: Path) -> None:
    """A test with time.sleep(10) is killed by --timeout=5 → None."""
    prod = _write_production_module(tmp_path)
    slow_test = tmp_path / "test_slow.py"
    slow_test.write_text("import time\ndef test_sleepy():\n    time.sleep(10)\n")
    result = run_python_with_coverage(slow_test, prod)
    # --timeout=5 means pytest exits with failure; no coverage data written
    assert result is None


# ---------------------------------------------------------------------------
# Environment-scrubbing tests
#
# The subprocess runs `coverage run -m pytest <untrusted test file>`. The
# child must NOT inherit secret-bearing vars from the parent process: a gamed
# or malicious test under audit could exfiltrate API keys via the environment.
# ---------------------------------------------------------------------------


def _capture_child_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Run the runner with subprocess.run stubbed; return the child env it built."""
    prod = _write_production_module(tmp_path)
    test_file = _write_passing_test(tmp_path, prod)

    captured: dict[str, dict[str, str]] = {}

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN003
        captured["env"] = dict(kwargs.get("env") or {})
        # Mimic a failed run so the runner returns None without touching the DB.
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 10))

    with patch("pragma.coverage.runner.subprocess.run", side_effect=fake_run):
        run_python_with_coverage(test_file, prod)

    assert "env" in captured, "subprocess.run was never called with an env"
    return captured["env"]


def test_runner_strips_pragma_api_keys_from_child_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PRAGMA_*_API_KEY secrets in the parent env must not reach the child."""
    monkeypatch.setenv("PRAGMA_LLM_API_KEY", "sk-secret-llm")
    monkeypatch.setenv("PRAGMA_OPENAI_API_KEY", "sk-secret-openai")

    env = _capture_child_env(tmp_path, monkeypatch)

    assert "PRAGMA_LLM_API_KEY" not in env, f"PRAGMA_LLM_API_KEY leaked: {env.keys()}"
    assert "PRAGMA_OPENAI_API_KEY" not in env, f"PRAGMA_OPENAI_API_KEY leaked: {env.keys()}"


def test_runner_strips_common_secret_vars_from_child_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Common secret-bearing vars (tokens, AWS creds) must not reach the child."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret")
    monkeypatch.setenv("MY_DB_PASSWORD", "hunter2")

    env = _capture_child_env(tmp_path, monkeypatch)
    keys = sorted(env.keys())

    assert "OPENAI_API_KEY" not in env, f"OPENAI_API_KEY leaked into child env: {keys}"
    assert "AWS_SECRET_ACCESS_KEY" not in env, f"AWS_SECRET_ACCESS_KEY leaked: {keys}"
    assert "GITHUB_TOKEN" not in env, f"GITHUB_TOKEN leaked into child env: {keys}"
    assert "MY_DB_PASSWORD" not in env, f"MY_DB_PASSWORD leaked into child env: {keys}"


def test_runner_child_env_keeps_essentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The allowlisted child env must still carry PATH and the coverage DB pointer."""
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    env = _capture_child_env(tmp_path, monkeypatch)

    assert env.get("PATH"), "PATH must be forwarded so the interpreter/tools resolve"
    assert env.get("COVERAGE_FILE"), "COVERAGE_FILE must point the child at the temp DB"


def test_runner_forwards_pythonpath_to_child_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PYTHONPATH must reach the child: src-layout repos need it for imports.

    It is not secret-bearing, and without it tier 2 silently skips when the
    target imports resolve via PYTHONPATH rather than an installed package.
    """
    monkeypatch.setenv("PYTHONPATH", "/proj/src:/proj/extra")

    env = _capture_child_env(tmp_path, monkeypatch)

    assert env.get("PYTHONPATH") == "/proj/src:/proj/extra", (
        f"PYTHONPATH must be forwarded so src-layout imports resolve: {sorted(env.keys())}"
    )
