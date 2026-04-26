"""Tier 2 public entry — orchestrates target resolution, runner, query, cache."""

from __future__ import annotations

import shutil
import sys
from contextlib import suppress
from pathlib import Path
from typing import Protocol

from pragma.coverage.cache import MISS, content_hash, lookup, store
from pragma.coverage.query import query_python_coverage, query_vitest_coverage
from pragma.coverage.runner import run_python_with_coverage, run_vitest_with_coverage
from pragma.coverage.target import (
    _vitest_symbol_lines,
    production_lines_python,
    production_target_vitest,
)
from pragma.verdict import Verdict


class _LanguageModule(Protocol):
    """The Classifier protocol slice tier 2 actually depends on."""

    LANGUAGE: str

    def matches(self, path: Path) -> bool: ...


def classify_file(
    test_path: Path,
    prior_verdicts: list[Verdict],
    lang: _LanguageModule,
) -> list[Verdict]:
    """Run tier 2 on `test_path`, returning verdicts that augment/replace `prior_verdicts`.

    Contract:
    - Tests already flagged blocking by tier 1 keep their tier-1 verdict (no
      double-flagging; tier 1 is more specific about *what kind* of gaming).
    - Tests classified `<lang>.verified` by tier 1 are subject to the
      coverage check. If the inferred target's lines were never hit under
      that test's coverage context, the verified verdict is replaced with
      `<lang>.target_not_covered`.
    - On any infrastructure failure, return `prior_verdicts` unchanged.

    Dispatch: python → _run_python_tier2; vitest → _run_vitest_tier2;
    unknown language → prior_verdicts unchanged.
    """
    if not prior_verdicts:
        return prior_verdicts
    if lang.LANGUAGE == "python":
        try:
            return _run_python_tier2(test_path, prior_verdicts)
        except Exception as exc:
            sys.stderr.write(f"[pragma:tier2] error in gate.classify_file: {exc}\n")
            return prior_verdicts
    if lang.LANGUAGE == "vitest":
        try:
            return _run_vitest_tier2(test_path, prior_verdicts)
        except Exception as exc:
            sys.stderr.write(f"[pragma:tier2] error in vitest gate: {exc}\n")
            return prior_verdicts
    return prior_verdicts  # unknown language


# ---------------------------------------------------------------------------
# Internal Python tier-2 implementation
# ---------------------------------------------------------------------------


def _run_python_tier2(
    test_path: Path,
    prior_verdicts: list[Verdict],
) -> list[Verdict]:
    from pragma.languages.python.inference import infer_target  # noqa: PLC0415

    verified_kind = "python.verified"
    verified_tests = [v for v in prior_verdicts if v.kind == verified_kind]
    if not verified_tests:
        return prior_verdicts

    source = test_path.read_text(encoding="utf-8")
    test_hash = content_hash(test_path)

    # Resolve (target_file, target_lines, target_hash, target_symbol) per test.
    # Tests with no inferable target are skipped silently.
    per_test: dict[str, tuple[Path, range, str, str]] = {}
    for v in verified_tests:
        target_module, target_symbol = infer_target(source, v.test_name)
        if target_module is None or target_symbol is None:
            continue
        target_info = production_lines_python(target_module, target_symbol)
        if target_info is None:
            continue
        target_file, target_lines = target_info
        target_hash = content_hash(target_file)
        per_test[v.test_name] = (target_file, target_lines, target_hash, target_symbol)

    if not per_test:
        return prior_verdicts

    # --- Cache pass: classify what we can without running -------------------
    # new_verdicts maps test_name → replacement verdict (or None = covered/keep verified)
    # The sentinel `...` (Ellipsis) means "not yet decided / not in scope."
    new_verdicts: dict[str, Verdict | None] = {}
    needs_runner: list[str] = []

    for name, (_target_file, _target_lines, target_hash, target_symbol) in per_test.items():
        cached = lookup(test_hash, target_hash, target_symbol)
        if cached is MISS:
            needs_runner.append(name)
        elif cached is None:
            new_verdicts[name] = None  # cached as "covered, no verdict" → keep verified
        else:
            new_verdicts[name] = cached  # type: ignore[assignment]  # cached Verdict

    # --- Runner pass: cover everything that missed the cache ----------------
    if needs_runner:
        # Group by unique target file so we spawn one subprocess per (test_file, target_file).
        runs_by_target: dict[Path, list[str]] = {}
        for name in needs_runner:
            tf = per_test[name][0]
            runs_by_target.setdefault(tf, []).append(name)

        for target_file, names in runs_by_target.items():
            db_path = run_python_with_coverage(test_path, target_file)
            if db_path is None:
                # Infrastructure failure — don't cache, keep verified for all names.
                continue
            try:
                for name in names:
                    target_lines = per_test[name][1]
                    target_hash = per_test[name][2]
                    target_symbol = per_test[name][3]
                    covered_map = query_python_coverage(db_path, target_file, target_lines)
                    if name not in covered_map:
                        # Test didn't appear in coverage data (skipped, collection error, etc.).
                        # Conservative: keep verified, no cache write.
                        continue
                    if covered_map[name]:
                        new_verdicts[name] = None  # covered → keep verified
                        store(test_hash, target_hash, target_symbol, None)
                    else:
                        verdict = Verdict(
                            kind="python.target_not_covered",
                            evidence=(
                                f"test ran but {target_symbol} (lines "
                                f"{target_lines.start}-{target_lines.stop - 1}) had 0 hits "
                                f"in this test's coverage context"
                            ),
                            test_name=name,
                        )
                        new_verdicts[name] = verdict
                        store(test_hash, target_hash, target_symbol, verdict)
            finally:
                with suppress(Exception):
                    db_path.unlink(missing_ok=True)

    # --- Build output: walk prior_verdicts in order, substituting where needed ---
    result: list[Verdict] = []
    for v in prior_verdicts:
        if v.kind != verified_kind:
            result.append(v)
            continue
        if v.test_name not in new_verdicts:
            # Not in new_verdicts: no inferable target, or test absent from coverage data.
            # Keep verified — tier 2 has no opinion.
            result.append(v)
            continue
        replacement = new_verdicts[v.test_name]
        if replacement is None:
            result.append(v)  # covered → keep verified
        else:
            result.append(replacement)  # target_not_covered or other tier-2 verdict
    return result


