"""Pragma CLI entrypoint."""

from __future__ import annotations

import typer

from pragma.cli.commands.doctor import doctor
from pragma.cli.commands.freeze import freeze
from pragma.cli.commands.hook import hook
from pragma.cli.commands.hooks import hooks_app
from pragma.cli.commands.init import init
from pragma.cli.commands.migrate import migrate
from pragma.cli.commands.narrative import narrative_app
from pragma.cli.commands.report import report
from pragma.cli.commands.slice import slice_app
from pragma.cli.commands.spec import spec_app
from pragma.cli.commands.unlock import unlock
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
app.command(name="hook")(hook)
app.command(name="doctor")(doctor)
app.command(name="migrate")(migrate)
app.command(name="unlock")(unlock)
app.command(name="report")(report)
app.add_typer(slice_app)
app.add_typer(spec_app)
app.add_typer(hooks_app)
app.add_typer(narrative_app)
app.add_typer(verify_app)


if __name__ == "__main__":
    app()
