"""Tests for the vitest.mismatched rule."""

from __future__ import annotations

from pathlib import Path

from pragma.languages.vitest import classify_file


def test_mismatched_fires_on_ts_error_name_with_plain_assertion(tmp_path: Path) -> None:
    """TypeScript test named 'throws_...' but body only has a plain expect(..).toBe(...)."""
    src = """\
import { expect, it } from "vitest";
it("throws_on_invalid_input_but_no_assert", () => {
    const result = doSomething("bad");
    expect(result).toBe(null);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mismatched" for v in verdicts)


def test_mismatched_fires_on_ts_blockage_name_with_plain_assertion(tmp_path: Path) -> None:
    """TypeScript test named 'denies_...' but body has no .toThrow assertion."""
    src = """\
import { expect, it } from "vitest";
it("denies_bad_request", () => {
    const result = doSomething();
    expect(result).toBe(false);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mismatched" for v in verdicts)


def test_mismatched_clear_on_ts_error_name_with_toThrow_body(tmp_path: Path) -> None:
    """TypeScript test named 'throws_...' AND body uses .toThrow() — no mismatch."""
    src = """\
import { expect, it } from "vitest";
it("throws_on_invalid_input", () => {
    expect(() => doSomething("bad")).toThrow();
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mismatched" for v in verdicts)


def test_mismatched_clear_on_neutral_ts_name(tmp_path: Path) -> None:
    """TypeScript test with no error keyword in name — should not fire."""
    src = """\
import { expect, it } from "vitest";
it("handles_valid_input", () => {
    expect(doSomething("good")).toBe(true);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mismatched" for v in verdicts)


def test_mismatched_clear_on_ts_error_name_with_await_chain(tmp_path: Path) -> None:
    """TypeScript test with error keyword in TS name uses .rejects.toThrow() — no mismatch."""
    src = """\
import { expect, it } from "vitest";
it("rejects_bad_input", async () => {
    await expect(doAsyncThing("bad")).rejects.toThrow();
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mismatched" for v in verdicts)
