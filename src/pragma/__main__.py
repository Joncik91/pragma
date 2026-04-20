"""Pragma CLI entrypoint."""

from __future__ import annotations

import typer

from pragma.cli.commands.doctor import doctor
from pragma.cli.commands.freeze import freeze
from pragma.cli.commands.init import init
from pragma.cli.commands.spec import spec_app
from pragma.cli.commands.verify import verify_app

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
app.command(name="freeze")(freeze)
app.command(name="doctor")(doctor)
app.add_typer(spec_app)
app.add_typer(verify_app)


if __name__ == "__main__":
    app()
