"""Recovery-engine for `pragma doctor`.

v1.0 of ``pragma doctor`` is a real recovery tool rather than a stub.
``diagnose(cwd)`` walks the project tree, classifies each failure mode,
and returns a deterministic list of diagnostic dicts that doctor renders
into its JSON payload. The same function is the test target for the
eight branches in spec §7.8.6.

Fatal diagnostics short-circuit: if a fatal branch fires, it's returned
as the only entry. Warn diagnostics coexist and sort by ``code`` so the
output is byte-stable.

``diagnose`` NEVER raises. Any filesystem read that fails is folded
into the relevant classification branch (e.g. an unparseable lockfile
becomes ``lockfile_unparseable`` rather than a ``JSONDecodeError``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from pragma.core.integrity import verify_settings_integrity
from pragma.core.manifest import hash_manifest, load_manifest


def _canonical_manifest_hash(manifest_path: Path) -> str | None:
    """Return the canonical sha256 of the manifest, or None if unreadable.

    Uses the same ``hash_manifest`` pipeline as ``pragma freeze`` so the
    comparison with ``lock.manifest_hash`` is meaningful byte-for-byte.
    Any error (missing file, bad YAML, schema violation) collapses to
    None — the caller classifies that as hash_mismatch.
    """
    try:
        manifest = load_manifest(manifest_path)
    except Exception:
        return None
    try:
        return hash_manifest(manifest)
    except Exception:
        return None


def _manifest_hash_from_lock(lock_path: Path) -> str | None:
    """Return ``lock.manifest_hash`` if readable; else None.

    Swallows every filesystem / JSON error — the caller uses the None
    signal to raise an ``lockfile_unparseable`` diagnostic instead.
    """
    try:
        raw = lock_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    value = parsed.get("manifest_hash")
    if not isinstance(value, str) or not value:
        return None
    return value


def _state_has_slices(state_path: Path) -> bool | None:
    """Return True if state.json has a non-empty slices dict.

    None means the file exists but is unparseable — treat it the same as
    "no useful state", i.e. the caller will look at audit.jsonl for an
    orphan signal.
    """
    try:
        raw = state_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    slices = parsed.get("slices")
    if not isinstance(slices, dict):
        return False
    return len(slices) > 0


def _state_manifest_hash(state_path: Path) -> str | None:
    try:
        raw = state_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    value = parsed.get("manifest_hash")
    if not isinstance(value, str) or not value:
        return None
    return value


_SLICE_TRANSITION_EVENTS = frozenset(
    {
        "slice_activated",
        "slice_completed",
        "slice_cancelled",
        "unlocked",
        "emergency_unlock",
    }
)


def _audit_has_slice_transitions(audit_path: Path) -> bool:
    """True iff audit.jsonl has at least one slice-lifecycle event.

    BUG-030 / REQ-029: events like hooks_seal and spans_cleaned are
    metadata; they populate audit.jsonl without creating slice
    history. They must not trip audit_orphan — that diagnostic exists
    to catch nuked slice state, not nuked metadata.
    """
    try:
        raw = audit_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if obj.get("event") in _SLICE_TRANSITION_EVENTS:
            return True
    return False


def _diag_no_manifest(manifest_path: Path) -> dict[str, object]:
    return {
        "code": "no_manifest",
        "severity": "fatal",
        "message": "pragma.yaml is missing from this directory.",
        "remediation": (
            "Run `pragma init --brownfield` to scaffold an existing "
            "repo, or `pragma init --greenfield --name <name>` for a "
            "new one."
        ),
        "context": {"path": str(manifest_path)},
    }


def _diag_no_lock(lock_path: Path) -> dict[str, object]:
    return {
        "code": "no_lock",
        "severity": "fatal",
        "message": "pragma.yaml exists but pragma.lock.json is missing.",
        "remediation": "Run `pragma freeze` to regenerate the lock file.",
        "context": {"path": str(lock_path)},
    }


def _diag_lockfile_unparseable(lock_path: Path) -> dict[str, object]:
    return {
        "code": "lockfile_unparseable",
        "severity": "fatal",
        "message": "pragma.lock.json is not valid JSON or is missing `manifest_hash`.",
        "remediation": "Run `pragma freeze` to regenerate.",
        "context": {"path": str(lock_path)},
    }


def _diag_hash_mismatch(manifest_hash: str | None, lock_hash: str) -> dict[str, object]:
    unreadable = manifest_hash is None
    return {
        "code": "hash_mismatch",
        "severity": "fatal",
        "message": (
            "pragma.yaml could not be parsed / hashed; cannot confirm it matches pragma.lock.json."
            if unreadable
            else "pragma.yaml has drifted from pragma.lock.json "
            "(canonical hash does not match the hash stored in the lock)."
        ),
        "remediation": (
            "Run `pragma freeze` if the manifest edit was intentional, "
            "otherwise `git restore pragma.yaml pragma.lock.json`."
        ),
        "context": {
            "manifest_hash": "<unreadable>" if unreadable else manifest_hash,
            "lock_manifest_hash": lock_hash,
        },
    }


def _check_fatal(
    manifest_path: Path, lock_path: Path
) -> tuple[list[dict[str, object]], str | None]:
    """Run the four fatal classifiers in order.

    Returns ``(diagnostics, lock_hash)``. ``diagnostics`` is either
    empty (no fatal branch fired, and ``lock_hash`` is set to the valid
    lock's manifest_hash) or a one-element list (a fatal branch fired,
    and the caller should return it directly).
    """
    if not manifest_path.exists():
        return [_diag_no_manifest(manifest_path)], None
    if not lock_path.exists():
        return [_diag_no_lock(lock_path)], None
    lock_hash = _manifest_hash_from_lock(lock_path)
    if lock_hash is None:
        return [_diag_lockfile_unparseable(lock_path)], None
    manifest_hash = _canonical_manifest_hash(manifest_path)
    if manifest_hash is None or manifest_hash != lock_hash:
        return [_diag_hash_mismatch(manifest_hash, lock_hash)], None
    return [], lock_hash


def _check_stale_state(state_path: Path, lock_hash: str) -> dict[str, object] | None:
    if not state_path.exists():
        return None
    state_hash = _state_manifest_hash(state_path)
    if state_hash is None or state_hash == lock_hash:
        return None
    return {
        "code": "stale_state",
        "severity": "warn",
        "message": (
            ".pragma/state.json references a manifest_hash that no longer matches the lockfile."
        ),
        "remediation": (
            "Run `pragma freeze`. If the active slice should remain, "
            "re-activate it after: `pragma slice activate <id>`."
        ),
        "context": {
            "state_manifest_hash": state_hash,
            "lock_manifest_hash": lock_hash,
        },
    }


def _check_settings_mismatch(settings_path: Path, pragma_dir: Path) -> dict[str, object] | None:
    if not settings_path.exists():
        return None
    if verify_settings_integrity(settings_path, pragma_dir) is not False:
        return None
    return {
        "code": "claude_settings_mismatch",
        "severity": "warn",
        "message": (
            ".claude/settings.json hash differs from the value stored in "
            ".pragma/claude-settings.hash."
        ),
        "remediation": (
            "Review diff with `git diff .claude/settings.json` then "
            "`pragma init --force` to restamp."
        ),
        "context": {
            "settings_path": str(settings_path),
            "hash_path": str(pragma_dir / "claude-settings.hash"),
        },
    }


def _check_audit_orphan(audit_path: Path, state_path: Path) -> dict[str, object] | None:
    if not _audit_has_slice_transitions(audit_path):
        return None
    state_has_slices = False if not state_path.exists() else _state_has_slices(state_path)
    if state_has_slices:
        return None
    return {
        "code": "audit_orphan",
        "severity": "warn",
        "message": (
            ".pragma/audit.jsonl has entries but .pragma/state.json is "
            "missing or empty — prior slice state was nuked while "
            "keeping the evidence trail."
        ),
        "remediation": (
            "Run `pragma doctor --emergency-unlock --reason "
            '"recovered from audit orphan"` to reset cleanly, or '
            "manually reconstruct state from audit.jsonl."
        ),
        "context": {
            "audit_path": str(audit_path),
            "state_path": str(state_path),
        },
    }


def diagnose(cwd: Path) -> list[dict[str, object]]:
    """Classify the Pragma-project state at ``cwd`` into diagnostics.

    Returns a deterministic list of diagnostic dicts:

        {
            "code": <stable-id>,
            "severity": "warn" | "fatal",
            "message": <one-line>,
            "remediation": <exact-command>,
            "context": {<key facts>},
        }

    If any fatal branch fires, ONLY that fatal diagnostic is returned
    (fail-fast — the user needs to fix it before any warn-level advice
    matters). Warn diagnostics coexist and sort by ``code``.

    Never raises: any file-read / parse error gets reclassified as the
    appropriate branch (e.g. a broken lockfile becomes
    ``lockfile_unparseable``).
    """
    manifest_path = cwd / "pragma.yaml"
    lock_path = cwd / "pragma.lock.json"
    pragma_dir = cwd / ".pragma"
    state_path = pragma_dir / "state.json"
    audit_path = pragma_dir / "audit.jsonl"
    settings_path = cwd / ".claude" / "settings.json"

    fatal, lock_hash = _check_fatal(manifest_path, lock_path)
    if fatal:
        return fatal
    assert lock_hash is not None  # invariant of _check_fatal returning []

    warnings: list[dict[str, object]] = []

    if not pragma_dir.exists():
        warnings.append(
            {
                "code": "no_pragma_dir",
                "severity": "warn",
                "message": (".pragma/ directory is missing (audit log + state cannot be written)."),
                "remediation": (
                    "Run `pragma freeze` (it recreates .pragma/ alongside regenerating the lock)."
                ),
                "context": {"path": str(pragma_dir)},
            }
        )

    for checker in (
        _check_stale_state(state_path, lock_hash),
        _check_settings_mismatch(settings_path, pragma_dir),
        _check_audit_orphan(audit_path, state_path),
    ):
        if checker is not None:
            warnings.append(checker)

    warnings.sort(key=lambda d: cast(str, d["code"]))
    return warnings
