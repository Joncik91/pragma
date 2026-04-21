from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def test_report_json_deterministic(monkeypatch, tmp_project_with_spans: Path) -> None:
    monkeypatch.chdir(tmp_project_with_spans)
    r1 = runner.invoke(app, ["report", "--json"])
    r2 = runner.invoke(app, ["report", "--json"])
    assert r1.exit_code == 0, r1.output
    assert r1.output == r2.output
    payload = json.loads(r1.output)
    assert payload["ok"] is True
    assert "requirements" in payload


def test_report_json_and_human_mutually_exclusive(monkeypatch, tmp_project: Path) -> None:
    monkeypatch.chdir(tmp_project)
    (tmp_project / "pragma.yaml").write_text(
        'version: "2"\n'
        "project:\n"
        "  name: demo\n"
        "  mode: brownfield\n"
        "  language: python\n"
        "  source_root: src/\n"
        "  tests_root: tests/\n"
        "milestones: []\n"
        "requirements: []\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["report", "--json", "--human"])
    assert result.exit_code != 0


def test_report_json_default_flag(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True


def test_report_human_output_is_markdown(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    result = runner.invoke(app, ["report", "--human"])
    assert result.exit_code == 0, result.output
    assert "# " in result.output or "## " in result.output or result.output.strip() == ""


def test_report_no_manifest_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["report"])
    assert result.exit_code != 0
