from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.hooks.session_start import handle

runner = CliRunner()


def test_session_start_no_state(tmp_path: Path) -> None:
    out = handle({"session_id": "x", "source": "startup"}, tmp_path)
    assert out.get("continue") is True
    assert "additionalContext" in out


def test_session_start_with_active_slice(
    monkeypatch, tmp_project_v2: Path,
) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    out = handle({"session_id": "x", "source": "startup"}, tmp_project_v2)
    ctx = out["additionalContext"]
    assert "M01.S1" in ctx
    assert "LOCKED" in ctx
    assert "REQ-001" in ctx


def test_session_start_integrity_warning(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"hooks":{}}', encoding="utf-8")
    pragma_dir = tmp_path / ".pragma"
    pragma_dir.mkdir()
    (pragma_dir / "claude-settings.hash").write_text(
        "sha256:" + "0" * 64 + "\n", encoding="utf-8",
    )
    out = handle({"session_id": "x", "source": "startup"}, tmp_path)
    assert "tamper" in out["additionalContext"].lower() or \
           "hash" in out["additionalContext"].lower()


def test_session_start_caps_additional_context_length(
    monkeypatch, tmp_path: Path,
) -> None:
    import yaml
    vision = "x" * 20000
    manifest = {
        "version": "2",
        "project": {"name": "demo", "mode": "brownfield", "language": "python",
                    "source_root": "src/", "tests_root": "tests/"},
        "vision": vision,
        "requirements": [],
    }
    (tmp_path / "pragma.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    out = handle({"session_id": "x", "source": "startup"}, tmp_path)
    assert len(out.get("additionalContext", "")) <= 9500
