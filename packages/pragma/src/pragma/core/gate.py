"""Pure transition functions for the v0.2 gate.

Each function takes (state, ...) and returns (new_state, audit_entry).
No IO — callers (cli/commands/slice.py, cli/commands/unlock.py) handle
writing state.json and audit.jsonl.
"""

from __future__ import annotations

from typing import Any

from pragma.core.errors import (
    GateWrongState,
    MilestoneDepUnshipped,
    SliceAlreadyActive,
    SliceNotActive,
    SliceNotFound,
)
from pragma.core.models import Manifest
from pragma.core.state import LastTransition, SliceState, State


def _find_slice(manifest: Manifest, slice_id: str) -> tuple[str, str] | None:
    for m in manifest.milestones:
        for s in m.slices:
            if s.id == slice_id:
                return (m.id, s.id)
    return None


def _locate_slice_or_raise(manifest: Manifest, slice_id: str) -> str:
    location = _find_slice(manifest, slice_id)
    if location is None:
        raise SliceNotFound(
            message=f"Slice {slice_id!r} not declared in manifest.",
            remediation=(
                "Add the slice under milestones[].slices[] in "
                "pragma.yaml, or pick one of the declared slice ids."
            ),
            context={"slice": slice_id},
        )
    return location[0]


def _reject_already_active(active: str, requested: str) -> None:
    raise SliceAlreadyActive(
        message=f"Slice {active!r} is already active.",
        remediation=(
            "Complete it (`pragma slice complete`), cancel it "
            "(`pragma slice cancel`), or pass --force to switch."
        ),
        context={"active": active, "requested": requested},
    )


def _check_milestone_deps_shipped(
    state: State, manifest: Manifest, milestone_id: str, slice_id: str
) -> None:
    milestone = next(m for m in manifest.milestones if m.id == milestone_id)
    for dep in milestone.depends_on:
        dep_slices = next(m for m in manifest.milestones if m.id == dep).slices
        for s in dep_slices:
            st = state.slices.get(s.id)
            if st is None or st.status != "shipped":
                raise MilestoneDepUnshipped(
                    message=(
                        f"Cannot activate {slice_id!r}: milestone "
                        f"{milestone_id!r} depends on {dep!r} which "
                        f"still has unshipped slice {s.id!r}."
                    ),
                    remediation=(
                        f"Finish {dep!r} first: activate, unlock, and complete each of its slices."
                    ),
                    context={"milestone": milestone_id, "dep": dep, "pending": s.id},
                )


def _build_activated_state(
    state: State, slice_id: str, now_iso: str, *, force_prior: str | None = None
) -> State:
    """Construct the post-activation State.

    If ``force_prior`` is set, mark that prior slice as ``cancelled``
    in the new ``slices`` map so it does not linger as in-progress
    after a ``--force`` switch (BUG-011).
    """
    new_slices = dict(state.slices)
    if force_prior is not None and force_prior in new_slices:
        prior = new_slices[force_prior]
        new_slices[force_prior] = SliceState(
            status="cancelled",
            gate=None,
            activated_at=prior.activated_at,
            unlocked_at=prior.unlocked_at,
            completed_at=now_iso,
        )
    new_slices[slice_id] = SliceState(
        status="in_progress",
        gate="LOCKED",
        activated_at=now_iso,
        unlocked_at=None,
        completed_at=None,
    )
    return State(
        version=1,
        active_slice=slice_id,
        gate="LOCKED",
        manifest_hash=state.manifest_hash,
        slices=new_slices,
        last_transition=LastTransition(
            event="slice_activated",
            at=now_iso,
            reason=f"pragma slice activate {slice_id}",
            from_gate=None,
            to_gate="LOCKED",
            slice=slice_id,
        ),
    )


def activate(
    *,
    state: State,
    manifest: Manifest,
    slice_id: str,
    now_iso: str,
    force: bool = False,
) -> tuple[State, dict[str, Any]]:
    milestone_id = _locate_slice_or_raise(manifest, slice_id)
    if state.active_slice is not None and not force:
        _reject_already_active(state.active_slice, slice_id)
    _check_milestone_deps_shipped(state, manifest, milestone_id, slice_id)
    # BUG-011: --force must cancel the prior active slice rather than
    # leaving it in_progress-forever in state.slices.
    force_prior = state.active_slice if (force and state.active_slice is not None) else None
    new_state = _build_activated_state(state, slice_id, now_iso, force_prior=force_prior)
    audit = {
        "event": "slice_activated",
        "slice": slice_id,
        "from_state": None,
        "to_state": "LOCKED",
        "reason": (
            f"pragma slice activate {slice_id} (force-switched from {force_prior!r})"
            if force_prior is not None
            else f"pragma slice activate {slice_id}"
        ),
    }
    return new_state, audit


