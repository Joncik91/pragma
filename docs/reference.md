# Pragma reference

Alphabetical reference for every CLI command, manifest field, audit
event, and hook. For *why* any of this exists, see
[`concepts.md`](concepts.md). For *how to drive it end-to-end*, see
[`usage.md`](usage.md).

All Pragma commands exit `0` on success with a JSON `{"ok": true, ...}`
payload, or non-zero with a JSON `{"error": "code", "message": "...",
"remediation": "...", "context": {...}}` payload on failure.
`pragma doctor` is the one intentional exception — it always exits
`0` and puts any findings under `diagnostics`.

## CLI — quick index

| Command | Purpose |
|---|---|
| `pragma init` | Scaffold manifest + pre-commit + hooks. |
| `pragma freeze` | Regenerate `pragma.lock.json` from `pragma.yaml`. |
| `pragma spec add-requirement` | Append one requirement to `pragma.yaml`. |
| `pragma spec plan-greenfield` | Bootstrap a greenfield manifest from a problem statement. |
| `pragma slice activate` | Lock the gate on the named slice. |
| `pragma slice complete` | Ship the slice (requires green tests). |
| `pragma slice cancel` | Abandon the active slice. |
| `pragma slice status` | Print the gate + slice state as JSON. |
| `pragma unlock` | Flip gate LOCKED → UNLOCKED (requires red tests). |
| `pragma verify manifest` | Check manifest ↔ lock agreement. |
| `pragma verify gate` | Check gate state is coherent with manifest. |
| `pragma verify discipline` | Check AST overengineering budgets. |
| `pragma verify integrity` | Check `.claude/settings.json` hash. |
| `pragma verify commits` | Check commit message shape on a range. |
| `pragma verify message` | Check one commit-msg file (commit-msg hook). |
| `pragma verify all` | Run every verifier; fail on any. |
| `pragma report --json` | Emit deterministic JSON from spans + JUnit. |
| `pragma report --human` | Emit the Markdown Post-Implementation Log. |
| `pragma narrative commit` | Draft a commit message from the active slice. |
| `pragma narrative pr` | Draft a PR description. |
| `pragma narrative adr` | Draft an ADR. |
| `pragma narrative remediation` | Draft remediation copy for a doctor diagnostic. |
| `pragma doctor` | Diagnostic + recovery JSON. |
| `pragma doctor --emergency-unlock` | Reset gate to neutral (audit trail). |
| `pragma doctor --clean-spans` | Prune `.pragma/spans/` by retention. |
| `pragma hook <event>` | Dispatch a Claude Code hook event (used by `.claude/settings.json`). |
| `pragma hooks seal` | Record hash of `.claude/settings.json`. |
| `pragma hooks verify` | Compare current hash to seal. |
| `pragma hooks show` | Print the current sealed hash. |
| `pragma migrate` | Upgrade `pragma.yaml` from v1 schema to v2. |

## Commands — details

### `pragma init`

Scaffolds the files Pragma needs. Two modes:

| Flag | What it does |
|---|---|
| `--brownfield` | In-place on an existing repo. Writes `pragma.yaml` (empty requirements), `pragma.lock.json`, `.pre-commit-config.yaml`, `.claude/settings.json`, `.claude/settings.hash`. Leaves your code untouched. |
| `--greenfield` | Full project scaffold. Adds `src/<name>/`, `tests/`, `pyproject.toml`, `README.md`, `.gitignore`, `pytest.ini`, plus every brownfield artifact. |
| `--name NAME` | Project name. Defaults to the current directory name. |
| `--language python` | Target language for the seed manifest. Only `python` supported in v1.0. |
| `--force` | Overwrite existing files if present. |

### `pragma freeze`

Reads `pragma.yaml`, validates against the schema, computes a
deterministic SHA-256 of the canonical form, writes
`pragma.lock.json`. Atomic (tempfile + rename). Idempotent — running
twice on an unchanged manifest produces byte-identical locks.

