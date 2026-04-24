"""Red tests for REQ-015 - pragma package pyproject separates runtime and dev deps.

BUG-019 (ex-KI-14). pre-v1.0.6 `packages/pragma/pyproject.toml` listed
dev-only tools under `[project.dependencies]`. Deptry flagged all of
them as DEP002 unused-at-runtime. Fix: move them to
`[project.optional-dependencies.dev]` so runtime installs stay lean
and `pip install pragma[dev]` pulls the full set.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

from pragma_sdk import set_permutation, trace

_DEV_TOOL_NAMES = frozenset(
    {
        "ruff",
        "mypy",
        "pytest-cov",
        "pre-commit",
        "types-PyYAML",
        "opentelemetry-api",
        "opentelemetry-sdk",
    }
)


def _pragma_package_root() -> Path:
    return Path(__file__).resolve().parents[3] / "pragma"


def _load_pyproject() -> dict:
    text = (_pragma_package_root() / "pyproject.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)


def _dep_name(spec: str) -> str:
    """Extract the package name from a PEP 508 dep string."""
    for sep in (">=", "<=", "==", ">", "<", "~=", "!="):
        if sep in spec:
            return spec.split(sep, 1)[0].strip()
    return spec.split("[", 1)[0].strip()


@trace("REQ-015")
def _assert_runtime_deps_do_not_include_dev_tools() -> None:
    data = _load_pyproject()
    runtime = {_dep_name(d) for d in data["project"].get("dependencies", [])}
    overlap = runtime & _DEV_TOOL_NAMES
    assert not overlap, (
        f"runtime deps must not list dev tools; found {sorted(overlap)!r} under "
        "project.dependencies — move them to project.optional-dependencies.dev"
    )


@trace("REQ-015")
def _assert_dev_extra_contains_dev_tools() -> None:
    data = _load_pyproject()
    dev = data["project"].get("optional-dependencies", {}).get("dev", [])
    dev_names = {_dep_name(d) for d in dev}
    missing = _DEV_TOOL_NAMES - dev_names
    assert not missing, (
        f"project.optional-dependencies.dev must list every dev tool; missing {sorted(missing)!r}"
    )


@trace("REQ-015")
def _assert_deptry_clean_on_pragma_package() -> None:
    pkg = _pragma_package_root()
    # Deptry is a dev-only tool; when it isn't installed in the test
    # environment (bare CI matrix without `pip install pragma[dev]`)
    # there's nothing to assert on. Pre-commit runs deptry directly
    # via the .pre-commit-config hook, so coverage is not lost.
    deptry_check = subprocess.run(
        [sys.executable, "-c", "import deptry"],
        capture_output=True,
        text=True,
    )
    if deptry_check.returncode != 0:
        import pytest as _pytest

        _pytest.skip("deptry not installed in this environment")
    proc = subprocess.run(
        [sys.executable, "-m", "deptry", "src"],
        capture_output=True,
        text=True,
        cwd=str(pkg),
    )
    assert proc.returncode == 0, (
        f"deptry must be clean on packages/pragma after dep reshape; "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def test_req_015_runtime_deps_do_not_include_dev_tools() -> None:
    with set_permutation("runtime_deps_do_not_include_dev_tools"):
        _assert_runtime_deps_do_not_include_dev_tools()


def test_req_015_dev_extra_contains_dev_tools() -> None:
    with set_permutation("dev_extra_contains_dev_tools"):
        _assert_dev_extra_contains_dev_tools()


def test_req_015_deptry_clean_on_pragma_package() -> None:
    with set_permutation("deptry_clean_on_pragma_package"):
        _assert_deptry_clean_on_pragma_package()
