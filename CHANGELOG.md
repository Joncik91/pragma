# Changelog

All notable changes to Pragma are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.3] — 2026-04-30

**Tier 3 now actually fires.** v2.1.2 wired DeepSeek but tier 3 stayed silent in real use because production-source resolution depended on tier-1's `infer_target` — which returns `None` exactly for the gaming patterns where production code is replaced (mock.patch + AsyncMock, monkeypatch, vi.mock, inline subclass). Every false-negative the lower tiers couldn't catch silently bypassed tier 3 too.

### Fixed

- **Two-tier production-source resolution.** When `infer_target` returns nothing, tier 3 now walks the test file's imports to find a sibling `<module>.py` (or `.ts`/`.tsx`/`.js`/`.jsx`) and reads it as the production source. If even that fails, the LLM judges the test alone with a `(production source not available)` placeholder — the prompt explicitly handles that case.
- **Verified end-to-end against the 4 v2.1.1 false-negatives.** All 4 sandboxes that escaped tier 1 + tier 2 (py-async with AsyncMock, py-class with inline fake subclass, py-import-as with autouse monkeypatch fixture, vitest-default-export with `vi.mock(...default: vi.fn())`) now emit `<lang>.semantic_gaming` warning verdicts on every test, with accurate per-test explanations from DeepSeek.

### Internal

- New private helpers in `src/pragma/judge/classify.py`: `_resolve_python_prod_source`, `_find_sibling_python_module`, `_resolve_vitest_prod_source`, `_find_sibling_vitest_module`. Walks imports, filters stdlib/test-only modules via `sys.stdlib_module_names`.

## [2.1.2] — 2026-04-30

**Tier 3 switches to provider-agnostic LLM via OpenAI SDK.** DeepSeek is the new default backend (faster, cheaper, OpenAI-compatible). Any OpenAI-compatible endpoint works — set `PRAGMA_LLM_BASE_URL` and `PRAGMA_LLM_MODEL` to swap providers without code changes.

### Changed

- **Tier 3 LLM judge backend: Anthropic → DeepSeek (default).** The `[llm]` extra now installs `openai>=1.40` instead of `anthropic`. The judge calls `client.chat.completions.create()` against the configured `base_url`. DeepSeek's automatic prompt caching kicks in for the system message — no explicit opt-in needed.
- **New env vars:**
  - `PRAGMA_LLM_API_KEY` (preferred) — provider-agnostic key.
  - `PRAGMA_LLM_BASE_URL` (default `https://api.deepseek.com/v1`) — point at any OpenAI-compatible endpoint.
  - `PRAGMA_LLM_MODEL` (default `deepseek-chat`) — model ID for the configured provider.
- **Legacy env vars still honored:** `PRAGMA_DEEPSEEK_API_KEY` and `PRAGMA_ANTHROPIC_API_KEY` continue to work as the API key (read in that order of preference). Existing v2.1.1 setups with `PRAGMA_ANTHROPIC_API_KEY` set will now hit DeepSeek by default — set `PRAGMA_LLM_BASE_URL` if you want to keep using a different provider.

### Notes

- **Anthropic API not directly supported in v2.1.2.** Anthropic uses a different message format (`/v1/messages`) than OpenAI-compatible chat completions (`/v1/chat/completions`). DeepSeek, OpenAI, Groq, Together, and most local servers (Ollama, LM Studio, vLLM) all work out of the box. If first-class Anthropic support is needed back, file an issue.
- **Test count: 391 → 402.** Same coverage area; more thorough env-var resolution and passthrough tests added.

## [2.1.1] — 2026-04-26

**Tier 3 LLM judge (warning-only).** Closes the v2.1 three-tier defense. After tier 1 (AST) and tier 2 (coverage), tier 3 asks Anthropic Haiku 4.5 whether each remaining `verified` test actually verifies the production function's behavior. Emits `<lang>.semantic_gaming` as a warning verdict (NOT in `BLOCKING_SUFFIXES`) — conformal calibration is deferred to v2.2 before tier 3 can block.

### Added

- **Tier 3 LLM judge.** Scaffolds shipped in v2.1.0 are now wired. Reads `PRAGMA_ANTHROPIC_API_KEY` from env; uses `claude-haiku-4-5` with prompt caching on the system message (saves cost dramatically across multiple tests in one file). Skips silently when the key is missing, the API call fails, or the response is malformed.
- **`pragma verify tests --with-llm`** — opt-in CLI flag. Off by default everywhere.
- **`PRAGMA_HOOK_WITH_LLM=1`** — opt-in env var for the PostToolUse hook. Off by default.
- New optional dep: `[llm]` extra (`anthropic>=0.40`). Required only when `--with-llm` is enabled.

### Internal

- `src/pragma/judge/{classify,prompt,client}.py` — full implementations.
- New verdict: `<lang>.semantic_gaming` (warning, NOT blocking).
- Test count: 360 → 391.

### Roadmap

- **v2.2**: Conformal-prediction calibration to make tier 3 block-capable. Tier 2.5 mutation oracle (`mutmut`/Stryker).

## [2.1.0] — 2026-04-26

**Outcome-based tier 2: coverage-of-target gate.** v2.0.x's static AST classifier kept playing whack-a-mole — every blind-subagent smoke run surfaced 3-7 new evasion patterns. v2.1 stops chasing patterns and starts checking outcomes. After the AST classifier (tier 1) marks a test as `verified`, tier 2 runs the test under coverage instrumentation and verifies the production target's lines actually executed. Every gaming pattern shares one property — production code never runs. One check kills entire classes of evasion.

### Added

