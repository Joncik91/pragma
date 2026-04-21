from __future__ import annotations

from pragma.report.formatter_md import render_markdown
from pragma.report.models import (
    PermutationStatus,
    Report,
    ReportPermutation,
    ReportRequirement,
)


def _sample_report() -> Report:
    return Report(
        slice="M01.S1",
        gate="UNLOCKED",
        generated_at="2026-04-21T00:00:00Z",
        requirements=[
            ReportRequirement(
                id="REQ-001",
                title="User login",
                permutations=[
                    ReportPermutation(
                        id="valid",
                        status=PermutationStatus.ok,
                        test_nodeid="tests/test_auth.py::test_req_001_valid",
                        span_count=2,
                    ),
                    ReportPermutation(
                        id="weak_password",
                        status=PermutationStatus.mocked,
                        test_nodeid="tests/test_auth.py::test_req_001_weak_password",
                        span_count=0,
                        remediation="Add @trace('REQ-001') to the auth path.",
                    ),
                ],
            ),
        ],
        summary={
            "ok": 1,
            "total": 2,
            "partial": 0,
            "mocked": 1,
            "missing": 0,
            "red": 0,
            "skipped": 0,
        },
    )


def test_render_contains_header() -> None:
    md = render_markdown(_sample_report())
    assert "# Pragma Verification Report" in md
    assert "M01.S1" in md


def test_render_contains_summary() -> None:
    md = render_markdown(_sample_report())
    assert "Summary" in md
    assert "2 permutations" in md


def test_render_contains_req_table() -> None:
    md = render_markdown(_sample_report())
    assert "REQ-001" in md
    assert "User login" in md


def test_render_contains_flagged_section() -> None:
    md = render_markdown(_sample_report())
    assert "mocked" in md
    assert "Add @trace" in md
