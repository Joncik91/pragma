from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class CollectError(RuntimeError):
    pass


@dataclass(frozen=True)
class CollectedTest:
    nodeid: str
    name: str


def expected_test_name(req_id: str, permutation_id: str) -> str:
    normalised = req_id.lower().replace("-", "_")
    return f"test_{normalised}_{permutation_id}"


def collect_tests(tests_dir: Path, *, cwd: Path | None = None) -> list[CollectedTest]:
    """Invoke pytest --collect-only against ``tests_dir`` and parse nodeids.

    ``cwd`` is the directory pytest runs in and the reference point for
    emitted nodeids. Defaults to ``tests_dir.parent`` for backward
    compatibility with greenfield projects where tests_root is
    top-level. Callers working on brownfield layouts with nested
    tests_root should pass the project root explicitly (BUG-018 /
    REQ-014).
    """
    effective_cwd = cwd if cwd is not None else tests_dir.parent
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(tests_dir),
        "--collect-only",
        "-q",
        "--no-header",
        "-o",
        "addopts=",
    ]
    proc = subprocess.run(  # noqa: S603 — controlled pytest invocation
        cmd,
        capture_output=True,
        text=True,
        cwd=str(effective_cwd),
    )
    if proc.returncode not in (0, 5):
        raise CollectError(
            f"pytest --collect-only exited {proc.returncode}: {proc.stdout}\n{proc.stderr}".strip()
        )
    out: list[CollectedTest] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("="):
            nodeid = line.split(" ")[0]
            name = nodeid.split("::")[-1]
            name = re.sub(r"\[.*\]$", "", name)
            out.append(CollectedTest(nodeid=nodeid, name=name))
    return out


def group_by_name(collected: list[CollectedTest]) -> dict[str, list[CollectedTest]]:
    """Group collected tests by parametrize-stripped name.

    BUG-006: a parametrized test `def test_req_001_happy(x)` appears
    once per parameter value. The old `{c.name: c for c in collected}`
    idiom in consumer sites kept only the last variant, which made the
    gate's "all red-tests present / all red-tests passing" decisions
    depend on whatever variant pytest collected last. Grouping makes
    every variant visible so callers can iterate all nodeids for a
    given expected name.
    """
    out: dict[str, list[CollectedTest]] = {}
    for c in collected:
        out.setdefault(c.name, []).append(c)
    return out


_RESULT_RE = re.compile(r"^(\S+::\S+)\s+(PASSED|FAILED|ERROR)")


def run_tests(
    tests_dir: Path,
    nodeids: list[str],
    *,
    cwd: Path | None = None,
    junit_xml: Path | None = None,
) -> dict[str, str]:
    """Run pytest. Emits junit.xml (BUG-020); cwd-safe on nested tests_root (BUG-018)."""
    if not nodeids:
        return {}
    effective_cwd = cwd if cwd is not None else tests_dir.parent
    effective_junit = (
        junit_xml if junit_xml is not None else effective_cwd / ".pragma" / "pytest-junit.xml"
    )
    # Ensure the parent dir exists — pytest won't create it.
    effective_junit.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *nodeids,
        "-v",
        "--tb=no",
        "--no-header",
        "-p",
        "no:cacheprovider",
        # BUG-015 / REQ-011: clear inherited addopts (e.g. `-q` in a
        # user pytest.ini) that would collapse per-test output to dots
        # and defeat the _RESULT_RE parse below. Matches the
        # collect_tests fix from v1.0.3 (BUG-009 / ex-KI-12).
        "-o",
        "addopts=",
        # BUG-020 / REQ-016: emit junit.xml via an explicit CLI flag so
        # it survives the addopts clear. Without this the PIL cannot
        # be populated from pragma's own flows (slice complete etc.)
        # because the aggregator needs junit+spans, and junit never
        # lands if it only lives in user pytest.ini addopts.
        f"--junit-xml={effective_junit}",
        "-o",
        "junit_family=xunit2",
    ]
    proc = subprocess.run(  # noqa: S603 — controlled pytest invocation
        cmd,
        capture_output=True,
        text=True,
        cwd=str(effective_cwd),
    )
    results: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        m = _RESULT_RE.match(line.strip())
        if m:
            nodeid, verdict = m.group(1), m.group(2)
            results[nodeid] = verdict.lower()
    for nodeid in nodeids:
        results.setdefault(nodeid, "error")
    return results


def run_full_suite_junit(
    *,
    tests_dir: Path,
    cwd: Path,
    junit_xml: Path | None = None,
) -> bool:
    """Regenerate junit.xml from a full-suite pytest run (BUG-021/REQ-020).

    ``slice complete`` runs pytest on only the active slice's nodeids
    for its gate check, and the resulting junit overwrites any
    previous slice's. Multi-slice projects then show every earlier
    slice as ``missing`` in ``pragma report``. Fix: after the per-
    slice gate run succeeds, call this helper to regenerate
    ``.pragma/pytest-junit.xml`` from a full-suite run so the PIL
    reflects every test in the project.

    Returns True if pytest exited cleanly (returncode 0 or 5,
    meaning all-passed or no-tests-collected). False on any other
    exit — caller can decide whether to fail loudly or warn. We
    don't raise because the gate check already passed; if the
    full-suite run hits a pre-existing unrelated failure in some
    other slice's tests, callers may want to keep the slice
    shipped anyway.
    """
    effective_junit = junit_xml if junit_xml is not None else cwd / ".pragma" / "pytest-junit.xml"
    effective_junit.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(tests_dir),
        "--tb=no",
        "--no-header",
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        f"--junit-xml={effective_junit}",
        "-o",
        "junit_family=xunit2",
    ]
    proc = subprocess.run(  # noqa: S603 — controlled pytest invocation
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    return proc.returncode in (0, 5)
