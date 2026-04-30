"""End-to-end tests for the `pragma` CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"
BLOCKING_DIR = FIXTURE_DIR / "blocking"
WARNING_DIR = FIXTURE_DIR / "warning"


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Invoke the CLI as a subprocess. Uses `python -m pragma` so we
    don't depend on `pragma` being on PATH (the package may be source-only
    in CI, before `pip install -e .`)."""
    env_path = str(REPO_ROOT / "src")
    cmd = [sys.executable, "-m", "pragma", *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": env_path},
        check=False,
    )


class TestVerifyTests:
    @pytest.mark.parametrize(
        "fixture, expected_kind",
        [
            ("gamed_tautology.py", "python.tautological"),
            ("gamed_mocked_away.py", "python.mocked-away"),
            ("gamed_mismatched.py", "python.mismatched"),
            ("gamed_swallowed.py", "python.swallowed"),
            ("gamed_skipped.py", "python.skipped"),
            ("gamed_conditional.py", "python.conditional"),
            ("gamed_monkeypatched.py", "python.monkeypatched"),
            ("gamed_lazy_import_monkeypatched.py", "python.monkeypatched"),
            ("gamed_module_shimmed.py", "python.module_shimmed"),
            ("gamed_module_attr_reassignment.py", "python.module_attr_reassignment"),
            ("gamed_xfail_strict.py", "python.xfail_gaming"),
            ("test_orphan_target.py", "python.orphan_test"),
            ("gamed_async_mocked_away.py", "python.mocked-away"),
            ("vitest_tautological.test.ts", "vitest.tautological"),
            ("vitest_mocked_away.test.ts", "vitest.mocked-away"),
            ("vitest_mocked_away_intermediate.test.ts", "vitest.mocked-away"),
            ("vitest_mocked_away_namespace.test.ts", "vitest.mocked-away"),
            ("vitest_spyon_mocked_away.test.ts", "vitest.mocked-away"),
            ("vitest_skipped.test.ts", "vitest.skipped"),
            ("vitest_swallowed.test.ts", "vitest.swallowed"),
            ("vitest_conditional.test.ts", "vitest.conditional"),
            ("vitest_mismatched.test.ts", "vitest.mismatched"),
            ("vitest_mismatched_stub_error.test.ts", "vitest.stub_error_match"),
            ("vitest_mismatched_backend_offline.test.ts", "vitest.stub_error_match"),
            ("vitest_stub_error_positive_name.test.ts", "vitest.stub_error_match"),
            ("vitest_orphan_mock.test.ts", "vitest.orphan_mock"),
        ],
    )
    def test_blocking_fixtures_exit_one(self, fixture: str, expected_kind: str) -> None:
        result = _run("verify", "tests", str(BLOCKING_DIR / fixture))
        assert result.returncode == 1, f"expected exit 1; got {result.returncode}\n{result.stdout}"
        payload = json.loads(result.stdout)
        assert payload["blocking"] is True
        verdicts = payload["results"][str(BLOCKING_DIR / fixture)]
        kinds = [v["kind"] for v in verdicts]
        assert expected_kind in kinds, f"expected {expected_kind} in {kinds}"

    @pytest.mark.parametrize(
        "fixture, expected_kind",
        [
            ("gamed_parametrize_thin.py", "python.parametrize_thin"),
            ("gamed_empty_body.py", "python.empty_body"),
            ("vitest_empty_body.test.ts", "vitest.empty_body"),
        ],
    )
    def test_warning_fixtures_exit_zero(self, fixture: str, expected_kind: str) -> None:
        result = _run("verify", "tests", str(WARNING_DIR / fixture))
        assert result.returncode == 0, f"expected exit 0; got {result.returncode}\n{result.stdout}"
        payload = json.loads(result.stdout)
        assert payload["blocking"] is False
        verdicts = payload["results"][str(WARNING_DIR / fixture)]
        kinds = [v["kind"] for v in verdicts]
        assert expected_kind in kinds, f"expected {expected_kind} in {kinds}"

    def test_verified_fixture_exits_zero(self) -> None:
        result = _run("verify", "tests", str(FIXTURE_DIR / "verified_ok.py"))
        assert result.returncode == 0, f"expected exit 0; got {result.returncode}\n{result.stdout}"
        payload = json.loads(result.stdout)
        assert payload["blocking"] is False
        verdicts = payload["results"][str(FIXTURE_DIR / "verified_ok.py")]
        assert verdicts[0]["kind"] == "python.verified"

    def test_human_output_is_one_line_per_test(self) -> None:
        result = _run("verify", "tests", str(BLOCKING_DIR / "gamed_tautology.py"), "--human")
        assert "test_login_happy_path" in result.stdout
        assert "python.tautological" in result.stdout

    def test_mixed_files_exits_one_when_any_blocks(self) -> None:
        result = _run(
            "verify",
            "tests",
            str(FIXTURE_DIR / "verified_ok.py"),
            str(BLOCKING_DIR / "gamed_tautology.py"),
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["blocking"] is True


class TestInitPrecommit:
    def test_writes_config_in_fresh_dir(self, tmp_path: Path) -> None:
        result = _run("init-precommit", cwd=tmp_path)
        assert result.returncode == 0, result.stdout
        cfg = tmp_path / ".pre-commit-config.yaml"
        assert cfg.exists()
        body = cfg.read_text(encoding="utf-8")
        assert "pragma verify tests" in body
        assert "id: pragma" in body

    def test_existing_config_blocks_overwrite_without_force(self, tmp_path: Path) -> None:
        (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
        result = _run("init-precommit", cwd=tmp_path)
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["error"] == "exists"
        assert "--force" in payload["remediation"]

    def test_force_overwrites(self, tmp_path: Path) -> None:
        (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
        result = _run("init-precommit", "--force", cwd=tmp_path)
        assert result.returncode == 0
        body = (tmp_path / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        assert "pragma verify tests" in body


class TestBlockingSubcommand:
    def test_blocking_subcommand_prints_json(self) -> None:
        result = _run("blocking")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert "tautological" in payload
        assert "skipped" in payload
        assert "mocked-away" in payload
        # Non-blocking suffix not in the list:
        assert "weak" not in payload
        assert "verified" not in payload


class TestLlmJudge:
    """CLI tests for `pragma verify tests --with-llm`.

    With no API key set, tier 3 skips silently — so results are identical
    to running without --with-llm. This validates the flag is wired correctly
    and doesn't crash when the key is absent.
    """

    def test_with_llm_flag_accepted_no_crash_when_key_missing(self) -> None:
        """--with-llm with no PRAGMA_ANTHROPIC_API_KEY exits 0 on a verified fixture."""
        fixture = FIXTURE_DIR / "verified_ok.py"
        env = {**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT / "src")}
        env.pop("PRAGMA_ANTHROPIC_API_KEY", None)  # ensure key is absent
        result = _run("verify", "tests", "--with-llm", str(fixture))
        assert result.returncode == 0, f"expected exit 0; got {result.returncode}\n{result.stderr}"
        payload = __import__("json").loads(result.stdout)
        assert payload["blocking"] is False

    def test_with_llm_flag_shown_in_help(self) -> None:
        # Wide terminal so Typer's Rich renderer doesn't wrap the flag name.
        env_path = str(REPO_ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-m", "pragma", "verify", "tests", "--help"],
            capture_output=True,
            text=True,
            env={
                **__import__("os").environ,
                "PYTHONPATH": env_path,
                "COLUMNS": "200",
                "TERM": "dumb",
            },
            check=False,
        )
        assert result.returncode == 0
        # Strip ANSI escape sequences and whitespace, then assert the flag appears.
        import re

        clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        clean = re.sub(r"\s+", " ", clean)
        assert "--with-llm" in clean, clean[:500]

    def test_semantic_gaming_not_in_blocking_suffixes(self) -> None:
        """pragma blocking must NOT include semantic_gaming."""
        result = _run("blocking")
        assert result.returncode == 0
        payload = __import__("json").loads(result.stdout)
        assert "semantic_gaming" not in payload


class TestCoverageGate:
    """End-to-end tests for `pragma verify tests --with-coverage`.

    Uses the existing tests/fixtures/coverage_gated/ fixtures from
    step 1. The conftest in that directory adds src/ to sys.path so
    inference resolves `inventory` correctly.
    """

    def test_no_flag_keeps_verified_on_imports_only(self) -> None:
        """Without --with-coverage, the orphan-import fixture stays verified."""
        fixture = (
            REPO_ROOT / "tests" / "fixtures" / "coverage_gated" / "test_inventory_imports_only.py"
        )
        result = _run("verify", "tests", str(fixture))
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["blocking"] is False
        verdicts = payload["results"][str(fixture)]
        assert any(v["kind"] == "python.verified" for v in verdicts)

    def test_with_flag_conservative_when_no_inferable_target(self) -> None:
        """With --with-coverage, a fixture with no inferable target stays verified.

        test_inventory_imports_only.py imports reserve but never calls it,
        so infer_target returns (None, None). Gate is conservative: no
        target inference → keep verified. This test confirms the flag is
        accepted and forwarded, and that the gate's conservative behavior
        is preserved end-to-end.
        """
        fixture = (
            REPO_ROOT / "tests" / "fixtures" / "coverage_gated" / "test_inventory_imports_only.py"
        )
        result = _run("verify", "tests", "--with-coverage", str(fixture))
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["blocking"] is False
        verdicts = payload["results"][str(fixture)]
        assert any(v["kind"] == "python.verified" for v in verdicts)

    def test_with_flag_keeps_verified_on_real_test(self) -> None:
        """The honest fixture stays verified even with --with-coverage."""
        fixture = REPO_ROOT / "tests" / "fixtures" / "coverage_gated" / "test_inventory_real.py"
        result = _run("verify", "tests", "--with-coverage", str(fixture))
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["blocking"] is False
        verdicts = payload["results"][str(fixture)]
        assert any(v["kind"] == "python.verified" for v in verdicts)

    def test_blocking_subcommand_includes_target_not_covered(self) -> None:
        """`pragma blocking` returns target_not_covered in the suffix list."""
        result = _run("blocking")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert "target_not_covered" in payload
