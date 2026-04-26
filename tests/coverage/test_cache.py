"""Tests for the tier-2 SQLite cache layer."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pragma.coverage.cache import MISS, content_hash, lookup, store
from pragma.verdict import Verdict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HASH_A = "aabbccdd" * 8
_HASH_B = "11223344" * 8
_HASH_C = "deadbeef" * 8
_SYMBOL = "mymodule.MyClass.my_method"

_VERDICT = Verdict(kind="python.tautological", evidence="assert True", test_name="test_foo")


def _fake_git_root(tmp_path: Path) -> None:
    """Create a .git marker so _find_repo_root() resolves to tmp_path."""
    (tmp_path / ".git").mkdir()


# ---------------------------------------------------------------------------
# Round-trip: store a Verdict and get it back
# ---------------------------------------------------------------------------


def test_round_trip_verdict(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)

    store(_HASH_A, _HASH_B, _SYMBOL, _VERDICT)
    result = lookup(_HASH_A, _HASH_B, _SYMBOL)

    assert result == _VERDICT


# ---------------------------------------------------------------------------
# Round-trip: store None (covered, no verdict) and get None back
# ---------------------------------------------------------------------------


def test_round_trip_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)

    store(_HASH_A, _HASH_B, _SYMBOL, None)
    result = lookup(_HASH_A, _HASH_B, _SYMBOL)

    assert result is None


# ---------------------------------------------------------------------------
# Unknown key → MISS sentinel
# ---------------------------------------------------------------------------


def test_miss_for_unknown_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)

    result = lookup(_HASH_A, _HASH_B, _SYMBOL)

    assert result is MISS


# ---------------------------------------------------------------------------
# Keys are independent — different triples don't collide
# ---------------------------------------------------------------------------


def test_keys_are_independent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)

    v1 = Verdict(kind="python.tautological", evidence="ev1", test_name="t1")
    v2 = Verdict(kind="python.assertion_free", evidence="ev2", test_name="t2")

    store(_HASH_A, _HASH_B, "symbol.one", v1)
    store(_HASH_A, _HASH_B, "symbol.two", v2)

    assert lookup(_HASH_A, _HASH_B, "symbol.one") == v1
    assert lookup(_HASH_A, _HASH_B, "symbol.two") == v2
    assert lookup(_HASH_A, _HASH_C, "symbol.one") is MISS


# ---------------------------------------------------------------------------
# INSERT OR REPLACE: re-store same key updates, no duplicates
# ---------------------------------------------------------------------------


def test_re_store_updates_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)

    v1 = Verdict(kind="python.tautological", evidence="old", test_name="t1")
    v2 = Verdict(kind="python.assertion_free", evidence="new", test_name="t2")

    store(_HASH_A, _HASH_B, _SYMBOL, v1)
    store(_HASH_A, _HASH_B, _SYMBOL, v2)
    result = lookup(_HASH_A, _HASH_B, _SYMBOL)

    assert result == v2

    # Confirm no duplicate rows
    import sqlite3

    db = tmp_path / ".pragma" / "cache.db"
    conn = sqlite3.connect(str(db))
    count = conn.execute("SELECT COUNT(*) FROM tier2_cache").fetchone()[0]
    conn.close()
    assert count == 1


# ---------------------------------------------------------------------------
# PRAGMA_NO_CACHE=1 disables both lookup and store
# ---------------------------------------------------------------------------


def test_no_cache_env_disables_lookup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)
    # Store something first (without env var)
    store(_HASH_A, _HASH_B, _SYMBOL, _VERDICT)

    monkeypatch.setenv("PRAGMA_NO_CACHE", "1")
    result = lookup(_HASH_A, _HASH_B, _SYMBOL)

    assert result is MISS


def test_no_cache_env_disables_store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)
    monkeypatch.setenv("PRAGMA_NO_CACHE", "1")

    store(_HASH_A, _HASH_B, _SYMBOL, _VERDICT)

    # DB should not have been created
    assert not (tmp_path / ".pragma" / "cache.db").exists()

    # lookup (without PRAGMA_NO_CACHE) should still return MISS
    monkeypatch.delenv("PRAGMA_NO_CACHE")
    assert lookup(_HASH_A, _HASH_B, _SYMBOL) is MISS


# ---------------------------------------------------------------------------
# Corrupt DB self-heals: write garbage, lookup returns MISS and removes file
# ---------------------------------------------------------------------------


def test_corrupt_db_self_heals(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)

    pragma_dir = tmp_path / ".pragma"
    pragma_dir.mkdir()
    db = pragma_dir / "cache.db"
    db.write_bytes(b"THIS IS NOT A SQLITE FILE\x00\xff\xfe")

    result = lookup(_HASH_A, _HASH_B, _SYMBOL)

    assert result is MISS
    # Self-healing: corrupt file should be removed
    assert not db.exists()


# ---------------------------------------------------------------------------
# DB + .pragma/ created on first store
# ---------------------------------------------------------------------------


def test_db_created_on_first_store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)

    assert not (tmp_path / ".pragma").exists()

    store(_HASH_A, _HASH_B, _SYMBOL, _VERDICT)

    assert (tmp_path / ".pragma").is_dir()
    assert (tmp_path / ".pragma" / "cache.db").is_file()


# ---------------------------------------------------------------------------
# .gitignore gets .pragma/ line appended when .gitignore exists
# ---------------------------------------------------------------------------


def test_gitignore_gets_pragma_line(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)
    gi = tmp_path / ".gitignore"
    gi.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")

    store(_HASH_A, _HASH_B, _SYMBOL, _VERDICT)

    content = gi.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in content.splitlines()]
    assert ".pragma/" in lines


# ---------------------------------------------------------------------------
# .gitignore not created when it doesn't exist
# ---------------------------------------------------------------------------


def test_gitignore_not_created_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)
    gi = tmp_path / ".gitignore"
    assert not gi.exists()

    store(_HASH_A, _HASH_B, _SYMBOL, _VERDICT)

    assert not gi.exists()


# ---------------------------------------------------------------------------
# .gitignore already contains .pragma/ — no double-append
# ---------------------------------------------------------------------------


def test_gitignore_no_double_append(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fake_git_root(tmp_path)
    gi = tmp_path / ".gitignore"
    gi.write_text("*.pyc\n.pragma/\n", encoding="utf-8")

    store(_HASH_A, _HASH_B, _SYMBOL, _VERDICT)

    content = gi.read_text(encoding="utf-8")
    assert content.count(".pragma/") == 1


# ---------------------------------------------------------------------------
# content_hash helper
# ---------------------------------------------------------------------------


def test_content_hash_returns_sha256(tmp_path):
    f = tmp_path / "sample.py"
    f.write_bytes(b"hello world")

    result = content_hash(f)

    expected = hashlib.sha256(b"hello world").hexdigest()
    assert result == expected


def test_content_hash_different_files_differ(tmp_path):
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_bytes(b"content one")
    f2.write_bytes(b"content two")

    assert content_hash(f1) != content_hash(f2)


def test_content_hash_same_content_same_hash(tmp_path):
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_bytes(b"same content")
    f2.write_bytes(b"same content")

    assert content_hash(f1) == content_hash(f2)