### `pragma spec add-requirement`

Appends one requirement. Errors on duplicate ID. Flags:

| Flag | Required | Notes |
|---|---|---|
| `--id REQ-NNN` | yes | Unique within the manifest. |
| `--title TEXT` | yes | One line. |
| `--description TEXT` | yes | Longer prose; multi-line supported via shell escapes. |
| `--touches PATH` | yes | File this requirement touches. Repeat for multiple files. |
| `--permutation 'id\|description\|verdict'` | yes | Pipe-delimited. `verdict` is `success` or `reject`. Repeat for each permutation. |
| `--milestone MNN` | no | Assigns to a milestone. |
| `--slice MNN.SN` | no | Assigns to a slice under that milestone. |

### `pragma spec plan-greenfield`

Bootstraps an empty greenfield manifest from a free-text problem
statement. Reads the statement, calls an AI to extract candidate
requirements with permutations, writes them to `pragma.yaml` for you
to review and refine.

| Flag | Notes |
|---|---|
| `--from PATH` | Path to the problem statement file (typically `docs/problem.md`). |
| `--model MODEL` | Override the default AI model. |
| `--dry-run` | Print proposed requirements without writing. |

### `pragma slice <subcommand>`

- `pragma slice activate SLICE_ID [--force]` — flips the gate LOCKED on the named slice. `--force` switches even if another slice is active.
- `pragma slice complete [--skip-tests]` — requires every permutation's test to be green. `--skip-tests` is the bootstrap-only bypass; using it emits a warning in the audit trail.
- `pragma slice cancel` — abandons the slice. Resets gate to neutral, writes `slice_cancelled` audit event.
- `pragma slice status` — prints current active slice, gate, and slice history as JSON.

### `pragma unlock`

Flips gate LOCKED → UNLOCKED. Refused unless every permutation in the
active slice has a *failing* test named per convention
(`test_req_<id>_<permutation>`). No flags.

### `pragma verify <subcommand>`

Every subcommand exits `0` on pass, non-zero with a JSON error on fail.

- `manifest` — `pragma.yaml` and `pragma.lock.json` agree.
- `gate` — `.pragma/state.json` is coherent with the manifest hash.
- `discipline` — AST overengineering budgets (cyclomatic complexity, file size, function count) are respected across `src/`.
- `integrity` — `.claude/settings.json` matches the sealed hash.
- `commits [--base REF]` — commit messages between `REF` and `HEAD` pass shape.
- `message PATH` — commit-msg hook form; validates one message file.
- `all [--ci]` — runs manifest, gate, integrity, discipline, commits. `--ci` tightens rules for CI environments.

### `pragma report`

| Flag | Notes |
|---|---|
| `--json` | Emit deterministic JSON to stdout. |
| `--human` | Emit Markdown PIL to stdout. |
| `--output PATH` | Write to file instead of stdout. |

