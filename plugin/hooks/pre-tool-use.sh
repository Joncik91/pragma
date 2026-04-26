#!/usr/bin/env bash
# Pragma PreToolUse hook — early gate before Claude lands an edit.
#
# Hook contract (Claude Code):
#   exit 0 → allow tool call.
#   exit 2 → BLOCK tool call; stderr is shown to Claude so it can rewrite.
#   other non-zero → hook errored; tool call proceeds (graceful degradation).
#
# Hook is silent when pragma isn't on PATH so the user sees no spurious
# blocks before they've installed `pipx install pragma`.

set -uo pipefail

# Resolve a working `pragma` invocation. Prefer the binary on PATH; fall
# back to `python3 -m pragma`. Probe each by running `verify --help`, not
# by import-checking — a stale `src/pragma/` on sys.path can satisfy
# `import pragma` without supplying a working CLI.
PRAGMA_CMD=()
if command -v pragma >/dev/null 2>&1 && pragma verify --help >/dev/null 2>&1; then
    PRAGMA_CMD=(pragma)
elif command -v python3 >/dev/null 2>&1 && python3 -m pragma verify --help >/dev/null 2>&1; then
    PRAGMA_CMD=(python3 -m pragma)
else
    # Pragma not installed (or not callable) in this environment — degrade silently.
    exit 0
fi

payload=$(cat)

tool=$(printf '%s' "$payload" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || true)
case "$tool" in Edit|Write|MultiEdit) ;; *) exit 0 ;; esac

path=$(printf '%s' "$payload" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null || true)
case "$path" in
    *test_*.py|*/tests/*.py|*/tests/*/*.py) ;;
    *) exit 0 ;;
esac

# PreToolUse can only see candidate content for Write (full-file). For
# Edit/MultiEdit we exit 0 and rely on PostToolUse scanning the on-disk
# result.
content=$(printf '%s' "$payload" | python3 -c "
import json, sys
d = json.load(sys.stdin)
if d.get('tool_name') != 'Write':
    sys.exit(0)
print(d.get('tool_input', {}).get('content', ''), end='')
" 2>/dev/null || true)

if [ -z "$content" ]; then
    exit 0
fi

tmp=$(mktemp --suffix=.py)
trap 'rm -f "$tmp"' EXIT
printf '%s' "$content" > "$tmp"

if "${PRAGMA_CMD[@]}" verify tests "$tmp" >/dev/null 2>&1; then
    exit 0
fi

human=$("${PRAGMA_CMD[@]}" verify tests "$tmp" --human 2>/dev/null || true)
{
    echo "Pragma rejected this test file: gamed assertions detected."
    echo "$human" | sed "s|$tmp|$path|g"
    echo ""
    echo "Rewrite each flagged test to:"
    echo "  - tautological: assert on the production function's actual return value (not constants)."
    echo "  - mocked-away: don't mock the function under test; mock its dependencies instead."
    echo "  - mismatched: a test named *_rejects_*/_raises_* must use 'with pytest.raises(...):'."
} >&2
exit 2
