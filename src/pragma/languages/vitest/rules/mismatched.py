"""Rule: vitest.mismatched — test name implies error but body has no .toThrow*() / try-rethrow."""

from __future__ import annotations

import re

from tree_sitter import Node

from pragma.verdict import Verdict

_ERROR_NAME_RE = re.compile(r"(rejects?|raises?|refuses?|denies|throws)", re.IGNORECASE)

# Stub-error message phrases. When .toThrow("...") matches one of these,
# the test is asserting the production stub's "not implemented" error
# rather than a real validation rejection — the SWE-bench gaming pattern.
# Substring match (lowercased) so "Error: not implemented yet." catches.
_STUB_PHRASES: frozenset[str] = frozenset(
    {
        "not implemented",
        "unimplemented",
        "not yet implemented",
        "todo",
        "tbd",
        "fixme",
        "stub",
        "no-op",
        "noop",
        "placeholder",
        # BUG-024: infrastructure/connectivity stub phrases
        "not connected",
        "offline",
        "not configured",
        "backend down",
        "service unavailable",
        "no api key",
        "not initialized",
    }
)


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
    """Return True if callback contains a meaningful throw assertion.

    A `.toThrow(...)` call only counts when it's specific:
    - `.toThrow()` with no args → fine, asserts any throw.
    - `.toThrow("real validation message")` → fine.
    - `.toThrow(CustomError)` → fine.
    - `.toThrow("not implemented yet")` → not fine; matches the stub error.
    - `.toThrow(Error)` (the bare base class) → not fine; too generic.
    Try-rethrow patterns and `.rejects.toThrow*` chains follow the same logic.
    """
    for node in _walk(callback):
        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func is None:
                continue
            if _is_to_throw_call(func) and _to_throw_args_are_specific(node):
                return True
            if _is_rejects_to_throw_chain(func) and _to_throw_args_are_specific(node):
                return True

        if node.type == "try_statement" and _try_has_rethrow(node):
            return True

    return False


def _to_throw_args_are_specific(call: Node) -> bool:
    """Return True when `.toThrow(...)` arg list is empty or carries a real signal.

    Empty args (no-arg `.toThrow()`) → True (asserts any throw, fine).
    String literal matching a stub phrase → False (gaming).
    Bare identifier `Error` → False (matches the stub's `throw new Error(...)`).
    Anything else → True.
    """
    args = call.child_by_field_name("arguments")
    if args is None:
        return True
    actual = [c for c in args.children if c.type not in {"(", ")", ","}]
    if not actual:
        return True
    first = actual[0]
    if first.type == "string":
        text = first.text.decode("utf-8").strip("\"'`").lower()
        if any(phrase in text for phrase in _STUB_PHRASES):
            return False
    return not (first.type == "identifier" and first.text.decode("utf-8") == "Error")


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
