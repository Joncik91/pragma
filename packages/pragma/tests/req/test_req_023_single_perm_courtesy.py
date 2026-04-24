"""Red tests for REQ-023 — single-permutation courtesy.

BUG-023. The aggregator comment advertised a courtesy: a requirement
with exactly one permutation whose test omits set_permutation should
still score `ok` (no ambiguity — there's only one permutation to
bind the span to). Implementation never matched the claim: the
matcher required `span_perm == perm_id` literally and the SDK emits
the string `"none"` when set_permutation wasn't called, so these
permutations scored `mocked`.

Fix: when the requirement has exactly one permutation, accept a
span with `pragma.permutation == "none"` as a match.
"""

from __future__ import annotations

from pragma_sdk import set_permutation, trace

from pragma.core.models import Manifest, Milestone, Permutation, Project, Requirement, Slice
from pragma.report.aggregator import build_report
from pragma.report.models import PermutationStatus


def _manifest(*permutations: tuple[str, str, str]) -> Manifest:
    """Build a minimal 1-REQ manifest with the given permutations."""
    perms = tuple(Permutation(id=pid, description=d, expected=e) for pid, d, e in permutations)
    return Manifest(
        version="2",
        project=Project(
            name="demo",
            mode="greenfield",
            language="python",
            source_root="src/",
            tests_root="tests/",
        ),
        milestones=(
            Milestone(
                id="M01",
                title="m",
                description="m",
                depends_on=(),
                slices=(Slice(id="M01.S1", title="s", description="s", requirements=("REQ-001",)),),
            ),
        ),
        requirements=(
            Requirement(
                id="REQ-001",
                title="r",
                description="r",
                touches=("src/x.py",),
                permutations=perms,
                milestone="M01",
                slice="M01.S1",
            ),
        ),
    )


def _junit_passing(test_name: str) -> str:
    return (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        f"<testsuites>\n"
        f"  <testsuite name='pytest' tests='1' failures='0' errors='0' skipped='0'>\n"
        f"    <testcase classname='tests.test_req_001' name='{test_name}'/>\n"
        f"  </testsuite>\n"
        f"</testsuites>\n"
    )


def _write_artifacts(tmp_path, *, test_name: str, span_perm: str) -> tuple:
    junit = tmp_path / "junit.xml"
    junit.write_text(_junit_passing(test_name), encoding="utf-8")
    spans = tmp_path / "spans"
    spans.mkdir()
    (spans / "run.jsonl").write_text(
        '{"attrs":{"pragma.logic_id":"REQ-001","pragma.permutation":"'
        + span_perm
        + '"},"span_name":"REQ-001:f","status":"ok","test_nodeid":"tests/test_req_001.py::'
        + test_name
        + '"}\n',
        encoding="utf-8",
    )
    return junit, spans


@trace("REQ-023")
def _assert_single_perm_without_set_permutation_is_ok(tmp_path) -> None:
    manifest = _manifest(("valid", "only permutation", "success"))
    junit, spans = _write_artifacts(tmp_path, test_name="test_req_001_valid", span_perm="none")
    report = build_report(
        manifest=manifest,
        state=None,
        spans_jsonl=spans,
        junit_xml=junit,
        commit_timestamp="0",
    )
    perm = report.requirements[0].permutations[0]
    assert perm.status == PermutationStatus.ok, (
        f"single-permutation REQ whose test omits set_permutation must score "
        f"ok; got status={perm.status!r} span_count={perm.span_count}"
    )


@trace("REQ-023")
def _assert_multi_perm_still_requires_exact_match(tmp_path) -> None:
    manifest = _manifest(
        ("a", "first", "success"),
        ("b", "second", "success"),
    )
    # Span for test_req_001_a has permutation="none" — with 2 permutations
    # the matcher CANNOT accept this as a match for either.
    junit = tmp_path / "junit.xml"
    junit.write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n"
        "<testsuites><testsuite>\n"
        "  <testcase classname='tests' name='test_req_001_a'/>\n"
        "  <testcase classname='tests' name='test_req_001_b'/>\n"
        "</testsuite></testsuites>\n",
        encoding="utf-8",
    )
    spans = tmp_path / "spans"
    spans.mkdir()
    (spans / "run.jsonl").write_text(
        '{"attrs":{"pragma.logic_id":"REQ-001","pragma.permutation":"none"},"span_name":"REQ-001:f","status":"ok","test_nodeid":"tests/t.py::test_req_001_a"}\n'
        '{"attrs":{"pragma.logic_id":"REQ-001","pragma.permutation":"none"},"span_name":"REQ-001:f","status":"ok","test_nodeid":"tests/t.py::test_req_001_b"}\n',
        encoding="utf-8",
    )
    report = build_report(
        manifest=manifest,
        state=None,
        spans_jsonl=spans,
        junit_xml=junit,
        commit_timestamp="0",
    )
    # Both permutations must NOT be ok (the courtesy is scoped to single-perm).
    for perm in report.requirements[0].permutations:
        assert perm.status == PermutationStatus.mocked, (
            f"multi-perm REQ must still require exact permutation match; got "
            f"{perm.id}={perm.status!r}"
        )


@trace("REQ-023")
def _assert_single_perm_with_explicit_set_permutation_still_ok(tmp_path) -> None:
    manifest = _manifest(("valid", "only permutation", "success"))
    junit, spans = _write_artifacts(tmp_path, test_name="test_req_001_valid", span_perm="valid")
    report = build_report(
        manifest=manifest,
        state=None,
        spans_jsonl=spans,
        junit_xml=junit,
        commit_timestamp="0",
    )
    perm = report.requirements[0].permutations[0]
    assert perm.status == PermutationStatus.ok, (
        f"single-perm with explicit set_permutation must still score ok; got {perm.status!r}"
    )


def test_req_023_single_perm_without_set_permutation_is_ok(tmp_path) -> None:
    with set_permutation("single_perm_without_set_permutation_is_ok"):
        _assert_single_perm_without_set_permutation_is_ok(tmp_path)


def test_req_023_multi_perm_still_requires_exact_match(tmp_path) -> None:
    with set_permutation("multi_perm_still_requires_exact_match"):
        _assert_multi_perm_still_requires_exact_match(tmp_path)


def test_req_023_single_perm_with_explicit_set_permutation_still_ok(tmp_path) -> None:
    with set_permutation("single_perm_with_explicit_set_permutation_still_ok"):
        _assert_single_perm_with_explicit_set_permutation_still_ok(tmp_path)
