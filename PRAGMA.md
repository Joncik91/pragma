# Pragma in this project

This project uses [Pragma](https://github.com/joncik/pragma) v0.1 to enforce
manifest-driven discipline on AI-generated code.

## Files

- `pragma.yaml` — the Logic Manifest. Human-edited (by you or by an AI
  assistant). Lists every requirement and its expected permutations.
- `pragma.lock.json` — machine-generated. Contains a SHA-256 hash over the
  canonical form of `pragma.yaml`. Regenerate with `pragma freeze` after
  any edit.
- `.pre-commit-config.yaml` — pre-commit wiring. `pragma verify manifest`
  runs before every commit and blocks if YAML/lock diverge.

## Daily flow

    # Edit pragma.yaml (or have Claude Code run `pragma spec add-requirement`)
    pragma freeze                # regenerate pragma.lock.json
    git add pragma.yaml pragma.lock.json
    git commit -m "..."          # pre-commit blocks if verify fails

See the Pragma v1 design spec for what's coming in v0.2+ (gate, hooks, SDK, PIL).
