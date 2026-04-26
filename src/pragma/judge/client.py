"""Thin Anthropic SDK wrapper. Uses prompt caching on the system message.

Reads `PRAGMA_ANTHROPIC_API_KEY` from env. Returns None on any failure
(missing key, 5xx, rate limit, JSON parse error) so the caller skips silently.
"""

from __future__ import annotations

import json
import os

from pragma.judge.prompt import SYSTEM_PROMPT, build_user_message

_MODEL_ID = "claude-haiku-4-5"


def judge_test(
    production_source: str, test_source: str, language: str
) -> tuple[bool, str] | None:
    """Ask Haiku whether `test_source` verifies `production_source`'s behavior.

    Returns `(verifies, reason)` on success, None on any failure (missing key,
    API error, malformed response). The caller (judge.classify) treats None
    as "skip — emit no semantic_gaming verdict."
    """
    api_key = os.environ.get("PRAGMA_ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic  # type: ignore[import-untyped]
    except ImportError:
        return None

    user_msg = build_user_message(production_source, test_source, language)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_MODEL_ID,
            max_tokens=256,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_msg}],
        )
    except Exception:
        return None

    try:
        text_blocks = [b.text for b in response.content if b.type == "text"]
        if not text_blocks:
            return None
        raw = text_blocks[0].strip()
        # Some models wrap JSON in code fences despite instructions; strip if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        parsed = json.loads(raw)
        verifies = bool(parsed.get("verifies"))
        reason = str(parsed.get("reason", ""))[:200]
        return (verifies, reason)
    except (json.JSONDecodeError, AttributeError, KeyError, ValueError):
        return None
