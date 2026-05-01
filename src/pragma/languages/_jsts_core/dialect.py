"""Dialect config: per-runner constants injected into the shared rule chain."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Dialect:
    """Per-runner config. One instance per language module."""

    language_prefix: str
    """Prefix for verdict kinds: 'vitest' or 'jest'."""

    mock_namespace: str
    """The namespace under which mock APIs live: 'vi' (vitest) or 'jest' (jest)."""

    runner_module_substring: str
    """Lowercase substring identifying runner imports in test files. Used by
    no_success_assertion to skip the runner's own import when scanning for
    production-target imports. 'vitest' or 'jest'."""

    test_ids: frozenset[str] = field(
        default_factory=lambda: frozenset({"it", "test", "xit", "xtest"})
    )
    """Top-level test-call identifiers."""

    test_members: frozenset[str] = field(default_factory=lambda: frozenset({"it", "test"}))
    """Identifiers that can be the bottom of a member-expression test call
    (e.g. `it.skip`, `test.failing`)."""


VITEST_DIALECT = Dialect(
    language_prefix="vitest",
    mock_namespace="vi",
    runner_module_substring="vitest",
)

JEST_DIALECT = Dialect(
    language_prefix="jest",
    mock_namespace="jest",
    runner_module_substring="jest",
)
