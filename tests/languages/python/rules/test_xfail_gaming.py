"""Tests for the python.xfail_gaming rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.xfail_gaming import classify


def _classify(src: str):
    func = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    return classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
    )


def test_fires_on_xfail_strict_true():
    src = textwrap.dedent("""
        @pytest.mark.xfail(strict=True)
        def test_x():
            assert do_thing() == 42
    """).strip()
    verdict = _classify(src)
    assert verdict is not None
    assert verdict.kind == "python.xfail_gaming"


def test_fires_on_xfail_with_exception_kwarg_and_strict_true():
    src = textwrap.dedent("""
        @pytest.mark.xfail(raises=NotImplementedError, strict=True, reason="stub")
        def test_x():
            assert do_thing() == 42
    """).strip()
    verdict = _classify(src)
    assert verdict is not None
    assert verdict.kind == "python.xfail_gaming"


def test_fires_on_bare_xfail_strict_true():
    src = textwrap.dedent("""
        @xfail(strict=True)
        def test_x():
            assert do_thing() == 42
    """).strip()
    verdict = _classify(src)
    assert verdict is not None
    assert verdict.kind == "python.xfail_gaming"


def test_does_not_fire_on_xfail_no_strict():
    src = textwrap.dedent("""
        @pytest.mark.xfail()
        def test_x():
            assert do_thing() == 42
    """).strip()
    verdict = _classify(src)
    assert verdict is None


def test_does_not_fire_on_xfail_strict_false():
    src = textwrap.dedent("""
        @pytest.mark.xfail(strict=False)
        def test_x():
            assert do_thing() == 42
    """).strip()
    verdict = _classify(src)
    assert verdict is None


def test_does_not_fire_on_undecorated_test():
    src = "def test_x(): assert do_thing() == 42"
    verdict = _classify(src)
    assert verdict is None


def test_module_level_pytestmark_xfail_strict():
    """BUG-034: pytestmark = pytest.mark.xfail(strict=True) is the same gaming."""
    src = textwrap.dedent("""
        import pytest

        pytestmark = pytest.mark.xfail(strict=True, raises=NotImplementedError)

        def test_x():
            search("")
    """).strip()
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    from pragma.languages.python.rules.xfail_gaming import classify

    v = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
        tree=tree,
    )
    assert v is not None
    assert v.kind == "python.xfail_gaming"


def test_module_level_pytestmark_list_with_xfail_strict():
    """List form: pytestmark = [pytest.mark.xfail(strict=True), other_mark]."""
    src = textwrap.dedent("""
        import pytest

        pytestmark = [
            pytest.mark.usefixtures("setup"),
            pytest.mark.xfail(strict=True, raises=NotImplementedError),
        ]

        def test_x():
            search("")
    """).strip()
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    from pragma.languages.python.rules.xfail_gaming import classify

    v = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
        tree=tree,
    )
    assert v is not None


def test_module_level_pytestmark_without_strict_does_not_fire():
    src = textwrap.dedent("""
        import pytest

        pytestmark = pytest.mark.usefixtures("setup")

        def test_x():
            search("")
    """).strip()
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    from pragma.languages.python.rules.xfail_gaming import classify

    v = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
        tree=tree,
    )
    assert v is None


def test_fires_on_xfail_strict_false_with_raises_NotImplementedError():
    """BUG-037: strict=False xfail with raises=NotImplementedError is still gaming."""
    src = textwrap.dedent("""
        @pytest.mark.xfail(raises=NotImplementedError, strict=False)
        def test_x():
            search("")
    """).strip()
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    from pragma.languages.python.rules.xfail_gaming import classify

    v = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
        tree=tree,
    )
    assert v is not None
    assert v.kind == "python.xfail_gaming"


def test_fires_on_xfail_via_variable():
    """BUG-037: stub_xfail = pytest.mark.xfail(...); @stub_xfail."""
    src = textwrap.dedent("""
        import pytest

        stub_xfail = pytest.mark.xfail(raises=NotImplementedError, strict=False)

        @stub_xfail
        def test_x():
            search("")
    """).strip()
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    from pragma.languages.python.rules.xfail_gaming import classify

    v = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
        tree=tree,
    )
    assert v is not None
    assert v.kind == "python.xfail_gaming"


def test_clear_on_xfail_with_real_raises_class():
    """xfail(raises=WeakPasswordError) on a real expected failure isn't gaming."""
    src = textwrap.dedent("""
        @pytest.mark.xfail(raises=WeakPasswordError)
        def test_x():
            login("u@e.com", "x")
    """).strip()
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    from pragma.languages.python.rules.xfail_gaming import classify

    v = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="m",
        target_symbol="s",
        tree=tree,
    )
    assert v is None
