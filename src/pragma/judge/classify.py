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

    # Resolve production source per language. Use the existing tier-2 helpers.
    prod_source: str | None = None
    if lang.LANGUAGE == "python":
        from pragma.coverage.target import production_lines_python  # noqa: PLC0415
        from pragma.languages.python.inference import infer_target  # noqa: PLC0415

        test_source_text = test_path.read_text(encoding="utf-8")
        # Use the first verified test's target as the production-source anchor.
        # All tests in one file usually target the same module; if not, the
        # judge sees the wrong production code but emits no verdict (it'll
        # vote "verifies=true" because nothing glaringly wrong is visible).
        for v in verified_tests:
            target_module, target_symbol = infer_target(test_source_text, v.test_name)
            if target_module and target_symbol:
                target_info = production_lines_python(target_module, target_symbol)
                if target_info is not None:
                    target_file, target_lines = target_info
                    try:
                        prod_lines = target_file.read_text(encoding="utf-8").splitlines()
                        # Slice to the symbol's range
                        start = max(0, target_lines.start - 1)
                        end = min(len(prod_lines), target_lines.stop - 1)
                        prod_source = "\n".join(prod_lines[start:end])
                        break
                    except OSError:
                        continue
    elif lang.LANGUAGE == "vitest":
        from pragma.coverage.target import production_target_vitest  # noqa: PLC0415

        target = production_target_vitest(test_path)
        if target is not None:
            target_file, _target_symbol = target
            with contextlib.suppress(OSError):
                prod_source = target_file.read_text(encoding="utf-8")

    if prod_source is None:
        return prior_verdicts

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
