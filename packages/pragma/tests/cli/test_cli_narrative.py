from __future__ import annotations

import yaml
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def test_narrative_commit_outputs_message(tmp_path) -> None:
    manifest = {
        "version": "2",
        "project": {
            "name": "demo",
            "mode": "brownfield",
            "language": "python",
            "source_root": "src/",
            "tests_root": "tests/",
        },
        "milestones": [
            {
                "id": "M01",
                "title": "Core",
                "description": "Core.",
                "depends_on": [],
                "slices": [
                    {
                        "id": "M01.S1",
                        "title": "S1",
                        "description": "S1.",
                        "requirements": ["REQ-001"],
                    }
                ],
            }
        ],
        "requirements": [
            {
                "id": "REQ-001",
                "title": "Do thing",
                "description": "Does a thing.",
                "touches": ["src/a.py"],
                "permutations": [{"id": "happy", "description": "happy", "expected": "success"}],
                "milestone": "M01",
                "slice": "M01.S1",
            }
        ],
    }
    (tmp_path / "pragma.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    (tmp_path / ".pragma").mkdir()

    result = runner.invoke(
        app,
        [
            "narrative",
            "commit",
            "--subject",
            "feat(a): add a",
            "--cwd",
            str(tmp_path),
            "--allow-empty",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "WHY:" in result.output
    assert "Co-Authored-By:" in result.output


def test_narrative_commit_errors_when_nothing_staged(tmp_path) -> None:
    (tmp_path / "pragma.yaml").write_text(
        (
            "version: '2'\n"
            "project:\n"
            "  name: x\n"
            "  mode: brownfield\n"
            "  language: python\n"
            "  source_root: src/\n"
            "  tests_root: tests/\n"
            "requirements: []\n"
            "milestones: []\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / ".pragma").mkdir()

    result = runner.invoke(
        app,
        [
            "narrative",
            "commit",
            "--subject",
            "feat: x",
            "--cwd",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    import json

    payload = json.loads(result.output)
    assert payload["error"] == "narrative_empty_stage"


def test_narrative_pr_requires_slice_or_active_slice(tmp_path) -> None:
    (tmp_path / "pragma.yaml").write_text(
        (
            "version: '2'\n"
            "project:\n"
            "  name: x\n"
            "  mode: brownfield\n"
            "  language: python\n"
            "  source_root: src/\n"
            "  tests_root: tests/\n"
            "requirements: []\n"
            "milestones: []\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / ".pragma").mkdir()

    result = runner.invoke(app, ["narrative", "pr", "--cwd", str(tmp_path)])
    assert result.exit_code == 1
    import json

    payload = json.loads(result.output)
    assert payload["error"] == "narrative_no_active_slice"


def test_narrative_remediation_outputs_string() -> None:
    result = runner.invoke(
        app, ["narrative", "remediation", "complexity", "--budget", "10", "--got", "15"]
    )
    assert result.exit_code == 0
    assert "10" in result.output
    assert "15" in result.output
