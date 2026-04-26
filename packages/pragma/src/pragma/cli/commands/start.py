"""`pragma start "<intent>"` — one-command bootstrap.

REQ-043 (v0.2.0). Collapses the five-command greenfield bootstrap
(init → write problem.md → plan-greenfield → freeze → slice activate)
into a single command. Auto-detects greenfield vs brownfield and
runs the right path. Designed for the Claude Code plugin: the user
asks Claude for a feature, the plugin calls `pragma start "<intent>"`,
the gate is LOCKED before the user even sees the diff.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import typer
from pragma_sdk import trace

from pragma.cli.commands.init import _scaffold
from pragma.core.audit import append_audit
from pragma.core.errors import AlreadyInitialised, PragmaError
from pragma.core.gate import activate
from pragma.core.greenfield import scaffold_greenfield
from pragma.core.lockfile import read_lock, write_lock
from pragma.core.manifest import hash_manifest, load_manifest
from pragma.core.state import default_state, read_state, write_state


def _detect_mode(cwd: Path) -> str:
    """Greenfield = empty src/ or no .git history; brownfield otherwise.

    Heuristic: if src/ has no Python files AND there are no git commits,
    treat as greenfield. Anything else (existing code OR existing repo)
    is brownfield - the user can always pick the other mode by calling
    `init` directly.
    """
    src = cwd / "src"
    has_existing_code = src.exists() and any(src.glob("**/*.py"))
    has_git_history = (cwd / ".git").exists() and _git_has_commits(cwd)
    if has_existing_code or has_git_history:
        return "brownfield"
    return "greenfield"


def _git_has_commits(cwd: Path) -> bool:
    import shutil

    git_bin = shutil.which("git")
    if git_bin is None:
        return False
    try:
        result = subprocess.run(  # noqa: S603 — resolved git binary, fixed args
            [git_bin, "rev-parse", "--verify", "HEAD"],
            cwd=str(cwd),
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _slug_from_intent(intent: str) -> str:
    """Derive a project name from the intent string (kebab, max 40 chars)."""
    cleaned = "".join(c if c.isalnum() or c in " -" else " " for c in intent.lower())
    parts = [p for p in cleaned.split() if p]
    slug = "-".join(parts)[:40].rstrip("-")
    return slug or "pragma-project"


def _write_problem_md(cwd: Path, intent: str) -> None:
    docs = cwd / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "problem.md").write_text(f"# {intent}\n", encoding="utf-8")


def _do_freeze(cwd: Path) -> None:
    """Inline equivalent of `pragma freeze` for orchestration."""
    manifest = load_manifest(cwd / "pragma.yaml")
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_lock(cwd / "pragma.lock.json", manifest, now_iso=now_iso)


def _activate_only_slice(cwd: Path, slice_id: str) -> None:
    """Activate the named slice; mirror what `slice activate` does."""
    lock = read_lock(cwd / "pragma.lock.json")
    state = read_state(cwd / ".pragma")
    manifest = load_manifest(cwd / "pragma.yaml")
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_state, audit_fields = activate(
        state=state,
        manifest=manifest,
        slice_id=slice_id,
        now_iso=now_iso,
        manifest_hash=lock.manifest_hash,
    )
    write_state(cwd / ".pragma", new_state)
    append_audit(
        cwd / ".pragma",
        event=audit_fields["event"],
        actor="cli",
        slice=audit_fields["slice"],
        from_state=audit_fields["from_state"],
        to_state=audit_fields["to_state"],
        reason=f"pragma start (orchestrator activate {slice_id})",
        now_iso=now_iso,
    )


def _run_greenfield(cwd: Path, intent: str, name: str) -> dict[str, object]:
    from pragma.core.plan_greenfield import plan_greenfield

    scaffold_greenfield(cwd, name=name, language="python")
    _write_problem_md(cwd, intent)
    plan_greenfield(cwd, cwd / "docs" / "problem.md")
    _do_freeze(cwd)
    _activate_only_slice(cwd, "M01.S1")
    return {"ok": True, "mode": "greenfield", "slice": "M01.S1", "gate": "LOCKED", "intent": intent}


def _run_brownfield(cwd: Path, intent: str, name: str) -> dict[str, object]:
    _scaffold(cwd, project_name=name, force=False)
    # Brownfield template ships an implicit M00.S0 slice; freeze, then activate.
    manifest = load_manifest(cwd / "pragma.yaml")
    pragma_dir = cwd / ".pragma"
    pragma_dir.mkdir(exist_ok=True)
    write_state(pragma_dir, default_state(manifest_hash=hash_manifest(manifest)))
    _do_freeze(cwd)
    _activate_only_slice(cwd, "M00.S0")
    return {"ok": True, "mode": "brownfield", "slice": "M00.S0", "gate": "LOCKED", "intent": intent}


@trace("REQ-043")
def start(
    intent: str = typer.Argument(
        ...,
        help='One-line feature intent, e.g. "User can log in with email and password".',
    ),
) -> None:
    """One-command bootstrap: detect mode, scaffold, plan, freeze, activate."""
    cwd = Path.cwd()
    if (cwd / "pragma.yaml").exists():
        err = AlreadyInitialised(
            message="pragma.yaml already exists; pragma start is for fresh dirs.",
            remediation=(
                "Either work with the existing manifest "
                "(pragma slice activate <id>) or remove pragma.yaml and re-run."
            ),
            context={"existing": ["pragma.yaml"]},
        )
        typer.echo(err.to_json())
        raise typer.Exit(code=1)

    mode = _detect_mode(cwd)
    name = _slug_from_intent(intent)
    try:
        if mode == "greenfield":
            payload = _run_greenfield(cwd, intent, name)
        else:
            payload = _run_brownfield(cwd, intent, name)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))
