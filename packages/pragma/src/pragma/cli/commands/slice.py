"""`pragma slice` — activate/complete/cancel/status subcommands."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer
from pragma_sdk import trace

from pragma.core.audit import append_audit
from pragma.core.errors import CompleteCollectFailed, PragmaError, StateNotFound
from pragma.core.gate import activate as activate_transition
from pragma.core.gate import cancel as cancel_transition
from pragma.core.gate import complete as complete_transition
from pragma.core.lockfile import LockFile, read_lock
from pragma.core.manifest import load_manifest, slice_requirements
from pragma.core.state import State, default_state, read_state, write_state
from pragma.core.tests_discovery import (
    CollectError,
    collect_tests,
    expected_test_name,
    group_by_name,
    run_full_suite_junit,
    run_tests,
)

slice_app = typer.Typer(
    name="slice",
    help="Activate, complete, or cancel a slice.",
    no_args_is_help=True,
)


def _pragma_dir(cwd: Path) -> Path:
    return cwd / ".pragma"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_state_or_default(cwd: Path) -> tuple[State, LockFile, Path]:
    pragma_dir = _pragma_dir(cwd)
    lock = read_lock(cwd / "pragma.lock.json")
    try:
        state = read_state(pragma_dir)
    except StateNotFound:
        state = default_state(manifest_hash=lock.manifest_hash)
    return state, lock, pragma_dir


@slice_app.command(name="activate")
@trace("REQ-003")
def activate(
    slice_id: str = typer.Argument(..., metavar="SLICE_ID"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Switch even if another slice is active.",
    ),
) -> None:
    cwd = Path.cwd()
    try:
        state, lock, pragma_dir = _load_state_or_default(cwd)
        manifest = load_manifest(cwd / "pragma.yaml")
        new_state, audit_fields = activate_transition(
            state=state,
            manifest=manifest,
            slice_id=slice_id,
            now_iso=_now_iso(),
            force=force,
            manifest_hash=lock.manifest_hash,
        )
        write_state(pragma_dir, new_state)
        append_audit(
            pragma_dir,
            event=audit_fields["event"],
            actor="cli",
            slice=audit_fields["slice"],
            from_state=audit_fields["from_state"],
            to_state=audit_fields["to_state"],
            reason=audit_fields["reason"],
            now_iso=(new_state.last_transition.at if new_state.last_transition else None),
        )
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(
        json.dumps(
            {"ok": True, "slice": slice_id, "gate": "LOCKED"},
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _assert_active_slice_tests_green(cwd: Path, state: State) -> None:
    """Collect + run the active slice's expected tests; raise on red or collect fail."""
    # Caller (complete) guards state.active_slice is not None.
    assert state.active_slice is not None
    manifest = load_manifest(cwd / "pragma.yaml")
    tests_dir = cwd / manifest.project.tests_root
    slice_reqs = slice_requirements(manifest, state.active_slice)
    expected = [expected_test_name(r.id, p.id) for r in slice_reqs for p in r.permutations]
    try:
        collected = collect_tests(tests_dir, cwd=cwd)
    except CollectError as exc:
        raise CompleteCollectFailed(
            message=f"pytest could not collect tests: {exc}",
            remediation="Fix the test collection error, then retry.",
        ) from exc
    by_name = group_by_name(collected)
    # BUG-006: include every parametrised variant of each expected name,
    # not just one; otherwise gate completion depends on pytest's
    # collection order.
    nodeids = [c.nodeid for n in expected for c in by_name.get(n, [])]
    # BUG-018 / REQ-014: thread the project root so nodeids resolve
    # correctly on brownfield layouts with nested tests_root.
    results = run_tests(tests_dir, nodeids, cwd=cwd) if nodeids else {}
    failing = [nid for nid, v in results.items() if v != "passed"]
    if failing:
        from pragma.core.errors import CompleteTestsFailing

        raise CompleteTestsFailing(
            message=f"{len(failing)} test(s) for the active slice are not green.",
            remediation="Make the tests pass (or run with --skip-tests for the bootstrap case).",
            context={"failing": failing},
        )

    # BUG-021 / REQ-020: the per-slice run above wrote a junit.xml
    # that only covers this slice's tests. `pragma report` across
    # multiple shipped slices would then flag every earlier slice's
    # permutations as missing. Regenerate junit from a full-suite
    # run so the PIL reflects the whole project. The gate check
    # already passed on this slice; we tolerate unrelated failures
    # in other slices' tests (the full-suite run's exit code is
    # advisory here, not gating).
    run_full_suite_junit(tests_dir=tests_dir, cwd=cwd)


@slice_app.command(name="complete")
@trace("REQ-003")
def complete(
    skip_tests: bool = typer.Option(
        False,
        "--skip-tests",
        help="Skip the green-tests check.",
    ),
) -> None:
    cwd = Path.cwd()
    try:
        state, lock, pragma_dir = _load_state_or_default(cwd)
        if not skip_tests and state.active_slice is not None:
            _assert_active_slice_tests_green(cwd, state)

        new_state, audit_fields = complete_transition(
            state,
            now_iso=_now_iso(),
            manifest_hash=lock.manifest_hash,
        )
        write_state(pragma_dir, new_state)
        append_audit(
            pragma_dir,
            event=audit_fields["event"],
            actor="cli",
            slice=audit_fields["slice"],
            from_state=audit_fields["from_state"],
            to_state=audit_fields["to_state"],
            reason=audit_fields["reason"],
            now_iso=(new_state.last_transition.at if new_state.last_transition else None),
        )
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(
        json.dumps(
            {"ok": True, "slice": audit_fields["slice"], "status": "shipped"},
            sort_keys=True,
            separators=(",", ":"),
        )
    )


@slice_app.command(name="cancel")
@trace("REQ-003")
def cancel() -> None:
    cwd = Path.cwd()
    try:
        state, lock, pragma_dir = _load_state_or_default(cwd)
        new_state, audit_fields = cancel_transition(
            state,
            now_iso=_now_iso(),
            manifest_hash=lock.manifest_hash,
        )
        write_state(pragma_dir, new_state)
        append_audit(
            pragma_dir,
            event=audit_fields["event"],
            actor="cli",
            slice=audit_fields["slice"],
            from_state=audit_fields["from_state"],
            to_state=audit_fields["to_state"],
            reason=audit_fields["reason"],
            now_iso=(new_state.last_transition.at if new_state.last_transition else None),
        )
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(
        json.dumps(
            {
                "ok": True,
                "slice": audit_fields["slice"],
                "status": "cancelled",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


@slice_app.command(name="status")
def status() -> None:
    cwd = Path.cwd()
    try:
        pragma_dir = _pragma_dir(cwd)
        try:
            state = read_state(pragma_dir)
        except StateNotFound:
            typer.echo(
                json.dumps(
                    {
                        "ok": True,
                        "active_slice": None,
                        "gate": None,
                        "slices": {},
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    slices_map = {sid: {"status": s.status, "gate": s.gate} for sid, s in state.slices.items()}
    typer.echo(
        json.dumps(
            {
                "ok": True,
                "active_slice": state.active_slice,
                "gate": state.gate,
                "slices": slices_map,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
