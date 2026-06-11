"""Performance regression test for classify_file (Fix 2).

A 4000-line / 1000-test synthetic file must classify in low single-digit
seconds. The original implementation re-ran `ast.parse(source)` once per test
inside `infer_target`, making the whole pass O(n^2) in the number of tests
(57.5s for this file). Parsing once and threading the tree down brings it to
linear time.
"""

from __future__ import annotations

import time
from pathlib import Path

from pragma.languages.python import classify_file


def _synthetic_source(n_tests: int) -> str:
    """Build a file with `n_tests` honest tests, ~4 lines each."""
    header = "from app.calc import add\n\n\n"
    blocks = []
    for i in range(n_tests):
        blocks.append(
            f"def test_add_case_{i}():\n    result = add({i}, {i})\n    assert result == {i + i}\n"
        )
    return header + "\n\n".join(blocks) + "\n"


def test_large_file_classifies_in_low_single_digit_seconds(tmp_path: Path) -> None:
    src = _synthetic_source(1000)
    # Sanity: this is the advertised size (~4000 lines, 1000 tests).
    assert src.count("def test_") == 1000
    assert src.count("\n") >= 4000

    path = tmp_path / "test_big.py"
    path.write_text(src, encoding="utf-8")

    start = time.perf_counter()
    verdicts = classify_file(path)
    elapsed = time.perf_counter() - start

    assert len(verdicts) == 1000
    # All honest tests; none should be a blocking false positive.
    assert all(v.kind in {"python.verified", "python.weak"} for v in verdicts), {
        v.kind for v in verdicts
    }
    assert elapsed < 5.0, f"classify_file took {elapsed:.2f}s for 1000 tests (expected < 5s)"
