from __future__ import annotations

from pragma.narrative.pr import build_pr_description
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
                ],
            ),
        ],
        summary={
            "ok": 1,
            "total": 1,
            "partial": 0,
            "mocked": 0,
            "missing": 0,
            "red": 0,
            "skipped": 0,
        },
    )


def test_pr_contains_required_sections() -> None:
    md = build_pr_description(report=_sample_report())
    assert "## Summary" in md
    assert "## REQs shipped" in md
    assert "## PIL verdict" in md
    assert "## What to review first" in md


def test_pr_lists_req_ids() -> None:
    md = build_pr_description(report=_sample_report())
    assert "REQ-001" in md
    assert "User login" in md


def test_pr_shows_verdict() -> None:
    md = build_pr_description(report=_sample_report())
    assert "ok" in md
