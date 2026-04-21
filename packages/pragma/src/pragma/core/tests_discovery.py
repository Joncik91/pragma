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


def collect_tests(tests_dir: Path) -> list[CollectedTest]:
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
        cwd=str(tests_dir.parent),
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


_RESULT_RE = re.compile(r"^(\S+::\S+)\s+(PASSED|FAILED|ERROR)")


def run_tests(tests_dir: Path, nodeids: list[str]) -> dict[str, str]:
    if not nodeids:
        return {}
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
    ]
    proc = subprocess.run(  # noqa: S603 — controlled pytest invocation
        cmd,
        capture_output=True,
        text=True,
        cwd=str(tests_dir.parent),
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
