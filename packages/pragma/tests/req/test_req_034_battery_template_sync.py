"""Red tests for REQ-034 — scaffolded pre-commit template stays in sync.

BUG-038/039 from round-7 confirmation. The scaffolded pytest hook
fired bare `python3 -m pytest`, missing pytest on systems without
a project venv; pip-audit had no `args:` entry to ignore the same
pip advisory the project's own config ignores. New users hit both
immediately.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _git_init(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)


def _scaffold_brownfield(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    _git_init(tmp_project)
    monkeypatch.chdir(tmp_project)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "demo"]).exit_code == 0
    return (tmp_project / ".pre-commit-config.yaml").read_text(encoding="utf-8")


@trace("REQ-034")
def _assert_pytest_hook_uses_resolution_chain(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _scaffold_brownfield(tmp_project, monkeypatch)
    # The pytest hook entry must reference the init-time interpreter
    # (BUG-037 chain) instead of bare `python3 -m pytest`.
    assert sys.executable in config, "init-time interpreter missing from scaffold"
    # Find the pytest hook block and assert its entry uses the chain.
    assert "id: pytest" in config
    pytest_block_start = config.index("id: pytest")
    pytest_block = config[pytest_block_start : pytest_block_start + 400]
    assert sys.executable in pytest_block, (
        f"pytest hook must use the {{ pragma_python_bin }} chain; got:\n{pytest_block}"
    )
    # And must NOT bare-invoke python3 directly (the BUG-038 shape).
    assert "entry: python3 -m pytest" not in pytest_block, (
        f"pytest hook must not bare-invoke python3; got:\n{pytest_block}"
    )


@trace("REQ-034")
def _assert_pip_audit_ignores_known_pip_advisory(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _scaffold_brownfield(tmp_project, monkeypatch)
    assert "GHSA-58qw-9mgm-455v" in config, (
        "scaffolded pip-audit must ignore GHSA-58qw-9mgm-455v "
        "(BUG-039); the advisory has no fix and pip is transitive."
    )
    # Sanity: ensure the ignore is on the pip-audit hook, not just a
    # comment somewhere unrelated.
    pa_idx = config.index("id: pip-audit")
    pa_block = config[pa_idx : pa_idx + 400]
    assert "GHSA-58qw-9mgm-455v" in pa_block, (
        f"GHSA-58qw-9mgm-455v ignore must be on the pip-audit hook; got:\n{pa_block}"
    )


def test_req_034_pytest_hook_uses_resolution_chain(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("pytest_hook_uses_resolution_chain"):
        _assert_pytest_hook_uses_resolution_chain(tmp_project, monkeypatch)


def test_req_034_pip_audit_ignores_known_pip_advisory(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("pip_audit_ignores_known_pip_advisory"):
        _assert_pip_audit_ignores_known_pip_advisory(tmp_project, monkeypatch)
