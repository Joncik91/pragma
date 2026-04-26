"""Diff-mode hook helper: block only when an edit introduces NEW gaming.

Called by both pre-tool-use.sh (Write candidate) and post-tool-use.sh
(on-disk after Edit). Reads the candidate file, the previous version
from git HEAD (when available), classifies both, and exits:

  0 — allow (no new blocking verdicts).
  2 — block (the edit introduced one or more new tautological /
      mocked-away / mismatched verdicts).

Pre-existing gaming in the file is not the user's problem to solve
right now — the hook only catches what THIS edit added.

Usage:
    check_diff.py <on_disk_path> <candidate_path>

When the two paths are the same (post-tool-use case), the candidate
is the on-disk file. When they differ (pre-tool-use Write case), the
candidate is a tempfile holding the proposed content.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_BLOCKING = {
    "tautological",
    "mocked-away",
    "monkeypatched",
    "swallowed",
    "skipped",
    "conditional",
    "mismatched",
}


def _run_pragma(file_path: Path) -> dict[str, object]:
    """Invoke `pragma verify tests <file>` and return parsed JSON, or {}."""
    for cmd in (["pragma"], [sys.executable, "-m", "pragma"]):
        result = subprocess.run(  # noqa: S603 — fixed args, no user input in argv
            [*cmd, "verify", "tests", str(file_path)],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                continue
    return {}


def _blocking_names(payload: dict[str, object]) -> set[str]:
    """Extract the set of test names with blocking verdicts."""
    names: set[str] = set()
    results = payload.get("results", {})
    if not isinstance(results, dict):
        return names
    for verdicts in results.values():
        if not isinstance(verdicts, list):
            continue
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            if v.get("kind") in _BLOCKING:
                name = v.get("test_name")
                if isinstance(name, str):
                    names.add(name)
    return names


def _get_old_source(on_disk_path: Path) -> str | None:
    """Read the previous version of the file from git HEAD, or None."""
    try:
        repo_root = subprocess.run(  # noqa: S603,S607
            ["git", "-C", str(on_disk_path.parent), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    rel = on_disk_path.resolve().relative_to(Path(repo_root).resolve())
    try:
        result = subprocess.run(  # noqa: S603,S607
            ["git", "-C", repo_root, "show", f"HEAD:{rel}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None


def _human_lines_for(payload: dict[str, object], names: set[str], display_path: Path) -> list[str]:
    """Render `<display_path>::<test> [kind] evidence` for each name."""
    lines: list[str] = []
    results = payload.get("results", {})
    if not isinstance(results, dict):
        return lines
    for verdicts in results.values():
        if not isinstance(verdicts, list):
            continue
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            name = v.get("test_name")
            if name in names and v.get("kind") in _BLOCKING:
                lines.append(f"{display_path}::{name} [{v.get('kind')}] {v.get('evidence', '')}")
    return lines


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <on_disk_path> <candidate_path>", file=sys.stderr)
        return 0  # don't fail-closed on bad usage; caller logs.
    on_disk = Path(argv[1])
    candidate = Path(argv[2])
    if not candidate.exists():
        return 0

    new_payload = _run_pragma(candidate)
    new_blocking = _blocking_names(new_payload)
    if not new_blocking:
        return 0

    old_blocking: set[str] = set()
    old_src = _get_old_source(on_disk) if on_disk.exists() else None
    if old_src is not None:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(old_src)
            old_tmp = Path(f.name)
        try:
            old_payload = _run_pragma(old_tmp)
            old_blocking = _blocking_names(old_payload)
        finally:
            old_tmp.unlink(missing_ok=True)

    new_only = new_blocking - old_blocking
    if not new_only:
        return 0

    lines = _human_lines_for(new_payload, new_only, on_disk)
    err = sys.stderr
    print("Pragma rejected this edit: it introduced new gamed assertions.", file=err)
    for line in lines:
        print(line, file=err)
    print("", file=err)
    print("Pre-existing gaming in this file is not blocked — only the new entries.", file=err)
    print("Each new test must:", file=err)
    print("  - Call the real production symbol (don't mock the function under test).", file=err)
    print(
        "  - Assert on its actual return value (not 'assert True', not '== same constant').",
        file=err,
    )
    print(
        "  - Use 'with pytest.raises(...):' when the name says rejects/raises/refuses/denies.",
        file=err,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
