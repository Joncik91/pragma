"""Tier 3 public entry — orchestrates prompt, client, verdict emission.

For each test that earlier tiers classified `<lang>.verified`, ask the LLM
judge whether it verifies behavior. Emit `<lang>.semantic_gaming` (warning,
NOT blocking) when the judge says no. Skip silently when the judge layer
fails for any reason.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Protocol

from pragma.judge.client import judge_test
from pragma.verdict import Verdict


class _LanguageModule(Protocol):
    LANGUAGE: str


def classify_file(
    test_path: Path,
    prior_verdicts: list[Verdict],
    lang: _LanguageModule,
) -> list[Verdict]:
    """Run tier 3 on tests `prior_verdicts` classified as verified.

    Returns prior_verdicts plus any `<lang>.semantic_gaming` warning verdicts
    the LLM judge produces. Skips silently when API key missing or call fails.
    """
    if not prior_verdicts:
        return prior_verdicts
    if lang.LANGUAGE not in {"python", "vitest"}:
        return prior_verdicts

    try:
        return _run_judge(test_path, prior_verdicts, lang)
    except Exception as exc:
        sys.stderr.write(f"[pragma:tier3] error in judge.classify_file: {exc}\n")
        return prior_verdicts


def _run_judge(
    test_path: Path, prior_verdicts: list[Verdict], lang: _LanguageModule
) -> list[Verdict]:
    """Per-language target resolution + judge call per verified test."""
    verified_kind = f"{lang.LANGUAGE}.verified"
    verified_tests = [v for v in prior_verdicts if v.kind == verified_kind]
    if not verified_tests:
        return prior_verdicts

    # Resolve production source per language. Use the existing tier-2 helpers
    # first; on miss, fall back to the test file's imports; on miss, send the
    # test alone and let the LLM judge from structure.
    prod_source: str | None = None
    if lang.LANGUAGE == "python":
        prod_source = _resolve_python_prod_source(test_path, verified_tests)
    elif lang.LANGUAGE == "vitest":
        prod_source = _resolve_vitest_prod_source(test_path)

    if prod_source is None:
        # No production source resolvable — let the LLM judge the test alone.
        # The prompt explicitly handles this: if the test asserts only on
        # mocks/literals/local fakes, that's verifies=false regardless of
        # what production code looks like.
        prod_source = "(production source not available — judge from test alone)"

    test_source = test_path.read_text(encoding="utf-8")

    new_verdicts: dict[str, Verdict] = {}
    for v in verified_tests:
        result = judge_test(prod_source, test_source, lang.LANGUAGE)
        if result is None:
            continue  # judge failed — skip silently
        verifies, reason = result
        if not verifies:
            new_verdicts[v.test_name] = Verdict(
                kind=f"{lang.LANGUAGE}.semantic_gaming",
                evidence=f"LLM judge: {reason}",
                test_name=v.test_name,
            )

    if not new_verdicts:
        return prior_verdicts

    # Insert semantic_gaming verdicts ALONGSIDE verified ones — don't replace.
    # Rationale: tier 3 is warning-only. The verified verdict still stands
    # (no blocking change); the semantic_gaming verdict surfaces the warning.
    result_verdicts: list[Verdict] = []
    for v in prior_verdicts:
        result_verdicts.append(v)
        if v.kind == verified_kind and v.test_name in new_verdicts:
            result_verdicts.append(new_verdicts[v.test_name])
    return result_verdicts


# ---------------------------------------------------------------------------
# Production-source resolution helpers
# ---------------------------------------------------------------------------


def _resolve_python_prod_source(test_path: Path, verified_tests: list[Verdict]) -> str | None:
    """Resolve production source for a Python test file.

    Tries (in order):
    1. infer_target + production_lines_python (precise — symbol's line range).
    2. Walk the test file's imports for any non-stdlib relative module on
       sys.path that the test imports; read that module's full source.
    3. Return None — caller falls back to "judge from test alone".
    """
    from pragma.coverage.target import production_lines_python  # noqa: PLC0415
    from pragma.languages.python.inference import infer_target  # noqa: PLC0415

    test_source_text = test_path.read_text(encoding="utf-8")

    # Tier 1: precise per-symbol resolution.
    for v in verified_tests:
        target_module, target_symbol = infer_target(test_source_text, v.test_name)
        if target_module and target_symbol:
            target_info = production_lines_python(target_module, target_symbol)
            if target_info is not None:
                target_file, target_lines = target_info
                with contextlib.suppress(OSError):
                    prod_lines = target_file.read_text(encoding="utf-8").splitlines()
                    start = max(0, target_lines.start - 1)
                    end = min(len(prod_lines), target_lines.stop - 1)
                    return "\n".join(prod_lines[start:end])

    # Tier 2 fallback: walk the test's imports, find a sibling production file.
    return _find_sibling_python_module(test_path, test_source_text)


def _find_sibling_python_module(test_path: Path, test_source_text: str) -> str | None:
    """Find a production module imported by the test that lives next to it.

    Walks the test file's `import X` and `from X import ...` statements,
    skips stdlib + test-only prefixes, and looks for `<X>.py` in:
    - the test's parent dir
    - the test's grandparent dir (so `tests/test_x.py` finds `../x.py`)
    """
    import ast  # noqa: PLC0415
    import sys  # noqa: PLC0415

    try:
        tree = ast.parse(test_source_text)
    except SyntaxError:
        return None

    candidate_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            candidate_modules.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            candidate_modules.append(node.module.split(".")[0])

    # Filter out stdlib + obvious test-only.
    skip = set(sys.stdlib_module_names) | {"pytest", "mock", "unittest", "tests"}
    candidates = [m for m in candidate_modules if m and m not in skip]

    search_dirs = [test_path.parent, test_path.parent.parent]
    for module_name in candidates:
        for d in search_dirs:
            candidate = d / f"{module_name}.py"
            if candidate.exists() and candidate != test_path:
                with contextlib.suppress(OSError):
                    return candidate.read_text(encoding="utf-8")
    return None


def _resolve_vitest_prod_source(test_path: Path) -> str | None:
    """Resolve production source for a Vitest test file.

    Tries production_target_vitest first; falls back to scanning the test's
    relative imports and reading the first existing `.ts`/`.js` file.
    """
    from pragma.coverage.target import production_target_vitest  # noqa: PLC0415

    target = production_target_vitest(test_path)
    if target is not None:
        target_file, _target_symbol = target
        with contextlib.suppress(OSError):
            return target_file.read_text(encoding="utf-8")

    # Fallback: scan the test for relative import statements and try each.
    return _find_sibling_vitest_module(test_path)


def _find_sibling_vitest_module(test_path: Path) -> str | None:
    """Walk the test's `import ... from "<rel>"` statements and read the first
    sibling `.ts`/`.tsx`/`.js`/`.jsx` file that exists on disk."""
    import re  # noqa: PLC0415

    try:
        text = test_path.read_text(encoding="utf-8")
    except OSError:
        return None

    # Capture relative imports: from "./foo" or from "../bar"
    pattern = re.compile(r"""from\s+['"](\.\.?/[^'"]+)['"]""")
    for match in pattern.finditer(text):
        rel = match.group(1)
        # Skip vitest itself if someone wrote `from "./vitest-helper"` etc.
        if "vitest" in rel.lower():
            continue
        base = (test_path.parent / rel).resolve()
        for ext in (".ts", ".tsx", ".js", ".jsx", ""):
            candidate = base.with_suffix(ext) if ext else base
            if candidate.exists() and candidate != test_path:
                with contextlib.suppress(OSError):
                    return candidate.read_text(encoding="utf-8")
    return None
