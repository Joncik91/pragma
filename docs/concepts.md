# Pragma concepts

This page explains **what Pragma is, why it exists, and how to think about
it**. For the "type these commands in this order" walkthrough, see
[`usage.md`](usage.md). For every flag and field, see
[`reference.md`](reference.md).

## What Pragma is

Pragma is a Python CLI plus a pre-commit gate plus a small Claude Code
integration that turns "I want to vibe-code this feature" into "here's
a specification, here are the failing tests that prove what 'done'
means, now the AI can write the code and I can verify it didn't
cheat."

It sits between you (or your AI assistant) and your git history. It
doesn't write your code. It makes sure:

- Every feature is **declared in a manifest** before anyone touches `src/`.
- Every declared feature has **failing tests per permutation** before implementation starts.
- Every commit **respects shape** (subject length, WHY: line, author trailer).
- Every shipped slice produces a **Post-Implementation Log** — a plain-English report of which declared behaviours were actually exercised at runtime, not just mock-passed.

The product thesis: **AI can generate code fast; AI-generated code is
trustworthy only when it's forced to prove what it did.** Pragma is the
force-function.

## Who Pragma is for

- **Solo devs using Claude Code / Cursor / Copilot** who want to move fast without waking up to a repo they don't recognise.
- **Small teams** adopting AI assistants where the review bottleneck is "was the AI honest about what it built?"
- **Non-coder product owners** pairing with an AI to ship real software — Pragma's PIL means the operator can read the report and trust the summary without reading diffs.

## Who Pragma is **not** for (yet)

- Large teams with mature CI/CD + gated merges already in place — Pragma's gate overlaps with what you have.
- Non-Python projects as of v1.0 (TypeScript lands in v1.1; Go/Rust after).
- Hard-real-time, embedded, or safety-critical work — Pragma is discipline scaffolding, not a certifier.
- Teams that want a silent tool — Pragma is opinionated, noisy, and refuses things by design. If that's annoying to you, it's the wrong fit.

## The five core pieces

### 1. The Manifest (`pragma.yaml` + `pragma.lock.json`)

A **declaration** of what the project is supposed to do, before any
implementation. Human-written YAML. Every requirement has:

- A unique ID (`REQ-001`).
- A one-line title, a longer description.
- A list of **permutations** — every distinct behaviour the requirement
  must exhibit. `valid_credentials | success`, `weak_password | reject`,
  `rate_limited | reject`, etc. Each permutation declares its expected
  verdict.
- A list of files the requirement **touches**.

The lockfile is a deterministic hash of the canonical manifest.
Pre-commit refuses to commit when YAML and lock disagree. The manifest
is the project's source of truth; the lock is the fingerprint that
proves nothing silently shifted.

**Why a manifest at all?** Because "what does done look like?" needs
to be written down before the AI writes code. Otherwise you're
vibe-checking a 2000-line diff against a vague memory of what you
wanted. The manifest forces the spec out of your head and onto disk.

### 2. The Gate (`.pragma/state.json` + audit log)

A state machine with three positions per slice: **LOCKED**, **UNLOCKED**,
**shipped**.

- `pragma slice activate M01.S1` flips LOCKED. From here, `src/` edits are
  the AI's to make, but it can't commit yet.
- `pragma unlock` is refused unless every declared permutation has a
  **failing test** on disk, named per convention
  (`test_req_001_valid_credentials`). This is the "test-first" invariant.
- You then write code. Tests go green.
- `pragma slice complete` is refused unless every required test is
  **green**. Then the slice ships.

Every transition writes one line to `.pragma/audit.jsonl` —
append-only, committed. Six months from now someone can read the audit
and reconstruct exactly what happened.

**Why a gate at all?** Because "write tests first" is advice that
dissolves on contact with a deadline. A gate makes it mechanical: you
cannot land code without the corresponding red test having existed at
some point. The audit proves it.

### 3. The Safety Battery (`.pre-commit-config.yaml`)

Every commit runs: gitleaks (secrets), ruff-format + ruff-lint
(style), mypy --strict (types), semgrep (patterns), pip-audit
(vulns), pytest (tests), plus Pragma's own `verify all` (manifest,
gate, discipline, integrity, commit shape).

All auto-run. All block the commit on failure. No `--no-verify`
escape hatch in normal flow.

**Why a battery at all?** Because AI code has characteristic
weaknesses — it hallucinates imports, leaves secrets in examples,
over-engineers, generates dead branches. The battery catches the ones
you'd otherwise miss under time pressure.

### 4. The SDK + PIL (Post-Implementation Log)

`pragma-sdk` is a separate pip package with `@trace("REQ-001")` and
`set_permutation("valid_credentials")`. When a test runs code
instrumented with `@trace`, the SDK emits an OpenTelemetry span
carrying `logic_id=REQ-001` and the active permutation. These dump to
`.pragma/spans/*.jsonl` at session end.

`pragma report --human` reads those spans plus the pytest JUnit XML
and produces a Markdown **Post-Implementation Log**: a table showing
every declared permutation, whether it was "exercised at runtime"
(real span seen), "test passed but no span" (possibly mocked), or
"never run."

Both artifacts — the spans JSONL and the junit XML — are produced
automatically by `pragma slice complete` / `pragma unlock` / `pragma
verify gate`, via Pragma's internal pytest subprocess invocations.
You don't need a separate `pytest` step to populate the PIL. If either
artifact is absent on a run of `pragma report`, the output includes a
diagnostic banner naming what's missing and the one-line fix.

