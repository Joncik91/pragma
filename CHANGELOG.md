# Changelog

All notable changes to Pragma are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.5] — 2026-04-24

**Span retention.** Closes the v1.0.4-parked paper cut that
`.pragma/spans/*.jsonl` accumulates forever on long-running projects.
Since KI-1 each pytest run writes a fresh uniquely-named JSONL, so on
a busy repo the directory grows linearly with test runs and starts
hurting `ls`, `pragma report`, and disk after a few months of real
use. v1.0.5 adds retention to `pragma doctor` — opt-in cleanup, not
auto-prune.

### Added

- **`pragma doctor --clean-spans`** with `--keep-runs N` / `--keep-days D`
  / `--dry-run`. Keeps the N newest span files by mtime, or files within
  D days, or both (union — more lenient rule wins). Default when no
  flag and no manifest config: `keep_runs=50`. `--dry-run` reports
  what would be removed without touching the filesystem.
- **`spans_retention:` block in `pragma.yaml`** — optional, fields
  `keep_runs` and `keep_days`. Picked up by `pragma doctor
  --clean-spans` when no CLI flag is given, so projects can pin their
  policy without typing it every time. CLI flags override manifest
  config for the one invocation.
- **`spans_cleaned` audit event** — every non-dry `--clean-spans` run
  appends one line to `.pragma/audit.jsonl` with `files_removed`,
  `bytes_freed`, and the strategy used. Keeps the forensic record
  complete even as span files themselves roll off.
- **`pragma doctor` base mode now reports `spans_count` and `spans_bytes`**
  in its diagnostics payload so users see accumulation before the
  directory gets uncomfortable. No new flag required.
- **`pragma.core.spans`** — pure-functional module with `SpansRetention`,
  `CleanReport`, `clean_spans`, `summarize_spans`, `span_files`. Sorted
  outputs for deterministic reporting. All paths traced with
  `@trace("REQ-010")`.

### Meta

v1.0.5 was scoped tight on purpose: one REQ (REQ-010), one new slice
(M01.S6), one new core module, seven permutations. No behavior change
to the gate, manifest canonicalisation of an optional new field
(`spans_retention`), `pragma freeze` re-runs idempotently on the same
input. Next release is v1.1.0 — TypeScript SDK + battery template +
discipline checker — which is a different shape of work and deserves
its own cycle.

### Changed

- `.pre-commit-config.yaml` — semgrep hook now pins
  `additional_dependencies: [setuptools]` so its vendored
  opentelemetry import of `pkg_resources` resolves on py3.12+; pip-audit
  ignores GHSA-58qw-9mgm-455v (pip advisory with no published fix);
  deptry replaced with a local hook that targets `packages/pragma-sdk`
  only (upstream hook can't handle the uv-workspace top-level
  pyproject; pragma package cleanup parked as KI-14). All three are
  infra fixes surfaced when v1.0.4→v1.0.5 pre-commit caches were
  rebuilt after the repo's on-disk move.

### Known Issues

- **KI-13: `pragma slice complete` subprocess cwd breaks for brownfield
  workspaces with nested `tests_root` (e.g. Pragma's own
  `tests_root: packages/pragma/tests/`).**
  `pragma.core.tests_discovery.run_tests` invokes pytest with
  `cwd=tests_dir.parent`, and `collect_tests` emits nodeids relative to
  the user's cwd. On a brownfield repo where `tests_root` is two
  levels deep, those nodeids prepend `packages/pragma/tests/...` but
  pytest is already chdir'd into `packages/pragma/`, so it looks for
  `packages/pragma/packages/pragma/tests/...` and reports every test
  as `error`. Workaround: finish the slice with
  `pragma slice complete --skip-tests` when the suite is known green
  via `python -m pytest` directly. Does not affect greenfield
  projects (the smoke script validates this). Targeted fix: thread
  the repo root into both functions as an explicit parameter and
  cwd there. Deferred to a focused follow-up so v1.0.5 stays
  scoped to span retention.
- **KI-14: deptry hook runs on `pragma-sdk` only — `pragma` package
  has eight DEP002 false-positives** where dev-only tools
  (ruff, mypy, pytest-cov, pre-commit, types-PyYAML, opentelemetry-api,
  opentelemetry-sdk) are listed under `[project.dependencies]` rather
  than `[project.optional-dependencies.dev]`. Deptry correctly reports
  they are unused at runtime. Fix is a pyproject.toml reshape, not a
  dependency change; parked so v1.0.5 does not conflate scope.

## [1.0.4] — 2026-04-21

**Release readiness.** Closing the v1.0 series with the gate gaps that
v1.0.3 + v1.0.3.1 + v1.0.3.2 kept surfacing on CI but not locally.
The local `pragma verify all` is now actually a mirror of what CI
enforces: mypy runs on every commit, the version pins can't drift
across release prep, and a `scripts/pre-release-smoke.sh` script
exercises the full day-one user flow (including the first
`git commit` under pre-commit on a fresh-init repo) before any tag
is cut. After this, v1.1's TypeScript work starts on a clean base.

### Added

