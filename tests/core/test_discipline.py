from __future__ import annotations

import textwrap
from pathlib import Path

from pragma.core.discipline import (
    check_file,
    check_source,
)


def _src(code: str) -> str:
    return textwrap.dedent(code).lstrip()


def test_complexity_within_budget_passes() -> None:
    code = _src("""
        def trivial(x):
            if x > 0:
                return 1
            return 0
    """)
    assert check_source(code, path="x.py") == []


def test_complexity_over_budget_flags() -> None:
    branches = "\n    ".join(f"if x == {i}: return {i}" for i in range(11))
    code = f"def f(x):\n    {branches}\n    return -1\n"
    violations = check_source(code, path="x.py")
    assert any(v.rule == "complexity" and v.got > 10 for v in violations)


def test_loc_per_function_over_budget() -> None:
    body = "\n    ".join(f"x = {i}" for i in range(65))
    code = f"def long_fn():\n    {body}\n"
    violations = check_source(code, path="x.py")
    assert any(v.rule == "loc_per_function" and v.got > 60 for v in violations)


def test_loc_per_file_over_budget() -> None:
    body = "\n".join(f"x{i} = {i}" for i in range(405))
    violations = check_source(body, path="x.py")
    assert any(v.rule == "loc_per_file" and v.got > 400 for v in violations)


def test_nesting_depth_over_budget() -> None:
    code = _src("""
        def f(x):
            if x:
                if x:
                    if x:
                        if x:
                            return 1
            return 0
    """)
    violations = check_source(code, path="x.py")
    assert any(v.rule == "nesting_depth" and v.got > 3 for v in violations)


def test_single_subclass_base_class_flagged() -> None:
    code = _src("""
        class Base:
            pass

        class OnlyOne(Base):
            pass
    """)
    violations = check_source(code, path="x.py")
    assert any(v.rule == "single_subclass_base" for v in violations)


def test_single_method_utility_class_flagged() -> None:
    code = _src("""
        class Util:
            def do_thing(self, x):
                return x + 1
    """)
    violations = check_source(code, path="x.py")
    assert any(v.rule == "single_method_util" for v in violations)


def test_empty_init_flagged() -> None:
    violations = check_source("", path="src/pkg/__init__.py")
    assert any(v.rule == "empty_init" for v in violations)


def test_todo_fixme_xxx_flagged() -> None:
    code = _src("""
        def f():
            # TODO: implement
            return None
    """)
    violations = check_source(code, path="x.py")
    assert any(v.rule == "todo_sentinel" for v in violations)


def test_dataclass_is_not_flagged_as_single_method(tmp_path: Path) -> None:
    code = _src("""
        from dataclasses import dataclass

        @dataclass
        class Point:
            x: int
            y: int
    """)
    violations = check_source(code, path="x.py")
    assert all(v.rule != "single_method_util" for v in violations)


def test_check_file_reads_from_disk(tmp_path: Path) -> None:
    f = tmp_path / "x.py"
    f.write_text("def ok(x): return x\n", encoding="utf-8")
    assert check_file(f) == []


def test_check_file_on_empty_init(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    init = pkg / "__init__.py"
    init.write_text("", encoding="utf-8")
    violations = check_file(init)
    assert any(v.rule == "empty_init" for v in violations)


def test_syntax_error_returns_syntax_violation() -> None:
    violations = check_source("def (", path="x.py")
    assert len(violations) == 1
    assert violations[0].rule == "syntax_error"
