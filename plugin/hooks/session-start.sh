#!/usr/bin/env bash
# Pragma Claude Code plugin — SessionStart hook.
#
# Reads $CLAUDE_PROJECT_DIR/.pragma/state.json and $CLAUDE_PROJECT_DIR/pragma.yaml
# and prints a one-paragraph context block telling Claude the active slice,
# gate state, and the next action. If no manifest exists, exits 0 silently
# (greenfield / non-Pragma dirs are not ambushed).
#
# Hook input is JSON on stdin per Claude Code spec, but for SessionStart we
# only need $CLAUDE_PROJECT_DIR which is exported by the host.

set -u

# Discover the project dir. Prefer the env var; fall back to PWD.
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"

manifest="$PROJECT_DIR/pragma.yaml"
state_file="$PROJECT_DIR/.pragma/state.json"

# No manifest → silent. Pragma is opt-in; don't pollute non-Pragma sessions.
if [ ! -f "$manifest" ]; then
  exit 0
fi

# No state yet (manifest exists but no init has happened in this dir,
# unusual but possible) → tell Claude the manifest is there but no slice
# is active.
if [ ! -f "$state_file" ]; then
  cat <<'EOF'
[Pragma plugin] pragma.yaml present but no .pragma/state.json. The
gate is not yet armed. Run `pragma freeze` (if needed) and
`pragma slice activate <id>` to start working a slice.
EOF
  exit 0
fi

# Best-effort JSON read. We don't require jq; python is part of every
# Pragma-using machine because Pragma itself is a Python tool.
python_bin="${PRAGMA_PYTHON_BIN:-python3}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
  python_bin=python
fi

active_slice=$("$python_bin" -c "
import json, sys
try:
    s = json.load(open('$state_file'))
    print(s.get('active_slice') or '')
except Exception:
    pass
" 2>/dev/null)

gate=$("$python_bin" -c "
import json, sys
try:
    s = json.load(open('$state_file'))
    print(s.get('gate') or 'NEUTRAL')
except Exception:
    pass
" 2>/dev/null)

if [ -z "$active_slice" ]; then
  cat <<EOF
[Pragma plugin] No active slice. Gate is NEUTRAL.

Next action: when the user describes a feature, call
\`pragma start "<intent>"\` (greenfield / brownfield is auto-detected).
This scaffolds the manifest, plans the slice, and lands at gate=LOCKED.
EOF
  exit 0
fi

case "$gate" in
  LOCKED)
    next="Write a failing test named test_req_<id>_<permutation_id> for each declared permutation under tests/. Run \`pragma unlock\` when all tests are red."
    ;;
  UNLOCKED)
    next="Write the implementation. When tests go green, run \`pragma slice complete\`."
    ;;
  *)
    next="Run \`pragma slice status\` to inspect the gate."
    ;;
esac

cat <<EOF
[Pragma plugin] Active slice: $active_slice. Gate: $gate.

Next action: $next

Rules: (1) Never edit pragma.yaml or pragma.lock.json directly — use
\`pragma spec add-requirement\` / \`pragma freeze\`. (2) Never bypass the
gate; \`pragma unlock --skip-tests --reason "..."\` is the only audited
escape hatch. (3) After completing a slice, use \`pragma narrative
commit --subject "..."\` to draft the message in the gate-conformant
shape (WHY paragraph + Co-Authored-By trailer).
EOF
