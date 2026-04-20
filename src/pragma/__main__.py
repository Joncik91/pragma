"""Pragma CLI entrypoint."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="pragma",
    help="Senior engineer on rails for AI-driven development.",
    no_args_is_help=True,
    add_completion=False,
    invoke_without_command=True,
)


@app.callback()
def _main(ctx: typer.Context) -> None:
    """Senior engineer on rails for AI-driven development."""


if __name__ == "__main__":
    app()
