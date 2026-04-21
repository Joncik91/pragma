from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pragma_sdk import trace

from pragma.core.audit import append_audit
from pragma.core.discipline import check_file


def _load_source_root(project_dir: Path) -> str | None:
    """Best-effort read of project.source_root from pragma.yaml.

    Returns None if the manifest is absent, unreadable, not valid YAML,
    or missing the expected keys. The hook then degrades to "allow,
    no discipline check" rather than raising through the dispatcher
    (which would log a spurious hook_crash audit entry). Only the
    specific read-path exceptions are caught; any other surprise still
    bubbles.
    """
    manifest_path = project_dir / "pragma.yaml"
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    try:
        return str(raw["project"]["source_root"])
    except (TypeError, KeyError):
        return None


@trace("REQ-004")
def handle(event_input: dict[str, Any], cwd: Path) -> dict[str, Any]:
    tool_input = event_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path.endswith(".py"):
        return {"continue": True}

    source_root_raw = _load_source_root(cwd)
    if source_root_raw is None:
        # No manifest (or unreadable) - nothing to check against.
        return {"continue": True}
    source_root = source_root_raw.rstrip("/") + "/"

    if not file_path.startswith(source_root) and not file_path.lstrip("./").startswith(source_root):
        return {"continue": True}

    norm = file_path.lstrip("./")
    full_path = cwd / norm

    if not full_path.exists():
        return {"continue": True}

    violations = check_file(full_path)

    if violations:
        details = "; ".join(
            f"{v.rule} (line {v.line}: got {v.got}, budget {v.budget})" for v in violations
        )
        append_audit(
            cwd / ".pragma",
            event="discipline_block",
            actor="hook:post_tool_use",
            slice=None,
            from_state=None,
            to_state=None,
            reason=details,
            context={"file": file_path, "violations": [v.rule for v in violations]},
        )
        return {"decision": "block", "reason": details}

    return {"continue": True}
