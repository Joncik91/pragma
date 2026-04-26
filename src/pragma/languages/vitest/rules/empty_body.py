"""Rule: vitest.empty_body — test body has no expect() and no assert call."""

from __future__ import annotations

from tree_sitter import Node

from pragma.verdict import Verdict


def classify(test_node: Node, *, source: bytes, test_name: str) -> Verdict | None:
    """Flag when the test callback has no expect() or assert.* call."""
    callback = _get_callback(test_node)
    if callback is None:
        return None
    if not _has_any_assertion(callback):
        return Verdict(
            kind="vitest.empty_body",
            evidence="test body has no expect() and no assert",
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


def _has_any_assertion(callback: Node) -> bool:
    """Return True if any expect(...) or assert.* call exists anywhere in the callback."""
    for node in _walk(callback):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None:
            continue
        # Direct expect(...) call
        if func.type == "identifier" and func.text.decode("utf-8") == "expect":
            return True
        # assert.something(...) call
        if func.type == "member_expression":
            obj = func.child_by_field_name("object")
            if obj is not None and obj.text.decode("utf-8") == "assert":
                return True
    return False


def _walk(node: Node):
    """Depth-first walk of all descendant nodes."""
    yield node
    for child in node.children:
        yield from _walk(child)
