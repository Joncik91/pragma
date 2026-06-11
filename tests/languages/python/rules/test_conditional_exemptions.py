"""Regression tests for Fix 1b: the python.conditional rule must not flag
legitimate loop/table-driven assertions or platform-guard assertions.

Both shapes put their `assert` inside a `for`/`if`, but the assertion DOES
run — a table-driven loop runs once per row, and a platform guard runs on the
matching platform. Flagging them is a false positive.
"""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.conditional import classify


def _func(src: str) -> ast.FunctionDef:
    return next(
        n for n in ast.walk(ast.parse(textwrap.dedent(src))) if isinstance(n, ast.FunctionDef)
    )


def _classify(func: ast.FunctionDef):
    return classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
    )


def test_table_driven_loop_over_literal_tuples_is_clean() -> None:
    func = _func("""
        def test_add_table():
            for a, b, want in [(1, 2, 3), (2, 2, 4), (0, 0, 0)]:
                assert add(a, b) == want
    """)
    assert _classify(func) is None


def test_table_driven_loop_over_literal_list_is_clean() -> None:
    func = _func("""
        def test_cases():
            for case in [{"in": 1, "out": 2}, {"in": 2, "out": 4}]:
                assert double(case["in"]) == case["out"]
    """)
    assert _classify(func) is None


def test_sys_platform_guard_is_clean() -> None:
    func = _func("""
        def test_path_sep():
            if sys.platform == "win32":
                assert sep() == "\\\\"
    """)
    assert _classify(func) is None


def test_os_environ_guard_is_clean() -> None:
    func = _func("""
        def test_env_gated():
            if os.environ.get("CI") == "1":
                assert run() == "ci-mode"
    """)
    assert _classify(func) is None


def test_genuine_dead_branch_still_flags() -> None:
    """A local boolean flag the inputs never flip is still a real evasion."""
    func = _func("""
        def test_sneaky():
            result = do_thing()
            enable_strict = False
            if enable_strict:
                assert result == 42
    """)
    verdict = _classify(func)
    assert verdict is not None
    assert verdict.kind == "python.conditional"


def test_loop_over_name_reference_still_flags() -> None:
    """A `for` over a non-literal name isn't a recognizable table — keep
    flagging (conservative: we can't prove the loop ever iterates)."""
    func = _func("""
        def test_dynamic():
            for case in get_cases():
                assert handle(case) == case.expected
    """)
    verdict = _classify(func)
    assert verdict is not None
    assert verdict.kind == "python.conditional"
