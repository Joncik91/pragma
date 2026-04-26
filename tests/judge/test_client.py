"""Unit tests for pragma.judge.client — tier 3 Anthropic SDK wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_response(text: str) -> MagicMock:
    """Build a minimal fake Anthropic response with a single text block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def _make_response_no_text_blocks() -> MagicMock:
    """Build a fake Anthropic response with no text blocks."""
    response = MagicMock()
    response.content = []
    return response


class TestJudgeTestMissingKey:
    def test_missing_api_key_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PRAGMA_ANTHROPIC_API_KEY", raising=False)
        from pragma.judge.client import judge_test

        result = judge_test("def foo(): pass", "def test_foo(): pass", "python")
        assert result is None

    def test_empty_api_key_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAGMA_ANTHROPIC_API_KEY", "")
        from pragma.judge.client import judge_test

        result = judge_test("def foo(): pass", "def test_foo(): pass", "python")
        assert result is None


class TestJudgeTestApiErrors:
    def test_api_exception_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAGMA_ANTHROPIC_API_KEY", "fake-test-key")

        mock_client_instance = MagicMock()
        mock_client_instance.messages.create.side_effect = RuntimeError("network error")
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client_instance

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            # Reimport to pick up the patched module
            import importlib

            import pragma.judge.client as client_mod

            importlib.reload(client_mod)
            result = client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")

        assert result is None

    def test_rate_limit_exception_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAGMA_ANTHROPIC_API_KEY", "fake-test-key")

        mock_client_instance = MagicMock()
        mock_client_instance.messages.create.side_effect = Exception("rate limit exceeded")
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client_instance

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            import importlib

            import pragma.judge.client as client_mod

            importlib.reload(client_mod)
            result = client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")

        assert result is None


class TestJudgeTestResponseParsing:
    def _run_with_response(
        self, monkeypatch: pytest.MonkeyPatch, response_text: str
    ) -> tuple[bool, str] | None:
        monkeypatch.setenv("PRAGMA_ANTHROPIC_API_KEY", "fake-test-key")

        mock_client_instance = MagicMock()
        mock_client_instance.messages.create.return_value = _make_response(response_text)
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client_instance

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            import importlib

            import pragma.judge.client as client_mod

            importlib.reload(client_mod)
            return client_mod.judge_test(
                "def foo(): return 42",
                "def test_foo():\n    assert foo() == 42",
                "python",
            )

    def test_valid_verifies_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_response(monkeypatch, '{"verifies": true, "reason": "looks fine"}')
        assert result == (True, "looks fine")

    def test_valid_verifies_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_response(
            monkeypatch, '{"verifies": false, "reason": "asserts on mock"}'
        )
        assert result == (False, "asserts on mock")

    def test_json_wrapped_in_code_fences(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_response(
            monkeypatch, '```json\n{"verifies": true, "reason": "ok"}\n```'
        )
        assert result is not None
        verifies, reason = result
        assert verifies is True
        assert reason == "ok"

    def test_json_wrapped_in_plain_code_fences(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_response(
            monkeypatch, '```\n{"verifies": false, "reason": "mock only"}\n```'
        )
        assert result is not None
        verifies, reason = result
        assert verifies is False
        assert reason == "mock only"

    def test_malformed_json_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_response(monkeypatch, "not json at all")
        assert result is None

    def test_no_text_blocks_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAGMA_ANTHROPIC_API_KEY", "fake-test-key")

        mock_client_instance = MagicMock()
        mock_client_instance.messages.create.return_value = _make_response_no_text_blocks()
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client_instance

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            import importlib

            import pragma.judge.client as client_mod

            importlib.reload(client_mod)
            result = client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")

        assert result is None

    def test_reason_truncated_to_200_chars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        long_reason = "x" * 300
        result = self._run_with_response(
            monkeypatch, f'{{"verifies": true, "reason": "{long_reason}"}}'
        )
        assert result is not None
        _, reason = result
        assert len(reason) == 200

    def test_missing_reason_key_gives_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_response(monkeypatch, '{"verifies": true}')
        assert result is not None
        verifies, reason = result
        assert verifies is True
        assert reason == ""
