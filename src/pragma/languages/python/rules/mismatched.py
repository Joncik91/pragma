"""Rule: python.mismatched — expected=reject but body has no pytest.raises / except."""

from __future__ import annotations

import ast

from pragma.languages.python.inference import reject_is_raise_token_only
from pragma.languages.python.rules._shared import (
    has_raises_assertion,
    has_real_value_assertion,
)
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
    if expected != "reject" or has_raises_assertion(func):
        return None
    # Reject inferred from a bare `raise(s)` token (e.g. `test_x_raises_event`)
    # is uncorroborated by name. If the body still asserts a real return value,
    # the test is honest — the name just described its subject, not an error.
    # Downgrade to a non-blocking warn instead of hard-blocking (Fix 1a).
    if reject_is_raise_token_only(test_name) and has_real_value_assertion(func):
        return Verdict(
            kind="python.mismatched_warn",
            evidence=(
                "name implies an error path but no pytest.raises / except is present; "
                "the body asserts a real return value, so treating as a warning "
                "(the `raises` token likely names the subject, not an exception)"
            ),
            test_name=test_name,
        )
    return Verdict(
        kind="python.mismatched",
        evidence="expected=reject but no pytest.raises / except assertion in body",
        test_name=test_name,
    )
