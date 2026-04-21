from __future__ import annotations

from pathlib import Path

from pragma.core.integrity import (
    compute_settings_hash,
    read_stored_hash,
    verify_settings_integrity,
    write_stored_hash,
)


def test_compute_is_stable(tmp_path: Path) -> None:
    f = tmp_path / "settings.json"
    f.write_text('{"a": 1}\n', encoding="utf-8")
    h1 = compute_settings_hash(f)
    h2 = compute_settings_hash(f)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_compute_changes_with_content(tmp_path: Path) -> None:
    f = tmp_path / "settings.json"
    f.write_text('{"a": 1}\n', encoding="utf-8")
    h1 = compute_settings_hash(f)
    f.write_text('{"a": 2}\n', encoding="utf-8")
    assert compute_settings_hash(f) != h1


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    pragma_dir = tmp_path / ".pragma"
    pragma_dir.mkdir()
    write_stored_hash(pragma_dir, "sha256:" + "a" * 64)
    assert read_stored_hash(pragma_dir) == "sha256:" + "a" * 64


def test_read_missing_returns_none(tmp_path: Path) -> None:
    pragma_dir = tmp_path / ".pragma"
    pragma_dir.mkdir()
    assert read_stored_hash(pragma_dir) is None


def test_verify_matches(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text("{}\n", encoding="utf-8")
    pragma_dir = tmp_path / ".pragma"
    pragma_dir.mkdir()
    write_stored_hash(pragma_dir, compute_settings_hash(settings))
    assert verify_settings_integrity(settings, pragma_dir) is True


def test_verify_mismatch(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text("{}\n", encoding="utf-8")
    pragma_dir = tmp_path / ".pragma"
    pragma_dir.mkdir()
    write_stored_hash(pragma_dir, "sha256:" + "0" * 64)
    assert verify_settings_integrity(settings, pragma_dir) is False


def test_verify_returns_none_when_hash_missing(tmp_path: Path) -> None:
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text("{}\n", encoding="utf-8")
    pragma_dir = tmp_path / ".pragma"
    pragma_dir.mkdir()
    assert verify_settings_integrity(settings, pragma_dir) is None
