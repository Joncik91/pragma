# Pragma — Roadmap

Pragma ships evolutionarily per Gall's Law: each release is useful on its
own, dogfooded on Pragma's own repo before the next begins, and never
larger than ~1 week of work.

## Principle

> *A complex system that works is invariably found to have evolved from a
> simple system that worked. A complex system designed from scratch never
> works and cannot be patched up to make it work. You have to start over
> with a working simple system.* — John Gall

v1.0 is the complex system. We do not ship it in one go.

## Releases

| Ver | Status | Ships | Useful standalone because… | Exit criteria |
|---|---|---|---|---|
| **v0.1** | **Released 2026-04-20** | `pragma` CLI (Typer), `pragma.yaml` schema, `pragma init --brownfield`, `pragma spec add-requirement`, `pragma freeze`, `pragma verify manifest`, `pragma doctor` stub, pre-commit hook that runs `pragma verify manifest` | A user can write a manifest, have it schema-validated, and be blocked from committing when the manifest is broken. No gate, no AI coupling, no SDK. Pragma's own repo dogfoods on itself at this stage. | `pragma init` produces a valid manifest scaffold; malformed YAML blocks pre-commit; Pragma's repo uses its own v0.1 |
| **v0.2** | Planned | Gate state machine (slice-scoped), `pragma slice activate\|complete\|cancel`, `pragma unlock`, `pragma verify gate`, `.pragma/state.json` atomic writes + append-only `audit.jsonl` | Adds the test-first discipline: can't commit `src/` without failing tests per permutation. Still no AI coupling; works for any dev. | Gate transitions LOCKED↔UNLOCKED end-to-end with pre-commit enforcement; `slice cancel` resets cleanly |
| **v0.3** | Planned | Claude Code hooks (session-start / pre-tool-use / post-tool-use / stop), `pragma hook <event>` dispatcher, `.claude/settings.json` integrity-hash verification, `additionalContext` injection of gate state | The AI-governor value prop lands: Claude Code is blocked from editing `src/` while LOCKED, sees structured remediation strings. | AI session can't bypass the gate without disabling the hash-verified hooks; bypass attempts logged to `audit.jsonl` |
| **v0.4** | Planned | Safety battery (gitleaks, ruff, mypy, semgrep, pip-audit, deptry) via `pragma init` writing `.pre-commit-config.yaml`; `pragma verify discipline` (AST-based overengineering checks); `pragma verify commits` (commit-message shape); GitHub Actions workflow with `pragma verify all` server-side; branch protection via `gh api` | The "non-coder can trust the commit" leg ships. No SDK / PIL yet — tests pass/fail is the quality signal. | Full battery runs auto on `git commit`; CI re-runs on PR; branch protection installed |
| **v0.5** | Planned | `pragma-sdk` (separate pip package): `@pragma.trace`, `set_permutation`, pytest autouse fixture via `conftest.py.tpl`; `pragma report` (JSON only, no Markdown yet) | PIL raw data available; lets us validate the span aggregation logic before spending time on prose formatting. | Tests emit spans; `pragma report --format json` produces a coverage matrix |
| **v0.6** | Planned | `pragma report --human` (Markdown PIL with plain-English prose, mock-flag detection via span-absence heuristic, discipline rollup); `narrative/` module (commits / PRs / ADRs / remediation) integrated across all surfaces | The full senior-engineer-frame user experience lands. | Non-coder readers rate PIL intelligible without coaching |
| **v1.0** | Planned | `pragma init --greenfield` + milestones / slices hierarchy; `pragma spec plan-greenfield` interactive bootstrap; docs; determinism statement + test; version migration stub | Greenfield bootstrap flow ships. v1 is feature-complete for the "non-coder ships new project from scratch" story. | v1.0 done criteria (see [`design.md` §7.5](design.md#75-v10-done-criteria)) all pass |

**Total plan: ~6.5 weeks.** No single increment takes more than a week.
Every increment is usable by Pragma's own team on Pragma's own repo.

## Dogfooding cadence

Pragma is a Python project. Each increment activates on Pragma's own repo
as soon as it lands:

- **v0.1:** Pragma gets a `pragma.yaml` for its own modules. **Done.**
- **v0.2:** Pragma's next slice goes through the gate.
- **v0.3:** Pragma's own Claude Code sessions run with the hooks
  installed.
- **v0.4:** Pragma's own pre-commit and CI run the battery.
- **v0.5-0.6:** Pragma's tests emit spans; Pragma's PRs include PIL
  reports.
- **v1.0:** a fresh `pragma init --greenfield` is used to start one
  throwaway sibling project from zero as the acceptance test.

If any increment feels heavy on Pragma itself, fix it before the next
lands.

## Out of scope (deferred beyond v1.0)

- Non-Python target apps — ~70% of Pragma is already language-agnostic
  (manifest, gate, hooks, narrative, PIL aggregation); adding a language
  means a new SDK package + a new pre-commit battery template + a new
  discipline-checker, not a core rewrite. TypeScript is the v1.1 target;
  Go / Rust follow on demand. See
  [`design.md` §2.2.1](design.md#221-whats-language-agnostic-vs-python-specific).
- Multi-user gate coordination (v1.1).
- Non-GitHub CI (GitLab / Bitbucket; v1.x on demand).
- Plugin architecture for custom gates / reporters.
- Signed commits / SLSA provenance.
- Configurable discipline budgets (v1 defaults are hard-coded until
  evidence warrants).
- In-IDE refactoring suggestions.
- Symbolic execution / formal verification.
