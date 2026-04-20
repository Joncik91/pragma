from __future__ import annotations

import pytest
from pydantic import ValidationError

from pragma.core.state import SliceState, State, default_state


def test_default_state_has_no_active_slice() -> None:
    s = default_state(manifest_hash="sha256:" + "0" * 64)
    assert s.active_slice is None
    assert s.gate is None
    assert s.slices == {}
    assert s.version == 1


def test_state_version_must_be_one() -> None:
    with pytest.raises(ValidationError):
        State(
            version=2,
            active_slice=None,
            gate=None,
            manifest_hash="sha256:" + "0" * 64,
            slices={},
            last_transition=None,
        )


def test_state_active_gate_must_match_slice_gate() -> None:
    with pytest.raises(ValidationError, match=r"gate mismatch"):
        State(
            version=1,
            active_slice="M01.S1",
            gate="UNLOCKED",
            manifest_hash="sha256:" + "0" * 64,
            slices={
                "M01.S1": SliceState(
                    status="in_progress",
                    gate="LOCKED",
                    activated_at="2026-04-20T14:30:00Z",
                    unlocked_at=None,
                    completed_at=None,
                ),
            },
            last_transition=None,
        )


def test_state_active_slice_must_exist_in_slices_map() -> None:
    with pytest.raises(ValidationError, match=r"active_slice.*not in slices"):
        State(
            version=1,
            active_slice="M01.S1",
            gate="LOCKED",
            manifest_hash="sha256:" + "0" * 64,
            slices={},
            last_transition=None,
        )


def test_slice_state_status_enum_enforced() -> None:
    with pytest.raises(ValidationError):
        SliceState(
            status="weird",
            gate=None,
            activated_at=None,
            unlocked_at=None,
            completed_at=None,
        )
