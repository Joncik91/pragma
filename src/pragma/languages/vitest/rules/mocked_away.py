"""Rule: <lang>.mocked-away — assertion on a vi.mock()ed / jest.mock()ed symbol tests the mock."""

from __future__ import annotations

from tree_sitter import Node

from pragma.languages._jsts_core.dialect import VITEST_DIALECT, Dialect
from pragma.verdict import Verdict

_MOCK_METHODS: frozenset[str] = frozenset(
    {
        "mockReturnValue",
        "mockReturnValueOnce",
        "mockImplementation",
        "mockImplementationOnce",
        "mockResolvedValue",
        "mockResolvedValueOnce",
        "mockRejectedValue",
        "mockRejectedValueOnce",
    }
)


def classify(
    test_node: Node,
    *,
    source: bytes,
    test_name: str,
    dialect: Dialect = VITEST_DIALECT,
) -> Verdict | None:
    """Flag when the test body calls and asserts on a mocked symbol.

    Two detection paths:
    1. <ns>.mock("./path") at module level + import { X } from "./path"
    2. <ns>.spyOn(<alias>, "<sym>").mock*(...) where alias is from
       ``import * as <alias> from "./path"``
    """
    ns = dialect.mock_namespace
    kind = f"{dialect.language_prefix}.mocked-away"

    root = _find_program_root(test_node)
    if root is None:
        return None

    # Find the callback
    callback = _get_callback(test_node)
    if callback is None:
        return None

    # --- Path 1: vi.mock(...) at module level ---
    mocked_paths = _collect_vi_mock_paths(root, ns)
    if mocked_paths:
        imports_by_path = _collect_imports(root)
        for path in mocked_paths:
            if path not in imports_by_path:
                continue
            imported_names = imports_by_path[path]
            for symbol in imported_names:
                if _body_calls_and_asserts_symbol(callback, symbol):
                    evidence = (
                        f"{ns}.mock on '{path}' + assertion on {symbol}(...)"
                        f" — testing the mock, not the implementation"
                    )
                    return Verdict(kind=kind, evidence=evidence, test_name=test_name)

    # --- Path 2: vi.spyOn(<alias>, "<sym>").mock*(...) ---
    namespace_imports = _collect_namespace_imports(root)
    if namespace_imports:
        spyon_targets = _collect_spyon_replacements(callback, ns)
        for alias, symbol in spyon_targets:
            if alias not in namespace_imports:
                continue
            module_path = namespace_imports[alias]
            if _body_calls_and_asserts_member(callback, alias, symbol):
                evidence = (
                    f"{ns}.spyOn({alias}, '{symbol}').mock*(...) on '{module_path}'"
                    f" + assertion on {alias}.{symbol}(...)"
                    f" — testing the mock, not the implementation"
                )
                return Verdict(kind=kind, evidence=evidence, test_name=test_name)

    # --- Path 3: vi.mock(<path>) + import * as <alias> (namespace import) ---
    if mocked_paths:
        if not namespace_imports:
            namespace_imports = _collect_namespace_imports(root)
        path_to_aliases: dict[str, list[str]] = {}
        for alias, path in namespace_imports.items():
            path_to_aliases.setdefault(path, []).append(alias)
        for path in mocked_paths:
            for alias in path_to_aliases.get(path, []):
                for symbol in _collect_member_calls_on(callback, alias):
                    if _body_calls_and_asserts_member(callback, alias, symbol):
                        evidence = (
                            f"{ns}.mock on {path!r} + assertion on {alias}.{symbol}(...)"
                            f" — testing the mock, not the implementation"
                        )
                        return Verdict(kind=kind, evidence=evidence, test_name=test_name)

    return None


def _find_program_root(node: Node) -> Node | None:
    """Walk up to the program (root) node."""
    current = node
    while current.parent is not None:
        current = current.parent
    return current if current.type == "program" else None


def _collect_vi_mock_paths(root: Node, ns: str = "vi") -> set[str]:
    """Find all top-level <ns>.mock("./path", ...) calls and return the module paths."""
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
            if obj.text.decode("utf-8") != ns:
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


