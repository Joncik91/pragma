# Changelog

All notable changes to Pragma are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6] — 2026-04-25

**Last open known-issue closed.** BUG-046 was logged at v0.1.3 as a
real friction point (brownfield retroactive REQ flow had no clean
gate path). Fixed.

### Fixed

- **BUG-046 / REQ-042** — `pragma unlock --skip-tests --reason "..."` is the brownfield-import escape hatch. The TDD red-first rule still applies by default; `--skip-tests` requires a non-empty `--reason` and audit-logs the bypass to `.pragma/audit.jsonl` so the trail is honest. Use case: existing code that you're retroactively wrapping in a manifest REQ — tests already pass, hand-editing `.pragma/state.json` is no longer necessary. Documented in `docs/reference.md`.

### Open known-issues at v0.1.6

None.

### Dogfood

Three post-fix clean walkthroughs on fresh sandboxes:

- **R22** — greenfield single-REQ literal README quick-start. `1 verified, 0 flagged`. Two-attempt commit (documented BUG-043 ruff speedbump on first).
- **R23** — brownfield literal README quick-start + new `unlock --skip-tests --reason` exercised end-to-end. Single-attempt adopt-pragma commit; `2 verified` after adding `@trace("REQ-001")` to existing code (the documented brownfield retroactive path).
- **R24** — greenfield multi-REQ slice (REQ-001 + REQ-002, 2 perms). `2 verified, 0 flagged`. Two-attempt commit (BUG-043 documented).

Zero new findings across the three rounds. Cadence rule cleared.

## [0.1.5] — 2026-04-25

