"""Pragma CLI entrypoint."""

from __future__ import annotations

import typer

from pragma.cli.commands.init import init

app = typer.Typer(
    name="pragma",
    help="Senior engineer on rails for AI-driven development.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _main() -> None:
    """Senior engineer on rails for AI-driven development."""


app.command(name="init")(init)


if __name__ == "__main__":
    app()
