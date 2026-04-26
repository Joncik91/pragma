"""Tests for the python.module_shimmed rule."""

from __future__ import annotations

import ast
import textwrap

from pragma.languages.python.rules.module_shimmed import classify


def _func_and_tree(src: str) -> tuple[ast.FunctionDef, ast.Module]:
    tree = ast.parse(textwrap.dedent(src).strip())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    return func, tree


# --- Positive cases ---


def test_subscript_assign_flags_when_target_matches():
    src = """
        import sys, types
        mod = types.ModuleType("orders")
        sys.modules["orders"] = mod

        def test_create_order():
            result = orders.create_order([], "c-1")
            assert isinstance(result, dict)
    """
    func, tree = _func_and_tree(src)
    verdict = classify(
        func,
        test_name="test_create_order",
        expected="success",
        target_module="orders",
        target_symbol="create_order",
        tree=tree,
    )
    assert verdict is not None
    assert verdict.kind == "python.module_shimmed"


def test_setdefault_flags_when_target_matches():
    src = """
        import sys, types
        mod = types.ModuleType("payments")
        sys.modules.setdefault("payments", mod)

        def test_pay():
            assert payments.pay(10) == "ok"
    """
    func, tree = _func_and_tree(src)
    verdict = classify(
        func,
        test_name="test_pay",
        expected="success",
        target_module="payments",
        target_symbol="pay",
        tree=tree,
    )
    assert verdict is not None
    assert verdict.kind == "python.module_shimmed"


def test_update_flags_when_target_matches():
    src = """
        import sys, types
        mod = types.ModuleType("inventory")
        sys.modules.update({"inventory": mod})

        def test_stock():
            assert inventory.stock("A") > 0
    """
    func, tree = _func_and_tree(src)
    verdict = classify(
        func,
        test_name="test_stock",
        expected="success",
        target_module="inventory",
        target_symbol="stock",
        tree=tree,
    )
    assert verdict is not None
    assert verdict.kind == "python.module_shimmed"


def test_module_type_constructor_flags_when_no_target():
    """When target_module is None, types.ModuleType at top level still flags."""
    src = """
        import sys, types
        _fake = types.ModuleType("orders")
        sys.modules["orders"] = _fake

        def test_something():
            assert orders.do() == 1
    """
    func, tree = _func_and_tree(src)
    verdict = classify(
        func,
        test_name="test_something",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=tree,
    )
    assert verdict is not None
    assert verdict.kind == "python.module_shimmed"


# --- Negative cases ---


def test_unrelated_module_does_not_flag():
    """Shimming a different module name does not flag when target is specified."""
    src = """
        import sys, types
        mod = types.ModuleType("unrelated")
        sys.modules["unrelated"] = mod

        def test_real_target():
            result = real_target.do()
            assert result == 42
    """
    func, tree = _func_and_tree(src)
    verdict = classify(
        func,
        test_name="test_real_target",
        expected="success",
        target_module="real_target",
        target_symbol="do",
        tree=tree,
    )
    assert verdict is None


def test_shim_inside_function_does_not_flag():
    """A sys.modules assignment inside a test body is not a top-level shim."""
    src = """
        def test_local_shim():
            import sys, types
            mod = types.ModuleType("orders")
            sys.modules["orders"] = mod
            import orders
            assert orders.create_order([], "c") == {}
    """
    func, tree = _func_and_tree(src)
    verdict = classify(
        func,
        test_name="test_local_shim",
        expected="success",
        target_module="orders",
        target_symbol="create_order",
        tree=tree,
    )
    assert verdict is None


def test_clean_test_does_not_flag():
    """A test with no sys.modules manipulation returns None."""
    src = """
        from orders import create_order

        def test_create_order():
            result = create_order([{"sku": "A"}], "c-1")
            assert result["order_id"] is not None
    """
    func, tree = _func_and_tree(src)
    verdict = classify(
        func,
        test_name="test_create_order",
        expected="success",
        target_module="orders",
        target_symbol="create_order",
        tree=tree,
    )
    assert verdict is None


def test_no_tree_returns_none():
    """When tree is None the rule must return None (graceful no-op)."""
    src = "def test_x(): assert 1 == 1"
    func, _ = _func_and_tree(src)
    verdict = classify(
        func,
        test_name="test_x",
        expected="success",
        target_module="mymod",
        target_symbol="myfunc",
        tree=None,
    )
    assert verdict is None
