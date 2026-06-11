"""Thin OpenAI-compatible LLM client. Defaults to DeepSeek; configurable via env.

Reads these env vars (in order of preference, first wins):
- PRAGMA_LLM_API_KEY (preferred — provider-agnostic)
- PRAGMA_DEEPSEEK_API_KEY (DeepSeek-specific alias)
- PRAGMA_ANTHROPIC_API_KEY (legacy from v2.1.1, still honored)

Other env vars (with defaults):
- PRAGMA_LLM_BASE_URL (default: https://api.deepseek.com/v1)
- PRAGMA_LLM_MODEL (default: deepseek-chat)
- PRAGMA_LLM_TIMEOUT (default: 30.0 seconds, per-request)

Returns None on any failure (missing key, SDK missing, API error,
malformed response) so the caller (judge.classify_file) skips silently.

The OpenAI SDK works against any OpenAI-compatible endpoint, so swapping
providers (DeepSeek → OpenAI → Groq → local Ollama) is one env var.
"""

from __future__ import annotations

import json
import os

from pragma.judge.prompt import SYSTEM_PROMPT, build_user_message

_DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
_DEFAULT_MODEL = "deepseek-chat"
_DEFAULT_TIMEOUT = 30.0


def _resolve_timeout() -> float:
    """Read the per-request timeout (seconds) from env, falling back to the default."""
    raw = os.environ.get("PRAGMA_LLM_TIMEOUT")
    if raw is None:
        return _DEFAULT_TIMEOUT
    try:
        return float(raw)
    except ValueError:
        return _DEFAULT_TIMEOUT


def _resolve_api_key() -> str | None:
    """Read the API key from env, in order of preference."""
    for var in ("PRAGMA_LLM_API_KEY", "PRAGMA_DEEPSEEK_API_KEY", "PRAGMA_ANTHROPIC_API_KEY"):
        val = os.environ.get(var)
        if val:
            return val
    return None


def judge_test(production_source: str, test_source: str, language: str) -> tuple[bool, str] | None:
    """Ask an OpenAI-compatible LLM whether `test_source` verifies `production_source`.

    Returns `(verifies, reason)` on success, None on any failure (missing key,
    SDK missing, API error, malformed response). The caller treats None as
    "skip — emit no semantic_gaming verdict."
    """
    api_key = _resolve_api_key()
    if not api_key:
        return None

    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError:
        return None

    base_url = os.environ.get("PRAGMA_LLM_BASE_URL", _DEFAULT_BASE_URL)
    model = os.environ.get("PRAGMA_LLM_MODEL", _DEFAULT_MODEL)
    timeout = _resolve_timeout()
    user_msg = build_user_message(production_source, test_source, language)

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            max_tokens=256,
            timeout=timeout,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
    except Exception:
        return None

    try:
        choices = response.choices
        if not choices:
            return None
        raw = (choices[0].message.content or "").strip()
        if not raw:
            return None
        # Some models wrap JSON in code fences despite instructions; strip.
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        parsed = json.loads(raw)
        verifies = bool(parsed.get("verifies"))
        reason = str(parsed.get("reason", ""))[:200]
        return (verifies, reason)
    except (json.JSONDecodeError, AttributeError, KeyError, ValueError):
        return None
