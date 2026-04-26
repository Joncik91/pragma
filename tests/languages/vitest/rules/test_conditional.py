"""Tests for the vitest.conditional rule."""

from __future__ import annotations

from pathlib import Path

from pragma.languages.vitest import classify_file


def test_conditional_fires_when_all_expects_in_if(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it("conditional_test", () => {
    if (someFlag) {
        expect(result).toBe(true);
    }
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.conditional" for v in verdicts)


def test_conditional_fires_when_all_expects_in_for(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it("conditional_test", () => {
    for (let i = 0; i < 3; i++) {
        expect(results[i]).toBe(i);
    }
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.conditional" for v in verdicts)


def test_conditional_negative_expect_outside_if(tmp_path: Path) -> None:
    """Expect outside any conditional — should not fire."""
    src = """\
import { expect, it } from "vitest";
it("normal_test", () => {
    const result = doSomething();
    if (someFlag) {
        console.log("debug");
    }
    expect(result).toBe(42);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.conditional" for v in verdicts)


def test_conditional_negative_no_expects(tmp_path: Path) -> None:
    """No expects at all — should be empty_body, not conditional."""
    src = """\
import { it } from "vitest";
it("empty_test", () => {
    if (someFlag) {
        console.log("noop");
    }
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.conditional" for v in verdicts)
