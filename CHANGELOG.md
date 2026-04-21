# Changelog

All notable changes to Pragma are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] — 2026-04-21

### Added

- Monorepo split: `packages/pragma-sdk/` + `packages/pragma/` with uv workspace.
- `pragma-sdk` runtime package: `@trace` decorator, `set_permutation` context manager, pytest plugin with InMemorySpanExporter and JSONL dump to `.pragma/spans/`.
- `pragma report --json` / `--human`: Post-Implementation Log with per-permutation status and `passed-but-mocked` heuristic. Byte-deterministic JSON output.
- `pragma narrative commit|pr|adr|remediation`: senior-engineer artifact generators backed by Jinja templates.
- CI matrix: sdk-isolated job, full job, report-determinism diff job.
- REQ-005 / M01.S3 declaring the v0.4 contract, dogfooded with one @trace'd Pragma helper.
- `logic_id_schema.md` documenting the shared `pragma.logic_id` / `pragma.permutation` OTel attribute contract.

### Changed

- `pragma init --brownfield` appends `.pragma/spans/` and `.pragma/pytest-junit.xml` to `.gitignore`.
- GitHub Actions workflow split from single job into three.

## [0.3.0] — 2026-04-20

Adds Claude Code hook integration and the full safety battery. An AI
session can no longer edit `src/` while the gate is LOCKED (enforced
at the tool-use boundary, before permission mode), cannot land a
commit that fails any check in the battery, and cannot silently
disable a hook (`.claude/settings.json` has a committed integrity
hash).

### Added

- Four Claude Code hooks wired by `pragma init`: SessionStart,
  PreToolUse, PostToolUse, Stop. Dispatched via `pragma hook <event>`.
- `pragma verify discipline` — AST-based overengineering checks
  (complexity, LoC, depth, single-subclass, single-method util,
  empty __init__, TODO/FIXME sentinels). Shared logic with
  PostToolUse hook.
- `pragma verify commits` — WHY/Co-Authored-By/subject-length shape
  validation across `main..HEAD`.
- `pragma verify integrity` — `.claude/settings.json` hash check.
- `pragma verify all` — runs manifest + gate + integrity.
- `pragma hooks seal/verify/show` — manage the settings integrity hash.
- Full pre-commit battery in the `pragma init` template: gitleaks,
  ruff format + lint, mypy --strict, semgrep, pip-audit, deptry,
  check-added-large-files, pytest.
- `pre-push` stage runs `pragma verify all --ci` — closes the
  `git commit --no-verify` bypass.
- `--ci` flag on `pragma verify all` for strict mode.
- New `PragmaError` subtypes: discipline_violation, commit_shape_violation,
  integrity_mismatch, settings_not_found, hash_not_found,
  unknown_hook_event, hook_input_missing.

### Dogfood

REQ-004 declared in Pragma's own `pragma.yaml` under slice M01.S2;
eight convention tests pin the v0.3 contract.

### Known limitations (by design)

- `pragma-sdk` + OpenTelemetry spans — **v0.4**.
- Post-Implementation Log — **v0.4**.
- `narrative/` module for auto-commits/PRs/ADRs — **v0.4**.
- `pragma init --greenfield` — **v1.0**.

[0.3.0]: https://github.com/Joncik91/pragma/releases/tag/v0.3.0

## [0.2.0] — 2026-04-20

Adds the first real discipline layer: test-first gate. Slice
activation locks `src/`, `pragma unlock` demands failing tests for
every permutation in the active slice, `pragma slice complete`
demands the same tests green. State and audit land under `.pragma/`.

### Added

- Manifest schema v2: optional `milestones:` / `slices:` blocks;
  per-requirement `milestone` / `slice` fields. v1 manifests still
  load verbatim.
- `pragma migrate` — one-shot v1 → v2 upgrade. Idempotent; supports
  `--dry-run`.
- `pragma slice activate|complete|cancel|status` — slice lifecycle
  CLI.
- `pragma unlock` — TDD red-phase gate, driven by the naming
  convention `test_req_<req_id>_<permutation_id>`.
- `pragma verify gate` — state/manifest coherence + red-phase check.
- `pragma verify all` — runs manifest + gate in order; used by
  pre-commit.
