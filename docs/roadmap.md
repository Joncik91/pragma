# Pragma — Roadmap

Pragma ships evolutionarily, but not dogmatically. v0.1 and v0.2 were
separated on purpose — each answered a real uncertainty (manifest as
source of truth, test-first gate, flock pattern, convention over SDK)
that could only be learned by dogfooding. The remaining increments
have less uncertainty and no dependency gaps between them; collapsing
them reduces release overhead without losing any checkpoint we
actually need.

## Principle

> *A complex system that works is invariably found to have evolved from a
> simple system that worked.* — John Gall

v1.0 is still the complex system. We still don't ship it in one go.
But "evolved from a simple system" doesn't mean seven sub-releases —
it means each step is a working whole, previous ones inform the next,
and no step is so large it can't be dogfooded honestly.

## Releases

| Ver | Status | Ships | Useful standalone because… | Exit criteria |
|---|---|---|---|---|
| **v0.1** | **Released 2026-04-20** | `pragma` CLI (Typer), `pragma.yaml` schema, `pragma init --brownfield`, `pragma spec add-requirement`, `pragma freeze`, `pragma verify manifest`, `pragma doctor` stub, pre-commit hook that runs `pragma verify manifest` | A user can write a manifest, have it schema-validated, and be blocked from committing when the manifest is broken. No gate, no AI coupling, no SDK. Pragma's own repo dogfoods on itself at this stage. | `pragma init` produces a valid manifest scaffold; malformed YAML blocks pre-commit; Pragma's repo uses its own v0.1 |
| **v0.2** | **Released 2026-04-20** | Gate state machine (slice-scoped), `pragma slice activate\|complete\|cancel`, `pragma unlock`, `pragma verify gate`, `.pragma/state.json` atomic writes + append-only `audit.jsonl` | Adds the test-first discipline: can't commit `src/` without failing tests per permutation. Still no AI coupling; works for any dev. | Gate transitions LOCKED↔UNLOCKED end-to-end with pre-commit enforcement; `slice cancel` resets cleanly |
| **v0.3** | **Released 2026-04-20** | Claude Code hooks (session-start / pre-tool-use / post-tool-use / stop) AND safety battery (gitleaks, ruff, mypy, semgrep, pip-audit, deptry) via `pragma init` writing `.pre-commit-config.yaml`; `pragma verify discipline` (AST overengineering); `pragma verify commits` (message shape); `pragma hook <event>` dispatcher; `.claude/settings.json` integrity-hash verification; GitHub Actions workflow with `pragma verify all --ci`; branch protection via `gh api` | The "non-coder trusts the commit and the AI can't bypass the gate" leg ships together. Hooks and battery are independent but both attach at the same commit-time seam, share the same remediation contract, and are more valuable paired than separated. | AI session blocked from editing `src/` while LOCKED; `--no-verify` blocked by pre-push + CI; hash-verified hooks detect tampering; full battery auto-fixes what it can |
| **v0.4** | **Released 2026-04-21 (0.4.2)** | `pragma-sdk` (separate pip package): `@pragma.trace`, `set_permutation`, pytest plugin auto-registered via `pytest11` entry point; `pragma report --json` and `pragma report --human` (Markdown PIL with mock-flag detection); `narrative/` module (commits / PRs / ADRs / remediation); `pragma verify message` + commit-msg hook enforcing canonical commit shape. v0.4.0 was cut and yanked; 0.4.1 closed the install-broken gap; 0.4.2 closed the dogfood + enforcement gap — PIL now 32/32 ok on Pragma's own repo. | Post-Implementation Log + runtime tracing ship as one unit. PIL without the SDK is useless (no spans to aggregate); SDK without the PIL is a half-told story. Merging them avoids a raw-JSON interim release. | Tests emit spans; Markdown PIL intelligible to a non-coder without coaching; mock-only permutations flagged |
| **v1.0** | **Released 2026-04-21** | `pragma init --greenfield` + milestones / slices hierarchy; `pragma spec plan-greenfield` interactive bootstrap; `pragma doctor` real recovery + `--emergency-unlock`; REQ-006 determinism acceptance; `docs/usage.md` + `docs/doctor.md` + `docs/migrate.md`; CI greenfield-smoke job; `migrate_to_current` dispatcher; version sync (pragma + sdk + `__version__`). PIL 34/34 ok. | Greenfield bootstrap flow ships. v1 is feature-complete for the "non-coder ships new project from scratch" story. Four of six §7.8 done criteria pass concretely; two (human-subjects validation, deployed-artifact half of greenfield CI) deferred to v1.1 with reasoning recorded in `docs/v10-rc-evidence.md`. | v1.0 done criteria (see [`design.md` §7.5](design.md#75-v10-done-criteria)) pass or deferred-with-reasoning |
| **v1.1** | Planned | (1) `pragma doctor --clean-spans` with configurable retention (keep last N runs / N days) — closes the parked v1.0.4 paper cut; (2) `pragma-sdk-ts` + TS pre-commit battery template (biome + tsc-strict + npm-audit) + TS discipline-checker; (3) human-subjects PIL legibility validation on 3 non-coders (closes v1.0 criterion 3). PyPI publish deferred. | First non-Python target ships. Span accumulation stops being a usage-over-time cliff. One of v1.0's two deferred criteria closes (criterion 4 "deployed artifact" stays deferred until PyPI lands). | TS project can `pragma init` and run the full gate + battery + PIL; `.pragma/spans/` bounded under retention; 3 non-coders read a PIL without coaching |
| **v1.2** | Candidate | `pragma context <slice>` — manifest-as-context-selector. Given a slice id, emit the minimal file set (sources covered by the slice's permutations + their tests + the manifest entries) needed to work on it. Consumed by Claude Code / other LLM harnesses to bound session context on large codebases. Also shrinks the surface `verify discipline` and `pytest` scan per commit. | Turns the manifest from a gate into a context-selection tool. Uniquely Pragma's — only works because the manifest already maps requirements → source → tests. Biggest lever on large-codebase token cost. | `pragma context <slice>` output is stable, covers every file the slice's tests touch at runtime, and missing coverage triggers a doctor-reported diagnostic |

**Total plan: ~4 weeks** across three remaining releases. v0.3 ~1.5w,
v0.4 ~1.5w, v1.0 ~1w.

**Beyond v1.0:** v1.1 adds TypeScript + closes v1.0's two deferred
criteria + lands span pruning. v1.2 introduces manifest-as-context-
selector (`pragma context`), the largest lever on token cost for
large codebases. Order is deliberate: TS ships first because it's
already promised and has demand; context-selector follows because
it's a new feature category that benefits from TS already being in
the product.

### Why collapsed from seven

The earlier plan split hooks from battery (v0.3 vs v0.4) and SDK from
PIL (v0.5 vs v0.6). Both splits were Gall-for-Gall's-sake: each pair
is well-understood, shares a seam, and is more valuable together than
apart. Merging them saves two release-overhead cycles (tag + changelog
+ roadmap bump + dogfood checkpoint) without losing a checkpoint we
actually needed — v0.1 and v0.2 taught us enough about the manifest
and gate to move faster on the layers above.

## Dogfooding cadence

Pragma is a Python project. Each increment activates on Pragma's own repo
as soon as it lands:

- **v0.1:** Pragma gets a `pragma.yaml` for its own modules. **Done.**
- **v0.2:** Pragma's repo uses the gate; slice `M01.S1` declared
  REQ-003. **Done.**
- **v0.3:** Pragma's own Claude Code sessions run with the hooks
  installed; Pragma's own pre-commit and CI run the full battery.
- **v0.4:** Pragma's tests emit spans; Pragma's PRs include PIL
  reports written by its own `narrative/` module.
- **v1.0:** a fresh `pragma init --greenfield` is used to start one
  throwaway sibling project from zero as the acceptance test.
- **v1.1:** a throwaway TypeScript project is scaffolded with
  `pragma init --greenfield --target=typescript` and runs the full
  gate + battery + PIL; Pragma's own `.pragma/spans/` stays bounded
  under retention; `pip install pragma` from PyPI works on a clean
  machine.
- **v1.2:** `pragma context <slice>` is used on Pragma's own repo
  to drive Claude Code sessions — measured reduction in session
  context size vs. whole-repo scan is the acceptance signal.

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
