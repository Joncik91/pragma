"""Rule: vitest.mismatched — test name implies error but body has no .toThrow*() / try-rethrow."""

from __future__ import annotations

import re

from tree_sitter import Node

from pragma.verdict import Verdict

_ERROR_NAME_RE = re.compile(r"(rejects?|raises?|refuses?|denies|throws)", re.IGNORECASE)


def classify(test_node: Node, *, source: bytes, test_name: str) -> Verdict | None:
    """Flag when test_name implies an error/rejection but the body doesn't assert it."""
    if not _ERROR_NAME_RE.search(test_name):
        return None

    callback = _get_callback(test_node)
    if callback is None:
        return None

    if _has_throw_assertion(callback):
        return None

    return Verdict(
        kind="vitest.mismatched",
        evidence="test name implies rejection but body has no .toThrow*() / try-rethrow",
        test_name=test_name,
    )


def _get_callback(test_node: Node) -> Node | None:
    args = test_node.child_by_field_name("arguments")
    if args is None:
        return None
    actual_args = [c for c in args.children if c.type not in {"(", ")", ","}]
    if len(actual_args) < 2:
        return None
    return actual_args[1]


def _has_throw_assertion(callback: Node) -> bool:
    """Return True if callback contains .toThrow*, .rejects.toThrow*, or try-rethrow."""
    for node in _walk(callback):
        # Check .toThrow*(...) calls
        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func is not None:
                if _is_to_throw_call(func):
                    return True
                # Also check .rejects.toThrow* chain:
                # expect(...).rejects.toThrow() → call_expression whose func is member_expression
                # with object being another member_expression ending in .rejects
                if _is_rejects_to_throw_chain(func):
                    return True

        # Check try-rethrow pattern
        if node.type == "try_statement" and _try_has_rethrow(node):
            return True

    return False


def _is_to_throw_call(func: Node) -> bool:
    """Return True if func is a member_expression whose property starts with 'toThrow'."""
    if func.type != "member_expression":
        return False
    prop = func.child_by_field_name("property")
    if prop is None:
        return False
    prop_text = prop.text.decode("utf-8")
    return prop_text.startswith("toThrow")


def _is_rejects_to_throw_chain(func: Node) -> bool:
    """Return True if func looks like expect(...).rejects.toThrow* — i.e.
    member_expression(property=toThrow*, object=member_expression(property=rejects))."""
    if func.type != "member_expression":
        return False
    prop = func.child_by_field_name("property")
    if prop is None or not prop.text.decode("utf-8").startswith("toThrow"):
        return False
    obj = func.child_by_field_name("object")
    if obj is None or obj.type != "member_expression":
        return False
    inner_prop = obj.child_by_field_name("property")
    if inner_prop is None:
        return False
    return inner_prop.text.decode("utf-8") == "rejects"


def _try_has_rethrow(try_node: Node) -> bool:
    """Return True if any catch clause contains a throw statement."""
    for child in try_node.children:
        if child.type == "catch_clause":
            for node in _walk(child):
                if node.type == "throw_statement":
                    return True
    return False


def _walk(node: Node):
    """Depth-first walk of all descendant nodes."""
    yield node
    for child in node.children:
        yield from _walk(child)
