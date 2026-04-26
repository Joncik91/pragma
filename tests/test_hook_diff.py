"""End-to-end tests for plugin/hooks/check_diff.py — diff-mode rejection.

These exercise the hook script as a subprocess against fabricated git
repos so we catch regressions in tempfile naming, language matching,
and the new-vs-old diff logic.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "plugin" / "hooks" / "check_diff.py"


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], cwd=path)
    _git(["config", "user.email", "t@t.t"], cwd=path)
    _git(["config", "user.name", "hook-test"], cwd=path)


def _commit_file(repo: Path, rel: str, body: str) -> None:
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    _git(["add", rel], cwd=repo)
    _git(["commit", "-q", "-m", f"add {rel}"], cwd=repo)


def _run_hook(on_disk: Path, candidate: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(HOOK), str(on_disk), str(candidate)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    if not shutil.which("git"):
        pytest.skip("git not on PATH")
    if not shutil.which("pragma"):
        pytest.skip("pragma not on PATH")
    r = tmp_path / "repo"
    _init_repo(r)
    return r


def test_hook_allows_when_old_and_new_have_same_blocking_names(repo: Path) -> None:
    """Edit that touches an unrelated test must not block on pre-existing gaming."""
    body_v1 = (
        "def test_smoke():\n"
        "    assert True  # pre-existing gaming\n"
        "\n"
        "def test_other():\n"
        "    assert 1 == 2  # also pre-existing\n"
    )
    _commit_file(repo, "tests/test_x.py", body_v1)

    # New version adds a comment but keeps the same gamed tests.
    body_v2 = body_v1 + "\n# new comment, no behavior change\n"
    target = repo / "tests" / "test_x.py"
    target.write_text(body_v2, encoding="utf-8")

    result = _run_hook(target, target)
    # Pre-existing gaming is the user's history; the diff-mode hook
    # only blocks NEW gaming. Same names before and after → allow.
    assert result.returncode == 0, (
        f"hook should have allowed but exited {result.returncode}; stderr:\n{result.stderr}"
    )


def test_hook_blocks_when_edit_introduces_new_gaming(repo: Path) -> None:
    body_v1 = "def test_existing():\n    result = 1 + 1\n    assert result == 2\n"
    _commit_file(repo, "tests/test_y.py", body_v1)

    body_v2 = body_v1 + "\n\ndef test_new_smoke():\n    assert True\n"
    target = repo / "tests" / "test_y.py"
    target.write_text(body_v2, encoding="utf-8")

    result = _run_hook(target, target)
    assert result.returncode == 2, (
        f"expected block (exit 2) but got {result.returncode}; stderr:\n{result.stderr}"
    )
    assert "test_new_smoke" in result.stderr
