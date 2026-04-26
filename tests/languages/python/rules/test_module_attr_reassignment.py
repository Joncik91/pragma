"""Tests for the python.module_attr_reassignment rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.module_attr_reassignment import classify


def test_module_level_reassignment_fires():
    """import pricing; pricing.discount = stub at module level → flags."""
    src = textwrap.dedent("""
        import pricing

        def _stub(amount, code):
            return amount * 0.9

        pricing.discount = _stub

        def test_discount():
            assert pricing.discount(100.0, "SAVE10") == 90.0
    """).strip()
    tree = ast.parse(src)
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_discount"
    )
    verdict = classify(
        func,
        test_name="test_discount",
        expected="success",
        target_module="pricing",
        target_symbol="discount",
        tree=tree,
    )
    assert verdict is not None
    assert verdict.kind == "python.module_attr_reassignment"


def test_test_body_reassignment_fires():
    """pricing.discount = stub inside test function body → flags."""
    src = textwrap.dedent("""
        import pricing

        def test_discount():
            pricing.discount = lambda amount, code: amount * 0.9
            assert pricing.discount(100.0, "SAVE10") == 90.0
    """).strip()
    tree = ast.parse(src)
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_discount"
    )
    verdict = classify(
        func,
        test_name="test_discount",
        expected="success",
        target_module="pricing",
        target_symbol="discount",
        tree=tree,
    )
    assert verdict is not None
    assert verdict.kind == "python.module_attr_reassignment"


def test_dotted_target_module_root_resolution():
    """import pricing.utils + pricing.utils.discount = stub (dotted target_module) → flags."""
    src = textwrap.dedent("""
        import pricing.utils

        def _stub(amount, code):
            return amount * 0.9

        pricing.utils.discount = _stub

        def test_discount():
            assert pricing.utils.discount(100.0, "SAVE10") == 90.0
    """).strip()
    tree = ast.parse(src)
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_discount"
    )
    verdict = classify(
        func,
        test_name="test_discount",
        expected="success",
        target_module="pricing.utils",
        target_symbol="discount",
        tree=tree,
    )
    assert verdict is not None
    assert verdict.kind == "python.module_attr_reassignment"


def test_different_module_does_not_fire():
    """other.discount = stub when target is pricing.discount → does NOT flag."""
    src = textwrap.dedent("""
        import pricing
        import other

        other.discount = lambda amount, code: amount * 0.9

        def test_discount():
            assert pricing.discount(100.0, "SAVE10") == 90.0
    """).strip()
    tree = ast.parse(src)
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_discount"
    )
    verdict = classify(
        func,
        test_name="test_discount",
        expected="success",
        target_module="pricing",
        target_symbol="discount",
        tree=tree,
    )
    assert verdict is None


def test_different_symbol_does_not_fire():
    """pricing.helper = stub when target symbol is discount → does NOT flag."""
    src = textwrap.dedent("""
        import pricing

        pricing.helper = lambda x: x

        def test_discount():
            assert pricing.discount(100.0, "SAVE10") == 90.0
    """).strip()
    tree = ast.parse(src)
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_discount"
    )
    verdict = classify(
        func,
        test_name="test_discount",
        expected="success",
        target_module="pricing",
        target_symbol="discount",
        tree=tree,
    )
    assert verdict is None


def test_identity_assignment_does_not_fire():
    """pricing.discount = pricing.discount (no-op) → does NOT flag."""
    src = textwrap.dedent("""
        import pricing

        pricing.discount = pricing.discount

        def test_discount():
            assert pricing.discount(100.0, "SAVE10") == 90.0
    """).strip()
    tree = ast.parse(src)
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_discount"
    )
    verdict = classify(
        func,
        test_name="test_discount",
        expected="success",
        target_module="pricing",
        target_symbol="discount",
        tree=tree,
    )
    assert verdict is None


def test_clean_test_does_not_fire():
    """No reassignment → does NOT flag."""
    src = textwrap.dedent("""
        import pricing

        def test_discount():
            assert pricing.discount(100.0, "SAVE10") == 90.0
    """).strip()
    tree = ast.parse(src)
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_discount"
    )
    verdict = classify(
        func,
        test_name="test_discount",
        expected="success",
        target_module="pricing",
        target_symbol="discount",
        tree=tree,
    )
    assert verdict is None


def test_no_target_module_does_not_fire():
    """target_module is None → does NOT flag."""
    src = textwrap.dedent("""
        import pricing

        pricing.discount = lambda amount, code: amount * 0.9

        def test_discount():
            assert pricing.discount(100.0, "SAVE10") == 90.0
    """).strip()
    tree = ast.parse(src)
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_discount"
    )
    verdict = classify(
        func,
        test_name="test_discount",
        expected="success",
        target_module=None,
        target_symbol="discount",
        tree=tree,
    )
    assert verdict is None


def test_no_target_symbol_does_not_fire():
    """target_symbol is None → does NOT flag."""
    src = textwrap.dedent("""
        import pricing

        pricing.discount = lambda amount, code: amount * 0.9

        def test_discount():
            assert pricing.discount(100.0, "SAVE10") == 90.0
    """).strip()
    tree = ast.parse(src)
    func = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_discount"
    )
    verdict = classify(
        func,
        test_name="test_discount",
        expected="success",
        target_module="pricing",
        target_symbol=None,
        tree=tree,
    )
    assert verdict is None
