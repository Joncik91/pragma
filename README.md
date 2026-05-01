# Pragma

> The test-gaming detector for the agentic era.

Your AI assistant just made the tests pass. The question is whether it
*tested* anything. Pragma reads what got written, and refuses the
patterns that look like work but verify nothing.

A Claude Code plugin. A small CLI. Three tiers of defense, each one
catching a different kind of cheat.

## Three tiers, layered

- **Tier 1 — AST classifier.** Fast, deterministic, ~10ms. Catches the obvious stuff: `assert True`, `mock.patch` on the function under test, `pytest.skip` smuggled into a body, `vi.spyOn(...).mockReturnValue`. Always on.
- **Tier 2 — coverage-of-target gate.** Runs the test under coverage instrumentation, then asks: *did the production code's lines actually execute?* If the answer is no, the test isn't a test. Opt in with `--with-coverage`.
- **Tier 3 — the LLM judge.** A small model reads the test alongside the production code and decides whether the test verifies behavior or just confidently asserts on its own mocks. Powered by DeepSeek by default; any OpenAI-compatible endpoint works. Opt in with `--with-llm`.

Each tier catches what the previous one misses. Combined, they reach
patterns AST alone cannot — orphan tests, monkeypatched fakes, inline
shadow classes, `vi.mock` on default exports, the lot.

## what it catches — Python

| Verdict | Pattern | Blocked? |
|---|---|---|
| `python.tautological` | `assert True` / `assert 1 == 1` / `assert x == x` | yes |
| `python.mocked-away` | `mock.patch("auth.login.login")` inside a test of `auth.login.login` | yes |
| `python.monkeypatched` | `monkeypatch.setattr` targets the function under test | yes |
| `python.module_attr_reassignment` | `import pricing; pricing.discount = stub` | yes |
| `python.module_shimmed` | `sys.modules["X"] = types.ModuleType("X")` swap | yes |
| `python.swallowed` | `try: <call>; except: pass` swallows the call under test | yes |
| `python.skipped` | `pytest.skip(...)` / `xfail` smuggled at top of body | yes |
| `python.xfail_gaming` | `@pytest.mark.xfail(strict=True)` lets the stub ship green | yes |
| `python.mismatched` | name says `test_*_rejects_*` etc. but body has no `pytest.raises` | yes |
| `python.conditional` | every assertion lives inside an `if`/`for`/`while` branch | yes |
| `python.orphan_test` | `test_X.py` never imports `X`; redefines a fake locally | yes |
| `python.stub_error_match` | every `pytest.raises(...)` is `NotImplementedError`, `Exception`, or `match="not implemented"`, no other assert validates real value | yes |
| `python.target_not_covered` | tier 2: test ran but the target's lines had zero hits | yes |
| `python.semantic_gaming` | tier 3: the LLM judge says the test verifies nothing | warn |
| `python.empty_body` | test body has no assertion and no `pytest.raises` | warn |
| `python.parametrize_thin` | `@parametrize` with 0 or 1 case values | warn |
| `python.weak` | `assert x is not None` when an exact value was expected | warn |
| `python.verified` | calls the production target, asserts on return / raised exception | pass |

## what it catches — Vitest (TypeScript / JavaScript)

| Verdict | Pattern | Blocked? |
|---|---|---|
| `vitest.tautological` | `expect(true).toBe(true)` / `expect(x).toBe(x)` | yes |
| `vitest.mocked-away` | `vi.mock("./module")` or `vi.spyOn(...).mockReturnValue(...)` on the target | yes |
| `vitest.swallowed` | `try { call(); } catch (_) {}` swallows the call | yes |
| `vitest.skipped` | `it.skip(...)` / `xit(...)` / `it.todo(...)` | yes |
| `vitest.mismatched` | name says `*_throws_*` but no `expect(...).toThrow*()` | yes |
| `vitest.stub_error_match` | every `.toThrow(...)` is stub-shaped — stub-phrase string/regex, bare `.toThrow()`, or bare `Error` class — and no other `expect(value)...` validates real behavior | yes |
| `vitest.conditional` | every `expect()` lives inside an `if`/`for`/`while` | yes |
| `vitest.orphan_mock` | `const m = vi.fn().mockReturnValue(L); expect(m()).toEqual(L)` | yes |
| `vitest.target_not_covered` | tier 2: test ran but the target's lines had zero V8 hits | yes |
| `vitest.semantic_gaming` | tier 3: the LLM judge says the test verifies nothing | warn |
| `vitest.empty_body` | test callback has no `expect()` | warn |
| `vitest.verified` | calls the production target, asserts on return / thrown error | pass |

`expected: success | reject` is **inferred from the test name**.
Production target (`module.symbol`) is **inferred from the imports**.
Zero config to start.

## install

```shell
pipx install pragma
```

In Claude Code:

```text
/plugin install pragma@joncik91/pragma
```

That's it. The plugin's PreToolUse hook scans every `Write` of a file
matching `test_*.py` / `*/tests/*.py` / `*.test.ts` etc.; PostToolUse
re-scans on disk to catch `Edit` cases. Tier 1 always runs. Tier 2 is
on by default in the hook (set `PRAGMA_COVERAGE_DEFAULT_OFF=1` to
disable). Tier 3 is opt-in via `PRAGMA_HOOK_WITH_LLM=1`.

## tier 3 — bring your own LLM

Tier 3 is provider-agnostic. Set an API key for any
OpenAI-compatible endpoint. DeepSeek is the default — fast, cheap,
caches on its own.

```shell
export PRAGMA_LLM_API_KEY=sk-...           # DeepSeek by default
export PRAGMA_HOOK_WITH_LLM=1              # turn it on in the plugin
```

Want a different provider? Override the URL and model:

```shell
export PRAGMA_LLM_BASE_URL=https://api.openai.com/v1
export PRAGMA_LLM_MODEL=gpt-4o-mini
```

Local models work too — point at Ollama, LM Studio, vLLM, anything
that speaks `/v1/chat/completions`.

## use without Claude Code

The CLI works on its own.

```shell
# tier 1 only — fast, deterministic
pragma verify tests path/to/test_login.py

# tier 1 + tier 2 — slower, but catches "imported but never called"
pragma verify tests path/to/test_login.py --with-coverage

# all three tiers — catches semantic gaming AST and coverage can't see
pragma verify tests path/to/test_login.py --with-coverage --with-llm
```

Exit 1 + JSON when blocking. `--human` for one-line-per-test output.

To wire the AST classifier into pre-commit:

```shell
pragma init-precommit
```

Drops a `.pre-commit-config.yaml` calling `pragma verify tests` on
staged test files. See [`docs/PRECOMMIT.md`](docs/PRECOMMIT.md) for
the manual snippet.

## why

Ask an AI assistant to *make the tests pass* and it will. Sometimes
by writing real code. Sometimes by writing `assert True`, mocking the
function under test, or redefining the production class right there
in the test file. Coverage is green, CI is green, nothing is
verified.

Static rules alone become a whack-a-mole — every new evasion
pattern a new rule. Pragma plays a different game: tier 1 catches
the obvious shapes, tier 2 demands the production code actually run,
tier 3 reads both files and asks whether the test verifies behavior.

## license

MIT.
