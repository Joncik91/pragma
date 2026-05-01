"""Shared JS/TS core for Vitest, Jest, and future runners.

Each language module (`vitest/`, `jest/`) builds a `Dialect` describing its
namespace conventions, then delegates to `classify_with_dialect()` which runs
the rule chain and the file-level pass with dialect-derived strings injected.

The rule files themselves still live under `src/pragma/languages/vitest/rules/`
for now — they take an optional `dialect` kwarg that defaults to the vitest
dialect, so vitest's behavior is byte-identical and jest reuses every rule by
passing JEST_DIALECT.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pragma.languages._jsts_core.dialect import Dialect
from pragma.verdict import Verdict


def classify_with_dialect(
    path: Path, dialect: Dialect, extra_rules: tuple[Callable, ...] = ()
) -> list[Verdict]:
    """Parse `path`, run the shared rule chain and the file-level pass with
    `dialect` injected, return the verdicts.

    `extra_rules` are runner-specific rules prepended to the chain (e.g. jest's
    `test_failing` rule, which has no vitest analog).
    """
    from pragma.languages.vitest.parser import parse_file
    from pragma.languages.vitest.rules import RULES
    from pragma.languages.vitest.rules.no_success_assertion import apply_file_pass

    tree = parse_file(path)
    source = path.read_bytes()
    rules = list(extra_rules) + list(RULES)

    verdicts: list[Verdict] = []
    for test_node, test_name in _walk_test_calls(tree.root_node, dialect):
        for rule in rules:
            verdict = rule(test_node, source=source, test_name=test_name, dialect=dialect)
            if verdict is not None:
                verdicts.append(verdict)
                break
        else:
            verdicts.append(
                Verdict(
                    kind=f"{dialect.language_prefix}.verified",
                    evidence="assertion calls real symbol and asserts on return value",
                    test_name=test_name,
                )
            )
    return apply_file_pass(tree.root_node, source, path, verdicts, dialect=dialect)


def _walk_test_calls(root_node, dialect: Dialect):
    """Yield (call_expression_node, test_name_string) for every Vitest/Jest
    test call in the tree."""
    from pragma.languages.vitest import _get_string_arg

    def _walk(node):
        yield node
        for child in node.children:
            yield from _walk(child)

    for node in _walk(root_node):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None:
            continue

        is_test = False
        if func.type == "identifier":
            is_test = func.text.decode("utf-8") in dialect.test_ids
        elif func.type == "member_expression":
            base = _resolve_chain_base(func)
            if (
                base is not None
                and base.type == "identifier"
                and base.text.decode("utf-8") in dialect.test_members
            ):
                is_test = True
        if not is_test:
            continue

        args = node.child_by_field_name("arguments")
        if args is None:
            continue
        test_name = _get_string_arg(args)
        if test_name is None:
            continue
        yield node, test_name


def _resolve_chain_base(member_expr):
    """Walk down `.object` chain. Returns the bottom node (typically an identifier)."""
    cur = member_expr
    while cur is not None and cur.type == "member_expression":
        cur = cur.child_by_field_name("object")
    return cur
