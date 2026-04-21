# Pragma

Senior engineer on rails for AI-driven development.

> v1.0 shipped 2026-04-21. Greenfield bootstrap ships.

See [`docs/usage.md`](docs/usage.md) for the full walkthrough of both
flows. What's below is the 30-second version.

## Install

    pipx install pragma

## Quick start (greenfield Python project)

    mkdir demo && cd demo
    pragma init --greenfield --name demo --language python
    # write docs/problem.md with one "# Heading" per capability
    pragma spec plan-greenfield --from docs/problem.md
    pragma freeze

From there: `pragma slice activate M01.S1` → red tests → `pragma unlock`
→ green → `pragma slice complete` → commit.

## Quick start (brownfield Python project)

    cd your-project/
    pragma init --brownfield
    pragma spec add-requirement --id REQ-001 \
        --title "User can log in" \
        --description "Operator signs in with email + password" \
        --touches src/auth/login.py \
        --permutation 'valid_credentials|Valid email and strong password returns JWT|success'
    pragma freeze
    git add pragma.yaml pragma.lock.json .pre-commit-config.yaml
    git commit -m "chore: adopt pragma"

## Ship your first slice

    # 1. Activate a slice — gate is now LOCKED, src/ edits are watched.
    pragma slice activate M01.S1

    # 2. Write failing tests per convention:
    #    test_req_<req_id>_<permutation_id>  e.g. test_req_001_valid_credentials

    # 3. Unlock — refuses unless every declared permutation has a RED test.
    pragma unlock

    # 4. Implement the code, make the tests green.

    # 5. Complete — refuses unless every slice test is GREEN.
    pragma slice complete

`pragma slice status` at any time; `pragma slice cancel` to abandon.

## Upgrading an older manifest

    pragma migrate                     # v1 → v2; wraps flat requirements in implicit M00/M00.S0
    pragma init --brownfield --force   # refresh .pre-commit-config.yaml

See [`docs/migrate.md`](docs/migrate.md) for failure modes.

## What v1.0 ships

- **Greenfield bootstrap** — `pragma init --greenfield --name <name>
  --language python` scaffolds a seed manifest + `claude.md` primer.
  `pragma spec plan-greenfield --from problem.md` turns headings into
  REQ placeholders (deterministic, no LLM).
- **Manifest** — `pragma init --brownfield`, `pragma spec
  add-requirement`, `pragma freeze`, `pragma verify manifest`;
  dual-file integrity via SHA-256 over canonical JSON.
- **Schema v2** — `pragma.yaml` declares `milestones:` and `slices:`;
  `pragma migrate` upgrades v1 manifests in one idempotent shot.
- **Gate** — `pragma slice activate|complete|cancel|status`,
  `pragma unlock`. `.pragma/state.json` holds the active slice and
  gate (gitignored, atomic, flock-guarded); `.pragma/audit.jsonl`
  records every transition (committed, append-only, fsync'd).
- **Verify** — `pragma verify all` runs manifest + gate + discipline +
  integrity. The pre-commit hook refuses commits when the manifest
  drifts OR when the gate state is incoherent with the current
  red-phase tests. `pragma verify message` enforces commit shape at
  `commit-msg`; `pragma verify commits` runs at `pre-push`.
- **Recovery** — `pragma doctor` is a real diagnostic tool: eight
  classifier codes with exact remediation commands. `pragma doctor
  --emergency-unlock --reason "..."` is the escape hatch for a
  wedged gate.
- **Reports** — `pragma report` produces byte-identical JSON from the
  same inputs. `pragma narrative commit` / `pragma narrative pr`
  compose senior-engineer-grade commit and PR copy from the active
  slice.

## Docs

- [`docs/usage.md`](docs/usage.md) — first-time-user walkthrough for
  brownfield and greenfield.
- [`docs/doctor.md`](docs/doctor.md) — every diagnostic code, what it
  means, how to fix it.
- [`docs/migrate.md`](docs/migrate.md) — schema versions and
  `pragma migrate`.
- [`docs/design.md`](docs/design.md) — full v1 design. Reference, not
  tutorial.
- [`docs/roadmap.md`](docs/roadmap.md) — evolutionary rollout v0.1 →
  v1.0. Each increment was dogfooded before the next shipped.
- [`CHANGELOG.md`](CHANGELOG.md) — release history.
