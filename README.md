<div align="center">

<img src="docs/logo.png" alt="Pragma" width="160" height="160">

# Pragma

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-E8954A.svg)](LICENSE)
[![pytest · vitest · jest](https://img.shields.io/badge/pytest%20·%20vitest%20·%20jest-supported-58D070)]()
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-E8954A)](https://docs.claude.com/en/docs/claude-code/overview)

**The test-gaming detector for the agentic era.**

Pragma reads the tests your AI assistant just wrote and refuses the ones that
pass without verifying anything: `assert True`, mocking the function under test,
a test name that promises an error path with a body that asserts nothing.

A Claude Code plugin and a small CLI, with three tiers of defense.

</div>

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
  - [As a Claude Code plugin](#as-a-claude-code-plugin)
  - [As a CLI](#as-a-cli)
  - [As a pre-commit hook](#as-a-pre-commit-hook)
- [CLI reference](#cli-reference)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Background

Ask an AI assistant to *make the tests pass* and it will. Sometimes by writing
real code. Sometimes by writing `assert True`, mocking the function under test,
or redefining the production class right there in the test file. Coverage is
green, CI is green, nothing is verified.

Static rules alone become whack-a-mole — a new evasion for every new rule. Pragma
layers three tiers, each catching what the previous one misses:

- **Tier 1 — AST classifier.** Fast, deterministic, local. Parses the test
  (never runs it) and flags known gaming shapes: tautological asserts, mocking
  the symbol under test, `pytest.skip` smuggled into a body, name/body
  mismatches, and more. **Always on.**
- **Tier 2 — coverage-of-target gate.** Runs the test under coverage
  instrumentation and asks: *did the production code's lines actually execute?*
  If not, the test isn't testing the target. Because this **executes the test
  file under audit**, it is **opt-in**: `--with-coverage` on the CLI, or
  `PRAGMA_COVERAGE=1` in the plugin hook. The subprocess runs with a
  secret-scrubbed allowlist environment (see [Security](docs/security.md)).
- **Tier 3 — LLM judge.** A model reads the test alongside the production source
  and decides whether the test verifies behavior or just asserts on its own
  mocks. DeepSeek by default; any OpenAI-compatible endpoint works. **Opt-in**:
  `--with-llm` on the CLI, or `PRAGMA_HOOK_WITH_LLM=1` in the hook. Configured
  via `PRAGMA_LLM_API_KEY`, `PRAGMA_LLM_BASE_URL`, `PRAGMA_LLM_MODEL`, and
  `PRAGMA_LLM_TIMEOUT`. This is the only tier that touches the network.

Pragma classifies Python (pytest), Vitest, and Jest test files. The expected
outcome (`success` / `reject`) is inferred from the test name and the production
target from the imports — zero config to start. See
[`docs/rules.md`](docs/rules.md) for every verdict.

## Install

Requires **Python 3.11+**.

From source (editable install with dev tooling):

```shell
pip install -e ".[dev]"
```

Optional extras:

```shell
pip install -e ".[coverage]"   # tier 2 helper (pytest-timeout)
pip install -e ".[llm]"        # tier 3 LLM judge (openai SDK)
```

This installs the `pragma` command. Verify it:

```shell
pragma --help
```

In Claude Code, install the plugin from this repository:

```text
/plugin install pragma@joncik91/pragma
```

The plugin's hooks scan edits to files matching `test_*.py`, `*/tests/*.py`, and
`*/tests/*/*.py`. Tier 1 always runs; tiers 2 and 3 are opt-in via the
environment variables above. See [`docs/hooks.md`](docs/hooks.md).

## Usage

### As a Claude Code plugin

Once installed, the plugin gates test-file edits automatically:

- **PreToolUse** inspects a full-file `Write` before it lands and runs tier 1.
- **PostToolUse** re-checks on disk after `Edit` / `MultiEdit`, and is where
  `PRAGMA_COVERAGE=1` (tier 2) and `PRAGMA_HOOK_WITH_LLM=1` (tier 3) take effect.

The hook blocks only the gaming an edit *introduces* — pre-existing gaming in a
file is not your problem to fix right now. Full semantics, exit codes, and
environment variables are in [`docs/hooks.md`](docs/hooks.md).

### As a CLI

The CLI works on its own:

```shell
# tier 1 only — fast, deterministic
pragma verify tests path/to/test_login.py

# tier 1 + tier 2 — runs the test under coverage, requires target lines to execute
pragma verify tests path/to/test_login.py --with-coverage

# all three tiers
pragma verify tests path/to/test_login.py --with-coverage --with-llm
```

Default output is JSON; `--human` prints one `path::test [kind] evidence` line
per verdict. The command exits `1` when any blocking verdict fires, `0`
otherwise.

```console
$ pragma verify tests tests/fixtures/blocking/gamed_tautology.py --human
tests/fixtures/blocking/gamed_tautology.py::test_login_happy_path [python.tautological] `assert True` is a constant truthy
```

### As a pre-commit hook

Wire the tier-1 classifier into pre-commit:

```shell
pragma init-precommit
```

This writes a `.pre-commit-config.yaml` that runs `pragma verify tests` on
staged test files. For the manual snippet, see [`docs/PRECOMMIT.md`](docs/PRECOMMIT.md).

## CLI reference

Full command and option reference, plus the plugin, rules, and security pages,
live under [`docs/`](docs/README.md):

- [CLI reference](docs/cli.md)
- [Plugin / hooks integration](docs/hooks.md)
- [Rules reference](docs/rules.md)
- [Security](docs/security.md)

## Maintainers

Maintained by the Pragma contributors. See the repository for issues and pull
requests.

## Contributing

PRs welcome. Useful directions:

- **More languages.** The verdict-table shape generalises — Go's `_test.go`,
  Rust's `#[test]`, Ruby's RSpec all have analogous gaming patterns.
- **New tier 1 verdicts** for shapes the classifier doesn't yet catch (open an
  issue with a real-world test file showing the pattern).
- **Replay corpora** — anonymised test files where a tier got it wrong, so the
  classifier can be tuned.

Set up the dev environment with `pip install -e ".[dev]"` and run the suite with
`pytest`. See [`docs/PRECOMMIT.md`](docs/PRECOMMIT.md) for the existing
pre-commit integration.

## License

[MIT](LICENSE) © Pragma contributors.
