# Plugin / Hooks Integration Guide

Pragma ships as a Claude Code plugin under `plugin/`. The plugin registers two
hooks (`plugin/hooks/hooks.json`) that gate edits to test files. This page
documents exactly what those hooks do, grounded in
`plugin/hooks/pre-tool-use.sh`, `plugin/hooks/post-tool-use.sh`, and
`plugin/hooks/check_diff.py`.

## Registered hooks

Both hooks match the `Edit|Write|MultiEdit` tools (`plugin/hooks/hooks.json`):

| Hook | Script | Role |
|---|---|---|
| `PreToolUse` | `pre-tool-use.sh` | Gate a **`Write`** before the file lands on disk. |
| `PostToolUse` | `post-tool-use.sh` | Re-check on disk after **`Edit` / `MultiEdit`** (and `Write`). |

### File filter

Both hooks only act on paths matching one of:

```
*test_*.py   */tests/*.py   */tests/*/*.py
```

Anything else exits `0` (allow) immediately. The hooks also exit `0` if
`python3` is unavailable or no working `pragma` invocation is found — Pragma
degrades silently rather than blocking edits when it cannot run.

## PreToolUse: Write-only blocking

`pre-tool-use.sh`:

1. Reads the tool-call JSON from stdin.
2. Exits `0` unless the tool is `Edit`, `Write`, or `MultiEdit`.
3. Extracts `tool_input.content` **only when the tool is `Write`** — for
   `Edit`/`MultiEdit` the content field is empty, so the hook exits `0` and
   leaves those cases to `PostToolUse`.
4. Writes the proposed content to a tempfile and calls
   `check_diff.py <on_disk_path> <tempfile>`.

So at `PreToolUse` time, only a full-file `Write` is inspected. It runs
**tier 1 only** — the PreToolUse path passes no `--with-coverage` / `--with-llm`
flags.

## PostToolUse: detect-after-write

`post-tool-use.sh` runs after the edit has already been applied to disk. It
catches `Edit` / `MultiEdit` (and `Write`) by re-reading the file from disk and
calling `check_diff.py <path> <path>` (on-disk file is its own candidate).

PostToolUse is where tiers 2 and 3 can be enabled, by environment variable:

| Variable | Effect |
|---|---|
| `PRAGMA_COVERAGE=1` | Adds `--with-coverage` (tier 2). **Off by default.** Tier 2 executes the test file under audit — see [`security.md`](security.md). |
| `PRAGMA_HOOK_WITH_LLM=1` | Adds `--with-llm` (tier 3, warning-only). **Off by default.** |

Any other value (or unset) leaves the tier off. With neither set, PostToolUse
runs tier 1 only.

## Diff semantics: only new gaming blocks

`check_diff.py` does not block on pre-existing gaming. It blocks only when the
**current edit introduces** a new blocking verdict:

1. Classify the candidate (new) file; collect the set of test names with
   blocking verdicts (`new_blocking`).
2. If `new_blocking` is empty, exit `0`.
3. Read the previous version of the file from `git HEAD` (if the file is
   tracked). Classify it; collect `old_blocking`.
4. Compute `new_only = new_blocking - old_blocking`.
5. If `new_only` is empty, exit `0` — the edit added no new gaming.
6. Otherwise print the offending `path::test [kind] evidence` lines to stderr
   plus remediation guidance, and exit `2`.

When the file is not in git (no `HEAD` version), `old_blocking` is empty, so all
blocking verdicts in the candidate count as new.

### Blocking-suffix source of truth

`check_diff.py` learns which verdict suffixes block by shelling out to
`pragma blocking` (falling back to `python -m pragma blocking`). If neither
invocation succeeds, the blocking set is empty and **nothing blocks** — a
deliberate fail-open so a broken environment never wedges edits.

### Unparseable files

A file Pragma cannot parse (syntax error, non-UTF-8) produces a single
non-blocking `*.unparseable` verdict. `check_diff.py` logs it to stderr
(`Pragma skipped a file it could not parse`) but does not block — an unparseable
file is noise, not gaming, yet is never silently treated as clean.

## Exit codes

`check_diff.py` (and therefore both shell hooks) follow the Claude Code hook
contract:

| Exit | Meaning |
|---|---|
| `0` | Allow. No new blocking verdict, or Pragma could not run. |
| `2` | Block. The edit introduced one or more new blocking verdicts. |

Note this differs from the standalone CLI, where `pragma verify tests` exits `1`
on a blocking verdict. The `2` exit code is the hook-protocol block signal; the
`1` exit code is the CLI's "blocking found" signal.

## CLI version differences

The hook env vars (`PRAGMA_COVERAGE`, `PRAGMA_HOOK_WITH_LLM`) apply only to the
plugin hooks. Running Pragma directly uses CLI flags instead:

```shell
pragma verify tests path/to/test_login.py                                  # tier 1
pragma verify tests path/to/test_login.py --with-coverage                  # tier 1 + 2
pragma verify tests path/to/test_login.py --with-coverage --with-llm       # all three
```

See [`cli.md`](cli.md) for the full CLI reference.
