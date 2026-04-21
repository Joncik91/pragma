from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _init_repo(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@test.test")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            "chore: seed\n\nWHY: seed\n\nWHAT: seed\n\nWHERE: README.md.\n\n"
            "Co-Authored-By: Test <t@t.t>",
        ],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    _git(tmp_path, "checkout", "-b", "feature")


def test_verify_commits_all_conformant(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["verify", "commits"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["ok"] is True


def test_verify_commits_flags_bad_shape(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "x").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "x")
    subprocess.run(
        ["git", "commit", "-m", "just a subject"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["verify", "commits"])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload["error"] == "commit_shape_violation"
    assert any("missing_body" in v["rules"] for v in payload["context"]["commits"])


def test_verify_commits_respects_base(monkeypatch, tmp_path: Path) -> None:
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["verify", "commits", "--base", "HEAD"])
    assert r.exit_code == 0


def test_verify_message_accepts_canonical_shape(tmp_path: Path) -> None:
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(
        "feat(x): add widget\n"
        "\n"
        "WHY: the widget was missing.\n"
        "WHAT: added it.\n"
        "WHERE: src/x.py\n"
        "\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["verify", "message", str(msg)])
    assert r.exit_code == 0, r.output


def test_verify_message_rejects_long_subject(tmp_path: Path) -> None:
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(
        ("feat(scope): " + ("x" * 80)) + "\n\nWHY: a\n\nCo-Authored-By: Claude <n@a.com>\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["verify", "message", str(msg)])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload["error"] == "commit_shape_violation"
    assert "subject_too_long" in payload["context"]["rules"]


def test_verify_message_strips_git_comment_lines(tmp_path: Path) -> None:
    """Git appends '# Please enter the commit message...' lines; we must ignore them."""
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text(
        "feat(x): add widget\n"
        "\n"
        "WHY: the widget was missing.\n"
        "\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        "# Please enter the commit message for your changes. Lines starting\n"
        "# with '#' will be ignored, and an empty message aborts the commit.\n",
        encoding="utf-8",
    )
    r = runner.invoke(app, ["verify", "message", str(msg)])
    assert r.exit_code == 0, r.output


def test_verify_message_errors_when_file_missing(tmp_path: Path) -> None:
    r = runner.invoke(app, ["verify", "message", str(tmp_path / "nope")])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload["error"] == "commit_msg_not_found"
