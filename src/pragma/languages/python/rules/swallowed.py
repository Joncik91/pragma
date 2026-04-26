"""Rule: python.swallowed — try/except:pass swallows the call under test."""

from __future__ import annotations

import ast

from pragma.languages.python.rules._shared import is_docstring_stmt, node_inside_any
from pragma.verdict import Verdict


def classify(
    func: ast.FunctionDef,
    *,
    test_name: str,
    expected: str,
    target_module: str | None,
    target_symbol: str | None,
    **_: object,
) -> Verdict | None:
    if _swallows_call(func):
        return Verdict(
            kind="python.swallowed",
            evidence="`try: <call>; except: pass` swallows the call under test",
            test_name=test_name,
        )
    return None


def _swallows_call(func: ast.FunctionDef) -> bool:
    """True when the body wraps the system-under-test in a try/except: pass.

    Conservative: only fires when the function has at least one `Try` whose
    handler body is just `pass` (or `pass` + a docstring), AND the function
    has no plain `assert` statements outside that try. A test that does
    real work after the try is not swallowed.
    """
    tries_with_pass_only = [
        n
        for n in ast.walk(func)
        if isinstance(n, ast.Try)
        and n.handlers
        and all(_handler_only_passes(h) for h in n.handlers)
    ]
    if not tries_with_pass_only:
        return False
    # If the function has any `assert` outside the swallowing tries, it's
    # not just-swallow gaming — let the assert be classified normally.
    asserts_outside = [
        a
        for a in ast.walk(func)
        if isinstance(a, ast.Assert) and not node_inside_any(a, tries_with_pass_only)
    ]
    return not asserts_outside


def _handler_only_passes(handler: ast.ExceptHandler) -> bool:
    """True when `except: pass` (or with only a docstring + pass)."""
    body = [s for s in handler.body if not is_docstring_stmt(s)]
    return len(body) == 1 and isinstance(body[0], ast.Pass)
