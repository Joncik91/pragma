repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.2
    hooks:
      - id: gitleaks

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.6
    hooks:
      - id: ruff-format
      - id: ruff

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.14.1
    hooks:
      - id: mypy
        args: [--strict]

  - repo: https://github.com/returntocorp/semgrep
    rev: v1.99.0
    hooks:
      - id: semgrep

  - repo: https://github.com/pypa/pip-audit
    rev: v2.8.0
    hooks:
      - id: pip-audit

  - repo: https://github.com/fpgmaas/deptry
    rev: 0.22.0
    hooks:
      - id: deptry

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: python3 -m pytest
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]

      # Each entry prefers the repo-local .venv/bin/python3 so `git push`
      # from a non-activated shell still resolves pragma. Falls back to PATH
      # python3 (pipx installs or system-wide pragma).
      - id: pragma-verify-pre-commit
        name: pragma verify all
        entry: bash -c 'PY=".venv/bin/python3"; [ -x "$PY" ] || PY=python3; exec "$PY" -m pragma verify all'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]

      - id: pragma-verify-commit-msg
        name: pragma verify message (commit-msg)
        entry: bash -c 'PY=".venv/bin/python3"; [ -x "$PY" ] || PY=python3; exec "$PY" -m pragma verify message "$1"' --
        language: system
        stages: [commit-msg]

      - id: pragma-verify-pre-push
        name: pragma verify all (pre-push)
        entry: bash -c 'PY=".venv/bin/python3"; [ -x "$PY" ] || PY=python3; exec "$PY" -m pragma verify all --ci'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]

      - id: pragma-verify-commits-pre-push
        name: pragma verify commits (pre-push range)
        entry: bash -c 'PY=".venv/bin/python3"; [ -x "$PY" ] || PY=python3; exec "$PY" -m pragma verify commits --base=$(git merge-base HEAD origin/main 2>/dev/null || echo HEAD~1)'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]
