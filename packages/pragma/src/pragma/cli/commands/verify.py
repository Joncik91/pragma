"""`pragma verify manifest`, `verify gate`, `verify all`.

CLI wrappers over the check helpers in ``verify_checks``. Each
command translates a result dict into sorted-key JSON on success,
or a ``PragmaError.to_json()`` payload on failure. Business logic
lives in the helpers; this file is UI and exit-code shaping only.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pragma.cli.commands.verify_checks import (
    _check_commits,
    _check_discipline,
    _check_gate,
    _check_integrity,
    _check_manifest,
)
from pragma.core.commits import validate_commit_shape
from pragma.core.errors import CommitMsgNotFound, PragmaError

verify_app = typer.Typer(
    name="verify",
    help="Check invariants of the Pragma project.",
    no_args_is_help=True,
)


@verify_app.command(name="manifest")
def verify_manifest() -> None:
    cwd = Path.cwd()
    try:
        result = _check_manifest(cwd)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None
    typer.echo(json.dumps(result, sort_keys=True, separators=(",", ":")))


@verify_app.command(name="gate")
def verify_gate() -> None:
    cwd = Path.cwd()
    try:
        result = _check_gate(cwd)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None
    typer.echo(json.dumps(result, sort_keys=True, separators=(",", ":")))


@verify_app.command(name="discipline")
def verify_discipline() -> None:
    cwd = Path.cwd()
    try:
        result = _check_discipline(cwd)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None
    typer.echo(json.dumps(result, sort_keys=True, separators=(",", ":")))


@verify_app.command(name="integrity")
def verify_integrity() -> None:
    cwd = Path.cwd()
    try:
        result = _check_integrity(cwd)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None
    typer.echo(json.dumps(result, sort_keys=True, separators=(",", ":")))


@verify_app.command(name="commits")
def verify_commits(
    base: str = typer.Option(
        "main",
        "--base",
        help="Walk commits from <base>..HEAD. Defaults to main.",
    ),
) -> None:
    cwd = Path.cwd()
    try:
        result = _check_commits(cwd, base=base)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None
    typer.echo(json.dumps(result, sort_keys=True, separators=(",", ":")))


@verify_app.command(name="message")
def verify_message(
    message_file: Path = typer.Argument(
        ...,
        help="Path to a commit-message file (git passes .git/COMMIT_EDITMSG).",
    ),
) -> None:
    from pragma.core.errors import CommitShapeViolationError

    if not message_file.exists():
        err = CommitMsgNotFound(
            message=f"commit-msg file not found at {message_file}",
            remediation="Git normally passes .git/COMMIT_EDITMSG; don't invoke this manually.",
            context={"path": str(message_file)},
        )
        typer.echo(err.to_json())
        raise typer.Exit(code=1)

    message = message_file.read_text(encoding="utf-8")
    errors = validate_commit_shape(message)
    if errors:
        err = CommitShapeViolationError(
            message=f"Draft commit message fails shape validation: {len(errors)} issue(s).",
            remediation=(
                "Keep the subject ≤72 chars, add a body separated by a blank "
                "line, include a WHY: paragraph, and a Co-Authored-By: trailer."
            ),
            context={
                "rules": [e.rule for e in errors],
                "remediations": [e.remediation for e in errors],
            },
        )
        typer.echo(err.to_json())
        raise typer.Exit(code=1)

    typer.echo(json.dumps({"ok": True, "check": "message"}, sort_keys=True, separators=(",", ":")))


@verify_app.command(name="all")
def verify_all(
    ci: bool = typer.Option(
        False,
        "--ci",
        help="Accepted for backwards compatibility; all checks now run unconditionally.",
    ),
) -> None:
    """Umbrella check — fails on any violation across all sub-verifiers.

    The Stop hook invokes this to decide whether a turn can end; any
    check missing here becomes a silent gate hole. As of v1.0.2 this
    is the full list: manifest, gate, integrity, discipline, commits.
    The ``--ci`` flag is retained as a no-op for commands in existing
    CI configs so upgrades don't break.
    """
    del ci  # accepted but no longer meaningful; see docstring
    cwd = Path.cwd()
    try:
        _check_manifest(cwd)
        _check_gate(cwd)
        _check_integrity(cwd)
        _check_discipline(cwd)
        _check_commits(cwd)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "checks": ["manifest", "gate", "integrity", "discipline", "commits"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
