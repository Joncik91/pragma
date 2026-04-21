from __future__ import annotations

import contextlib
import hashlib
import os
import tempfile
from pathlib import Path

_HASH_FILENAME = "claude-settings.hash"


def compute_settings_hash(settings_path: Path) -> str:
    raw = settings_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    return f"sha256:{digest}"


def read_stored_hash(pragma_dir: Path) -> str | None:
    path = pragma_dir / _HASH_FILENAME
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def write_stored_hash(pragma_dir: Path, hash_value: str) -> None:
    pragma_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f"{_HASH_FILENAME}.tmp-", dir=str(pragma_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(hash_value)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, pragma_dir / _HASH_FILENAME)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def verify_settings_integrity(settings_path: Path, pragma_dir: Path) -> bool | None:
    stored = read_stored_hash(pragma_dir)
    if stored is None:
        return None
    current = compute_settings_hash(settings_path)
    return current == stored
