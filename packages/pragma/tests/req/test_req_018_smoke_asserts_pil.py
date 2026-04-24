"""Red tests for REQ-018 - pre-release-smoke asserts end-to-end PIL.

BUG-020 ship-reason. `scripts/pre-release-smoke.sh` runs `pragma
verify all` and checks that span files exist, but never runs
`pragma report` and never asserts that `.pragma/pytest-junit.xml`
was produced by Pragma's own flows. That blind spot is what let
BUG-020 ship. v1.1.0 closes it: the script must exit non-zero when
junit is missing after slice complete, and when `pragma report
--json` shows any `missing` permutations.

These tests inspect the smoke script's *text* for the right
assertions — running the script itself in a pytest would be slow
and brittle, and the script's correctness is about what it checks,
not how fast it runs.
"""

from __future__ import annotations

from pathlib import Path

from pragma_sdk import set_permutation, trace

_SMOKE_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "pre-release-smoke.sh"


@trace("REQ-018")
def _assert_smoke_asserts_junit_exists() -> None:
    assert _SMOKE_SCRIPT.exists(), f"smoke script not found at {_SMOKE_SCRIPT}"
    text = _SMOKE_SCRIPT.read_text(encoding="utf-8")
    # Script must run slice activate + complete inside the greenfield
    # smoke, and must assert junit.xml exists as a result.
    assert "slice activate" in text, "smoke script must exercise slice activate"
    assert "slice complete" in text, "smoke script must exercise slice complete"
    # Script must assert junit.xml was produced.
    assert "pytest-junit.xml" in text and ("-s" in text or "test -s" in text or "[ -s " in text), (
        "smoke script must assert .pragma/pytest-junit.xml exists and is "
        "non-empty after slice complete (use `[ -s ... ]` or equivalent)"
    )


@trace("REQ-018")
def _assert_smoke_asserts_pil_verified() -> None:
    text = _SMOKE_SCRIPT.read_text(encoding="utf-8")
    # Script must run pragma report and assert the summary is healthy.
    assert "pragma report" in text or "report --json" in text, (
        "smoke script must run `pragma report` to exercise the PIL"
    )
    # Script must assert summary.ok > 0 and summary.missing == 0, or
    # an equivalent text check on --human output. Accept either shape.
    has_json_check = ('"ok"' in text or "summary.ok" in text or "summary']['ok" in text) and (
        '"missing"' in text or "summary.missing" in text or "summary']['missing" in text
    )
    has_human_check = "verified" in text and "missing" in text
    assert has_json_check or has_human_check, (
        "smoke script must assert pragma report shows verified > 0 and "
        "missing == 0, either via --json parsing or --human text match"
    )


def test_req_018_smoke_asserts_junit_exists() -> None:
    with set_permutation("smoke_asserts_junit_exists"):
        _assert_smoke_asserts_junit_exists()


def test_req_018_smoke_asserts_pil_verified() -> None:
    with set_permutation("smoke_asserts_pil_verified"):
        _assert_smoke_asserts_pil_verified()
