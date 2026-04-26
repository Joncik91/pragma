# Pre-commit hook

If you don't want `pragma init-precommit` to manage the file, drop
this into your existing `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: pragma
        name: pragma verify tests
        entry: pragma verify tests
        language: system
        files: '(^|/)test_.*\.py$|/tests/.*\.py$'
```

Then:

```shell
pre-commit install
```

Every commit that touches a test file matching the regex above
runs the classifier; gamed tests block the commit.
