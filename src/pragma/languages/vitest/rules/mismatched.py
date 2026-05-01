"""Rules: vitest.mismatched and vitest.stub_error_match.

`mismatched` — test name implies error but body has no .toThrow*() / try-rethrow.
`stub_error_match` — body's only throw-assertions match stub-phrase strings
(e.g. `.rejects.toThrow("payments backend offline")`), regardless of test name.
The second pattern catches BUG-029: positive-named tests that assert on the
production stub's "not implemented" / "backend offline" error and ship green.
"""

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
    """Two-path classifier.

    Path 1 (vitest.mismatched): test name implies rejection but body has no
    real throw assertion at all.

    Path 2 (vitest.stub_error_match): body has throw assertions, but every
    `.toThrow(...)` / `.rejects.toThrow(...)` arg matches a stub phrase. Fires
    regardless of test name — a positive-named test asserting the stub's
    error message is gaming, not verifying.
    """
    callback = _get_callback(test_node)
    if callback is None:
        return None

    throw_calls = list(_walk_throw_calls(callback))
    has_try_rethrow = any(
        node.type == "try_statement" and _try_has_rethrow(node) for node in _walk(callback)
    )

    if throw_calls and not has_try_rethrow:
        stub_idents = _collect_stub_phrase_identifiers(test_node)
        all_stub = all(_to_throw_arg_is_stub(call, stub_idents) for call in throw_calls)
        if all_stub and not _has_value_assertion(callback, throw_calls):
            return Verdict(
                kind="vitest.stub_error_match",
                evidence=(
                    "test's only throw assertions are stub-shaped "
                    "(stub-phrase string, regex, bare .toThrow(), or bare Error class) "
                    "and no other expect() validates real behavior — pins the stub's "
                    "'not implemented' contract, not validated behavior"
                ),
                test_name=test_name,
            )

    if not _ERROR_NAME_RE.search(test_name):
        return None

    if _has_specific_throw_assertion(callback):
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


def _walk_throw_calls(callback: Node):
    """Yield call_expression nodes whose function is `.toThrow*` or `.rejects.toThrow*`."""
    for node in _walk(callback):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None:
            continue
        if _is_to_throw_call(func) or _is_rejects_to_throw_chain(func):
            yield node


def _has_specific_throw_assertion(callback: Node) -> bool:
    """Return True if callback contains a meaningful throw assertion.

    A `.toThrow(...)` call only counts when it's specific:
    - `.toThrow()` with no args → fine, asserts any throw.
    - `.toThrow("real validation message")` → fine.
    - `.toThrow(CustomError)` → fine.
    - `.toThrow("not implemented yet")` → not fine; matches the stub error.
    - `.toThrow(Error)` (the bare base class) → not fine; too generic.
    Try-rethrow patterns and `.rejects.toThrow*` chains follow the same logic.
    """
    if any(_to_throw_args_are_specific(call) for call in _walk_throw_calls(callback)):
        return True

    return any(node.type == "try_statement" and _try_has_rethrow(node) for node in _walk(callback))


def _to_throw_arg_is_stub(call: Node, stub_idents: frozenset[str]) -> bool:
    """Return True if the .toThrow(...) call's arg shape is stub-gaming-shaped.

    Stub shapes:
    - No args (bare `.toThrow()`) — accepts any throw, matches the stub's throw.
    - String literal containing a stub phrase (`"not implemented"`, etc.).
    - Regex literal containing a stub phrase (`/not implemented/i`).
    - Bare `Error` identifier — matches the stub's `throw new Error(...)`.
    - Identifier bound to a stub-phrase string/regex at module scope (BUG-036).
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
        return any(phrase in text for phrase in _STUB_PHRASES)

    if first.type == "regex":
        text = first.text.decode("utf-8").lower()
        return any(phrase in text for phrase in _STUB_PHRASES)

    if first.type == "identifier":
        ident = first.text.decode("utf-8")
        if ident == "Error":
            return True
        if ident in stub_idents:
            return True

    return False


def _collect_stub_phrase_identifiers(test_node: Node) -> frozenset[str]:
    """Return module-level identifiers bound to a stub-phrase string or regex.

    Catches BUG-036: `const NOT_IMPLEMENTED = /not yet implemented/;` at the
    top of the file, then `.toThrow(NOT_IMPLEMENTED)` inside the test.
    """
    root = test_node
    while root.parent is not None:
        root = root.parent

    out: set[str] = set()
    for node in _walk(root):
        if node.type not in {"variable_declarator", "assignment_expression"}:
            continue
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")
        if name_node is None or value_node is None:
            continue
        if name_node.type != "identifier":
            continue
        name = name_node.text.decode("utf-8")
        if value_node.type == "string":
            text = value_node.text.decode("utf-8").strip("\"'`").lower()
            if any(phrase in text for phrase in _STUB_PHRASES):
                out.add(name)
        elif value_node.type == "regex":
            text = value_node.text.decode("utf-8").lower()
            if any(phrase in text for phrase in _STUB_PHRASES):
                out.add(name)
    return frozenset(out)


def _has_value_assertion(callback: Node, throw_calls: list[Node]) -> bool:
    """Return True if callback contains an expect() chain that isn't a .toThrow chain.

    `expect(value).toBe(42)` / `expect(arr).toEqual([...])` / `expect(x).not.toBe(null)` —
    real value assertions. They distinguish honest tests with throw assertions from
    tests whose only verification is the throw shape.
    """
    throw_call_ids = {id(c) for c in throw_calls}
    for node in _walk(callback):
        if node.type != "call_expression":
            continue
        if id(node) in throw_call_ids:
            continue
        func = node.child_by_field_name("function")
        if func is None or func.type != "member_expression":
            continue
        if not _chain_starts_with_expect(func):
            continue
        prop = func.child_by_field_name("property")
        if prop is None:
            continue
        prop_text = prop.text.decode("utf-8")
        if prop_text.startswith("toThrow") or prop_text == "rejects" or prop_text == "resolves":
            continue
        return True
    return False


def _chain_starts_with_expect(member_expr: Node) -> bool:
    """Walk down the .object chain. True if the bottom is `expect(...)`."""
    cur = member_expr
    while cur is not None and cur.type == "member_expression":
        cur = cur.child_by_field_name("object")
    if cur is None or cur.type != "call_expression":
        return False
    fn = cur.child_by_field_name("function")
    return fn is not None and fn.type == "identifier" and fn.text.decode("utf-8") == "expect"


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
