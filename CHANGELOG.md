# Changelog

All notable changes to Pragma are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.2] — 2026-04-26

**Seven new false-negatives surfaced by 8 fresh blind-subagent sandboxes.** Same evening as v2.0.1. All seven fixed.

### Fixed

- **BUG-023 — `vitest.mocked-away` missed `vi.mock` + intermediate-variable expect.** Rule required `expect(symbol(...)).toXxx(...)` (call directly inside expect). Models routinely write `const r = symbol(...); expect(r).toEqual(...)` — sailed through. Two of eight sandboxes used this exact pattern. Now: walk for `variable_declarator` binding `<symbol>(...)`, collect bound names, then `expect(<bound_name>).toXxx(...)` satisfies the rule.
- **BUG-024 — `vitest.mismatched` stub-phrase set too narrow.** v2.0.1 caught `"not implemented"` etc. but missed `"backend offline"`, `"not connected"`, `"service unavailable"`, `"not initialized"`, `"backend down"`, `"not configured"`, `"no api key"`. Same SWE-bench gaming style with different vocabulary. Substring match catches `"payments backend offline"` via `"offline"`, `"api not connected"` via `"not connected"`.

### Added (new rules)

- **`vitest.mocked-away` extended with `vi.spyOn` (BUG-019).** `vi.spyOn(<module>, "<sym>").mockReturnValue(...)` (and the `mockImplementation` / `mockResolvedValue` / `mockRejectedValue` siblings — including the `Once` variants) replaces the production function exactly like `vi.mock`. Rule now resolves `import * as M from "..."` namespace imports and walks the body for `vi.spyOn(M, "fn").mock*(...)` chains. Member-expression calls `M.fn(args)` are recognized.
- **`python.xfail_gaming` (BUG-022, blocking).** `@pytest.mark.xfail(strict=True)` on every test of an unimplemented stub makes the suite go green: each test predictably fails, `xfail`'s expectation is satisfied, nothing verified. Plain `xfail()` and `xfail(strict=False)` stay clean — those are legitimate known-failure markers.
- **`python.module_shimmed` (BUG-018, blocking).** Top-level `sys.modules["target"] = types.ModuleType("target")` (or `.setdefault` / `.update` variants) replaces the production module before the test imports it. Bypasses both `mocked-away` (no `mock.patch`) and `monkeypatched` (no `monkeypatch.setattr`). Rule walks the test file's module body for `sys.modules` subscript-assign / setdefault / update calls, plus `types.ModuleType(...)` constructor calls.
- **`vitest.orphan_mock` (BUG-020, blocking).** Stand-alone `const m = vi.fn().mockResolvedValue(L); const r = await m(); expect(r).toEqual(L)` — the mock is never wired to a production symbol; the assertion checks the mock returns its configured value. Structurally tautological but the existing `vitest.tautological` rule missed it. Fires only when the asserted literal byte-matches the mock's return literal.
- **`python.orphan_test` (BUG-021, blocking).** `tests/test_<name>.py` that never imports `<name>` and instead redefines a class named `PascalCase(<name>)` or a function named `<name>` inline. Fires conservatively — requires a *local module-level definition* in the test file with the matching name. Pragma's own test files do not trip it (verified end-to-end).

### Internal

- Rule classifiers now receive `tree` (the parsed AST) and `file_path` (the path of the file being classified) via the orchestrator's ctx kwargs. Existing rules accept `**_` so they ignore the additions.
- New fixtures: `vitest_mocked_away_intermediate.test.ts`, `vitest_mismatched_backend_offline.test.ts`, `vitest_spyon_mocked_away.test.ts`, `gamed_xfail_strict.py`, `gamed_module_shimmed.py`, `vitest_orphan_mock.test.ts`, `test_orphan_target.py`. All wired into `tests/test_cli.py` parametrize and the CI smoke loops.
- `BLOCKING_SUFFIXES` extended with `xfail_gaming`, `module_shimmed`, `orphan_mock`, `orphan_test` (the new blocking kinds).
- Test count: 148 → 211.

## [2.0.1] — 2026-04-26

**Three false-negatives surfaced in v2.0 blind-subagent smoke testing.** All three caught the same week v2.0 shipped, all three fixed in this patch.

### Fixed

- **BUG-016 — diff-mode hook false-blocks edits to files with pre-existing gaming.** `_get_old_source` wrote the prior version to `tempfile.NamedTemporaryFile(suffix=".py")`, which produced `/tmp/tmpXXXX.py`. That path doesn't satisfy `python.matches()` (no `test_` prefix, no `_test.py` suffix, no `tests/` segment) — same blind spot for `vitest.matches()`. The classifier returned `[]`, the old-blocking set was empty, and every blocking verdict in the new file was treated as new gaming. Any edit to a file with historic gamed tests false-blocked. Fix: write the old source under its **original filename** in a fresh tempdir so both language matchers recognize it.
- **BUG-014 — `python.monkeypatched` blind to lazy `import X` + attribute access.** `infer_target` only walked `from X import Y`. The gamed pattern from blind-subagent testing was `import tasks` (plain `ast.Import`) inside a try/except, paired with `monkeypatch.setattr(tasks, "schedule_task", _fake)`. With no `(target_module, target_symbol)` pair, the rule short-circuited and pragma classified the file as `python.verified`. Fix: as a fallback, collect plain-import module names (skipping stdlib + test-only) and pair each with attribute access in the body — `<root>.<attr>(...)` and `monkeypatch.setattr(<root>, "<attr>", …)`.
- **BUG-015 — `vitest.mismatched` lets stub-error and bare-`Error` `.toThrow(...)` pass.** The rule treated any `.toThrow(...)` as a real assertion. `expect(() => login(...)).toThrow("not implemented yet")` matches the production stub's `throw new Error("not implemented yet")` rather than asserting validation; same with `.toThrow(Error)` (matches anything). Both passed. Fix: when the test name implies an error and the body's `.toThrow(...)` arg is either a string literal containing a stub phrase (`not implemented`, `todo`, `stub`, `fixme`, `tbd`, `unimplemented`, `placeholder`, `no-op`, `noop`) or the bare `Error` identifier, the call doesn't count as a real assertion and the rule fires. Genuine validation messages and custom error classes stay clean. Same logic applies to `.rejects.toThrow*` chains.

### Added

- Two new fixtures exercising the fixed patterns end-to-end: `tests/fixtures/blocking/gamed_lazy_import_monkeypatched.py` and `tests/fixtures/blocking/vitest_mismatched_stub_error.test.ts`. Both wired into `tests/test_cli.py` parametrize and the CI smoke loops.
- `tests/test_hook_diff.py` — first end-to-end regression suite for the diff-mode hook against a fabricated git repo.

### Internal

- Test count: 137 → 148.

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

