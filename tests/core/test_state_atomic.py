from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pragma.core.errors import StateLocked, StateNotFound, StateSchemaError
from pragma.core.state import State, default_state, read_state, write_state

STATE_FILENAME = "state.json"


def _state(hash_: str) -> State:
    return default_state(manifest_hash=hash_)


def test_write_then_read_roundtrips(tmp_path: Path) -> None:
    dir_ = tmp_path / ".pragma"
    dir_.mkdir()
    s = _state("sha256:" + "a" * 64)
    write_state(dir_, s)
    read = read_state(dir_)
    assert read == s


def test_write_is_atomic_no_tmp_leftovers(tmp_path: Path) -> None:
    dir_ = tmp_path / ".pragma"
    dir_.mkdir()
    write_state(dir_, _state("sha256:" + "b" * 64))
    entries = {p.name for p in dir_.iterdir()}
    assert STATE_FILENAME in entries
    assert not any(e.startswith("state.json.tmp") for e in entries)


def test_read_missing_raises(tmp_path: Path) -> None:
    dir_ = tmp_path / ".pragma"
    dir_.mkdir()
    with pytest.raises(StateNotFound):
        read_state(dir_)


def test_read_malformed_raises_schema_error(tmp_path: Path) -> None:
    dir_ = tmp_path / ".pragma"
    dir_.mkdir()
    (dir_ / STATE_FILENAME).write_text("not json at all", encoding="utf-8")
    with pytest.raises(StateSchemaError):
        read_state(dir_)


def test_read_bad_schema_raises_schema_error(tmp_path: Path) -> None:
    dir_ = tmp_path / ".pragma"
    dir_.mkdir()
    (dir_ / STATE_FILENAME).write_text(
        json.dumps({"version": 1, "unexpected": True}), encoding="utf-8"
    )
    with pytest.raises(StateSchemaError):
        read_state(dir_)


def test_write_creates_pragma_dir_if_missing(tmp_path: Path) -> None:
    dir_ = tmp_path / ".pragma"
    write_state(dir_, _state("sha256:" + "c" * 64))
    assert (dir_ / STATE_FILENAME).exists()


def test_flock_blocks_concurrent_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dir_ = tmp_path / ".pragma"
    dir_.mkdir()
    import fcntl
    lock_path = dir_ / "state.json.lock"
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        monkeypatch.setenv("PRAGMA_STATE_FLOCK_TIMEOUT_S", "1")
        with pytest.raises(StateLocked):
            write_state(dir_, _state("sha256:" + "d" * 64))
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
