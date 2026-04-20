from __future__ import annotations

import pytest

from pragma.core.errors import (
    GateWrongState,
    MilestoneDepUnshipped,
    SliceAlreadyActive,
    SliceNotActive,
    SliceNotFound,
)
from pragma.core.gate import activate, cancel, complete, unlock_transition
from pragma.core.models import Manifest
from pragma.core.state import SliceState, State, default_state


def _state_with_no_active(hash_: str) -> State:
    return default_state(manifest_hash=hash_)


def test_activate_sets_locked(v2_manifest_dict: dict) -> None:
    manifest = Manifest.model_validate(v2_manifest_dict)
    initial = _state_with_no_active(hash_="sha256:" + "a" * 64)
    new_state, audit = activate(
        state=initial, manifest=manifest, slice_id="M01.S1",
        now_iso="2026-04-20T14:30:00Z",
    )
    assert new_state.active_slice == "M01.S1"
    assert new_state.gate == "LOCKED"
    assert new_state.slices["M01.S1"].status == "in_progress"
    assert new_state.slices["M01.S1"].gate == "LOCKED"
    assert audit["event"] == "slice_activated"
    assert audit["to_state"] == "LOCKED"


def test_activate_unknown_slice_raises(v2_manifest_dict: dict) -> None:
    manifest = Manifest.model_validate(v2_manifest_dict)
    with pytest.raises(SliceNotFound):
        activate(
            state=_state_with_no_active(hash_="sha256:" + "a" * 64),
            manifest=manifest, slice_id="M99.S99",
            now_iso="2026-04-20T14:30:00Z",
        )


def test_activate_refuses_when_another_active_without_force(v2_manifest_dict: dict) -> None:
    manifest = Manifest.model_validate(v2_manifest_dict)
    active = activate(
        state=_state_with_no_active(hash_="sha256:" + "a" * 64),
        manifest=manifest, slice_id="M01.S1",
        now_iso="2026-04-20T14:30:00Z",
    )[0]
    with pytest.raises(SliceAlreadyActive):
        activate(
            state=active, manifest=manifest, slice_id="M01.S1",
            now_iso="2026-04-20T14:30:00Z",
        )


def test_activate_rejects_when_milestone_dep_unshipped(v2_manifest_dict: dict) -> None:
    v2_manifest_dict["milestones"].append(
        {
            "id": "M02", "title": "Two", "description": "x",
            "depends_on": ["M01"], "slices": [
                {"id": "M02.S1", "title": "a", "description": "b", "requirements": []},
            ],
        }
    )
    manifest = Manifest.model_validate(v2_manifest_dict)
    initial = _state_with_no_active(hash_="sha256:" + "a" * 64)
    with pytest.raises(MilestoneDepUnshipped):
        activate(
            state=initial, manifest=manifest, slice_id="M02.S1",
            now_iso="2026-04-20T14:30:00Z",
        )


def test_unlock_transition_flips_gate() -> None:
    state = State(
        version=1,
        active_slice="M01.S1",
        gate="LOCKED",
        manifest_hash="sha256:" + "a" * 64,
        slices={"M01.S1": SliceState(
            status="in_progress", gate="LOCKED",
            activated_at="2026-04-20T14:30:00Z",
            unlocked_at=None, completed_at=None,
        )},
        last_transition=None,
    )
    new_state, audit = unlock_transition(state, now_iso="2026-04-20T14:31:00Z")
    assert new_state.gate == "UNLOCKED"
    assert new_state.slices["M01.S1"].gate == "UNLOCKED"
    assert new_state.slices["M01.S1"].unlocked_at == "2026-04-20T14:31:00Z"
    assert audit["event"] == "unlocked"


def test_unlock_refuses_when_not_locked() -> None:
    state = State(
        version=1,
        active_slice="M01.S1",
        gate="UNLOCKED",
        manifest_hash="sha256:" + "a" * 64,
        slices={"M01.S1": SliceState(
            status="in_progress", gate="UNLOCKED",
            activated_at="2026-04-20T14:30:00Z",
            unlocked_at="2026-04-20T14:31:00Z", completed_at=None,
        )},
        last_transition=None,
    )
    with pytest.raises(GateWrongState):
        unlock_transition(state, now_iso="2026-04-20T14:32:00Z")


def test_complete_requires_unlocked() -> None:
    state = State(
        version=1, active_slice="M01.S1", gate="LOCKED",
        manifest_hash="sha256:" + "a" * 64,
        slices={"M01.S1": SliceState(
            status="in_progress", gate="LOCKED",
            activated_at="2026-04-20T14:30:00Z",
            unlocked_at=None, completed_at=None,
        )},
        last_transition=None,
    )
    with pytest.raises(GateWrongState):
        complete(state, now_iso="2026-04-20T14:32:00Z")


def test_complete_marks_shipped() -> None:
    state = State(
        version=1, active_slice="M01.S1", gate="UNLOCKED",
        manifest_hash="sha256:" + "a" * 64,
        slices={"M01.S1": SliceState(
            status="in_progress", gate="UNLOCKED",
            activated_at="2026-04-20T14:30:00Z",
            unlocked_at="2026-04-20T14:31:00Z", completed_at=None,
        )},
        last_transition=None,
    )
    new_state, audit = complete(state, now_iso="2026-04-20T14:32:00Z")
    assert new_state.slices["M01.S1"].status == "shipped"
    assert new_state.slices["M01.S1"].completed_at == "2026-04-20T14:32:00Z"
    assert new_state.active_slice is None
    assert new_state.gate is None
    assert audit["event"] == "slice_completed"


def test_cancel_requires_active() -> None:
    with pytest.raises(SliceNotActive):
        cancel(
            _state_with_no_active(hash_="sha256:" + "a" * 64),
            now_iso="2026-04-20T14:32:00Z",
        )


def test_cancel_marks_cancelled() -> None:
    state = State(
        version=1, active_slice="M01.S1", gate="LOCKED",
        manifest_hash="sha256:" + "a" * 64,
        slices={"M01.S1": SliceState(
            status="in_progress", gate="LOCKED",
            activated_at="2026-04-20T14:30:00Z",
            unlocked_at=None, completed_at=None,
        )},
        last_transition=None,
    )
    new_state, audit = cancel(state, now_iso="2026-04-20T14:32:00Z")
    assert new_state.slices["M01.S1"].status == "cancelled"
    assert new_state.active_slice is None
    assert audit["event"] == "slice_cancelled"
