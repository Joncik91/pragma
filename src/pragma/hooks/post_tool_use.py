from __future__ import annotations

from pathlib import Path

import yaml

from pragma.core.audit import append_audit
from pragma.core.discipline import check_file


def _load_source_root(project_dir: Path) -> str:
    manifest_path = project_dir / "pragma.yaml"
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return raw["project"]["source_root"]


def handle(event_input: dict, cwd: Path) -> dict:
    tool_input = event_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path.endswith(".py"):
        return {"continue": True}

    source_root = _load_source_root(cwd).rstrip("/") + "/"

    if not file_path.startswith(source_root) and not file_path.lstrip("./").startswith(source_root):
        return {"continue": True}

    norm = file_path.lstrip("./")
    full_path = cwd / norm

    if not full_path.exists():
        return {"continue": True}

    violations = check_file(full_path)

    if violations:
        details = "; ".join(
            f"{v.rule} (line {v.line}: got {v.got}, budget {v.budget})"
            for v in violations
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
