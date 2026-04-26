"""Rule: vitest.skipped — it.skip / it.todo / xit / xtest declares a non-running test."""

from __future__ import annotations

from tree_sitter import Node

from pragma.verdict import Verdict

_SKIP_IDENTIFIERS = frozenset({"xit", "xtest"})
_SKIP_ATTRS = frozenset({"skip", "todo"})


def classify(test_node: Node, *, source: bytes, test_name: str) -> Verdict | None:
    """Flag skipped/todo/xit/xtest test declarations."""
    func = test_node.child_by_field_name("function")
    if func is None:
        return None

    if func.type == "identifier":
        name = func.text.decode("utf-8")
        if name in _SKIP_IDENTIFIERS:
            return Verdict(
                kind="vitest.skipped",
                evidence=f"{name}(...) declares a non-running test",
                test_name=test_name,
            )

    elif func.type == "member_expression":
        prop = func.child_by_field_name("property")
        obj = func.child_by_field_name("object")
        if prop is not None and obj is not None:
            attr = prop.text.decode("utf-8")
            obj_name = obj.text.decode("utf-8")
            if attr in _SKIP_ATTRS:
                return Verdict(
                    kind="vitest.skipped",
                    evidence=f"{obj_name}.{attr}(...) declares a non-running test",
                    test_name=test_name,
                )

    return None
