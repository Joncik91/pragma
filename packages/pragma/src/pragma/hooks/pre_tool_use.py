from __future__ import annotations

from pathlib import Path
from typing import Any

from pragma_sdk import trace

from pragma.core.errors import StateNotFound
from pragma.core.manifest import load_manifest, slice_requirements
from pragma.core.models import Requirement
from pragma.core.state import read_state
from pragma.core.tests_discovery import expected_test_name

_ALLOW = {"permissionDecision": "allow"}


def _deny_locked(slice_id: str, reqs: list[Requirement]) -> dict[str, Any]:
    test_names = [expected_test_name(r.id, p.id) for r in reqs for p in r.permutations]
    return {
        "permissionDecision": "deny",
        "permissionDecisionReason": f"Gate is LOCKED for slice {slice_id}",
        "remediation": (
            f"Slice {slice_id} is LOCKED. "
            "Write passing tests first, then run `pragma unlock`. "
            f"Expected tests: {', '.join(test_names)}"
        ),
    }


def _deny_not_in_touches(file_path: str, slice_id: str, all_touches: set[str]) -> dict[str, Any]:
    return {
        "permissionDecision": "deny",
        "permissionDecisionReason": f"File not in touches for slice {slice_id}",
        "remediation": (
            f"File {file_path} is not in the touches list for active slice "
            f"{slice_id}. Allowed files: {', '.join(sorted(all_touches))}"
        ),
    }


def _is_in_touches(cwd: Path, file_path: str, touches: set[str]) -> bool:
    resolved = str((cwd / file_path).resolve())
    return any(
        resolved == str((cwd / t).resolve()) or resolved.startswith(str((cwd / t).resolve()))
        for t in touches
    )


@trace("REQ-004")
def handle(event_input: dict[str, Any], cwd: Path) -> dict[str, Any]:
    file_path = event_input.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return _ALLOW

    try:
        state = read_state(cwd / ".pragma")
    except StateNotFound:
        return _ALLOW
    if state.active_slice is None:
        return _ALLOW

    manifest = load_manifest(cwd / "pragma.yaml")
    source_root = manifest.project.source_root.rstrip("/")
    if not file_path.startswith(source_root + "/") and file_path != source_root:
        return _ALLOW

    reqs = slice_requirements(manifest, state.active_slice)
    if state.gate == "LOCKED":
        return _deny_locked(state.active_slice, reqs)

    all_touches: set[str] = {t for req in reqs for t in req.touches}
    if not _is_in_touches(cwd, file_path, all_touches):
        return _deny_not_in_touches(file_path, state.active_slice, all_touches)
    return _ALLOW
