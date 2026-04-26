---
name: pragma
description: Pragma rejects gamed tests on Edit/Write of *.py files in tests/ or named test_*.py. Avoid these patterns when writing tests.
---

# Pragma — anti-gaming rules for tests

Pragma is watching every test file you Edit/Write. It will block the
tool call when it sees:

- **tautological asserts** — `assert True`, `assert 1 == 1`, `assert x == x`.
- **mock-the-target** — `mock.patch("auth.login.login")` *inside* a test that imports and claims to test `auth.login.login`. Mock the dependencies, not the symbol under test.
- **name/body mismatch** — a test named `test_*_rejects_*`, `_raises_*`, `_refuses_*`, or `_denies_*` must use `with pytest.raises(...):` (or an `except` block). Asserting on a return value contradicts the name.

To pass: import the production symbol, call it with realistic inputs,
assert on the actual return value (or the raised exception type). If
you're tempted to mock the function under test or write `assert True`
to make a test pass — stop and rewrite the test to verify behaviour.

`weak` verdicts (`assert x is not None` when an exact value was
expected) are warnings, not blocks. Tighten when the spec is clear.
