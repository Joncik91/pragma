"""Unit tests for pragma.judge.classify — tier 3 orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import (
    MagicMock,
    patch,  # noqa: F401
)

import pytest

from pragma.verdict import Verdict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lang(language: str) -> MagicMock:
    lang = MagicMock()
    lang.LANGUAGE = language
    return lang


def _verified(name: str, language: str = "python") -> Verdict:
    return Verdict(kind=f"{language}.verified", evidence="", test_name=name)


def _blocking(name: str, language: str = "python") -> Verdict:
    return Verdict(kind=f"{language}.tautological", evidence="assert True", test_name=name)


# ---------------------------------------------------------------------------
# classify_file: guard conditions
# ---------------------------------------------------------------------------


class TestClassifyFileGuards:
    def test_empty_prior_verdicts_returns_empty(self, tmp_path: Path) -> None:
        from pragma.judge.classify import classify_file

        f = tmp_path / "test_foo.py"
        f.write_text("def test_foo(): pass\n")
        result = classify_file(f, [], _make_lang("python"))
        assert result == []

    def test_unknown_language_returns_prior_unchanged(self, tmp_path: Path) -> None:
        from pragma.judge.classify import classify_file

        f = tmp_path / "test_foo.py"
        f.write_text("def test_foo(): pass\n")
        prior = [_verified("test_foo", "ruby")]
        result = classify_file(f, prior, _make_lang("ruby"))
        assert result == prior

    def test_only_blocking_verdicts_no_verified_returns_prior_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pragma.judge import classify as classify_mod

        f = tmp_path / "test_foo.py"
        f.write_text("def test_foo(): assert True\n")
        prior = [_blocking("test_foo")]

        # Patch judge_test to make sure it's never called
        called = []

        def fake_judge(*args, **kwargs):
            called.append(args)
            return None

        monkeypatch.setattr(classify_mod, "judge_test", fake_judge)
        result = classify_mod.classify_file(f, prior, _make_lang("python"))
        assert result == prior
        # No verified tests → judge_test should NOT be called
        assert called == []


# ---------------------------------------------------------------------------
# classify_file: judge outcomes
# ---------------------------------------------------------------------------


class TestClassifyFileJudgeOutcomes:
    def _setup_with_mock_judge(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        judge_return,
        language: str = "python",
    ) -> tuple[Path, list[Verdict]]:
        """Create a test file with a verified verdict, mock production target resolution."""
        from pragma.judge import classify as classify_mod

        f = tmp_path / "test_foo.py"
        f.write_text("def test_foo(): pass\n")

        monkeypatch.setattr(classify_mod, "judge_test", lambda *args, **kwargs: judge_return)

        # Patch _run_judge's production source resolution to return a dummy source
        def patched_run_judge(test_path, prior_verdicts, lang):
            # Bypass target resolution by injecting prod_source directly
            verified_kind = f"{lang.LANGUAGE}.verified"
            verified_tests = [v for v in prior_verdicts if v.kind == verified_kind]
            if not verified_tests:
                return prior_verdicts

            prod_source = "def foo(): return 42"
            test_source = test_path.read_text(encoding="utf-8")

            new_verdicts: dict[str, Verdict] = {}
            for v in verified_tests:
                result = classify_mod.judge_test(prod_source, test_source, lang.LANGUAGE)
                if result is None:
                    continue
                verifies, reason = result
                if not verifies:
                    new_verdicts[v.test_name] = Verdict(
                        kind=f"{lang.LANGUAGE}.semantic_gaming",
                        evidence=f"LLM judge: {reason}",
                        test_name=v.test_name,
                    )

            if not new_verdicts:
                return prior_verdicts

            result_verdicts: list[Verdict] = []
            for v in prior_verdicts:
                result_verdicts.append(v)
                if v.kind == verified_kind and v.test_name in new_verdicts:
                    result_verdicts.append(new_verdicts[v.test_name])
            return result_verdicts

        monkeypatch.setattr(classify_mod, "_run_judge", patched_run_judge)

        prior = [_verified("test_foo", language)]
        return f, prior

    def test_judge_returns_true_no_semantic_gaming_added(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pragma.judge import classify as classify_mod

        f, prior = self._setup_with_mock_judge(
            tmp_path, monkeypatch, (True, "test calls foo and asserts on result")
        )
        result = classify_mod.classify_file(f, prior, _make_lang("python"))
        assert result == prior
        kinds = [v.kind for v in result]
        assert "python.semantic_gaming" not in kinds

    def test_judge_returns_false_semantic_gaming_added(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pragma.judge import classify as classify_mod

        f, prior = self._setup_with_mock_judge(tmp_path, monkeypatch, (False, "fake reason"))
        result = classify_mod.classify_file(f, prior, _make_lang("python"))

        kinds = [v.kind for v in result]
        assert "python.verified" in kinds
        assert "python.semantic_gaming" in kinds

        # semantic_gaming verdict should follow the verified one
        verified_idx = kinds.index("python.verified")
        gaming_idx = kinds.index("python.semantic_gaming")
        assert gaming_idx == verified_idx + 1

    def test_judge_returns_false_evidence_contains_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pragma.judge import classify as classify_mod

        f, prior = self._setup_with_mock_judge(
            tmp_path, monkeypatch, (False, "asserts on mock return value")
        )
        result = classify_mod.classify_file(f, prior, _make_lang("python"))
        gaming_verdicts = [v for v in result if v.kind == "python.semantic_gaming"]
        assert len(gaming_verdicts) == 1
        assert "asserts on mock return value" in gaming_verdicts[0].evidence

    def test_judge_returns_none_no_verdict_added(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pragma.judge import classify as classify_mod

        f, prior = self._setup_with_mock_judge(tmp_path, monkeypatch, None)
        result = classify_mod.classify_file(f, prior, _make_lang("python"))
        assert result == prior
        kinds = [v.kind for v in result]
        assert "python.semantic_gaming" not in kinds

    def test_judge_false_for_vitest_language(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pragma.judge import classify as classify_mod

        f, prior = self._setup_with_mock_judge(
            tmp_path, monkeypatch, (False, "mock only"), language="vitest"
        )
        result = classify_mod.classify_file(f, prior, _make_lang("vitest"))
        kinds = [v.kind for v in result]
        assert "vitest.semantic_gaming" in kinds


# ---------------------------------------------------------------------------
# classify_file: production target resolution failure
# ---------------------------------------------------------------------------


class TestClassifyFileTargetResolution:
    def test_no_production_target_returns_prior_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When production target can't be resolved, prior_verdicts returned unchanged."""
        from pragma.judge import classify as classify_mod

        f = tmp_path / "test_foo.py"
        f.write_text("def test_foo(): pass\n")
        prior = [_verified("test_foo")]

        # Patch infer_target to return (None, None) — target not inferable
        with patch("pragma.languages.python.inference.infer_target", return_value=(None, None)):
            result = classify_mod.classify_file(f, prior, _make_lang("python"))

        assert result == prior


# ---------------------------------------------------------------------------
# classify_file: fail-open on internal exception
# ---------------------------------------------------------------------------


class TestClassifyFileFailOpen:
    def test_internal_exception_returns_prior_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pragma.judge import classify as classify_mod

        f = tmp_path / "test_foo.py"
        f.write_text("def test_foo(): pass\n")
        prior = [_verified("test_foo")]

        def exploding_run_judge(*args, **kwargs):
            raise RuntimeError("unexpected internal error")

        monkeypatch.setattr(classify_mod, "_run_judge", exploding_run_judge)
        result = classify_mod.classify_file(f, prior, _make_lang("python"))
        assert result == prior