- **mypy runs in the project venv** via a new `language: system`
  pre-commit hook (two entries, one per package). Previously
  mypy's isolated pre-commit env couldn't import `pragma-sdk` as
  an editable dep, so the hook got `SKIP=mypy`'d on every local
  commit — which is why v1.0.3 shipped with 18 mypy-strict errors
  only CI caught. The `init` scaffold template now documents both
  patterns (isolated mirrors-mypy vs language:system local) so
  downstream projects can pick the one that fits their setup.
- **`scripts/pre-release-smoke.sh`** runs every release's checks:
  pragma + pragma-sdk pytest, mypy strict on both packages,
  `pragma verify all`, span-file glob (KI-1 layout), and a full
  greenfield scaffold → `pre-commit install` → first
  shape-conformant `git commit` → post-commit `verify all` cycle
  in a tmp dir. Every bullet corresponds to a real v1.0.x bug CI
  caught: BUG-013 (first-commit on fresh-init repo), v1.0.3.1
  (mypy strict), v1.0.3.2 (spans-file glob). Exits 0 iff every
  check passes.
- **Version-pin sync test** at
  `packages/pragma/tests/test_version_sync.py` reads the three
  places the Pragma version is declared — `__version__` in
  `__init__.py`, `version` in `pyproject.toml`, and the assertion
  in `test_cli_doctor` — and fails the commit if any two disagree.
  Guards against the class of release-prep drift where one file
  gets bumped and another is forgotten.

### Meta

After v1.0.4 the local pre-commit gate runs: gitleaks, ruff-format,
ruff-lint, mypy-pragma, mypy-pragma-sdk, pip-audit, check-added-
large-files, check-merge-conflict, pytest, `pragma verify all`. All
the same checks CI runs on every push. The release protocol is:

1. bump versions in the three pin sites
2. `scripts/pre-release-smoke.sh`
3. git commit + tag + push + gh release

Known issues parked for v1.1 / later: span-file pruning (`.pragma/
spans/*.jsonl` accumulates forever; doctor should offer cleanup).

## [1.0.3.2] — 2026-04-21

**CI workflow catches up to v1.0.2's KI-1.** v1.0.3.1 passed mypy strict
but failed the "report determinism check" job because `.github/
workflows/ci.yml` still asserted the pre-KI-1 fixed filename
`.pragma/spans/test-run.jsonl`. After KI-1, the pytest plugin writes
per-session files like `test-run-{timestamp}-{pid}-{uuid}.jsonl` so
the fixed-filename test always failed. Again, Pragma's local gate
couldn't catch this (CI workflow isn't run locally); only the real
GH Actions run did. Same meta-pattern as v1.0.3.1.

### Fixed

- `.github/workflows/ci.yml` — the "Assert spans and junit landed at
  repo root" step now globs `.pragma/spans/*.jsonl` and asserts at
  least one non-empty file exists, rather than checking the exact
  pre-KI-1 `test-run.jsonl` path. Pairs with the KI-1 aggregator
  back-compat shim that already handled both single-file and
  directory inputs.

## [1.0.3.1] — 2026-04-21

**Hotfix-of-hotfix.** v1.0.3 CI failed on `mypy --strict` because the
KI-11 refactor in v1.0.2 left ~10 extracted private helpers without
full type annotations. Locally the pre-commit mypy hook gets SKIP'd
(known-broken env), so the v1.0.2 gate didn't catch them; the
pragma-sdk CI job does run mypy fresh and flagged it on v1.0.3's
push. No functional code change, just type annotations + a couple of
`cast` calls to align reality with the types that were already
declared.

### Fixed

- **18 mypy --strict errors across 10 files** introduced by the v1.0.2
  KI-11 function-splitting pass. All signatures of the new
  `_assert_*` / `_check_*` / `_deny_*` / `_emit_*` helpers now carry
  full parameter annotations (`Manifest`, `State`, `Requirement`,
  `list[Requirement]`, `dict[str, list[CollectedTest]]` etc). The
  dispatcher's `_get_handler` returns a properly `cast`-narrowed
  Callable. A stale `# type: ignore[return-value]` in the migrator
  is removed (the return value is now correctly typed and the ignore
  was unused). One latent assignment-type mismatch in
  `verify_message` (an `err: PragmaError` shared between two
  subclass constructors) is annotated at the base-class level.

### Meta

- Keeping v1.0.3's tag + release (functional contract is unchanged);
  v1.0.3.1 is purely the CI green-up. Pattern to fix separately:
  the pragma-sdk CI's mypy-strict step is real gate coverage that
  the local pragma pre-commit can't mirror today. Tracking as a KI
  for v1.0.4+: get mypy to pass locally without SKIP.

## [1.0.3] — 2026-04-21

**Same-day hotfix.** v1.0.2's CI failed on the very commit that
tagged it, because `pragma verify all` erred on a freshly-initialised
repo that had no commits yet — the exact scenario every new user hits
on their first `git commit`. The smoke test before v1.0.2 caught
BUG-012 at the `pragma init` step but stopped there; it didn't
exercise pre-commit + first commit, so BUG-013 slipped past. Also
cleared KI-12: Pragma's PIL is now 42/42 ok (previously 28/42 ok +
14/42 mocked because legacy REQ-003/REQ-004 tests predated the
`set_permutation` pattern).

### Fixed

