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

## Commit message shape (v0.3+)

Every commit's message must carry:

- **Subject line ≤ 72 characters.** Anything longer is truncated in
  `git log --oneline` and on GitHub's PR list.
- **Body** separated by a blank line, with at least a `WHY:` paragraph
  and a `Co-Authored-By:` trailer (for AI-assisted commits).

`pragma verify message` runs automatically at the `commit-msg` stage
via pre-commit — if the draft fails shape, the commit is rejected
before it lands. `pragma verify commits` runs at `pre-push` against
`origin/main` to block pushing a broken range.

**Planning note.** When writing an implementation plan, keep each
task's subject short enough that it can be copied verbatim into a
commit subject. If your task heading is 84 characters, the commit
for that task will fail the hook. Budget the title to ≤72 chars
(conventional-commits prefix included) and put the longer rationale
in the task body.

## Post-Implementation Log (v0.4+)

After a slice ships, `pragma report --human` produces a plain-English
summary of which declared permutations were genuinely exercised
(spans observed), which passed but might be mocked, and which were
never run. `pragma report --json` is the deterministic machine form.
