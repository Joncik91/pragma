"""Dogfood tests for REQ-007 - pre-commit ruff rev matches local ruff.

Asserts that .pre-commit-config.yaml pins a ruff-pre-commit rev that
matches the local ruff version used in the venv, so ruff-format run
locally and by pre-commit agree on output and CI does not need
SKIP=ruff-format as a workaround.

Wrapped in a thin @trace("REQ-007") helper so the span carries
logic_id=REQ-007; otherwise the work happens in bare subprocess calls
and the PIL aggregator would tag the permutations as mocked.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml
from pragma_sdk import set_permutation, trace

REPO_ROOT = Path(__file__).resolve().parents[4]


def _pinned_ruff_rev() -> str:
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    for repo in config["repos"]:
        if "ruff-pre-commit" in repo["repo"]:
            return str(repo["rev"]).lstrip("v")
    raise AssertionError("ruff-pre-commit repo missing from .pre-commit-config.yaml")


def _local_ruff_version() -> str:
    out = subprocess.run(
        [sys.executable, "-m", "ruff", "--version"],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    m = re.search(r"ruff\s+(\S+)", out)
    assert m, f"Could not parse ruff version from {out!r}"
    return m.group(1)


@trace("REQ-007")
def _assert_rev_matches_local() -> None:
    pinned = _pinned_ruff_rev()
    local = _local_ruff_version()
    assert pinned == local, (
        f"pre-commit ruff rev {pinned!r} must match local ruff version "
        f"{local!r} so ruff-format output is stable between local and CI."
    )


@trace("REQ-007")
def _assert_ci_format_check_green() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "packages/"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"ruff format --check must pass under the pinned rev without "
        f"SKIP=ruff-format; stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def test_req_007_rev_matches_local() -> None:
    with set_permutation("rev_matches_local"):
        _assert_rev_matches_local()


def test_req_007_ci_format_check_green() -> None:
    with set_permutation("ci_format_check_green"):
        _assert_ci_format_check_green()
