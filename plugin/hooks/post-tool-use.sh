#!/usr/bin/env bash
# Pragma PostToolUse hook — final gate after Claude lands an edit.
#
# After Claude writes or edits a test file, scan the on-disk file. If the
# classifier finds gamed tests, block and tell Claude what to fix. The
# block here forces Claude to redo the edit, similar to PreToolUse but
# catches the Edit case where we don't have post-state content in stdin.

set -uo pipefail

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

if pragma verify tests "$path" >/dev/null 2>&1; then
    exit 0
fi

human=$(pragma verify tests "$path" --human 2>/dev/null || true)
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