**Why a PIL at all?** Because "tests pass" is lying to you when the
test mocked the thing it was supposed to prove. The PIL
distinguishes "the real code path ran and asserted" from "a stub
returned the expected value." That's the difference between a trusted
summary and a false-confident one.

### 5. The Claude Code integration

A `.claude/settings.json` wired into four hook events:

- **SessionStart** — injects gate state into the AI's context. "Active slice is M01.S1, gate is LOCKED, these permutations need red tests."
- **PreToolUse** — denies Edit/Write on `src/` when the gate is LOCKED (the AI has to unlock first, which requires red tests).
- **PostToolUse** — runs discipline checks on just-edited files. Blocks if cyclomatic complexity > threshold, if a file ballooned past budget, etc.
- **Stop** — runs `pragma verify all` at turn-end. Refuses the turn if the repo is in a broken state.

The hooks are opt-in — you install them via `pragma init --brownfield`
or `--greenfield`. They require a hash seal (`pragma hooks seal`)
that detects tampering.

**Why Claude Code integration at all?** Because AI assistants are the
primary thing that will try to commit broken code. The gate catches
it at `git commit`, but blocking earlier (at the AI's tool call) is
cheaper — the AI gets told "no, unlock first" before it generates the
half-finished change.

## The daily flow

```shell
# 1. Declare what you're building. Edit pragma.yaml or run
#    `pragma spec add-requirement`.
pragma freeze                   # regenerate pragma.lock.json

# 2. Activate the slice. Gate flips LOCKED.
pragma slice activate M01.S1

# 3. Write failing tests per declared permutation.
#    Name them test_req_001_<permutation_id>.

# 4. Unlock. Refuses if any permutation lacks a red test.
pragma unlock

# 5. Write code. AI or human. Tests go green.

# 6. Ship. Refuses if any permutation test is red.
pragma slice complete

# 7. Commit. Pre-commit runs the battery + pragma verify all.
git commit -m "feat: REQ-001 login flow"

# 8. See the PIL.
pragma report --human
```

## When to prune span files (`--clean-spans`)

Every `pytest` run writes one `test-run-{ts}-{pid}-{uuid}.jsonl` under
`.pragma/spans/`. Each file is the raw trace for that run — one span
per `@trace`'d function call. Consumed by `pragma report` and the PIL
to show which declared permutations were actually exercised.

Only the **most recent** runs matter for reporting — PIL reflects the
latest test pass, not last month's. Older files are evidence of
history but have diminishing value per additional file. On a busy
project that's dozens of files/day. After a year: thousands of files,
hundreds of MB. `ls .pragma/spans/` slows, `pragma report` scans
more, disk fills.

`pragma doctor --clean-spans` prunes on demand with two retention
strategies:

- `--keep-runs N` — keep the N most recent runs' traces, drop older.
  Good when you want a fixed ceiling on file count.
- `--keep-days D` — keep anything from the last D days. Good when you
  want "a month of forensic depth," don't care if that's 5 runs or 5000.

Both together take the union — a file is kept when it satisfies
*either* rule.

**When would you pin this in the manifest?** When your retention
policy is stable across contributors. Write it once:

```yaml
spans_retention:
  keep_runs: 100
  keep_days: 30
```

CLI flags override the manifest block for one invocation.

**When would you *not* prune?**

- Small project, low test frequency — directory stays small, no problem.
- Compliance requirement to retain all test evidence forever — don't prune; handle size with rotation or off-repo archival instead.

Nothing is auto-pruned. `pragma doctor --clean-spans` runs on demand,
never as a side effect of another command. Every non-dry run appends
a `spans_cleaned` line to `.pragma/audit.jsonl` so the forensic record
of *what rolled off* survives the rolloff itself.

## Brownfield vs greenfield

**Brownfield** — you have a repo with working code and want to add
Pragma. `pragma init --brownfield` writes `pragma.yaml`,
`.pre-commit-config.yaml`, and `.claude/settings.json`. The first
manifest is empty; you declare requirements as you touch code going
forward. The pre-existing code doesn't need to be retrofitted.

**Greenfield** — you're starting a new project from zero.
`pragma init --greenfield --language python --name myapp` scaffolds a
full project: `src/myapp/`, `tests/`, `pyproject.toml`, `pragma.yaml`
with one placeholder milestone, a README, a `.gitignore`, `pytest.ini`
— plus all the Pragma machinery. `pragma spec plan-greenfield --from
docs/problem.md` takes a problem statement, extracts requirements
using an AI, and writes a real manifest you can then refine by hand.

Both flows end in the same place: a repo where every commit has to
pass the gate + battery.

## What Pragma is not

- **Not a code generator.** Pragma doesn't write your code. It shapes
  the constraints the code-writer (human or AI) has to satisfy.
- **Not a linter.** Linters tell you about style; Pragma tells you
  whether you actually built what you claimed you'd build.
- **Not a CI replacement.** Pragma runs pre-commit and pre-push on
  your machine. CI still runs. The two are complementary — Pragma
  catches it before the push; CI catches cross-machine regressions.
- **Not a test framework.** Pragma uses pytest (and only pytest for
  now). The SDK's pytest plugin is how spans get emitted.
- **Not a mandatory methodology.** You can turn any piece off. But
  the design pressure is that the pieces work together — disable one
  and you lose more than its own value.

## Further reading

- [`usage.md`](usage.md) — step-by-step walkthrough of both flows.
- [`reference.md`](reference.md) — every CLI flag, manifest field, hook event.
- [`doctor.md`](doctor.md) — diagnostic codes and their remediations.
- [`roadmap.md`](roadmap.md) — what's shipped, what's next.
- [`design.md`](design.md) — deeper architectural rationale. Internal-leaning; read only after the above.
