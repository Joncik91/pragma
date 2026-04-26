"""Per-file orchestrator: walk every test_* function, classify each."""

from __future__ import annotations

import ast
from pathlib import Path

from pragma.inference import infer_expected, infer_target
from pragma.test_gaming import Verdict, classify_test

_BLOCKING_KINDS: frozenset[str] = frozenset(
    {
        "tautological",
        "mocked-away",
        "monkeypatched",
        "swallowed",
        "skipped",
        "conditional",
        "mismatched",
    }
)


def verify_file(path: Path) -> list[Verdict]:
    """Classify every `test_*` function in a single file."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    verdicts: list[Verdict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            verdicts.append(_classify_one(source, node.name))
    return verdicts


def _classify_one(source: str, test_name: str) -> Verdict:
    expected = infer_expected(test_name)
    target_module, target_symbol = infer_target(source, test_name)
    return classify_test(
        source,
        test_name=test_name,
        expected=expected,
        target_module=target_module,
        target_symbol=target_symbol,
    )


def is_blocking(verdicts: list[Verdict]) -> bool:
    """True if any verdict is in the hard-block set."""
    return any(v.kind in _BLOCKING_KINDS for v in verdicts)