Reads `.pragma/pytest-junit.xml` (pytest junit output) and
`.pragma/spans/*.jsonl` (OpenTelemetry span dumps from
`pragma-sdk`'s pytest plugin). Both artifacts are produced
automatically by `pragma slice complete`, `pragma unlock`, and
`pragma verify gate` — no separate `pytest` invocation needed. If
either is absent when `pragma report` runs, the output includes a
`## Diagnostics` banner naming the missing artifact.

### `pragma narrative <subcommand>`

- `commit` — draft a commit message for the active slice.
- `pr` — draft a PR description.
- `adr` — draft an Architecture Decision Record.
- `remediation CODE` — draft a remediation narrative for a doctor diagnostic code.

All read the manifest, the active slice, and the latest PIL.

### `pragma doctor`

Diagnostic command. Always exits `0` in standard mode. Three modes:

| Mode | Flags | What it does |
|---|---|---|
| Default | *(none)* | Prints install + project state + `diagnostics[]` JSON. Includes `spans_count` and `spans_bytes`. |
| Emergency unlock | `--emergency-unlock --reason "..."` | Resets `.pragma/state.json` to neutral, appends `emergency_unlock` audit event. Requires non-empty reason. |
| Clean spans | `--clean-spans [--keep-runs N] [--keep-days D] [--dry-run]` | Prunes `.pragma/spans/*.jsonl`. |

`--clean-spans` retention precedence: CLI flag > `spans_retention:` in
manifest > default (`keep_runs=50`).

### `pragma hook EVENT`

Internal — invoked by `.claude/settings.json`. One of:
`session-start`, `pre-tool-use`, `post-tool-use`, `stop`. Reads stdin,
writes stdout. Not usually called by hand.

### `pragma hooks <subcommand>`

- `seal` — compute hash of `.claude/settings.json`, write to `.pragma/claude-settings.hash`.
- `verify` — compare current hash to sealed hash. Exit non-zero on drift.
- `show` — print the current sealed hash.

### `pragma migrate`

Upgrades `pragma.yaml` from v1 (flat requirements list) to v2
(requirements + milestones + slices). Idempotent.

| Flag | Notes |
|---|---|
| `--dry-run` | Print the proposed new manifest without writing. |

## Manifest — `pragma.yaml`

Top-level keys:

```yaml
version: "2"                  # schema version; "1" supported read-only via pragma migrate
project:
  name: string                # required
  mode: brownfield|greenfield # required
  language: python            # v1.0: python only
  source_root: path           # required, relative
  tests_root: path            # required, relative
vision: string                # optional; shown in PIL headers
requirements: [Requirement]   # the declared behaviour surface
milestones: [Milestone]       # v2 only; groups slices of requirements
spans_retention:              # optional; default keep_runs=50
  keep_runs: int              # optional, >=1
  keep_days: number           # optional, >0
```

### Requirement

```yaml
- id: REQ-NNN                 # unique, required
  title: string               # one-line
  description: string         # multi-line prose
  touches: [path]             # files this requirement touches
  permutations:
    - id: string              # unique within the requirement
      description: string
      expected: success|reject
  milestone: MNN              # optional; v2 schema
  slice: MNN.SN               # optional; v2 schema
```

### Milestone (v2)

```yaml
- id: MNN
  title: string
  description: string
  depends_on: [MNN]           # cycle detection enforced
  slices:
    - id: MNN.SN
      title: string
      description: string
      requirements: [REQ-NNN] # IDs of requirements assigned to this slice
```

### `spans_retention`

See [`doctor.md` § Span retention](doctor.md#span-retention-clean-spans)
for operational guidance. Syntax:

```yaml
spans_retention:
  keep_runs: 50               # keep N newest files by mtime
  keep_days: 30               # keep files within D days
```

Both optional. When both are set, a file is kept when it satisfies
*either* rule (union).

## Audit events — `.pragma/audit.jsonl`

Every line is `{"ts", "event", "actor", "slice", "from_state",
"to_state", "reason", "context"}`. Events emitted:

| Event | Actor | When |
|---|---|---|
| `slice_activated` | `cli` | `pragma slice activate`. |
| `slice_completed` | `cli` | `pragma slice complete` succeeds. |
| `slice_cancelled` | `cli` | `pragma slice cancel`. |
| `unlocked` | `cli` | `pragma unlock` flips gate. |
| `emergency_unlock` | `doctor` | `pragma doctor --emergency-unlock`. |
| `spans_cleaned` | `doctor` | `pragma doctor --clean-spans` (non-dry). |
| `hook_crash` | `hook` | A Claude Code hook crashed; written to `.pragma/hook-crash.jsonl` (KI-6: separate file so audit stays clean). |

## Hooks — `.claude/settings.json`

| Event | Entry | Denies when |
|---|---|---|
| `SessionStart` | `pragma hook session-start` | — (emits `additionalContext`, never denies) |
| `PreToolUse` | `pragma hook pre-tool-use` | Edit/Write under `src/` while gate is LOCKED or writing outside declared `touches`. |
| `PostToolUse` | `pragma hook post-tool-use` | Discipline violation on just-edited files. |
| `Stop` | `pragma hook stop` | `pragma verify all` fails at turn end. |

Hooks are sealed: `pragma hooks seal` writes a hash to
`.pragma/claude-settings.hash` and `pragma verify integrity` refuses
drift. Tampering with `settings.json` flips integrity red.

## Files Pragma writes

| Path | Purpose | Committed? |
|---|---|---|
| `pragma.yaml` | Manifest. Human-written. | yes |
| `pragma.lock.json` | Fingerprint of canonical manifest. | yes |
| `.pre-commit-config.yaml` | Battery + Pragma gate. | yes |
| `.claude/settings.json` | Claude Code hook wiring. | yes |
| `PRAGMA.md` | Short project-level primer. | yes |
| `.pragma/audit.jsonl` | Append-only transition log. | yes |
| `.pragma/state.json` | Current gate + slice state. | **no** (machine-local) |
| `.pragma/state.json.lock` | Flock for atomic state writes. | no |
| `.pragma/claude-settings.hash` | Integrity seal. | yes |
| `.pragma/spans/*.jsonl` | Per-run trace dumps. | no |
| `.pragma/pytest-junit.xml` | Per-run pytest results. | no |
| `.pragma/hook-crash.jsonl` | Hook-crash forensics. | no |

## Error codes

Every failure returns `{"error": "<code>", ...}`. Common ones:

| Code | Meaning |
|---|---|
| `manifest_not_found` | No `pragma.yaml` in cwd. |
| `manifest_schema_error` | YAML valid but doesn't match schema. |
| `hash_mismatch` | `pragma.yaml` and `pragma.lock.json` disagree. |
| `requirement_unassigned` | Requirement lacks `milestone` or `slice`. |
| `unlock_requires_red_tests` | Tried to unlock with missing/green tests. |
| `complete_tests_failing` | Tried to complete with failing tests. |
| `slice_already_active` | `slice activate` without `--force`. |
| `gate_hash_drift` | State references an older manifest hash. |
| `integrity_hash_mismatch` | `.claude/settings.json` tampered with. |
| `commit_shape_violation` | Message lacks WHY: / exceeds subject length / missing trailer. |
| `discipline_budget_exceeded` | AST violation (complexity, size, count). |
| `emergency_unlock_refused` | Emergency unlock on a healthy repo. |
| `reason_required` | `--reason` empty or whitespace. |

Every error ships with a `remediation` string written to be
copy-pasteable.

## Issue ID conventions

Pragma's manifest only formally models `REQ-NNN`. The other prefixes
that appear in this repo's commits, CHANGELOG, and roadmap are
internal conventions, not enforced by the gate.

| Prefix | Meaning | Where it lives |
|---|---|---|
| `REQ-NNN` | A requirement declared in `pragma.yaml`. Has permutations the gate enforces. **Authoritative.** | `requirements:` array in the manifest |
| `BUG-NNN` | A defect the team filed against a fix. Often closes a `REQ-NNN`; sometimes bundled into one. | Commit messages, CHANGELOG, this repo's issue tracker |
| `KI-NN` | "Known Issue" — a flaw acknowledged but not yet fixed. May or may not become a `BUG-NNN` later. | CHANGELOG, roadmap, occasional code comments |

Numbering is monotonic per prefix and not reused. A `BUG-NNN` cited in
a CHANGELOG entry should also appear in the commit message that fixed
it; the commit message in turn names the `REQ-NNN` that closes it (if
any), so a reader can trace fix → requirement → manifest permutation
→ test → span.

## See also

- [`concepts.md`](concepts.md) — mental model and why.
- [`usage.md`](usage.md) — step-by-step walkthrough.
- [`doctor.md`](doctor.md) — diagnostic codes explained.
- [`migrate.md`](migrate.md) — schema v1 → v2 details.
- [`roadmap.md`](roadmap.md) — shipped vs planned.
