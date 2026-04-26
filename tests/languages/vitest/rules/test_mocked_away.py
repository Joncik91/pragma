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


# ---------------------------------------------------------------------------
# BUG-023: intermediate-variable pattern
# ---------------------------------------------------------------------------


def test_mocked_away_fires_on_const_intermediate_variable(tmp_path: Path) -> None:
    """const result = symbol(...); expect(result).toXxx(...) must flag."""
    src = """\
import { it, expect, vi } from "vitest";
import { notifyUser } from "./notify";
vi.mock("./notify", () => ({ notifyUser: vi.fn() }));
it("notifyUser_happy_path", () => {
    vi.mocked(notifyUser).mockReturnValue({ sent: true });
    const result = notifyUser("user-1", "Hello!");
    expect(result).toEqual({ sent: true });
});
"""
    f = tmp_path / "notify.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_fires_on_let_intermediate_variable(tmp_path: Path) -> None:
    """let result = symbol(...); expect(result).toXxx(...) must flag."""
    src = """\
import { it, expect, vi } from "vitest";
import { notifyUser } from "./notify";
vi.mock("./notify", () => ({ notifyUser: vi.fn() }));
it("notifyUser_happy_path", () => {
    let result = notifyUser("user-1", "Hello!");
    expect(result).toEqual({ sent: true });
});
"""
    f = tmp_path / "notify.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_fires_with_multiple_intermediate_uses(tmp_path: Path) -> None:
    """const a = X(...); doStuff(a); expect(a).toXxx(...) must flag."""
    src = """\
import { it, expect, vi } from "vitest";
import { notifyUser } from "./notify";
vi.mock("./notify", () => ({ notifyUser: vi.fn() }));
it("notifyUser_with_side_effect", () => {
    const result = notifyUser("user-1", "Hello!");
    console.log(result);
    expect(result).toEqual({ sent: true });
});
"""
    f = tmp_path / "notify.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_negative_body_never_calls_symbol(tmp_path: Path) -> None:
    """vi.mock + import but body never calls the symbol — must NOT flag."""
    src = """\
import { it, expect, vi } from "vitest";
import { notifyUser } from "./notify";
vi.mock("./notify", () => ({ notifyUser: vi.fn() }));
it("some_other_test", () => {
    const result = { sent: true };
    expect(result).toEqual({ sent: true });
});
"""
    f = tmp_path / "notify.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_negative_result_bound_to_other_symbol(tmp_path: Path) -> None:
    """const result = OTHER_FUNC(...); expect(result) — must NOT flag when
    OTHER_FUNC is not the mocked symbol."""
    src = """\
import { it, expect, vi } from "vitest";
import { notifyUser } from "./notify";
vi.mock("./notify", () => ({ notifyUser: vi.fn() }));
it("some_other_test", () => {
    const result = buildPayload("user-1", "Hello!");
    expect(result).toEqual({ sent: true });
});
"""
    f = tmp_path / "notify.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mocked-away" for v in verdicts)


# ---------------------------------------------------------------------------
# BUG-019: vi.spyOn(...).mock* detection
# ---------------------------------------------------------------------------


def test_mocked_away_spyon_mock_return_value(tmp_path: Path) -> None:
    """import * as M + vi.spyOn(M, 'fn').mockReturnValue + M.fn() call + assert."""
    src = """\
import { it, expect, vi } from "vitest";
import * as chargeModule from "../src/charge";

it("chargeCard_happy_path", () => {
    vi.spyOn(chargeModule, "chargeCard").mockReturnValue({ id: "ch_test_001" });
    const result = chargeModule.chargeCard("tok_visa", 1000);
    expect(result).toEqual({ id: "ch_test_001" });
});
"""
    f = tmp_path / "charge.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_spyon_mock_implementation(tmp_path: Path) -> None:
    """mockImplementation variant must also flag."""
    src = """\
import { it, expect, vi } from "vitest";
import * as chargeModule from "../src/charge";

it("chargeCard_impl", () => {
    vi.spyOn(chargeModule, "chargeCard").mockImplementation(() => ({ id: "ch_2" }));
    const result = chargeModule.chargeCard("tok", 500);
    expect(result).toEqual({ id: "ch_2" });
});
"""
    f = tmp_path / "charge.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_spyon_mock_resolved_value(tmp_path: Path) -> None:
    """mockResolvedValue variant must also flag."""
    src = """\
import { it, expect, vi } from "vitest";
import * as chargeModule from "../src/charge";

it("chargeCard_resolved", async () => {
    vi.spyOn(chargeModule, "chargeCard").mockResolvedValue({ id: "ch_3" });
    const result = await chargeModule.chargeCard("tok", 200);
    expect(result).toEqual({ id: "ch_3" });
});
"""
    f = tmp_path / "charge.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_spyon_mock_rejected_value(tmp_path: Path) -> None:
    """mockRejectedValue variant must also flag."""
    src = """\
import { it, expect, vi } from "vitest";
import * as chargeModule from "../src/charge";

it("chargeCard_rejected", async () => {
    vi.spyOn(chargeModule, "chargeCard").mockRejectedValue(new Error("fail"));
    try {
        const result = await chargeModule.chargeCard("tok", 200);
        expect(result).toBeUndefined();
    } catch (e) {
        expect(e).toBeDefined();
    }
});
"""
    f = tmp_path / "charge.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_spyon_with_intermediate_variable(tmp_path: Path) -> None:
    """spyOn + intermediate variable combining BUG-023 and BUG-019."""
    src = """\
import { it, expect, vi } from "vitest";
import * as chargeModule from "../src/charge";

it("chargeCard_intermediate", () => {
    vi.spyOn(chargeModule, "chargeCard").mockReturnValue({ id: "ch_4" });
    const r = chargeModule.chargeCard("tok_mc", 750);
    expect(r).toEqual({ id: "ch_4" });
});
"""
    f = tmp_path / "charge.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_spyon_no_mock_chain_does_not_flag(tmp_path: Path) -> None:
    """vi.spyOn without .mock* (observation only) must NOT flag."""
    src = """\
import { it, expect, vi } from "vitest";
import * as chargeModule from "../src/charge";

it("chargeCard_spy_only", () => {
    vi.spyOn(chargeModule, "chargeCard");
    const result = chargeModule.chargeCard("tok_visa", 1000);
    expect(result).toBeDefined();
});
"""
    f = tmp_path / "charge.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mocked-away" for v in verdicts)


