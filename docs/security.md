# Security

This page describes Pragma's threat model and the limits of what it guarantees.
It is grounded in `src/pragma/coverage/runner.py`, `src/pragma/judge/client.py`,
and the plugin hooks under `plugin/hooks/`.

## What each tier does to your machine

| Tier | Reads code? | Executes code? | Network? | Default in plugin |
|---|---|---|---|---|
| Tier 1 — AST classifier | yes (static parse) | no | no | always on |
| Tier 2 — coverage gate | yes | **yes — runs the test under audit** | no | **off** (opt-in via `PRAGMA_COVERAGE=1`) |
| Tier 3 — LLM judge | yes | no | **yes — sends source to an endpoint** | off (opt-in via `PRAGMA_HOOK_WITH_LLM=1`) |

## Tier 1 only parses

The AST classifier reads the test source and walks its syntax tree. It never
runs the code. Tier 1 is the only tier the plugin enables by default.

## Tier 2 executes untrusted test code

To measure coverage, tier 2 spawns a subprocess that **runs the test file under
audit** (`python -m coverage run -m pytest <test file>`, or
`npx vitest run` for Vitest). That file is the very artifact being checked. It
may be AI-written, gamed, or hostile. Executing it runs arbitrary code with the
privileges of whoever invoked Pragma.

For this reason:

- **Tier 2 is opt-in.** It is off by default in the plugin and requires
  `PRAGMA_COVERAGE=1` in the PostToolUse hook, or `--with-coverage` on the CLI.
- **The subprocess environment is scrubbed.** The child process does not inherit
  the parent environment. `runner.py` builds the child env from a minimal
  allowlist — `PATH`, `HOME`, `TMPDIR`/`TEMP`/`TMP`, `LANG`/`LC_ALL`/`LC_CTYPE`,
  `PYTHONHASHSEED`, `PYTHONDONTWRITEBYTECODE`, `PYTHONPATH`, `SYSTEMROOT`, plus
  the coverage DB pointer — and drops everything else. Secret-bearing variables
  (`PRAGMA_*_API_KEY`, cloud credentials, tokens, DB passwords) are therefore
  not visible to the test under audit.
- **The subprocess is time-bounded.** Python: a 5-second per-test pytest timeout
  inside a 10-second outer subprocess kill-switch. Vitest: an 8-second timeout.

The allowlist and timeouts limit blast radius; they are **not** a sandbox. Only
enable tier 2 when you are comfortable executing the test files in question.

## Tier 3 sends source over the network

Tier 3 sends the **test source plus the resolved production source** to whatever
OpenAI-compatible endpoint `PRAGMA_LLM_BASE_URL` points at (DeepSeek by
default). Implications:

- Treat that payload like any other code-review send-off. For proprietary code,
  point tier 3 at a self-hosted endpoint (Ollama, LM Studio, vLLM, or an
  internal gateway) instead of a third-party SaaS.
- Tier 3 is opt-in precisely for this reason: it is off by default and only runs
  when `PRAGMA_HOOK_WITH_LLM=1` (hook) or `--with-llm` (CLI) is set **and** an
  API key is present.
- Tier 3 fails open: if the key, the `openai` package, or the API call is
  missing/failing, the judge is skipped silently and no `semantic_gaming`
  verdict is emitted.

## Pragma is a heuristic detector, not a security boundary

Pragma raises the cost of shipping a test that verifies nothing. It does not
prove a test is correct, and it can be bypassed.

- **The classifier is heuristic.** It recognizes known gaming *shapes*. A novel
  evasion that none of the rules match will classify as `verified`. Tier 1
  catches structural patterns; tier 2 demands the production code actually run;
  tier 3 reads both files — but none of them is a proof of correctness.
- **The hooks fail open by design.** If `pragma` cannot be invoked, the plugin
  hooks exit `0` (allow) rather than block. If the blocking-suffix list cannot
  be fetched (`pragma blocking`), the hook treats nothing as blocking. This
  keeps a broken environment from wedging all edits — but it means a determined
  actor who disables or hides `pragma` removes the gate entirely.
- **The hooks only block new gaming.** Pre-existing gaming in a file is not
  blocked; only verdicts the current edit *introduces* (relative to git `HEAD`)
  block. See [`hooks.md`](hooks.md).
- **Do not rely on Pragma as your only control.** It is a guardrail against
  accidental and lazy test-gaming by AI assistants, layered on top of human
  review and CI — not a replacement for them.

## Reporting

Pragma is MIT-licensed and provided as-is (see `LICENSE`). There is no warranty;
review the code before granting it the ability to execute test files in a
sensitive environment.
