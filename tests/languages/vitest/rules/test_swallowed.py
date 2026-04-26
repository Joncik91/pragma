"""Tests for the vitest.swallowed rule."""

from __future__ import annotations

from pathlib import Path

from pragma.languages.vitest import classify_file


def test_swallowed_fires_on_empty_catch(tmp_path: Path) -> None:
    src = """\
import { it } from "vitest";
it("swallow_test", () => {
    try {
        doThing();
    } catch (e) {}
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.swallowed" for v in verdicts)


def test_swallowed_fires_on_console_only_catch(tmp_path: Path) -> None:
    src = """\
import { it } from "vitest";
it("swallow_console", () => {
    try {
        doThing();
    } catch (e) {
        console.error(e);
    }
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.swallowed" for v in verdicts)


def test_swallowed_negative_expect_outside_try(tmp_path: Path) -> None:
    """expect() outside the try block — not swallowed."""
    src = """\
import { expect, it } from "vitest";
it("with_assert", () => {
    try {
        doThing();
    } catch (e) {}
    expect(true).toBe(true);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    # tautological fires first, but swallowed should not fire independently
    assert not any(v.kind == "vitest.swallowed" for v in verdicts)


def test_swallowed_negative_no_try(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it("no_try", () => {
    expect(doSomething()).toBe(42);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.swallowed" for v in verdicts)
