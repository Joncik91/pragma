from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pragma", "init", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def test_greenfield_creates_seed_manifest(tmp_path: Path) -> None:
    result = _run(tmp_path, "--greenfield", "--name", "demo", "--language", "python")

    assert result.returncode == 0, result.stdout + result.stderr

    manifest_text = (tmp_path / "pragma.yaml").read_text(encoding="utf-8")
    assert "mode: greenfield" in manifest_text
    assert "M01" in manifest_text
    assert "REQ-000" in manifest_text

    for rel in (
        "pragma.lock.json",
        ".pragma/state.json",
        "claude.md",
        "PRAGMA.md",
        ".pre-commit-config.yaml",
        ".claude/settings.json",
    ):
        assert (tmp_path / rel).exists(), f"missing {rel}"

    for rel in ("src", "tests"):
        d = tmp_path / rel
        assert d.is_dir(), f"missing directory {rel}"


def test_greenfield_refuses_nonempty_src(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "anything.py").write_text("x = 1\n", encoding="utf-8")

    result = _run(tmp_path, "--greenfield", "--name", "demo", "--language", "python")

    assert result.returncode != 0
    assert "greenfield_non_empty_src" in result.stdout


def test_greenfield_requires_name(tmp_path: Path) -> None:
    result = _run(tmp_path, "--greenfield", "--language", "python")

    assert result.returncode == 1, result.stdout + result.stderr
    assert "name_required" in result.stdout


def test_greenfield_refuses_both_modes(tmp_path: Path) -> None:
    result = _run(tmp_path, "--brownfield", "--greenfield", "--name", "demo")

    assert result.returncode == 2, result.stdout + result.stderr
    assert "both_modes" in result.stdout


def test_greenfield_refuses_existing_manifest(tmp_path: Path) -> None:
    (tmp_path / "pragma.yaml").write_text("version: '2'\n", encoding="utf-8")

    result = _run(tmp_path, "--greenfield", "--name", "demo", "--language", "python")

    assert result.returncode != 0
    assert "already_initialised" in result.stdout


def test_greenfield_emits_ok_json(tmp_path: Path) -> None:
    result = _run(tmp_path, "--greenfield", "--name", "demo", "--language", "python")

    assert result.returncode == 0, result.stdout + result.stderr

    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["project_name"] == "demo"
    created = set(payload["created"])
    for expected in (
        "pragma.yaml",
        "pragma.lock.json",
        ".pragma/state.json",
        "claude.md",
        "PRAGMA.md",
        ".pre-commit-config.yaml",
        ".claude/settings.json",
        "src/",
        "tests/",
    ):
        assert expected in created, f"missing {expected} in created list: {sorted(created)}"
