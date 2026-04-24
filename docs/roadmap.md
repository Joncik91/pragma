# Pragma — Roadmap

Alpha product. Ships when the dogfood is honest, not when the calendar
turns.

## Principle

> *A complex system that works is invariably found to have evolved from a
> simple system that worked.* — John Gall

## Status

**v0.1.0 — 2026-04-24, current.** First alpha. The full thesis works
end-to-end on a fresh greenfield Python project: manifest → slice →
red tests → unlock → code → complete → populated PIL. No manual
`pytest` step. On Pragma's own repo the whole gate + battery + PIL +
Claude Code hooks are self-enforcing.

But: every dogfood pass still surfaces bugs. v0.1.0 is the starting
line for serious hardening, not the finish.

## Cadence

v0.1.x patches continue until **three consecutive clean dogfood
passes** — a full two-slice greenfield project shipped end-to-end
with zero findings, three times in a row. That's when v0.2 starts
planning. No more "one bug per release" cadence. Fix on main, dogfood,
fix the next one on main, no tag storm.

When v0.2 starts it gets one honest scope: something measurable the
product doesn't do today. Same rule at the end — three clean dogfoods
or it doesn't tag.

## Beyond v0.1

Parked for when the alpha hardens:

- **Human-subjects PIL legibility** — three non-coders read a PIL
  without coaching. This is the v0.1 done-criterion that was
  deferred; becomes the v0.2 headline once dogfood is stable.
- **TypeScript target** — `pragma-sdk-ts` + TS pre-commit battery +
  TS discipline checker. Significant new scope; blocked on v0.1
  being actually stable.
- **`pragma context <slice>`** — manifest-as-context-selector: emit
  the minimal file set an LLM needs for a given slice. Turns the
  manifest from a gate into a context-selection tool. Largest lever
  on large-codebase token cost.
- **PyPI publish** — currently the gate on v0.1 done-criterion
  "deployed artifact." Depends on a packaging-and-release discipline
  that doesn't exist yet (see the pre-collapse CHANGELOG for why
  release cadence was the problem).

## Out of scope (indefinite)

- Multi-user gate coordination.
- Non-GitHub CI (GitLab / Bitbucket) — contribute if you need it.
- Plugin architecture for custom gates / reporters.
- Signed commits / SLSA provenance.
- Configurable discipline budgets (alpha defaults are hard-coded).
- In-IDE refactoring suggestions.
- Symbolic execution / formal verification.

## History note

Between 2026-04-20 and 2026-04-24, Pragma iterated rapidly through
tags `v0.1.0` → `v1.1.2` (17 releases across 3 days). That cadence
represented alpha iteration misrepresented as stable releases. On
2026-04-24 the public tag history was collapsed to a single
`v0.1.0`; the detailed per-version notes live in
`CHANGELOG-archive.md` and the git log is intact. The product
capability set in v0.1.0 is the sum of every tagged commit on that
3-day arc — nothing was removed, only the version labels.
