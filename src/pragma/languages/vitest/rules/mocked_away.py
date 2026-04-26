"""Rule: vitest.mocked-away — assertion on a vi.mock()ed symbol tests the mock."""

from __future__ import annotations

from tree_sitter import Node

from pragma.verdict import Verdict


def classify(test_node: Node, *, source: bytes, test_name: str) -> Verdict | None:
    """Flag when all four conditions hold:
    1. vi.mock("./path") at module level
    2. import { X } from "./path" for the same path
    3. test body calls X(...)
    4. test body has expect(X(...)).toXxx(...)
    """
    root = _find_program_root(test_node)
    if root is None:
        return None

    # Collect top-level vi.mock paths
    mocked_paths = _collect_vi_mock_paths(root)
    if not mocked_paths:
        return None

    # Collect imports per module path
    imports_by_path = _collect_imports(root)

    # Find the callback
    callback = _get_callback(test_node)
    if callback is None:
        return None

    # For each mocked path that is also imported, check if the test uses + asserts on it
    for path in mocked_paths:
        if path not in imports_by_path:
            continue
        imported_names = imports_by_path[path]
        for symbol in imported_names:
            if _body_calls_and_asserts_symbol(callback, symbol):
                evidence = (
                    f"vi.mock on '{path}' + assertion on {symbol}(...)"
                    f" — testing the mock, not the implementation"
                )
                return Verdict(kind="vitest.mocked-away", evidence=evidence, test_name=test_name)
    return None


def _find_program_root(node: Node) -> Node | None:
    """Walk up to the program (root) node."""
    current = node
    while current.parent is not None:
        current = current.parent
    return current if current.type == "program" else None


def _collect_vi_mock_paths(root: Node) -> set[str]:
    """Find all top-level vi.mock("./path", ...) calls and return the module paths."""
    paths: set[str] = set()
    for child in root.children:
        # Must be top-level: expression_statement containing a call_expression
        if child.type != "expression_statement":
            continue
        for node in child.children:
            if node.type != "call_expression":
                continue
            func = node.child_by_field_name("function")
            if func is None or func.type != "member_expression":
                continue
            obj = func.child_by_field_name("object")
            prop = func.child_by_field_name("property")
            if obj is None or prop is None:
                continue
            if obj.text.decode("utf-8") != "vi":
                continue
            if prop.text.decode("utf-8") != "mock":
                continue
            args = node.child_by_field_name("arguments")
            if args is None:
                continue
            path_str = _extract_string_arg(args)
            if path_str is not None:
                paths.add(path_str)
    return paths


def _collect_imports(root: Node) -> dict[str, set[str]]:
    """Map module path -> set of imported names for named imports."""
    result: dict[str, set[str]] = {}
    for child in root.children:
        if child.type != "import_statement":
            continue
        # Find the from-string
        module_path: str | None = None
        for node in child.children:
            if node.type == "string":
                for frag in node.children:
                    if frag.type == "string_fragment":
                        module_path = frag.text.decode("utf-8")
        if module_path is None:
            continue
        # Find the imported names
        import_clause = child.child_by_field_name("import")
        if import_clause is None:
            # fallback: find import_clause by type
            for node in child.children:
                if node.type == "import_clause":
                    import_clause = node
                    break
        if import_clause is None:
            continue
        names = _extract_named_imports(import_clause)
        if names:
            result.setdefault(module_path, set()).update(names)
    return result


def _extract_named_imports(import_clause: Node) -> set[str]:
    """Extract identifiers from a named_imports clause."""
    names: set[str] = set()
    for node in _walk(import_clause):
        if node.type == "named_imports":
            for child in node.children:
                if child.type == "import_specifier":
                    # The local name is the last identifier
                    idents = [c for c in child.children if c.type == "identifier"]
                    if idents:
                        names.add(idents[-1].text.decode("utf-8"))
    return names


def _extract_string_arg(args_node: Node) -> str | None:
    """Get the first string literal from an arguments node."""
    actual = [c for c in args_node.children if c.type not in {"(", ")", ","}]
    if not actual:
        return None
    first = actual[0]
    if first.type == "string":
        for child in first.children:
            if child.type == "string_fragment":
                return child.text.decode("utf-8")
    return None


def _get_callback(test_node: Node) -> Node | None:
    """Return the second argument (callback) from the test call."""
    args = test_node.child_by_field_name("arguments")
    if args is None:
        return None
    actual_args = [c for c in args.children if c.type not in {"(", ")", ","}]
    if len(actual_args) < 2:
        return None
    return actual_args[1]


def _body_calls_and_asserts_symbol(callback: Node, symbol: str) -> bool:
    """Return True if the callback body contains expect(symbol(...)).toXxx(...)."""
    for node in _walk(callback):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None or func.type != "member_expression":
            continue
        obj = func.child_by_field_name("object")
        if obj is None or obj.type != "call_expression":
            continue
        # obj should be expect(...)
        callee = obj.child_by_field_name("function")
        if callee is None or callee.text.decode("utf-8") != "expect":
            continue
        # The arg to expect should be symbol(...)
        expect_args = obj.child_by_field_name("arguments")
        if expect_args is None:
            continue
        actual = [c for c in expect_args.children if c.type not in {"(", ")", ","}]
        if not actual:
            continue
        inner = actual[0]
        if inner.type != "call_expression":
            continue
        inner_func = inner.child_by_field_name("function")
        if inner_func is None:
            continue
        if inner_func.text.decode("utf-8") == symbol:
            return True
    return False


def _walk(node: Node):
    """Depth-first walk of all descendant nodes."""
    yield node
    for child in node.children:
        yield from _walk(child)