def _collect_bound_names(callback: Node, symbol: str) -> set[str]:
    """Return variable names bound to a call of <symbol>(...) in the callback.

    Walks the callback for:
      - ``lexical_declaration``  (const / let)
      - ``variable_declaration`` (var)
    containing a ``variable_declarator`` whose ``value`` is a
    ``call_expression`` whose ``function`` text equals ``symbol``.
    """
    bound: set[str] = set()
    for node in _walk(callback):
        if node.type not in {"lexical_declaration", "variable_declaration"}:
            continue
        for child in node.children:
            if child.type != "variable_declarator":
                continue
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            if name_node is None or value_node is None:
                continue
            if value_node.type != "call_expression":
                continue
            fn = value_node.child_by_field_name("function")
            if fn is None:
                continue
            if fn.text.decode("utf-8") == symbol:
                bound.add(name_node.text.decode("utf-8"))
    return bound


def _body_calls_and_asserts_symbol(callback: Node, symbol: str) -> bool:
    """Return True if the callback body contains expect(symbol(...)).toXxx(...)
    or const/let/var result = symbol(...); expect(result).toXxx(...)."""
    # Pass 1: collect variable names bound to symbol(...)
    bound_names = _collect_bound_names(callback, symbol)

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
        # The arg to expect should be symbol(...) directly, or a bound name
        expect_args = obj.child_by_field_name("arguments")
        if expect_args is None:
            continue
        actual = [c for c in expect_args.children if c.type not in {"(", ")", ","}]
        if not actual:
            continue
        inner = actual[0]
        # Case A: expect(symbol(...)).toXxx(...)  — original behaviour
        if inner.type == "call_expression":
            inner_func = inner.child_by_field_name("function")
            if inner_func is not None and inner_func.text.decode("utf-8") == symbol:
                return True
        # Case B: expect(result).toXxx(...) where result was bound to symbol(...)
        if inner.type == "identifier" and inner.text.decode("utf-8") in bound_names:
            return True
    return False


def _collect_namespace_imports(root: Node) -> dict[str, str]:
    """Map namespace alias -> module path for ``import * as <alias> from "..."``."""
    result: dict[str, str] = {}
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
        # Find namespace_import: import_clause > namespace_import > identifier
        import_clause = child.child_by_field_name("import")
        if import_clause is None:
            for node in child.children:
                if node.type == "import_clause":
                    import_clause = node
                    break
        if import_clause is None:
            continue
        for node in _walk(import_clause):
            if node.type == "namespace_import":
                for sub in node.children:
                    if sub.type == "identifier":
                        result[sub.text.decode("utf-8")] = module_path
                        break
                break
    return result


def _collect_spyon_replacements(callback: Node, ns: str = "vi") -> set[tuple[str, str]]:
    """Walk callback for ``<ns>.spyOn(<alias>, "<sym>").<mock*>(...)`` chains.

    Returns a set of (alias, symbol) pairs where a mock* method is chained.
    Plain ``<ns>.spyOn(...)`` without a mock* chain is excluded (observation only).
    """
    targets: set[tuple[str, str]] = set()
    for node in _walk(callback):
        # Looking for: call_expression whose function is a member_expression
        # with property in _MOCK_METHODS, and whose object is the <ns>.spyOn call.
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None or func.type != "member_expression":
            continue
        prop = func.child_by_field_name("property")
        if prop is None or prop.text.decode("utf-8") not in _MOCK_METHODS:
            continue
        # The object of the member_expression must be the <ns>.spyOn(...) call
        obj = func.child_by_field_name("object")
        if obj is None or obj.type != "call_expression":
            continue
        spyon_pair = _extract_spyon_args(obj, ns)
        if spyon_pair is not None:
            targets.add(spyon_pair)
    return targets


