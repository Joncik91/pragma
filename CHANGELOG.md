# Changelog

All notable changes to Pragma are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] — 2026-04-26

**Multi-language support — Vitest joins Python.** v2.0 refactors
Pragma's classifier into per-language plugins so adding a language is
a contained, additive change.

### Breaking

- **Verdict kinds are now language-prefixed.** Output JSON's `kind`
  field changed from `tautological` to `python.tautological`,
  `mocked-away` to `python.mocked-away`, etc. Anyone parsing the
  CLI's JSON programmatically must update.
- The `pragma.test_gaming` module is gone. Code lives under
  `pragma.languages.python.rules.<rule>`. Tests can use
  `pragma.languages.python._compat.classify_test` for the legacy
  per-function call shape.

### Added

- **Vitest support.** PreToolUse + PostToolUse hooks now classify
  Vitest test files (`.ts` / `.tsx` / `.js` / `.jsx` / `.mjs` / `.cjs`
  named `*.test.*` / `*.spec.*` / under `tests/` / under `__tests__/`
  AND importing from `vitest`). Seven verdicts ship: `vitest.tautological`,
  `vitest.mocked-away`, `vitest.swallowed`, `vitest.skipped`,
  `vitest.mismatched`, `vitest.conditional`, `vitest.empty_body`.
- **`pragma blocking`** subcommand prints the blocking-suffix set as
  JSON. The bash hook now consumes this to stay in lockstep with the
  library — no more drift between hook and CLI.

### Internal

- Per-language plugins live under `src/pragma/languages/<lang>/`.
  Each rule is its own file under `rules/<name>.py`. Adding a rule =
  adding a file + appending to the `RULES` list. SOLID/SRP/OCP.
- New runtime deps: `tree-sitter`, `tree-sitter-typescript`. Required
  for Vitest support (Python still uses stdlib `ast`).
- Single source of truth for Verdict (`pragma.verdict`), blocking
  suffixes (`pragma.blocking`), and the language registry
  (`pragma.languages`). DRY.

### Roadmap

- v2.1: Go.
- v2.2: Rust.
- v2.3: Kotlin.
- v2.4: Swift.
- v2.5+: Jest, Mocha, `node:test` (additional JS/TS frameworks).

## [1.1.0] — 2026-04-26

**Six new gamed-test detectors.** v1.0.x shipped five verdicts. A
research brief grounded in Bavota's test-smell taxonomy and METR /
SWE-bench agent-eval reports identified six more high-evidence
patterns. v1.1.0 ships them all in a single release. Verdict surface
grows from 5 to 11.

### Added (blocking)

- **`monkeypatched`** — `monkeypatch.setattr` targeting the production module/symbol. Sibling of `mocked-away`. Cited: Spadini et al., *"Mock Objects for Testing"* (ICSME 2017) — mocking the SUT correlates with low fault detection.
- **`swallowed`** — `try: target_call(); except: pass` swallows the call under test. Cited: Bavota's Exception Handling test smell + ruff `S110`. Conservative: only fires when no `assert` exists outside the swallowing try.
- **`skipped`** — `pytest.skip(...)` / `pytest.xfail` smuggled at the top of a test body. Cited: METR / SWE-bench agent transcripts where models add `skip` to dodge failing tests.
- **`conditional`** — every assertion lives inside an `if` / `for` / `while` branch the inputs never enter. Cited: Bavota's Conditional Test Logic; van Deursen *"Refactoring Test Code"* (XP 2001). Conservative: requires *every* assertion to be guarded.

### Added (warning, not blocking)

- **`empty_body`** — test body has no assertion and no `pytest.raises`. Cited: Bavota's Assertion Roulette / Empty Test smell. Warn-only because real codebases have placeholder tests during incremental development.
- **`parametrize_thin`** — `@pytest.mark.parametrize` with 0 or 1 case values. No prior literature; speculative but cheap to detect.

### Internal

- Test fixtures moved into `tests/fixtures/blocking/` and `tests/fixtures/warning/` subdirs to make the CI smoke step's expectations explicit.
- `_BLOCKING_KINDS` set extended in both `verify.py` and `plugin/hooks/check_diff.py` to keep verdict semantics in sync between the CLI and the hook.
- Plugin SKILL.md lists all 11 verdicts so Claude knows what to avoid.

