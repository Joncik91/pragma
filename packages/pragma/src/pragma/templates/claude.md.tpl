# Claude Code primer for {{ project_name }}

This repository uses **Pragma** — a senior-engineer-on-rails framework that
blocks shipping code without a failing test per permutation.

## The loop

1. `pragma spec add-requirement ...` — declare a requirement in pragma.yaml.
2. `pragma freeze` — lock the manifest hash.
3. `pragma slice activate M01.S1` — tell Pragma which slice you're working on.
4. Write failing tests for every permutation.
5. `pragma unlock` — proves the tests are red; unlocks src/ edits.
6. Make tests pass.
7. Commit. Pre-commit hooks run `pragma verify all` before the commit lands.

## First run

```bash
pragma spec plan-greenfield --from docs/problem.md
$EDITOR pragma.yaml
pragma spec add-requirement --id REQ-001 --title "..." ...
pragma freeze
pragma slice activate M01.S1
```

Read `docs/doctor.md` if anything gets stuck.
