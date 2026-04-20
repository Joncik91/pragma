"""`pragma init --brownfield` — scaffold a new Pragma project in place."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from pragma.core.errors import AlreadyInitialised, PragmaError
from pragma.templates import TEMPLATES_DIR

_FILES_TO_CREATE = {
    "pragma.yaml.tpl": "pragma.yaml",
    "pre-commit-config.yaml.tpl": ".pre-commit-config.yaml",
    "README.md.tpl": "PRAGMA.md",
}


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
    """Scaffold pragma.yaml, .pre-commit-config.yaml, PRAGMA.md."""
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
    existing = [dest for dest in _FILES_TO_CREATE.values() if (cwd / dest).exists()]
    if existing and not force:
        raise AlreadyInitialised(
            message=(f"Refusing to overwrite existing files: {', '.join(existing)}"),
            remediation="Pass --force to overwrite, or remove the files manually.",
            context={"existing": existing},
        )

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,  # noqa: S701 — YAML/Markdown templates, not HTML
    )

    created: list[str] = []
    for tpl_name, dest_name in _FILES_TO_CREATE.items():
        tpl = env.get_template(tpl_name)
        rendered = tpl.render(project_name=project_name)
        (cwd / dest_name).write_text(rendered, encoding="utf-8")
        created.append(dest_name)
    return created
