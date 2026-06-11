"""Run tests under coverage instrumentation, return raw coverage data.

Python: spawns `python -m coverage run -m pytest` in a subprocess with
--context=test_function, capturing per-test coverage into a tempfile
.coverage SQLite DB.
Vitest: spawns `npx vitest run --coverage.enabled --coverage.reporter=json`.

Both return `None` on any infrastructure failure (coverage missing, npx
not on PATH, package.json missing, pytest collection error, timeout). The
caller (gate.py) treats None as "skip tier 2 silently — emit no verdict."
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# The subprocess runs `coverage run -m pytest <untrusted test file>`. The test
# file is the very artifact under audit and may be gamed or hostile, so the
# child must not inherit the parent's full environment — that would hand any
# PRAGMA_*_API_KEY, cloud credential, or token straight to attacker-controlled
# code. Instead we build the child env from a minimal allowlist of vars the
# interpreter and pytest legitimately need, plus the coverage DB pointer.
_ENV_ALLOWLIST: frozenset[str] = frozenset(
    {
        "PATH",  # locate the interpreter and any tooling pytest shells out to
        "HOME",  # some libs and pytest plugins read user config from $HOME
        "TMPDIR",  # honor a custom temp dir if the parent set one
        "TEMP",
        "TMP",
        "LANG",  # locale — keeps text encoding / collation deterministic
        "LC_ALL",
        "LC_CTYPE",
        "PYTHONHASHSEED",  # reproducibility if the parent pinned it
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONPATH",  # src-layout repos need it for imports; not secret-bearing
        "SYSTEMROOT",  # required for the Python interpreter to start on Windows
    }
)


def _build_child_env(db_path: Path) -> dict[str, str]:
    """Build a minimal, secret-free environment for the coverage subprocess.

    Only allowlisted vars are forwarded from the parent process; everything
    else (API keys, tokens, DB passwords, cloud creds) is dropped. COVERAGE_FILE
    is set so the child writes coverage data to our temp DB.
    """
    env = {k: v for k, v in os.environ.items() if k in _ENV_ALLOWLIST}
    env["COVERAGE_FILE"] = str(db_path)
    return env


def run_python_with_coverage(test_path: Path, target_file: Path) -> Path | None:
    """Run pytest on `test_path` with coverage of `target_file`'s lines.

    Spawns `python -m coverage run -m pytest` in a subprocess with
    --context=test_function so each line hit is attributed to the test
    that triggered it. 5s pytest-timeout per test, 10s outer subprocess
    kill-switch. Returns path to the .coverage SQLite DB on success, None
    on any failure (missing files, subprocess error, timeout, etc.).
    """
    # Guard: test file must exist before spending a subprocess budget.
    if not test_path.exists():
        return None
    # Guard: target file must exist so coverage --include is meaningful.
    if not target_file.exists():
        return None

    # Allocate a temp path for the .coverage DB.
    with tempfile.NamedTemporaryFile(suffix=".coverage", delete=False) as tmp:
        db_path = Path(tmp.name)

    # Write a minimal .coveragerc so `dynamic_context = test_function` is
    # active. The CLI --context flag sets a static label; the ini option is
    # what enables per-test attribution.
    rc_content = "[run]\ndynamic_context = test_function\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".coveragerc", delete=False) as rc_tmp:
        rc_tmp.write(rc_content)
        rc_path = Path(rc_tmp.name)

    cmd = [
        sys.executable,
        "-m",
        "coverage",
        "run",
        "--data-file",
        str(db_path),
        f"--include={target_file}",
        f"--rcfile={rc_path}",
        "-m",
        "pytest",
        "-x",
        "--no-header",
        "-q",
        "--timeout=5",
        "-p",
        "no:cacheprovider",
        str(test_path),
    ]
    env = _build_child_env(db_path)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=10,
            cwd=test_path.parent,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
    finally:
        # Clean up the temp rcfile regardless of outcome.
        with contextlib.suppress(Exception):
            rc_path.unlink(missing_ok=True)

    # Pytest exit code 0 = all tests passed; 1 = tests failed/timed-out.
    # Only return coverage data when all tests actually passed — a failing
    # run means the DB may contain partial/misleading attribution.
    if proc.returncode != 0:
        return None

    # Coverage only writes the DB when it actually recorded something.
    if db_path.exists() and db_path.stat().st_size > 0:
        return db_path
    return None


def _find_vitest_project_root(test_path: Path) -> Path | None:
    """Walk up from test_path looking for a package.json that lists vitest."""
    import json as _json  # noqa: PLC0415

    current = test_path.resolve().parent
    for candidate in [current, *current.parents]:
        pkg = candidate / "package.json"
        if pkg.exists():
            try:
                data = _json.loads(pkg.read_text(encoding="utf-8"))
            except (_json.JSONDecodeError, OSError):
                continue
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "vitest" in deps:
                return candidate
    return None


def run_vitest_with_coverage(test_path: Path, target_file: Path) -> Path | None:
    """Spawn `npx vitest run` with V8 coverage; return JSON report path.

    Walks up from `test_path` looking for a `package.json` with vitest in
    deps. Skips silently when no package.json found OR npx not on PATH.
    8s timeout (Vitest cold start is slower than pytest).

    Returns the path to coverage-final.json on success, None on any failure.
    Caller is responsible for cleanup: ``shutil.rmtree(report_path.parent)``.
    """
    if not test_path.exists():
        return None
    if not target_file.exists():
        return None

    project_root = _find_vitest_project_root(test_path)
    if project_root is None:
        return None

    coverage_dir = Path(tempfile.mkdtemp(prefix="pragma-vitest-coverage-"))

    try:
        rel_test = test_path.resolve().relative_to(project_root)
        rel_target = target_file.resolve().relative_to(project_root)
    except ValueError:
        # Files outside the project root — shouldn't happen, but fail cleanly.
        return None

    cmd = [
        "npx",
        "--no-install",
        "vitest",
        "run",
        "--coverage.enabled=true",
        "--coverage.provider=v8",
        "--coverage.reporter=json",
        f"--coverage.reportsDirectory={coverage_dir}",
        f"--coverage.include={rel_target}",
        "--no-color",
        "--reporter=basic",
        str(rel_test),
    ]

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            timeout=8,
            cwd=project_root,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

    report_path = coverage_dir / "coverage-final.json"
    if not report_path.exists():
        return None
    return report_path