def unlock_transition(state: State, *, now_iso: str) -> tuple[State, dict[str, Any]]:
    if state.active_slice is None:
        raise SliceNotActive(
            message="No active slice; nothing to unlock.",
            remediation="Run `pragma slice activate <id>` first.",
            context={},
        )
    if state.gate != "LOCKED":
        raise GateWrongState(
            message=(f"unlock requires gate=LOCKED; current gate={state.gate}."),
            remediation="This slice is already UNLOCKED or completed.",
            context={"gate": state.gate, "slice": state.active_slice},
        )
    sid = state.active_slice
    old = state.slices[sid]
    new_slices = dict(state.slices)
    new_slices[sid] = SliceState(
        status=old.status,
        gate="UNLOCKED",
        activated_at=old.activated_at,
        unlocked_at=now_iso,
        completed_at=old.completed_at,
    )
    new_state = State(
        version=1,
        active_slice=sid,
        gate="UNLOCKED",
        manifest_hash=state.manifest_hash,
        slices=new_slices,
        last_transition=LastTransition(
            event="unlocked",
            at=now_iso,
            reason=f"pragma unlock (slice {sid})",
            from_gate="LOCKED",
            to_gate="UNLOCKED",
            slice=sid,
        ),
    )
    audit = {
        "event": "unlocked",
        "slice": sid,
        "from_state": "LOCKED",
        "to_state": "UNLOCKED",
        "reason": f"pragma unlock (slice {sid})",
    }
    return new_state, audit


def complete(state: State, *, now_iso: str) -> tuple[State, dict[str, Any]]:
    if state.active_slice is None:
        raise SliceNotActive(
            message="No active slice; nothing to complete.",
            remediation="Activate a slice first.",
            context={},
        )
    if state.gate != "UNLOCKED":
        raise GateWrongState(
            message=(f"complete requires gate=UNLOCKED; current gate={state.gate}."),
            remediation=("Run `pragma unlock` first after writing failing tests."),
            context={"gate": state.gate, "slice": state.active_slice},
        )
    sid = state.active_slice
    old = state.slices[sid]
    new_slices = dict(state.slices)
    new_slices[sid] = SliceState(
        status="shipped",
        gate=None,
        activated_at=old.activated_at,
        unlocked_at=old.unlocked_at,
        completed_at=now_iso,
    )
    new_state = State(
        version=1,
        active_slice=None,
        gate=None,
        manifest_hash=state.manifest_hash,
        slices=new_slices,
        last_transition=LastTransition(
            event="slice_completed",
            at=now_iso,
            reason=f"pragma slice complete (slice {sid})",
            from_gate="UNLOCKED",
            to_gate=None,
            slice=sid,
        ),
    )
    audit = {
        "event": "slice_completed",
        "slice": sid,
        "from_state": "UNLOCKED",
        "to_state": None,
        "reason": f"pragma slice complete (slice {sid})",
    }
    return new_state, audit


def cancel(state: State, *, now_iso: str) -> tuple[State, dict[str, Any]]:
    """Cancel the active slice.

    KI-5: slices that never reached UNLOCKED have no useful history
    (the user activated by mistake, changed their mind, or the
    transition failed halfway). Those are erased from state.slices
    entirely so a subsequent ``pragma freeze`` on a slightly-edited
    manifest does not cause gate_hash_drift against a stale slice
    record that the state machine can't move forward or clean up.

    Slices that did reach UNLOCKED at some point are genuine history:
    they stay in state.slices with status=cancelled for downstream
    narrative / doctor audit. The distinction is ``unlocked_at`` -
    non-None means the gate observed the slice pass the red-tests
    check, so the record is worth keeping.
    """
    if state.active_slice is None:
        raise SliceNotActive(
            message="No active slice; nothing to cancel.",
            remediation="Activate a slice first.",
            context={},
        )
    sid = state.active_slice
    old = state.slices[sid]
    new_slices = dict(state.slices)
    if old.unlocked_at is None:
        # Never reached UNLOCKED. Erase rather than mark cancelled.
        del new_slices[sid]
    else:
        new_slices[sid] = SliceState(
            status="cancelled",
            gate=None,
            activated_at=old.activated_at,
            unlocked_at=old.unlocked_at,
            completed_at=old.completed_at,
        )
    new_state = State(
        version=1,
        active_slice=None,
        gate=None,
        manifest_hash=state.manifest_hash,
        slices=new_slices,
        last_transition=LastTransition(
            event="slice_cancelled",
            at=now_iso,
            reason=f"pragma slice cancel (slice {sid})",
            from_gate=state.gate,
            to_gate=None,
            slice=sid,
        ),
    )
    audit = {
        "event": "slice_cancelled",
        "slice": sid,
        "from_state": state.gate,
        "to_state": None,
        "reason": f"pragma slice cancel (slice {sid})",
    }
    return new_state, audit
