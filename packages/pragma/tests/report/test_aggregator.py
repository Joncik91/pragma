from __future__ import annotations

from pathlib import Path

from pragma.core.manifest import load_manifest
from pragma.report.aggregator import build_report
from pragma.report.models import PermutationStatus


def test_ok_when_span_matches_passing_test(tmp_project_with_spans: Path) -> None:
    manifest = load_manifest(tmp_project_with_spans / "pragma.yaml")
    report = build_report(
        manifest=manifest,
        state=None,
        spans_jsonl=tmp_project_with_spans / ".pragma" / "spans" / "test-run.jsonl",
        junit_xml=tmp_project_with_spans / ".pragma" / "pytest-junit.xml",
        commit_timestamp="2026-04-21T00:00:00Z",
    )
    assert report.requirements[0].permutations[0].status == PermutationStatus.ok
    assert report.requirements[0].permutations[0].span_count == 1


def test_missing_when_no_test_for_permutation(tmp_project_v2: Path) -> None:
    manifest = load_manifest(tmp_project_v2 / "pragma.yaml")
    report = build_report(
        manifest=manifest,
        state=None,
        spans_jsonl=None,
        junit_xml=None,
        commit_timestamp="2026-04-21T00:00:00Z",
    )
    assert report.requirements[0].permutations[0].status == PermutationStatus.missing
    assert report.requirements[0].permutations[1].status == PermutationStatus.missing


def test_mocked_when_span_logic_id_matches_but_permutation_mismatches(
    tmp_project_with_spans: Path,
) -> None:
    """BUG-007: span with right logic_id but wrong/none permutation is mocked, not ok.

    Before v1.0.2 the aggregator matched spans purely on
    pragma.logic_id; any @trace-decorated helper that fired inside a
    test would score the enclosing permutation as ok regardless of
    whether set_permutation had ever been called. That let a user
    ship a green PIL without ever writing the per-permutation tests
    the manifest promised.
    """
    manifest = load_manifest(tmp_project_with_spans / "pragma.yaml")

    # Replace the seeded span: correct logic_id, permutation="none".
    # The test_req_001_happy JUnit row still says "passed" - which is
    # exactly the "implementation exists but no permutation-aware test
    # body" shape we want to flag.
    (tmp_project_with_spans / ".pragma" / "spans" / "test-run.jsonl").write_text(
        '{"test_nodeid":"tests/test_req.py::test_req_001_happy",'
        '"span_name":"REQ-001:do_thing",'
        '"attrs":{"pragma.logic_id":"REQ-001","pragma.permutation":"none"},'
        '"status":"ok"}\n',
        encoding="utf-8",
    )

    report = build_report(
        manifest=manifest,
        state=None,
        spans_jsonl=tmp_project_with_spans / ".pragma" / "spans",
        junit_xml=tmp_project_with_spans / ".pragma" / "pytest-junit.xml",
        commit_timestamp="2026-04-21T00:00:00Z",
    )
    perm = report.requirements[0].permutations[0]
    assert perm.status == PermutationStatus.mocked, (
        "Span missed the declared permutation - PIL must not score this as ok."
    )
    assert perm.span_count == 0


def test_mocked_when_test_passes_without_matching_span(tmp_project_with_spans: Path) -> None:
    """The 'sad' permutation has no span in JSONL but the test passes in JUnit -> mocked."""
    manifest = load_manifest(tmp_project_with_spans / "pragma.yaml")
    (tmp_project_with_spans / ".pragma" / "pytest-junit.xml").write_text(
        '<?xml version="1.0"?><testsuites><testsuite>'
        '<testcase classname="tests.test_req" name="test_req_001_happy"/>'
        '<testcase classname="tests.test_req" name="test_req_001_sad"/>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    report = build_report(
        manifest=manifest,
        state=None,
        spans_jsonl=tmp_project_with_spans / ".pragma" / "spans" / "test-run.jsonl",
        junit_xml=tmp_project_with_spans / ".pragma" / "pytest-junit.xml",
        commit_timestamp="2026-04-21T00:00:00Z",
    )
    assert report.requirements[0].permutations[1].status == PermutationStatus.mocked
    assert report.requirements[0].permutations[1].span_count == 0
    assert report.requirements[0].permutations[1].remediation is not None


def test_red_when_test_failed(tmp_project_v2: Path) -> None:
    manifest = load_manifest(tmp_project_v2 / "pragma.yaml")
    (tmp_project_v2 / ".pragma").mkdir(exist_ok=True)
    (tmp_project_v2 / ".pragma" / "pytest-junit.xml").write_text(
        '<?xml version="1.0"?><testsuites><testsuite>'
        '<testcase classname="tests.test_req" name="test_req_001_happy">'
        '<failure message="assert False"/>'
        "</testcase>"
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    report = build_report(
        manifest=manifest,
        state=None,
        spans_jsonl=None,
        junit_xml=tmp_project_v2 / ".pragma" / "pytest-junit.xml",
        commit_timestamp="2026-04-21T00:00:00Z",
    )
    assert report.requirements[0].permutations[0].status == PermutationStatus.red


def test_generated_at_uses_commit_timestamp(tmp_project_v2: Path) -> None:
    manifest = load_manifest(tmp_project_v2 / "pragma.yaml")
    report = build_report(
        manifest=manifest,
        state=None,
        spans_jsonl=None,
        junit_xml=None,
        commit_timestamp="2026-04-21T12:34:56Z",
    )
    assert report.generated_at == "2026-04-21T12:34:56Z"
