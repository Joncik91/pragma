# Rules Reference

Every verdict Pragma can emit, with its blocking status and a one-line trigger.

- **Verdict kind** is language-prefixed: `python.*`, `vitest.*`, `jest.*`.
- **Blocking** is decided by suffix in `src/pragma/blocking.py` (the
  `BLOCKING_SUFFIXES` set). A suffix in that set blocks regardless of language
  prefix; everything else is a non-blocking **warn** or a **pass**.
- The canonical blocking suffix list is what `pragma blocking` prints.

The blocking suffixes (from `pragma blocking`):

```
conditional, mismatched, mocked-away, module_attr_reassignment,
module_shimmed, monkeypatched, no_success_assertion, orphan_mock,
orphan_test, skipped, stub_error_match, swallowed, target_not_covered,
tautological, test_failing_gaming, xfail_gaming
```

Tier 1 rules run in priority order (first match wins); see
`src/pragma/languages/python/rules/__init__.py` for the Python order.

---

## Python (`src/pragma/languages/python/rules/`)

| Verdict kind | Blocking? | Trigger |
|---|---|---|
| `python.mocked-away` | block | `mock.patch(...)` / `patch.object(...)` targets the function under test. |
| `python.monkeypatched` | block | `monkeypatch.setattr` points at the function under test. |
| `python.module_attr_reassignment` | block | `import pricing; pricing.discount = stub` — production symbol replaced by attribute assignment. |
| `python.module_shimmed` | block | `sys.modules["X"] = <stub module>` swaps the production module before import. |
| `python.swallowed` | block | `try: <call>; except: pass` swallows the call that was the test signal. |
| `python.skipped` | block | `pytest.skip(...)` / `pytest.xfail(...)` at the top of the body, or reached via `try/except NotImplementedError -> skip` (directly or via a module-level helper). |
| `python.xfail_gaming` | block | `@pytest.mark.xfail(...)` (per-function, via variable, or module-level `pytestmark`) used to let a stub ship green; `raises=NotImplementedError`/`Exception`/`BaseException` counts regardless of `strict`. |
| `python.stub_error_match` | block | Every `pytest.raises(...)` matches a stub's "not implemented" contract (`NotImplementedError`, `Exception`, or `match="not implemented"`) and no other assert validates a real return value. |
| `python.mismatched` | block | Name implies an error path (`*_rejects_*`, `*_raises_*`, `*_refuses_*`, `*_denies_*`) but the body has no `pytest.raises` / `except`. |
| `python.conditional` | block | Every assertion lives inside an `if` / `for` / `while` branch, so it may never run. |
| `python.tautological` | block | Constant-truthy assert (`assert True`), `x == x`, or constant == same-constant. |
| `python.orphan_test` | block | `test_X.py` never imports `X` and instead redefines a fake locally, so production code is never exercised. |
| `python.no_success_assertion` | block | File-level: the file imports a production target but no test in it calls the target and asserts on a real return value. |
| `python.target_not_covered` | block | Tier 2: the test ran under coverage but the inferred target's lines were never executed. |
| `python.mismatched_warn` | warn | Reject inferred only from a bare `raises` token in the name, but the body asserts a real return value — likely the name describes the subject, not an error. |
| `python.tautological_warn` | warn | `x == x` in a test whose name implies a reflexivity / `__eq__` check, so self-equality exercises real behavior. |
| `python.empty_body` | warn | Test body has no assertion and no `pytest.raises`. |
| `python.parametrize_thin` | warn | `@pytest.mark.parametrize` with 0 or 1 case values claiming multi-case breadth. |
| `python.weak` | warn | Weak assertion (e.g. `assert x is not None`) when an exact value was expected. |
| `python.semantic_gaming` | warn | Tier 3: the LLM judge says the test verifies nothing. |
| `python.unparseable` | (skip) | The file could not be parsed (syntax error / non-UTF-8). Non-blocking; logged, never silently passed. |
| `python.verified` | pass | The test calls the production target and asserts on its return value or raised exception. |

