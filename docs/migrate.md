# `pragma migrate`

This page explains how the `pragma.yaml` schema version works and what
to do when you pull a repo whose manifest is on an older schema. Read
this if `pragma verify all` fails with a schema-version error or if
`pragma.yaml` starts with `version: "1"`.

## Schema versions

Pragma's manifest schema is versioned by the `version:` key at the top
of `pragma.yaml`. Only two versions exist:

- **v1** — the original flat schema. Shipped in Pragma v0.1 only.
  `requirements:` is a flat list; no `milestones:` or `slices:`. A v1
  manifest has `version: "1"`.
- **v2** — the milestone + slice schema. Shipped in Pragma v0.2 and
  every release since. The root carries `version: "2"`, a
  `milestones:` list, and every requirement names its `milestone:` and
  `slice:`. **v2 is current as of Pragma v1.0.**

Pragma v1.0 understands both. `pragma verify manifest` rejects any
other `version:` value. The only supported migration path is v1 → v2
(forward). There is no v2 → v1 downgrade.

## Running `pragma migrate`

```shell
pragma migrate
```

Expected output on a v1 manifest:

```json
{"from_version":"1","manifest_hash":"sha256:...","migrated":true,"ok":true,"slices_created":["M00.S0"],"to_version":"2"}
```

Expected output on a v2 manifest (no-op, idempotent):

```json
{"migrated":false,"ok":true,"reason":"already_v2"}
```

Dry-run mode prints what it would write without touching disk:

```shell
pragma migrate --dry-run
```

What the migrator does:

1. Reads `pragma.yaml` and asserts `version: "1"`.
2. Creates an implicit milestone `M00` titled *"Implicit brownfield
   milestone"* with a single slice `M00.S0`.
3. Reassigns every existing requirement to `milestone: M00` and
   `slice: M00.S0` so the flat list is preserved.
4. Bumps `version:` to `"2"`.
5. Writes `pragma.yaml` and re-freezes `pragma.lock.json`.

You can rename `M00` / `M00.S0` afterward once you carve real
milestones — the migrator picks the sentinel name so it's obvious
which milestone was auto-generated.

After migration:

```shell
pragma verify all
git add pragma.yaml pragma.lock.json
git commit -m "chore: migrate pragma manifest v1 to v2"
```

## What to do if migration fails

### Unknown schema version

```json
{"code":"manifest_schema_error","message":"unexpected manifest version '3'; only v1 can be migrated to v2",...}
```

Your `pragma.yaml` declares a `version:` value Pragma doesn't know. Two
possibilities:

- Typo in the `version:` field. Open `pragma.yaml` and set it back to
  `"1"` or `"2"`.
- The manifest was produced by a newer Pragma than the one you have
  installed. Upgrade Pragma: `pipx upgrade pragma` (or `pip install
  --upgrade pragma` in a venv).

### Corrupt YAML

```json
{"code":"manifest_schema_error","message":"pragma.yaml is not valid YAML: ..."}
```

The YAML parser failed before the migrator could run. Usually a merge
conflict marker (`<<<<<<<`, `=======`, `>>>>>>>`) or a stray tab. Open
`pragma.yaml`, fix the syntax, re-run `pragma migrate`.

### Duplicate requirement IDs

```json
{"code":"manifest_schema_error","message":"migrated manifest failed v2 schema validation: ..."}
```

If the v1 manifest already had duplicate `id:` values, the v2 schema
(which is stricter) rejects the upgraded dict. Open `pragma.yaml`, fix
the duplicates by hand, re-run `pragma migrate`.

### Missing `pragma.yaml`

```json
{"code":"manifest_not_found","remediation":"Run `pragma init --brownfield` first."}
```

You ran `pragma migrate` in a directory that isn't a Pragma project.
Cd into the repo root and try again.

## See also

- [`usage.md`](usage.md) — full brownfield + greenfield flows.
- [`doctor.md`](doctor.md) — diagnostic codes and recovery steps.
