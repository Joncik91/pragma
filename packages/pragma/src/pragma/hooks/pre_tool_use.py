from __future__ import annotations

from pathlib import Path
from typing import Any

from pragma_sdk import trace

from pragma.core.errors import StateNotFound
from pragma.core.manifest import load_manifest, slice_requirements
from pragma.core.state import read_state
from pragma.core.tests_discovery import expected_test_name


@trace("REQ-004")
def handle(event_input: dict[str, Any], cwd: Path) -> dict[str, Any]:
    file_path = event_input.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return {"permissionDecision": "allow"}

    pragma_dir = cwd / ".pragma"

    try:
        state = read_state(pragma_dir)
    except StateNotFound:
        return {"permissionDecision": "allow"}

    if state.active_slice is None:
        return {"permissionDecision": "allow"}

    manifest_path = cwd / "pragma.yaml"
    manifest = load_manifest(manifest_path)
    source_root = manifest.project.source_root.rstrip("/")
    if not file_path.startswith(source_root + "/") and file_path != source_root:
        return {"permissionDecision": "allow"}

    reqs = slice_requirements(manifest, state.active_slice)

    if state.gate == "LOCKED":
        test_names = []
        for req in reqs:
            for perm in req.permutations:
                test_names.append(expected_test_name(req.id, perm.id))
        remediation = (
            f"Slice {state.active_slice} is LOCKED. "
            f"Write passing tests first, then run `pragma unlock`. "
            f"Expected tests: {', '.join(test_names)}"
        )
        return {
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Gate is LOCKED for slice {state.active_slice}",
            "remediation": remediation,
        }

    all_touches: set[str] = set()
    for req in reqs:
        all_touches.update(req.touches)

    resolved = str((cwd / file_path).resolve())
    allowed = any(
        resolved == str((cwd / t).resolve()) or resolved.startswith(str((cwd / t).resolve()))
        for t in all_touches
    )

    if not allowed:
        remediation = (
            f"File {file_path} is not in the touches list for active slice "
            f"{state.active_slice}. Allowed files: {', '.join(sorted(all_touches))}"
        )
        return {
            "permissionDecision": "deny",
            "permissionDecisionReason": f"File not in touches for slice {state.active_slice}",
            "remediation": remediation,
        }

    return {"permissionDecision": "allow"}
