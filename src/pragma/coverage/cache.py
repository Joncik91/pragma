"""SQLite cache for tier-2 results, keyed by content hashes.

The expensive part of tier 2 is `run_python_with_coverage` / `run_vitest_with_coverage`
— pytest spin-up alone is 200ms+. We cache the verdict outcome by
`sha256(test_contents) || sha256(target_contents) || target_symbol`
so a re-edit that doesn't change either file is a sub-100ms cache hit.

Cache lives at `.pragma/cache.db` (auto-gitignored on first hook run).
Bypass via `PRAGMA_NO_CACHE=1` env var.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import sqlite3
import time
from pathlib import Path

from pragma.verdict import Verdict

# Sentinel returned by lookup when the cache has no entry for the key.
MISS: object = object()

_SCHEMA_VERSION = 1
_GITIGNORE_LINE = ".pragma/"


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------


def content_hash(path: Path) -> str:
    """Return the sha256 hex-digest of the file at *path*."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cache_disabled() -> bool:
    return os.environ.get("PRAGMA_NO_CACHE") == "1"


def _find_repo_root() -> Path:
    """Walk up from cwd looking for .git or pyproject.toml; fallback to cwd."""
    current = Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent
    return current


def _cache_db_path() -> Path:
    return _find_repo_root() / ".pragma" / "cache.db"


def _ensure_gitignored(repo_root: Path) -> None:
    """If .gitignore exists and doesn't list .pragma/, append it."""
    gi = repo_root / ".gitignore"
    if not gi.exists():
        return
    try:
        content = gi.read_text(encoding="utf-8")
    except Exception:
        return
    lines = {ln.strip() for ln in content.splitlines()}
    if _GITIGNORE_LINE in lines or ".pragma" in lines:
        return
    try:
        with gi.open("a", encoding="utf-8") as f:
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write(f"{_GITIGNORE_LINE}\n")
    except Exception:
        return


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tier2_cache (
            test_hash TEXT NOT NULL,
            target_hash TEXT NOT NULL,
            target_symbol TEXT NOT NULL,
            verdict_kind TEXT,
            verdict_evidence TEXT,
            verdict_test_name TEXT,
            created_at REAL NOT NULL,
            PRIMARY KEY (test_hash, target_hash, target_symbol)
        );
        CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
        (_SCHEMA_VERSION,),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def lookup(test_hash: str, target_hash: str, target_symbol: str) -> Verdict | None | object:
    """Return the cached Verdict, None for 'covered (no verdict)', or the
    sentinel `MISS` when the cache hasn't seen this combination."""
    if _cache_disabled():
        return MISS

    db = _cache_db_path()
    if not db.exists():
        return MISS

    try:
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                "SELECT verdict_kind, verdict_evidence, verdict_test_name "
                "FROM tier2_cache WHERE test_hash=? AND target_hash=? AND target_symbol=?",
                (test_hash, target_hash, target_symbol),
            ).fetchone()
        finally:
            conn.close()
    except Exception:
        # Self-heal corrupt DB.
        with contextlib.suppress(Exception):
            db.unlink(missing_ok=True)
        return MISS

    if row is None:
        return MISS

    kind, evidence, name = row
    if kind is None:
        return None
    return Verdict(kind=kind, evidence=evidence or "", test_name=name or "")


def store(
    test_hash: str,
    target_hash: str,
    target_symbol: str,
    verdict: Verdict | None,
) -> None:
    """Persist the tier-2 outcome. None means 'covered, no verdict'."""
    if _cache_disabled():
        return

    repo_root = _find_repo_root()
    db = repo_root / ".pragma" / "cache.db"
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
        _ensure_gitignored(repo_root)
        conn = sqlite3.connect(str(db))
        try:
            _init_schema(conn)
            conn.execute(
                "INSERT OR REPLACE INTO tier2_cache "
                "(test_hash, target_hash, target_symbol, verdict_kind, "
                "verdict_evidence, verdict_test_name, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    test_hash,
                    target_hash,
                    target_symbol,
                    verdict.kind if verdict is not None else None,
                    verdict.evidence if verdict is not None else None,
                    verdict.test_name if verdict is not None else None,
                    time.time(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        return
