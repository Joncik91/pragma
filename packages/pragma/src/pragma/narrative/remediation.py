from __future__ import annotations

_REMEDIATIONS: dict[str, str] = {
    "complexity": (
        "Function complexity is {got}, exceeding budget of {budget}. "
        "Extract helper functions to bring complexity within budget. "
        "Consider: early returns, guard clauses, or splitting into smaller functions."
    ),
    "nesting_depth": (
        "Nesting depth is {got}, exceeding budget of {budget}. "
        "Flatten the control flow using early returns, guard clauses, "
        "or extract nested logic into well-named helper functions."
    ),
    "loc_per_function": (
        "Function body is {got} lines, exceeding budget of {budget}. "
        "Split into smaller, focused functions. Each function should do one thing."
    ),
}


def get_remediation(rule: str, *, budget: int, got: int) -> str:
    template = _REMEDIATIONS.get(
        rule,
        "Rule '{rule}' triggered: got {got}, budget {budget}. "
        "Review and adjust the code to meet the budget.",
    )
    return template.format(rule=rule, budget=budget, got=got)
