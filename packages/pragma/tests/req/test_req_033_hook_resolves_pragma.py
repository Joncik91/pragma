"""Red tests for REQ-033 — scaffolded pre-commit hook resolves pragma.

BUG-037. Round-7 dogfood follow-up: BUG-036 made init install hooks,
but the hooks themselves fire `python -m pragma` against `.venv/bin/
python3` with fallback to system `python3`. A user with no project-
local venv (common in first-run sandboxes) hits "No module named
pragma.__main__" because system Python does not have pragma. Fix
bakes the init-time interpreter into the rendered config.
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


@trace("REQ-033")
def _assert_hook_uses_init_python(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _git_init(tmp_project)
    monkeypatch.chdir(tmp_project)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "demo"]).exit_code == 0
    config = (tmp_project / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    # The interpreter that ran init must appear in the rendered config
    # so the hook can invoke pragma without depending on a project venv.
    assert sys.executable in config, (
        f"scaffolded .pre-commit-config.yaml must reference the init-time "
        f"interpreter {sys.executable!r}; got:\n{config[:500]}"
    )


@trace("REQ-033")
def _assert_bad_commit_blocked_after_init(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init(tmp_project)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(tmp_project), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(tmp_project), check=True)
    monkeypatch.chdir(tmp_project)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "demo"]).exit_code == 0
    # Freeze so verify-all has a lock to read.
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    # Stage a trivial change.
    (tmp_project / "x.txt").write_text("hi", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_project), check=True)
    # Try a malformed commit message — no body, no WHY, no trailer.
    result = subprocess.run(
        ["git", "commit", "-m", "feat: malformed"],
        cwd=str(tmp_project),
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        f"git commit with malformed message must be blocked by the "
        f"commit-msg hook; got rc={result.returncode}\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    combined = result.stdout + result.stderr
    # Either the commit-msg shape hook fires (preferred) or the
    # pre-commit verify-all hook catches the missing artifacts; both
    # are correct refusal paths.
    accepted_signals = ("shape", "WHY", "Co-Authored-By", "commit_shape_violation")
    assert any(sig in combined for sig in accepted_signals) or "pragma" in combined.lower(), (
        f"hook output must point at a pragma refusal; got:\n{combined}"
    )
    # Negative: the system-python module-not-found error must NOT
    # appear (that was the BUG-037 symptom).
    assert "No module named pragma.__main__" not in combined, (
        f"BUG-037 regression — system python invoked instead of init-time "
        f"interpreter; got:\n{combined}"
    )


def test_req_033_hook_uses_init_python(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with set_permutation("hook_uses_init_python"):
        _assert_hook_uses_init_python(tmp_project, monkeypatch)


def test_req_033_bad_commit_blocked_after_init(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("bad_commit_blocked_after_init"):
        _assert_bad_commit_blocked_after_init(tmp_project, monkeypatch)
