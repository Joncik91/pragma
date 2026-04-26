"""Thin Anthropic SDK wrapper. Uses prompt caching on the system message.

Step 11 will implement. Reads `PRAGMA_ANTHROPIC_API_KEY` from env. Returns
None on any failure (missing key, 5xx, rate limit, JSON parse error) so
the caller can skip silently.

Use the `claude-api` skill when implementing — it has the up-to-date
Haiku model ID and prompt-caching headers.
"""

from __future__ import annotations
