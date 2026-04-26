#!/usr/bin/env bash
# Pragma PostToolUse hook — final gate after Claude lands an edit.
#
# Catches Edit/MultiEdit cases where PreToolUse couldn't see post-state
# content. Hook contract: exit 0 allow, exit 2 block, other non-zero
# error (proceeds). Silent when pragma isn't installed.

set -uo pipefail

PRAGMA_CMD=()
if command -v pragma >/dev/null 2>&1 && pragma verify --help >/dev/null 2>&1; then
    PRAGMA_CMD=(pragma)
elif command -v python3 >/dev/null 2>&1 && python3 -m pragma verify --help >/dev/null 2>&1; then
    PRAGMA_CMD=(python3 -m pragma)
else
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

if [ ! -f "$path" ]; then
    exit 0
fi

if "${PRAGMA_CMD[@]}" verify tests "$path" >/dev/null 2>&1; then
    exit 0
fi

human=$("${PRAGMA_CMD[@]}" verify tests "$path" --human 2>/dev/null || true)
{
    echo "Pragma rejected this test file: gamed assertions detected on disk."
    echo "$human"
    echo ""
    echo "Edit the file again to fix the flagged assertions. Each test must:"
    echo "  - Call the real production symbol (don't mock the function under test)."
    echo "  - Assert on its actual return value (not 'assert True', not '== same constant')."
    echo "  - Use 'with pytest.raises(...):' when the name says rejects/raises/refuses/denies."
} >&2
exit 2
