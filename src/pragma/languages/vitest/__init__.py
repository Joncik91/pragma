"""Vitest language plugin for Pragma.

Conforms to `pragma.languages._protocol.Classifier`.
"""

from __future__ import annotations

import re
from pathlib import Path

from pragma.languages.vitest.parser import parse_file as parse_file  # re-export
from pragma.verdict import Verdict

LANGUAGE = "vitest"

_EXTS = frozenset({".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"})
_TEST_NAME_PATTERN = re.compile(r"(?:^|/)(?:.+\.(?:test|spec)\.|tests?/|__tests__/)")
_VITEST_IMPORT = re.compile(rb'from\s+["\']vitest["\']|require\(\s*["\']vitest["\']')

# Top-level test call identifiers
_TEST_IDS = frozenset({"it", "test", "xit", "xtest"})
# Member call objects (it.skip, test.todo, etc.)
_TEST_MEMBERS = frozenset({"it", "test"})
_TEST_ATTRS = frozenset({"skip", "todo", "each", "only", "concurrent", "sequential"})


def matches(path: Path) -> bool:
    """True when path is a Vitest test file."""
    if path.suffix not in _EXTS:
        return False
    if not _TEST_NAME_PATTERN.search(str(path)):
        return False
    try:
        head = path.read_bytes()[:4096]
    except OSError:
        return False
    return bool(_VITEST_IMPORT.search(head))


def _get_string_arg(args_node) -> str | None:
    """Extract the first string-literal argument text from an arguments node."""
    actual = [c for c in args_node.children if c.type not in {"(", ")", ","}]
    if not actual:
        return None
    first = actual[0]
    if first.type == "string":
        for child in first.children:
            if child.type == "string_fragment":
                return child.text.decode("utf-8")
        return ""
    if first.type == "template_string":
        # grab raw template content minus backticks
        raw = first.text.decode("utf-8")
        return raw.strip("`")
    return None


def _walk_test_calls(root):
    """Yield (call_node, test_name_str) for every it/test/xit/xtest declaration."""
    for node in _walk_nodes(root):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None:
            continue
        # Check if it's a test declaration (identifier or member expression)
        if func.type == "identifier":
            name = func.text.decode("utf-8")
            if name not in _TEST_IDS:
                continue
        elif func.type == "member_expression":
            obj = func.child_by_field_name("object")
            prop = func.child_by_field_name("property")
            if obj is None or prop is None:
                continue
            obj_name = obj.text.decode("utf-8")
            prop_name = prop.text.decode("utf-8")
            if obj_name not in _TEST_MEMBERS or prop_name not in _TEST_ATTRS:
                continue
            # it.each returns a function that is then called — skip it (not a test declaration)
            # We accept it.skip, it.todo, it.only, etc.
        else:
            continue
        args = node.child_by_field_name("arguments")
        if args is None:
            continue
        test_name = _get_string_arg(args)
        if test_name is None:
            continue
        yield node, test_name


def _walk_nodes(node):
    """Depth-first walk of all nodes."""
    yield node
    for child in node.children:
        yield from _walk_nodes(child)


def classify_file(path: Path) -> list[Verdict]:
    """Classify every Vitest test call in `path`, then apply the file-level
    no_success_assertion pass over the resulting verdicts."""
    from pragma.languages.vitest.rules import RULES
    from pragma.languages.vitest.rules.no_success_assertion import apply_file_pass

    tree = parse_file(path)
    source = path.read_bytes()
    verdicts: list[Verdict] = []
    for test_node, test_name in _walk_test_calls(tree.root_node):
        for rule in RULES:
            verdict = rule(test_node, source=source, test_name=test_name)
            if verdict is not None:
                verdicts.append(verdict)
                break
        else:
            verdicts.append(
                Verdict(
                    kind="vitest.verified",
                    evidence="assertion calls real symbol and asserts on return value",
                    test_name=test_name,
                )
            )
    return apply_file_pass(tree.root_node, source, path, verdicts)