### Reuse decisions

Per `decisions/never-reinvent.md` (vault): an OSS survey was run before writing pattern code. Ruff covers `S110` / `BLE001` / `PIE790`, but bringing it in as a runtime dep doubled the install tree for ~15 lines of detection — kept ruff as a dev-only dep, wrote the bare-except detector natively. PyNose's Kotlin code was a candidate to port but the patterns are simple enough fresh; cross-language port wasn't worth the attribution overhead.

## [1.0.2] — 2026-04-26

**Diff-mode hooks.** v1.0.1 hooks scanned the entire test file and
blocked when *any* test had a blocking verdict — pre-existing or
not. That meant any file with a historical gaming pattern was
permanently locked from edits, even legitimate ones. Live test in
the original session immediately surfaced this: editing a clean
test in a file containing one historic mismatched-flagged test
got blocked.

### Fixed

- **Hooks block only when an edit *introduces* new gaming.** Compare blocking-verdict test names before vs. after the edit (using `git show HEAD:<path>` for the previous version). Block only if the post-edit set contains a name that wasn't in the pre-edit set. Pre-existing gaming is the user's history — the hook's job is to catch the new stuff.
- **Logic moved to `plugin/hooks/check_diff.py`** so PreToolUse and PostToolUse stay tiny shell wrappers. Helper handles the no-git-repo case (treats previous as empty), graceful pragma-missing degradation, and clean error reporting that names only the new gamed tests.

### Verified

Smoke-tested all four cases:
- Clean file → gamed: BLOCKED ✓
- Pre-existing gamed test left alone, real test edited: ALLOWED ✓
- Pre-existing gamed test removed: ALLOWED ✓
- No-git-repo + new gamed test: BLOCKED ✓

## [1.0.1] — 2026-04-26

**Hook robustness.** v1.0.0 plugin hooks called bare `pragma verify
tests` and emitted a misleading "gamed assertion detected" message
when `pragma` wasn't on PATH (i.e. user hadn't run `pipx install
pragma` yet). Honest tests got rejected the same as gamed ones.

### Fixed

- **Plugin hooks degrade silently when pragma is not installed.** PreToolUse and PostToolUse now probe by running `pragma verify --help` (not by `import pragma`, which a stale namespace package can satisfy without supplying a working CLI). When neither `pragma` on PATH nor `python3 -m pragma` works, the hook exits 0 silently. Users without pragma installed are no longer ambushed; users with pragma installed get the real classifier output as before.
- Smoke-tested via blind subagent: a clean agent asked to write a test against an unimplemented module produced honest tests (call the production symbol, assert on return value, use `pytest.raises` for the reject case) and confirmed the v1.0.0 hooks were over-blocking.

## [1.0.0] — 2026-04-26

Initial release.

### CLI

- **`pragma verify tests <files>...`** — AST classifier. JSON by default, `--human` for terminal use. Exit 1 if any test in the file is in the blocking set; exit 0 otherwise.
- **`pragma init-precommit`** — drops a `.pre-commit-config.yaml` calling `pragma verify tests` on staged test files. Idempotent; refuses to overwrite without `--force`.

### Claude Code plugin

Installable via `/plugin install pragma@joncik91/pragma`.

- **PreToolUse hook** (`Edit|Write|MultiEdit` matcher): when Claude tries to write a test file, scan the candidate content; refuse with exit 2 if gamed.
- **PostToolUse hook** (same matcher): re-scan on disk after the tool lands. Catches `Edit` cases where the candidate content isn't directly visible at PreToolUse time.
- **Skill** (`plugin/skills/pragma/SKILL.md`): teaches Claude what patterns to avoid.

### Inference (zero config)

- `expected: success | reject` is inferred from the test name (`_rejects_` / `_raises_` / `_refuses_` / `_denies_` → reject, else success).
- Production target `(module, symbol)` is inferred from the test's imports (most-recently-imported non-stdlib symbol the body actually calls).

### Verdicts

Five at v1.0.0: `tautological`, `mocked-away`, `mismatched`, `weak`, `verified`.

