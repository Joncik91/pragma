---
name: pragma
description: Use whenever the user describes a software feature, fix, or change in plain English. Drives Pragma's manifest+gate so every code change goes through a declared slice with a test-first proof. Required before editing src/ or tests/ in any Pragma-aware project.
---

# Pragma — senior engineer on rails

You are operating in a project that uses Pragma, a test-first gate.
The gate enforces: **declare → red test → unlock → implement → green
test → complete → commit**. Your job is to drive this loop on the
user's behalf so they only type intent, never gate ceremony.

## When the user describes a feature

If the project has **no `pragma.yaml`** yet:

```bash
pragma start "<the user's intent verbatim>"
```

This auto-detects greenfield vs brownfield, scaffolds the manifest,
plans the slice, and lands at `gate=LOCKED` on `M01.S1` (greenfield)
or `M00.S0` (brownfield). Read the JSON output to confirm `mode`,
`slice`, and `gate`.

If the project **already has `pragma.yaml`**:

1. Run `pragma slice status` to see the current state.
2. If no slice is active, add a requirement:
   ```bash
   pragma spec add-requirement --id REQ-NNN \
     --title "<feature>" \
     --description "<one paragraph>" \
     --touches src/<file>.py \
     --permutation '<perm_id>|<description>|success'
   pragma freeze
   pragma slice activate <slice_id>
   ```
3. If a slice is already active, work that slice first.

## The gate loop

Once `gate=LOCKED`, the loop is fixed:

| Step | Command | When |
|---|---|---|
| Write red test(s) | edit `tests/test_req_<id>_<perm_id>.py` | One per declared permutation. Test must wrap body in `with set_permutation('<perm_id>'):`. |
| Unlock | `pragma unlock` | When every required test exists and asserts something not yet implemented. Pragma will reject if any test is already passing. |
| Implement | edit `src/<file>.py` | Add `@trace("REQ-NNN")` to the function the test exercises. |
| Complete | `pragma slice complete` | When all slice tests are green. |
| Commit | `pragma narrative commit --subject "..."` then `git commit -F-` | Drafts a gate-conformant message (WHY + Co-Authored-By). |

## Hard rules

- **Never edit `pragma.yaml` or `pragma.lock.json` directly.** Use `pragma spec add-requirement`, `pragma freeze`. The gate verifies the lock matches the manifest hash; direct edits will be refused on commit.
- **Never bypass the gate.** `pragma unlock` requires red tests by design. The only audited escape hatch is `pragma unlock --skip-tests --reason "..."`, used only for brownfield retroactive imports where production code already exists. Do not use this when the user is asking for new functionality.
- **Never edit `.pragma/state.json` or `.pragma/audit.jsonl` by hand.** State is flock-guarded; audit is append-only and fsync'd.
- **Test names follow convention**: `def test_req_<id>_<permutation_id>():`. Pragma rejects unlock if a permutation has no matching test.

## When the user asks for a status check

Run `pragma slice status` and `pragma report --human` and read both
back to the user in plain English. Don't dump JSON — the PIL is the
proof; explain what was *exercised* vs *flagged* per permutation.

## When something goes wrong

- `slice_not_found` → `pragma slice status` to list declared slice ids.
- `manifest_hash_mismatch` → user edited `pragma.yaml`. Run `pragma freeze`, stage both files, retry.
- `commit_shape_violation` → re-draft via `pragma narrative commit` and re-commit.
- `unlock_test_passing` → either remove the implementation (TDD violation) or remove the permutation. Don't reach for `--skip-tests`.

## Why this matters

The user's contract with Pragma is: every diff carries proof of what
it claimed to build. Your job is to make that contract invisible —
the user types "build me X", and you handle every step. The Post-
Implementation Log (`pragma report --human`) is what they read, not
the diff.
