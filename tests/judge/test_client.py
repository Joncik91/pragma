"""Unit tests for pragma.judge.client — tier 3 OpenAI-compatible LLM client."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _make_openai_client(content: str) -> MagicMock:
    """Build a fake OpenAI client whose chat.completions.create() returns `content`."""
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    client.chat.completions.create.return_value = response
    return client


def _make_openai_client_empty_choices() -> MagicMock:
    """Build a fake OpenAI client that returns empty choices."""
    client = MagicMock()
    response = MagicMock()
    response.choices = []
    client.chat.completions.create.return_value = response
    return client


def _make_openai_client_none_content() -> MagicMock:
    """Build a fake OpenAI client that returns None as message content."""
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=None))]
    client.chat.completions.create.return_value = response
    return client


class TestJudgeTestMissingKey:
    def test_missing_all_keys_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PRAGMA_LLM_API_KEY", raising=False)
        monkeypatch.delenv("PRAGMA_DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("PRAGMA_ANTHROPIC_API_KEY", raising=False)
        from pragma.judge.client import judge_test

        result = judge_test("def foo(): pass", "def test_foo(): pass", "python")
        assert result is None

    def test_empty_preferred_key_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAGMA_LLM_API_KEY", "")
        monkeypatch.delenv("PRAGMA_DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("PRAGMA_ANTHROPIC_API_KEY", raising=False)
        from pragma.judge.client import judge_test

        result = judge_test("def foo(): pass", "def test_foo(): pass", "python")
        assert result is None

    def test_legacy_anthropic_key_still_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PRAGMA_ANTHROPIC_API_KEY is still honored as the key fallback."""
        monkeypatch.delenv("PRAGMA_LLM_API_KEY", raising=False)
        monkeypatch.delenv("PRAGMA_DEEPSEEK_API_KEY", raising=False)
        monkeypatch.setenv("PRAGMA_ANTHROPIC_API_KEY", "legacy-key")

        captured_key: list[str] = []

        def fake_openai_class(*args: object, **kwargs: object) -> MagicMock:
            captured_key.append(str(kwargs.get("api_key", "")))
            return _make_openai_client('{"verifies": true, "reason": "ok"}')

        import pragma.judge.client as client_mod

        monkeypatch.setattr(client_mod, "_resolve_api_key", lambda: "legacy-key")

        import importlib

        import openai as openai_mod

        monkeypatch.setattr(openai_mod, "OpenAI", fake_openai_class)
        importlib.reload(client_mod)
        result = client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")
        assert result is not None


