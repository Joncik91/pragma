"""Tests for the vitest.empty_body rule."""

from __future__ import annotations

from pathlib import Path

from pragma.languages.vitest import classify_file


def test_empty_body_fires_on_no_expect(tmp_path: Path) -> None:
    src = """\
import { it } from "vitest";
it("no_assert", () => {
    const x = doSomething();
    console.log(x);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.empty_body" for v in verdicts)


def test_empty_body_fires_on_truly_empty(tmp_path: Path) -> None:
    src = """\
import { it } from "vitest";
it("empty", () => {});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.empty_body" for v in verdicts)


def test_empty_body_negative_has_expect(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it("with_expect", () => {
    expect(doSomething()).toBe(42);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.empty_body" for v in verdicts)
