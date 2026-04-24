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

## Making the Post-Implementation Log useful

After your first slice ships, `pragma report --human` will show every
permutation as `missing`. That's not a bug — the PIL is built from
OpenTelemetry spans emitted at runtime, not from "tests passed." A
permutation counts as *exercised* only when the real code path ran
under a `@trace` decorator with an active `set_permutation(...)` baggage
context. Otherwise the PIL flags it `missing` or `possibly-mocked`,
which is the whole point: a passing test that never touched the real
implementation doesn't prove anything.

To make the PIL show real coverage on your own code:

```python
# src/greeter.py
from pragma_sdk import trace

@trace("REQ-001")
def greet(name: str) -> str:
    if not name:
        raise ValueError("name must be non-empty")
    return f"Hello, {name}!"
```

```python
# tests/test_req_001_greeter.py
import pytest
from pragma_sdk import set_permutation
from greeter import greet

def test_req_001_valid_name() -> None:
    with set_permutation("valid_name"):
        assert greet("Ada") == "Hello, Ada!"

def test_req_001_empty_name_rejected() -> None:
    with set_permutation("empty_name_rejected"):
        with pytest.raises(ValueError):
            greet("")
```

After the next `pytest` + `pragma slice complete`, rerun
`pragma report --human` — the two permutations will show as `ok`
instead of `missing`. That's a trustworthy summary: the real code
ran, the real permutation was attested, the real test asserted.
