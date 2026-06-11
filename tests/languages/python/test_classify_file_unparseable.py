"""Regression tests for Fix 3: classify_file must not crash on a file it
cannot parse. A SyntaxError or a non-UTF-8 decode must yield one explicit,
non-blocking `python.unparseable` skip verdict instead of a traceback (which
would fail open and let gamed-but-broken files slip through silently).
"""

from __future__ import annotations

from pathlib import Path

from pragma.blocking import is_blocking_kind
from pragma.languages.python import classify_file


def test_syntactically_broken_file_yields_skip_verdict(tmp_path: Path) -> None:
    path = tmp_path / "test_broken.py"
    path.write_text("def test_x(:\n    assert ???\n", encoding="utf-8")

    verdicts = classify_file(path)

    assert len(verdicts) == 1
    assert verdicts[0].kind == "python.unparseable"
    assert verdicts[0].evidence
    # An explicit skip must not block — a broken file isn't gamed, it's noise.
    assert not is_blocking_kind(verdicts[0].kind)


def test_non_utf8_file_yields_skip_verdict(tmp_path: Path) -> None:
    path = tmp_path / "test_latin1.py"
    # 0xff is invalid as a UTF-8 start byte → UnicodeDecodeError on read.
    path.write_bytes(b"def test_x():\n    assert caf\xe9 == 1\n")

    verdicts = classify_file(path)

    assert len(verdicts) == 1
    assert verdicts[0].kind == "python.unparseable"
    assert not is_blocking_kind(verdicts[0].kind)


def test_valid_file_is_unaffected(tmp_path: Path) -> None:
    path = tmp_path / "test_ok.py"
    path.write_text(
        "from app.calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    verdicts = classify_file(path)

    assert [v.kind for v in verdicts] == ["python.verified"]
