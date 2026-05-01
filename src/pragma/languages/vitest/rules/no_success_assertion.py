"""Rule: vitest.no_success_assertion — file-level structural check.

Universal property every stub-pinning evasion violates:

    A test file that imports a production target must contain at least one test
    that calls the target and asserts on a real return value.

This is a file-level pass that runs after per-test rules. It replaces residual
`vitest.verified` (and a small set of stub-pinning per-test verdicts) with
`vitest.no_success_assertion` when the file fails the predicate.
"""

from __future__ import annotations

import re
from pathlib import Path

from tree_sitter import Node

from pragma.languages._jsts_core.dialect import VITEST_DIALECT, Dialect
from pragma.languages.vitest.rules.mismatched import (
    _STUB_PHRASES,
    _walk,
)
from pragma.verdict import Verdict

# Replacement-eligible verdict suffixes (without language prefix). Built per call
# from `dialect.language_prefix`.
_REPLACE_SUFFIXES: frozenset[str] = frozenset(
    {"verified", "stub_error_match", "skipped", "mismatched", "swallowed"}
)


def _allowed_replacements(prefix: str) -> frozenset[str]:
    return frozenset(f"{prefix}.{s}" for s in _REPLACE_SUFFIXES)


# Back-compat: existing imports of ALLOWED_REPLACEMENTS still resolve, defaulted to vitest.
ALLOWED_REPLACEMENTS: frozenset[str] = _allowed_replacements("vitest")

_REJECT_RE = re.compile(r"(rejects?|raises?|refuses?|denies|throws)", re.IGNORECASE)

# Matchers that count as a real return-value assertion. Excludes
# .toThrow*, .toBeUndefined, .toBeNull, .toBeFalsy, .toBeTruthy
# (the last three are too generic to count).
_VALUE_MATCHERS: frozenset[str] = frozenset(
    {
        "toBe",
        "toEqual",
        "toStrictEqual",
        "toMatch",
        "toMatchObject",
        "toMatchInlineSnapshot",
        "toMatchSnapshot",
        "toBeCloseTo",
        "toBeGreaterThan",
        "toBeGreaterThanOrEqual",
        "toBeLessThan",
        "toBeLessThanOrEqual",
        "toContain",
        "toContainEqual",
        "toHaveProperty",
        "toHaveLength",
        "toHaveBeenCalled",
        "toHaveBeenCalledWith",
        "toHaveBeenCalledTimes",
        "toHaveReturned",
        "toHaveReturnedWith",
    }
)


def apply_file_pass(
    root_node: Node,
    source: bytes,
    test_path: Path,
    prior_verdicts: list[Verdict],
    dialect: Dialect = VITEST_DIALECT,
) -> list[Verdict]:
    """Replace eligible verdicts with <lang>.no_success_assertion when the file
    has imported production targets but no test asserts on a real return value
    (and the file isn't a pure-validator file)."""
    imported = _imported_targets(root_node, test_path, dialect.runner_module_substring)
    if not imported:
        return prior_verdicts
    if _file_has_success_assertion(root_node, imported):
        return prior_verdicts
    if _is_pure_validator_file(root_node, imported):
        return prior_verdicts

    sample = sorted(imported)[:3]
    suffix = "..." if len(imported) > 3 else ""
    evidence = (
        f"file imports {sample}{suffix} but no test calls the target and asserts "
        "on a real return value — every test in this file pins the stub's "
        "failure-mode contract"
    )
    allowed = _allowed_replacements(dialect.language_prefix)
    new_kind = f"{dialect.language_prefix}.no_success_assertion"
    return [
        Verdict(kind=new_kind, evidence=evidence, test_name=v.test_name) if v.kind in allowed else v
        for v in prior_verdicts
    ]


def _imported_targets(
    root_node: Node, test_path: Path, runner_substring: str = "vitest"
) -> set[str]:
    """Return identifiers from `import { a, b } from "<rel>"` where <rel>
    resolves to a sibling file. Also `import X from "<rel>"` (default).
    Skips runner-self imports (`from "vitest"` / `from "@jest/globals"`).
    """
    out: set[str] = set()
    for node in _walk(root_node):
        if node.type != "import_statement":
            continue
        src = _import_source(node)
        if not src or not src.startswith("."):
            continue
        if runner_substring in src.lower():
            continue
        # Resolve to verify it's a sibling (skip if no file exists — defensive,
        # this is just used to filter out broken imports).
        base = (test_path.parent / src).resolve()
        resolved = False
        for ext in (".ts", ".tsx", ".js", ".jsx", ""):
            candidate = base.with_suffix(ext) if ext else base
            if candidate.exists() and candidate != test_path:
                resolved = True
                break
        if not resolved:
            continue
        # Collect import clause identifiers.
        for clause in _walk(node):
            if clause.type == "named_imports":
                for spec in clause.children:
                    if spec.type == "import_specifier":
                        name_node = spec.child_by_field_name("name")
                        alias_node = spec.child_by_field_name("alias")
                        target = alias_node or name_node
                        if target is not None and target.type == "identifier":
                            out.add(target.text.decode("utf-8"))
            elif clause.type == "import_clause":
                # Default import: `import X from "..."`
                for child in clause.children:
                    if child.type == "identifier":
                        out.add(child.text.decode("utf-8"))
    return out


