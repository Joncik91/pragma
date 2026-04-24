"""Red tests for REQ-022 — slice activate refuses to un-ship a shipped slice.

BUG-024. `pragma slice activate <id>` on an already-shipped slice
quietly flipped it back to in_progress + LOCKED, erased the ship
record from state.slices, and blocked dep-gated slices in later
milestones from activating. Fix: refuse with slice_already_shipped
unless --force is passed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pragma_sdk import set_permutation, trace

from pragma.core.errors import SliceAlreadyShipped
from pragma.core.gate import activate
from pragma.core.models import (
    Manifest,
    Milestone,
    Permutation,
    Project,
    Requirement,
    Slice,
)
from pragma.core.state import SliceState, State


def _manifest_with_one_slice() -> Manifest:
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
                permutations=(Permutation(id="a", description="a", expected="success"),),
                milestone="M01",
                slice="M01.S1",
            ),
        ),
    )


def _shipped_state() -> State:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return State(
        version=1,
        active_slice=None,
        gate=None,
        manifest_hash="sha256:" + "0" * 64,
        slices={
            "M01.S1": SliceState(
                status="shipped",
                gate=None,
                activated_at=now,
                unlocked_at=now,
                completed_at=now,
            ),
        },
        last_transition=None,
    )


@trace("REQ-022")
def _assert_activate_refuses_shipped() -> None:
    manifest = _manifest_with_one_slice()
    state = _shipped_state()
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with pytest.raises(SliceAlreadyShipped) as exc_info:
        activate(state=state, manifest=manifest, slice_id="M01.S1", now_iso=now)
    assert exc_info.value.context.get("slice") == "M01.S1"


@trace("REQ-022")
def _assert_activate_force_reopens_shipped() -> None:
    manifest = _manifest_with_one_slice()
    state = _shipped_state()
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_state, _audit = activate(
        state=state, manifest=manifest, slice_id="M01.S1", now_iso=now, force=True
    )
    assert new_state.active_slice == "M01.S1"
    assert new_state.gate == "LOCKED"
    # --force is explicit intent; the old shipped record IS overwritten.
    # That's acceptable because the user opted in.
    assert new_state.slices["M01.S1"].status == "in_progress"


@trace("REQ-022")
def _assert_shipped_record_survives_refused_activate() -> None:
    manifest = _manifest_with_one_slice()
    state = _shipped_state()
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with pytest.raises(SliceAlreadyShipped):
        activate(state=state, manifest=manifest, slice_id="M01.S1", now_iso=now)
    # State must not have been mutated by the refused call.
    assert state.slices["M01.S1"].status == "shipped"
    assert state.active_slice is None


def test_req_022_activate_refuses_shipped() -> None:
    with set_permutation("activate_refuses_shipped"):
        _assert_activate_refuses_shipped()


def test_req_022_activate_force_reopens_shipped() -> None:
    with set_permutation("activate_force_reopens_shipped"):
        _assert_activate_force_reopens_shipped()


def test_req_022_shipped_record_survives_refused_activate() -> None:
    with set_permutation("shipped_record_survives_refused_activate"):
        _assert_shipped_record_survives_refused_activate()
