"""Tests for the python.orphan_test rule."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from pragma.languages.python.rules.orphan_test import classify


def _parse_func(src: str, func_name: str) -> tuple[ast.FunctionDef, ast.Module]:
    tree = ast.parse(textwrap.dedent(src).strip())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == func_name)
    return func, tree


# ---------------------------------------------------------------------------
# Positive cases — should flag
# ---------------------------------------------------------------------------


def test_inline_class_no_import_flags():
    """test_user_repo.py with class UserRepo defined inline, no import → flags."""
    src = """
        class UserRepo:
            def __init__(self): self._store = {}
            def find(self, user_id): ...
            def save(self, user): ...

        def test_find_returns_user_dict():
            repo = UserRepo()
            repo.save({"id": "u1", "name": "Alice"})
            assert repo.find("u1") == {"id": "u1", "name": "Alice"}
    """
    func, tree = _parse_func(src, "test_find_returns_user_dict")
    verdict = classify(
        func,
        test_name="test_find_returns_user_dict",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=tree,
        file_path=Path("tests/test_user_repo.py"),
    )
    assert verdict is not None
    assert verdict.kind == "python.orphan_test"
    assert "user_repo" in verdict.evidence


def test_function_call_no_import_flags():
    """test_emails.py with emails() function defined locally, no import → flags."""
    src = """
        def emails(recipient, body):
            return f"sent to {recipient}"

        def test_send_email_basic():
            result = emails("alice@example.com", "Hello")
            assert isinstance(result, str)
    """
    func, tree = _parse_func(src, "test_send_email_basic")
    verdict = classify(
        func,
        test_name="test_send_email_basic",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=tree,
        file_path=Path("tests/test_emails.py"),
    )
    assert verdict is not None
    assert verdict.kind == "python.orphan_test"
    assert "emails" in verdict.evidence


# ---------------------------------------------------------------------------
# Negative cases — should NOT flag
# ---------------------------------------------------------------------------


def test_direct_import_does_not_flag():
    """from user_repo import UserRepo at top-level → no flag."""
    src = """
        from user_repo import UserRepo

        def test_find_returns_user_dict():
            repo = UserRepo()
            assert repo.find("u1") is not None
    """
    func, tree = _parse_func(src, "test_find_returns_user_dict")
    verdict = classify(
        func,
        test_name="test_find_returns_user_dict",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=tree,
        file_path=Path("tests/test_user_repo.py"),
    )
    assert verdict is None


def test_submodule_import_does_not_flag():
    """from app.user_repo import UserRepo → no flag (last segment matches)."""
    src = """
        from app.user_repo import UserRepo

        def test_find_returns_user_dict():
            repo = UserRepo()
            assert repo.find("u1") is not None
    """
    func, tree = _parse_func(src, "test_find_returns_user_dict")
    verdict = classify(
        func,
        test_name="test_find_returns_user_dict",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=tree,
        file_path=Path("tests/test_user_repo.py"),
    )
    assert verdict is None


def test_no_same_name_local_does_not_flag():
    """test_helpers.py with no Helpers class or helpers() call → no flag (rule 4 fails)."""
    src = """
        import conftest

        def test_do_something():
            result = conftest.helper_fn()
            assert result == 42
    """
    func, tree = _parse_func(src, "test_do_something")
    verdict = classify(
        func,
        test_name="test_do_something",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=tree,
        file_path=Path("tests/test_helpers.py"),
    )
    assert verdict is None


def test_file_path_none_does_not_flag():
    """file_path=None (compat shim) → no flag (returns None silently)."""
    src = """
        class UserRepo:
            pass

        def test_find_returns_user_dict():
            repo = UserRepo()
            assert repo is not None
    """
    func, tree = _parse_func(src, "test_find_returns_user_dict")
    verdict = classify(
        func,
        test_name="test_find_returns_user_dict",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=tree,
        file_path=None,
    )
    assert verdict is None


def test_tree_none_does_not_flag():
    """tree=None → no flag (returns None silently)."""
    src = "def test_find_returns_user_dict(): assert True"
    func, _ = _parse_func(src, "test_find_returns_user_dict")
    verdict = classify(
        func,
        test_name="test_find_returns_user_dict",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=None,
        file_path=Path("tests/test_user_repo.py"),
    )
    assert verdict is None


def test_basename_non_test_prefix_does_not_flag():
    """File not starting with test_ → no flag (rule 1 fails)."""
    src = """
        class UserRepo:
            pass

        def test_find_returns_user_dict():
            repo = UserRepo()
            assert repo is not None
    """
    func, tree = _parse_func(src, "test_find_returns_user_dict")
    verdict = classify(
        func,
        test_name="test_find_returns_user_dict",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=tree,
        file_path=Path("tests/user_repo_test.py"),
    )
    assert verdict is None


def test_import_pkg_dot_name_does_not_flag():
    """import app.user_repo → no flag (last segment matches)."""
    src = """
        import app.user_repo

        def test_find_returns_user_dict():
            repo = app.user_repo.UserRepo()
            assert repo is not None
    """
    func, tree = _parse_func(src, "test_find_returns_user_dict")
    verdict = classify(
        func,
        test_name="test_find_returns_user_dict",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=tree,
        file_path=Path("tests/test_user_repo.py"),
    )
    assert verdict is None


def test_no_local_definition_does_not_flag():
    """test_user_repo.py references UserRepo but it's not defined locally → no flag."""
    src = """
        def test_find_returns_user_dict():
            repo = UserRepo()
            assert repo is not None
    """
    func, tree = _parse_func(src, "test_find_returns_user_dict")
    verdict = classify(
        func,
        test_name="test_find_returns_user_dict",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=tree,
        file_path=Path("tests/test_user_repo.py"),
    )
    # UserRepo is referenced but not defined locally — no flag
    assert verdict is None


def test_single_letter_name_no_local_class_does_not_flag():
    """test_x.py with no X class or x() function → no flag."""
    src = """
        def test_x_basic():
            assert True
    """
    func, tree = _parse_func(src, "test_x_basic")
    verdict = classify(
        func,
        test_name="test_x_basic",
        expected="success",
        target_module=None,
        target_symbol=None,
        tree=tree,
        file_path=Path("tests/test_x.py"),
    )
    assert verdict is None