- `.pragma/state.json` (gitignored, atomic, flock-guarded) +
  `.pragma/audit.jsonl` (committed, append-only, fsync'd).
- Typed errors for every new failure mode — `state_not_found`,
  `state_schema_error`, `state_locked`, `slice_not_found`,
  `slice_already_active`, `slice_not_active`, `gate_wrong_state`,
  `gate_hash_drift`, `milestone_dep_unshipped`,
  `unlock_missing_tests`, `unlock_test_passing`,
  `complete_tests_failing`.
- Template upgrade: `pragma init` now writes
  `.pre-commit-config.yaml` with `entry: python3 -m pragma verify all`.
- PRAGMA.md template documents the slice workflow + test-naming
  convention.

### Dogfood

Pragma's own repo ran `pragma migrate`, added REQ-003 declaring
v0.2's gate behaviour, and carved slice `M01.S1` for it (cancelled
rather than retro-fitted, since v0.2 code shipped before the
manifest entry).

### Known limitations (by design)

- Claude Code hook integration (SessionStart / PreToolUse /
  PostToolUse / Stop) is **v0.3**.
- `pragma-sdk` and OpenTelemetry spans are **v0.5**.
- No safety battery beyond manifest + gate — **v0.4**.
- `pragma doctor` is still a stub; `--emergency-unlock` lands in
  **v0.4**.

[0.2.0]: https://github.com/Joncik91/pragma/releases/tag/v0.2.0

## [0.1.0] — 2026-04-20

First public release. v0.1 is the Gall-compliant thin slice: a manifest
schema, a lockfile, and a pre-commit hook that refuses to commit when the
two disagree. No gate, no Claude Code hooks, no SDK, no PIL — those land
in v0.2 through v1.0 (see [`docs/roadmap.md`](docs/roadmap.md)).

### Added

- `pragma` CLI (Typer) installable via `pipx install pragma` — machine-
  parseable JSON output by default.
- `pragma init --brownfield` — scaffolds `pragma.yaml`, `PRAGMA.md`, and
  `.pre-commit-config.yaml` in an existing repo. Non-interactive;
  `--force` overwrites, `--name` overrides the project name.
- `pragma spec add-requirement` — appends a requirement with one or more
  permutations to `pragma.yaml`. Handles pipe-in-description safely.
- `pragma freeze` — writes `pragma.lock.json` with a SHA-256 hash over
  canonicalised manifest JSON (`sort_keys=True`, deterministic).
- `pragma verify manifest` — exits non-zero when `pragma.yaml` and
  `pragma.lock.json` disagree, or when the YAML is malformed against the
  schema.
- `pragma doctor` — stub self-check. Always exits 0 in v0.1; reports
  cwd, version, and presence of `pragma.yaml`, `pragma.lock.json`, and
  `.pre-commit-config.yaml`.
- Typed `PragmaError` hierarchy — every error exits with structured JSON
  `{error, message, remediation, context}`.
- Pydantic v2 manifest schema — `extra="forbid"`, frozen models, tuple-
  backed collections for immutability.
- Atomic lockfile writes (`mkstemp` → `fsync` → `os.replace`).
- Jinja2 templates for init scaffolding, shipped inside the wheel via
  `hatchling` `force-include`.
- Pre-commit hook template using `python3 -m pragma verify manifest`
  (portable across Debian / Ubuntu without assuming `pipx` is on
  `PATH`).
- GitHub Actions CI — runs `pragma verify manifest`, `ruff check`,
  `ruff format --check`, `mypy --strict`, and `pytest` on every push and
  PR.
- End-to-end test proving the pre-commit hook blocks a drifted commit.

### Dogfood

Pragma uses its own v0.1 on its own repo: `pragma.yaml` declares
`REQ-001` (CLI JSON contract) and `REQ-002` (manifest / lockfile
roundtrip) with 11 permutations; `.pre-commit-config.yaml` runs
`pragma verify manifest` on every commit.

### Known limitations (by design — shipping in later versions)

- No gate, slice state machine, or `pragma unlock` — **v0.2**.
- No Claude Code hook integration — **v0.3**.
- No full safety battery (gitleaks, semgrep, pip-audit, deptry) — **v0.4**.
- No `pragma-sdk`, `@pragma.trace`, or OpenTelemetry spans — **v0.5**.
- No Post-Implementation Log (PIL) — **v0.6**.
- No `pragma init --greenfield` or milestones / slices hierarchy —
  **v1.0**.

See [`docs/roadmap.md`](docs/roadmap.md) for the full evolutionary path.

[0.1.0]: https://github.com/Joncik91/pragma/releases/tag/v0.1.0
