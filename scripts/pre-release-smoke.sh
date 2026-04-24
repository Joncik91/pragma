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

echo "=== end-to-end PIL: greenfield, declare, activate, unlock, complete, report ==="
# BUG-020 / REQ-018: prove the full first-run flow produces
# junit.xml + spans + a verified PIL without the user ever having to
# run pytest manually. This is the class of regression that shipped
# as BUG-020 — aggregator needed junit, run_tests never wrote it.
tmp_pil="$(mktemp -d -t pragma-pil-XXXXXXXX)"
trap 'rm -rf "$tmp" "$tmp_pil"' EXIT

(
  cd "$tmp_pil"
  git init -q
  git config user.email "pil-smoke@pragma.local"
  git config user.name "Pragma PIL Smoke"

  "$PRAGMA" init --greenfield --name pil_smoke --language python > /dev/null

  # Replace the REQ-000 placeholder with a real one-permutation REQ.
  cat > pragma.yaml <<YAML
version: '2'
project:
  name: pil_smoke
  mode: greenfield
  language: python
  source_root: src/
  tests_root: tests/
milestones:
- id: M01
  title: PIL smoke
  description: multi-slice first-run flow
  depends_on: []
  slices:
  - id: M01.S1
    title: echo
    description: single permutation to prove the PIL populates
    requirements: [REQ-001]
  - id: M01.S2
    title: shout
    description: second slice so BUG-021 (junit overwritten per slice) stays closed
    requirements: [REQ-002]
requirements:
- id: REQ-001
  title: echo returns input
  description: echo(x) returns x verbatim.
  touches: [src/echo_mod.py]
  permutations:
  - id: identity
    description: echo("hi") returns "hi"
    expected: success
  milestone: M01
  slice: M01.S1
- id: REQ-002
  title: shout uppercases input
  description: shout(x) returns x.upper().
  touches: [src/shout_mod.py]
  permutations:
  - id: upper
    description: shout("hi") returns "HI"
    expected: success
  milestone: M01
  slice: M01.S2
YAML

  "$PRAGMA" freeze > /dev/null
  "$PRAGMA" slice activate M01.S1 > /dev/null

  # Red test + red stub for slice 1.
  cat > tests/test_req_001_echo.py <<PY
from pragma_sdk import set_permutation

from echo_mod import echo


def test_req_001_identity() -> None:
    with set_permutation("identity"):
        assert echo("hi") == "hi"
PY

  cat > src/echo_mod.py <<PY
from pragma_sdk import trace


@trace("REQ-001")
def echo(x: str) -> str:
    raise NotImplementedError
PY

  "$PRAGMA" unlock > /dev/null

  cat > src/echo_mod.py <<PY
from pragma_sdk import trace


@trace("REQ-001")
def echo(x: str) -> str:
    return x
PY

  "$PRAGMA" slice complete > /dev/null

  # Slice 2 — added specifically to exercise BUG-021: if slice complete
  # overwrites junit instead of regenerating from the full suite, the
  # final PIL assertion below will show REQ-001 as missing.
  "$PRAGMA" slice activate M01.S2 > /dev/null

  cat > tests/test_req_002_shout.py <<PY
from pragma_sdk import set_permutation

from shout_mod import shout


def test_req_002_upper() -> None:
    with set_permutation("upper"):
        assert shout("hi") == "HI"
PY

  cat > src/shout_mod.py <<PY
from pragma_sdk import trace


@trace("REQ-002")
def shout(x: str) -> str:
    raise NotImplementedError
PY

  "$PRAGMA" unlock > /dev/null

  cat > src/shout_mod.py <<PY
from pragma_sdk import trace


@trace("REQ-002")
def shout(x: str) -> str:
    return x.upper()
PY

  "$PRAGMA" slice complete > /dev/null

  # BUG-020 assertion #1: junit.xml must exist and be non-empty after
  # slice complete.
  if [ ! -s .pragma/pytest-junit.xml ]; then
    echo "ERROR: .pragma/pytest-junit.xml missing or empty after slice complete — BUG-020 regressed"
    exit 1
  fi

  # BUG-020 assertion #2: --json report shows ok >= 2 (both slices) and
  # missing == 0. BUG-021 would fail this because junit from slice 1
  # would be overwritten by slice 2's per-slice run.
  report_json="$("$PRAGMA" report --json)"
  ok_count="$(echo "$report_json" | "$PY" -c 'import json,sys; print(json.loads(sys.stdin.read())["summary"]["ok"])')"
  missing_count="$(echo "$report_json" | "$PY" -c 'import json,sys; print(json.loads(sys.stdin.read())["summary"]["missing"])')"
  if [ "$ok_count" -lt 2 ] || [ "$missing_count" -ne 0 ]; then
    echo "ERROR: pragma report shows ok=$ok_count missing=$missing_count — expected ok>=2 missing=0 after shipping both slices"
    echo "full report:"
    echo "$report_json"
    exit 1
  fi

  # BUG-020 assertion #3: --human output shows both slices verified and
  # no diagnostic banner.
  report_md="$("$PRAGMA" report --human)"
  if ! echo "$report_md" | grep -q "2 verified"; then
    echo "ERROR: pragma report --human missing '2 verified' line (BUG-021 regression check)"
    echo "$report_md"
    exit 1
  fi
  if echo "$report_md" | grep -q "## Diagnostics"; then
    echo "ERROR: pragma report --human shows a Diagnostics banner on the happy path"
    echo "$report_md"
    exit 1
  fi
  echo "end-to-end PIL OK (ok=$ok_count, missing=$missing_count)"
)

echo ""
echo "=========================================="
echo "ALL PRE-RELEASE SMOKE CHECKS PASSED"
echo "=========================================="
