from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from pragma.core.manifest import slice_requirements
from pragma.core.models import Manifest, Requirement
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
    "or wrap the test body in `with set_permutation('{perm_id}'):` so the SDK "
    "labels the trace correctly."
)


def _parse_spans(path: Path | None) -> dict[str, list[dict[str, object]]]:
    """Parse span JSONL into {test_name: [span_dict, ...]}.

    Accepts either a single .jsonl file (back-compat with pre-KI-1
    fixed-filename spans) or a directory holding many per-session
    *.jsonl files. The pytest plugin as of v1.0.2 writes one file
    per pytest session so PIL stays correct across multi-suite
    projects; this parser merges them transparently.
    """
    if path is None or not path.exists():
        return {}
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    result: dict[str, list[dict[str, object]]] = {}
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            nodeid = str(obj.get("test_nodeid", ""))
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


def _span_matches(
    span: dict[str, object],
    *,
    req_id: str,
    perm_id: str,
    total_permutations: int,
) -> bool:
    """True when `span` is evidence of `(req_id, perm_id)` executing.

    BUG-007: both pragma.logic_id and pragma.permutation must match
    for a span to count (matching on logic_id alone scored unrelated
    spans as exercising every permutation).

    BUG-023 / REQ-023: on single-permutation requirements the test
    name alone disambiguates, so a span with pragma.permutation="none"
    (SDK default when set_permutation wasn't called) is accepted.
    """
    attrs = span.get("attrs")
    if not isinstance(attrs, dict) or attrs.get("pragma.logic_id") != req_id:
        return False
    span_perm = attrs.get("pragma.permutation")
    if span_perm == perm_id:
        return True
    return span_perm == "none" and total_permutations == 1


def _compute_permutation_status(
    *,
    req_id: str,
    perm_id: str,
    junit_results: dict[str, str],
    spans_by_test: dict[str, list[dict[str, object]]],
    total_permutations: int = 1,
) -> tuple[PermutationStatus, int, str | None]:
    test_name = expected_test_name(req_id, perm_id)
    junit_status = junit_results.get(test_name)
    matching = [
        s
        for s in spans_by_test.get(test_name, [])
        if _span_matches(s, req_id=req_id, perm_id=perm_id, total_permutations=total_permutations)
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


def _resolve_active_slice(state: State | None, override: str | None) -> str | None:
    if override is not None:
        return override
    return state.active_slice if state is not None else None


def _build_report_requirement(
    req: Requirement,
    junit_results: dict[str, str],
    spans_by_test: dict[str, list[dict[str, object]]],
    summary: dict[str, int],
) -> ReportRequirement:
    report_perms: list[ReportPermutation] = []
    total_permutations = len(req.permutations)
    for perm in req.permutations:
        status, span_count, remediation = _compute_permutation_status(
            req_id=req.id,
            perm_id=perm.id,
            junit_results=junit_results,
            spans_by_test=spans_by_test,
            total_permutations=total_permutations,
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
    return ReportRequirement(
        id=req.id,
        title=req.title,
        permutations=tuple(report_perms),
    )


def _compute_diagnostics(
    *,
    spans_jsonl: Path | None,
    junit_xml: Path | None,
    spans_by_test: dict[str, list[dict[str, object]]],
    junit_results: dict[str, str],
    summary: dict[str, int],
) -> tuple[str, ...]:
    """Return short banner strings naming absent artifacts.

    BUG-020 / REQ-017. When a user runs `pragma report` without the
    artifacts the aggregator needs, they see a wall of "missing"
    rows and no remediation. These banners tell them *why* and
    what to type.

    Only fires when either artifact is absent AND at least one
    permutation came back `missing` or `mocked` (i.e. the absence
    plausibly explains the rows). On the happy path — both artifacts
    present, all verified — returns empty.
    """
    banners: list[str] = []
    silent_rows = summary.get("missing", 0) + summary.get("mocked", 0)
    if silent_rows == 0:
        return ()

    junit_absent = junit_xml is None or not junit_xml.exists()
    if junit_absent:
        banners.append(
            ".pragma/pytest-junit.xml not found — every permutation reads "
            "`missing` without it. `pragma slice complete` produces this "
            "automatically in v1.1+; if you're on an older version, run "
            "`pytest` once before `pragma report`."
        )

    spans_absent = (
        spans_jsonl is None
        or not spans_jsonl.exists()
        or not spans_by_test  # directory exists but is empty / unparseable
    )
    if spans_absent:
        banners.append(
            ".pragma/spans/ is empty or missing — no runtime evidence "
            "of the real code executing. Make sure your production "
            "functions are decorated with `@trace('REQ-NNN')` and your "
            "tests wrap the call in `set_permutation('perm_id')`."
        )

    # Defensive: the caller may pass paths that do exist but produced
    # zero useful data (e.g. junit parsed but no matching test names).
    # We don't add a banner for that case — the "mocked" remediation
    # per row already points at the problem.
    return tuple(banners)


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
    active_slice = _resolve_active_slice(state, active_slice_override)

    requirements = (
        slice_requirements(manifest, active_slice)
        if active_slice is not None
        else list(manifest.requirements)
    )

    summary = {"ok": 0, "total": 0, "partial": 0, "mocked": 0, "missing": 0, "red": 0, "skipped": 0}
    report_reqs = [
        _build_report_requirement(req, junit_results, spans_by_test, summary)
        for req in requirements
    ]

    diagnostics = _compute_diagnostics(
        spans_jsonl=spans_jsonl,
        junit_xml=junit_xml,
        spans_by_test=spans_by_test,
        junit_results=junit_results,
        summary=summary,
    )

    return Report(
        slice=active_slice,
        gate=state.gate if state is not None else None,
        generated_at=commit_timestamp,
        requirements=tuple(report_reqs),
        summary=summary,
        diagnostics=diagnostics,
    )
