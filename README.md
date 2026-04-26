# Pragma

> Catches AI test-gaming.

Pragma is a Claude Code plugin (and a small CLI) that watches every
test file your AI assistant writes and **blocks the edit** when the
test is gamed — assertions that pass without actually verifying
anything.

## What it catches

| Verdict | Pattern | Blocked? |
|---|---|---|
| `tautological` | `assert True` / `assert 1 == 1` / `assert x == x` | yes |
| `mocked-away` | `mock.patch("auth.login.login")` inside a test of `auth.login.login` | yes |
| `monkeypatched` | `monkeypatch.setattr` targets the function under test | yes |
| `swallowed` | `try: <call>; except: pass` swallows the call under test | yes |
| `skipped` | `pytest.skip(...)` / `xfail` smuggled at top of body | yes |
| `mismatched` | name says `test_*_rejects_*` / `_raises_*` / `_refuses_*` / `_denies_*` but body has no `pytest.raises` / `except` | yes |
| `conditional` | every assertion lives inside an `if` / `for` / `while` branch the inputs never enter | yes |
| `empty_body` | test body has no assertion and no `pytest.raises` | warn |
| `parametrize_thin` | `@parametrize` with 0 or 1 case values claims breadth | warn |
| `weak` | `assert x is not None` when the spec wanted a specific value | warn |
| `verified` | calls the production target, asserts on its return / raised exception | pass |

`expected: success | reject` is **inferred from the test name**.
Production target (`module.symbol`) is **inferred from the imports**.
Zero config.

## Install

```shell
pipx install pragma
```

Then in Claude Code:

```text
/plugin install pragma@joncik91/pragma
```

That's it. The plugin's PreToolUse hook scans every `Write` of a
file matching `test_*.py` or `*/tests/*.py`; the PostToolUse hook
re-scans on disk to catch `Edit` cases. Gamed tests are rejected
before they land.

## Use without Claude Code

The CLI works on its own:

```shell
pragma verify tests path/to/test_login.py
```

Exit code 1 + JSON if any test is gamed; exit 0 otherwise. Pass
`--human` for one-line-per-test output.

To wire it into pre-commit:

```shell
pragma init-precommit
```

Drops `.pre-commit-config.yaml` calling `pragma verify tests` on every
staged test file. See [`docs/PRECOMMIT.md`](docs/PRECOMMIT.md) for the
manual snippet.

## Why

Ask an AI assistant to "make the tests pass" and you get tests that
pass. Sometimes by writing real code. Sometimes by writing
`assert True` and moving on. Coverage tools say you're covered, CI
is green, nothing is verified. Pragma reads the test source, not
just the pass/fail status, and refuses the patterns that game the
gate.

## License

Apache-2.0.
