# `pragma doctor`

This page tells you how to read the output of `pragma doctor` and what
to type to fix each diagnostic. Read this when pre-commit blocks you, a
Pragma command fails, or you've pulled a repo that looks broken.

## What doctor tells you

```shell
pragma doctor
```

Always exits zero in standard mode. Writes a single-line JSON payload
to stdout. Shape:

```json
{
  "ok": true,
  "pragma_version": "1.0.5",
  "cwd": "/path/to/repo",
  "manifest_exists": true,
  "lock_exists": true,
  "pragma_dir_exists": true,
  "pre_commit_config_exists": true,
  "claude_settings_exists": true,
  "spans_count": 42,
  "spans_bytes": 180224,
  "diagnostics": [
    {
      "code": "stale_state",
      "severity": "warn",
      "message": "...",
      "remediation": "...",
      "context": {"state_manifest_hash": "...", "lock_manifest_hash": "..."}
    }
  ]
}
```

Each diagnostic has four fields:

- `code` — stable identifier. The list below documents every code.
- `severity` — `fatal` or `warn`. If any `fatal` diagnostic fires, it is
  the only one returned (the fatal branch short-circuits the
  classifier).
- `message` — one-line human summary.
- `remediation` — the exact command you should run next.
- `context` — key facts the remediation might need (paths, hashes).

When there are no problems, `diagnostics` is an empty list.

## Diagnostic codes

### `no_manifest` (fatal)

No `pragma.yaml` in the current directory. Pragma can't do anything
without a manifest.

Fix — brownfield:

```shell
pragma init --brownfield --name <your-project-name>
```

Fix — greenfield:

```shell
pragma init --greenfield --name <your-project-name>
```

### `no_lock` (fatal)

`pragma.yaml` exists but `pragma.lock.json` is missing. The hash can't
be checked against anything. This usually means someone deleted the
lock, or you haven't frozen yet after an `init --greenfield`.

Fix:

```shell
pragma freeze
```

### `hash_mismatch` (fatal)

`pragma.yaml` has been edited but `pragma freeze` hasn't been run, OR
`pragma.yaml` is unreadable and the canonical hash couldn't be
computed.

Fix — if the edit was intentional:

```shell
pragma freeze
```

Fix — if the edit was a mistake:

```shell
git restore pragma.yaml pragma.lock.json
```

### `lockfile_unparseable` (fatal)

`pragma.lock.json` is not valid JSON, or it lacks the `manifest_hash`
field. Usually a merge conflict marker left in the file.

Fix:

```shell
pragma freeze
```

If `pragma freeze` itself fails, open `pragma.lock.json` in an editor,
delete anything that looks like `<<<<<<<` / `=======` / `>>>>>>>`, and
re-run `pragma freeze`.

### `no_pragma_dir` (warn)

`.pragma/` is missing. The audit log (`.pragma/audit.jsonl`) and gate
state (`.pragma/state.json`) have nowhere to land.

Fix:

```shell
pragma freeze
```

`pragma freeze` recreates the directory as a side effect.

### `stale_state` (warn)

`.pragma/state.json` references a `manifest_hash` that no longer
matches the lockfile. This happens when someone edits `pragma.yaml` +
runs `pragma freeze` while a slice is active — the state is still
pointing at the old manifest.

Fix:

```shell
pragma freeze
pragma slice activate <your-active-slice-id>
```

The `activate` call re-binds the slice to the new manifest hash. Skip
the second command if no slice needs to stay active.

### `claude_settings_mismatch` (warn)

`.claude/settings.json` has been modified but
`.pragma/claude-settings.hash` is stale. Pragma can't vouch that the
Claude Code permission profile hasn't been tampered with.

Fix — review the diff first:

```shell
git diff .claude/settings.json
```

If the change is legitimate, restamp:

```shell
pragma init --force
```

`--force` rewrites the hash file against the current settings. Never
run it without reading the diff first — an attacker could have widened
the permission surface.

### `audit_orphan` (warn)

`.pragma/audit.jsonl` has entries but `.pragma/state.json` is either
missing or has no slices. Someone deleted state but left the audit
trail. The repo is in a half-reset state.

Fix:

```shell
pragma doctor --emergency-unlock --reason "recovered from audit orphan"
```

This resets state to neutral and appends an `emergency_unlock` entry
to the audit log. See below.

## Emergency unlock

```shell
pragma doctor --emergency-unlock --reason "<why you're doing this>"
```

Use when the gate is wedged and normal commands can't recover — for
example, `pragma slice complete` refuses because a permutation test
vanished from disk, and you've decided to abandon the slice rather
than fix it forward.

What it does:

- Resets `.pragma/state.json` to the neutral shape (`active_slice:
  null`, `gate: null`, `manifest_hash` rebound to the current
  lockfile). Writes atomically.
- Appends one line to `.pragma/audit.jsonl` with `event:
  emergency_unlock`, `actor: doctor`, the previous `active_slice`, the
  previous `gate`, and your verbatim `reason`.
- Exits `0` and prints `{"ok": true, "action": "emergency_unlock",
  ...}`.

What it refuses:

- Empty or whitespace-only `--reason`. The reason is the audit trail;
  it is not optional.
- A repo that is already neutral (no active slice, no gate). Running
  emergency-unlock on a healthy repo would be audit spam, so doctor
  refuses and exits `1`.

Why `--reason` is mandatory: emergency unlock bypasses the "every
permutation green before slice complete" invariant. Six months from
now someone reading `.pragma/audit.jsonl` needs to know whether this
was legitimate recovery or someone shortcutting the process. The
reason is the only way to tell.

Example:

```shell
pragma doctor --emergency-unlock --reason "abandoning M01.S3 — requirement REQ-007 was mis-scoped, re-planning in M01.S4"
```

After emergency unlock you are back at the start of the slice flow:
`pragma slice activate <id>` → red tests → `pragma unlock` → green →
`pragma slice complete`.

## Span retention (`--clean-spans`)

Every pytest run writes a uniquely-named JSONL under
`.pragma/spans/`. Those files are the raw input to
`pragma report` and to the PIL narrative — evidence, not cache — but
they accumulate linearly with test runs. On a long-running project
the directory starts slowing `ls`, `pragma report`, and (eventually)
disk.

`pragma doctor` surfaces accumulation in standard mode:
`spans_count` and `spans_bytes` are always in the payload. When
they get uncomfortable, prune with:

```shell
pragma doctor --clean-spans                 # default: keep_runs=50
pragma doctor --clean-spans --keep-runs 20
pragma doctor --clean-spans --keep-days 30
pragma doctor --clean-spans --keep-runs 50 --keep-days 30   # union: either rule keeps
pragma doctor --clean-spans --dry-run       # preview, no fs change
```

`--keep-runs N` keeps the N newest files by mtime. `--keep-days D`
keeps files whose mtime is within D days. Both together take the
union — a file is kept when it satisfies *either* rule (the more
lenient wins).

Prefer writing your retention policy once in `pragma.yaml` so the
CLI call stays short:

```yaml
spans_retention:
  keep_runs: 50
  keep_days: 30
```

CLI flags override the manifest block for one invocation.

Every non-dry `--clean-spans` run appends one line to
`.pragma/audit.jsonl` with event `spans_cleaned`, `files_removed`,
`bytes_freed`, and the `strategy` used. You still have the
forensic record of what rolled off, even though the span files
themselves are gone.

Defaults: `keep_runs=50` when neither the CLI flag nor the manifest
block is present. Nothing is auto-pruned — `pragma doctor
--clean-spans` runs on demand, never as a side effect of another
command.