**Edge-case dogfood pass.** Probed 15 first-run-user error scenarios.
12 surfaced clean errors; 3 had remediation-string defects (commands
that don't exist, missing context, dishonest about flag scope). All
fixed under one REQ.

### Fixed

- **BUG-049 / REQ-041** — PIL `mocked` remediation no longer points users at the nonexistent `pragma spec mark-mocked` subcommand. New text says: wrap the test body in `with set_permutation('<id>'):` so the SDK labels the trace correctly. That's the actual fix.
- **BUG-050 / REQ-041** — `pragma init --greenfield` on an already-initialised dir now explains that greenfield does not support `--force` (would erase the manifest), and points at `pragma init --brownfield --force` as the escape hatch for refreshing hooks/templates while keeping the manifest.
- **BUG-051 / REQ-041** — `pragma slice activate <unknown>` now lists the declared slice ids in the remediation. Mirrors what `add-requirement --slice` already does.

## [0.1.4] — 2026-04-25

**Brownfield adopt-pragma commit lands cleanly.** Round-18 strict
brownfield walkthrough surfaced two more dead-ends after BUG-045:
the commit-shape check rejected pre-Pragma history (BUG-047) and
the scaffolded pytest hook treated "no tests yet" as a hook failure
(BUG-048). Both fixed.

### Fixed

- **BUG-047 / REQ-039** — `pragma verify commits` skips pre-Pragma history. When `--base` (default `main`) does not exist, the range scopes to commits that touched `pragma.yaml` instead of walking full HEAD. When `pragma.yaml` is staged but uncommitted (the first adopt commit), the range yields zero commits so the check trivially passes. Pre-Pragma commits are exempt by definition.
- **BUG-048 / REQ-040** — scaffolded pre-commit pytest hook traps pytest exit code 5 ("no tests collected") to 0. A freshly-adopted brownfield repo with no `tests/` dir can now land its first commit. Other exit codes still propagate.
- **README** — brownfield "chore: adopt pragma" example now uses the multi-line WHY/Co-Authored-By shape that the gate actually enforces.

## [0.1.3] — 2026-04-25

**Brownfield quick-start reaches LOCKED gate.** Round-16 strict
brownfield walkthrough surfaced BUG-045 — the README's brownfield
quick-start landed users in a dead end at `pragma slice activate
M01.S1` because the brownfield manifest had no slices declared.

### Fixed

- **BUG-045 / REQ-038** — `pragma init --brownfield` now writes v2 schema with an implicit `M00.S0` slice (matching the `pragma migrate` precedent). `pragma spec add-requirement` defaults to the only-declared slice when the caller omits `--milestone`/`--slice`, so the literal README walkthrough lands the new REQ in `M00.S0` automatically. README's "Ship a slice" block notes brownfield uses `M00.S0` (greenfield still uses `M01.S1`).

### Known issues at v0.1.3

- **BUG-046** — Brownfield retroactive-REQ flow has no clean path through the gate. `pragma unlock` refuses when tests already pass (TDD red-first rule); `pragma doctor --emergency-unlock` clears the active slice, leaving `slice complete` unreachable. Workaround: edit `.pragma/state.json` manually to flip the gate to `UNLOCKED`, then `slice complete --skip-tests`. This is a real friction point, not a doc fix — likely needs a `pragma slice unlock --skip-tests` or a brownfield-import flag in a future patch.

## [0.1.2] — 2026-04-25

**Closes the v0.1.0 known-issues backlog.** The BUG-023..026 entries
that the v0.1.0 CHANGELOG flagged as open were re-checked. Three of
the four were already fixed in earlier patches and the CHANGELOG was
stale; the fourth (BUG-026, narrative prose) is now fixed.

### Fixed

- **BUG-026 / REQ-037** — `pragma narrative commit` now produces senior-engineer prose. WHY names the REQ titles in the active slice instead of "<slice>: N permutations declared." WHAT lists each REQ with id, title, and per-permutation verdicts (e.g. `valid=success, weak_pw=reject`) inline, so a reader sees the behaviour that landed without opening the manifest.

### Documented (already fixed, CHANGELOG was stale)

- **BUG-023** — single-permutation REQ courtesy was implemented in 2116db3 (`fix: BUG-023 — single-permutation courtesy in PIL`). PIL now reports `ok` when a one-perm REQ test omits `set_permutation`. Verified by sandbox repro.
- **BUG-024** — `pragma slice activate` on a shipped slice was made refusable in 87273b7 (`fix: BUG-024 — slice activate refuses to un-ship a shipped slice`). `--force` is the explicit opt-in to re-open. Verified by sandbox repro.
- **BUG-025** — `span_count` multiplier was already accurate. Sandbox showed `span_count` matches the count of non-empty span files on disk. CHANGELOG entry was speculative.

## [0.1.1] — 2026-04-25

**First post-v0.1.0 patch.** Three consecutive clean strict-README
walkthroughs (rounds 12, 13, 14) cleared the cadence rule for an
alpha bump.

### Fixed

- **BUG-036 / REQ-032** — `pragma init` now runs `pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push`. Previously the hooks were never wired so the gate enforcement the README advertises was structurally bypassable on a fresh project.
- **BUG-037 / REQ-033** — scaffolded pre-commit `pragma verify all` hook resolves the pragma binary via the same `{{ pragma_python_bin }} → .venv/bin/python3 → python3` chain init was launched with, instead of bare `python -m pragma`. First-run users without a project venv no longer hit "No module named pragma.__main__".
- **BUG-038 / BUG-039 / REQ-034** — scaffolded pytest hook uses the same PY resolution chain; scaffolded pip-audit ignores GHSA-58qw-9mgm-455v by default. Brought the scaffolded battery template back in sync with Pragma's own `.pre-commit-config.yaml`.
- **BUG-040** — README's slice-activate example used a stale test-name placeholder; now points at `pragma slice status` / `pragma.yaml` to discover the right ids.
- **BUG-042 / REQ-035** — scaffolded `.gitignore` covers `.pragma/state.json`, `.pragma/state.json.lock`, `__pycache__/`, and `*.pyc`. First `git add -A` no longer accidentally stages bytecode + flock files; ruff-format and pytest no longer "modify" cache files on every commit.
- **BUG-043** — README warns about the ruff-format first-commit speedbump (re-stage with `git add -A` and re-run; second attempt lands).
- **BUG-044 / REQ-036** — `pragma init --greenfield` runs `git init -q` when the cwd has no repo, so the README quick-start (`mkdir demo && cd demo && pragma init --greenfield`) actually wires the pre-commit / commit-msg / pre-push hooks. Previously `hooks_installed: false` shipped silently. Brownfield is unaffected.

### Cadence

The strict-README dogfood passed three rounds in a row with zero
findings under varied project shapes (1-REQ/1-perm, 2-REQ/2-perm,
multiple project names). v0.1.x patch cycle continues until the
known issues below either ship a fix or the workarounds remain
stable through three more rounds.

## [0.1.0] — 2026-04-24

**First alpha.** Pragma is a senior-engineer-on-rails framework for
AI-driven Python development: manifest-declared permutations, a
test-first gate, a Claude Code hook integration, a pre-commit safety
battery, and a Post-Implementation Log that shows which declared
behaviours were actually exercised at runtime.

This is alpha. The thesis works end-to-end on a fresh greenfield
project (docs-only flow produces a populated PIL with zero manual
`pytest` steps), and the author's own repo dogfoods the whole gate.
But the dogfood is still finding bugs per pass. v0.1.x patches will
continue until three consecutive clean dogfoods — that's when v0.2
starts.

### What's here

- **Manifest + lockfile** — `pragma.yaml` + `pragma.lock.json` with SHA-256 canonical hash. `pragma init --brownfield` or `--greenfield`, `pragma spec add-requirement`, `pragma freeze`, `pragma verify manifest`.
- **Schema v2** — milestones + slices. `pragma migrate` upgrades v1 manifests idempotently.
- **Gate** — `pragma slice activate|complete|cancel|status`, `pragma unlock`. `.pragma/state.json` (atomic, flock-guarded, gitignored) + `.pragma/audit.jsonl` (append-only, fsync'd, committed).
- **Verify** — `pragma verify manifest|gate|discipline|integrity|commits|message|all`. Pre-commit enforces shape + gate; commit-msg enforces WHY/trailer; pre-push runs the full battery.
- **Recovery** — `pragma doctor` with classifier diagnostics. `--emergency-unlock` for wedged gates, `--clean-spans` for span retention.
- **Reports** — `pragma report --json|--human` produce byte-identical output from the same inputs; Markdown PIL shows `ok|mocked|missing|partial|red|skipped` per permutation with a Diagnostics banner when input artifacts are absent.
- **SDK** — `pragma-sdk` (separate pip package): `@trace(...)`, `set_permutation(...)`, pytest plugin auto-registered via `pytest11`. OpenTelemetry spans with `logic_id` + `permutation` attrs feed the PIL.
- **Claude Code hooks** — SessionStart / PreToolUse / PostToolUse / Stop, sealed by hash, integrity-verifiable.
- **Narrative** — `pragma narrative commit|pr|adr|remediation` drafts copy from the active slice and PIL. **Content quality is weak** (known); the template is in place but the prose generation is a placeholder.
- **Docs** — README, `docs/concepts.md`, `docs/usage.md`, `docs/reference.md`, `docs/doctor.md`, `docs/migrate.md`, `docs/roadmap.md`.

### Known issues at v0.1.0

All v0.1.0 known-issues (BUG-023, BUG-024, BUG-025, BUG-026) closed
in v0.1.2. See that entry for details.

### Pre-v0.1.0 history

The git log contains the iterative development path from the first
commit through this release. Old release tags (v0.1.0 through v1.1.2)
were consolidated into this single v0.1.0 during release-cadence
cleanup on 2026-04-24 — they represented a 3-day patch sequence on
what was really an alpha, not a stable 1.x. See
`CHANGELOG-archive.md` for the detailed per-version notes if you
need the history.
