"""Red tests for REQ-040 — scaffolded pytest hook tolerates "no tests."

BUG-048. Round-18 brownfield walkthrough: scaffolded brownfield
project has no tests/ dir, so pytest exits 5 ("no tests collected")
and pre-commit treats that as a hook failure. The user cannot land
the very first adopt-pragma commit until they manually create a
tests/ dir and a placeholder test.

Fix - scaffolded pytest hook suppresses exit 5 to 0 (no tests is a
legitimate state for a freshly-adopted brownfield repo). Every other
exit code still propagates so real failures still block.
"""

from __future__ import annotations

from pathlib import Path

from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


@trace("REQ-040")
def _assert_pytest_hook_suppresses_exit_5(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--brownfield"])
    assert result.exit_code == 0, result.stdout
    config = (tmp_path / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "rc=$?" in config and '[ "$rc" -eq 5 ]' in config, (
        f"scaffolded pytest hook must trap exit 5 (no tests collected); got:\n{config}"
    )


@trace("REQ-040")
def _assert_pytest_hook_propagates_other_failures(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--brownfield"])
    assert result.exit_code == 0
    config = (tmp_path / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    # Exit code 1 (test failure) and 2 (collection error) must still
    # fail the hook — the trap is exit-5-specific.
    assert 'exit "$rc"' in config, (
        f"scaffolded pytest hook must propagate non-5 exit codes; got:\n{config}"
    )


def test_req_040_pytest_hook_suppresses_exit_5(tmp_path: Path, monkeypatch) -> None:
    with set_permutation("pytest_hook_suppresses_exit_5"):
        _assert_pytest_hook_suppresses_exit_5(tmp_path, monkeypatch)


def test_req_040_pytest_hook_propagates_other_failures(tmp_path: Path, monkeypatch) -> None:
    with set_permutation("pytest_hook_propagates_other_failures"):
        _assert_pytest_hook_propagates_other_failures(tmp_path, monkeypatch)
