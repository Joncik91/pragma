"""Dogfood tests for REQ-002 — manifest + lockfile round-trip determinism."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pragma_sdk import set_permutation

from pragma.core.errors import ManifestSchemaError
from pragma.core.lockfile import read_lock, write_lock
from pragma.core.manifest import hash_manifest, load_manifest


def _write_min_manifest(path: Path, *, name: str = "demo") -> None:
    path.write_text(
        (
            "version: '2'\n"
            "project:\n"
            f"  name: {name}\n"
            "  mode: brownfield\n"
            "  language: python\n"
            "  source_root: src/\n"
            "  tests_root: tests/\n"
            "requirements: []\n"
            "milestones: []\n"
        ),
        encoding="utf-8",
    )


def test_req_002_hash_stable(tmp_path: Path) -> None:
    _write_min_manifest(tmp_path / "pragma.yaml")
    with set_permutation("hash_stable"):
        m1 = load_manifest(tmp_path / "pragma.yaml")
        m2 = load_manifest(tmp_path / "pragma.yaml")
        assert hash_manifest(m1) == hash_manifest(m2)


def test_req_002_hash_changes(tmp_path: Path) -> None:
    yaml_path = tmp_path / "pragma.yaml"
    _write_min_manifest(yaml_path, name="alpha")
    with set_permutation("hash_changes"):
        h1 = hash_manifest(load_manifest(yaml_path))
        _write_min_manifest(yaml_path, name="beta")
        h2 = hash_manifest(load_manifest(yaml_path))
    assert h1 != h2


def test_req_002_write_atomic(tmp_path: Path) -> None:
    _write_min_manifest(tmp_path / "pragma.yaml")
    lock_path = tmp_path / "pragma.lock.json"
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with set_permutation("write_atomic"):
        write_lock(lock_path, load_manifest(tmp_path / "pragma.yaml"), now_iso=now)
    assert lock_path.exists()
    # No leftover tempfiles — atomicity contract.
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith("pragma.lock.json.tmp-")]
    assert leftovers == []


def test_req_002_read_malformed(tmp_path: Path) -> None:
    bad = tmp_path / "pragma.lock.json"
    bad.write_text("{not valid json", encoding="utf-8")
    with set_permutation("read_malformed"), pytest.raises(ManifestSchemaError):
        read_lock(bad)
