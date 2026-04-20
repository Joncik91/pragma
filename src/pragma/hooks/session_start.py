from __future__ import annotations

from pathlib import Path

import yaml

from pragma.core.audit import append_audit, read_audit
from pragma.core.errors import StateNotFound
from pragma.core.integrity import verify_settings_integrity
from pragma.core.manifest import load_manifest, slice_requirements
from pragma.core.state import read_state

_MAX_CONTEXT = 9500
_VISION_TRIM = 800


def handle(event_input: dict, cwd: Path) -> dict:
    parts: list[str] = []

    settings_path = cwd / ".claude" / "settings.json"
    pragma_dir = cwd / ".pragma"
    yaml_path = cwd / "pragma.yaml"

    if settings_path.exists():
        integrity = verify_settings_integrity(settings_path, pragma_dir)
        if integrity is False:
            parts.append(
                "WARNING INTEGRITY: .claude/settings.json hash mismatch "
                "- file may have been tampered with outside Pragma."
            )
            if pragma_dir.exists():
                append_audit(
                    pragma_dir,
                    event="integrity_warning",
                    actor="hook:session-start",
                    slice=None,
                    from_state=None,
                    to_state=None,
                    reason="settings.json hash mismatch on session start",
                )

    if yaml_path.exists():
        try:
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("vision"):
                vision = str(raw["vision"])[:_VISION_TRIM]
                parts.append(f"## Vision\n{vision}")
        except Exception:
            pass

    try:
        state = read_state(pragma_dir)
        if state.active_slice:
            parts.append(f"## Active Slice: {state.active_slice}")
            parts.append(f"Gate: {state.gate or 'N/A'}")

            try:
                manifest = load_manifest(yaml_path)
                reqs = slice_requirements(manifest, state.active_slice)
                if reqs:
                    parts.append("### Requirements")
                    for req in reqs[:5]:
                        parts.append(f"- {req.id}: {req.title}")
                        for perm in req.permutations[:5]:
                            parts.append(
                                f"  - {perm.id}: {perm.description}"
                                f" (expected: {perm.expected})"
                            )
            except Exception:
                pass

            parts.append(f"## Rules-in-force: {state.gate or 'N/A'}")
            if state.gate == "LOCKED":
                parts.append(
                    "- Only files listed in requirement.touches may be edited."
                )
                parts.append("- Tests must exist before implementation.")
            elif state.gate == "UNLOCKED":
                parts.append("- All files editable. Tests expected to pass.")
    except StateNotFound:
        parts.append(
            "No active slice. Use `pragma slice activate <id>` to begin."
        )

    if pragma_dir.exists():
        try:
            audit = read_audit(pragma_dir)
            if audit:
                parts.append("## Recent Audit")
                for entry in audit[-3:]:
                    parts.append(
                        f"- [{entry.get('ts', '?')}] "
                        f"{entry.get('event', '?')}: "
                        f"{entry.get('reason', '?')}"
                    )
        except Exception:
            pass

    context = "\n".join(parts)
    if len(context) > _MAX_CONTEXT:
        context = context[:_MAX_CONTEXT]

    return {"continue": True, "additionalContext": context}
