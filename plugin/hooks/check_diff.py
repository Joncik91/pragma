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


def _load_blocking_suffixes() -> set[str]:
    """Pull the blocking-suffix set from `pragma blocking` so the hook
    and the library share one source of truth (DRY)."""
    for cmd in (["pragma"], [sys.executable, "-m", "pragma"]):
        result = subprocess.run(  # noqa: S603 — fixed argv
            [*cmd, "blocking"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                return set(json.loads(result.stdout))
            except json.JSONDecodeError:
                continue
    # Fail-safe: if we can't reach pragma, treat nothing as blocking.
    # The hook will exit 0 in that case, which is the existing
    # graceful-degrade behavior.
    return set()


_BLOCKING = _load_blocking_suffixes()


def _run_pragma(
    file_path: Path, *, with_coverage: bool = False, with_llm: bool = False
) -> dict[str, object]:
    """Invoke `pragma verify tests <file>` and return parsed JSON, or {}."""
    extra_args: list[str] = []
    if with_coverage:
        extra_args.append("--with-coverage")
    if with_llm:
        extra_args.append("--with-llm")
    for cmd in (["pragma"], [sys.executable, "-m", "pragma"]):
        result = subprocess.run(  # noqa: S603 — fixed args, no user input in argv
            [*cmd, "verify", "tests", *extra_args, str(file_path)],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                continue
    return {}


_SKIP_SUFFIXES = frozenset({"unparseable"})


def _skip_lines(payload: dict[str, object]) -> list[str]:
    """Render `<path> [kind] evidence` for explicit skip verdicts (e.g. an
    unparseable file). These don't block, but the hook logs them so a broken
    or non-UTF-8 file is never silently treated as clean."""
    lines: list[str] = []
    results = payload.get("results", {})
    if not isinstance(results, dict):
        return lines
    for path_str, verdicts in results.items():
        if not isinstance(verdicts, list):
            continue
        for v in verdicts:
            if not isinstance(v, dict):
                continue
            kind = v.get("kind")
            if isinstance(kind, str) and kind.rsplit(".", 1)[-1] in _SKIP_SUFFIXES:
                lines.append(f"{path_str} [{kind}] {v.get('evidence', '')}")
    return lines


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
            kind = v.get("kind")
            if not isinstance(kind, str):
                continue
            suffix = kind.rsplit(".", 1)[-1]
            if suffix in _BLOCKING:
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
            kind = v.get("kind")
            if name in names and isinstance(kind, str) and kind.rsplit(".", 1)[-1] in _BLOCKING:
                lines.append(f"{display_path}::{name} [{kind}] {v.get('evidence', '')}")
    return lines


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            f"usage: {argv[0]} <on_disk_path> <candidate_path> [--with-coverage] [--with-llm]",
            file=sys.stderr,
        )
        return 0  # don't fail-closed on bad usage; caller logs.
    on_disk = Path(argv[1])
    candidate = Path(argv[2])
    with_coverage = "--with-coverage" in argv[3:]
    with_llm = "--with-llm" in argv[3:]
    if not candidate.exists():
        return 0

    new_payload = _run_pragma(candidate, with_coverage=with_coverage, with_llm=with_llm)

    # Log (but don't block on) explicit skip verdicts — an unparseable or
    # non-UTF-8 file is noise, not gaming, yet must never be silently passed.
    skip_lines = _skip_lines(new_payload)
    if skip_lines:
        print("Pragma skipped a file it could not parse (not blocked):", file=sys.stderr)
        for line in skip_lines:
            print(line, file=sys.stderr)

    new_blocking = _blocking_names(new_payload)
    if not new_blocking:
        return 0

    old_blocking: set[str] = set()
    old_src = _get_old_source(on_disk) if on_disk.exists() else None
    if old_src is not None:
        import tempfile

        # Preserve the original filename so the language matchers
        # (python.matches, vitest.matches) recognize it as a test file.
        # A bare /tmp/tmpXXXX.py wouldn't match python's `test_*` /
        # `*_test.py` / contains-`tests/` rules and the file would
        # silently classify as "no language" → empty blocking set.
        old_tmp_dir = Path(tempfile.mkdtemp(prefix="pragma-diff-tests-"))
        old_tmp = old_tmp_dir / on_disk.name
        old_tmp.write_text(old_src, encoding="utf-8")
        try:
            old_payload = _run_pragma(old_tmp, with_coverage=with_coverage, with_llm=with_llm)
            old_blocking = _blocking_names(old_payload)
        finally:
            old_tmp.unlink(missing_ok=True)
            old_tmp_dir.rmdir()

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
