# Changelog

All notable changes to Pragma are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
