"""`pragma unlock` — flip LOCKED -> UNLOCKED when tests are red."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer
from pragma_sdk import trace

from pragma.core.audit import append_audit
from pragma.core.errors import (
    PragmaError,
    StateNotFound,
    UnlockMissingTests,
    UnlockTestPassing,
)
from pragma.core.gate import unlock_transition
from pragma.core.lockfile import read_lock
from pragma.core.manifest import load_manifest, slice_requirements
from pragma.core.state import default_state, read_state, write_state
from pragma.core.tests_discovery import (
    CollectError,
    collect_tests,
    expected_test_name,
    run_tests,
)


def _assert_slice_unlock_ready(cwd: Path, manifest, state) -> None:
    """Validate the active slice is ready to unlock: tests exist, all red.

    Raises UnlockMissingTests when tests_dir is missing or expected names
    aren't found; UnlockTestPassing when any of the red tests have
    already flipped green; PragmaError(unlock_collect_failed) on collect
    errors.
    """
    tests_dir = cwd / manifest.project.tests_root
    if not tests_dir.exists():
        raise UnlockMissingTests(
            message=f"Tests directory {tests_dir} does not exist.",
            remediation=(
                f"Create {tests_dir} and write failing tests "
                "for each permutation of the active slice's "
                "requirements."
            ),
            context={"tests_root": str(tests_dir)},
        )
    slice_reqs = slice_requirements(manifest, state.active_slice)
    expected = [expected_test_name(r.id, p.id) for r in slice_reqs for p in r.permutations]
    try:
        collected = collect_tests(tests_dir)
    except CollectError as exc:
        raise PragmaError(
            code="unlock_collect_failed",
            message=f"pytest could not collect tests: {exc}",
            remediation="Fix the test collection error (usually an import error) and retry.",
        ) from exc
    by_name = {c.name: c for c in collected}
    missing = [n for n in expected if n not in by_name]
    if missing:
        raise UnlockMissingTests(
            message=f"{len(missing)} required test(s) missing.",
            remediation=(
                "Add a failing test for each permutation. Convention: "
                "`def test_req_<req_id>_<permutation_id>():` "
                f"under {tests_dir}."
            ),
            context={"missing": missing},
        )
    nodeids = [by_name[n].nodeid for n in expected]
    results = run_tests(tests_dir, nodeids)
    passing = [nid for nid, v in results.items() if v == "passed"]
    if passing:
        raise UnlockTestPassing(
            message=f"{len(passing)} expected-failing test(s) already pass.",
            remediation=(
                "A test in the red phase must assert something that "
                "isn't implemented yet. If the implementation exists, "
                "either remove it (TDD violation) or remove the "
                "permutation from the manifest."
            ),
            context={"passing": passing},
        )


@trace("REQ-003")
def unlock() -> None:
    cwd = Path.cwd()
    try:
        lock = read_lock(cwd / "pragma.lock.json")
        try:
            state = read_state(cwd / ".pragma")
        except StateNotFound:
            state = default_state(manifest_hash=lock.manifest_hash)
        manifest = load_manifest(cwd / "pragma.yaml")

        if state.active_slice is not None and state.gate == "LOCKED":
            _assert_slice_unlock_ready(cwd, manifest, state)

        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_state, audit_fields = unlock_transition(state, now_iso=now_iso)
        write_state(cwd / ".pragma", new_state)
        append_audit(
            cwd / ".pragma",
            event=audit_fields["event"],
            actor="cli",
            slice=audit_fields["slice"],
            from_state=audit_fields["from_state"],
            to_state=audit_fields["to_state"],
            reason=audit_fields["reason"],
            now_iso=now_iso,
        )
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(
        json.dumps(
            {
                "ok": True,
                "slice": audit_fields["slice"],
                "gate": "UNLOCKED",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
