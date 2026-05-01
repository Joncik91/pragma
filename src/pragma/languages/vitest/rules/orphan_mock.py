"""Rule: <lang>.orphan_mock — assert on a <ns>.fn()'s configured return value."""

from __future__ import annotations

from tree_sitter import Node

from pragma.languages._jsts_core.dialect import VITEST_DIALECT, Dialect
from pragma.verdict import Verdict

# vi.fn() chained mock methods that set a return literal
_MOCK_METHODS = frozenset(
    {
        "mockReturnValue",
        "mockReturnValueOnce",
        "mockResolvedValue",
        "mockResolvedValueOnce",
        "mockRejectedValue",
        "mockRejectedValueOnce",
        "mockImplementation",
        "mockImplementationOnce",
    }
)

_MATCHERS = frozenset({"toBe", "toEqual", "toStrictEqual"})


def classify(
    test_node: Node,
    *,
    source: bytes,
    test_name: str,
    dialect: Dialect = VITEST_DIALECT,
) -> Verdict | None:
    """Flag orphan mock assertions: const m = <ns>.fn().<mock*>(L); expect(m(...)).toXxx(L)."""
    callback = _get_callback(test_node)
    if callback is None:
        return None

    # Phase 1: collect orphan mock bindings: {mock_name: literal_bytes}
    orphan_mocks = _collect_orphan_mocks(callback, dialect.mock_namespace)
    if not orphan_mocks:
        return None

    # Phase 2: collect result bindings — variables assigned by calling an orphan mock:
    #   const result = mock("u1")  OR  const result = await mock("u1")
    # Maps result_var_name -> (mock_name, literal_bytes)
    result_bindings = _collect_result_bindings(callback, orphan_mocks)

    # Phase 3: look for expect(<x>).toXxx(<lit>) where:
    #   - <x> is a call to an orphan mock directly, OR an identifier in result_bindings
    #   - <lit> byte-matches the captured literal
    evidence = _find_orphan_assertion(callback, orphan_mocks, result_bindings)
    if evidence is None:
        return None

    return Verdict(
        kind=f"{dialect.language_prefix}.orphan_mock", evidence=evidence, test_name=test_name
    )


def _get_callback(test_node: Node) -> Node | None:
    """Return the arrow_function / function body from the second arg of an it/test call."""
    args = test_node.child_by_field_name("arguments")
    if args is None:
        return None
    actual_args = [c for c in args.children if c.type not in {"(", ")", ","}]
    if len(actual_args) < 2:
        return None
    return actual_args[1]


def _collect_orphan_mocks(callback: Node, ns: str = "vi") -> dict[str, bytes]:
    """Walk for `const <name> = <ns>.fn().<mock*>(<literal>)` declarations.

    Returns {name: literal_bytes} for each binding found.
    """
    result: dict[str, bytes] = {}
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
            if name_node.type != "identifier":
                continue
            literal = _extract_vi_fn_mock_literal(value_node, ns)
            if literal is None:
                continue
            result[name_node.text.decode("utf-8")] = literal
    return result


def _collect_result_bindings(
    callback: Node, orphan_mocks: dict[str, bytes]
) -> dict[str, tuple[str, bytes]]:
    """Walk for `const <result> = <mock_name>(...)` or `const <result> = await <mock_name>(...)`.

    Returns {result_var: (mock_name, literal_bytes)}.
    """
    result: dict[str, tuple[str, bytes]] = {}
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
            if name_node.type != "identifier":
                continue
            mock_name = _extract_mock_call_name(value_node)
            if mock_name is None or mock_name not in orphan_mocks:
                continue
            result[name_node.text.decode("utf-8")] = (mock_name, orphan_mocks[mock_name])
    return result


