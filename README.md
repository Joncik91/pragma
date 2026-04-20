# Pragma

Senior engineer on rails for AI-driven development.

**Status:** v0.1 — manifest validation only. Gate, hooks, SDK, and PIL come in v0.2-v1.0.

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

## What v0.1 does

- `pragma init --brownfield` scaffolds a `pragma.yaml` and `.pre-commit-config.yaml`.
- `pragma spec add-requirement` appends a new requirement with permutations to the manifest.
- `pragma freeze` writes a `pragma.lock.json` with a SHA-256 hash over the YAML.
- `pragma verify manifest` exits non-zero when the YAML and lock disagree or the YAML is malformed.
- A pre-commit hook runs `pragma verify manifest` automatically.

## Docs

- [`docs/design.md`](docs/design.md) — full v1 design. What Pragma looks
  like when the complete vision lands.
- [`docs/roadmap.md`](docs/roadmap.md) — evolutionary rollout v0.1 → v1.0.
  Each increment is useful on its own and dogfooded before the next.
- [`CHANGELOG.md`](CHANGELOG.md) — release history.
