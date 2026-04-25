#                              Pragma safety battery
#
# The hooks below ship on by default because they work reliably in the
# default Python 3.11+ / pip venv setup and catch high-value issues
# (secrets, lint, format, dependency CVEs, large files, merge markers).
#
# Commented-out entries at the bottom are OPT-IN: they are excellent
# checks in principle but need per-project configuration or have
# known environment-brittleness under pre-commit's isolated venv
# (mypy needs your project's deps pinned in `additional_dependencies`;
# semgrep's env imports pkg_resources which fails on 3.13; deptry
# requires its binary to be present). Uncomment once you're ready to
# configure them for your project.
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.21.2
    hooks:
      - id: gitleaks

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.12
    hooks:
      - id: ruff-format
      - id: ruff

  - repo: https://github.com/pypa/pip-audit
    rev: v2.8.0
    hooks:
      - id: pip-audit
        # GHSA-58qw-9mgm-455v: pip advisory, no published fix at scaffold
        # time. Pip is a transitive tool and your code likely doesn't
        # call the affected path. Drop this `args:` entry when pip
        # ships a fix and re-pin v2.8.x to pick it up.
        args: ["--ignore-vuln=GHSA-58qw-9mgm-455v"]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict

  # Opt-in: strict type check.
  #
  # Two patterns — uncomment whichever suits your project:
  #
  # (a) mirrors-mypy with pre-commit's isolated venv (sandbox-like,
  # needs additional_dependencies for every runtime import):
  # - repo: https://github.com/pre-commit/mirrors-mypy
  #   rev: v1.14.1
  #   hooks:
  #     - id: mypy
  #       args: [--strict]
  #       additional_dependencies: []
  #
  # (b) language: system against your project's .venv (mypy sees real
  # installed packages; matches what CI does). Recommended when your
  # own dev venv has mypy installed alongside the project:
  # - repo: local
  #   hooks:
  #     - id: mypy-local
  #       name: mypy --strict (project venv)
  #       entry: bash -c 'PY="{{ pragma_python_bin }}"; [ -x "$PY" ] || PY=".venv/bin/python3"; [ -x "$PY" ] || PY=python3; exec "$PY" -m mypy --strict src/'
  #       language: system
  #       pass_filenames: false
  #       always_run: true
  #       stages: [pre-commit]
  #
  # Opt-in: semgrep rules. Requires a ruleset (see semgrep.dev).
  # Known-broken on Python 3.13 due to pkg_resources removal; re-enable
  # when your env pins a 3.13-compatible build.
  # - repo: https://github.com/returntocorp/semgrep
  #   rev: v1.99.0
  #   hooks:
  #     - id: semgrep
  #
  # Opt-in: unused / missing / transitive dep detection.
  # - repo: https://github.com/fpgmaas/deptry
  #   rev: 0.22.0
  #   hooks:
  #     - id: deptry

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        # BUG-048 / REQ-040: exit 5 means "no tests collected" — that is a
        # legitimate state for a brownfield repo on the very first
        # adopt-pragma commit, before any test files exist. Suppress 5
        # to 0 so the gate doesn't refuse the adopt commit; every other
        # exit code still propagates.
        entry: bash -c 'PY="{{ pragma_python_bin }}"; [ -x "$PY" ] || PY=".venv/bin/python3"; [ -x "$PY" ] || PY=python3; "$PY" -m pytest; rc=$?; [ "$rc" -eq 5 ] && exit 0; exit "$rc"'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]

      # Each entry prefers the repo-local .venv/bin/python3 so `git push`
      # from a non-activated shell still resolves pragma. Falls back to PATH
      # python3 (pipx installs or system-wide pragma).
      - id: pragma-verify-pre-commit
        name: pragma verify all
        entry: bash -c 'PY="{{ pragma_python_bin }}"; [ -x "$PY" ] || PY=".venv/bin/python3"; [ -x "$PY" ] || PY=python3; exec "$PY" -m pragma verify all'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]

      - id: pragma-verify-commit-msg
        name: pragma verify message (commit-msg)
        entry: bash -c 'PY="{{ pragma_python_bin }}"; [ -x "$PY" ] || PY=".venv/bin/python3"; [ -x "$PY" ] || PY=python3; exec "$PY" -m pragma verify message "$1"' --
        language: system
        stages: [commit-msg]

      - id: pragma-verify-pre-push
        name: pragma verify all (pre-push)
        entry: bash -c 'PY="{{ pragma_python_bin }}"; [ -x "$PY" ] || PY=".venv/bin/python3"; [ -x "$PY" ] || PY=python3; exec "$PY" -m pragma verify all --ci'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]

      - id: pragma-verify-commits-pre-push
        name: pragma verify commits (pre-push range)
        entry: bash -c 'PY="{{ pragma_python_bin }}"; [ -x "$PY" ] || PY=".venv/bin/python3"; [ -x "$PY" ] || PY=python3; exec "$PY" -m pragma verify commits --base=$(git merge-base HEAD origin/main 2>/dev/null || echo HEAD~1)'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]
