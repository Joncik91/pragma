from __future__ import annotations

import sys
from pathlib import Path

import typer

from pragma.hooks.dispatcher import dispatch


def hook(
    event: str = typer.Argument(
        ..., metavar="EVENT",
        help="One of: session-start, pre-tool-use, post-tool-use, stop.",
    ),
) -> None:
    exit_code = dispatch(
        event=event,
        stdin=sys.stdin,
        stdout=sys.stdout,
        cwd=Path.cwd(),
    )
    raise typer.Exit(code=exit_code)
