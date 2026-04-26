"""Fixture: async def test with mock.patch on the production target.

BUG-028 regression — pragma was silently skipping ast.AsyncFunctionDef nodes,
so any `async def test_*` file came back with zero verdicts. Now both
sync and async test functions are walked.
"""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_send_email_returns_message_id():
    fake_id = "msg-abc123"
    with patch("emails.send_email", new=AsyncMock(return_value=fake_id)):
        from emails import send_email  # type: ignore[import-not-found]
        result = await send_email("user@example.com", "body text")
        assert result == fake_id
