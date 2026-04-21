"""Dogfood test: Pragma's own pragma.yaml + pragma.lock.json are valid."""

from __future__ import annotations

from pathlib import Path

from pragma.core.lockfile import read_lock
from pragma.core.manifest import hash_manifest, load_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_pragma_has_its_own_manifest() -> None:
    assert (REPO_ROOT / "pragma.yaml").exists()
    assert (REPO_ROOT / "pragma.lock.json").exists()


def test_pragma_own_manifest_is_schema_valid() -> None:
    m = load_manifest(REPO_ROOT / "pragma.yaml")
    assert m.project.name == "pragma"
    assert m.project.mode == "brownfield"
    assert len(m.requirements) >= 2


def test_pragma_own_lock_matches_manifest_hash() -> None:
    m = load_manifest(REPO_ROOT / "pragma.yaml")
    lock = read_lock(REPO_ROOT / "pragma.lock.json")
    assert lock.manifest_hash == hash_manifest(
        m
    ), "Pragma's own lock is stale — run `pragma freeze` and commit."
