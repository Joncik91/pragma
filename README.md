<div align="center">

<img src="docs/logo.svg" alt="Pragma" width="160" height="160">

# Pragma

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyPI](https://img.shields.io/badge/pypi-pragma-E8954A?logo=pypi&logoColor=white)](https://pypi.org/project/pragma/)
[![License: MIT](https://img.shields.io/badge/license-MIT-E8954A.svg)](LICENSE)
[![Local-first](https://img.shields.io/badge/local--first-✓-58D070)](https://www.inkandswitch.com/local-first/)
[![pytest · vitest · jest](https://img.shields.io/badge/pytest%20·%20vitest%20·%20jest-supported-58D070)]()
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-E8954A)](https://docs.claude.com/en/docs/claude-code/overview)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-E8954A.svg)](#contributing)

**The test-gaming detector for the agentic era.**

Your AI assistant just made the tests pass. The question is whether it
*tested* anything. Pragma reads what got written, and refuses the
patterns that look like work but verify nothing.

A Claude Code plugin. A small CLI. Three tiers of defense, each one
catching a different kind of cheat.

</div>

## Table of Contents

- [Three Tiers, Layered](#three-tiers-layered)
- [What It Catches — Python](#what-it-catches--python)
- [What It Catches — Vitest (TypeScript / JavaScript)](#what-it-catches--vitest-typescript--javascript)
- [What It Catches — Jest (TypeScript / JavaScript)](#what-it-catches--jest-typescript--javascript)
- [Install](#install)
- [Tier 3 — Bring Your Own LLM](#tier-3--bring-your-own-llm)
- [Use Without Claude Code](#use-without-claude-code)
- [Why](#why)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

## Three Tiers, Layered

- **Tier 1 — AST classifier.** Fast, deterministic, ~10ms. Catches the obvious stuff: `assert True`, `mock.patch` on the function under test, `pytest.skip` smuggled into a body, `vi.spyOn(...).mockReturnValue`. Always on.
- **Tier 2 — coverage-of-target gate.** Runs the test under coverage instrumentation, then asks: *did the production code's lines actually execute?* If the answer is no, the test isn't a test. Opt in with `--with-coverage`.
- **Tier 3 — the LLM judge.** A small model reads the test alongside the production code and decides whether the test verifies behavior or just confidently asserts on its own mocks. Powered by DeepSeek by default; any OpenAI-compatible endpoint works. Opt in with `--with-llm`.

Each tier catches what the previous one misses. Combined, they reach
patterns AST alone cannot — orphan tests, monkeypatched fakes, inline
shadow classes, `vi.mock` on default exports, the lot.

## What It Catches — Python

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
| `python.no_success_assertion` | file-level: imports a target but no test calls it and asserts on a real return value | yes |
| `python.target_not_covered` | tier 2: test ran but the target's lines had zero hits | yes |
| `python.semantic_gaming` | tier 3: the LLM judge says the test verifies nothing | warn |
| `python.empty_body` | test body has no assertion and no `pytest.raises` | warn |
| `python.parametrize_thin` | `@parametrize` with 0 or 1 case values | warn |
| `python.weak` | `assert x is not None` when an exact value was expected | warn |
| `python.verified` | calls the production target, asserts on return / raised exception | pass |

## What It Catches — Vitest (TypeScript / JavaScript)

| Verdict | Pattern | Blocked? |
|---|---|---|
| `vitest.tautological` | `expect(true).toBe(true)` / `expect(x).toBe(x)` | yes |
| `vitest.mocked-away` | `vi.mock("./module")` or `vi.spyOn(...).mockReturnValue(...)` on the target | yes |
| `vitest.swallowed` | `try { call(); } catch (_) {}` swallows the call | yes |
| `vitest.skipped` | `it.skip(...)` / `xit(...)` / `it.todo(...)` | yes |
| `vitest.mismatched` | name says `*_throws_*` but no `expect(...).toThrow*()` | yes |
| `vitest.stub_error_match` | every `.toThrow(...)` is stub-shaped — stub-phrase string/regex, bare `.toThrow()`, or bare `Error` class — and no other `expect(value)...` validates real behavior | yes |
| `vitest.no_success_assertion` | file-level: imports a target but no test calls it and asserts on a real return value | yes |
| `vitest.conditional` | every `expect()` lives inside an `if`/`for`/`while` | yes |
| `vitest.orphan_mock` | `const m = vi.fn().mockReturnValue(L); expect(m()).toEqual(L)` | yes |
| `vitest.target_not_covered` | tier 2: test ran but the target's lines had zero V8 hits | yes |
| `vitest.semantic_gaming` | tier 3: the LLM judge says the test verifies nothing | warn |
| `vitest.empty_body` | test callback has no `expect()` | warn |
| `vitest.verified` | calls the production target, asserts on return / thrown error | pass |

## What It Catches — Jest (TypeScript / JavaScript)

Jest support uses the same rule chain as Vitest, plus one Jest-only verdict for the `test.failing` shape that Vitest doesn't have. Substitute `jest.` for the `vitest.` prefix in the table above (the `vi.mock` patterns become `jest.mock`, `vi.fn` becomes `jest.fn`, etc.). Plus:

| Verdict | Pattern | Blocked? |
|---|---|---|
| `jest.test_failing_gaming` | `test.failing("name", () => { throw ... })` / `it.failing(...)` — pins a stub's throw, the runner's xfail-strict equivalent | yes |

`expected: success | reject` is **inferred from the test name**.
Production target (`module.symbol`) is **inferred from the imports**.
Zero config to start.

## Install

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

## Tier 3 — Bring Your Own LLM

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

## Use Without Claude Code

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

## Why

Ask an AI assistant to *make the tests pass* and it will. Sometimes
by writing real code. Sometimes by writing `assert True`, mocking the
function under test, or redefining the production class right there
in the test file. Coverage is green, CI is green, nothing is
verified.

Static rules alone become a whack-a-mole — every new evasion
pattern a new rule. Pragma plays a different game: tier 1 catches
the obvious shapes, tier 2 demands the production code actually run,
tier 3 reads both files and asks whether the test verifies behavior.

## Security

Tier 3 is the only tier that touches the network. The LLM judge sends
the **test source plus the production source** to whichever endpoint
`PRAGMA_LLM_BASE_URL` points at. Two implications:

1. **Treat the test+production payload as you would any other code
   review send-off.** If your codebase is proprietary, point Tier 3 at
   a self-hosted endpoint (Ollama, LM Studio, vLLM, an internal
   OpenAI-compatible gateway) rather than a third-party SaaS.
2. **Tier 3 is opt-in for exactly this reason** — the default plugin
   wiring runs Tier 1 and Tier 2 only. Set `PRAGMA_HOOK_WITH_LLM=1`
   when you've decided the endpoint is acceptable for your code.

Tiers 1 and 2 stay fully local: AST parsing happens in-process,
coverage instrumentation runs in the local interpreter. Nothing leaves
the machine unless Tier 3 is on.

## Contributing

PRs welcome. Useful directions:

- **More languages.** The verdict-table shape generalises — Go's `_test.go`,
  Rust's `#[test]`, Ruby's RSpec all have analogous gaming patterns.
- **Tier 1 verdicts** for patterns the AST classifier doesn't yet catch
  (open issue with a real-world test file showing the shape).
- **Replay corpora** — anonymised test files where a tier got it wrong,
  so the classifier can be tuned.

See [`docs/PRECOMMIT.md`](docs/PRECOMMIT.md) for the existing pre-commit
integration if you want to wire Tier 1 into another project's hooks.

## License

MIT © Joncik91. See [LICENSE](LICENSE).
