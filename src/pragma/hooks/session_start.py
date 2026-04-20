from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import yaml

from pragma.core.audit import append_audit, read_audit
from pragma.core.errors import StateNotFound
from pragma.core.integrity import verify_settings_integrity
from pragma.core.manifest import load_manifest, slice_requirements
from pragma.core.state import State, read_state

_MAX_CONTEXT = 9500
_VISION_TRIM = 800
_TRUNC_SUFFIX = "\n…see `pragma slice status` for full details"


def _integrity_section(cwd: Path) -> list[str]:
    settings_path = cwd / ".claude" / "settings.json"
    pragma_dir = cwd / ".pragma"
    if not settings_path.exists():
        return []
    integrity = verify_settings_integrity(settings_path, pragma_dir)
    if integrity is not False:
        return []
    parts = [
        "WARNING INTEGRITY: .claude/settings.json hash mismatch "
        "- file may have been tampered with outside Pragma."
    ]
    if pragma_dir.exists():
        with contextlib.suppress(OSError):
            append_audit(
                pragma_dir,
                event="integrity_warning",
                actor="hook:session-start",
                slice=None,
                from_state=None,
                to_state=None,
                reason="settings.json hash mismatch on session start",
            )
    return parts


def _vision_section(yaml_path: Path) -> list[str]:
    if not yaml_path.exists():
        return []
    with contextlib.suppress(yaml.YAMLError, OSError):
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and raw.get("vision"):
            vision = str(raw["vision"])[:_VISION_TRIM]
            return [f"## Vision\n{vision}"]
    return []


def _requirements_section(yaml_path: Path, active_slice: str) -> list[str]:
    parts: list[str] = []
    with contextlib.suppress(Exception):
        manifest = load_manifest(yaml_path)
        reqs = slice_requirements(manifest, active_slice)
        if reqs:
            parts.append("### Requirements")
            for req in reqs[:5]:
                parts.append(f"- {req.id}: {req.title}")
                for perm in req.permutations[:5]:
                    parts.append(f"  - {perm.id}: {perm.description} (expected: {perm.expected})")
    return parts


def _rules_section(state: State) -> list[str]:
    parts = [f"## Rules-in-force: {state.gate or 'N/A'}"]
    if state.gate == "LOCKED":
        parts.append("- Only files listed in requirement.touches may be edited.")
        parts.append("- Tests must exist before implementation.")
    elif state.gate == "UNLOCKED":
        parts.append("- All files editable. Tests expected to pass.")
    return parts


def _slice_sections(yaml_path: Path, pragma_dir: Path) -> list[str]:
    try:
        state = read_state(pragma_dir)
    except StateNotFound:
        return ["No active slice. Use `pragma slice activate <id>` to begin."]
    if state.active_slice is None:
        return ["No active slice. Use `pragma slice activate <id>` to begin."]
    parts = [
        f"## Active Slice: {state.active_slice}",
        f"Gate: {state.gate or 'N/A'}",
        *_requirements_section(yaml_path, state.active_slice),
        *_rules_section(state),
    ]
    return parts


def _audit_section(pragma_dir: Path) -> list[str]:
    if not pragma_dir.exists():
        return []
    with contextlib.suppress(Exception):
        audit = read_audit(pragma_dir)
        if audit:
            parts = ["## Recent Audit"]
            for entry in audit[-3:]:
                parts.append(
                    f"- [{entry.get('ts', '?')}] "
                    f"{entry.get('event', '?')}: "
                    f"{entry.get('reason', '?')}"
                )
            return parts
    return []


def handle(event_input: dict[str, Any], cwd: Path) -> dict[str, Any]:
    yaml_path = cwd / "pragma.yaml"
    pragma_dir = cwd / ".pragma"

    parts: list[str] = [
        *_integrity_section(cwd),
        *_vision_section(yaml_path),
        *_slice_sections(yaml_path, pragma_dir),
        *_audit_section(pragma_dir),
    ]

    context = "\n".join(parts)
    if len(context) > _MAX_CONTEXT:
        budget = _MAX_CONTEXT - len(_TRUNC_SUFFIX)
        context = context[:budget].rstrip() + _TRUNC_SUFFIX

    return {"continue": True, "additionalContext": context}