def _extract_spyon_args(call_node: Node, ns: str = "vi") -> tuple[str, str] | None:
    """If call_node is ``<ns>.spyOn(<alias>, "<sym>")``, return (alias, sym)."""
    spyon_func = call_node.child_by_field_name("function")
    if spyon_func is None or spyon_func.type != "member_expression":
        return None
    vi_obj = spyon_func.child_by_field_name("object")
    vi_prop = spyon_func.child_by_field_name("property")
    if vi_obj is None or vi_prop is None:
        return None
    if vi_obj.text.decode("utf-8") != ns:
        return None
    if vi_prop.text.decode("utf-8") != "spyOn":
        return None
    args = call_node.child_by_field_name("arguments")
    if args is None:
        return None
    actual = [c for c in args.children if c.type not in {"(", ")", ","}]
    if len(actual) < 2:
        return None
    alias_node = actual[0]
    sym_node = actual[1]
    if alias_node.type != "identifier":
        return None
    alias = alias_node.text.decode("utf-8")
    # sym_node is a string literal
    if sym_node.type != "string":
        return None
    sym: str | None = None
    for child in sym_node.children:
        if child.type == "string_fragment":
            sym = child.text.decode("utf-8")
    if sym is None:
        return None
    return alias, sym


def _collect_bound_names_member(callback: Node, alias: str, symbol: str) -> set[str]:
    """Return variable names bound to ``<alias>.<symbol>(...)`` calls.

    Also handles ``await <alias>.<symbol>(...)`` (async tests).
    """
    bound: set[str] = set()
    member_text = f"{alias}.{symbol}"
    for node in _walk(callback):
        if node.type not in {"lexical_declaration", "variable_declaration"}:
            continue
        for child in node.children:
            if child.type != "variable_declarator":
                continue
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            if name_node is None or value_node is None:
                continue
            # Unwrap await_expression if present
            actual_value = value_node
            if actual_value.type == "await_expression":
                # The child after the 'await' keyword is the expression
                non_await = [c for c in actual_value.children if c.type != "await"]
                actual_value = non_await[0] if non_await else actual_value
            if actual_value.type != "call_expression":
                continue
            fn = actual_value.child_by_field_name("function")
            if fn is None:
                continue
            if fn.text.decode("utf-8") == member_text:
                bound.add(name_node.text.decode("utf-8"))
    return bound


def _body_calls_and_asserts_member(callback: Node, alias: str, symbol: str) -> bool:
    """Return True if callback has expect(<alias>.<symbol>(...)).toXxx(...)
    or const r = <alias>.<symbol>(...); expect(r).toXxx(...)."""
    member_text = f"{alias}.{symbol}"
    bound_names = _collect_bound_names_member(callback, alias, symbol)

    for node in _walk(callback):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None or func.type != "member_expression":
            continue
        obj = func.child_by_field_name("object")
        if obj is None or obj.type != "call_expression":
            continue
        callee = obj.child_by_field_name("function")
        if callee is None or callee.text.decode("utf-8") != "expect":
            continue
        expect_args = obj.child_by_field_name("arguments")
        if expect_args is None:
            continue
        actual = [c for c in expect_args.children if c.type not in {"(", ")", ","}]
        if not actual:
            continue
        inner = actual[0]
        # Case A: expect(<alias>.<symbol>(...)).toXxx(...)
        if inner.type == "call_expression":
            inner_func = inner.child_by_field_name("function")
            if inner_func is not None and inner_func.text.decode("utf-8") == member_text:
                return True
        # Case B: expect(result).toXxx(...) where result was bound to <alias>.<symbol>(...)
        if inner.type == "identifier" and inner.text.decode("utf-8") in bound_names:
            return True
    return False


def _collect_member_calls_on(callback: Node, alias: str) -> set[str]:
    """Return the set of property names called as ``<alias>.<prop>(...)`` in callback.

    Walks the callback for ``call_expression`` nodes whose ``function`` is a
    ``member_expression`` with ``object`` equal to the identifier ``alias``.
    Only direct calls (not chained ones like ``foo.bar.baz()``) are collected.
    """
    symbols: set[str] = set()
    for node in _walk(callback):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None or func.type != "member_expression":
            continue
        obj = func.child_by_field_name("object")
        prop = func.child_by_field_name("property")
        if obj is None or prop is None:
            continue
        if obj.type != "identifier":
            continue
        if obj.text.decode("utf-8") != alias:
            continue
        symbols.add(prop.text.decode("utf-8"))
    return symbols


def _walk(node: Node):
    """Depth-first walk of all descendant nodes."""
    yield node
    for child in node.children:
        yield from _walk(child)
