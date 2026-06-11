# CLI Reference

The `pragma` command is installed by the `pragma` package (`[project.scripts]`
in `pyproject.toml`). All commands and options below are taken from
`src/pragma/cli.py` and verified by running `--help`.

```
pragma [OPTIONS] COMMAND [ARGS]...
```

`pragma` with no arguments prints help and exits (no default action).

## Commands

| Command | Purpose |
|---|---|
| `pragma verify tests` | Classify one or more test files; exit non-zero if any blocking verdict fires. |
| `pragma init-precommit` | Write a `.pre-commit-config.yaml` that runs `pragma verify tests`. |
| `pragma blocking` | Print the set of blocking verdict suffixes as a JSON array. |

---

## `pragma verify tests`

```
pragma verify tests [OPTIONS] FILES...
```

Classify every test function in each file in `FILES`. Each `FILES` entry must
exist, be a file (not a directory), and be readable — Typer rejects the call
otherwise.

### Options

| Option | Default | Effect |
|---|---|---|
| `--human` | off | Human-readable output: one `path::test_name [kind] evidence` line per verdict, instead of JSON. |
| `--with-coverage` | off | Tier 2. Run the tests under coverage instrumentation and require the inferred production target's lines to actually execute. Python coverage is fully supported; the flag also drives Vitest coverage when a Vitest project is detected. **This executes the test file under audit.** |
| `--with-llm` | off | Tier 3 (warning only). Send the test plus resolved production source to an LLM judge. Requires `PRAGMA_LLM_API_KEY` (see the [LLM judge section](#tier-3-environment-variables)). |

### Output

Default (JSON, keys sorted):

```json
{"blocking": false, "results": {"<path>": [{"evidence": "...", "kind": "python.verified", "test_name": "..."}]}}
```

With `--human`:

```
<path>::<test_name> [<kind>] <evidence>
```

### Exit codes

| Exit | Meaning |
|---|---|
| `0` | No blocking verdict in any file. |
| `1` | At least one blocking verdict was found (see [`rules.md`](rules.md) for which kinds block). |

A blocking verdict is any verdict whose suffix is in the blocking set
(`src/pragma/blocking.py`). Warning verdicts (e.g. `*.empty_body`,
`*.semantic_gaming`) appear in the output but never raise the exit code.

### Verified examples

A gamed file blocks (exit 1):

```console
$ pragma verify tests tests/fixtures/blocking/gamed_tautology.py --human
tests/fixtures/blocking/gamed_tautology.py::test_login_happy_path [python.tautological] `assert True` is a constant truthy
$ echo $?
1
```

An honest file passes (exit 0):

```console
$ pragma verify tests tests/fixtures/verified_ok.py
{"blocking": false, "results": {"tests/fixtures/verified_ok.py": [{"evidence": "assertion passes runtime-derived value through real comparison", "kind": "python.verified", "test_name": "test_login_happy_path"}]}}
$ echo $?
0
```

---

## `pragma init-precommit`

```
pragma init-precommit [OPTIONS]
```

Write a `.pre-commit-config.yaml` in the current directory whose single hook
runs `pragma verify tests` over staged test files matching
`(^|/)test_.*\.py$|/tests/.*\.py$`.

### Options

| Option | Default | Effect |
|---|---|---|
| `--force` | off | Overwrite an existing `.pre-commit-config.yaml`. |

### Behavior

- If `.pre-commit-config.yaml` already exists and `--force` is not passed, the
  command prints a JSON error object (`{"ok": false, "error": "exists", ...}`)
  and exits `1`.
- On success it prints `{"ok": true, "wrote": ".pre-commit-config.yaml"}` and
  exits `0`.

For the manual snippet (if you would rather merge it into an existing config),
see [`PRECOMMIT.md`](PRECOMMIT.md).

---

## `pragma blocking`

```
pragma blocking
```

Print the blocking-suffix set (`src/pragma/blocking.py`) as a sorted JSON
array. This is the source of truth the plugin hook reads so it never hardcodes
the suffix list.

### Verified example

```console
$ pragma blocking
["conditional", "mismatched", "mocked-away", "module_attr_reassignment", "module_shimmed", "monkeypatched", "no_success_assertion", "orphan_mock", "orphan_test", "skipped", "stub_error_match", "swallowed", "target_not_covered", "tautological", "test_failing_gaming", "xfail_gaming"]
```

---

## Tier 3 environment variables

Tier 3 (`--with-llm`) reads these variables (`src/pragma/judge/client.py`):

| Variable | Default | Purpose |
|---|---|---|
| `PRAGMA_LLM_API_KEY` | (none) | API key. Preferred, provider-agnostic. Tier 3 is skipped silently if no key is set. |
| `PRAGMA_DEEPSEEK_API_KEY` | (none) | DeepSeek-specific alias, used if `PRAGMA_LLM_API_KEY` is unset. |
| `PRAGMA_ANTHROPIC_API_KEY` | (none) | Legacy alias, used if both above are unset. |
| `PRAGMA_LLM_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI-compatible endpoint. |
| `PRAGMA_LLM_MODEL` | `deepseek-chat` | Model name. |
| `PRAGMA_LLM_TIMEOUT` | `30.0` | Per-request timeout in seconds. |

Any OpenAI-compatible endpoint works (OpenAI, Groq, a local Ollama / LM Studio /
vLLM server). Tier 3 requires the `openai` package — install with the `llm`
extra (`pip install "pragma[llm]"`); if it is missing, tier 3 is skipped
silently.
