---
name: pragma
description: Pragma rejects gamed tests on Edit/Write of *.py files in tests/ or named test_*.py. Avoid these patterns when writing tests.
---

# Pragma — anti-gaming rules for tests

Pragma is watching every test file you Edit/Write. It will **block** the
tool call when it sees any of these patterns:

- **tautological asserts** — `assert True`, `assert 1 == 1`, `assert x == x`.
- **mock-the-target** — `mock.patch("auth.login.login")` inside a test of `auth.login.login`. Mock dependencies, not the symbol under test.
- **monkeypatched-target** — `monkeypatch.setattr` whose target is the function under test. Same problem as `mock.patch` on the SUT.
- **swallowed** — `try: target_call(); except: pass`. The exception was the test signal; swallowing it deletes the verification.
- **skipped** — `pytest.skip(...)` or `pytest.xfail` smuggled at the top of a test body to dodge a failing assertion.
- **name/body mismatch** — a test named `test_*_rejects_*`, `_raises_*`, `_refuses_*`, or `_denies_*` must use `with pytest.raises(...):` (or an `except` block).
- **conditional** — every assertion lives inside an `if`/`for`/`while` branch that the test inputs never enter. Assertions that may not run can't catch bugs.

It will **warn** (not block) on:

- **empty_body** — test body has no assertion and no `pytest.raises`. Placeholder tests are fine during refactors but should be filled in.
- **parametrize_thin** — `@pytest.mark.parametrize` with 0 or 1 case values claiming multi-case breadth. Use real cases or drop the decorator.
- **weak** — `assert x is not None` / `len(x) > 0` when the spec implies a specific return value.

To pass: import the production symbol, call it with realistic inputs,
assert on the actual return value (or the raised exception type via
`pytest.raises`). If you're tempted to mock the function under test,
write `assert True`, or skip the assertion — stop and rewrite to
verify real behaviour.

## TypeScript / JavaScript (Vitest)

Same anti-gaming rules apply. Pragma blocks Edit/Write of Vitest tests
that contain:

- **tautological asserts** — `expect(true).toBe(true)`, `expect(x).toBe(x)`.
- **mock-the-target** — `vi.mock("./auth/login")` when the test asserts on `login()`'s return.
- **swallowed** — `try { call(); } catch (_) {}` swallows the call.
- **skipped** — `it.skip(...)`, `it.todo(...)`, `xit(...)`.
- **conditional** — every `expect()` inside an `if`/`for`/`while`.
- **mismatched** — name says `*_throws_*` but no `expect(...).toThrow*()`.

To pass: import the production symbol, call it, assert on the actual
return value or thrown error using `expect(...).toThrow*()`.
