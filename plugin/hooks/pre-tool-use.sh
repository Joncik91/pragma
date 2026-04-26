#!/usr/bin/env bash
# Pragma PreToolUse hook — early gate before Claude lands a Write.
#
# Block only when the proposed Write content introduces NEW gaming
# relative to the current on-disk file (or git HEAD for new files).
# Hook contract: 0 allow, 2 block, other proceeds.

set -uo pipefail

if ! command -v python3 >/dev/null 2>&1; then
    exit 0
fi
if ! command -v pragma >/dev/null 2>&1 || ! pragma verify --help >/dev/null 2>&1; then
    if ! python3 -m pragma verify --help >/dev/null 2>&1; then
        exit 0
    fi
fi

payload=$(cat)
tool=$(printf '%s' "$payload" | python3 -c "import json,sys;print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || true)
case "$tool" in Edit|Write|MultiEdit) ;; *) exit 0 ;; esac

path=$(printf '%s' "$payload" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null || true)
case "$path" in
    *test_*.py|*/tests/*.py|*/tests/*/*.py) ;;
    *) exit 0 ;;
esac

# PreToolUse only sees post-edit content for Write (full-file). For
# Edit/MultiEdit, PostToolUse handles it.
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

# Write candidate to a tempfile; pass both paths so check_diff can read
# the candidate while diff'ing against git HEAD of on-disk path.
tmp=$(mktemp --suffix=.py)
trap 'rm -f "$tmp"' EXIT
printf '%s' "$content" > "$tmp"

exec python3 "${CLAUDE_PLUGIN_ROOT}/hooks/check_diff.py" "$path" "$tmp"
