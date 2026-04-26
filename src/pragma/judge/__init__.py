"""Tier 3: optional LLM-based semantic judge.

Public entry point: `classify.classify_file(test_path, prior_verdicts, lang)`.

Asks a small model (Haiku via Anthropic SDK) "does this test verify the
production function's behavior, or does it only test structure?" Emits
`<lang>.semantic_gaming` verdict (warning, not blocking) when the model
says no.

Tier 3 is opt-in via `--with-llm` CLI flag and `PRAGMA_ANTHROPIC_API_KEY`.
Skips silently when the key is missing or the API call fails. Warning-only
at v2.1 — conformal-prediction calibration is deferred to v2.2.

Architecture:
    classify.py  -> public classify_file(test_path, prior, lang) entry
    prompt.py    -> cached system prompt + per-call user message
    client.py    -> thin Anthropic SDK wrapper (Haiku, prompt caching)

Uses the `claude-api` skill for SDK best practices, prompt caching, and
the up-to-date Haiku model ID.
"""
