"""Tests for the vitest.skipped rule."""

from __future__ import annotations

from pathlib import Path

from pragma.languages.vitest import classify_file


def test_skipped_fires_on_it_skip(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it.skip("skipped_test", () => {
    const result = doSomething();
    expect(result).toBe(42);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.skipped" for v in verdicts)


def test_skipped_fires_on_it_todo(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it.todo("todo_test");
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.skipped" for v in verdicts)


def test_skipped_fires_on_xit(tmp_path: Path) -> None:
    src = """\
import { expect, it, xit } from "vitest";
xit("xt_test", () => {
    expect(doSomething()).toBe(2);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.skipped" for v in verdicts)


def test_skipped_fires_on_xtest(tmp_path: Path) -> None:
    src = """\
import { expect, xtest } from "vitest";
xtest("xt_test", () => {
    expect(doSomething()).toBe(2);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.skipped" for v in verdicts)


def test_skipped_negative_normal_test(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it("normal_test", () => {
    expect(2 + 2).toBe(4);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.skipped" for v in verdicts)