- **BUG-013** — `pragma verify all` on a freshly-initialised git repo
  with no commits yet failed with `git_unavailable`. `_check_commits`
  now probes `git rev-parse --verify HEAD` after confirming the repo
  exists; if HEAD doesn't resolve, returns `{ok: true, check: commits,
  skipped: "no_head"}`. Day-one flow `git init → pragma init → pragma
  freeze → git commit` now works end-to-end. Caught by CI on v1.0.2's
  release commit.
- **KI-12** — Six REQ-003 + eight REQ-004 test bodies wrapped in
  `@trace(req_id)` helpers called inside `with set_permutation(...)`
  so PIL scores them `ok` rather than `mocked`. Pragma's own PIL is
  now a truthful 42/42 ok.

### Added

- Pre-release smoke protocol now goes further than v1.0.2's: fresh
  `git init`, scaffold, install pre-commit, and run `git commit`
  under the scaffolded config. The v1.0.2 smoke test stopped at
  `pragma verify all` and missed BUG-013; keeping the heavier check
  as part of the release routine going forward.

## [1.0.2] — 2026-04-21

**The "stop leaking insider knowledge" release.** v1.0.1 published seven
known issues in its changelog; a Phase-1 bug-hunt turned up eleven more
in an explicit "find what isn't in that list yet" pass, and a pre-release
greenfield smoke test caught a twentieth at the doorstep. All are fixed
or honestly deferred. 37 commits; every fix ships with a regression test.
`pragma verify all` is now the real umbrella — manifest, gate, integrity,
discipline, commits — rather than three of five. Pragma's own source
passes its own discipline check cleanly for the first time since the
check existed.

### Fixed

**PIL accuracy (KI-1, BUG-007, BUG-010).** Spans are per-session files
under `.pragma/spans/` instead of a single overwritten `test-run.jsonl`,
so PIL survives multi-suite projects (pragma + pragma-sdk, pre-commit
pytest + CI pytest). The aggregator now requires `pragma.permutation` to
match, not just `pragma.logic_id` — a span carrying `permutation="none"`
no longer false-positives a declared permutation as `ok`. `@trace` on
generator, async, and async-generator functions wraps the actual
execution instead of object construction, so PIL sees real work.

**Gate + slice lifecycle (BUG-011, KI-5, KI-3, BUG-012).** `slice
activate --force` now cancels the prior active slice (with
`completed_at=now`) rather than orphaning it as forever-`in_progress`.
`slice cancel` erases never-unlocked slices from `state.slices` so a
subsequent manifest edit doesn't trigger spurious `gate_hash_drift`;
slices that did reach UNLOCKED stay as real history. The `M01.depends_on:
[M00]` phantom dependency on the migrator's implicit backfill milestone
is gone, and the migrator's source carries an explicit invariant comment
to stop the next author re-introducing it. `plan-greenfield` now rebinds
`state.manifest_hash` after refreezing, so `pragma verify all` stays
green on the day-one greenfield flow — surfaced by the pre-release smoke
test; without it, every new greenfield user would have hit
`gate_hash_drift` on their first verification.

**Hook dispatcher (BUG-003, BUG-001, KI-6).** Stop hook crashes now fail
to `{"continue": false, "stopReason": ...}` so the turn ends cleanly with
a visible reason rather than silently pretending the gate check passed.
PreToolUse / PostToolUse / SessionStart still fail open (allow edits when
the hook breaks) because a DoSed editing turn is worse than a missed
check there. `post_tool_use` degrades gracefully when `pragma.yaml` is
missing or malformed — previously logged a spurious `hook_crash` audit
entry on every first-use. Hook crash forensics now route to
`.pragma/hook-crash.jsonl` (gitignored) instead of the committed
`audit.jsonl`, so a buggy hook or a test run can't pollute real gate
history.

**`verify all` completeness (BUG-009).** `verify all` was the umbrella
the Stop hook invoked to decide whether a turn could end, but it only
ran `manifest`, `gate`, `integrity`. Now it runs all five:
`["manifest","gate","integrity","discipline","commits"]`. The `--ci`
flag stays as an accepted no-op so existing CI configs keep working.
The commits check skips gracefully on non-git scaffolds (fresh
`pragma init` under test fixtures) rather than erroring on
`git_unavailable`.

**Discipline debt (KI-11).** Enabling discipline in `verify all`
surfaced 36 pre-existing violations in Pragma's own source — 17 commits
cleared them across 13 files. Key per-file splits: doctor's emergency
unlock into phases, verify.py into `verify.py` (CLI shell) + new
`verify_checks.py` (check logic), gate.activate into
locate/check/build, pytest-plugin-aware collector, plan-greenfield into
read/validate/build/rewrite phases, init's mode-validation ladder. The
discipline checker itself also held itself to its own budget for the
first time. Acknowledged `TODO(owner)` markers no longer trip the
`todo_sentinel` rule — `plan-greenfield` writes `TODO(pragma): …`
placeholders by design and they're no longer cause for failure.

**Manifest + error-payload contract (REQ-006, KI-2, BUG-005, BUG-004,
BUG-006, BUG-008).** `pragma freeze` on an unchanged `pragma.yaml` is
now truly idempotent at the lockfile-bytes level, not just
manifest-hash-level — `write_lock` short-circuits when the existing
lockfile already records the same hash. v2 manifests with requirements
but no milestones now fail validation instead of silently hashing. A
`vision: ""` string hashes identically to the field being absent. Six
ad-hoc `PragmaError(code="...")` call sites promoted to typed
subclasses (`CompleteCollectFailed`, `UnlockCollectFailed`,
`VerifyCollectFailed`, `GitUnavailable`, `CommitMsgNotFound`,
`ReasonRequired`) so the public error contract lives in one file.
Parametrised tests now participate in gate decisions fully — the
consumer pattern `{c.name: c for c in collected}` that silently kept
only the last variant has been replaced by a `group_by_name` helper.
`verify commits` surfaces `commits_checked` and `range` so vacuous
runs (empty range, fallback-to-HEAD on a missing `--base`) are visible.

### Changed

- Default `.pre-commit-config.yaml` scaffolded by `pragma init`
  (**KI-7**) now ships only hooks that work out-of-the-box: gitleaks,
  ruff, pip-audit, pre-commit-hooks. `mypy`, `semgrep`, and `deptry`
  move into commented-out opt-in blocks with per-hook explanations of
  what each requires to work. Users get a first commit that succeeds
  without `SKIP=` gymnastics.
- Ruff pre-commit pin bumped from `v0.8.6` to `v0.15.11` in the
  scaffolded template so new projects inherit the v1.0.1 skew fix.
- Dispatcher uses `_get_handler(event)` on-call rather than a pre-bound
  `_HANDLERS` dict, so monkeypatching a hook module's `handle` actually
  reaches the dispatch code — fixed a silent false-positive in an
  existing crash-recovery test.

### Added

- `pragma.core.tests_discovery.group_by_name` — parametrise-aware
  grouping of collected tests by base name.
- `pragma.core.audit.append_hook_crash` + `HOOK_CRASH_FILENAME`
  constant.
- Three new `@trace` variants (async, generator, async-generator) in
  `pragma_sdk.trace`.
- Six new typed `PragmaError` subclasses covering every previously
  ad-hoc error path.

### Known issues (parked for v1.0.3)

- **KI-12** — 14 legacy REQ-003 / REQ-004 test bodies don't wrap their
  work with `set_permutation`, so BUG-007's stricter aggregator scores
  them `mocked` rather than `ok`. PIL on Pragma's own repo is 28/42 ok
  + 14/42 mocked. Each test needs a small `_assert_*` helper decorated
  `@trace(req_id)` called inside `with set_permutation(perm_id)` — see
  `test_req_006_determinism.py` for the canonical template. Mechanical
  but voluminous.
- **Span-file pruning** — `.pragma/spans/*.jsonl` accumulates
  per-session files indefinitely. Spans are gitignored so no history
  pollution, but disk use grows without bound. Needs a `pragma doctor
  --prune-spans` or similar. Not a v1.0.2 blocker.

## [1.0.1] — 2026-04-21

**Stabilisation patch. Three v1.0-era bugs uncovered by first real dogfood
session.** PIL on Pragma's own repo is now 41/41 ok — up from 34/34 —
because the collector can finally see the test suite.

### Fixed

- **REQ-007 — pre-commit ruff rev skew.** `.pre-commit-config.yaml`
  pinned ruff-pre-commit at `v0.8.6` while the project venv runs
  `0.15.11`; the two disagree on assert-statement line-wrapping, which
  caused CI format checks to fail against locally-clean trees and
  forced `SKIP=ruff-format` on every push. Bumped the pre-commit pin to
  `v0.15.11` and removed the SKIP workaround. Other tool pins (gitleaks,
  mypy, semgrep, pip-audit, deptry) intentionally left alone — bulk
  updates belong in their own toolchain-refresh slice.
- **REQ-008 — `pragma freeze` crashed on malformed milestone refs.**
  When a requirement references a non-existent milestone (e.g.
  `milestone: M99`), pydantic's `@model_validator` raises `ValueError`,
  which pydantic wraps under `ctx.error = <the ValueError object>`.
  `json.dumps` on the error-payload path then died with
  `TypeError: Object of type ValueError is not JSON serializable`
  instead of emitting the structured `manifest_schema_error` JSON the
  CLI contract promises. Added `_jsonable_errors()` in
  `pragma.core.manifest` that `str()`-coerces any `BaseException`
  sitting inside `ctx` before serialisation.
- **REQ-009 — pytest 9 collector returned zero nodeids under
  inherited `-q`.** `collect_tests` ran `pytest --collect-only -q` and
  parsed lines containing `::`, which worked under pytest 8. Pytest 9
  compacted `-q --collect-only` output into file-summary form
  (`path.py: 4`) so the parser returned zero collected tests. Because
  the gate's "unlock requires all expected test names present" check
  intersects the collected set with the expected set, this made every
  slice activation report **all** required tests as missing — the
  silent reason why `pragma slice activate M01.S5` failed in the first
  minute of this session. Fixed by passing `-o addopts=` to override
  the inherited addopts so pytest uses default nodeid-per-line output.

### Added

- Three new dogfood tests at `packages/pragma/tests/req/` — one per REQ
  above — each wrapped in `@trace("REQ-00N")` so the PIL aggregator
  scores them as `ok` rather than `mocked`. These are the first
  acceptance tests for Pragma's own stabilisation work.

### Changed

- Pre-push hook SKIP list no longer needs `ruff-format` (REQ-007).
  `mypy` stays skipped because `pre-commit`'s mypy environment lacks
  `pragma-sdk` as an editable dependency; CI still runs mypy fresh in a
  proper venv, so correctness isn't lost. Fixing that properly is
  v1.0.2 work.

### Known issues (parked for v1.0.2 — the "insider-knowledge" slice)

v1.0.1 patches three ambient bugs but does not close the larger gap
surfaced during this dogfood session: **several real problems still
require tribal knowledge to work around**, which defeats the "non-
coder trusts the commit" premise. Each item below is something a
first-time Pragma user would hit and not know how to resolve without
reading this changelog.

**PIL aggregation**

- `.pragma/spans/test-run.jsonl` is overwritten on each `pytest` run
  (`write_text`, not append), so any project with more than one test
  path (pragma + pragma-sdk, monorepo packages, split test targets,
  pre-commit's pytest hook + a second CI pytest invocation) sees PIL
  collapse to 0/N after the "wrong" suite runs last. The v1.0.1 fix
  for this repo was to run the span-producing suite **last** — that
  knowledge should not live in the user's head. Honest fix: append
  mode with per-session isolation, or a persistent span store that
  merges across runs. Aggregator then reads all files.

**Slice lifecycle hygiene**

- `slice activate` mutates state **before** checking
  `milestone_dep_unshipped`, so a failed activation leaves a phantom
  LOCKED slice that has to be `slice cancel`ed. Should be swapped to
  check deps first, then mutate. (Noted in this session while trying
  to activate `M01.S5`.)
- `slice cancel` marks a never-unlocked slice as `cancelled` rather
  than erasing it, so the next `freeze` changes the manifest hash and
  `verify all` then errors with `gate_hash_drift`. The only clean
  recovery is `rm .pragma/state.json`, which contradicts "state is
  authoritative" as a user-facing promise. `doctor --emergency-unlock`
  should handle gate-hash-drift-after-freeze, not only bricked-LOCKED.
- `.pragma/audit.jsonl` is a tracked file, so any mistaken
  `slice activate` before the user's first intentional slice
  produces audit-log entries that will be committed as part of the
  next real slice unless the user manually removes them. Fix: don't
  log until the first intentional activation, or have `doctor`
  detect-and-offer-to-clean cancelled-only preambles.

**Freeze + migration edge cases**

- Freezing a manifest with a REQ missing `milestone:` or `slice:`
  fields succeeds silently rather than emitting the promised
  `requirement_unassigned` error. The pydantic model makes those
  fields `Optional` and the validator only runs when values are
  non-null. Needs a schema-level tightening.
- The v1→v2 migrator's auto-created `M00` milestone is an unshipped
  dependency of `M01`, so `M01` slices can't be activated without
  manually editing `M01.depends_on`. Either drop the auto-dep or mark
  `M00` as pre-shipped on migration.
- `pragma freeze` is not idempotent at the lockfile-bytes level: the
  `generated_at` timestamp is rewritten on every call even when the
  manifest hash is unchanged, so back-to-back `freeze`s produce
  diff-noisy lockfiles. REQ-006's acceptance test covers *hash
  stability* and *`pragma report` byte equality*, but not *lockfile
  byte equality* — so the test passes while the user-visible
  behaviour fails. Fix: either skip the file write when the hash
  matches the existing lock's hash, or move `generated_at` out of
  the lockfile into a sibling metadata file; strengthen REQ-006's
  test to assert lockfile-byte stability.

**Safety battery template**

- `pragma init --brownfield` writes a `.pre-commit-config.yaml` with
  six hooks (`mypy`, `semgrep`, `pip-audit`, `deptry`, `gitleaks`,
  `ruff`) that do not all work out-of-the-box in common sandbox / CI
  environments. Specifically: `mypy`'s pre-commit env lacks
  `pragma-sdk` as an editable dep; `semgrep`'s pinned env ships a
  `pkg_resources` import that fails on Python 3.13; `deptry`'s
  environment doesn't install the `deptry` binary reliably. New users
  hit cryptic failures on their first commit with no guidance on which
  to `SKIP=` vs which is a real signal. Fix: the `pragma init` battery
  template should only include hooks that work in the default venv/CI
  setup, with opt-in flags for the rest — or ship a versioned
  `.pragma/skip-known-broken.env` that pre-push sources automatically.

## [1.0.0] — 2026-04-21

**Greenfield bootstrap ships. Evolutionary rollout complete.**

v0.1 taught us the manifest was load-bearing. v0.2 taught us the gate
could be built on top of it without AI coupling. v0.3 taught us the
hooks + safety battery compose at one seam. v0.4 taught us PIL and
the SDK ship together or not at all. v1.0 finishes the UX around the
bones — `pragma init --greenfield` scaffolds a seed manifest plus a
Claude Code primer, `pragma spec plan-greenfield` turns a markdown
problem statement into a REQ skeleton, `pragma doctor` is now a real
recovery tool with eight diagnostic codes and an `--emergency-unlock`
escape hatch, and REQ-006 locks in `pragma report` byte-determinism as
an acceptance test on Pragma itself. PIL now 34/34 ok.

### Added

- `pragma init --greenfield --name <name> --language python` —
  scaffolds a seed `pragma.yaml` with M01.S1 + REQ-000 placeholders,
  freezes the lock, primes `.pragma/state.json`, stamps the settings
  integrity hash, writes `claude.md` as the Claude Code primer, and
  creates empty `src/` + `tests/` trees. Refuses non-empty `src/` and
  existing `pragma.yaml`.
- `pragma spec plan-greenfield --from <problem.md>` — deterministic
  Pattern C bootstrap. Parses `# Heading` sections and turns each into
  a TODO requirement (`REQ-001..REQ-00N`) under M01.S1. No LLM calls;
  same input → same manifest bytes. Refuses brownfield repos and
  second runs.
- `pragma doctor` real recovery engine. Walks the repo, classifies
  eight failure modes (`no_manifest`, `no_lock`, `hash_mismatch`,
  `lockfile_unparseable`, `no_pragma_dir`, `stale_state`,
  `claude_settings_mismatch`, `audit_orphan`), emits ordered
  `remediation:` strings. Fatal codes short-circuit; warns coexist.
- `pragma doctor --emergency-unlock --reason "..."` — escape hatch for
  bricked state. Resets `state.json` to neutral, appends a structured
  audit entry with the user's reason, refuses when state is already
  neutral.
- REQ-006 (new M01.S4 slice) — two permutations asserting
  `pragma report --json` byte-identical output and manifest-hash
  stability across a noop freeze. Closes v1.0 done criterion §7.8.5.
- `docs/usage.md`, `docs/doctor.md`, `docs/migrate.md` — first
  user-facing documentation. Covers brownfield + greenfield flows,
  every diagnostic code, and the schema version contract.
- CI `greenfield-smoke` job — spins up a fresh greenfield repo on a
  clean runner, runs init → plan-greenfield → freeze → verify →
  doctor end-to-end. Closes v1.0 done criterion §7.8.4 (empty-to-green).
- `migrate_to_current()` dispatcher in `core/migrate.py` with
  `CURRENT_SCHEMA_VERSION = "2"` constant. Future schema bumps slot
  in next to `migrate_v1_to_v2` without changing caller signatures.

### Changed

- `Manifest` schema now accepts an optional `vision:` field.
  `canonicalise()` strips it when absent so pre-vision manifests keep
  their byte-stable hash. Greenfield templates populate it with a
  TODO placeholder paragraph.
- `pragma doctor` payload grows a `diagnostics: [...]` list, a
  `pragma_dir_exists` boolean, and a `claude_settings_exists` boolean.
  All v0.1 fields (ok, pragma_version, cwd, manifest_exists,
  lock_exists, pre_commit_config_exists) remain for
  backward-compatibility.
- `pragma.__version__` literal synced to package version (was frozen
  at `0.1.0` since v0.1 — `pragma doctor`'s `pragma_version` now
  reflects reality).
- Packages (`pragma`, `pragma-sdk`) both bumped to 1.0.0.

### Deferred to v1.1

- Human-subjects validation of done criteria §7.8.1 (non-coder
  bootstraps in < 1h) and §7.8.3 (PIL legible to 3 non-coders).
  Tooling passes; real user studies come post-ship.
- "Deployed artifact" half of §7.8.4 — Pragma itself doesn't publish
  wheels or containers yet; adding that belongs with a concrete
  distribution target.

See `docs/v10-rc-evidence.md` for the full §7.8 walkthrough.

## [0.4.2] — 2026-04-21

Dogfood polish + commit-shape enforcement.

### Added

- `pragma verify message <file>` subcommand — validates one draft
  commit message against the canonical shape (subject ≤72 chars,
  body with WHY: paragraph, Co-Authored-By: trailer). Strips git
  comment lines so it composes with the `commit-msg` hook.
- Pre-commit template now wires `pragma-verify-commit-msg` at the
  `commit-msg` stage and `pragma-verify-commits-pre-push` at the
  `pre-push` stage. Both active on Pragma's own repo — the
  commit-shape rule is now enforced automatically, not just
  declared.
- `@pragma_sdk.trace` now on 18 Pragma helpers across REQ-001..REQ-004
  so `pragma report` shows 32/32 ok permutations against Pragma's
  own repo (up from 7/32 at v0.4.1 ship).

### Changed

- Pragma's own `.pre-commit-config.yaml` pytest hook scoped to the
  two package test subtrees instead of running pytest from repo
  root — avoids the known ImportPathMismatchError between the two
  `conftest.py` files.
- `PRAGMA.md` template + Pragma's own PRAGMA.md now document the
  commit-message shape rule and the "plan task titles ≤72 chars"
  planning guardrail.

## [0.4.1] — 2026-04-21

v0.4 was cut but the initial tag pointed at a tree that was
unusable from a clean clone — `pragma.narrative.commit` was left
untracked so `pragma --help` ImportErrored on any fresh install.
v0.4.1 is the real v0.4 release: same feature set, now actually
shippable, with the fixes the internal code review demanded.

### Fixed

- `pragma.narrative.commit` module + `commit-message.tpl` + round-trip test
  are now tracked in git (`fix(v04): ship missing narrative.commit module`).
  The pre-tag HEAD could import-fail on clean install; this resolves it.
- Single-source `pragma.yaml` at the repo root; the duplicate under
  `packages/pragma/` is removed so manifest edits don't have to be
  applied twice.
- Pytest config moved to the repo-root `pyproject.toml` so pytest
  rootdir equals repo root. Span dumps and JUnit XML now land where
  `pragma report` actually reads them; the mock-detection heuristic
  is no longer inert on real projects.
- `pragma init --brownfield` now writes `pytest.ini` (when no
  existing pytest config is present) with `--junit-xml=.pragma/pytest-junit.xml`.
- REQ-005 dogfood tests renamed to `test_req_005_<permutation>` so
  the aggregator joins emitted spans to declared permutations.
  `pragma report --json` now shows `summary.ok = 7` for REQ-005
  against Pragma's own repo, up from `0`.
- Mypy `--strict` actually runs in CI now (it was silently off because
  config lived in a sub-package pyproject). `pragma-sdk` ships a
  `py.typed` marker so downstream strict mypy doesn't flag
  `@pragma.trace` as untyped.
- Report-determinism CI job asserts spans, junit and
  `summary.ok > 0` before diffing. An empty-report green is no
  longer possible.
- Four spec §8.1 error classes added (`ReportNoSpans`,
  `ReportManifestDesync`, `NarrativeEmptyStage`,
  `NarrativeNoActiveSlice`). `narrative commit` refuses to generate
  an empty commit message unless `--allow-empty` is passed.
  `narrative pr` refuses to dump the whole manifest when
  `state.active_slice` is null — pass `--slice=<id>` or activate
  a slice.
- `.gitignore` covers `.pragma/spans/`, `.pragma/pytest-junit.xml`,
  and the corresponding `packages/*/.pragma/` leaks.

## [0.4.0] — 2026-04-21 — YANKED

Internal release; not shipped. See 0.4.1 for the real v0.4.

### Added

- Monorepo split: `packages/pragma-sdk/` + `packages/pragma/` with uv workspace.
- `pragma-sdk` runtime package: `@trace` decorator, `set_permutation` context manager, pytest plugin with InMemorySpanExporter and JSONL dump to `.pragma/spans/`.
- `pragma report --json` / `--human`: Post-Implementation Log with per-permutation status and `passed-but-mocked` heuristic. Byte-deterministic JSON output.
- `pragma narrative commit|pr|adr|remediation`: senior-engineer artifact generators backed by Jinja templates.
- CI matrix: sdk-isolated job, full job, report-determinism diff job.
- REQ-005 / M01.S3 declaring the v0.4 contract, dogfooded with one @trace'd Pragma helper.
- `logic_id_schema.md` documenting the shared `pragma.logic_id` / `pragma.permutation` OTel attribute contract.

### Changed

- `pragma init --brownfield` appends `.pragma/spans/` and `.pragma/pytest-junit.xml` to `.gitignore`.
- GitHub Actions workflow split from single job into three.

## [0.3.0] — 2026-04-20

Adds Claude Code hook integration and the full safety battery. An AI
session can no longer edit `src/` while the gate is LOCKED (enforced
at the tool-use boundary, before permission mode), cannot land a
commit that fails any check in the battery, and cannot silently
disable a hook (`.claude/settings.json` has a committed integrity
hash).

### Added

- Four Claude Code hooks wired by `pragma init`: SessionStart,
  PreToolUse, PostToolUse, Stop. Dispatched via `pragma hook <event>`.
- `pragma verify discipline` — AST-based overengineering checks
  (complexity, LoC, depth, single-subclass, single-method util,
  empty __init__, TODO/FIXME sentinels). Shared logic with
  PostToolUse hook.
- `pragma verify commits` — WHY/Co-Authored-By/subject-length shape
  validation across `main..HEAD`.
- `pragma verify integrity` — `.claude/settings.json` hash check.
- `pragma verify all` — runs manifest + gate + integrity.
- `pragma hooks seal/verify/show` — manage the settings integrity hash.
- Full pre-commit battery in the `pragma init` template: gitleaks,
  ruff format + lint, mypy --strict, semgrep, pip-audit, deptry,
  check-added-large-files, pytest.
- `pre-push` stage runs `pragma verify all --ci` — closes the
  `git commit --no-verify` bypass.
- `--ci` flag on `pragma verify all` for strict mode.
- New `PragmaError` subtypes: discipline_violation, commit_shape_violation,
  integrity_mismatch, settings_not_found, hash_not_found,
  unknown_hook_event, hook_input_missing.

### Dogfood

REQ-004 declared in Pragma's own `pragma.yaml` under slice M01.S2;
eight convention tests pin the v0.3 contract.

### Known limitations (by design)

- `pragma-sdk` + OpenTelemetry spans — **v0.4**.
- Post-Implementation Log — **v0.4**.
- `narrative/` module for auto-commits/PRs/ADRs — **v0.4**.
- `pragma init --greenfield` — **v1.0**.

[0.3.0]: https://github.com/Joncik91/pragma/releases/tag/v0.3.0

## [0.2.0] — 2026-04-20

Adds the first real discipline layer: test-first gate. Slice
activation locks `src/`, `pragma unlock` demands failing tests for
every permutation in the active slice, `pragma slice complete`
demands the same tests green. State and audit land under `.pragma/`.

### Added

- Manifest schema v2: optional `milestones:` / `slices:` blocks;
  per-requirement `milestone` / `slice` fields. v1 manifests still
  load verbatim.
- `pragma migrate` — one-shot v1 → v2 upgrade. Idempotent; supports
  `--dry-run`.
- `pragma slice activate|complete|cancel|status` — slice lifecycle
  CLI.
- `pragma unlock` — TDD red-phase gate, driven by the naming
  convention `test_req_<req_id>_<permutation_id>`.
- `pragma verify gate` — state/manifest coherence + red-phase check.
- `pragma verify all` — runs manifest + gate in order; used by
  pre-commit.
- `.pragma/state.json` (gitignored, atomic, flock-guarded) +
  `.pragma/audit.jsonl` (committed, append-only, fsync'd).
- Typed errors for every new failure mode — `state_not_found`,
  `state_schema_error`, `state_locked`, `slice_not_found`,
  `slice_already_active`, `slice_not_active`, `gate_wrong_state`,
  `gate_hash_drift`, `milestone_dep_unshipped`,
  `unlock_missing_tests`, `unlock_test_passing`,
  `complete_tests_failing`.
- Template upgrade: `pragma init` now writes
  `.pre-commit-config.yaml` with `entry: python3 -m pragma verify all`.
- PRAGMA.md template documents the slice workflow + test-naming
  convention.

### Dogfood

Pragma's own repo ran `pragma migrate`, added REQ-003 declaring
v0.2's gate behaviour, and carved slice `M01.S1` for it (cancelled
rather than retro-fitted, since v0.2 code shipped before the
manifest entry).

### Known limitations (by design)

- Claude Code hook integration (SessionStart / PreToolUse /
  PostToolUse / Stop) is **v0.3**.
- `pragma-sdk` and OpenTelemetry spans are **v0.5**.
- No safety battery beyond manifest + gate — **v0.4**.
- `pragma doctor` is still a stub; `--emergency-unlock` lands in
  **v0.4**.

[0.2.0]: https://github.com/Joncik91/pragma/releases/tag/v0.2.0

## [0.1.0] — 2026-04-20

First public release. v0.1 is the Gall-compliant thin slice: a manifest
schema, a lockfile, and a pre-commit hook that refuses to commit when the
two disagree. No gate, no Claude Code hooks, no SDK, no PIL — those land
in v0.2 through v1.0 (see [`docs/roadmap.md`](docs/roadmap.md)).

### Added

- `pragma` CLI (Typer) installable via `pipx install pragma` — machine-
  parseable JSON output by default.
- `pragma init --brownfield` — scaffolds `pragma.yaml`, `PRAGMA.md`, and
  `.pre-commit-config.yaml` in an existing repo. Non-interactive;
  `--force` overwrites, `--name` overrides the project name.
- `pragma spec add-requirement` — appends a requirement with one or more
  permutations to `pragma.yaml`. Handles pipe-in-description safely.
- `pragma freeze` — writes `pragma.lock.json` with a SHA-256 hash over
  canonicalised manifest JSON (`sort_keys=True`, deterministic).
- `pragma verify manifest` — exits non-zero when `pragma.yaml` and
  `pragma.lock.json` disagree, or when the YAML is malformed against the
  schema.
- `pragma doctor` — stub self-check. Always exits 0 in v0.1; reports
  cwd, version, and presence of `pragma.yaml`, `pragma.lock.json`, and
  `.pre-commit-config.yaml`.
- Typed `PragmaError` hierarchy — every error exits with structured JSON
  `{error, message, remediation, context}`.
- Pydantic v2 manifest schema — `extra="forbid"`, frozen models, tuple-
  backed collections for immutability.
- Atomic lockfile writes (`mkstemp` → `fsync` → `os.replace`).
- Jinja2 templates for init scaffolding, shipped inside the wheel via
  `hatchling` `force-include`.
- Pre-commit hook template using `python3 -m pragma verify manifest`
  (portable across Debian / Ubuntu without assuming `pipx` is on
  `PATH`).
- GitHub Actions CI — runs `pragma verify manifest`, `ruff check`,
  `ruff format --check`, `mypy --strict`, and `pytest` on every push and
  PR.
- End-to-end test proving the pre-commit hook blocks a drifted commit.

### Dogfood

Pragma uses its own v0.1 on its own repo: `pragma.yaml` declares
`REQ-001` (CLI JSON contract) and `REQ-002` (manifest / lockfile
roundtrip) with 11 permutations; `.pre-commit-config.yaml` runs
`pragma verify manifest` on every commit.

### Known limitations (by design — shipping in later versions)

- No gate, slice state machine, or `pragma unlock` — **v0.2**.
- No Claude Code hook integration — **v0.3**.
- No full safety battery (gitleaks, semgrep, pip-audit, deptry) — **v0.4**.
- No `pragma-sdk`, `@pragma.trace`, or OpenTelemetry spans — **v0.5**.
- No Post-Implementation Log (PIL) — **v0.6**.
- No `pragma init --greenfield` or milestones / slices hierarchy —
  **v1.0**.

See [`docs/roadmap.md`](docs/roadmap.md) for the full evolutionary path.

[0.1.0]: https://github.com/Joncik91/pragma/releases/tag/v0.1.0
