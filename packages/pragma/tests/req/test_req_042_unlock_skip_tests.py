"""Red tests for REQ-042 — unlock --skip-tests for brownfield retroactive REQ.

BUG-046. Logged at v0.1.3 - brownfield retroactive-REQ flow had no
clean gate path. `pragma unlock` refuses when tests already pass
(TDD red-first rule); `pragma doctor --emergency-unlock` clears the
active slice, leaving `slice complete` unreachable. The workaround
required hand-editing .pragma/state.json.

Fix - `pragma unlock --skip-tests --reason "..."` bypasses the
red-test check, requires an explicit reason, and audit-logs the
bypass with the reason. The TDD rule still applies by default;
`--skip-tests` is the explicit, audited escape hatch.
"""

from __future__ import annotations

import json
from pathlib import Path

from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _bootstrap_brownfield(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--brownfield"])
    runner.invoke(
        app,
        [
            "spec",
            "add-requirement",
            "--id",
            "REQ-001",
            "--title",
            "x",
            "--description",
            "x",
            "--touches",
            "src/x.py",
            "--permutation",
            "valid|x|success",
        ],
    )
    runner.invoke(app, ["freeze"])
    runner.invoke(app, ["slice", "activate", "M00.S0"])
    # Brownfield reality: code already exists, test already passes.
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "x.py").write_text(
        "from pragma_sdk import trace\n\n\n@trace('REQ-001')\ndef f():\n    return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_req_001_valid.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))\n"
        "from pragma_sdk import set_permutation\n"
        "def test_req_001_valid():\n"
        "    with set_permutation('valid'):\n"
        "        from x import f\n"
        "        assert f() == 1\n",
        encoding="utf-8",
    )


@trace("REQ-042")
def _assert_unlock_skip_tests_requires_reason(tmp_path: Path, monkeypatch) -> None:
    _bootstrap_brownfield(tmp_path, monkeypatch)
    result = runner.invoke(app, ["unlock", "--skip-tests"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["error"] == "reason_required", (
        f"unlock --skip-tests must require --reason; got:\n{result.stdout}"
    )


@trace("REQ-042")
def _assert_unlock_skip_tests_unlocks_with_passing_tests(tmp_path: Path, monkeypatch) -> None:
    _bootstrap_brownfield(tmp_path, monkeypatch)
    # Without --skip-tests this would fail because test passes.
    result = runner.invoke(
        app,
        ["unlock", "--skip-tests", "--reason", "brownfield import"],
    )
    assert result.exit_code == 0, f"unlock --skip-tests must succeed; got:\n{result.stdout}"
    payload = json.loads(result.stdout)
    assert payload["gate"] == "UNLOCKED"
    assert payload["skip_tests"] is True


@trace("REQ-042")
def _assert_unlock_skip_tests_audited(tmp_path: Path, monkeypatch) -> None:
    _bootstrap_brownfield(tmp_path, monkeypatch)
    runner.invoke(
        app,
        ["unlock", "--skip-tests", "--reason", "brownfield import — REQ-001 pre-exists"],
    )
    audit_path = tmp_path / ".pragma" / "audit.jsonl"
    assert audit_path.exists()
    text = audit_path.read_text(encoding="utf-8")
    assert "unlock --skip-tests" in text, f"audit must record --skip-tests bypass; got:\n{text}"
    assert "brownfield import" in text, (
        f"audit must record the user-supplied reason verbatim; got:\n{text}"
    )


def test_req_042_unlock_skip_tests_requires_reason(tmp_path: Path, monkeypatch) -> None:
    with set_permutation("unlock_skip_tests_requires_reason"):
        _assert_unlock_skip_tests_requires_reason(tmp_path, monkeypatch)


def test_req_042_unlock_skip_tests_unlocks_with_passing_tests(tmp_path: Path, monkeypatch) -> None:
    with set_permutation("unlock_skip_tests_unlocks_with_passing_tests"):
        _assert_unlock_skip_tests_unlocks_with_passing_tests(tmp_path, monkeypatch)


def test_req_042_unlock_skip_tests_audited(tmp_path: Path, monkeypatch) -> None:
    with set_permutation("unlock_skip_tests_audited"):
        _assert_unlock_skip_tests_audited(tmp_path, monkeypatch)
