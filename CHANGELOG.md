# Changelog

All notable changes to Pragma are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] — 2026-04-25

**First post-v0.1.0 patch.** Three consecutive clean strict-README
walkthroughs (rounds 12, 13, 14) cleared the cadence rule for an
alpha bump.

### Fixed

- **BUG-036 / REQ-032** — `pragma init` now runs `pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push`. Previously the hooks were never wired so the gate enforcement the README advertises was structurally bypassable on a fresh project.
- **BUG-037 / REQ-033** — scaffolded pre-commit `pragma verify all` hook resolves the pragma binary via the same `{{ pragma_python_bin }} → .venv/bin/python3 → python3` chain init was launched with, instead of bare `python -m pragma`. First-run users without a project venv no longer hit "No module named pragma.__main__".
- **BUG-038 / BUG-039 / REQ-034** — scaffolded pytest hook uses the same PY resolution chain; scaffolded pip-audit ignores GHSA-58qw-9mgm-455v by default. Brought the scaffolded battery template back in sync with Pragma's own `.pre-commit-config.yaml`.
- **BUG-040** — README's slice-activate example used a stale test-name placeholder; now points at `pragma slice status` / `pragma.yaml` to discover the right ids.
- **BUG-042 / REQ-035** — scaffolded `.gitignore` covers `.pragma/state.json`, `.pragma/state.json.lock`, `__pycache__/`, and `*.pyc`. First `git add -A` no longer accidentally stages bytecode + flock files; ruff-format and pytest no longer "modify" cache files on every commit.
- **BUG-043** — README warns about the ruff-format first-commit speedbump (re-stage with `git add -A` and re-run; second attempt lands).
- **BUG-044 / REQ-036** — `pragma init --greenfield` runs `git init -q` when the cwd has no repo, so the README quick-start (`mkdir demo && cd demo && pragma init --greenfield`) actually wires the pre-commit / commit-msg / pre-push hooks. Previously `hooks_installed: false` shipped silently. Brownfield is unaffected.

### Cadence

The strict-README dogfood passed three rounds in a row with zero
findings under varied project shapes (1-REQ/1-perm, 2-REQ/2-perm,
multiple project names). v0.1.x patch cycle continues until the
known issues below either ship a fix or the workarounds remain
stable through three more rounds.

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

### Pre-v0.1.0 history

The git log contains the iterative development path from the first
commit through this release. Old release tags (v0.1.0 through v1.1.2)
were consolidated into this single v0.1.0 during release-cadence
cleanup on 2026-04-24 — they represented a 3-day patch sequence on
what was really an alpha, not a stable 1.x. See
`CHANGELOG-archive.md` for the detailed per-version notes if you
need the history.
