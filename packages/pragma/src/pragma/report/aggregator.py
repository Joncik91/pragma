from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from pragma.core.manifest import slice_requirements
from pragma.core.models import Manifest
from pragma.core.state import State
from pragma.core.tests_discovery import expected_test_name
from pragma.report.models import (
    PermutationStatus,
    Report,
    ReportPermutation,
    ReportRequirement,
)

_MOCKED_REMEDIATION = (
    "No pragma.logic_id={logic_id} span observed during this test. "
    "Either add @trace('{logic_id}') to the production path the test exercises, "
    "or acknowledge mock-only via `pragma spec mark-mocked {logic_id} {perm_id}`."
)


def _parse_spans(path: Path | None) -> dict[str, list[dict]]:
    if path is None or not path.exists():
        return {}
    result: dict[str, list[dict]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        nodeid = obj.get("test_nodeid", "")
        test_name = nodeid.split("::")[-1] if "::" in nodeid else nodeid
        result.setdefault(test_name, []).append(obj)
    return result


def _parse_junit(path: Path | None) -> dict[str, str]:
    """Parse JUnit XML into {test_name: "passed"|"failed"|"skipped"}."""
    if path is None or not path.exists():
        return {}
    results: dict[str, str] = {}
    try:
        tree = ET.parse(path)  # noqa: S314 — local JUnit from our own pytest, not untrusted
    except ET.ParseError:
        return {}
    for tc in tree.iter("testcase"):
        name = tc.get("name", "")
        if tc.find("failure") is not None:
            results[name] = "failed"
        elif tc.find("skipped") is not None:
            results[name] = "skipped"
        else:
            results[name] = "passed"
    return results


def _compute_permutation_status(
    *,
    req_id: str,
    perm_id: str,
    junit_results: dict[str, str],
    spans_by_test: dict[str, list[dict]],
) -> tuple[PermutationStatus, int, str | None]:
    test_name = expected_test_name(req_id, perm_id)
    junit_status = junit_results.get(test_name)
    matching = [
        s
        for s in spans_by_test.get(test_name, [])
        if s.get("attrs", {}).get("pragma.logic_id") == req_id
    ]
    span_count = len(matching)

    if junit_status is None:
        return PermutationStatus.missing, 0, None

    if junit_status == "failed":
        return PermutationStatus.red, 0, None

    if junit_status == "skipped":
        return PermutationStatus.skipped, 0, None

    if span_count > 0:
        return PermutationStatus.ok, span_count, None

    if test_name.startswith("test_req_"):
        remediation = _MOCKED_REMEDIATION.format(logic_id=req_id, perm_id=perm_id)
        return PermutationStatus.mocked, 0, remediation

    return PermutationStatus.partial, 0, None


def build_report(
    *,
    manifest: Manifest,
    state: State | None,
    spans_jsonl: Path | None,
    junit_xml: Path | None,
    commit_timestamp: str,
    active_slice_override: str | None = None,
) -> Report:
    spans_by_test = _parse_spans(spans_jsonl)
    junit_results = _parse_junit(junit_xml)

    active_slice = active_slice_override
    if active_slice is None and state is not None:
        active_slice = state.active_slice

    if active_slice is not None:
        requirements = slice_requirements(manifest, active_slice)
    else:
        requirements = list(manifest.requirements)

    report_reqs: list[ReportRequirement] = []
    summary = {"ok": 0, "total": 0, "partial": 0, "mocked": 0, "missing": 0, "red": 0, "skipped": 0}

    for req in requirements:
        report_perms: list[ReportPermutation] = []
        for perm in req.permutations:
            status, span_count, remediation = _compute_permutation_status(
                req_id=req.id,
                perm_id=perm.id,
                junit_results=junit_results,
                spans_by_test=spans_by_test,
            )
            report_perms.append(
                ReportPermutation(
                    id=perm.id,
                    status=status,
                    test_nodeid=None,
                    span_count=span_count,
                    remediation=remediation,
                )
            )
            summary[status.value] += 1
            summary["total"] += 1
        report_reqs.append(
            ReportRequirement(
                id=req.id,
                title=req.title,
                permutations=tuple(report_perms),
            )
        )

    gate = None
    if state is not None:
        gate = state.gate

    return Report(
        slice=active_slice,
        gate=gate,
        generated_at=commit_timestamp,
        requirements=tuple(report_reqs),
        summary=summary,
    )
