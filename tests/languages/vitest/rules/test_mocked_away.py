"""Tests for the vitest.mocked-away rule."""

from __future__ import annotations

from pathlib import Path

from pragma.languages.vitest import classify_file


def test_mocked_away_fires_on_vi_mock_with_assertion(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
import { login } from "./auth/login";
vi.mock("./auth/login", () => ({ login: vi.fn().mockReturnValue("ok") }));
it("auth_test", () => {
    expect(login("user", "pass")).toBe("ok");
});
"""
    f = tmp_path / "auth.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_negative_no_vi_mock(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
import { login } from "./auth/login";
it("auth_test", () => {
    expect(login("user", "pass")).toBe("ok");
});
"""
    f = tmp_path / "auth.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_negative_different_module(tmp_path: Path) -> None:
    """vi.mock on a different module than the import."""
    src = """\
import { expect, it } from "vitest";
import { login } from "./auth/login";
vi.mock("./other/module", () => ({}));
it("auth_test", () => {
    expect(login("user", "pass")).toBe("ok");
});
"""
    f = tmp_path / "auth.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mocked-away" for v in verdicts)
