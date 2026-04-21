#!/usr/bin/env bash
# Greenfield end-to-end smoke-test.
#
# Exercises the v1.0 "non-coder bootstraps a project from zero" contract:
# init --greenfield scaffolds the seed, plan-greenfield expands the
# problem statement into REQs, freeze + verify + doctor all stay green
# with TODO placeholders intact. Called from CI.
set -euo pipefail

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cd "$tmp"

echo ">> pragma init --greenfield --name demo --language python"
pragma init --greenfield --name demo --language python

for f in pragma.yaml pragma.lock.json .pragma/state.json claude.md PRAGMA.md \
         .pre-commit-config.yaml .claude/settings.json; do
    test -e "$f" || { echo "MISSING: $f"; exit 1; }
done
test -d src || { echo "MISSING: src/"; exit 1; }
test -d tests || { echo "MISSING: tests/"; exit 1; }

grep -q "mode: greenfield" pragma.yaml || { echo "pragma.yaml missing 'mode: greenfield'"; exit 1; }
grep -q "REQ-000" pragma.yaml || { echo "pragma.yaml missing REQ-000 seed"; exit 1; }

echo ">> pragma spec plan-greenfield --from problem.md"
cat > problem.md <<'MD'
# Register

Users sign up with an email and a strong password.

# Login

Returning users sign in to receive a JWT.
MD

pragma spec plan-greenfield --from problem.md
grep -q "REQ-001" pragma.yaml || { echo "REQ-001 not created"; exit 1; }
grep -q "REQ-002" pragma.yaml || { echo "REQ-002 not created"; exit 1; }
grep -q "REQ-000" pragma.yaml && { echo "REQ-000 seed should have been replaced"; exit 1; } || true

echo ">> pragma freeze"
pragma freeze

echo ">> pragma verify manifest"
pragma verify manifest

echo ">> pragma doctor"
pragma doctor | python -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['ok'] is True, d
fatals = [x for x in d.get('diagnostics', []) if x.get('severity') == 'fatal']
assert not fatals, f'unexpected fatal diagnostics: {fatals}'
print('doctor: ok')
"

echo "greenfield e2e: OK"
