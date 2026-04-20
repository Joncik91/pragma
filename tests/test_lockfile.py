"""Tests for core/lockfile.py — pragma.lock.json read/write + roundtrip."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pragma.core.errors import LockNotFound, ManifestSchemaError
from pragma.core.lockfile import LockFile, read_lock, write_lock
from pragma.core.manifest import load_manifest


def test_write_lock_creates_file_with_expected_envelope(
    tmp_project: Path, minimal_valid_yaml: str
) -> None:
    yaml_path = tmp_project / "pragma.yaml"
    yaml_path.write_text(minimal_valid_yaml)
    lock_path = tmp_project / "pragma.lock.json"

    manifest = load_manifest(yaml_path)
    write_lock(lock_path, manifest, now_iso="2026-04-20T14:30:00Z")

    assert lock_path.exists()
    raw = json.loads(lock_path.read_text())
    assert raw["version"] == "1"
    assert raw["manifest_hash"].startswith("sha256:")
    assert raw["generated_at"] == "2026-04-20T14:30:00Z"
    assert raw["manifest"]["project"]["name"] == "example"


def test_read_lock_returns_typed_lockfile(
    tmp_project: Path, minimal_valid_yaml: str
) -> None:
    yaml_path = tmp_project / "pragma.yaml"
    yaml_path.write_text(minimal_valid_yaml)
    lock_path = tmp_project / "pragma.lock.json"

    write_lock(lock_path, load_manifest(yaml_path), now_iso="2026-04-20T14:30:00Z")
    lock = read_lock(lock_path)

    assert isinstance(lock, LockFile)
    assert lock.version == "1"
    assert lock.manifest_hash.startswith("sha256:")


def test_read_missing_lock_raises_typed_error(tmp_project: Path) -> None:
    with pytest.raises(LockNotFound) as exc_info:
        read_lock(tmp_project / "pragma.lock.json")
    assert "pragma freeze" in exc_info.value.remediation


def test_read_malformed_lock_raises_schema_error(tmp_project: Path) -> None:
    (tmp_project / "pragma.lock.json").write_text('{"not": "valid lock"}')
    with pytest.raises(ManifestSchemaError):
        read_lock(tmp_project / "pragma.lock.json")


def test_write_is_atomic_temp_then_rename(
    tmp_project: Path, minimal_valid_yaml: str
) -> None:
    """write_lock must never leave a half-written file on disk."""
    yaml_path = tmp_project / "pragma.yaml"
    yaml_path.write_text(minimal_valid_yaml)
    lock_path = tmp_project / "pragma.lock.json"

    write_lock(lock_path, load_manifest(yaml_path), now_iso="2026-04-20T14:30:00Z")

    # After a successful write, no stray .tmp files should remain.
    stray = list(tmp_project.glob("pragma.lock.json.tmp*"))
    assert stray == []


def test_lock_roundtrip_is_stable(tmp_project: Path, minimal_valid_yaml: str) -> None:
    yaml_path = tmp_project / "pragma.yaml"
    yaml_path.write_text(minimal_valid_yaml)
    lock_path = tmp_project / "pragma.lock.json"

    manifest = load_manifest(yaml_path)
    write_lock(lock_path, manifest, now_iso="2026-04-20T14:30:00Z")

    lock = read_lock(lock_path)
    assert lock.manifest.project.name == manifest.project.name
    assert len(lock.manifest.requirements) == len(manifest.requirements)
