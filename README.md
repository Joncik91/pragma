# Pragma

> The pragmatic gate that catches AI test-gaming.

Pragma is a Claude Code plugin that catches the thing AI assistants
do most often when asked to "write tests": write tests that pass
without actually verifying anything. The detector parses every test,
classifies the assertion shape, and refuses commits that contain:

- **`tautological`** — `assert True`, `x == x`, `1 == 1`, asserts on test setup not output.
- **`mocked-away`** — `mock.patch()` on the very function the test claims to test.
- **`mismatched`** — manifest says `expected=reject` but the body has no `pytest.raises`.
- **`weak`** *(warning)* — `assert x is not None` when the spec called for an exact value.

Real tests pass. Gamed tests get rejected at commit time, so the AI
can't fake the proof.

- **Current version:** v0.3.0 (2026-04-26)
- **License:** Apache-2.0
- **Status:** Alpha. Python-only. v0.3.0 ships the **anti-gaming detector** — the layer that classifies AI-written tests as `verified | tautological | mocked-away | weak | mismatched` so the gate can refuse tests that pass without verifying anything.

## What it looks like in Claude Code

You install Pragma once. From then on, every Claude Code session in
any project you've Pragma-enabled drives the gate for you. The user
types feature intent in plain English; Claude does the rest.

```text
You: build me an endpoint where users log in with email and password

Claude (driven by the Pragma plugin):
  → ran `pragma start "User can log in with email and password"`
  → manifest scaffolded, slice M01.S1 active, gate=LOCKED
  → wrote tests/test_req_001_happy_path.py with the failing assertion
  → ran `pragma unlock` → gate=UNLOCKED
  → wrote src/auth/login.py with @trace("REQ-001")
  → tests green; ran `pragma slice complete` → status=shipped
  → drafted commit via `pragma narrative commit`

Now read the PIL: REQ-001 — happy_path — verified (1 span observed).
```

You read the Post-Implementation Log, not the diff. The AI can't
fake the PIL because the PIL is built from OpenTelemetry spans
captured at runtime, not from what the AI claimed it did.

## Install

Two pieces — the CLI on your machine, and the plugin in Claude Code.

```shell
pipx install pragma
```

Then in Claude Code:

```text
/plugin install pragma@joncik91/pragma
```

That's it. Open Claude Code in any directory; the plugin's
SessionStart hook silently reads the project's Pragma state if any
exists, and the embedded skill teaches Claude the loop. Non-Pragma
directories are not ambushed — the hook exits silently when there's
no `pragma.yaml`.

## How the gate works (30 seconds)

1. **Declare** — `pragma.yaml` lists the requirement, its permutations (e.g. `valid_credentials → success`, `weak_password → reject`), and the files it touches. The plugin (or `pragma start`) writes this for you on first feature ask.
2. **Lock** — `pragma slice activate` flips the gate to `LOCKED`. Claude can see what to build, but cannot ship yet.
3. **Red test first** — A failing test goes in for each declared permutation. `pragma unlock` refuses to flip the gate until every required test exists *and is failing*.
4. **Implement** — Code is written with `@trace("REQ-NNN")` on the entry function so OpenTelemetry spans label which requirement was exercised.
5. **Green & ship** — `pragma slice complete` refuses if any test is red.
6. **Pre-commit battery** — gitleaks, ruff, mypy, semgrep, pytest, `pragma verify all` all run; one-line commit messages are refused.
7. **Read the PIL** — `pragma report --human` produces a Post-Implementation Log: every declared permutation, marked *exercised*, *possibly mocked*, or *never run*, with the span count as runtime proof.

## Why this exists

AI assistants generate code fast. Fast code without a check is a
repo you don't recognise by Tuesday. The existing guardrails — code
review, CI, tests — assume a human wrote the code and spot-check the
diff. Those assumptions break under AI-authored volume.

Pragma is the alternative: constrain the process so every diff
carries proof of what it claimed to build. You read the PIL, not the
diff. The AI can't fake the PIL because the PIL is built from
runtime evidence, not from what the AI said it did.

See [`docs/concepts.md`](docs/concepts.md) for the full rationale.

## Who Pragma is for

- **Solo devs using Claude Code / Cursor / Copilot** who want velocity *and* legibility.
- **Small teams adopting AI assistants** where "was the AI honest?" is the review bottleneck.
- **Non-coder product owners pairing with an AI** — the PIL is readable without diff-diving.

Not a fit (yet) for: non-Python projects, large teams with mature
gated-merge already in place, hard-real-time or safety-critical
work, or anyone who needs stable-release guarantees.

