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
        state=initial,
        manifest=manifest,
        slice_id="M01.S1",
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
            manifest=manifest,
            slice_id="M99.S99",
            now_iso="2026-04-20T14:30:00Z",
        )


def test_activate_refuses_when_another_active_without_force(v2_manifest_dict: dict) -> None:
    manifest = Manifest.model_validate(v2_manifest_dict)
    active = activate(
        state=_state_with_no_active(hash_="sha256:" + "a" * 64),
        manifest=manifest,
        slice_id="M01.S1",
        now_iso="2026-04-20T14:30:00Z",
    )[0]
    with pytest.raises(SliceAlreadyActive):
        activate(
            state=active,
            manifest=manifest,
            slice_id="M01.S1",
            now_iso="2026-04-20T14:30:00Z",
        )


def test_activate_rejects_when_milestone_dep_unshipped(v2_manifest_dict: dict) -> None:
    v2_manifest_dict["milestones"].append(
        {
            "id": "M02",
            "title": "Two",
            "description": "x",
            "depends_on": ["M01"],
            "slices": [
                {"id": "M02.S1", "title": "a", "description": "b", "requirements": []},
            ],
        }
    )
    manifest = Manifest.model_validate(v2_manifest_dict)
    initial = _state_with_no_active(hash_="sha256:" + "a" * 64)
    with pytest.raises(MilestoneDepUnshipped):
        activate(
            state=initial,
            manifest=manifest,
            slice_id="M02.S1",
            now_iso="2026-04-20T14:30:00Z",
        )


def test_activate_force_cancels_prior_active_slice(v2_manifest_dict: dict) -> None:
    """--force must cancel the prior in-progress slice, not orphan it (BUG-011).

    Before v1.0.2, activating slice B with force=True while slice A was
    active left slice A as in_progress forever in state.slices. That
    breaks every downstream check that enumerates slice statuses (e.g.
    milestone_dep_unshipped). --force should mark the prior slice
    cancelled with completed_at=now so the state machine stays coherent.
    """
    # Two slices in the same milestone so no dep check gets in the way.
    v2_manifest_dict["milestones"][0]["slices"].append(
        {"id": "M01.S2", "title": "b", "description": "c", "requirements": []}
    )
    manifest = Manifest.model_validate(v2_manifest_dict)

    state_a, _ = activate(
        state=_state_with_no_active(hash_="sha256:" + "a" * 64),
        manifest=manifest,
        slice_id="M01.S1",
        now_iso="2026-04-20T14:30:00Z",
    )
    assert state_a.slices["M01.S1"].status == "in_progress"

    state_b, audit_b = activate(
        state=state_a,
        manifest=manifest,
        slice_id="M01.S2",
        now_iso="2026-04-20T15:00:00Z",
        force=True,
    )
    # New slice is in_progress and active.
    assert state_b.active_slice == "M01.S2"
    assert state_b.slices["M01.S2"].status == "in_progress"
    # Prior slice is cancelled (not still in_progress).
    assert state_b.slices["M01.S1"].status == "cancelled"
    assert state_b.slices["M01.S1"].completed_at == "2026-04-20T15:00:00Z"
    # Audit reason flags the force-switch for post-hoc narrative.
    assert "force-switched" in audit_b["reason"]


def test_unlock_transition_flips_gate() -> None:
    state = State(
        version=1,
        active_slice="M01.S1",
        gate="LOCKED",
        manifest_hash="sha256:" + "a" * 64,
        slices={
            "M01.S1": SliceState(
                status="in_progress",
                gate="LOCKED",
                activated_at="2026-04-20T14:30:00Z",
                unlocked_at=None,
                completed_at=None,
            )
        },
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
        slices={
            "M01.S1": SliceState(
                status="in_progress",
                gate="UNLOCKED",
                activated_at="2026-04-20T14:30:00Z",
                unlocked_at="2026-04-20T14:31:00Z",
                completed_at=None,
            )
        },
        last_transition=None,
    )
    with pytest.raises(GateWrongState):
        unlock_transition(state, now_iso="2026-04-20T14:32:00Z")


def test_complete_requires_unlocked() -> None:
    state = State(
        version=1,
        active_slice="M01.S1",
        gate="LOCKED",
        manifest_hash="sha256:" + "a" * 64,
        slices={
            "M01.S1": SliceState(
                status="in_progress",
                gate="LOCKED",
                activated_at="2026-04-20T14:30:00Z",
                unlocked_at=None,
                completed_at=None,
            )
        },
        last_transition=None,
    )
    with pytest.raises(GateWrongState):
        complete(state, now_iso="2026-04-20T14:32:00Z")


def test_complete_marks_shipped() -> None:
    state = State(
        version=1,
        active_slice="M01.S1",
        gate="UNLOCKED",
        manifest_hash="sha256:" + "a" * 64,
        slices={
            "M01.S1": SliceState(
                status="in_progress",
                gate="UNLOCKED",
                activated_at="2026-04-20T14:30:00Z",
                unlocked_at="2026-04-20T14:31:00Z",
                completed_at=None,
            )
        },
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


def test_cancel_erases_never_unlocked_slice() -> None:
    """Cancelling a slice that never reached UNLOCKED removes it from state (KI-5).

    Before v1.0.2, cancel marked the slice cancelled and left it in
    state.slices. A subsequent pragma freeze on an edited manifest
    then produced gate_hash_drift because the slice record was
    pinned to the old manifest_hash but nothing could transition it
    further. Erasing never-unlocked slices keeps the state machine
    coherent; slices that did reach UNLOCKED stay as real history.
    """
    state = State(
        version=1,
        active_slice="M01.S1",
        gate="LOCKED",
        manifest_hash="sha256:" + "a" * 64,
        slices={
            "M01.S1": SliceState(
                status="in_progress",
                gate="LOCKED",
                activated_at="2026-04-20T14:30:00Z",
                unlocked_at=None,
                completed_at=None,
            )
        },
        last_transition=None,
    )
    new_state, audit = cancel(state, now_iso="2026-04-20T14:32:00Z")
    assert "M01.S1" not in new_state.slices
    assert new_state.active_slice is None
    assert new_state.gate is None
    assert audit["event"] == "slice_cancelled"


def test_cancel_keeps_unlocked_slice_as_cancelled() -> None:
    """Cancel of an UNLOCKED slice keeps the record with status=cancelled (KI-5)."""
    state = State(
        version=1,
        active_slice="M01.S1",
        gate="UNLOCKED",
        manifest_hash="sha256:" + "a" * 64,
        slices={
            "M01.S1": SliceState(
                status="in_progress",
                gate="UNLOCKED",
                activated_at="2026-04-20T14:30:00Z",
                unlocked_at="2026-04-20T14:31:00Z",
                completed_at=None,
            )
        },
        last_transition=None,
    )
    new_state, audit = cancel(state, now_iso="2026-04-20T14:32:00Z")
    assert new_state.slices["M01.S1"].status == "cancelled"
    assert new_state.slices["M01.S1"].unlocked_at == "2026-04-20T14:31:00Z"
    assert new_state.active_slice is None
    assert audit["event"] == "slice_cancelled"
