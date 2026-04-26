"""Tier 2: coverage-of-target gate.

Public entry point: `gate.classify_file(test_path, prior_verdicts, lang)`.

The tier 2 gate is an outcome-based verifier — instead of pattern-matching
the test source for gaming shapes, it runs the test under coverage
instrumentation and checks whether the production target's lines actually
executed. Every gaming pattern (mocked-away, monkeypatched, sys.modules
shim, orphan test, async-only-mock, module-attr reassign, vi.mock-namespace,
vi.spyOn, etc.) shares one property: production code never runs. One check
kills them all.

Architecture:
    gate.py    -> public classify_file(test_path, prior, lang) entry
    target.py  -> resolve (target_module, target_symbol) -> (file, line range)
    runner.py  -> run pytest/vitest under coverage, return raw coverage data
    query.py   -> read coverage data; answer "did the target lines run under this test?"
    cache.py   -> SQLite cache at .pragma/cache.db keyed by content hash

Failure-mode invariant: never block on infrastructure failure. coverage
crash, pytest collection error, target import fail, npx missing — all skip
silently and emit no tier-2 verdict. Tier 1 verdict stands. Only block on
positive `target_not_covered` outcomes.
"""