# ---------------------------------------------------------------------------
# Internal Vitest tier-2 implementation
# ---------------------------------------------------------------------------


def _run_vitest_tier2(
    test_path: Path,
    prior_verdicts: list[Verdict],
) -> list[Verdict]:
    verified_kind = "vitest.verified"
    verified_tests = [v for v in prior_verdicts if v.kind == verified_kind]
    if not verified_tests:
        return prior_verdicts

    # Step 1: resolve one production target for the whole file.
    target = production_target_vitest(test_path)
    if target is None:
        return prior_verdicts
    target_file, target_symbol = target

    # Step 2: resolve the symbol's line range in the target file.
    target_lines = _vitest_symbol_lines(target_file, target_symbol)
    if target_lines is None:
        return prior_verdicts

    # Step 3: compute hashes and check the cache.
    test_hash = content_hash(test_path)
    target_hash = content_hash(target_file)
    cached = lookup(test_hash, target_hash, target_symbol)

    # Step 4: cache hit.
    if cached is not MISS:
        if cached is None:
            # Covered — keep all verified verdicts unchanged.
            return prior_verdicts
        else:
            # Cached as target_not_covered. Broadcast to all verified tests.
            result: list[Verdict] = []
            for v in prior_verdicts:
                if v.kind == verified_kind:
                    result.append(
                        Verdict(
                            kind=cached.kind,  # type: ignore[union-attr]
                            evidence=cached.evidence,  # type: ignore[union-attr]
                            test_name=v.test_name,
                        )
                    )
                else:
                    result.append(v)
            return result

    # Step 5: cache miss — run vitest with coverage.
    db_path = run_vitest_with_coverage(test_path, target_file)
    if db_path is None:
        # Infrastructure failure — don't cache.
        return prior_verdicts

    try:
        query_result = query_vitest_coverage(db_path, target_file, target_lines)
    finally:
        # Cleanup the V8 coverage report dir.
        with suppress(Exception):
            shutil.rmtree(db_path.parent)

    # Step 6: interpret query result.
    if not query_result:
        # Query failed — keep prior_verdicts, no cache write.
        return prior_verdicts

    aggregate_covered = query_result.get("_aggregate")

    if aggregate_covered is True:
        # Target was hit — cache None (covered) for this file; keep all verified.
        store(test_hash, target_hash, target_symbol, None)
        return prior_verdicts

    # aggregate_covered is False — target was NOT hit.
    # Build per-test target_not_covered verdicts.
    out_verdicts: list[Verdict] = []
    first_verdict: Verdict | None = None

    for v in prior_verdicts:
        if v.kind != verified_kind:
            out_verdicts.append(v)
            continue
        verdict = Verdict(
            kind="vitest.target_not_covered",
            evidence=(
                f"vitest run completed but {target_symbol} (in "
                f"{target_file.name}, lines {target_lines.start}-{target_lines.stop - 1}) "
                f"had 0 hits in this run's V8 coverage"
            ),
            test_name=v.test_name,
        )
        out_verdicts.append(verdict)
        if first_verdict is None:
            first_verdict = verdict

    # Cache one entry for the file; broadcast on subsequent lookups.
    if first_verdict is not None:
        store(test_hash, target_hash, target_symbol, first_verdict)

    return out_verdicts
