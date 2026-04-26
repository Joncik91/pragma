"""Rule: vitest.swallowed — try { call(); } catch (_) {} swallows the call under test."""

from __future__ import annotations

from tree_sitter import Node

from pragma.verdict import Verdict


def classify(test_node: Node, *, source: bytes, test_name: str) -> Verdict | None:
    """Flag when:
    - The callback contains a try_statement with an empty catch (or console.* only)
    - No expect() exists OUTSIDE the try_statement
    """
    callback = _get_callback(test_node)
    if callback is None:
        return None

    try_nodes = _collect_try_statements(callback)
    if not try_nodes:
        return None

    # Check if any expect() exists outside all try blocks
    if _has_expect_outside_try(callback, try_nodes):
        return None

    # Check if any of the try blocks has a swallowed catch
    for try_node in try_nodes:
        if _has_swallowed_catch(try_node):
            return Verdict(
                kind="vitest.swallowed",
                evidence="try { call(); } catch (_) {} swallows the call under test",
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


def _collect_try_statements(callback: Node) -> list[Node]:
    """Collect all try_statement nodes within the callback."""
    results = []
    for node in _walk(callback):
        if node.type == "try_statement":
            results.append(node)
    return results


def _has_expect_outside_try(callback: Node, try_nodes: list[Node]) -> bool:
    """Return True if any expect() call is NOT inside any of the try_nodes."""
    for node in _walk(callback):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None:
            continue
        if func.type != "identifier" or func.text.decode("utf-8") != "expect":
            continue
        # Is this expect inside any try node?
        if not any(_is_descendant(node, t) for t in try_nodes):
            return True
    return False


def _has_swallowed_catch(try_node: Node) -> bool:
    """Return True if try_node's catch clause is empty or has only console.* calls."""
    for child in try_node.children:
        if child.type == "catch_clause":
            return _is_catch_swallowed(child)
    return False


def _is_catch_swallowed(catch_node: Node) -> bool:
    """Return True if catch body is empty or contains only console.* calls."""
    for child in catch_node.children:
        if child.type == "statement_block":
            stmts = [c for c in child.children if c.type not in {"{", "}", "comment"}]
            if not stmts:
                return True
            # Allow only console.* calls
            return all(_is_console_call(stmt) for stmt in stmts)
    return False


def _is_console_call(stmt: Node) -> bool:
    """Return True if stmt is an expression_statement with a console.* call."""
    if stmt.type != "expression_statement":
        return False
    for child in stmt.children:
        if child.type == "call_expression":
            func = child.child_by_field_name("function")
            if func is not None and func.type == "member_expression":
                obj = func.child_by_field_name("object")
                if obj is not None and obj.text.decode("utf-8") == "console":
                    return True
    return False


def _is_descendant(node: Node, ancestor: Node) -> bool:
    """Return True if node is ancestor or a descendant of ancestor."""
    if node is ancestor:
        return True
    return any(_is_descendant(node, child) for child in ancestor.children)


def _walk(node: Node):
    """Depth-first walk of all descendant nodes."""
    yield node
    for child in node.children:
        yield from _walk(child)
