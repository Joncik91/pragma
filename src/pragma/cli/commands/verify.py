"""`pragma verify manifest`, `verify gate`, `verify all`."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from pragma.core.errors import (
    GateHashDrift,
    ManifestHashMismatch,
    PragmaError,
    StateNotFound,
    UnlockMissingTests,
    UnlockTestPassing,
)
from pragma.core.lockfile import read_lock
from pragma.core.manifest import hash_manifest, load_manifest
from pragma.core.models import Manifest, Requirement
from pragma.core.state import read_state
from pragma.core.tests_discovery import (
    CollectError,
    collect_tests,
    expected_test_name,
    run_tests,
)

verify_app = typer.Typer(
    name="verify",
    help="Check invariants of the Pragma project.",
    no_args_is_help=True,
)


def _check_manifest(cwd: Path) -> dict[str, object]:
    manifest = load_manifest(cwd / "pragma.yaml")
    lock = read_lock(cwd / "pragma.lock.json")
    computed = hash_manifest(manifest)
    if computed != lock.manifest_hash:
        raise ManifestHashMismatch(
            message=(
                "pragma.yaml has changed since the last `pragma freeze`. "
                "The lockfile hash no longer matches the manifest."
            ),
            remediation=(
                "Run `pragma freeze` to regenerate "
                "pragma.lock.json, then stage both files and "
                "retry the commit."
            ),
            context={"computed": computed, "lock": lock.manifest_hash},
        )
    return {"ok": True, "check": "manifest", "manifest_hash": lock.manifest_hash}


def _slice_requirements(manifest: Manifest, slice_id: str) -> list[Requirement]:
    sreqs: tuple[str, ...] | None = None
    for m in manifest.milestones:
        for s in m.slices:
            if s.id == slice_id:
                sreqs = s.requirements
                break
    if sreqs is None:
        return []
    req_ids = set(sreqs)
    return [r for r in manifest.requirements if r.id in req_ids]


def _check_gate(cwd: Path) -> dict[str, object]:
    lock = read_lock(cwd / "pragma.lock.json")
    manifest = load_manifest(cwd / "pragma.yaml")
    try:
        state = read_state(cwd / ".pragma")
    except StateNotFound:
        return {
            "ok": True, "check": "gate",
            "active_slice": None, "gate": None,
        }

    if state.manifest_hash != lock.manifest_hash:
        raise GateHashDrift(
            message=(
                "Gate state references a different manifest hash "
                "than the current lockfile. The gate was set against "
                "an older manifest."
            ),
            remediation=(
                "Run `pragma slice status` to inspect, then either "
                "`pragma slice cancel` and re-activate on the new "
                "manifest, or roll the manifest back."
            ),
            context={
                "state_hash": state.manifest_hash,
                "lock_hash": lock.manifest_hash,
            },
        )

    if state.active_slice is not None and state.gate == "LOCKED":
        tests_dir = cwd / manifest.project.tests_root
        slice_reqs = _slice_requirements(manifest, state.active_slice)
        expected = [
            expected_test_name(r.id, p.id)
            for r in slice_reqs
            for p in r.permutations
        ]
        if expected:
            if not tests_dir.exists():
                raise UnlockMissingTests(
                    message=(
                        f"Tests directory {tests_dir} does not exist."
                    ),
                    remediation=(
                        f"Create {tests_dir} and add failing tests."
                    ),
                    context={"tests_root": str(tests_dir)},
                )
            try:
                collected = collect_tests(tests_dir)
            except CollectError as exc:
                raise PragmaError(
                    code="verify_collect_failed",
                    message=f"pytest could not collect tests: {exc}",
                    remediation=(
                        "Fix the test collection error and retry."
                    ),
                ) from exc
            by_name = {c.name: c for c in collected}
            missing = [n for n in expected if n not in by_name]
            if missing:
                raise UnlockMissingTests(
                    message=(
                        f"{len(missing)} required test(s) missing."
                    ),
                    remediation=(
                        "Add failing tests per the naming convention."
                    ),
                    context={"missing": missing},
                )
            results = run_tests(
                tests_dir, [by_name[n].nodeid for n in expected]
            )
            passing = [
                nid for nid, v in results.items() if v == "passed"
            ]
            if passing:
                raise UnlockTestPassing(
                    message=(
                        f"{len(passing)} expected-failing test(s) "
                        "already pass."
                    ),
                    remediation=(
                        "Remove the premature implementation or drop "
                        "the permutation from the manifest."
                    ),
                    context={"passing": passing},
                )

    return {
        "ok": True,
        "check": "gate",
        "active_slice": state.active_slice,
        "gate": state.gate,
    }


@verify_app.command(name="manifest")
def verify_manifest() -> None:
    cwd = Path.cwd()
    try:
        result = _check_manifest(cwd)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None
    typer.echo(json.dumps(result, sort_keys=True, separators=(",", ":")))


@verify_app.command(name="gate")
def verify_gate() -> None:
    cwd = Path.cwd()
    try:
        result = _check_gate(cwd)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None
    typer.echo(json.dumps(result, sort_keys=True, separators=(",", ":")))


@verify_app.command(name="all")
def verify_all() -> None:
    cwd = Path.cwd()
    try:
        _check_manifest(cwd)
        _check_gate(cwd)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None
    typer.echo(
        json.dumps(
            {"ok": True, "checks": ["manifest", "gate"]},
            sort_keys=True, separators=(",", ":"),
        )
    )
