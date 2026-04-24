from __future__ import annotations

# AST discipline rules — budget/got carry real numeric meaning.
_DISCIPLINE_RULES: dict[str, str] = {
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

# User-facing error codes raised by the CLI. budget/got are ignored;
# the text is the guidance. Covers the codes a user actually hits
# under pre-commit / pre-push / CI. Unknown codes fall through to a
# generic placeholder below.
_ERROR_CODES: dict[str, str] = {
    "commit_shape_violation": (
        "Commit message fails shape. Requirements: subject ≤72 chars, a "
        "blank line before the body, a WHY: paragraph explaining the "
        "motivation, and a Co-Authored-By: trailer. Amend the commit "
        "(git commit --amend) and retry."
    ),
    "unlock_missing_tests": (
        "Required tests are missing. Every permutation declared in the "
        "active slice needs a red test named "
        "`test_req_<req_id>_<permutation_id>` under the tests_root. "
        "Add the missing ones (still failing; pragma unlock refuses if "
        "they already pass) and retry."
    ),
    "unlock_test_passing": (
        "Expected-failing tests are already green. A red-phase test "
        "must assert something the implementation does not yet "
        "provide. Either revert the premature implementation, or "
        "drop the permutation from pragma.yaml if it genuinely has "
        "no reject shape to test."
    ),
    "slice_already_shipped": (
        "That slice has already shipped. Shipped slices are terminal. "
        "Pass --force to deliberately reopen (loses the ship record "
        "and breaks dep-gated slices downstream), or pick a different "
        "slice."
    ),
    "slice_already_active": (
        "A different slice is already active. Complete it with "
        "pragma slice complete, cancel it with pragma slice cancel, "
        "or pass --force to switch."
    ),
    "gate_hash_drift": (
        "State references an older manifest hash than the lockfile. "
        "The manifest was rewritten without re-activating the slice. "
        "pragma slice cancel (if active) or pragma doctor "
        '--emergency-unlock --reason "..." to reset.'
    ),
    "manifest_hash_mismatch": (
        "pragma.yaml and pragma.lock.json disagree. Run pragma freeze "
        "to regenerate the lock, then commit both files."
    ),
    "manifest_schema_error": (
        "pragma.yaml does not match the schema. Check milestones "
        "declare slices, slices declare requirements, permutations "
        "have id + description + expected (success|reject)."
    ),
    "requirement_unassigned": (
        "A requirement has no milestone or slice assignment. Add "
        "milestone: MNN and slice: MNN.SN under the requirement in "
        "pragma.yaml."
    ),
    "integrity_mismatch": (
        ".claude/settings.json has drifted from its sealed hash. If "
        "the change is intentional, pragma hooks seal to re-seal. If "
        "not, git checkout -- .claude/settings.json to restore."
    ),
    "milestone_dep_unshipped": (
        "The target slice's milestone depends on an upstream milestone "
        "that has unshipped slices. Finish every slice of the dep "
        "milestone (activate, unlock, complete) before activating this "
        "one."
    ),
}


def get_remediation(rule: str, *, budget: int, got: int) -> str:
    template = _DISCIPLINE_RULES.get(rule)
    if template is not None:
        return template.format(rule=rule, budget=budget, got=got)
    text = _ERROR_CODES.get(rule)
    if text is not None:
        return text
    # Fallback — preserve the v0.1.0 template so any caller that
    # previously relied on the exact format still gets a non-empty
    # string. Unknown rule names land here.
    generic = (
        "Rule '{rule}' triggered: got {got}, budget {budget}. "
        "Review and adjust the code to meet the budget."
    )
    return generic.format(rule=rule, budget=budget, got=got)
