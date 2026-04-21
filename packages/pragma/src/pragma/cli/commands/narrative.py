from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from pragma.core.errors import StateNotFound
from pragma.core.manifest import load_manifest
from pragma.core.state import read_state
from pragma.narrative.adr import build_adr
from pragma.narrative.commit import build_commit_message
from pragma.narrative.pr import build_pr_description
from pragma.narrative.remediation import get_remediation
from pragma.report.aggregator import build_report

narrative_app = typer.Typer(name="narrative", help="Generate senior-engineer artifacts.")


def _commit_timestamp(cwd: Path) -> str:
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "log", "-1", "--format=%cI"],  # noqa: S607
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip() or "0"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "0"


@narrative_app.command(name="commit")
def cmd_commit(
    subject: str = typer.Option(..., "--subject"),
    why: str | None = typer.Option(None, "--why"),
    cwd: Path | None = typer.Option(None, "--cwd"),
) -> None:
    project_dir = cwd or Path.cwd()
    try:
        staged_result = subprocess.run(  # noqa: S603
            ["git", "diff", "--staged", "--name-only"],  # noqa: S607
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        staged_files = [f for f in staged_result.stdout.strip().splitlines() if f] or [
            "(no staged files)"
        ]
    except (subprocess.CalledProcessError, FileNotFoundError):
        staged_files = ["(unknown)"]

    msg = build_commit_message(
        cwd=project_dir,
        staged_files=staged_files,
        subject_hint=subject,
        why_hint=why,
    )
    typer.echo(msg)


@narrative_app.command(name="pr")
def cmd_pr(
    cwd: Path | None = typer.Option(None, "--cwd"),
) -> None:
    project_dir = cwd or Path.cwd()
    manifest = load_manifest(project_dir / "pragma.yaml")
    try:
        state = read_state(project_dir / ".pragma")
    except StateNotFound:
        state = None

    spans = project_dir / ".pragma" / "spans" / "test-run.jsonl"
    junit = project_dir / ".pragma" / "pytest-junit.xml"

    report = build_report(
        manifest=manifest,
        state=state,
        spans_jsonl=spans if spans.exists() else None,
        junit_xml=junit if junit.exists() else None,
        commit_timestamp=_commit_timestamp(project_dir),
    )

    typer.echo(build_pr_description(report=report))


@narrative_app.command(name="adr")
def cmd_adr(
    slug: str = typer.Argument(...),
    context: str = typer.Option(..., "--context"),
    decision: str = typer.Option(..., "--decision"),
    consequences: str = typer.Option(..., "--consequences"),
    alternatives: str = typer.Option(..., "--alternatives"),
    who: str = typer.Option(..., "--who"),
) -> None:
    md = build_adr(
        slug=slug,
        context=context,
        decision=decision,
        consequences=consequences,
        alternatives=alternatives,
        who=who,
    )
    typer.echo(md)


@narrative_app.command(name="remediation")
def cmd_remediation(
    rule: str = typer.Argument(...),
    budget: int = typer.Option(10, "--budget"),
    got: int = typer.Option(0, "--got"),
) -> None:
    typer.echo(get_remediation(rule, budget=budget, got=got))
