# Pragma

> Senior engineer on rails for AI-driven development.

Pragma keeps AI-generated code honest. It sits between you (or your
AI assistant) and git, forcing every feature through a declared
specification, a test-first gate, and a plain-English report of what
actually ran — so you can ship code an AI wrote and know what you're
shipping.

- **Current version:** v0.1.0 (2026-04-24)
- **License:** Apache-2.0
- **Status:** Alpha. Python-only. Thesis works end-to-end on a fresh greenfield; dogfood is still finding bugs. See [`CHANGELOG.md`](CHANGELOG.md) for the release cadence plan and known issues.

## What Pragma does in 30 seconds

1. You declare the feature in `pragma.yaml` — requirement, permutations, files touched.
2. `pragma slice activate` locks the gate. The AI can see what to build, but cannot commit yet.
3. Failing tests go in first. `pragma unlock` refuses without them.
4. Code gets written. Tests go green. `pragma slice complete` refuses if any are red.
5. The commit goes through the safety battery (gitleaks, ruff, mypy, semgrep, pytest).
6. `pragma report --human` produces a Post-Implementation Log: every declared behaviour, marked *exercised*, *possibly mocked*, or *never run*.

The AI still writes the code. Pragma makes it prove what it did.

## Install

```shell
pipx install pragma
```

Or in a project venv:

```shell
python -m venv .venv
source .venv/bin/activate
pip install "pragma[dev]"
```

Verify:

```shell
pragma --help
```

## Quick start — brownfield (existing repo)

```shell
cd your-project/
pragma init --brownfield
pragma spec add-requirement --id REQ-001 \
    --title "User can log in" \
    --description "Operator signs in with email + password" \
    --touches src/auth/login.py \
    --permutation 'valid_credentials|Returns JWT on valid email + strong password|success' \
    --permutation 'weak_password|Rejects weak passwords|reject'
pragma freeze
git add pragma.yaml pragma.lock.json .pre-commit-config.yaml
git commit -m "chore: adopt pragma"
```

## Quick start — greenfield (new project)

```shell
mkdir demo && cd demo
pragma init --greenfield --name demo --language python
# write docs/problem.md — one "# heading" per user capability
pragma spec plan-greenfield --from docs/problem.md
pragma freeze
```

## Ship a slice

```shell
pragma slice activate M01.S1       # gate flips LOCKED
# write a failing test for each declared permutation, named
# test_req_<id>_<permutation_id> to match what `pragma unlock` checks.
# Run `pragma slice status` or open pragma.yaml to see the exact ids.
pragma unlock                      # refuses if any permutation lacks a red test
# write code, tests go green
pragma slice complete              # refuses if any test is red
git commit -m "$(cat <<'MSG'
feat: REQ-001 login flow

WHY: <one paragraph on why this slice matters; pre-commit checks shape>

Co-Authored-By: <name> <email>
MSG
)"
pragma report --human              # Post-Implementation Log
```

`pragma slice status` at any time. `pragma slice cancel` to abandon.

> **First commit gotcha:** ruff-format may reformat your code (and
> Pragma's scaffolded files) on first commit. Pre-commit treats that
> as a hook failure — re-stage with `git add -A` and re-run the
> commit. Second attempt lands.

The pre-commit / commit-msg / pre-push hooks are wired by `pragma init`
(see [`docs/reference.md`](docs/reference.md)). They enforce shape on
the message above; a one-line subject without WHY/trailer is
refused.

## Documentation

| Read this | When |
|---|---|
| [`docs/concepts.md`](docs/concepts.md) | **Start here.** What Pragma is, why it exists, the mental model. |
| [`docs/usage.md`](docs/usage.md) | Step-by-step walkthrough of brownfield and greenfield flows. |
| [`docs/reference.md`](docs/reference.md) | Every CLI flag, manifest field, audit event, hook. |
| [`docs/doctor.md`](docs/doctor.md) | Diagnostic codes and their remediations. |
| [`docs/migrate.md`](docs/migrate.md) | Schema versions and `pragma migrate`. |
| [`docs/roadmap.md`](docs/roadmap.md) | Shipped versions, planned work, rationale. |
| [`docs/design.md`](docs/design.md) | Deeper architectural rationale. Internal-leaning. |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history. |

## Why this exists

AI assistants generate code fast. Fast code without a check is a repo
you don't recognise by Tuesday. The existing guardrails — code review,
CI, tests — assume a human wrote the code and spot-check the diff. Those
assumptions break under AI-authored volume.

Pragma is the alternative: constrain the process so every diff carries
proof of what it claimed to build. You read the PIL, not the diff.
The AI can't fake the PIL because the PIL is built from runtime
evidence, not from what the AI said it did.

See [`docs/concepts.md`](docs/concepts.md) for the full rationale.

## Who Pragma is for

- Solo devs using Claude Code / Cursor / Copilot who want velocity *and* legibility.
- Small teams adopting AI assistants where "was the AI honest?" is the review bottleneck.
- Non-coder product owners pairing with an AI — the PIL is readable without diff-diving.

Not a fit (yet) for: non-Python projects, large teams with mature gated-merge already in place, hard-real-time or safety-critical work, or anyone who needs stable-release guarantees — this is alpha.

## Upgrading an older manifest

```shell
pragma migrate                     # v1 → v2, idempotent
pragma init --brownfield --force   # refresh .pre-commit-config.yaml
```

See [`docs/migrate.md`](docs/migrate.md) for failure modes.

## What's in v0.1

- **Greenfield bootstrap** — `pragma init --greenfield` scaffolds a seed manifest + `claude.md` primer. `pragma spec plan-greenfield` turns a problem statement into REQ placeholders.
- **Manifest + schema v2** — `pragma init --brownfield`, `pragma spec add-requirement`, `pragma freeze`, `pragma verify manifest`; dual-file integrity via SHA-256 over canonical JSON; milestones + slices hierarchy.
- **Gate** — `pragma slice activate|complete|cancel|status`, `pragma unlock`. `.pragma/state.json` (gitignored, atomic, flock-guarded) + `.pragma/audit.jsonl` (committed, append-only, fsync'd).
- **Verify** — `pragma verify all` runs manifest + gate + discipline + integrity + commits. Commit-msg and pre-push hooks enforce shape.
- **Recovery** — `pragma doctor` with classifier diagnostics. `--emergency-unlock` for wedged gates, `--clean-spans` for span retention.
- **Reports** — `pragma report --json` / `--human` (PIL). `pragma narrative commit|pr|adr|remediation` drafts copy from the active slice (prose quality is weak — BUG-026).
- **Claude Code hooks** — SessionStart / PreToolUse / PostToolUse / Stop, sealed by hash.

Known alpha bugs at v0.1.0: see [`CHANGELOG.md`](CHANGELOG.md#known-issues-at-v010).

## Contributing

Issues and PRs welcome. The repo dogfoods its own tooling — your PR
runs the same gate on CI that every contributor runs locally. See
[`CHANGELOG.md`](CHANGELOG.md) for the recent release rhythm and
[`docs/roadmap.md`](docs/roadmap.md) for where we're headed.
