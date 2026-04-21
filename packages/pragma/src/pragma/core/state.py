"""Machine-local gate state lives in `.pragma/state.json`.

The file is gitignored — committing it causes merge conflicts on every
long-running branch. The audit log (`.pragma/audit.jsonl`) is the
repo-wide evidence trail; state.json is just the local session cursor.

Writes are atomic (tempfile + fsync + os.replace) and flock-serialised
so two `pragma` processes cannot corrupt each other.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from pragma.core.errors import StateLocked, StateNotFound, StateSchemaError

_STATE_FILENAME = "state.json"
_LOCK_FILENAME = "state.json.lock"
_DEFAULT_FLOCK_TIMEOUT_S = 5.0


class SliceState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["pending", "in_progress", "shipped", "cancelled"]
    gate: Literal["LOCKED", "UNLOCKED"] | None
    activated_at: str | None = None
    unlocked_at: str | None = None
    completed_at: str | None = None


class LastTransition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event: str
    at: str
    reason: str
    from_gate: Literal["LOCKED", "UNLOCKED"] | None = None
    to_gate: Literal["LOCKED", "UNLOCKED"] | None = None
    slice: str | None = None


class State(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1]
    active_slice: str | None
    gate: Literal["LOCKED", "UNLOCKED"] | None
    manifest_hash: str = Field(min_length=len("sha256:") + 64)
    slices: dict[str, SliceState]
    last_transition: LastTransition | None

    @model_validator(mode="after")
    def _check_active_slice_coherence(self) -> State:
        if self.active_slice is None:
            if self.gate is not None:
                raise ValueError("gate must be null when no slice is active")
            return self
        if self.active_slice not in self.slices:
            raise ValueError(f"active_slice {self.active_slice!r} not in slices map")
        active = self.slices[self.active_slice]
        if active.gate != self.gate:
            raise ValueError(
                f"gate mismatch: top-level gate={self.gate} but "
                f"slices[{self.active_slice!r}].gate={active.gate}"
            )
        return self


def default_state(*, manifest_hash: str) -> State:
    """The initial state for a freshly-migrated repo: no slice active."""
    return State(
        version=1,
        active_slice=None,
        gate=None,
        manifest_hash=manifest_hash,
        slices={},
        last_transition=None,
    )


def read_state(pragma_dir: Path) -> State:
    path = pragma_dir / _STATE_FILENAME
    if not path.exists():
        raise StateNotFound(
            message=f".pragma/state.json not found at {path}",
            remediation=("Run `pragma slice activate <slice-id>` to create initial state."),
            context={"path": str(path)},
        )

    text = path.read_text(encoding="utf-8")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise StateSchemaError(
            message=f".pragma/state.json is not valid JSON: {exc}",
            remediation=("Delete the file; `pragma doctor` will recover from audit.jsonl."),
            context={"path": str(path)},
        ) from exc

    try:
        return State.model_validate(raw)
    except ValidationError as exc:
        raise StateSchemaError(
            message=(
                f".pragma/state.json schema invalid: {exc.errors(include_url=False)[0]['msg']}"
            ),
            remediation=("Delete the file and re-run `pragma slice activate ...`."),
            context={"path": str(path)},
        ) from exc


def write_state(pragma_dir: Path, state: State) -> None:
    """Atomic, flock-guarded write of state.json."""
    pragma_dir.mkdir(parents=True, exist_ok=True)
    lock_path = pragma_dir / _LOCK_FILENAME
    timeout = float(os.environ.get("PRAGMA_STATE_FLOCK_TIMEOUT_S", _DEFAULT_FLOCK_TIMEOUT_S))

    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                if time.monotonic() >= deadline:
                    raise StateLocked(
                        message=("Another pragma process is holding the state lock."),
                        remediation=(
                            "Wait for the other process to finish, or "
                            "remove "
                            f"{lock_path} if you are sure none is running."
                        ),
                        context={"path": str(lock_path)},
                    ) from None
                time.sleep(0.05)

        payload = state.model_dump_json(indent=2) + "\n"
        fd, tmp_name = tempfile.mkstemp(prefix=f"{_STATE_FILENAME}.tmp-", dir=str(pragma_dir))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, pragma_dir / _STATE_FILENAME)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
