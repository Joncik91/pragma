---
name: pragma
description: Pragma watches every Edit/Write of a test file and blocks the gamed ones. Three tiers — AST, coverage, and an LLM judge. Write tests that actually verify behavior.
---

# Pragma — write tests that actually test things

Pragma is watching. Every Edit/Write of a test file goes through up to
three tiers — AST shape, coverage of the target, and a small LLM that
reads the whole thing and decides whether the test verifies behavior.

If any tier flags blocking gaming, the tool call is refused before
the file lands.

## tier 1 — patterns it blocks (Python)

- **tautological asserts** — `assert True`, `assert 1 == 1`, `assert x == x`. The assertion is a constant; nothing is tested.
- **mock-the-target** — `mock.patch("auth.login.login")` inside a test of `auth.login.login`. Mock dependencies, not the symbol under test.
- **monkeypatched target** — `monkeypatch.setattr` pointed at the function under test. Same problem as `mock.patch` on the SUT.
- **module-attribute reassignment** — `import pricing; pricing.discount = stub`. Replaces the production function via direct attribute assignment after import.
- **module shimmed** — `sys.modules["X"] = types.ModuleType("X")` swaps the production module before the test imports it.
- **swallowed** — `try: target_call(); except: pass`. The exception was the test signal; swallowing it deletes the verification.
- **skipped** — `pytest.skip(...)` or `pytest.xfail` smuggled into a test body to dodge a failing assertion.
- **xfail-strict gaming** — `@pytest.mark.xfail(strict=True)` on stub tests. The test predictably fails, satisfies xfail, and the suite goes green.
- **stub-error match** — every `pytest.raises(...)` in the test asserts a stub shape (`NotImplementedError`, `Exception`, or `match="not implemented"`) and no other `assert` validates a real return value. Same gaming as the vitest variant.
- **no success assertion (file-level)** — the file imports a production target but NO test in the file calls the target and asserts on a real return value. The structural rule that replaces whack-a-mole. Even if every individual test looks reasonable, a file where no test exercises real-target behavior is pinning the stub's contract.
- **name/body mismatch** — a test named `test_*_rejects_*` / `_raises_*` / `_refuses_*` / `_denies_*` must use `with pytest.raises(...):` (or an `except` block).
- **conditional** — every assertion lives inside an `if`/`for`/`while` branch the inputs never enter. Assertions that may not run can't catch bugs.
- **orphan test** — `tests/test_X.py` that never imports `X` and instead redefines a fake locally. The production code is never exercised.

## tier 1 — patterns it blocks (Vitest)

- **tautological asserts** — `expect(true).toBe(true)`, `expect(x).toBe(x)`.
- **mock-the-target** — `vi.mock("./auth/login")` or `vi.spyOn(authModule, "login").mockReturnValue(...)` when the test asserts on `login()`'s return.
- **swallowed** — `try { call(); } catch (_) {}` swallows the call under test.
- **skipped** — `it.skip(...)`, `it.todo(...)`, `xit(...)`.
- **conditional** — every `expect()` inside an `if`/`for`/`while`.
- **name/body mismatch** — name says `*_throws_*` / `*_rejects_*` but body has no `expect(...).toThrow*()`.
- **stub-error match** — every `.toThrow(...)` / `.rejects.toThrow(...)` in the test is stub-shaped: stub-phrase string, regex containing a stub phrase, bare `.toThrow()` with no args, or bare `Error` class. Fires when no other `expect(value).toBe/...` in the body validates real behavior — the test is just pinning the production stub's error shape.
- **orphan mock** — `const m = vi.fn().mockReturnValue(L); expect(m()).toEqual(L)`. The mock is never wired to a production symbol; the test asserts the mock returns its own configured value.

## tier 1 — patterns it warns on

These don't block but they surface in the verdict output.

- **empty_body** — test body has no assertion and no `pytest.raises`. Placeholder tests are fine during refactors but should be filled in.
- **parametrize_thin** — `@pytest.mark.parametrize` with 0 or 1 case values claiming multi-case breadth. Use real cases or drop the decorator.
- **weak** — `assert x is not None` / `len(x) > 0` when the spec implies a specific return value.

## tier 2 — did the production code actually run?

After tier 1 clears a test as `verified`, tier 2 runs it under coverage
instrumentation and checks whether the production target's lines
actually executed.

- **target_not_covered** — your test imports the production target, looks clean to tier 1, but the production symbol's lines were never hit when the test ran. Common causes:
  - the test only exercises a different symbol than the inferred target
  - the test imports the target but asserts on a stand-alone mock
  - a class or function was redefined inline in the test, shadowing the production one

To pass tier 2: actually call the production function with realistic
inputs and assert on its return value. The coverage hit lands; the
verdict stays `verified`.

Tier 2 runs by default in the Claude Code hook. Disable with
`PRAGMA_COVERAGE_DEFAULT_OFF=1`. CLI: `--with-coverage`.

## tier 3 — does the test actually verify behavior?

Tier 3 is the LLM judge. A small model reads the production function
and the test side-by-side and decides whether the test verifies
behavior or only confirms its own setup. It catches semantic gaming
that AST and coverage can't see — because the gaming is *plausible*,
not pattern-matched.

- **semantic_gaming** — the LLM judge says the test asserts on mocks, fakes, or local literals without exercising the real implementation. Warning verdict (not blocking).

To pass tier 3: write the test the way you'd write it if no one was
mocking anything. Call the production function. Assert on what it
returns or what it raises. If the production function isn't ready,
the test isn't ready — say so with a real `pytest.raises(NotImplementedError)`,
not by quietly mocking it away.

Tier 3 is opt-in. Set `PRAGMA_LLM_API_KEY` (DeepSeek by default) and
`PRAGMA_HOOK_WITH_LLM=1` to enable in the hook. CLI: `--with-llm`.

## how to pass — Python

```python
from auth.login import login   # import the real symbol
import pytest

def test_login_happy_path():
    result = login("user@example.com", "Strong-Password-1")
    assert result == "JWT"

def test_login_rejects_weak_password():
    with pytest.raises(WeakPasswordError):
        login("user@example.com", "x")
```

## how to pass — Vitest

```typescript
import { it, expect } from "vitest";
import { login } from "./auth/login";

it("login_happy_path", () => {
  expect(login("user@example.com", "Strong-Password-1")).toBe("JWT");
});

it("login_rejects_weak_password", () => {
  expect(() => login("user@example.com", "x")).toThrow(WeakPasswordError);
});
```

Import the real symbol. Call it with realistic inputs. Assert on the
actual return value or the actual exception type. If you're reaching
for a mock to make the test pass, stop and ask whether the test should
exist yet.
