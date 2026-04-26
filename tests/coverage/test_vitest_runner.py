"""Tests for run_vitest_with_coverage.

All subprocess calls are monkeypatched so CI does not require Node or vitest.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from pragma.coverage.runner import run_vitest_with_coverage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_vitest_package_json(project_root: Path) -> Path:
    """Write a package.json with vitest in devDependencies."""
    pkg = project_root / "package.json"
    pkg.write_text(
        json.dumps(
            {
                "name": "test-project",
                "devDependencies": {
                    "vitest": "^1.0.0",
                    "@vitest/coverage-v8": "^1.0.0",
                },
            }
        )
    )
    return pkg


def _write_test_file(project_root: Path, name: str = "src/foo.test.ts") -> Path:
    """Write a stub test file at the given relative path."""
    p = project_root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "import { describe, it } from 'vitest';\n"
        "describe('foo', () => { it('works', () => {}); });\n"
    )
    return p


def _write_target_file(project_root: Path, name: str = "src/foo.ts") -> Path:
    """Write a stub target file."""
    p = project_root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("export function add(a: number, b: number): number { return a + b; }\n")
    return p


def _make_fake_subprocess_run(coverage_dir_holder: list[Path]):
    """Return a fake subprocess.run that writes coverage-final.json into coverage dir."""

    def fake_run(cmd, **kwargs):
        # Extract --coverage.reportsDirectory=<dir> from cmd
        for arg in cmd:
            if arg.startswith("--coverage.reportsDirectory="):
                cov_dir = Path(arg.split("=", 1)[1])
                cov_dir.mkdir(parents=True, exist_ok=True)
                report = cov_dir / "coverage-final.json"
                report.write_text(json.dumps({}))
                coverage_dir_holder.append(cov_dir)
                break
        return subprocess.CompletedProcess(cmd, returncode=0)

    return fake_run


# ---------------------------------------------------------------------------
# Guard tests — missing files / missing project root
# ---------------------------------------------------------------------------


def test_run_vitest_returns_none_when_test_path_missing(tmp_path: Path) -> None:
    """test_path does not exist → None immediately."""
    target = _write_target_file(tmp_path)
    result = run_vitest_with_coverage(tmp_path / "nope.test.ts", target)
    assert result is None


def test_run_vitest_returns_none_when_target_file_missing(tmp_path: Path) -> None:
    """target_file does not exist → None immediately."""
    _write_vitest_package_json(tmp_path)
    test_file = _write_test_file(tmp_path)
    result = run_vitest_with_coverage(test_file, tmp_path / "nonexistent.ts")
    assert result is None


def test_run_vitest_returns_none_when_no_package_json(tmp_path: Path) -> None:
    """No package.json in any ancestor → None (no vitest project found)."""
    # Create files inside a deep subdirectory, but NO package.json anywhere.
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    test_file = deep / "foo.test.ts"
    target = deep / "foo.ts"
    test_file.write_text("// test\n")
    target.write_text("// src\n")

    result = run_vitest_with_coverage(test_file, target)
    assert result is None


def test_run_vitest_returns_none_when_package_json_lacks_vitest(tmp_path: Path) -> None:
    """package.json exists but has no vitest → None."""
    pkg = tmp_path / "package.json"
    pkg.write_text(json.dumps({"name": "proj", "devDependencies": {"jest": "^29.0.0"}}))
    test_file = _write_test_file(tmp_path)
    target = _write_target_file(tmp_path)

    result = run_vitest_with_coverage(test_file, target)
    assert result is None


def test_run_vitest_returns_none_when_package_json_is_malformed(tmp_path: Path) -> None:
    """Malformed package.json → skip that candidate, return None if no other found."""
    pkg = tmp_path / "package.json"
    pkg.write_text("this is not json {{")
    test_file = _write_test_file(tmp_path)
    target = _write_target_file(tmp_path)

    result = run_vitest_with_coverage(test_file, target)
    assert result is None


# ---------------------------------------------------------------------------
# Subprocess failure tests — all monkeypatched
# ---------------------------------------------------------------------------


def test_run_vitest_returns_none_when_npx_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """subprocess.run raises FileNotFoundError (npx not on PATH) → None."""
    _write_vitest_package_json(tmp_path)
    test_file = _write_test_file(tmp_path)
    target = _write_target_file(tmp_path)

    def raise_fnf(*a, **kw):
        raise FileNotFoundError("npx not found")

    monkeypatch.setattr(subprocess, "run", raise_fnf)

    result = run_vitest_with_coverage(test_file, target)
    assert result is None


def test_run_vitest_returns_none_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """subprocess.run raises TimeoutExpired → None."""
    _write_vitest_package_json(tmp_path)
    test_file = _write_test_file(tmp_path)
    target = _write_target_file(tmp_path)

    def fake_timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd=["npx", "vitest"], timeout=8)

    monkeypatch.setattr(subprocess, "run", fake_timeout)

    result = run_vitest_with_coverage(test_file, target)
    assert result is None


def test_run_vitest_returns_none_when_report_not_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """subprocess exits 0 but no coverage-final.json produced → None."""
    _write_vitest_package_json(tmp_path)
    test_file = _write_test_file(tmp_path)
    target = _write_target_file(tmp_path)

    def no_op(*a, **kw):
        return subprocess.CompletedProcess(a[0] if a else [], returncode=0)

    monkeypatch.setattr(subprocess, "run", no_op)

    result = run_vitest_with_coverage(test_file, target)
    assert result is None


def test_run_vitest_returns_none_on_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """subprocess.run raises OSError → None."""
    _write_vitest_package_json(tmp_path)
    test_file = _write_test_file(tmp_path)
    target = _write_target_file(tmp_path)

    def raise_oserr(*a, **kw):
        raise OSError("exec error")

    monkeypatch.setattr(subprocess, "run", raise_oserr)

    result = run_vitest_with_coverage(test_file, target)
    assert result is None


# ---------------------------------------------------------------------------
# Positive test
# ---------------------------------------------------------------------------


def test_run_vitest_returns_path_when_subprocess_writes_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subprocess writes coverage-final.json → runner returns that path."""
    _write_vitest_package_json(tmp_path)
    test_file = _write_test_file(tmp_path)
    target = _write_target_file(tmp_path)

    coverage_dir_holder: list[Path] = []
    monkeypatch.setattr(subprocess, "run", _make_fake_subprocess_run(coverage_dir_holder))

    result = run_vitest_with_coverage(test_file, target)

    assert result is not None
    assert isinstance(result, Path)
    assert result.exists()
    assert result.name == "coverage-final.json"


