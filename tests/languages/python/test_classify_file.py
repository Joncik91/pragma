"""End-to-end tests for the Python language module's classify_file."""

from __future__ import annotations

from pathlib import Path

import pragma.languages.python as python_lang


def test_matches_py_test_file(tmp_path: Path) -> None:
    f = tmp_path / "test_x.py"
    f.write_text("def test_x(): pass\n")
    assert python_lang.matches(f) is True


def test_does_not_match_non_py(tmp_path: Path) -> None:
    f = tmp_path / "test_x.ts"
    f.write_text("it('x', () => {})")
    assert python_lang.matches(f) is False


def test_does_not_match_non_test_py(tmp_path: Path) -> None:
    # Production code, not a test file.
    f = tmp_path / "models.py"
    f.write_text("def get_user(id): pass\n")
    assert python_lang.matches(f) is False


def test_classify_file_returns_verdicts_with_python_prefix(tmp_path: Path) -> None:
    f = tmp_path / "test_smoke.py"
    f.write_text("def test_smoke():\n    assert True\n")
    verdicts = python_lang.classify_file(f)
    assert len(verdicts) == 1
    assert verdicts[0].kind == "python.tautological"
    assert verdicts[0].test_name == "test_smoke"
