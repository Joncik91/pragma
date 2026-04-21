"""End-to-end test: a scaffolded Pragma project blocks drifted commits.

This test spins up a throwaway git repo, installs Pragma into it via
`pragma init --brownfield`, makes a commit, then edits pragma.yaml
without running `pragma freeze`, and asserts that the pre-commit hook
blocks the next commit. This is the one integration test that proves
v0.1's single user-visible value delivery works end-to-end.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VENV_BIN = _REPO_ROOT / ".venv" / "bin"


def _have(cmd: str) -> bool:
    # Check venv first (Pragma's install location), then fall back to PATH.
    if (_VENV_BIN / cmd).exists():
        return True
    return shutil.which(cmd) is not None


@pytest.mark.skipif(not _have("git"), reason="git required for e2e")
@pytest.mark.skipif(not _have("pre-commit"), reason="pre-commit required for e2e")
def test_precommit_blocks_commit_when_lock_is_stale(tmp_project: Path) -> None:
    # Prepend .venv/bin so pragma + pre-commit resolve correctly even if the
    # test runner was invoked with the system Python.
    env = {
        **os.environ,
        "PATH": f"{_VENV_BIN}{os.pathsep}{os.environ.get('PATH', '')}",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@t",
    }

    def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            cwd=tmp_project,
            env=env,
            capture_output=True,
            text=True,
            check=check,
        )

    # Initialise a git repo and Pragma.
    run("git", "init", "-q")
    run("pragma", "init", "--brownfield", "--name", "e2e")
    run("pragma", "freeze")

    # The v0.3 default battery pulls gitleaks/ruff/mypy/semgrep/pip-audit/
    # deptry from public repos. This e2e asserts one specific invariant —
    # that pragma verify all blocks a commit with a stale lockfile — and
    # shouldn't depend on the sandbox's ability to reach those repos or on
    # semgrep/deptry being runnable here. Replace the generated config with
    # a minimal one that only runs pragma verify all locally.
    (tmp_project / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: pragma-verify-all\n"
        "        name: pragma verify all\n"
        "        entry: python3 -m pragma verify all\n"
        "        language: system\n"
        "        pass_filenames: false\n"
        "        always_run: true\n"
        "        stages: [pre-commit]\n",
        encoding="utf-8",
    )
    run("pre-commit", "install", "--install-hooks")

    # Baseline commit — should succeed.
    run("git", "add", ".")
    first = run("git", "commit", "-m", "chore: adopt pragma")
    assert first.returncode == 0, first.stderr

    # Drift: edit pragma.yaml without re-freezing.
    yaml_path = tmp_project / "pragma.yaml"
    yaml_path.write_text(yaml_path.read_text().replace('name: "e2e"', 'name: "drifted"'))
    run("git", "add", "pragma.yaml")

    blocked = run("git", "commit", "-m", "drift", check=False)
    assert blocked.returncode != 0, (
        "pre-commit should have blocked a commit with a stale lockfile; "
        f"stdout={blocked.stdout!r} stderr={blocked.stderr!r}"
    )
    assert "manifest_hash_mismatch" in blocked.stdout + blocked.stderr