def _extract_vi_fn_mock_literal(node: Node, ns: str = "vi") -> bytes | None:
    """If node is `<ns>.fn().<mockMethod>(<literal>)`, return the literal bytes; else None.

    Shape (from AST inspection):
      call_expression
        function: member_expression
          object: call_expression  (<ns>.fn())
            function: member_expression
              object: identifier '<ns>'
              property: property_identifier 'fn'
            arguments: '()'
          property: property_identifier '<mockMethod>'
        arguments: '(' <literal> ')'
    """
    if node.type != "call_expression":
        return None

    func = node.child_by_field_name("function")
    if func is None or func.type != "member_expression":
        return None

    obj = func.child_by_field_name("object")
    prop = func.child_by_field_name("property")
    if obj is None or prop is None:
        return None

    mock_method = prop.text.decode("utf-8")
    if mock_method not in _MOCK_METHODS:
        return None

    # obj must be <ns>.fn() — a call_expression whose function is '<ns>.fn'
    if not _is_vi_fn_call(obj, ns):
        return None

    args = node.child_by_field_name("arguments")
    if args is None:
        return None
    actual_args = [c for c in args.children if c.type not in {"(", ")", ","}]
    if not actual_args:
        return None

    return actual_args[0].text


def _is_vi_fn_call(node: Node, ns: str = "vi") -> bool:
    """True when node is the call_expression `<ns>.fn()`."""
    if node.type != "call_expression":
        return False
    func = node.child_by_field_name("function")
    if func is None or func.type != "member_expression":
        return False
    vi_obj = func.child_by_field_name("object")
    fn_prop = func.child_by_field_name("property")
    if vi_obj is None or fn_prop is None:
        return False
    ns_bytes = ns.encode("utf-8")
    return vi_obj.type == "identifier" and vi_obj.text == ns_bytes and fn_prop.text == b"fn"


def _find_orphan_assertion(
    callback: Node,
    orphan_mocks: dict[str, bytes],
    result_bindings: dict[str, tuple[str, bytes]],
) -> str | None:
    """Walk for `expect(<x>).toXxx(<lit>)` where <x> is an orphan mock call or result binding."""
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

        matcher = prop.text.decode("utf-8")
        if matcher not in _MATCHERS:
            continue

        # obj must be expect(...)
        if obj.type != "call_expression":
            continue
        callee = obj.child_by_field_name("function")
        if callee is None or callee.text.decode("utf-8") != "expect":
            continue

        expect_args = obj.child_by_field_name("arguments")
        matcher_args = node.child_by_field_name("arguments")
        if expect_args is None or matcher_args is None:
            continue

        expect_arg = _first_arg(expect_args)
        matcher_arg = _first_arg(matcher_args)
        if expect_arg is None or matcher_arg is None:
            continue

        # Determine expected literal bytes from the expect argument
        mock_name: str | None = None
        captured_literal: bytes | None = None

        # Case A: expect(<name>(...)) or expect(await <name>(...)) — direct call
        direct_call_name = _extract_mock_call_name(expect_arg)
        if direct_call_name is not None and direct_call_name in orphan_mocks:
            mock_name = direct_call_name
            captured_literal = orphan_mocks[direct_call_name]

        # Case B: expect(<result>) where result was bound to a mock call
        elif expect_arg.type == "identifier" and expect_arg.text.decode("utf-8") in result_bindings:
            result_var = expect_arg.text.decode("utf-8")
            mock_name, captured_literal = result_bindings[result_var]

        if mock_name is None or captured_literal is None:
            continue

        # matcher_arg must byte-match the captured literal
        if matcher_arg.text != captured_literal:
            continue

        lit_text = captured_literal.decode("utf-8")
        return (
            f"expect({mock_name}(...)).{matcher}({lit_text}) asserts the mock returns "
            f"its own configured value — mock is never wired to a production symbol"
        )

    return None


def _extract_mock_call_name(node: Node) -> str | None:
    """If node is `<name>(...)` or `await <name>(...)`, return name; else None."""
    if node.type == "call_expression":
        func = node.child_by_field_name("function")
        if func is not None and func.type == "identifier":
            return func.text.decode("utf-8")
    if node.type == "await_expression":
        # children: [await, <expr>]
        for child in node.children:
            if child.type == "call_expression":
                func = child.child_by_field_name("function")
                if func is not None and func.type == "identifier":
                    return func.text.decode("utf-8")
    return None


def _first_arg(args_node: Node) -> Node | None:
    actual = [c for c in args_node.children if c.type not in {"(", ")", ","}]
    return actual[0] if actual else None


def _walk(node: Node):
    """Depth-first walk of all descendant nodes."""
    yield node
    for child in node.children:
        yield from _walk(child)
