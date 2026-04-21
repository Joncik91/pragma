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

## Adjusting the pre-commit entry

`.pre-commit-config.yaml` uses `python3 -m pragma verify manifest` by default,
which works on Debian/Ubuntu/Alpine/macOS/GitHub Actions (where `python3`
always exists). If your environment is different:

- **pipx install pragma** — change the `entry:` to `pragma verify manifest`.
- **Windows (no python3 alias)** — change the `entry:` to `python -m pragma verify manifest`.
- **Specific venv you want to pin** — change the `entry:` to
  `path/to/venv/bin/python -m pragma verify manifest`.

## Slice workflow (v0.2+)

Each deliverable is a **slice** (e.g. `M01.S1`) that moves through
a strict state machine:

1. **`pragma slice activate M01.S1`** — claims the slice, gate set
   to `LOCKED`. You must write failing tests before you can unlock.
2. **Write failing tests** — one test function per permutation,
   named `test_req_<req_id>_<perm_id>()` (e.g. `test_req_001_happy`).
   `pragma verify all` will pass once every expected test exists and
   is red.
3. **`pragma unlock`** — flips the gate to `UNLOCKED`. This is the
   signal that the TDD red phase is done and implementation may begin.
4. **Implement** — write production code until every test passes.
5. **`pragma slice complete`** — verifies all tests are green, then
   marks the slice as `shipped`. The gate is cleared and no slice is
   active.

At any point, `pragma slice status` shows the current slice and gate
state. `pragma slice cancel` aborts the active slice.
