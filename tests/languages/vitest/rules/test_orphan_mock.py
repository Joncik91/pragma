"""Tests for the vitest.orphan_mock rule."""

from __future__ import annotations

from pathlib import Path

from pragma.languages.vitest import classify_file


def _make_file(tmp_path: Path, src: str) -> Path:
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    return f


# ---------------------------------------------------------------------------
# Positive cases — should fire vitest.orphan_mock
# ---------------------------------------------------------------------------


def test_orphan_mock_resolved_value(tmp_path: Path) -> None:
    """Classic pattern: mockResolvedValue with await call, asserted value matches literal."""
    src = """\
import { it, expect, vi } from "vitest";
it("fetchUser_returns_user", async () => {
    const m = vi.fn().mockResolvedValue({ id: "u1", name: "Alice" });
    const r = await m("u1");
    expect(r).toEqual({ id: "u1", name: "Alice" });
});
"""
    verdicts = classify_file(_make_file(tmp_path, src))
    assert any(v.kind == "vitest.orphan_mock" for v in verdicts), [v.kind for v in verdicts]


def test_orphan_mock_return_value_sync(tmp_path: Path) -> None:
    """mockReturnValue (sync) variant."""
    src = """\
import { it, expect, vi } from "vitest";
it("getConfig_returns_config", () => {
    const m = vi.fn().mockReturnValue({ env: "prod" });
    const r = m();
    expect(r).toEqual({ env: "prod" });
});
"""
    verdicts = classify_file(_make_file(tmp_path, src))
    assert any(v.kind == "vitest.orphan_mock" for v in verdicts), [v.kind for v in verdicts]


def test_orphan_mock_resolved_value_once(tmp_path: Path) -> None:
    """mockResolvedValueOnce variant."""
    src = """\
import { it, expect, vi } from "vitest";
it("loadData_once", async () => {
    const m = vi.fn().mockResolvedValueOnce({ data: 42 });
    const r = await m();
    expect(r).toEqual({ data: 42 });
});
"""
    verdicts = classify_file(_make_file(tmp_path, src))
    assert any(v.kind == "vitest.orphan_mock" for v in verdicts), [v.kind for v in verdicts]


def test_orphan_mock_return_value_once(tmp_path: Path) -> None:
    """mockReturnValueOnce variant."""
    src = """\
import { it, expect, vi } from "vitest";
it("getVal_once", () => {
    const m = vi.fn().mockReturnValueOnce(99);
    const r = m();
    expect(r).toEqual(99);
});
"""
    verdicts = classify_file(_make_file(tmp_path, src))
    assert any(v.kind == "vitest.orphan_mock" for v in verdicts), [v.kind for v in verdicts]


def test_orphan_mock_string_literal(tmp_path: Path) -> None:
    """Works with string literals too."""
    src = """\
import { it, expect, vi } from "vitest";
it("getName", () => {
    const m = vi.fn().mockReturnValue("alice");
    const r = m();
    expect(r).toBe("alice");
});
"""
    verdicts = classify_file(_make_file(tmp_path, src))
    assert any(v.kind == "vitest.orphan_mock" for v in verdicts), [v.kind for v in verdicts]


# ---------------------------------------------------------------------------
# Negative cases — should NOT fire vitest.orphan_mock
# ---------------------------------------------------------------------------


def test_no_flag_when_asserted_value_differs(tmp_path: Path) -> None:
    """Different literal in expect → no flag."""
    src = """\
import { it, expect, vi } from "vitest";
it("fetchUser_returns_user", async () => {
    const m = vi.fn().mockResolvedValue({ id: "u1", name: "Alice" });
    const r = await m("u1");
    expect(r).toEqual({ id: "u2", name: "Bob" });
});
"""
    verdicts = classify_file(_make_file(tmp_path, src))
    assert not any(v.kind == "vitest.orphan_mock" for v in verdicts), [v.kind for v in verdicts]


def test_no_flag_for_real_production_call(tmp_path: Path) -> None:
    """Clean test calling a real production symbol — no mock at all."""
    src = """\
import { it, expect } from "vitest";
import { fetchUser } from "../src/api";
it("fetchUser_returns_user", async () => {
    const result = await fetchUser("u1");
    expect(result.id).toBe("u1");
});
"""
    verdicts = classify_file(_make_file(tmp_path, src))
    assert not any(v.kind == "vitest.orphan_mock" for v in verdicts), [v.kind for v in verdicts]


def test_no_flag_for_wired_vi_mock(tmp_path: Path) -> None:
    """vi.mock wires to a module symbol — mocked_away rule, not orphan_mock."""
    src = """\
import { it, expect, vi } from "vitest";
import { fetchUser } from "../src/api";
vi.mock("../src/api", () => ({
    fetchUser: vi.fn().mockResolvedValue({ id: "u1", name: "Alice" }),
}));
it("fetchUser_is_mocked", async () => {
    const result = await fetchUser("u1");
    expect(result).toEqual({ id: "u1", name: "Alice" });
});
"""
    verdicts = classify_file(_make_file(tmp_path, src))
    # vi.mock at module level means mocked_away fires, not orphan_mock
    assert not any(v.kind == "vitest.orphan_mock" for v in verdicts), [v.kind for v in verdicts]
