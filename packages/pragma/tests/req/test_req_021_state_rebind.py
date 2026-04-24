"""Red tests for REQ-021 — every transition rebinds state.manifest_hash.

BUG-022. Greenfield scaffold writes state.json with the scaffold's
manifest hash. User edits the seed manifest and runs `pragma freeze`
— lock hash changes. `activate`, `unlock`, and `complete` all
preserve state.manifest_hash from the previous state, so after
shipping every slice `state.manifest_hash` is still the scaffold's
original hash and `verify gate` fails with `gate_hash_drift`. Cancel
was fixed in v1.0.6 (BUG-016); v1.1.2 generalises the pattern.
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


def _build_greenfield_with_refreeze(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Scaffold greenfield, rewrite manifest with real content, refreeze.

    Returns the new lock's manifest_hash so tests can assert rebind.
    """
    monkeypatch.chdir(tmp_project)
    assert (
        runner.invoke(
            app,
            ["init", "--greenfield", "--name", "demo", "--language", "python", "--force"],
        ).exit_code
        == 0
    )
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
              title: one
              description: one
              depends_on: []
              slices:
              - id: M01.S1
                title: one
                description: one
                requirements: [REQ-001]
            requirements:
            - id: REQ-001
              title: one
              description: one
              touches: [src/demo_mod.py]
              permutations:
              - id: a
                description: a
                expected: success
              milestone: M01
              slice: M01.S1
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["freeze"]).exit_code == 0
    payload = json.loads((tmp_project / "pragma.lock.json").read_text(encoding="utf-8"))
    new_hash = payload["manifest_hash"]
    assert isinstance(new_hash, str)
    # Sanity: state.json still carries the scaffold's original hash,
    # so any transition that only preserves state.manifest_hash will
    # leave state stale.
    scaffold_state = read_state(tmp_project / ".pragma")
    assert scaffold_state.manifest_hash != new_hash, (
        "test precondition: scaffold state should hold stale hash before first transition"
    )
    return new_hash


def _write_red_test_and_stub(tmp_project: Path) -> None:
    (tmp_project / "src" / "demo_mod.py").write_text(
        textwrap.dedent(
            """
            from pragma_sdk import trace

            @trace("REQ-001")
            def f() -> str:
                raise NotImplementedError
            """
        ),
        encoding="utf-8",
    )
    (tmp_project / "tests" / "test_req_001_demo.py").write_text(
        textwrap.dedent(
            """
            from pragma_sdk import set_permutation
            from demo_mod import f

            def test_req_001_a() -> None:
                with set_permutation("a"):
                    assert f() == "ok"
            """
        ),
        encoding="utf-8",
    )


def _make_green(tmp_project: Path) -> None:
    (tmp_project / "src" / "demo_mod.py").write_text(
        textwrap.dedent(
            """
            from pragma_sdk import trace

            @trace("REQ-001")
            def f() -> str:
                return "ok"
            """
        ),
        encoding="utf-8",
    )


@trace("REQ-021")
def _assert_activate_rebinds_manifest_hash(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_hash = _build_greenfield_with_refreeze(tmp_project, monkeypatch)
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    state = read_state(tmp_project / ".pragma")
    assert state.manifest_hash == new_hash, (
        f"activate must rebind state.manifest_hash to the current lock hash "
        f"({new_hash!r}); got {state.manifest_hash!r}"
    )


@trace("REQ-021")
def _assert_unlock_rebinds_manifest_hash(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_hash = _build_greenfield_with_refreeze(tmp_project, monkeypatch)
    _write_red_test_and_stub(tmp_project)
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    assert runner.invoke(app, ["unlock"]).exit_code == 0
    state = read_state(tmp_project / ".pragma")
    assert state.manifest_hash == new_hash, (
        f"unlock must rebind state.manifest_hash to the current lock hash "
        f"({new_hash!r}); got {state.manifest_hash!r}"
    )


@trace("REQ-021")
def _assert_complete_rebinds_manifest_hash(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_hash = _build_greenfield_with_refreeze(tmp_project, monkeypatch)
    _write_red_test_and_stub(tmp_project)
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    assert runner.invoke(app, ["unlock"]).exit_code == 0
    _make_green(tmp_project)
    assert runner.invoke(app, ["slice", "complete"]).exit_code == 0
    state = read_state(tmp_project / ".pragma")
    assert state.manifest_hash == new_hash, (
        f"slice complete must rebind state.manifest_hash to the current lock hash "
        f"({new_hash!r}); got {state.manifest_hash!r}"
    )


@trace("REQ-021")
def _assert_verify_gate_green_after_shipping_all_slices(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _build_greenfield_with_refreeze(tmp_project, monkeypatch)
    _write_red_test_and_stub(tmp_project)
    assert runner.invoke(app, ["slice", "activate", "M01.S1"]).exit_code == 0
    assert runner.invoke(app, ["unlock"]).exit_code == 0
    _make_green(tmp_project)
    assert runner.invoke(app, ["slice", "complete"]).exit_code == 0
    result = runner.invoke(app, ["verify", "gate"])
    assert result.exit_code == 0, (
        f"verify gate must be green after shipping every slice on a refrozen "
        f"greenfield; got exit_code={result.exit_code} stdout={result.stdout!r}"
    )


def test_req_021_activate_rebinds_manifest_hash(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("activate_rebinds_manifest_hash"):
        _assert_activate_rebinds_manifest_hash(tmp_project, monkeypatch)


def test_req_021_unlock_rebinds_manifest_hash(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("unlock_rebinds_manifest_hash"):
        _assert_unlock_rebinds_manifest_hash(tmp_project, monkeypatch)


def test_req_021_complete_rebinds_manifest_hash(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("complete_rebinds_manifest_hash"):
        _assert_complete_rebinds_manifest_hash(tmp_project, monkeypatch)


def test_req_021_verify_gate_green_after_shipping_all_slices(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("verify_gate_green_after_shipping_all_slices"):
        _assert_verify_gate_green_after_shipping_all_slices(tmp_project, monkeypatch)
