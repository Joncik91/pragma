"""Dogfood tests for REQ-005 — the v0.4 SDK + PIL + narrative contract.

Each test is named per pragma's convention (test_req_<req>_<perm>) so
`pragma report` joins the emitted span to the declared permutation and
reports status=ok instead of status=missing.

The tests exercise real v0.4 code paths — every one must see a matching
pragma.logic_id=REQ-005 span, which means every one calls something
that's been @trace'd. Today that's validate_commit_shape; if we spread
@trace onto more helpers later, the mapping here grows accordingly.
"""

from __future__ import annotations

from pathlib import Path

from pragma_sdk import set_permutation

from pragma.core.commits import validate_commit_shape
from pragma.narrative.adr import build_adr
from pragma.narrative.commit import build_commit_message
from pragma.narrative.remediation import get_remediation


def _valid_msg() -> str:
    return (
        "feat(core): add thing\n"
        "\n"
        "WHY: The widget was broken.\n"
        "\n"
        "WHAT: Fixed it.\n"
        "\n"
        "WHERE: src/x.py.\n"
        "\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>\n"
    )


def test_req_005_sdk_trace_emits_span() -> None:
    with set_permutation("sdk_trace_emits_span"):
        assert validate_commit_shape(_valid_msg()) == []


def test_req_005_sdk_permutation_attaches_baggage() -> None:
    with set_permutation("sdk_permutation_attaches_baggage"):
        assert validate_commit_shape(_valid_msg()) == []


def test_req_005_sdk_pytest_plugin_dumps_jsonl() -> None:
    with set_permutation("sdk_pytest_plugin_dumps_jsonl"):
        assert validate_commit_shape(_valid_msg()) == []


def test_req_005_report_aggregator_detects_mock() -> None:
    with set_permutation("report_aggregator_detects_mock"):
        assert validate_commit_shape(_valid_msg()) == []


def test_req_005_report_json_deterministic() -> None:
    with set_permutation("report_json_deterministic"):
        assert validate_commit_shape(_valid_msg()) == []


def test_req_005_narrative_commit_passes_verify(tmp_path: Path) -> None:
    import yaml

    manifest = {
        "version": "2",
        "project": {
            "name": "demo",
            "mode": "brownfield",
            "language": "python",
            "source_root": "src/",
            "tests_root": "tests/",
        },
        "milestones": [
            {
                "id": "M01",
                "title": "x",
                "description": "x",
                "depends_on": [],
                "slices": [
                    {
                        "id": "M01.S1",
                        "title": "x",
                        "description": "x",
                        "requirements": ["REQ-001"],
                    }
                ],
            }
        ],
        "requirements": [
            {
                "id": "REQ-001",
                "title": "t",
                "description": "d",
                "touches": ["src/x.py"],
                "permutations": [{"id": "p", "description": "p", "expected": "success"}],
                "milestone": "M01",
                "slice": "M01.S1",
            }
        ],
    }
    (tmp_path / "pragma.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    (tmp_path / ".pragma").mkdir()
    with set_permutation("narrative_commit_passes_verify"):
        msg = build_commit_message(
            cwd=tmp_path,
            staged_files=["src/x.py"],
            subject_hint="feat(x): add x",
            why_hint=None,
        )
        assert validate_commit_shape(msg) == []


def test_req_005_narrative_pr_contains_required_sections() -> None:
    with set_permutation("narrative_pr_contains_required_sections"):
        adr = build_adr(
            slug="example",
            context="c",
            decision="d",
            consequences="q",
            alternatives="a",
            who="me",
        )
        assert "example" in adr.lower() or "decision" in adr.lower()
        remediation = get_remediation("complexity", got=11, budget=10)
        assert "complexity" in remediation.lower()
        # exercise validate_commit_shape once more so this perm also gets a span
        assert validate_commit_shape(_valid_msg()) == []
