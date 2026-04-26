"""Step 1 sanity tests — confirm the tier-2 module tree imports cleanly.

Real behavior tests land in subsequent steps. This file just verifies
that the scaffold doesn't break the suite (every module imports without
side effects, public functions are callable with their stub signatures).
"""

from __future__ import annotations

from pathlib import Path

from pragma.coverage import cache, gate, query, runner, target
from pragma.judge import classify, client, prompt  # noqa: F401
from pragma.verdict import Verdict


def test_gate_classify_file_returns_prior_verdicts_unchanged() -> None:
    """Step 1 stub: `gate.classify_file` is a pass-through."""
    prior = [Verdict(kind="python.verified", evidence="stub", test_name="t1")]

    class _StubLang:
        LANGUAGE = "python"

        def matches(self, _path: Path) -> bool:
            return True

    out = gate.classify_file(Path("/tmp/x.py"), prior, _StubLang())
    assert out == prior


def test_target_resolvers_return_none_until_step_2() -> None:
    assert target.production_lines_python(None, None) is None
    assert target.production_lines_python("missing_module", "fn") is None
    assert target.production_target_vitest(Path("/tmp/x.test.ts")) is None


def test_runner_stubs_return_none() -> None:
    assert runner.run_python_with_coverage(Path("/tmp/x.py"), Path("/tmp/y.py")) is None
    assert runner.run_vitest_with_coverage(Path("/tmp/x.test.ts"), Path("/tmp/y.ts")) is None


def test_query_stubs_return_empty_dict() -> None:
    assert query.query_python_coverage(Path("/tmp/db"), Path("/tmp/y.py"), range(0, 10)) == {}
    assert query.query_vitest_coverage(Path("/tmp/json"), Path("/tmp/y.ts"), range(0, 10)) == {}


def test_cache_lookup_returns_miss_sentinel() -> None:
    assert cache.lookup("a", "b", "c") is cache.MISS


def test_judge_classify_returns_prior_verdicts() -> None:
    prior = [Verdict(kind="python.verified", evidence="stub", test_name="t1")]

    class _StubLang:
        LANGUAGE = "python"

    out = classify.classify_file(Path("/tmp/x.py"), prior, _StubLang())
    assert out == prior