> The priority order means, for example, that a file with both `mocked-away`
> and `tautological` shapes reports `mocked-away` for the affected test, since
> `mocked_away` runs earlier in the chain.

---

## Vitest (`src/pragma/languages/vitest/rules/`)

Verdicts use the `vitest.` prefix. The shared JS/TS rule chain
(`_jsts_core`) drives both Vitest and Jest.

| Verdict kind | Blocking? | Trigger |
|---|---|---|
| `vitest.tautological` | block | `expect(true).toBe(true)` / `expect(x).toBe(x)`. |
| `vitest.mocked-away` | block | `vi.mock("./module")` or `vi.spyOn(...).mockReturnValue(...)` on the symbol under test. |
| `vitest.swallowed` | block | `try { call(); } catch (_) {}` swallows the call under test. |
| `vitest.skipped` | block | `it.skip(...)` / `xit(...)` / `it.todo(...)`. |
| `vitest.mismatched` | block | Name says `*_throws_*` / `*_rejects_*` but body has no `expect(...).toThrow*()`. |
| `vitest.stub_error_match` | block | Every `.toThrow(...)` is stub-shaped (stub-phrase string/regex, bare `.toThrow()`, or bare `Error`) and no other `expect(value)` validates real behavior. |
| `vitest.conditional` | block | Every `expect()` lives inside an `if` / `for` / `while`. |
| `vitest.orphan_mock` | block | `const m = vi.fn().mockReturnValue(L); expect(m()).toEqual(L)` — the mock is never wired to a production symbol. |
| `vitest.no_success_assertion` | block | File-level: imports a target but no test calls it and asserts on a real return value. |
| `vitest.target_not_covered` | block | Tier 2: the test ran but the target's lines had zero V8 coverage hits. |
| `vitest.empty_body` | warn | Test callback has no `expect()`. |
| `vitest.semantic_gaming` | warn | Tier 3: the LLM judge says the test verifies nothing. |
| `vitest.verified` | pass | The test calls the production target and asserts on its return / thrown error. |

Vitest does **not** emit the Python-only verdicts (`monkeypatched`,
`module_shimmed`, `module_attr_reassignment`, `orphan_test`, `xfail_gaming`,
`parametrize_thin`, `weak`).

---

## Jest (`src/pragma/languages/jest/rules/`)

Jest reuses the entire Vitest rule chain via the dialect-parameterized
`_jsts_core`. Every `vitest.*` verdict above has a `jest.*` equivalent with the
same trigger; the mock namespace is `jest.*` instead of `vi.*` (e.g.
`jest.mock(...)`, `jest.fn()`, `jest.spyOn(...)`). Jest adds one verdict with no
Vitest analog:

| Verdict kind | Blocking? | Trigger |
|---|---|---|
| `jest.test_failing_gaming` | block | `test.failing(...)` / `it.failing(...)` pins a stub's throw — the runner's xfail-strict equivalent. |

---

## File matching

Which language claims a file (`*.matches(path)`):

- **Python** — extension `.py` and the name starts with `test_`, ends with
  `_test.py`, or the path contains a `tests` directory.
- **Vitest** — a JS/TS extension, a test-name path
  (`*.test.*` / `*.spec.*` / `tests/` / `__tests__/`), **and** the file imports
  `from "vitest"` (or `require("vitest")`).
- **Jest** — same JS/TS extension and test-name path, but the file **does not**
  import from `"vitest"`. (Jest tests usually rely on auto-injected globals.)

The registry order is `python, vitest, jest`; the first match wins. Vitest
claims its files via the `from "vitest"` import; Jest catches the remaining
JS/TS test files.

`expected: success | reject` is inferred from the test name; the production
target (`module.symbol`) is inferred from the imports. No config is required to
start.
