"""Red tests for REQ-013 - greenfield scaffold ships src import glue.

BUG-017: before v1.0.6 the greenfield scaffold wrote `src/` and
`tests/` but no `conftest.py`, so the first test file that imported
from `src/<module>.py` raised ModuleNotFoundError at collection time
and blocked `pragma unlock`. v1.0.6 ships a `tests/conftest.py` that
inserts `<project>/src` into `sys.path`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


@trace("REQ-013")
def _assert_greenfield_writes_conftest(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_project)
    result = runner.invoke(
        app, ["init", "--greenfield", "--name", "demo", "--language", "python", "--force"]
    )
    assert result.exit_code == 0, result.stdout
    conftest = tmp_project / "tests" / "conftest.py"
    assert conftest.exists(), f"greenfield scaffold must write {conftest}"
    text = conftest.read_text(encoding="utf-8")
    # Must wire src/ onto sys.path somehow. We don't care about the
    # exact style, just that a fresh test can import from src.
    assert "sys.path" in text and "src" in text, (
        f"conftest.py must wire src/ onto sys.path; got:\n{text}"
    )


@trace("REQ-013")
def _assert_greenfield_tests_can_import_src(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    assert (
        runner.invoke(
            app,
            ["init", "--greenfield", "--name", "demo", "--language", "python", "--force"],
        ).exit_code
        == 0
    )
    # Drop a minimal module + test that imports it.
    (tmp_project / "src" / "demo_module.py").write_text(
        "def hello() -> str:\n    return 'hi'\n", encoding="utf-8"
    )
    (tmp_project / "tests" / "test_demo.py").write_text(
        "from demo_module import hello\n\ndef test_hello():\n    assert hello() == 'hi'\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--no-header", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        cwd=str(tmp_project),
    )
    assert proc.returncode == 0, (
        f"pytest must collect and pass test_demo on a fresh greenfield tree; "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def test_req_013_greenfield_writes_conftest(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("greenfield_writes_conftest"):
        _assert_greenfield_writes_conftest(tmp_project, monkeypatch)


def test_req_013_greenfield_tests_can_import_src(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("greenfield_tests_can_import_src"):
        _assert_greenfield_tests_can_import_src(tmp_project, monkeypatch)
