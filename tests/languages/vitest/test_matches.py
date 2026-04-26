"""Tests for the Vitest matcher (language dispatch)."""

from __future__ import annotations

from pathlib import Path

import pragma.languages.vitest as vitest_lang


def test_matches_ts_test_file_with_vitest_import(tmp_path: Path) -> None:
    f = tmp_path / "auth.test.ts"
    f.write_text('import { it, expect } from "vitest";\nit("x", () => expect(1).toBe(1));\n')
    assert vitest_lang.matches(f) is True


def test_does_not_match_jest_file(tmp_path: Path) -> None:
    f = tmp_path / "auth.test.ts"
    f.write_text('import { it, expect } from "@jest/globals";\nit("x", () => {});\n')
    assert vitest_lang.matches(f) is False


def test_does_not_match_non_test_ts(tmp_path: Path) -> None:
    f = tmp_path / "models.ts"
    f.write_text('import { it } from "vitest";\nexport const x = 1;\n')
    # No `.test.` / `/tests/` / `__tests__/` in the path.
    assert vitest_lang.matches(f) is False


def test_does_not_match_python_file(tmp_path: Path) -> None:
    f = tmp_path / "test_x.py"
    f.write_text("def test_x(): pass\n")
    assert vitest_lang.matches(f) is False


def test_matches_jsx_with_vitest(tmp_path: Path) -> None:
    f = tmp_path / "Button.spec.tsx"
    f.write_text('import { describe, it } from "vitest";\ndescribe("x", () => {});\n')
    assert vitest_lang.matches(f) is True
