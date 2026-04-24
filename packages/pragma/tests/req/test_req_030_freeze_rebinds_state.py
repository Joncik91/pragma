"""Red tests for REQ-030 — freeze rebinds state.manifest_hash when neutral.

BUG-032. After greenfield init + manifest edit + freeze, the state
still carries the scaffold-init hash, so `pragma doctor` reports
`stale_state` immediately. Freeze is the authoritative "lock on
this manifest" action and should carry state along with it — but
only when no slice is active (rebind mid-active-slice would hide
real drift the gate needs to catch).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.state import read_state

runner = CliRunner()


def _init_greenfield(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.chdir(tmp_project)
    assert (
        runner.invoke(
            app,
            ["init", "--greenfield", "--name", "demo", "--language", "python", "--force"],
        ).exit_code
        == 0
    )
    lock = json.loads((tmp_project / "pragma.lock.json").read_text(encoding="utf-8"))
    return str(lock["manifest_hash"])


def _rewrite_manifest(tmp_project: Path) -> None:
    (tmp_project / "pragma.yaml").write_text(
        textwrap.dedent(
            """
            version: '2'
            project:
              name: demo
              mode: greenfield
              language: python
              source_root: src/
              tests_root: tests/
            milestones:
            - id: M01
              title: m
              description: m
              depends_on: []
              slices:
              - id: M01.S1
                title: s
                description: s
                requirements: [REQ-001]
            requirements:
            - id: REQ-001
              title: t
              description: d
              touches: [src/x.py]
              permutations:
              - id: h
                description: h
                expected: success
              milestone: M01
              slice: M01.S1
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


@trace("REQ-030")
def _assert_rebinds_when_neutral(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scaffold_hash = _init_greenfield(tmp_project, monkeypatch)
    # Precondition: state carries scaffold hash, no active slice.
    state_before = read_state(tmp_project / ".pragma")
    assert state_before.active_slice is None
    assert state_before.manifest_hash == scaffold_hash

    _rewrite_manifest(tmp_project)
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    new_lock = json.loads((tmp_project / "pragma.lock.json").read_text(encoding="utf-8"))
    new_hash = new_lock["manifest_hash"]
    assert new_hash != scaffold_hash

    state_after = read_state(tmp_project / ".pragma")
    assert state_after.manifest_hash == new_hash, (
        f"freeze on a neutral-state project must rebind state.manifest_hash "
        f"to the new lock hash ({new_hash!r}); got {state_after.manifest_hash!r}"
    )

    # And verify gate / verify all must now stay green without any
    # emergency-unlock ceremony.
    assert runner.invoke(app, ["verify", "gate"]).exit_code == 0


@trace("REQ-030")
def _assert_leaves_state_when_slice_active(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init_greenfield(tmp_project, monkeypatch)
    _rewrite_manifest(tmp_project)
    # First freeze + activate brings state into alignment with the new lock.
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    state_activated = read_state(tmp_project / ".pragma")
    locked_hash = state_activated.manifest_hash

    # Edit the manifest AGAIN while the slice is active, then freeze.
    # The active-slice invariant matters here: freeze must NOT rebind
    # state mid-slice, otherwise verify gate would hide the real drift
    # the gate exists to catch.
    (tmp_project / "pragma.yaml").write_text(
        (tmp_project / "pragma.yaml").read_text(encoding="utf-8") + "\nvision: added-mid-slice\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["freeze"]).exit_code == 0

    state_after = read_state(tmp_project / ".pragma")
    assert state_after.manifest_hash == locked_hash, (
        f"freeze during an active slice must NOT rebind state.manifest_hash; "
        f"got {state_after.manifest_hash!r} expected preserved {locked_hash!r}"
    )
    # The gate must surface drift; verify gate exits non-zero.
    assert runner.invoke(app, ["verify", "gate"]).exit_code != 0


def test_req_030_rebinds_when_neutral(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with set_permutation("rebinds_when_neutral"):
        _assert_rebinds_when_neutral(tmp_project, monkeypatch)


def test_req_030_leaves_state_when_slice_active(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("leaves_state_when_slice_active"):
        _assert_leaves_state_when_slice_active(tmp_project, monkeypatch)
