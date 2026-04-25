# Changelog

All notable changes to Pragma are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-04-24

**First alpha.** Pragma is a senior-engineer-on-rails framework for
AI-driven Python development: manifest-declared permutations, a
test-first gate, a Claude Code hook integration, a pre-commit safety
battery, and a Post-Implementation Log that shows which declared
behaviours were actually exercised at runtime.

This is alpha. The thesis works end-to-end on a fresh greenfield
project (docs-only flow produces a populated PIL with zero manual
`pytest` steps), and the author's own repo dogfoods the whole gate.
But the dogfood is still finding bugs per pass. v0.1.x patches will
continue until three consecutive clean dogfoods — that's when v0.2
starts.

### What's here

- **Manifest + lockfile** — `pragma.yaml` + `pragma.lock.json` with SHA-256 canonical hash. `pragma init --brownfield` or `--greenfield`, `pragma spec add-requirement`, `pragma freeze`, `pragma verify manifest`.
- **Schema v2** — milestones + slices. `pragma migrate` upgrades v1 manifests idempotently.
- **Gate** — `pragma slice activate|complete|cancel|status`, `pragma unlock`. `.pragma/state.json` (atomic, flock-guarded, gitignored) + `.pragma/audit.jsonl` (append-only, fsync'd, committed).
- **Verify** — `pragma verify manifest|gate|discipline|integrity|commits|message|all`. Pre-commit enforces shape + gate; commit-msg enforces WHY/trailer; pre-push runs the full battery.
- **Recovery** — `pragma doctor` with classifier diagnostics. `--emergency-unlock` for wedged gates, `--clean-spans` for span retention.
- **Reports** — `pragma report --json|--human` produce byte-identical output from the same inputs; Markdown PIL shows `ok|mocked|missing|partial|red|skipped` per permutation with a Diagnostics banner when input artifacts are absent.
- **SDK** — `pragma-sdk` (separate pip package): `@trace(...)`, `set_permutation(...)`, pytest plugin auto-registered via `pytest11`. OpenTelemetry spans with `logic_id` + `permutation` attrs feed the PIL.
- **Claude Code hooks** — SessionStart / PreToolUse / PostToolUse / Stop, sealed by hash, integrity-verifiable.
- **Narrative** — `pragma narrative commit|pr|adr|remediation` drafts copy from the active slice and PIL. **Content quality is weak** (known); the template is in place but the prose generation is a placeholder.
- **Docs** — README, `docs/concepts.md`, `docs/usage.md`, `docs/reference.md`, `docs/doctor.md`, `docs/migrate.md`, `docs/roadmap.md`.

### Known issues at v0.1.0

- **BUG-023** — single-permutation REQ reads `mocked` in the PIL when the test omits `set_permutation`. Aggregator comment claims a "courtesy" for single-perm that isn't implemented. Workaround: always call `set_permutation(id)` even when there's only one permutation.
- **BUG-024** — `pragma slice activate` on an already-shipped slice silently un-ships it. Destructive; no confirmation. Workaround: don't re-activate shipped slices.
- **BUG-025** — `span_count` in the PIL multiplies by the number of pytest invocations run across the project (unlock + complete + full-suite regen). Cosmetic; doesn't affect `status`.
- **BUG-026** — `pragma narrative commit` produces valid shape but placeholder "WHY" and a raw file list that includes `.pyc` + `.pragma/state.json.lock`. The senior-engineer prose isn't generated yet.

### Fixed since v0.1.0 (rolling, untagged)

- **BUG-044 / REQ-036** — `pragma init --greenfield` now runs `git init -q` when the cwd has no repo, so the README quick-start (`mkdir demo && cd demo && pragma init --greenfield`) actually wires the pre-commit / commit-msg / pre-push hooks. Previously `hooks_installed: false` shipped silently and the gate enforcement the README advertises was not in place on a literal first run. Brownfield is unaffected.

### Pre-v0.1.0 history

The git log contains the iterative development path from the first
commit through this release. Old release tags (v0.1.0 through v1.1.2)
were consolidated into this single v0.1.0 during release-cadence
cleanup on 2026-04-24 — they represented a 3-day patch sequence on
what was really an alpha, not a stable 1.x. See
`CHANGELOG-archive.md` for the detailed per-version notes if you
need the history.
