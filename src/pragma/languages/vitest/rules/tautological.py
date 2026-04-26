"""Rule: vitest.tautological — expect(x).toBe(x) / expect(true).toBe(true) etc."""

from __future__ import annotations

from tree_sitter import Node

from pragma.verdict import Verdict

_MATCHERS = frozenset({"toBe", "toEqual", "toStrictEqual"})


def classify(test_node: Node, *, source: bytes, test_name: str) -> Verdict | None:
    """Flag tautological assertions: expect(X).toXxx(X) where both sides are the same."""
    callback = _get_callback(test_node)
    if callback is None:
        return None
    evidence = _find_tautological(callback)
    if evidence:
        return Verdict(kind="vitest.tautological", evidence=evidence, test_name=test_name)
    return None


def _get_callback(test_node: Node) -> Node | None:
    """Return the arrow_function / function body from the second arg of an it/test call."""
    args = test_node.child_by_field_name("arguments")
    if args is None:
        return None
    # arguments node: ( <arg0>, <arg1>, ... )
    # Skip punctuation to get actual args
    actual_args = [c for c in args.children if c.type not in {"(", ")", ","}]
    if len(actual_args) < 2:
        return None
    return actual_args[1]


def _find_tautological(callback: Node) -> str:
    """Walk the callback looking for expect(X).toBe/toEqual/toStrictEqual(X)."""
    for node in _walk(callback):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None or func.type != "member_expression":
            continue
        # func: expect(X).toBe  — object is expect(X), property is toBe
        obj = func.child_by_field_name("object")
        prop = func.child_by_field_name("property")
        if obj is None or prop is None:
            continue
        matcher = prop.text.decode("utf-8")
        if matcher not in _MATCHERS:
            continue
        # obj should be expect(X)
        if obj.type != "call_expression":
            continue
        callee = obj.child_by_field_name("function")
        if callee is None or callee.text.decode("utf-8") != "expect":
            continue
        # Get the arg to expect
        expect_args = obj.child_by_field_name("arguments")
        matcher_args = node.child_by_field_name("arguments")
        if expect_args is None or matcher_args is None:
            continue
        expect_arg = _first_arg(expect_args)
        matcher_arg = _first_arg(matcher_args)
        if expect_arg is None or matcher_arg is None:
            continue
        ev = _tautology_evidence(expect_arg, matcher_arg, matcher)
        if ev:
            return ev
    return ""


def _first_arg(args_node: Node) -> Node | None:
    actual = [c for c in args_node.children if c.type not in {"(", ")", ","}]
    return actual[0] if actual else None


def _tautology_evidence(lhs: Node, rhs: Node, matcher: str) -> str:
    lhs_text = lhs.text.decode("utf-8")
    rhs_text = rhs.text.decode("utf-8")

    # Both booleans same
    if lhs.type == "true" and rhs.type == "true":
        return f"expect(true).{matcher}(true) is constant tautology"
    if lhs.type == "false" and rhs.type == "false":
        return f"expect(false).{matcher}(false) is constant tautology"

    # Both number/string literals same value
    if lhs.type in {"number", "string"} and rhs.type == lhs.type and lhs_text == rhs_text:
        return f"expect({lhs_text}).{matcher}({rhs_text}) is constant tautology"

    # Identifier equals itself
    if lhs.type == "identifier" and rhs.type == "identifier" and lhs_text == rhs_text:
        return f"expect({lhs_text}).{matcher}({rhs_text}) is x.equals(x) tautology"

    return ""


def _walk(node: Node):
    """Depth-first walk of all descendant nodes."""
    yield node
    for child in node.children:
        yield from _walk(child)
