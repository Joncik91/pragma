"""Read coverage data, answer 'did the target lines run under this test?'

Python: reads `.coverage` SQLite via `coverage.CoverageData.contexts_by_lineno`.
Vitest: parses V8 coverage JSON for per-test attribution.

The output shape is a dict `{test_name: bool}` indicating whether each
test in the file covered any line in the target's range.
"""

from __future__ import annotations

import json
from pathlib import Path


def query_python_coverage(
    coverage_db: Path, target_file: Path, target_lines: range
) -> dict[str, bool]:
    """Return {test_name: True if target lines covered, False otherwise}.

    Reads the .coverage SQLite DB via coverage.CoverageData, walks
    contexts_by_lineno for target_file's lines, and builds a {test_name: bool}
    mapping over every test that ran. Returns {} on any failure (missing DB,
    corrupt DB, no contexts recorded, etc.).

    Context strings are of the form "<module>::<test_name>|run" (or similar
    suffixes like |setup / |teardown). The test name is extracted as the
    portion after the last "::" and before the "|" separator.
    """
    try:
        import coverage as cov_module  # noqa: PLC0415
    except ImportError:
        return {}

    if not coverage_db.exists():
        return {}

    try:
        data = cov_module.CoverageData(basename=str(coverage_db))
        data.read()
    except Exception:
        return {}

    # Collect all measured files; normalise to resolved absolute paths for
    # reliable membership testing.
    try:
        measured = {str(Path(f).resolve()) for f in data.measured_files()}
    except Exception:
        return {}

    target_resolved = str(target_file.resolve())

    # --- collect contexts that hit target lines ----------------------------
    contexts_hitting_target: set[str] = set()
    if target_resolved in measured:
        try:
            ctx_by_line: dict[int, list[str]] = data.contexts_by_lineno(target_resolved)
        except Exception:
            ctx_by_line = {}
        for line in target_lines:
            contexts_hitting_target.update(ctx_by_line.get(line, []))

    # --- collect ALL contexts across every measured file ------------------
    all_contexts: set[str] = set()
    try:
        for f in data.measured_files():
            for line_ctxs in data.contexts_by_lineno(f).values():
                all_contexts.update(line_ctxs)
    except Exception:
        return {}

    # Remove the empty-string sentinel coverage uses for "no context".
    all_contexts.discard("")
    if not all_contexts:
        return {}

    # --- parse context strings → test names --------------------------------
    def _parse_test_name(ctx: str) -> str | None:
        """Extract test name from coverage context strings.

        Handles several formats produced by `dynamic_context = test_function`:
        - "module.test_name"         → "test_name"  (dot-separated, no suffix)
        - "module::test_name|run"    → "test_name"  (:: separator, |phase suffix)
        - "test_name|run"            → "test_name"  (bare name, |phase suffix)
        - "test_name"                → "test_name"  (bare name, no suffix)
        """
        # Strip the trailing phase suffix (|run, |setup, |teardown, etc.)
        base = ctx.split("|")[0] if "|" in ctx else ctx
        if not base:
            return None
        # Pytest node-id style with "::" separator (e.g. from pytest-xdist).
        if "::" in base:
            return base.rsplit("::", 1)[-1]
        # Standard `dynamic_context = test_function` format: "module.test_name".
        # The test function is the last dot-separated segment.
        if "." in base:
            return base.rsplit(".", 1)[-1]
        # Bare function name — use as-is.
        return base

    all_test_names: set[str] = set()
    for ctx in all_contexts:
        name = _parse_test_name(ctx)
        if name:
            all_test_names.add(name)

    covered_test_names: set[str] = set()
    for ctx in contexts_hitting_target:
        name = _parse_test_name(ctx)
        if name:
            covered_test_names.add(name)

    return {name: name in covered_test_names for name in all_test_names}


def query_vitest_coverage(
    coverage_json: Path, target_file: Path, target_lines: range
) -> dict[str, bool]:
    """Did target_file's target_lines have ANY hits in this V8 coverage report?

    V8 coverage is aggregated across the whole run, not per-test. Returns
    ``{"_aggregate": True}`` if at least one statement in target_lines has a
    positive hit count, ``{"_aggregate": False}`` if the file is present but no
    lines were hit, or ``{}`` on any failure (missing JSON, malformed, target
    absent from report).

    Step 8's gate calls this and broadcasts the boolean to every test in the
    file. Coarse but conservative; per-test refinement is deferred to v2.2.
    """
    if not coverage_json.exists():
        return {}
    try:
        data = json.loads(coverage_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    # Find the entry for target_file. Keys are typically absolute paths.
    target_resolved = target_file.resolve()
    entry = data.get(str(target_resolved))
    if entry is None:
        # Fall back: try resolving each key and compare.
        for k, v in data.items():
            try:
                if Path(k).resolve() == target_resolved:
                    entry = v
                    break
            except (OSError, ValueError):
                continue
    if entry is None:
        return {}

    statement_map = entry.get("statementMap", {})
    statement_hits = entry.get("s", {})

    target_set = set(target_lines)
    covered = False
    for stmt_id, stmt in statement_map.items():
        start_line = stmt.get("start", {}).get("line")
        if start_line is None:
            continue
        if start_line in target_set and (statement_hits.get(stmt_id) or 0) > 0:
            covered = True
            break

    return {"_aggregate": covered}
