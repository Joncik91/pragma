"""`pragma init --brownfield` — scaffold a new Pragma project in place."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pragma_sdk import trace

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


def _emit_error_and_exit(code: str, message: str, remediation: str, exit_code: int) -> None:
    typer.echo(
        json.dumps(
            {"error": code, "message": message, "remediation": remediation, "context": {}},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    raise typer.Exit(code=exit_code)


def _validate_init_flags(brownfield: bool, greenfield: bool) -> None:
    if brownfield and greenfield:
        _emit_error_and_exit(
            code="both_modes",
            message="Pass exactly one of --brownfield / --greenfield.",
            remediation="Choose --brownfield (existing repo) OR --greenfield (new).",
            exit_code=2,
        )
    if not brownfield and not greenfield:
        _emit_error_and_exit(
            code="mode_required",
            message=(
                "Pragma init requires an explicit mode: "
                "--brownfield (existing repo) or --greenfield (new)."
            ),
            remediation="Pass --brownfield or --greenfield.",
            exit_code=2,
        )


def _run_greenfield(cwd: Path, name: str | None, language: str) -> None:
    if not name:
        _emit_error_and_exit(
            code="name_required",
            message="--name is required for --greenfield.",
            remediation=("Pass --name <project-name>; the manifest needs an explicit name."),
            exit_code=1,
        )
    from pragma.core.greenfield import scaffold_greenfield

    try:
        created = scaffold_greenfield(cwd, name=name, language=language)  # type: ignore[arg-type]
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None
    typer.echo(
        json.dumps(
            {"ok": True, "created": sorted(created), "project_name": name},
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _run_brownfield(cwd: Path, name: str | None, force: bool) -> None:
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


def init(
    brownfield: bool = typer.Option(
        False,
        "--brownfield",
        help="Initialise a brownfield project (in-place on an existing repo).",
    ),
    greenfield: bool = typer.Option(
        False,
        "--greenfield",
        help="Initialise a greenfield project (fresh tree with seed manifest).",
    ),
    name: str | None = typer.Option(
        None, "--name", help="Project name. Defaults to the current directory name."
    ),
    language: str = typer.Option(
        "python",
        "--language",
        help="Target language for the seed manifest (greenfield only).",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files if present."),
) -> None:
    """Scaffold pragma.yaml, .pre-commit-config.yaml, PRAGMA.md, .claude/settings.json."""
    _validate_init_flags(brownfield, greenfield)
    cwd = Path.cwd()
    if greenfield:
        _run_greenfield(cwd, name, language)
        return
    _run_brownfield(cwd, name, force)


def _refuse_overwrite_if_needed(cwd: Path, force: bool) -> Path:
    """Check for existing scaffold files; raise AlreadyInitialised if any exist and --force is off.

    Returns the settings-path for downstream phases to hash.
    """
    plain_dests = {k: v for k, v in _FILES_TO_CREATE.items() if k != _SETTINGS_KEY}
    existing = [dest for dest in plain_dests.values() if (cwd / dest).exists()]
    settings_path = cwd / _FILES_TO_CREATE[_SETTINGS_KEY]
    if settings_path.exists() and not force:
        existing.append(str(settings_path.relative_to(cwd)))
    if existing and not force:
        raise AlreadyInitialised(
            message=f"Refusing to overwrite existing files: {', '.join(sorted(existing))}",
            remediation="Pass --force to overwrite, or remove the files manually.",
            context={"existing": sorted(existing)},
        )
    return settings_path


def _render_scaffold_templates(cwd: Path, project_name: str) -> list[str]:
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
        dest.write_text(
            env.get_template(tpl_name).render(project_name=project_name),
            encoding="utf-8",
        )
        created.append(dest_name)
    return created


def _append_gitignore_entries(cwd: Path) -> None:
    gitignore_path = cwd / ".gitignore"
    entries_to_add = [".pragma/spans/", ".pragma/pytest-junit.xml"]
    existing_lines: set[str] = set()
    if gitignore_path.exists():
        existing_lines = set(gitignore_path.read_text(encoding="utf-8").splitlines())
    new_entries = [e for e in entries_to_add if e not in existing_lines]
    if not new_entries:
        return
    with gitignore_path.open("a", encoding="utf-8") as f:
        if existing_lines and not gitignore_path.read_text(encoding="utf-8").endswith("\n"):
            f.write("\n")
        f.write("\n".join(new_entries) + "\n")


@trace("REQ-001")
def _scaffold(cwd: Path, *, project_name: str, force: bool) -> list[str]:
    settings_path = _refuse_overwrite_if_needed(cwd, force)
    created = _render_scaffold_templates(cwd, project_name)

    pragma_dir = cwd / ".pragma"
    pragma_dir.mkdir(exist_ok=True)
    write_stored_hash(pragma_dir, compute_settings_hash(settings_path))
    created.append(".pragma/claude-settings.hash")
    (pragma_dir / "spans").mkdir(exist_ok=True)

    _append_gitignore_entries(cwd)
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