def test_run_vitest_cmd_includes_target_and_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The npx command includes coverage.include for target file and test file."""
    _write_vitest_package_json(tmp_path)
    test_file = _write_test_file(tmp_path)
    target = _write_target_file(tmp_path)

    captured_cmd: list[list[str]] = []

    def capturing_run(cmd, **kwargs):
        captured_cmd.append(list(cmd))
        # Also write the report so the function can succeed.
        for arg in cmd:
            if arg.startswith("--coverage.reportsDirectory="):
                cov_dir = Path(arg.split("=", 1)[1])
                cov_dir.mkdir(parents=True, exist_ok=True)
                (cov_dir / "coverage-final.json").write_text("{}")
        return subprocess.CompletedProcess(cmd, returncode=0)

    monkeypatch.setattr(subprocess, "run", capturing_run)
    run_vitest_with_coverage(test_file, target)

    assert len(captured_cmd) == 1
    cmd = captured_cmd[0]
    # Must include coverage provider and json reporter flags.
    assert "--coverage.enabled=true" in cmd
    assert "--coverage.provider=v8" in cmd
    assert "--coverage.reporter=json" in cmd
    # Must include coverage.include pointing at the target file.
    include_flags = [a for a in cmd if a.startswith("--coverage.include=")]
    assert len(include_flags) == 1
    assert "foo.ts" in include_flags[0]


def test_run_vitest_finds_package_json_in_ancestor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """package.json in a grandparent dir is found correctly."""
    _write_vitest_package_json(tmp_path)
    # Put the test file in a subdirectory.
    sub = tmp_path / "packages" / "core" / "src"
    sub.mkdir(parents=True)
    test_file = sub / "core.test.ts"
    target = sub / "core.ts"
    test_file.write_text("// test\n")
    target.write_text("// src\n")

    coverage_dir_holder: list[Path] = []
    monkeypatch.setattr(subprocess, "run", _make_fake_subprocess_run(coverage_dir_holder))

    result = run_vitest_with_coverage(test_file, target)
    assert result is not None
