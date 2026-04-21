"""Dogfood tests for REQ-006 — pragma report + pragma freeze determinism.

Locks in v1.0 done criterion #5 (§7.8): `pragma report` must produce
byte-identical JSON across repeated invocations on the same commit, and
`pragma freeze` on an unchanged `pragma.yaml` must not drift the
manifest hash.

Each test wraps its body in a thin `@trace("REQ-006")` helper so the
emitted span carries `logic_id=REQ-006`; without it, the work happens
inside REQ-002-traced helpers (hash_manifest, load_manifest) and the
PIL aggregator tags the permutation as mocked.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pragma_sdk import set_permutation, trace

from pragma.core.manifest import hash_manifest, load_manifest

REPO_ROOT = Path(__file__).resolve().parents[4]


@trace("REQ-006")
def _assert_report_identical() -> None:
    out1 = subprocess.run(
        [sys.executable, "-m", "pragma", "report", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        check=True,
    ).stdout
    out2 = subprocess.run(
        [sys.executable, "-m", "pragma", "report", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        check=True,
    ).stdout
    assert out1 == out2, (
        "pragma report --json must produce byte-identical JSON on repeat; "
        "any non-determinism here breaks v1.0 done criterion #5."
    )


@trace("REQ-006")
def _assert_hash_stable_after_noop_freeze(tmp_path: Path) -> None:
    manifest_src = REPO_ROOT / "pragma.yaml"
    local_manifest = tmp_path / "pragma.yaml"
    local_manifest.write_text(manifest_src.read_text(encoding="utf-8"), encoding="utf-8")

    before = hash_manifest(load_manifest(local_manifest))

    subprocess.run(
        [sys.executable, "-m", "pragma", "freeze"],
        cwd=str(tmp_path),
        capture_output=True,
        check=True,
    )

    after = hash_manifest(load_manifest(local_manifest))
    assert before == after, (
        "pragma freeze on an unchanged pragma.yaml must leave the canonical "
        "manifest hash unchanged; drift here breaks REQ-006."
    )


def test_req_006_report_byte_identical() -> None:
    with set_permutation("report_byte_identical"):
        _assert_report_identical()


def test_req_006_hash_stable_after_noop_freeze(tmp_path: Path) -> None:
    with set_permutation("hash_stable_after_noop_freeze"):
        _assert_hash_stable_after_noop_freeze(tmp_path)