def _import_source(import_node: Node) -> str | None:
    for child in import_node.children:
        if child.type == "string":
            return child.text.decode("utf-8").strip("\"'`")
    return None


def _file_has_success_assertion(root_node: Node, imported: set[str]) -> bool:
    """True if any test callback contains expect(call_to_target).<value-matcher>(...)."""
    # File-level instance bindings: `let r: Router`, `const r = new Router()`,
    # `r = new Router()` in any beforeEach. Treat these as additional targets.
    file_aliases = _collect_file_level_target_aliases(root_node, imported)
    pool = imported | file_aliases
    for test_node in _walk_test_calls(root_node):
        callback = _get_callback(test_node)
        if callback is None:
            continue
        if _real_return_assertion_in(callback, pool):
            return True
    return False


def _collect_file_level_target_aliases(root_node: Node, imported: set[str]) -> set[str]:
    """Find identifiers bound to instances of imported classes anywhere in the file.

    Catches three common patterns:
    - `let r: Router` (declared in outer describe)
    - `const r = new Router()` (file-level or describe-level)
    - `r = new Router()` (inside beforeEach)
    """
    out: set[str] = set()
    for node in _walk(root_node):
        # let/const r: Router (typed declaration)
        if node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            if name_node is None or name_node.type != "identifier":
                continue
            value_node = node.child_by_field_name("value")
            if value_node is not None and _value_uses_target(value_node, imported):
                out.add(name_node.text.decode("utf-8"))
                continue
            # type annotation: `let r: Router`
            for child in node.children:
                if child.type != "type_annotation":
                    continue
                for sub in _walk(child):
                    if (
                        sub.type in {"type_identifier", "identifier"}
                        and sub.text.decode("utf-8") in imported
                    ):
                        out.add(name_node.text.decode("utf-8"))
                        break
        # assignment_expression: `r = new Router()`
        if node.type == "assignment_expression":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None or left.type != "identifier":
                continue
            if _value_uses_target(right, imported):
                out.add(left.text.decode("utf-8"))
    return out


def _real_return_assertion_in(callback: Node, imported: set[str]) -> bool:
    """True if the callback (a) exercises an imported target AND (b) makes at
    least one value-matcher expect(...) call.

    Exercises = imported target appears as a Call, instantiation, or member
    access (e.g. `new TargetClass()`, `target(args)`, `bus.method()` where bus
    is a TargetClass instance).

    Value-matcher expect = any expect(...).<matcher>(...) where matcher is in
    _VALUE_MATCHERS. Specifically excludes .toThrow*, .toBeUndefined,
    .toBeNull, .toBeFalsy, .toBeTruthy.
    """
    if not _exercises_target(callback, imported):
        return False
    for node in _walk(callback):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None or func.type != "member_expression":
            continue
        prop = func.child_by_field_name("property")
        if prop is None:
            continue
        if prop.text.decode("utf-8") not in _VALUE_MATCHERS:
            continue
        # Confirm the chain bottoms out at `expect(...)`.
        if _chain_starts_with_expect(func):
            return True
    return False


def _exercises_target(callback: Node, imported: set[str]) -> bool:
    """True when the callback contains a Call/instantiation/member-access of an
    imported target (or an alias bound from such a call)."""
    aliases = _collect_target_aliases(callback, imported)
    pool = imported | aliases
    for node in _walk(callback):
        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func is None:
                continue
            if func.type == "identifier" and func.text.decode("utf-8") in pool:
                return True
            if func.type == "member_expression":
                obj = func.child_by_field_name("object")
                if (
                    obj is not None
                    and obj.type == "identifier"
                    and obj.text.decode("utf-8") in pool
                ):
                    return True
        if node.type == "new_expression":
            ctor = node.child_by_field_name("constructor")
            if (
                ctor is not None
                and ctor.type == "identifier"
                and ctor.text.decode("utf-8") in imported
            ):
                return True
    return False


def _chain_starts_with_expect(member_expr: Node) -> bool:
    """Walk down `.object` chain. True if the bottom is `expect(...)`."""
    cur = member_expr
    while cur is not None and cur.type == "member_expression":
        cur = cur.child_by_field_name("object")
    if cur is None or cur.type != "call_expression":
        return False
    fn = cur.child_by_field_name("function")
    return fn is not None and fn.type == "identifier" and fn.text.decode("utf-8") == "expect"