## Manual usage (without the plugin)

If you're not in Claude Code, or you want fine control, the CLI
surface is identical. One-command bootstrap:

```shell
pragma start "User can log in with email and password"
```

Auto-detects greenfield vs brownfield, scaffolds the manifest +
lockfile + hooks, plans the slice, and lands at `gate=LOCKED`. From
there:

```shell
# Write a failing test for each declared permutation:
#   tests/test_req_<id>_<permutation_id>.py
# (run `pragma slice status` or open pragma.yaml to see ids)

pragma unlock                   # refuses if any permutation lacks a red test
# write code, tests go green
pragma slice complete           # refuses if any test is red
pragma narrative commit --subject "feat: REQ-001 login flow" > /tmp/msg
git commit -F /tmp/msg
pragma report --human           # Post-Implementation Log
```

> **First commit gotcha:** ruff-format may reformat your code on
> first commit. Pre-commit treats that as a hook failure — re-stage
> with `git add -A` and re-run. Second attempt lands.

For the lower-level commands (`pragma init`, `pragma spec
add-requirement`, `pragma freeze`, `pragma slice activate`), see
[`docs/usage.md`](docs/usage.md).

## Documentation

| Read this | When |
|---|---|
| [`docs/concepts.md`](docs/concepts.md) | **Start here.** What Pragma is, why it exists, the mental model. |
| [`docs/usage.md`](docs/usage.md) | Step-by-step walkthrough of brownfield and greenfield flows (manual). |
| [`docs/reference.md`](docs/reference.md) | Every CLI flag, manifest field, audit event, hook. Includes the `REQ-` / `BUG-` / `KI-` issue ID conventions. |
| [`docs/doctor.md`](docs/doctor.md) | Diagnostic codes and their remediations. |
| [`docs/migrate.md`](docs/migrate.md) | Schema versions and `pragma migrate`. |
| [`docs/roadmap.md`](docs/roadmap.md) | Shipped versions, planned work, rationale. |
| [`docs/design.md`](docs/design.md) | Deeper architectural rationale. Internal-leaning. |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history. |
| [`plugin/skills/pragma/SKILL.md`](plugin/skills/pragma/SKILL.md) | The skill Claude follows. Useful for understanding what the plugin tells the agent. |

## What's shipped (v0.2.1)

- **Claude Code plugin** (v0.2.1) — marketplace-installable. SessionStart hook + skill.
- **`pragma start "<intent>"`** (v0.2.0) — one-command bootstrap. Auto-detects mode.
- **Manifest + lockfile** — `pragma.yaml` + `pragma.lock.json` with SHA-256 canonical hash. v2 schema (milestones + slices). `pragma migrate` upgrades v1 idempotently.
- **Gate** — `pragma slice activate|complete|cancel|status`, `pragma unlock` (with `--skip-tests --reason "..."` for brownfield retroactive imports). `.pragma/state.json` (atomic, flock-guarded, gitignored) + `.pragma/audit.jsonl` (append-only, fsync'd, committed).
- **Verify** — `pragma verify manifest|gate|discipline|integrity|commits|message|all`. Pre-commit + commit-msg + pre-push hooks. Pre-Pragma history is exempt by design.
- **Recovery** — `pragma doctor` with classifier diagnostics. `--emergency-unlock` for wedged gates, `--clean-spans` for span retention.
- **Reports** — `pragma report --json|--human`. PIL marks each permutation *ok | mocked | missing | partial | red | skipped* with a Diagnostics banner when input artifacts are absent.
- **SDK** — `pragma-sdk` (separate pip package): `@trace(...)`, `set_permutation(...)`, pytest plugin auto-registered. OpenTelemetry spans with `logic_id` + `permutation` attrs feed the PIL.
- **Narrative** — `pragma narrative commit|pr|adr|remediation` drafts gate-conformant prose from the active slice and PIL.

See [`CHANGELOG.md`](CHANGELOG.md) for the per-release detail.

## Upgrading an older manifest

```shell
pragma migrate                     # v1 → v2, idempotent
pragma init --brownfield --force   # refresh .pre-commit-config.yaml
```

See [`docs/migrate.md`](docs/migrate.md) for failure modes.

## Contributing

Issues and PRs welcome. The repo dogfoods its own tooling — your PR
runs the same gate on CI that every contributor runs locally. See
[`CHANGELOG.md`](CHANGELOG.md) for the recent release rhythm and
[`docs/roadmap.md`](docs/roadmap.md) for where we're headed.
