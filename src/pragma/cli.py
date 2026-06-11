"""`pragma` CLI — verify tests, init pre-commit."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from pragma.verify import is_blocking, verify_file

app = typer.Typer(
    name="pragma",
    help="Catch AI test-gaming. Run on test files; refuse gamed tests.",
    no_args_is_help=True,
    add_completion=False,
)
verify_app = typer.Typer(name="verify", help="Run the test-gaming detector.")
app.add_typer(verify_app)


@verify_app.command("tests")
def verify_tests(
    files: list[Path] = typer.Argument(  # noqa: B008 — typer requires call in default
        ..., exists=True, dir_okay=False, readable=True
    ),
    human: bool = typer.Option(False, "--human", help="Human-readable output."),
    with_coverage: bool = typer.Option(
        False,
        "--with-coverage",
        help="Tier 2: run tests under coverage; require target lines executed (Python only).",
    ),
    with_llm: bool = typer.Option(
        False,
        "--with-llm",
        help="Tier 3 (warning): LLM judge via DeepSeek. Requires PRAGMA_LLM_API_KEY.",
    ),
) -> None:
    """Classify tests in <files>; exit 1 if any are tautological/mocked-away/mismatched."""
    results: dict[str, list[dict[str, str]]] = {}
    blocking = False
    for path in files:
        verdicts = verify_file(path, with_coverage=with_coverage, with_llm=with_llm)
        if is_blocking(verdicts):
            blocking = True
        results[str(path)] = [asdict(v) for v in verdicts]

    if human:
        for path_str, verdicts in results.items():
            for v in verdicts:
                typer.echo(f"{path_str}::{v['test_name']} [{v['kind']}] {v['evidence']}")
    else:
        typer.echo(json.dumps({"results": results, "blocking": blocking}, sort_keys=True))

    raise typer.Exit(code=1 if blocking else 0)


_PRECOMMIT_SNIPPET = """\
- repo: local
  hooks:
    - id: pragma
      name: pragma verify tests
      entry: pragma verify tests
      language: system
      files: '(^|/)test_.*\\\\.py$|/tests/.*\\\\.py$'
"""


@app.command("init-precommit")
def init_precommit(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing config."),
) -> None:
    """Drop a `.pre-commit-config.yaml` calling `pragma verify tests`."""
    cfg = Path(".pre-commit-config.yaml")
    if cfg.exists() and not force:
        typer.echo(
            json.dumps(
                {
                    "ok": False,
                    "error": "exists",
                    "remediation": "Run with --force to overwrite, or merge the snippet manually.",
                    "path": str(cfg),
                },
                sort_keys=True,
            )
        )
        raise typer.Exit(code=1)
    cfg.write_text(f"repos:\n  {_PRECOMMIT_SNIPPET}", encoding="utf-8")
    typer.echo(json.dumps({"ok": True, "wrote": str(cfg)}, sort_keys=True))


@app.command("blocking")
def blocking() -> None:
    """Print the blocking-suffix set as a JSON array.

    Used by the plugin hook so it doesn't have to hardcode the suffixes.
    """
    from pragma.blocking import BLOCKING_SUFFIXES

    typer.echo(json.dumps(sorted(BLOCKING_SUFFIXES)))


if __name__ == "__main__":
    app()
