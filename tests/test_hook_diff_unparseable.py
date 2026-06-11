"""Regression tests for Fix 3 (hook layer): check_diff.py must log an explicit
skip when the candidate file is unparseable, rather than silently exiting 0 as
if the file were clean.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]


def _import_check_diff():
    spec = importlib.util.spec_from_file_location(
        "check_diff_unparseable",
        REPO_ROOT / "plugin" / "hooks" / "check_diff.py",
    )
    mod = importlib.util.module_from_spec(spec)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = '["tautological", "no_success_assertion"]'
    with patch("subprocess.run", return_value=mock_result):
        spec.loader.exec_module(mod)
    return mod


def test_unparseable_verdict_is_logged_and_not_blocking(tmp_path, capsys) -> None:
    mod = _import_check_diff()
    f = tmp_path / "test_broken.py"
    f.write_text("def test_x(:\n", encoding="utf-8")

    payload = {
        "results": {
            str(f): [
                {
                    "kind": "python.unparseable",
                    "evidence": "could not parse test_broken.py: SyntaxError: ...",
                    "test_name": "test_broken.py",
                }
            ]
        }
    }

    with patch.object(mod, "_run_pragma", return_value=payload):
        rc = mod.main(["check_diff", str(f), str(f)])

    # Unparseable is not gamed → must not block.
    assert rc == 0
    err = capsys.readouterr().err
    # ...but it must be logged, not silently passed.
    assert "skip" in err.lower() or "unparseable" in err.lower()
    assert "test_broken.py" in err


def test_clean_file_logs_nothing(tmp_path, capsys) -> None:
    mod = _import_check_diff()
    f = tmp_path / "test_ok.py"
    f.write_text("def test_x():\n    assert add(1, 2) == 3\n", encoding="utf-8")

    payload = {"results": {str(f): [{"kind": "python.verified", "test_name": "test_x"}]}}

    with patch.object(mod, "_run_pragma", return_value=payload):
        rc = mod.main(["check_diff", str(f), str(f)])

    assert rc == 0
    err = capsys.readouterr().err
    assert "unparseable" not in err.lower()
    assert "skip" not in err.lower()
