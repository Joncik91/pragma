from __future__ import annotations

import json
from pathlib import Path

from pragma.core.audit import AUDIT_FILENAME, append_audit, read_audit


def test_append_creates_file(tmp_path: Path) -> None:
    dir_ = tmp_path / ".pragma"
    dir_.mkdir()
    append_audit(
        dir_,
        event="slice_activated",
        actor="cli",
        slice="M00.S0",
        from_state=None,
        to_state="LOCKED",
        reason="test",
    )
    assert (dir_ / AUDIT_FILENAME).exists()


def test_append_adds_one_line_per_call(tmp_path: Path) -> None:
    dir_ = tmp_path / ".pragma"
    dir_.mkdir()
    for i in range(3):
        append_audit(
            dir_,
            event="slice_activated",
            actor="cli",
            slice=f"M00.S{i}",
            from_state=None,
            to_state="LOCKED",
            reason=f"r{i}",
        )
    lines = (dir_ / AUDIT_FILENAME).read_text().splitlines()
    assert len(lines) == 3
    for line in lines:
        assert json.loads(line)["event"] == "slice_activated"


def test_append_never_truncates_existing(tmp_path: Path) -> None:
    dir_ = tmp_path / ".pragma"
    dir_.mkdir()
    existing = dir_ / AUDIT_FILENAME
    existing.write_text('{"ts":"old","event":"x","actor":"cli"}\n', encoding="utf-8")
    append_audit(
        dir_,
        event="slice_activated",
        actor="cli",
        slice="M00.S0",
        from_state=None,
        to_state="LOCKED",
        reason="test",
    )
    lines = existing.read_text().splitlines()
    assert len(lines) == 2
    assert "old" in lines[0]


def test_append_entries_are_sorted_json(tmp_path: Path) -> None:
    dir_ = tmp_path / ".pragma"
    dir_.mkdir()
    append_audit(
        dir_,
        event="x",
        actor="cli",
        slice="M00.S0",
        from_state=None,
        to_state="LOCKED",
        reason="r",
    )
    line = (dir_ / AUDIT_FILENAME).read_text().strip()
    assert line.startswith("{")
    loaded = json.loads(line)
    assert set(loaded.keys()) == {
        "ts",
        "event",
        "actor",
        "slice",
        "from_state",
        "to_state",
        "reason",
        "context",
    }


def test_read_audit_returns_all_lines(tmp_path: Path) -> None:
    dir_ = tmp_path / ".pragma"
    dir_.mkdir()
    for i in range(2):
        append_audit(
            dir_,
            event="e",
            actor="cli",
            slice="S",
            from_state=None,
            to_state="LOCKED",
            reason=f"r{i}",
        )
    entries = read_audit(dir_)
    assert len(entries) == 2
    assert entries[0]["reason"] == "r0"
    assert entries[1]["reason"] == "r1"
