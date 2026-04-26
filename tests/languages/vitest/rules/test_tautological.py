"""Tests for the vitest.tautological rule."""

from __future__ import annotations

from pathlib import Path

from pragma.languages.vitest import classify_file


def test_tautological_true_toBe_true(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it("always_passes", () => {
    expect(true).toBe(true);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.tautological" for v in verdicts)


def test_tautological_number_toEqual_same(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it("number_taut", () => {
    expect(42).toEqual(42);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.tautological" for v in verdicts)


def test_tautological_identifier_toBe_itself(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it("id_taut", () => {
    const x = doSomething();
    expect(x).toBe(x);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.tautological" for v in verdicts)


def test_tautological_clean_test_gets_verified(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it("clean_test", () => {
    const result = doSomething();
    expect(result).toBe(42);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.verified" for v in verdicts)
    assert not any(v.kind == "vitest.tautological" for v in verdicts)
