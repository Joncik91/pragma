"""Tests for `pragma spec plan-greenfield` — Pattern C bootstrap."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_init_greenfield(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pragma",
            "init",
            "--greenfield",
            "--name",
            "demo",
            "--language",
            "python",
        ],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _run_init_brownfield(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pragma", "init", "--brownfield", "--name", "demo"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _run_plan(cwd: Path, problem_path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pragma",
            "spec",
            "plan-greenfield",
            "--from",
            problem_path,
        ],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def test_plan_greenfield_emits_skeleton(tmp_path: Path) -> None:
    init_result = _run_init_greenfield(tmp_path)
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr

    (tmp_path / "problem.md").write_text(
        "# Register\n\nUsers sign up.\n\n# Login\n\nUsers sign in.\n",
        encoding="utf-8",
    )

    result = _run_plan(tmp_path, "problem.md")
    assert result.returncode == 0, result.stdout + result.stderr

    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["wrote"] == "pragma.yaml"
    assert payload["requirements"] == ["REQ-001", "REQ-002"]

    manifest_text = (tmp_path / "pragma.yaml").read_text(encoding="utf-8")
    assert "Register" in manifest_text
    assert "Login" in manifest_text
    assert "REQ-001" in manifest_text
    assert "REQ-002" in manifest_text
    assert "REQ-000" not in manifest_text

    # Lockfile must also have been refreshed (no leftover REQ-000).
    lock_text = (tmp_path / "pragma.lock.json").read_text(encoding="utf-8")
    assert "REQ-001" in lock_text
    assert "REQ-000" not in lock_text


def test_plan_greenfield_rebinds_state_to_new_hash(tmp_path: Path) -> None:
    """BUG-012: plan-greenfield must leave pragma verify all green.

    pragma init --greenfield primes .pragma/state.json with the seed
    manifest's hash. plan-greenfield rewrites pragma.yaml and refreezes
    the lock - so without the state-rebind fix, the next pragma verify
    all fires gate_hash_drift because state.manifest_hash points at the
    pre-plan hash. This is the day-one greenfield flow; it must not
    brick. Guard against regression by running `pragma verify all` end
    to end after plan and asserting exit 0.
    """
    init_result = _run_init_greenfield(tmp_path)
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr

    (tmp_path / "problem.md").write_text(
        "# Area\nOne.\n\n# Other\nTwo.\n",
        encoding="utf-8",
    )
    plan = _run_plan(tmp_path, "problem.md")
    assert plan.returncode == 0, plan.stdout + plan.stderr

    verify = subprocess.run(
        [sys.executable, "-m", "pragma", "verify", "all"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert verify.returncode == 0, (
        "verify all must be green immediately after "
        f"init --greenfield + plan-greenfield; got {verify.stdout!r}"
    )


def test_plan_greenfield_missing_file(tmp_path: Path) -> None:
    init_result = _run_init_greenfield(tmp_path)
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr

    result = _run_plan(tmp_path, "does-not-exist.md")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "problem_statement_missing" in result.stdout


def test_plan_greenfield_empty_file(tmp_path: Path) -> None:
    init_result = _run_init_greenfield(tmp_path)
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr

    (tmp_path / "problem.md").write_text("", encoding="utf-8")

    result = _run_plan(tmp_path, "problem.md")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "problem_statement_missing" in result.stdout


def test_plan_greenfield_no_headers(tmp_path: Path) -> None:
    init_result = _run_init_greenfield(tmp_path)
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr

    (tmp_path / "problem.md").write_text(
        "Just some prose, nothing that looks like a heading.\n"
        "More prose here to make it non-empty.\n",
        encoding="utf-8",
    )

    result = _run_plan(tmp_path, "problem.md")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "problem_statement_missing" in result.stdout


def test_plan_greenfield_refuses_brownfield(tmp_path: Path) -> None:
    init_result = _run_init_brownfield(tmp_path)
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr

    (tmp_path / "problem.md").write_text("# Topic\n\nwords\n", encoding="utf-8")

    result = _run_plan(tmp_path, "problem.md")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "plan_greenfield_on_brownfield" in result.stdout


def test_plan_greenfield_refuses_second_run(tmp_path: Path) -> None:
    init_result = _run_init_greenfield(tmp_path)
    assert init_result.returncode == 0, init_result.stdout + init_result.stderr

    (tmp_path / "problem.md").write_text(
        "# Register\n\nUsers sign up.\n\n# Login\n\nUsers sign in.\n",
        encoding="utf-8",
    )

    first = _run_plan(tmp_path, "problem.md")
    assert first.returncode == 0, first.stdout + first.stderr

    second = _run_plan(tmp_path, "problem.md")
    assert second.returncode == 1, second.stdout + second.stderr
    assert "plan_greenfield_already_planned" in second.stdout
