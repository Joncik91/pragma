from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer

from pragma.core.errors import PragmaError, StateNotFound
from pragma.core.manifest import load_manifest
from pragma.core.state import read_state
from pragma.report.aggregator import build_report
from pragma.report.formatter_md import render_markdown


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


def report(
    json_out: bool = typer.Option(False, "--json"),
    human: bool = typer.Option(False, "--human"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    if json_out and human:
        typer.echo(
            json.dumps(
                {
                    "error": "flag_conflict",
                    "message": "--json and --human are mutually exclusive",
                    "remediation": "Pick one.",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        raise typer.Exit(code=1)
    if not json_out and not human:
        json_out = True

    cwd = Path.cwd()
    try:
        manifest = load_manifest(cwd / "pragma.yaml")
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    try:
        state = read_state(cwd / ".pragma")
    except StateNotFound:
        state = None

    spans_dir = cwd / ".pragma" / "spans"
    junit = cwd / ".pragma" / "pytest-junit.xml"

    report_obj = build_report(
        manifest=manifest,
        state=state,
        spans_jsonl=spans_dir if spans_dir.exists() else None,
        junit_xml=junit if junit.exists() else None,
        commit_timestamp=_commit_timestamp(cwd),
    )

    if human:
        text = render_markdown(report_obj)
    else:
        payload = json.loads(report_obj.model_dump_json(exclude_none=False))
        text = json.dumps({"ok": True, **payload}, sort_keys=True, separators=(",", ":"))

    if output:
        output.write_text(text + "\n", encoding="utf-8")
    else:
        typer.echo(text)
