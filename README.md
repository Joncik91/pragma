# Pragma

Senior engineer on rails for AI-driven development.

**Status:** v0.4 — SDK + Post-Implementation Log + narrative module. Greenfield bootstrap comes in v1.0.

## Install

    pipx install pragma

## Quick start (brownfield Python project)

    cd your-project/
    pragma init --brownfield
    pragma spec add-requirement --id REQ-001 \
        --title "User can log in" \
        --description "Operator signs in with email + password" \
        --permutation 'valid_credentials|Valid email and strong password returns JWT|success'
    pragma freeze
    git add pragma.yaml pragma.lock.json .pre-commit-config.yaml
    git commit -m "chore: adopt pragma"

## Ship your first slice (v0.2 workflow)

    # 1. Activate a slice — gate is now LOCKED, src/ edits are watched.
    pragma slice activate M00.S0

    # 2. Write failing tests per convention:
    #    test_req_<req_id>_<permutation_id>  e.g. test_req_001_valid_credentials

    # 3. Unlock — refuses unless every declared permutation has a RED test.
    pragma unlock

    # 4. Implement the code, make the tests green.

    # 5. Complete — refuses unless every slice test is GREEN.
    pragma slice complete

`pragma slice status` at any time; `pragma slice cancel` to abandon.

## Upgrading from v0.1

    pragma migrate                     # wraps flat requirements in implicit M00/M00.S0
    pragma init --brownfield --force   # refresh .pre-commit-config.yaml (verify manifest → verify all)

## What v0.2 does

- **Manifest** — `pragma init --brownfield`, `pragma spec add-requirement`,
  `pragma freeze`, `pragma verify manifest`; dual-file integrity via
  SHA-256 over canonical JSON.
- **Schema v2** — `pragma.yaml` optionally declares `milestones:` and
  `slices:`; `pragma migrate` upgrades v0.1 manifests in one idempotent
  shot.
- **Gate** — `pragma slice activate|complete|cancel|status`,
  `pragma unlock`. `.pragma/state.json` holds the active slice and gate
  (gitignored, atomic, flock-guarded); `.pragma/audit.jsonl` records
  every transition (committed, append-only, fsync'd).
- **Verify** — `pragma verify gate` and `pragma verify all` (runs
  manifest + gate). The pre-commit hook refuses commits when the
  manifest drifts OR when the gate state is incoherent with the current
  red-phase tests.
- **Convention over config** — no pytest plugin or SDK in v0.2; the
  gate inspects test names (`test_req_<req>_<permutation>`) against the
  declared permutations and the tests' pass/fail state.

## Docs

- [`docs/design.md`](docs/design.md) — full v1 design. What Pragma looks
  like when the complete vision lands.
- [`docs/roadmap.md`](docs/roadmap.md) — evolutionary rollout v0.1 → v1.0.
  Each increment is useful on its own and dogfooded before the next.
- [`CHANGELOG.md`](CHANGELOG.md) — release history.