class TestKeyResolutionOrder:
    def test_preferred_key_wins_over_legacy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PRAGMA_LLM_API_KEY takes precedence over the legacy vars."""
        monkeypatch.setenv("PRAGMA_LLM_API_KEY", "preferred-key")
        monkeypatch.setenv("PRAGMA_DEEPSEEK_API_KEY", "deepseek-key")
        monkeypatch.setenv("PRAGMA_ANTHROPIC_API_KEY", "anthropic-key")

        import pragma.judge.client as client_mod

        assert client_mod._resolve_api_key() == "preferred-key"

    def test_deepseek_key_over_anthropic_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PRAGMA_LLM_API_KEY", raising=False)
        monkeypatch.setenv("PRAGMA_DEEPSEEK_API_KEY", "deepseek-key")
        monkeypatch.setenv("PRAGMA_ANTHROPIC_API_KEY", "anthropic-key")

        import pragma.judge.client as client_mod

        assert client_mod._resolve_api_key() == "deepseek-key"

    def test_anthropic_key_as_final_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PRAGMA_LLM_API_KEY", raising=False)
        monkeypatch.delenv("PRAGMA_DEEPSEEK_API_KEY", raising=False)
        monkeypatch.setenv("PRAGMA_ANTHROPIC_API_KEY", "anthropic-key")

        import pragma.judge.client as client_mod

        assert client_mod._resolve_api_key() == "anthropic-key"

    def test_no_keys_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PRAGMA_LLM_API_KEY", raising=False)
        monkeypatch.delenv("PRAGMA_DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("PRAGMA_ANTHROPIC_API_KEY", raising=False)

        import pragma.judge.client as client_mod

        assert client_mod._resolve_api_key() is None


class TestEnvVarPassthrough:
    def _run_capturing_client_args(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[list[tuple], list[dict]]:
        """Run judge_test and return (OpenAI() call args, create() call kwargs)."""
        monkeypatch.setenv("PRAGMA_LLM_API_KEY", "test-key")

        constructor_calls: list[dict] = []
        create_calls: list[dict] = []

        def fake_openai_class(*args: object, **kwargs: object) -> MagicMock:
            constructor_calls.append(dict(kwargs))
            return _make_openai_client('{"verifies": true, "reason": "ok"}')

        import importlib

        import openai as openai_mod

        monkeypatch.setattr(openai_mod, "OpenAI", fake_openai_class)

        import pragma.judge.client as client_mod

        importlib.reload(client_mod)

        # Patch create to capture kwargs too
        original_run = client_mod.judge_test

        def capturing_judge_test(
            prod: str, test: str, lang: str
        ) -> tuple[bool, str] | None:
            return original_run(prod, test, lang)

        client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")
        return constructor_calls, create_calls

    def test_base_url_env_var_passed_to_constructor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PRAGMA_LLM_API_KEY", "test-key")
        monkeypatch.setenv("PRAGMA_LLM_BASE_URL", "https://custom.example.com/v1")

        constructor_calls: list[dict] = []

        def fake_openai_class(*args: object, **kwargs: object) -> MagicMock:
            constructor_calls.append(dict(kwargs))
            return _make_openai_client('{"verifies": true, "reason": "ok"}')

        import importlib

        import openai as openai_mod

        monkeypatch.setattr(openai_mod, "OpenAI", fake_openai_class)

        import pragma.judge.client as client_mod

        importlib.reload(client_mod)
        client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")

        assert len(constructor_calls) == 1
        assert constructor_calls[0]["base_url"] == "https://custom.example.com/v1"

    def test_model_env_var_passed_to_create(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAGMA_LLM_API_KEY", "test-key")
        monkeypatch.setenv("PRAGMA_LLM_MODEL", "my-custom-model")
        monkeypatch.delenv("PRAGMA_LLM_BASE_URL", raising=False)

        create_kwargs: list[dict] = []

        def fake_openai_class(*args: object, **kwargs: object) -> MagicMock:
            client = MagicMock()
            response = MagicMock()
            response.choices = [
                MagicMock(message=MagicMock(content='{"verifies": true, "reason": "ok"}'))
            ]

            def capturing_create(**kw: object) -> MagicMock:
                create_kwargs.append(dict(kw))
                return response

            client.chat.completions.create.side_effect = capturing_create
            return client

        import importlib

        import openai as openai_mod

        monkeypatch.setattr(openai_mod, "OpenAI", fake_openai_class)

        import pragma.judge.client as client_mod

        importlib.reload(client_mod)
        client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")

        assert len(create_kwargs) == 1
        assert create_kwargs[0]["model"] == "my-custom-model"

    def test_default_base_url_is_deepseek(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAGMA_LLM_API_KEY", "test-key")
        monkeypatch.delenv("PRAGMA_LLM_BASE_URL", raising=False)

        constructor_calls: list[dict] = []

        def fake_openai_class(*args: object, **kwargs: object) -> MagicMock:
            constructor_calls.append(dict(kwargs))
            return _make_openai_client('{"verifies": true, "reason": "ok"}')

        import importlib

        import openai as openai_mod

        monkeypatch.setattr(openai_mod, "OpenAI", fake_openai_class)

        import pragma.judge.client as client_mod

        importlib.reload(client_mod)
        client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")

        assert len(constructor_calls) == 1
        assert constructor_calls[0]["base_url"] == "https://api.deepseek.com/v1"

    def test_default_model_is_deepseek_chat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAGMA_LLM_API_KEY", "test-key")
        monkeypatch.delenv("PRAGMA_LLM_MODEL", raising=False)

        create_kwargs: list[dict] = []

        def fake_openai_class(*args: object, **kwargs: object) -> MagicMock:
            client = MagicMock()
            response = MagicMock()
            response.choices = [
                MagicMock(message=MagicMock(content='{"verifies": true, "reason": "ok"}'))
            ]

            def capturing_create(**kw: object) -> MagicMock:
                create_kwargs.append(dict(kw))
                return response

            client.chat.completions.create.side_effect = capturing_create
            return client

        import importlib

        import openai as openai_mod

        monkeypatch.setattr(openai_mod, "OpenAI", fake_openai_class)

        import pragma.judge.client as client_mod

        importlib.reload(client_mod)
        client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")

        assert len(create_kwargs) == 1
        assert create_kwargs[0]["model"] == "deepseek-chat"


class TestJudgeTestApiErrors:
    def _run_with_exception(
        self, monkeypatch: pytest.MonkeyPatch, exc: Exception
    ) -> tuple[bool, str] | None:
        monkeypatch.setenv("PRAGMA_LLM_API_KEY", "fake-test-key")

        def fake_openai_class(*args: object, **kwargs: object) -> MagicMock:
            client = MagicMock()
            client.chat.completions.create.side_effect = exc
            return client

        import importlib

        import openai as openai_mod

        monkeypatch.setattr(openai_mod, "OpenAI", fake_openai_class)

        import pragma.judge.client as client_mod

        importlib.reload(client_mod)
        return client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")

    def test_api_exception_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_exception(monkeypatch, RuntimeError("network error"))
        assert result is None

    def test_rate_limit_exception_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_exception(monkeypatch, Exception("rate limit exceeded"))
        assert result is None


class TestJudgeTestResponseParsing:
    def _run_with_content(
        self, monkeypatch: pytest.MonkeyPatch, content: str
    ) -> tuple[bool, str] | None:
        monkeypatch.setenv("PRAGMA_LLM_API_KEY", "fake-test-key")

        def fake_openai_class(*args: object, **kwargs: object) -> MagicMock:
            return _make_openai_client(content)

        import importlib

        import openai as openai_mod

        monkeypatch.setattr(openai_mod, "OpenAI", fake_openai_class)

        import pragma.judge.client as client_mod

        importlib.reload(client_mod)
        return client_mod.judge_test(
            "def foo(): return 42",
            "def test_foo():\n    assert foo() == 42",
            "python",
        )

    def test_valid_verifies_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_content(monkeypatch, '{"verifies": true, "reason": "looks fine"}')
        assert result == (True, "looks fine")

    def test_valid_verifies_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_content(
            monkeypatch, '{"verifies": false, "reason": "asserts on mock"}'
        )
        assert result == (False, "asserts on mock")

    def test_json_wrapped_in_code_fences(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_content(
            monkeypatch, '```json\n{"verifies": true, "reason": "ok"}\n```'
        )
        assert result is not None
        verifies, reason = result
        assert verifies is True
        assert reason == "ok"

    def test_json_wrapped_in_plain_code_fences(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_content(
            monkeypatch, '```\n{"verifies": false, "reason": "mock only"}\n```'
        )
        assert result is not None
        verifies, reason = result
        assert verifies is False
        assert reason == "mock only"

    def test_malformed_json_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_content(monkeypatch, "not json at all")
        assert result is None

    def test_empty_choices_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAGMA_LLM_API_KEY", "fake-test-key")

        def fake_openai_class(*args: object, **kwargs: object) -> MagicMock:
            return _make_openai_client_empty_choices()

        import importlib

        import openai as openai_mod

        monkeypatch.setattr(openai_mod, "OpenAI", fake_openai_class)

        import pragma.judge.client as client_mod

        importlib.reload(client_mod)
        result = client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")
        assert result is None

    def test_none_content_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRAGMA_LLM_API_KEY", "fake-test-key")

        def fake_openai_class(*args: object, **kwargs: object) -> MagicMock:
            return _make_openai_client_none_content()

        import importlib

        import openai as openai_mod

        monkeypatch.setattr(openai_mod, "OpenAI", fake_openai_class)

        import pragma.judge.client as client_mod

        importlib.reload(client_mod)
        result = client_mod.judge_test("def foo(): pass", "def test_foo(): pass", "python")
        assert result is None

    def test_empty_string_content_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_content(monkeypatch, "")
        assert result is None

    def test_reason_truncated_to_200_chars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        long_reason = "x" * 300
        result = self._run_with_content(
            monkeypatch, f'{{"verifies": true, "reason": "{long_reason}"}}'
        )
        assert result is not None
        _, reason = result
        assert len(reason) == 200

    def test_missing_reason_key_gives_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = self._run_with_content(monkeypatch, '{"verifies": true}')
        assert result is not None
        verifies, reason = result
        assert verifies is True
        assert reason == ""
