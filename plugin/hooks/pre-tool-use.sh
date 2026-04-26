#!/usr/bin/env bash
# Pragma PreToolUse hook — early gate before Claude lands an edit.
#
# Reads the tool call payload from stdin. If Claude is writing/editing a
# test file with content that contains gamed assertions, refuse the
# tool call and emit a message Claude can read so it rewrites instead.
#
# Hook contract (Claude Code):
#   - exit 0: allow tool call, no output to user.
#   - exit 2: BLOCK tool call. stderr is shown to Claude (will be re-prompted).
#   - other non-zero: error in the hook itself; tool call proceeds.

set -uo pipefail

payload=$(cat)

tool=$(printf '%s' "$payload" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || true)
case "$tool" in Edit|Write|MultiEdit) ;; *) exit 0 ;; esac

path=$(printf '%s' "$payload" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null || true)
case "$path" in
    *test_*.py|*/tests/*.py|*/tests/*/*.py) ;;
    *) exit 0 ;;
esac

# Extract the post-edit content from the tool input. For Write: tool_input.content.
# For Edit: we approximate by applying tool_input.new_string into the existing file
# in memory — but the simpler-and-still-correct path is to wait for PostToolUse to
# scan the on-disk file. PreToolUse here only catches `Write` (full-file replacements)
# where we have the candidate content directly; for Edit we exit 0 and rely on
# PostToolUse.
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

# Run the classifier against a tempfile containing the candidate content.
tmp=$(mktemp --suffix=.py)
trap 'rm -f "$tmp"' EXIT
printf '%s' "$content" > "$tmp"

if pragma verify tests "$tmp" >/dev/null 2>&1; then
    exit 0
fi

# Block. Build a friendly message for Claude.
human=$(pragma verify tests "$tmp" --human 2>/dev/null || true)
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
