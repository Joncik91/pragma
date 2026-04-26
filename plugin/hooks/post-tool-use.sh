#!/usr/bin/env bash
# Pragma PostToolUse hook — block when an edit introduces NEW gaming.
#
# Catches Edit/MultiEdit cases. Blocks only when the edit added new
# blocking verdicts; pre-existing gaming in the file is not the user's
# problem right now. Hook contract: 0 allow, 2 block.

set -uo pipefail

# Detect a working pragma invocation; degrade silently if missing.
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

if [ ! -f "$path" ]; then
    exit 0
fi

# On-disk file IS the candidate post-edit. Diff against git HEAD.
# Pass --with-coverage by default so tier 2 (coverage-based gaming detection)
# runs on every edit. Opt out by setting PRAGMA_COVERAGE_DEFAULT_OFF=1.
if [ "${PRAGMA_COVERAGE_DEFAULT_OFF:-}" = "1" ]; then
    exec python3 "${CLAUDE_PLUGIN_ROOT}/hooks/check_diff.py" "$path" "$path"
else
    exec python3 "${CLAUDE_PLUGIN_ROOT}/hooks/check_diff.py" "$path" "$path" --with-coverage
fi
