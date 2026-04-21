"""`pragma init --greenfield` scaffolding.

Greenfield flow: renders a seed Logic Manifest with `mode: greenfield`,
M01.S1, and one REQ-000 placeholder that Pattern A (`spec add-requirement`)
or Pattern C (`spec plan-greenfield`) will fill in. Also drops the same
brownfield integrity files (`.pre-commit-config.yaml`, `PRAGMA.md`,
`.claude/settings.json`, settings-hash stamp, `.pragma/spans/`, gitignore
entries, `pytest.ini`) plus a top-level `claude.md` primer that explains
the loop to a non-coder walking in cold.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pragma_sdk import trace

from pragma.cli.commands.init import _wire_pytest_junit
from pragma.core.errors import AlreadyInitialised, GreenfieldNonEmptySrc
from pragma.core.integrity import compute_settings_hash, write_stored_hash
from pragma.core.lockfile import write_lock
from pragma.core.manifest import hash_manifest, load_manifest
from pragma.core.state import default_state, write_state
from pragma.templates import TEMPLATES_DIR

_SHARED_TEMPLATES = {
    "pre-commit-config.yaml.tpl": ".pre-commit-config.yaml",
    "README.md.tpl": "PRAGMA.md",
    "claude-settings.json.tpl": ".claude/settings.json",
}


@trace("REQ-001")
def scaffold_greenfield(cwd: Path, *, name: str, language: str) -> list[str]:
    """Scaffold a greenfield Pragma project in ``cwd``.

    Raises ``GreenfieldNonEmptySrc`` if ``cwd/src`` exists and is non-empty,
    or ``AlreadyInitialised`` if ``pragma.yaml`` already exists at the root.
    Returns the sorted list of created/modified paths (relative to ``cwd``).
    """
    src_dir = cwd / "src"
    if src_dir.exists() and any(src_dir.iterdir()):
        raise GreenfieldNonEmptySrc(
            message=f"{src_dir} is not empty; greenfield requires a fresh tree.",
            remediation=(
                "Move existing code out of src/, or run " "`pragma init --brownfield` instead."
            ),
            context={"path": str(src_dir)},
        )

    manifest_path = cwd / "pragma.yaml"
    if manifest_path.exists():
        raise AlreadyInitialised(
            message=f"Refusing to overwrite existing pragma.yaml at {manifest_path}",
            remediation="Remove pragma.yaml manually if you intend to re-scaffold.",
            context={"existing": ["pragma.yaml"]},
        )

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,  # noqa: S701 — YAML/Markdown templates, not HTML
    )

    created: list[str] = []

    # 1. Seed manifest.
    manifest_tpl = env.get_template("greenfield-manifest.yaml.tpl")
    manifest_path.write_text(
        manifest_tpl.render(project_name=name, language=language),
        encoding="utf-8",
    )
    created.append("pragma.yaml")

    # 2. Brownfield-shared scaffolding files.
    for tpl_name, dest_rel in _SHARED_TEMPLATES.items():
        dest = cwd / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        tpl = env.get_template(tpl_name)
        dest.write_text(tpl.render(project_name=name), encoding="utf-8")
        created.append(dest_rel)

    # 3. claude.md primer.
    primer = env.get_template("claude.md.tpl").render(project_name=name)
    (cwd / "claude.md").write_text(primer, encoding="utf-8")
    created.append("claude.md")

    # 4. Freeze the manifest -> pragma.lock.json.
    manifest = load_manifest(manifest_path)
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_lock(cwd / "pragma.lock.json", manifest, now_iso=now_iso)
    created.append("pragma.lock.json")

    # 5. Settings-hash stamp + spans dir.
    pragma_dir = cwd / ".pragma"
    pragma_dir.mkdir(exist_ok=True)
    settings_path = cwd / _SHARED_TEMPLATES["claude-settings.json.tpl"]
    write_stored_hash(pragma_dir, compute_settings_hash(settings_path))
    created.append(".pragma/claude-settings.hash")

    (pragma_dir / "spans").mkdir(exist_ok=True)

    # 6. gitignore hygiene (idempotent — same logic as brownfield _scaffold).
    gitignore_path = cwd / ".gitignore"
    entries_to_add = [".pragma/spans/", ".pragma/pytest-junit.xml"]
    existing_lines: set[str] = set()
    if gitignore_path.exists():
        existing_lines = set(gitignore_path.read_text(encoding="utf-8").splitlines())
    new_entries = [e for e in entries_to_add if e not in existing_lines]
    if new_entries:
        with gitignore_path.open("a", encoding="utf-8") as f:
            if existing_lines and not gitignore_path.read_text(encoding="utf-8").endswith("\n"):
                f.write("\n")
            f.write("\n".join(new_entries) + "\n")

    # 7. pytest.ini (only when nothing owns pytest config already).
    if _wire_pytest_junit(cwd):
        created.append("pytest.ini")

    # 8. Empty src/ + tests/ trees (greenfield-specific).
    src_dir.mkdir(exist_ok=True)
    (cwd / "tests").mkdir(exist_ok=True)
    created.append("src/")
    created.append("tests/")

    # 9. Prime .pragma/state.json with the default (no slice active) state.
    write_state(pragma_dir, default_state(manifest_hash=hash_manifest(manifest)))
    created.append(".pragma/state.json")

    return sorted(created)
