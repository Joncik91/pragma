"""Rule: <lang>.conditional — all expect() calls live inside conditional branches."""

from __future__ import annotations

from tree_sitter import Node

from pragma.languages._jsts_core.dialect import VITEST_DIALECT, Dialect
from pragma.verdict import Verdict

_CONDITIONAL_KINDS = frozenset(
    {
        "if_statement",
        "for_statement",
        "for_in_statement",
        "while_statement",
        "do_statement",
        "switch_statement",
    }
)


def classify(
    test_node: Node,
    *,
    source: bytes,
    test_name: str,
    dialect: Dialect = VITEST_DIALECT,
) -> Verdict | None:
    """Flag when at least one expect() exists AND every expect() is inside a conditional."""
    callback = _get_callback(test_node)
    if callback is None:
        return None

    expect_nodes = _collect_expect_calls(callback)
    if not expect_nodes:
        return None  # empty_body handles this

    # Check every expect is nested inside a conditional node within the callback
    if all(_is_inside_conditional(exp, callback) for exp in expect_nodes):
        return Verdict(
            kind=f"{dialect.language_prefix}.conditional",
            evidence="all expect() calls live inside conditional branches",
            test_name=test_name,
        )
    return None


def _get_callback(test_node: Node) -> Node | None:
    args = test_node.child_by_field_name("arguments")
    if args is None:
        return None
    actual_args = [c for c in args.children if c.type not in {"(", ")", ","}]
    if len(actual_args) < 2:
        return None
    return actual_args[1]


def _collect_expect_calls(callback: Node) -> list[Node]:
    """Collect all call_expression nodes whose function is `expect`."""
    results = []
    for node in _walk(callback):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is not None and func.type == "identifier" and func.text.decode("utf-8") == "expect":
            results.append(node)
    return results


def _is_inside_conditional(target: Node, root: Node) -> bool:
    """Return True if `target` has an ancestor that is a conditional, within `root`."""
    # Walk root tracking whether we're inside a conditional
    return _check_inside(target, root, inside_conditional=False)


def _check_inside(target: Node, current: Node, *, inside_conditional: bool) -> bool:
    """Recursive search: returns True if target is found while inside_conditional."""
    if current is target:
        return inside_conditional
    now_in_conditional = inside_conditional or current.type in _CONDITIONAL_KINDS
    for child in current.children:
        if _contains(child, target) and _check_inside(
            target, child, inside_conditional=now_in_conditional
        ):
            return True
    return False


def _contains(node: Node, target: Node) -> bool:
    """Return True if target is a descendant (or equal) of node."""
    if node is target:
        return True
    return any(_contains(child, target) for child in node.children)


def _walk(node: Node):
    """Depth-first walk of all descendant nodes."""
    yield node
    for child in node.children:
        yield from _walk(child)
