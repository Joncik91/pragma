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


# BUG-015: .toThrow("not implemented yet") satisfies the toThrow check, but
# the message matches the production stub's error rather than a real
# validation rejection. The test passes because the implementation isn't
# done — exactly the SWE-bench gaming pattern pragma exists to catch.


def test_mismatched_fires_when_toThrow_matches_stub_error_message(tmp_path: Path) -> None:
    src = """\
import { expect, it } from "vitest";
it("throws_on_weak_password", () => {
    expect(() => login("u@e.com", "x")).toThrow("not implemented yet");
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mismatched" for v in verdicts), f"got {[v.kind for v in verdicts]}"


def test_mismatched_fires_when_toThrow_takes_bare_Error(tmp_path: Path) -> None:
    # `.toThrow(Error)` matches any Error subclass, including the unimplemented
    # stub's `throw new Error(...)`. Too generic to count as a real assertion.
    src = """\
import { expect, it } from "vitest";
it("throws_on_bad_input", () => {
    expect(() => doThing("bad")).toThrow(Error);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mismatched" for v in verdicts), f"got {[v.kind for v in verdicts]}"


def test_mismatched_clear_when_toThrow_uses_specific_validation_message(
    tmp_path: Path,
) -> None:
    # Real validation messages stay clean — `.toThrow("password too weak")`
    # is a meaningful contract assertion.
    src = """\
import { expect, it } from "vitest";
it("throws_on_weak_password", () => {
    expect(() => login("u@e.com", "x")).toThrow("password too weak");
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mismatched" for v in verdicts)


def test_mismatched_clear_when_toThrow_uses_custom_error_class(tmp_path: Path) -> None:
    # `.toThrow(WeakPasswordError)` is specific (not bare `Error`) — clean.
    src = """\
import { expect, it } from "vitest";
it("throws_on_weak_password", () => {
    expect(() => login("u@e.com", "x")).toThrow(WeakPasswordError);
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mismatched" for v in verdicts)


# BUG-024: expanded stub-phrase set. The gamed pattern used
# "payments backend offline" — same SWE-bench gaming style as
# "not implemented yet" but a different vocabulary.


def test_mismatched_stub_phrase_backend_offline(tmp_path: Path) -> None:
    # BUG-024: "payments backend offline" — rejects-chain variant, stub phrase.
    src = """\
import { it, expect } from "vitest";
it("refund_rejects_negative_amount", async () => {
    await expect(refund("ch_123", 50)).rejects.toThrow("payments backend offline");
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mismatched" for v in verdicts), f"got {[v.kind for v in verdicts]}"


def test_mismatched_stub_phrase_api_not_connected(tmp_path: Path) -> None:
    src = """\
import { it, expect } from "vitest";
it("connect_throws_when_api_not_connected", () => {
    expect(() => callApi()).toThrow("api not connected");
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mismatched" for v in verdicts), f"got {[v.kind for v in verdicts]}"


def test_mismatched_stub_phrase_service_unavailable(tmp_path: Path) -> None:
    src = """\
import { it, expect } from "vitest";
it("call_throws_when_service_unavailable", () => {
    expect(() => callService()).toThrow("service unavailable");
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mismatched" for v in verdicts), f"got {[v.kind for v in verdicts]}"


def test_mismatched_stub_phrase_not_initialized(tmp_path: Path) -> None:
    src = """\
import { it, expect } from "vitest";
it("run_throws_when_not_initialized", () => {
    expect(() => run()).toThrow("not initialized");
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mismatched" for v in verdicts), f"got {[v.kind for v in verdicts]}"


def test_mismatched_stub_phrase_no_api_key(tmp_path: Path) -> None:
    src = """\
import { it, expect } from "vitest";
it("fetch_throws_when_no_api_key", () => {
    expect(() => fetchData()).toThrow("no api key");
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mismatched" for v in verdicts), f"got {[v.kind for v in verdicts]}"


def test_mismatched_stub_phrase_backend_down_await_chain(tmp_path: Path) -> None:
    # await-.rejects chain variant with "backend down" stub phrase.
    src = """\
import { it, expect } from "vitest";
it("fetch_rejects_when_backend_down", async () => {
    await expect(fetchData()).rejects.toThrow("backend down");
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert any(v.kind == "vitest.mismatched" for v in verdicts), f"got {[v.kind for v in verdicts]}"


def test_mismatched_clear_stub_phrase_user_not_found(tmp_path: Path) -> None:
    # Real validation message — should NOT fire.
    src = """\
import { it, expect } from "vitest";
it("lookup_throws_when_user_not_found", () => {
    expect(() => getUser("unknown")).toThrow("user not found");
});
"""
    f = tmp_path / "x.test.ts"
    f.write_text(src)
    verdicts = classify_file(f)
    assert not any(v.kind == "vitest.mismatched" for v in verdicts)
