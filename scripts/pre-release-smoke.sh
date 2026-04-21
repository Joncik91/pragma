#!/usr/bin/env bash
#
# scripts/pre-release-smoke.sh
#
# Pre-tag smoke test that mirrors what GitHub Actions runs. v1.0.2's
# smoke test stopped at `pragma verify all` after init, which missed
# BUG-013 (fresh-init repo, no HEAD) because that class of failure only
# shows up during pre-commit's first invocation. v1.0.4 adds this
# script to the release routine so the same class of gap can't ship
# again.
#
# Every check here corresponds to a real v1.0.x bug that CI caught:
#   * BUG-013   — first git commit under pre-commit on a fresh repo
#   * v1.0.3.1  — mypy --strict on both packages
#   * v1.0.3.2  — spans glob after a full pytest run
#
# Usage:
#   scripts/pre-release-smoke.sh
#
# Exits 0 iff every check passes. Writes progress to stdout with
# "=== name ===" section headers so failures are easy to locate in
# the terminal transcript.

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
PY="$ROOT/.venv/bin/python3"
PRAGMA="$ROOT/.venv/bin/pragma"
PRE_COMMIT="$ROOT/.venv/bin/pre-commit"

if [ ! -x "$PY" ]; then
  echo "ERROR: $PY is not executable. Create the venv first:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -e packages/pragma-sdk -e 'packages/pragma[dev]'"
  exit 1
fi

echo "=== local pytest: pragma-sdk ==="
"$PY" -m pytest "$ROOT/packages/pragma-sdk/tests" -q

echo "=== local pytest: pragma ==="
"$PY" -m pytest "$ROOT/packages/pragma/tests" -q

echo "=== mypy --strict: pragma ==="
(cd "$ROOT/packages/pragma" && "$PY" -m mypy --strict src/)

echo "=== mypy --strict: pragma-sdk ==="
(cd "$ROOT/packages/pragma-sdk" && "$PY" -m mypy --strict src/)

echo "=== local pragma verify all ==="
"$PRAGMA" verify all

echo "=== spans produced at .pragma/spans/*.jsonl (KI-1 glob) ==="
shopt -s nullglob
spans=("$ROOT"/.pragma/spans/*.jsonl)
if [ ${#spans[@]} -eq 0 ]; then
  echo "ERROR: no span files — pytest didn't populate .pragma/spans/"
  exit 1
fi
any=0
for f in "${spans[@]}"; do
  [ -s "$f" ] && { any=1; break; }
done
if [ "$any" -eq 0 ]; then
  echo "ERROR: all span files empty — plugin emitted no spans"
  exit 1
fi

echo "=== greenfield smoke: fresh tmp dir, full init->plan->verify->commit flow ==="
tmp="$(mktemp -d -t pragma-smoke-XXXXXXXX)"
trap 'rm -rf "$tmp"' EXIT

(
  cd "$tmp"
  git init -q
  git config user.email "smoke@pragma.local"
  git config user.name "Pragma Smoke"

  "$PRAGMA" init --brownfield --name smoke > /dev/null
  "$PRAGMA" freeze > /dev/null

  # Replace scaffolded config with a minimal one that exercises pre-commit
  # via the venv's pragma (the scaffolded config reaches public repos and
  # is slow to bootstrap here). The class of regression we care about -
  # pragma verify all under pre-commit on a fresh-init repo - is what
  # this hits.
  cat > .pre-commit-config.yaml <<CFG
repos:
  - repo: local
    hooks:
      - id: pragma-verify-all
        name: pragma verify all
        entry: $PY -m pragma verify all
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
CFG

  "$PRE_COMMIT" install --install-hooks > /dev/null 2>&1

  git add .
  # Shape-conformant commit message so the post-commit `pragma verify all`
  # (which runs `verify commits` too) is happy. The smoke is about
  # proving BUG-013 stays fixed, not about making the commit fail shape.
  msg="chore(smoke): adopt pragma

WHY: smoke test for first-commit-on-fresh-init-repo scenario that
v1.0.3 shipped broken. Ensures verify all + pre-commit co-exist
correctly on the day-one user flow.

WHAT: scaffolded via pragma init --brownfield and froze the lock
before this commit.

WHERE: scripts/pre-release-smoke.sh in the pragma repo.

Co-Authored-By: Pragma Smoke <smoke@pragma.local>"
  if ! git commit -m "$msg" > /dev/null 2>&1; then
    echo "ERROR: first git commit blocked by pre-commit on a fresh repo."
    echo "       re-running with output visible:"
    git commit -m "$msg" || true
    exit 1
  fi
  echo "first commit OK"

  # Verify the scaffolded project is in a clean state post-commit.
  "$PRAGMA" verify all > /dev/null
  echo "post-commit verify all OK"
)

echo ""
echo "=========================================="
echo "ALL PRE-RELEASE SMOKE CHECKS PASSED"
echo "=========================================="
