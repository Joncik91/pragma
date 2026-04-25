"""Red tests for REQ-039 — commit-shape check skips pre-Pragma history.

BUG-047. Round-18 strict brownfield walkthrough surfaced this:
`pragma verify all` running pre-commit walked the entire git history
and rejected every pre-Pragma commit for missing WHY/Co-Authored-By.
The whole point of brownfield is to adopt Pragma into a repo with
existing history — Pragma cannot reasonably retro-impose its commit
shape on commits that predate its adoption.

Fix - when the configured `--base` ref does not exist (sandbox on
`master` while base defaults to `main`), scope the range to commits
that touched `pragma.yaml`. Pre-Pragma commits are exempt by
definition. When pragma.yaml is staged for the very first adopt
commit, return an empty range so the check trivially passes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from pragma_sdk import set_permutation, trace

from pragma.cli.commands.verify_checks import _git_range_spec


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def _seed_repo(cwd: Path) -> None:
    _git(cwd, "init", "-q")
    _git(cwd, "config", "user.email", "t@t.t")
    _git(cwd, "config", "user.name", "t")


@trace("REQ-039")
def _assert_pre_adopt_history_excluded(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "pre.txt").write_text("pre-pragma\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial")
    (tmp_path / "pragma.yaml").write_text("version: '2'\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(
        tmp_path,
        "commit",
        "-q",
        "-m",
        "chore: adopt pragma\n\nWHY: w\n\nCo-Authored-By: x <x@x.x>",
    )
    spec = _git_range_spec(tmp_path, "main")
    assert spec.endswith("..HEAD"), f"range must skip pre-Pragma history; got {spec!r}"
    assert spec != "HEAD", "range must not walk full history when adopt-commit exists"


@trace("REQ-039")
def _assert_first_adopt_commit_in_progress(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "pre.txt").write_text("pre-pragma\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial")
    (tmp_path / "pragma.yaml").write_text("version: '2'\n", encoding="utf-8")
    _git(tmp_path, "add", "pragma.yaml")
    spec = _git_range_spec(tmp_path, "main")
    assert spec == "HEAD..HEAD", (
        f"range must yield zero commits when adopt is in flight; got {spec!r}"
    )


def test_req_039_pre_adopt_history_excluded(tmp_path: Path) -> None:
    with set_permutation("pre_adopt_history_excluded"):
        _assert_pre_adopt_history_excluded(tmp_path)


def test_req_039_first_adopt_commit_in_progress(tmp_path: Path) -> None:
    with set_permutation("first_adopt_commit_in_progress"):
        _assert_first_adopt_commit_in_progress(tmp_path)
