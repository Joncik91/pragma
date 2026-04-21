"""Dogfood tests for REQ-008 - freeze emits JSON error for unknown milestone/slice refs.

When pragma.yaml references a non-existent milestone/slice, pydantic's
@model_validator raises ValueError, which pydantic wraps under
ctx.error = <the ValueError object>. Before v1.0.1 the CLI's
json.dumps path crashed with TypeError because exceptions aren't
JSON-serializable. _jsonable_errors() sanitises the context before
serialisation.

Wrapped in @trace("REQ-008") helpers so the spans carry
logic_id=REQ-008 and the PIL aggregator does not tag these as mocked.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

from pragma_sdk import set_permutation, trace


def _write_manifest(
    tmp_path: Path,
    *,
    milestone: str | None,
    slice_id: str | None,
    include_milestones: bool = True,
) -> Path:
    req_extras = ""
    if milestone is not None:
        req_extras += f"  milestone: {milestone}\n"
    if slice_id is not None:
        req_extras += f"  slice: {slice_id}\n"
    milestones_block = (
        textwrap.dedent(
            """\
            milestones:
            - id: M01
              title: m1
              description: d
              depends_on: []
              slices:
              - id: M01.S1
                title: s1
                description: d
                requirements:
                - REQ-001
            """
        )
        if include_milestones
        else "milestones: []\n"
    )
    body = (
        textwrap.dedent(
            """\
            version: '2'
            project:
              name: testp
              mode: brownfield
              language: python
              source_root: src/
              tests_root: tests/
            requirements:
            - id: REQ-001
              title: foo
              description: bar
              touches:
              - src/x.py
              permutations:
              - id: p
                description: d
                expected: success
            """
        )
        + req_extras
        + milestones_block
    )
    path = tmp_path / "pragma.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _run_freeze(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pragma", "freeze"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )


@trace("REQ-008")
def _assert_null_milestone_rejected(tmp_path: Path) -> None:
    _write_manifest(tmp_path, milestone="M99", slice_id="M99.S1")
    proc = _run_freeze(tmp_path)
    assert proc.returncode != 0, f"expected non-zero; got stdout={proc.stdout!r}"
    payload = json.loads(proc.stdout)
    assert payload["error"] == "manifest_schema_error"
    assert "milestone" in payload["message"].lower()


@trace("REQ-008")
def _assert_null_slice_rejected(tmp_path: Path) -> None:
    _write_manifest(tmp_path, milestone="M01", slice_id="M01.S99")
    proc = _run_freeze(tmp_path)
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["error"] == "manifest_schema_error"
    assert "slice" in payload["message"].lower()


@trace("REQ-008")
def _assert_all_assigned_success(tmp_path: Path) -> None:
    _write_manifest(tmp_path, milestone="M01", slice_id="M01.S1")
    proc = _run_freeze(tmp_path)
    assert proc.returncode == 0, f"expected success; got stderr={proc.stderr!r}"
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True


def test_req_008_null_milestone_rejected(tmp_path: Path) -> None:
    with set_permutation("null_milestone_rejected"):
        _assert_null_milestone_rejected(tmp_path)


def test_req_008_null_slice_rejected(tmp_path: Path) -> None:
    with set_permutation("null_slice_rejected"):
        _assert_null_slice_rejected(tmp_path)


def test_req_008_all_assigned_success(tmp_path: Path) -> None:
    with set_permutation("all_assigned_success"):
        _assert_all_assigned_success(tmp_path)
