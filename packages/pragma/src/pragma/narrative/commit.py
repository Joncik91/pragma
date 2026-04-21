from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pragma.core.errors import StateNotFound
from pragma.core.manifest import load_manifest, slice_requirements
from pragma.core.state import read_state

_TPL_DIR = Path(__file__).parent.parent / "templates"


def build_commit_message(
    *,
    cwd: Path,
    staged_files: list[str],
    subject_hint: str,
    why_hint: str | None,
) -> str:
    manifest = load_manifest(cwd / "pragma.yaml")
    try:
        state = read_state(cwd / ".pragma")
    except StateNotFound:
        state = None

    reqs = []
    if state and state.active_slice:
        reqs = slice_requirements(manifest, state.active_slice)

    why = why_hint or (
        reqs[0].description.strip().split("\n")[0] if reqs else "Scope unclear; filling in."
    )

    env = Environment(
        loader=FileSystemLoader(_TPL_DIR),
        autoescape=select_autoescape([]),
    )
    tpl = env.get_template("commit-message.tpl")
    return tpl.render(subject=subject_hint, why=why, files=staged_files)
