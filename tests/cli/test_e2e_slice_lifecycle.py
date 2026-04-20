"""End-to-end: activate -> write failing tests -> unlock -> make green -> complete."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def test_full_slice_lifecycle(monkeypatch, tmp_project_v2: Path) -> None:
    monkeypatch.chdir(tmp_project_v2)
    assert runner.invoke(app, ["freeze"]).exit_code == 0

    # 1) Activate
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0

    # 2) verify all fails because tests are missing.
    r = runner.invoke(app, ["verify", "all"])
    assert r.exit_code == 1
    assert json.loads(r.output)["error"] == "unlock_missing_tests"

    # 3) Write failing tests.
    tests_dir = tmp_project_v2 / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "test_req_001.py").write_text(
        textwrap.dedent("""
            def test_req_001_happy(): assert False
            def test_req_001_sad(): assert False
        """),
        encoding="utf-8",
    )

    # 4) verify all now passes (tests exist and are red).
    assert runner.invoke(app, ["verify", "all"]).exit_code == 0

    # 5) Unlock.
    assert runner.invoke(app, ["unlock"]).exit_code == 0

    # 6) complete still blocked because tests are still red.
    r = runner.invoke(app, ["slice", "complete"])
    assert r.exit_code == 1
    assert json.loads(r.output)["error"] == "complete_tests_failing"

    # 7) Make tests green.
    (tests_dir / "test_req_001.py").write_text(
        textwrap.dedent("""
            def test_req_001_happy(): assert True
            def test_req_001_sad(): assert True
        """),
        encoding="utf-8",
    )

    # 8) complete ships.
    r = runner.invoke(app, ["slice", "complete"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["status"] == "shipped"

    # 9) status reflects shipped.
    status = json.loads(runner.invoke(app, ["slice", "status"]).output)
    assert status["active_slice"] is None
    assert status["slices"]["M01.S1"]["status"] == "shipped"