def _collect_target_aliases(callback: Node, imported: set[str]) -> set[str]:
    """Return variable names assigned from a call to one of the imported targets.

    Catches `const r = parse(s);` then `expect(r).toEqual(...)`.
    """
    out: set[str] = set()
    for node in _walk(callback):
        if node.type != "variable_declarator":
            continue
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")
        if name_node is None or value_node is None:
            continue
        if name_node.type != "identifier":
            continue
        # Look for a Call inside the value that uses an imported target.
        if not _value_uses_target(value_node, imported):
            continue
        out.add(name_node.text.decode("utf-8"))
    return out


def _value_uses_target(value: Node, imported: set[str]) -> bool:
    for node in _walk(value):
        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func is None:
                continue
            if func.type == "identifier" and func.text.decode("utf-8") in imported:
                return True
            if func.type == "member_expression":
                obj = func.child_by_field_name("object")
                if (
                    obj is not None
                    and obj.type == "identifier"
                    and obj.text.decode("utf-8") in imported
                ):
                    return True
        if node.type == "new_expression":
            ctor = node.child_by_field_name("constructor")
            if (
                ctor is not None
                and ctor.type == "identifier"
                and ctor.text.decode("utf-8") in imported
            ):
                return True
    return False


def _is_pure_validator_file(root_node: Node, imported: set[str]) -> bool:
    """All tests reject-named AND every .toThrow(...) uses a custom error class."""
    test_calls = list(_walk_test_calls(root_node))
    if not test_calls:
        return False
    for test_node in test_calls:
        test_name = _get_test_name(test_node)
        if test_name is None or not _REJECT_RE.search(test_name):
            return False
    stub_idents = _collect_stub_phrase_identifiers(root_node)
    for test_node in test_calls:
        callback = _get_callback(test_node)
        if callback is None:
            continue
        for throw_call in _walk_throw_calls(callback):
            args = throw_call.child_by_field_name("arguments")
            if args is None:
                return False
            actual = [c for c in args.children if c.type not in {"(", ")", ","}]
            if not actual:
                return False
            first = actual[0]
            if first.type == "identifier":
                ident = first.text.decode("utf-8")
                if ident == "Error":
                    return False
            elif first.type == "string":
                text = first.text.decode("utf-8").strip("\"'`").lower()
                if any(p in text for p in _STUB_PHRASES):
                    return False
            elif first.type == "regex":
                text = first.text.decode("utf-8").lower()
                if any(p in text for p in _STUB_PHRASES):
                    return False
            if first.type == "identifier" and first.text.decode("utf-8") in stub_idents:
                return False
    return True


def _walk_throw_calls(callback: Node):
    for node in _walk(callback):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None or func.type != "member_expression":
            continue
        prop = func.child_by_field_name("property")
        if prop is None:
            continue
        if prop.text.decode("utf-8").startswith("toThrow"):
            yield node


def _collect_stub_phrase_identifiers(root_node: Node) -> set[str]:
    """Module-level identifiers bound to a stub-phrase string or regex."""
    out: set[str] = set()
    for node in _walk(root_node):
        if node.type not in {"variable_declarator", "assignment_expression"}:
            continue
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")
        if name_node is None or value_node is None or name_node.type != "identifier":
            continue
        name = name_node.text.decode("utf-8")
        if value_node.type == "string":
            text = value_node.text.decode("utf-8").strip("\"'`").lower()
            if any(p in text for p in _STUB_PHRASES):
                out.add(name)
        elif value_node.type == "regex":
            text = value_node.text.decode("utf-8").lower()
            if any(p in text for p in _STUB_PHRASES):
                out.add(name)
    return out


def _walk_test_calls(root_node: Node):
    """Yield call_expression nodes that look like `it("...", () => ...)` etc."""
    for node in _walk(root_node):
        if node.type != "call_expression":
            continue
        func = node.child_by_field_name("function")
        if func is None:
            continue
        if func.type == "identifier" and func.text.decode("utf-8") in {"it", "test"}:
            yield node
        elif func.type == "member_expression":
            obj = func.child_by_field_name("object")
            prop = func.child_by_field_name("property")
            if obj is None or prop is None:
                continue
            if (
                obj.type == "identifier"
                and obj.text.decode("utf-8") in {"it", "test"}
                and prop.text.decode("utf-8") in {"only", "skip", "todo"}
            ):
                yield node


def _get_test_name(test_node: Node) -> str | None:
    args = test_node.child_by_field_name("arguments")
    if args is None:
        return None
    for child in args.children:
        if child.type == "string":
            return child.text.decode("utf-8").strip("\"'`")
    return None


def _get_callback(test_node: Node) -> Node | None:
    args = test_node.child_by_field_name("arguments")
    if args is None:
        return None
    actual = [c for c in args.children if c.type not in {"(", ")", ","}]
    if len(actual) < 2:
        return None
    return actual[1]