- **Tier 2 coverage gate (Python).** `python.target_not_covered` — new blocking verdict. When tier 1 marks a test verified but the inferred production target's lines have zero hits in the test's coverage context, tier 2 emits `target_not_covered` and the verdict joins the blocking set. Uses `coverage.py`'s programmatic API + dynamic_context to get per-test attribution. Caches outcomes by `(test_hash, target_hash, target_symbol)` in `.pragma/cache.db` so re-edits with unchanged content are sub-100ms.
- **Tier 2 coverage gate (Vitest).** `vitest.target_not_covered` — same shape for TS/JS. Spawns `npx vitest run --coverage.enabled --coverage.provider=v8` in the test's project root (walks up looking for a `package.json` declaring vitest). V8 coverage is aggregated across the whole run, not per-test, so the gate broadcasts the file-level outcome to every test in the file. Conservative-leaning: if any test in the file hits the target, all are reported as covering.
- **`pragma verify tests --with-coverage`** — opt-in CLI flag for tier 2 (off by default for backward compat).
- **PostToolUse hook runs tier 2 by default.** That's the v2.x usage path. Opt out via `PRAGMA_COVERAGE_DEFAULT_OFF=1` env var. PreToolUse stays AST-only — file isn't on disk yet.
- New runtime dep: `coverage[toml]>=7.4`. New optional extras: `[coverage]` (`pytest-timeout`), `[llm]` (`anthropic`, reserved for tier 3 in v2.1.1).
- `target_not_covered` added to `BLOCKING_SUFFIXES`. `pragma blocking` returns 13 entries.

### Architecture

- New module trees: `src/pragma/coverage/{gate,runner,query,target,cache}.py` (tier 2) and `src/pragma/judge/` (tier 3 scaffold, lands in v2.1.1).
- `verify_file(path, with_coverage=False)` — orchestrator gains a flag; routes through `coverage.gate.classify_file` when true.
- Tier 2 is fail-open everywhere: missing `coverage`, missing `npx`, runner timeout, target not on disk, query failure — all skip silently. Pragma never blocks on tier-2 infrastructure failure.
- `gate.classify_file` only acts on tests tier 1 marked `verified`. Existing blocking verdicts (mocked-away, etc.) survive untouched — tier 1 is more specific about *what kind* of gaming.

### Internal

- New fixture set: `tests/fixtures/coverage_gated/` with both Python (`src/inventory.py` + 3 test variants) and Vitest (`vitest/src/charge.ts` + 2 test variants).
- 130+ new tests across `tests/coverage/` (8 test files).
- Test count: 232 → 360.
- Subprocess pytest runs use `--import-mode=importlib` to avoid the `tests/coverage/` package shadowing the real `coverage` library.

### Roadmap (deferred)

- **v2.1.1**: Tier 3 LLM judge. Scaffolds shipped in `src/pragma/judge/` but not wired. New `python.semantic_gaming` / `vitest.semantic_gaming` warning verdicts (NOT blocking — conformal calibration deferred until we have labeled data). Opt-in via `--with-llm` and `PRAGMA_ANTHROPIC_API_KEY`.
- **v2.2**: Conformal-prediction wrapper for tier 3 (block-capable once calibrated). Tier 2.5 mutation oracle (`mutmut` for Python, Stryker for JS). `pytest-testmon` integration for incremental whole-suite tier 2.

## [2.0.3] — 2026-04-26

**Three more false-negatives from a third v2.0.x smoke run.** One regression (silent-skip), two new evasion patterns. Final patch before the v2.1 architectural shift to outcome-based verification (coverage gate + LLM judge).

### Fixed

- **BUG-028 — async test functions silently skipped.** `walk_test_functions` and `_find_test_func` only matched `ast.FunctionDef`. Files containing only `async def test_*` came back with **zero verdicts** — the file looked clean even when every test mocked the production target. Worse than a false negative; the file was a black hole. Fix walks both `ast.FunctionDef` and `ast.AsyncFunctionDef` at every parser/orchestrator boundary; downstream rules duck-type without union annotations.

### Added (new rules)

- **`python.module_attr_reassignment` (BUG-025, blocking).** Top-level `import pricing; pricing.discount = stub` (or the same inside a test body) replaces the production function via direct attribute assignment after import. Bypasses `mocked-away` (no `mock.patch`), `monkeypatched` (no `monkeypatch.setattr`), and `module_shimmed` (no `sys.modules`). Rule walks both the enclosing module body and the test function body for `Assign(target=Attribute(...))` whose attribute path matches `(target_module, target_symbol)`. Identity assignments (`pricing.discount = pricing.discount`) are skipped.
- **`vitest.mocked-away` extended for namespace imports (BUG-026).** v2.0.2's BUG-023 fix added intermediate-variable detection (`const r = X(); expect(r).toEqual(...)`) but only for **named** imports. The namespace flavor — `import * as M from "..."; vi.mock("..."); const r = M.foo(); expect(r).toEqual(L)` — slipped through. Rule now adds a third pass: for each `vi.mock`'d path, reverse-look-up namespace aliases via `_collect_namespace_imports` and run the existing BUG-019 member-expression check.

### Internal

- Two new fixtures: `gamed_async_mocked_away.py`, `gamed_module_attr_reassignment.py`, `vitest_mocked_away_namespace.test.ts`. Wired into CLI parametrize and CI smoke loops.
- `BLOCKING_SUFFIXES` extended with `module_attr_reassignment`.
- Test count: 211 → 232.

### Roadmap

v2.1.0 is the architectural shift. Static AST whack-a-mole reached its ceiling: every smoke run surfaces 3-7 new evasion patterns. v2.1 adds a **coverage-of-target** gate (`--with-coverage`) and an optional **LLM judge** (`--with-llm`) on top of the existing AST classifier. Three-tier defense, one signal per gaming class, no more rule-by-rule chasing.

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