# ---------------------------------------------------------------------------
# BUG-026: vi.mock + namespace import flavor
# ---------------------------------------------------------------------------


def test_mocked_away_namespace_import_vi_mock_direct_assert(tmp_path: Path) -> None:
    """import * as M + vi.mock on same path + expect(M.foo(...)).toXxx(...)."""
    src = """\
import { it, expect, vi } from "vitest";
import * as searchModule from "../src/search";

vi.mock("../src/search", () => ({
    searchProducts: vi.fn(),
}));

it("searchProducts_direct_assert", () => {
    searchModule.searchProducts.mockReturnValue([{ id: "1" }]);
    expect(searchModule.searchProducts("widget", 10)).toEqual([{ id: "1" }]);
});
"""
    f = tmp_path / "search.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_namespace_import_vi_mock_intermediate(tmp_path: Path) -> None:
    """Combines BUG-026 + BUG-023: const r = M.foo(...); expect(r).toXxx(...)."""
    src = """\
import { it, expect, vi } from "vitest";
import * as searchModule from "../src/search";

vi.mock("../src/search", () => ({
    searchProducts: vi.fn(),
}));

it("searchProducts_intermediate", () => {
    vi.mocked(searchModule.searchProducts).mockReturnValue([{ id: "1", name: "Widget" }]);
    const results = searchModule.searchProducts("widget", 10);
    expect(results).toHaveLength(2);
});
"""
    f = tmp_path / "search.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_namespace_import_vi_mock_await_intermediate(tmp_path: Path) -> None:
    """Combines BUG-026 + BUG-023: const r = await M.foo(...); expect(r).toXxx(...)."""
    src = """\
import { it, expect, vi } from "vitest";
import * as searchModule from "../src/search";

vi.mock("../src/search", () => ({
    searchProducts: vi.fn(),
}));

it("searchProducts_await_intermediate", async () => {
    vi.mocked(searchModule.searchProducts).mockResolvedValue([{ id: "1" }]);
    const results = await searchModule.searchProducts("widget", 10);
    expect(results).toEqual([{ id: "1" }]);
});
"""
    f = tmp_path / "search.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_namespace_import_no_vi_mock_does_not_flag(tmp_path: Path) -> None:
    """import * as M but NO vi.mock — must NOT flag."""
    src = """\
import { it, expect, vi } from "vitest";
import * as searchModule from "../src/search";

it("searchProducts_real", () => {
    const results = searchModule.searchProducts("widget", 10);
    expect(results).toEqual([{ id: "1" }]);
});
"""
    f = tmp_path / "search.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_namespace_import_vi_mock_different_path_does_not_flag(
    tmp_path: Path,
) -> None:
    """import * as M + vi.mock on a DIFFERENT path — must NOT flag."""
    src = """\
import { it, expect, vi } from "vitest";
import * as searchModule from "../src/search";

vi.mock("../src/other", () => ({ otherFn: vi.fn() }));

it("searchProducts_unrelated_mock", () => {
    const results = searchModule.searchProducts("widget", 10);
    expect(results).toEqual([{ id: "1" }]);
});
"""
    f = tmp_path / "search.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mocked-away" for v in verdicts)


def test_mocked_away_namespace_import_vi_mock_no_result_assert_does_not_flag(
    tmp_path: Path,
) -> None:
    """import * as M + vi.mock matches + M.foo() called but no assertion on result."""
    src = """\
import { it, expect, vi } from "vitest";
import * as searchModule from "../src/search";

vi.mock("../src/search", () => ({
    searchProducts: vi.fn(),
}));

it("searchProducts_no_result_assert", () => {
    searchModule.searchProducts("widget", 10);
    expect(true).toBe(true);
});
"""
    f = tmp_path / "search.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mocked-away" for v in verdicts)
