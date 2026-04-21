"""`pragma init --brownfield` — scaffold a new Pragma project in place."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from pragma.core.errors import AlreadyInitialised, PragmaError
from pragma.core.integrity import compute_settings_hash, write_stored_hash
from pragma.templates import TEMPLATES_DIR

_FILES_TO_CREATE = {
    "pragma.yaml.tpl": "pragma.yaml",
    "pre-commit-config.yaml.tpl": ".pre-commit-config.yaml",
    "README.md.tpl": "PRAGMA.md",
    "claude-settings.json.tpl": ".claude/settings.json",
}

_SETTINGS_KEY = "claude-settings.json.tpl"


def init(
    brownfield: bool = typer.Option(
        False,
        "--brownfield",
        help="Initialise a brownfield project (v0.1 only supports --brownfield).",
    ),
    name: str | None = typer.Option(
        None, "--name", help="Project name. Defaults to the current directory name."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files if present."),
) -> None:
    """Scaffold pragma.yaml, .pre-commit-config.yaml, PRAGMA.md, .claude/settings.json."""
    if not brownfield:
        typer.echo(
            json.dumps(
                {
                    "error": "mode_required",
                    "message": "v0.1 requires --brownfield explicitly.",
                    "remediation": "Pass --brownfield; --greenfield ships in v1.0.",
                    "context": {},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        raise typer.Exit(code=2)

    cwd = Path.cwd()
    project_name = name or cwd.name

    try:
        created = _scaffold(cwd, project_name=project_name, force=force)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(
        json.dumps(
            {"ok": True, "created": sorted(created), "project_name": project_name},
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _scaffold(cwd: Path, *, project_name: str, force: bool) -> list[str]:
    plain_dests = {k: v for k, v in _FILES_TO_CREATE.items() if k != _SETTINGS_KEY}
    existing = [dest for dest in plain_dests.values() if (cwd / dest).exists()]

    settings_path = cwd / _FILES_TO_CREATE[_SETTINGS_KEY]
    if settings_path.exists() and not force:
        existing.append(str(settings_path.relative_to(cwd)))

    if existing and not force:
        raise AlreadyInitialised(
            message=(f"Refusing to overwrite existing files: {', '.join(sorted(existing))}"),
            remediation="Pass --force to overwrite, or remove the files manually.",
            context={"existing": sorted(existing)},
        )

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,  # noqa: S701 — YAML/Markdown templates, not HTML
    )

    created: list[str] = []
    for tpl_name, dest_name in _FILES_TO_CREATE.items():
        dest = cwd / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        tpl = env.get_template(tpl_name)
        rendered = tpl.render(project_name=project_name)
        dest.write_text(rendered, encoding="utf-8")
        created.append(dest_name)

    pragma_dir = cwd / ".pragma"
    pragma_dir.mkdir(exist_ok=True)
    write_stored_hash(pragma_dir, compute_settings_hash(settings_path))
    created.append(".pragma/claude-settings.hash")

    (pragma_dir / "spans").mkdir(exist_ok=True)

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

    if _wire_pytest_junit(cwd):
        created.append("pytest.ini")

    return created


def _wire_pytest_junit(cwd: Path) -> bool:
    """Ensure pytest emits .pragma/pytest-junit.xml.

    Returns True if this call created `pytest.ini` at the project root.
    Leaves existing `[tool.pytest.ini_options]` in pyproject.toml or any
    pre-existing `pytest.ini` untouched — the downstream project owns its
    pytest config; we only scaffold when nothing is there.
    """
    junit_flag = "--junit-xml=.pragma/pytest-junit.xml"
    pyproject = cwd / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8")
        if "[tool.pytest.ini_options]" in text:
            return False
    existing_ini = cwd / "pytest.ini"
    if existing_ini.exists():
        return False
    existing_ini.write_text(
        f"[pytest]\naddopts = -q --strict-markers {junit_flag}\n",
        encoding="utf-8",
    )
    return True
