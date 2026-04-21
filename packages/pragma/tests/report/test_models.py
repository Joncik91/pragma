from __future__ import annotations

from pragma.report.models import PermutationStatus, Report, ReportPermutation, ReportRequirement


def test_status_serialises_as_string() -> None:
    p = ReportPermutation(id="x", status=PermutationStatus.ok, test_nodeid=None, span_count=0)
    assert p.model_dump()["status"] == "ok"


def test_report_round_trips() -> None:
    r = Report(
        slice="M01.S1",
        gate="UNLOCKED",
        generated_at="2026-04-21T00:00:00Z",
        requirements=[
            ReportRequirement(
                id="REQ-001",
                title="x",
                permutations=[
                    ReportPermutation(
                        id="a", status=PermutationStatus.ok, test_nodeid="t", span_count=1
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
    dumped = r.model_dump_json()
    loaded = Report.model_validate_json(dumped)
    assert loaded == r
