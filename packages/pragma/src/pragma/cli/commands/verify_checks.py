"""Check functions powering ``pragma verify`` subcommands.

Each ``_check_*`` returns a result dict on success or raises a typed
``PragmaError`` on failure. The CLI-facing wrappers in ``verify.py``
only translate these into JSON + exit codes. Keeping the checks in
their own module lets ``verify.py`` stay under the file-size budget
and makes each check individually testable without importing Typer.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from pragma_sdk import trace

from pragma.core.commits import validate_commit_shape
from pragma.core.discipline import check_file
from pragma.core.errors import (
    CommitShapeViolationError,
    GateHashDrift,
    GitUnavailable,
    ManifestHashMismatch,
    StateNotFound,
    UnlockMissingTests,
    UnlockTestPassing,
    VerifyCollectFailed,
)
from pragma.core.integrity import verify_settings_integrity
from pragma.core.lockfile import read_lock
from pragma.core.manifest import hash_manifest, load_manifest, slice_requirements
from pragma.core.models import Manifest
from pragma.core.state import State, read_state
from pragma.core.tests_discovery import (
    CollectedTest,
    CollectError,
    collect_tests,
    expected_test_name,
    group_by_name,
    run_tests,
)


def _check_integrity(cwd: Path) -> dict[str, object]:
    from pragma.core.errors import HashNotFoundError, IntegrityMismatchError

    settings = cwd / ".claude" / "settings.json"
    pragma_dir = cwd / ".pragma"

    if not settings.exists():
        return {"ok": True, "check": "integrity", "reason": "no_settings"}

    result = verify_settings_integrity(settings, pragma_dir)
    if result is None:
        raise HashNotFoundError(
            message=".claude/settings.json exists but .pragma/claude-settings.hash is missing.",
            remediation="Run `pragma hooks seal` to store the canonical hash.",
            context={"settings": str(settings)},
        )

    if result is False:
        raise IntegrityMismatchError(
            message=".claude/settings.json has been modified since `pragma hooks seal`.",
            remediation=(
                "Inspect the change with `pragma hooks show`. If intentional, "
                "run `pragma hooks seal` to re-canonicalise. If not, restore "
                "from git history."
            ),
            context={"settings": str(settings), "hash": str(pragma_dir / "claude-settings.hash")},
        )

    return {"ok": True, "check": "integrity"}


def _check_discipline(cwd: Path) -> dict[str, object]:
    from pragma.core.errors import DisciplineViolationError

    manifest = load_manifest(cwd / "pragma.yaml")
    src_root = cwd / manifest.project.source_root
    violations: list[dict[str, object]] = []
    if src_root.exists():
        for py in sorted(src_root.rglob("*.py")):
            for v in check_file(py):
                violations.append(
                    {
                        "rule": v.rule,
                        "path": v.path,
                        "line": v.line,
                        "got": v.got,
                        "budget": v.budget,
                        "remediation": v.remediation,
                    }
                )
    if violations:
        raise DisciplineViolationError(
            message=f"{len(violations)} discipline violation(s).",
            remediation="See context.violations for per-rule remediation.",
            context={"violations": violations},
        )
    return {"ok": True, "check": "discipline"}


def _is_git_repo(cwd: Path) -> bool:
    try:
        subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--is-inside-work-tree"],  # noqa: S607
            cwd=str(cwd),
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return True


def _repo_has_head(cwd: Path) -> bool:
    """Return True if HEAD resolves to a commit.

    BUG-013: a freshly-initialised repo has no commits yet, so
    ``git log HEAD`` fails during pre-commit's first invocation of
    ``pragma verify all``. ``_check_commits`` needs to distinguish
    "not a git repo" from "git repo with no history yet" so it can
    skip gracefully in both cases.
    """
    try:
        subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--verify", "HEAD"],  # noqa: S607
            cwd=str(cwd),
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return False
    return True


def _git_range_spec(cwd: Path, base: str) -> str:
    try:
        subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--verify", base],  # noqa: S607
            cwd=str(cwd),
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        # BUG-047 / REQ-039: when --base doesn't exist (e.g. sandbox is
        # on `master`, brownfield repo never had a `main`), walk only
        # commits that introduced or modified `pragma.yaml`. Pre-Pragma
        # history is exempt by definition — Pragma cannot demand its
        # commit shape on commits that predate its adoption. If
        # pragma.yaml is staged but not yet committed (the very first
        # adopt-pragma commit), there's nothing in-range to check, so
        # return an empty range that yields zero commits.
        adopt = _first_commit_touching_pragma_yaml(cwd)
        if adopt is not None:
            return f"{adopt}^..HEAD"
        if _pragma_yaml_staged_or_present(cwd):
            return "HEAD..HEAD"
        return "HEAD"
    return f"{base}..HEAD"


def _pragma_yaml_staged_or_present(cwd: Path) -> bool:
    """True if pragma.yaml is staged for commit or sitting in the working tree.

    Brownfield's first adopt-pragma commit hasn't introduced pragma.yaml
    to git history yet, so `git log --diff-filter=A` returns empty. But
    we know a Pragma adoption is in flight when the file exists locally
    or appears in the staged index.
    """
    if (cwd / "pragma.yaml").exists():
        return True
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "diff", "--cached", "--name-only"],  # noqa: S607
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return False
    return any(line.strip() == "pragma.yaml" for line in out.splitlines())


def _first_commit_touching_pragma_yaml(cwd: Path) -> str | None:
    """Return SHA of the earliest commit that touched pragma.yaml, or None.

    Used to scope the commit-shape check to the post-adoption range when
    no `--base` ref is available. Returns None when pragma.yaml has never
    been committed (e.g. brownfield mid-init), which lets the caller fall
    back to scanning full HEAD.
    """
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "log", "--diff-filter=A", "--format=%H", "--", "pragma.yaml"],  # noqa: S607
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None
    if not out:
        return None
    return out.splitlines()[-1].strip() or None


def _partition_commits(commit_log: str) -> tuple[int, list[dict[str, object]]]:
    """Return (total_commits_checked, bad_commits)."""
    total = 0
    bad: list[dict[str, object]] = []
    for entry in commit_log.split("\x1e"):
        entry = entry.strip()
        if not entry:
            continue
        total += 1
        sha, _, message = entry.partition("\x00")
        errors = validate_commit_shape(message)
        if errors:
            bad.append(
                {
                    "sha": sha.strip(),
                    "rules": [e.rule for e in errors],
                    "remediation": [e.remediation for e in errors],
                }
            )
    return total, bad


def _check_commits(cwd: Path, base: str = "main") -> dict[str, object]:
    if not _is_git_repo(cwd):
        return {"ok": True, "check": "commits", "skipped": "not_a_git_repo"}
    if not _repo_has_head(cwd):
        # BUG-013: freshly-initialised repo, no commits yet (e.g. the
        # first `git commit` is in progress and pre-commit is running
        # `pragma verify all`). Nothing to validate; skip gracefully.
        return {"ok": True, "check": "commits", "skipped": "no_head"}
    range_spec = _git_range_spec(cwd, base)
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "log", range_spec, "--format=%H%x00%B%x1e"],  # noqa: S607
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise GitUnavailable(
            message=f"git log failed: {exc.stderr}",
            remediation="Ensure this is a git repo and base exists.",
        ) from exc
    total, bad_commits = _partition_commits(out)
    if bad_commits:
        raise CommitShapeViolationError(
            message=f"{len(bad_commits)} commit(s) fail shape validation.",
            remediation=(
                "Amend each commit body to include a WHY: line, a "
                "Co-Authored-By: trailer, and keep the subject ≤72 chars."
            ),
            context={"commits": bad_commits, "commits_checked": total},
        )
    # BUG-008: surface commits_checked + range_spec so the user sees when
    # --base silently contracted to HEAD (e.g. when main doesn't exist)
    # and what range was actually validated.
    return {
        "ok": True,
        "check": "commits",
        "commits_checked": total,
        "range": range_spec,
    }


@trace("REQ-001")
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


def _collect_or_raise(tests_dir: Path, *, cwd: Path) -> dict[str, list[CollectedTest]]:
    try:
        collected = collect_tests(tests_dir, cwd=cwd)
    except CollectError as exc:
        raise VerifyCollectFailed(
            message=f"pytest could not collect tests: {exc}",
            remediation="Fix the test collection error and retry.",
        ) from exc
    return group_by_name(collected)


def _raise_if_red_tests_green(
    tests_dir: Path,
    expected: list[str],
    by_name: dict[str, list[CollectedTest]],
    *,
    cwd: Path,
) -> None:
    # BUG-006: include every parametrised variant per expected name.
    # BUG-018 / REQ-014: thread the project root.
    results = run_tests(tests_dir, [c.nodeid for n in expected for c in by_name[n]], cwd=cwd)
    passing = [nid for nid, v in results.items() if v == "passed"]
    if passing:
        raise UnlockTestPassing(
            message=f"{len(passing)} expected-failing test(s) already pass.",
            remediation=(
                "Remove the premature implementation or drop the permutation from the manifest."
            ),
            context={"passing": passing},
        )


def _assert_locked_slice_tests_red(cwd: Path, manifest: Manifest, state: State) -> None:
    """Verify the active LOCKED slice has all expected red tests present and failing."""
    # Caller (_check_gate) guards state.active_slice is not None + gate == LOCKED.
    assert state.active_slice is not None
    tests_dir = cwd / manifest.project.tests_root
    slice_reqs = slice_requirements(manifest, state.active_slice)
    expected = [expected_test_name(r.id, p.id) for r in slice_reqs for p in r.permutations]
    if not expected:
        return
    if not tests_dir.exists():
        raise UnlockMissingTests(
            message=f"Tests directory {tests_dir} does not exist.",
            remediation=f"Create {tests_dir} and add failing tests.",
            context={"tests_root": str(tests_dir)},
        )
    by_name = _collect_or_raise(tests_dir, cwd=cwd)
    missing = [n for n in expected if n not in by_name]
    if missing:
        raise UnlockMissingTests(
            message=f"{len(missing)} required test(s) missing.",
            remediation="Add failing tests per the naming convention.",
            context={"missing": missing},
        )
    _raise_if_red_tests_green(tests_dir, expected, by_name, cwd=cwd)


def _check_gate(cwd: Path) -> dict[str, object]:
    lock = read_lock(cwd / "pragma.lock.json")
    manifest = load_manifest(cwd / "pragma.yaml")
    try:
        state = read_state(cwd / ".pragma")
    except StateNotFound:
        return {"ok": True, "check": "gate", "active_slice": None, "gate": None}

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
            context={"state_hash": state.manifest_hash, "lock_hash": lock.manifest_hash},
        )

    if state.active_slice is not None and state.gate == "LOCKED":
        _assert_locked_slice_tests_red(cwd, manifest, state)

    return {
        "ok": True,
        "check": "gate",
        "active_slice": state.active_slice,
        "gate": state.gate,
    }
