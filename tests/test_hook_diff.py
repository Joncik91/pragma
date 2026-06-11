"""End-to-end tests for plugin/hooks/check_diff.py — diff-mode rejection.

These exercise the hook script as a subprocess against fabricated git
repos so we catch regressions in tempfile naming, language matching,
and the new-vs-old diff logic.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

HOOK = Path(__file__).resolve().parents[1] / "plugin" / "hooks" / "check_diff.py"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], cwd=path)
    _git(["config", "user.email", "t@t.t"], cwd=path)
    _git(["config", "user.name", "hook-test"], cwd=path)


def _commit_file(repo: Path, rel: str, body: str) -> None:
    f = repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    _git(["add", rel], cwd=repo)
    _git(["commit", "-q", "-m", f"add {rel}"], cwd=repo)


def _run_hook(on_disk: Path, candidate: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(HOOK), str(on_disk), str(candidate)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    if not shutil.which("git"):
        pytest.skip("git not on PATH")
    if not shutil.which("pragma"):
        pytest.skip("pragma not on PATH")
    r = tmp_path / "repo"
    _init_repo(r)
    return r


def test_hook_allows_when_old_and_new_have_same_blocking_names(repo: Path) -> None:
    """Edit that touches an unrelated test must not block on pre-existing gaming."""
    body_v1 = (
        "def test_smoke():\n"
        "    assert True  # pre-existing gaming\n"
        "\n"
        "def test_other():\n"
        "    assert 1 == 2  # also pre-existing\n"
    )
    _commit_file(repo, "tests/test_x.py", body_v1)

    # New version adds a comment but keeps the same gamed tests.
    body_v2 = body_v1 + "\n# new comment, no behavior change\n"
    target = repo / "tests" / "test_x.py"
    target.write_text(body_v2, encoding="utf-8")

    result = _run_hook(target, target)
    # Pre-existing gaming is the user's history; the diff-mode hook
    # only blocks NEW gaming. Same names before and after → allow.
    assert result.returncode == 0, (
        f"hook should have allowed but exited {result.returncode}; stderr:\n{result.stderr}"
    )


def test_hook_blocks_when_edit_introduces_new_gaming(repo: Path) -> None:
    body_v1 = "def test_existing():\n    result = 1 + 1\n    assert result == 2\n"
    _commit_file(repo, "tests/test_y.py", body_v1)

    body_v2 = body_v1 + "\n\ndef test_new_smoke():\n    assert True\n"
    target = repo / "tests" / "test_y.py"
    target.write_text(body_v2, encoding="utf-8")

    result = _run_hook(target, target)
    assert result.returncode == 2, (
        f"expected block (exit 2) but got {result.returncode}; stderr:\n{result.stderr}"
    )
    assert "test_new_smoke" in result.stderr


# ---------------------------------------------------------------------------
# Unit tests for --with-coverage flag plumbing (step 9)
# ---------------------------------------------------------------------------


def _import_check_diff():
    """Import check_diff module from plugin/hooks/check_diff.py."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_diff",
        REPO_ROOT / "plugin" / "hooks" / "check_diff.py",
    )
    mod = importlib.util.module_from_spec(spec)
    # _load_blocking_suffixes() runs at import time; patch subprocess so it
    # doesn't try to invoke pragma.
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = (
        '["tautological", "target_not_covered", "mocked_away", "assertion_mismatch"]'
    )
    with patch("subprocess.run", return_value=mock_result):
        spec.loader.exec_module(mod)
    return mod


def test_run_pragma_includes_with_coverage_flag(tmp_path: Path) -> None:
    """_run_pragma(path, with_coverage=True) must include --with-coverage in argv."""
    mod = _import_check_diff()
    fake_file = tmp_path / "test_x.py"
    fake_file.write_text("def test_x(): pass\n")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        r = MagicMock()
        r.stdout = "{}"
        return r

    with patch("subprocess.run", side_effect=fake_run):
        mod._run_pragma(fake_file, with_coverage=True)

    assert calls, "subprocess.run was never called"
    first_call = calls[0]
    assert "--with-coverage" in first_call, f"--with-coverage not found in argv: {first_call}"


def test_run_pragma_excludes_with_coverage_flag_when_false(tmp_path: Path) -> None:
    """_run_pragma(path, with_coverage=False) must NOT include --with-coverage."""
    mod = _import_check_diff()
    fake_file = tmp_path / "test_x.py"
    fake_file.write_text("def test_x(): pass\n")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        r = MagicMock()
        r.stdout = "{}"
        return r

    with patch("subprocess.run", side_effect=fake_run):
        mod._run_pragma(fake_file, with_coverage=False)

    assert calls, "subprocess.run was never called"
    first_call = calls[0]
    assert "--with-coverage" not in first_call, (
        f"--with-coverage unexpectedly found in argv: {first_call}"
    )


def test_run_pragma_default_excludes_with_coverage_flag(tmp_path: Path) -> None:
    """_run_pragma(path) with no kwarg must NOT include --with-coverage (backward compat)."""
    mod = _import_check_diff()
    fake_file = tmp_path / "test_x.py"
    fake_file.write_text("def test_x(): pass\n")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        r = MagicMock()
        r.stdout = "{}"
        return r

    with patch("subprocess.run", side_effect=fake_run):
        mod._run_pragma(fake_file)

    assert calls, "subprocess.run was never called"
    first_call = calls[0]
    assert "--with-coverage" not in first_call, (
        f"--with-coverage unexpectedly found in default argv: {first_call}"
    )


def test_main_parses_with_coverage_flag_and_forwards(tmp_path: Path) -> None:
    """main() with --with-coverage must call _run_pragma with with_coverage=True."""
    mod = _import_check_diff()
    fake_file = tmp_path / "test_x.py"
    fake_file.write_text("def test_x(): pass\n")

    captured_kwargs = []

    def fake_run_pragma(path, *, with_coverage=False, with_llm=False):
        captured_kwargs.append({"path": path, "with_coverage": with_coverage, "with_llm": with_llm})
        return {}

    with patch.object(mod, "_run_pragma", side_effect=fake_run_pragma):
        mod.main(["check_diff", str(fake_file), str(fake_file), "--with-coverage"])

    assert captured_kwargs, "_run_pragma was never called"
    assert captured_kwargs[0]["with_coverage"] is True, (
        f"Expected with_coverage=True, got: {captured_kwargs[0]}"
    )


def test_main_without_flag_calls_run_pragma_with_coverage_false(tmp_path: Path) -> None:
    """main() without --with-coverage must call _run_pragma with with_coverage=False."""
    mod = _import_check_diff()
    fake_file = tmp_path / "test_x.py"
    fake_file.write_text("def test_x(): pass\n")

    captured_kwargs = []

    def fake_run_pragma(path, *, with_coverage=False, with_llm=False):
        captured_kwargs.append({"path": path, "with_coverage": with_coverage, "with_llm": with_llm})
        return {}

    with patch.object(mod, "_run_pragma", side_effect=fake_run_pragma):
        mod.main(["check_diff", str(fake_file), str(fake_file)])

    assert captured_kwargs, "_run_pragma was never called"
    assert captured_kwargs[0]["with_coverage"] is False, (
        f"Expected with_coverage=False, got: {captured_kwargs[0]}"
    )


def test_post_tool_use_sh_coverage_is_opt_in() -> None:
    """post-tool-use.sh must gate --with-coverage behind PRAGMA_COVERAGE=1 opt-in.

    The old default-on opt-out path (PRAGMA_COVERAGE_DEFAULT_OFF) is removed:
    tier 2 executes the test file under audit, so it must not run unless the
    user explicitly opts in.
    """
    script = (REPO_ROOT / "plugin" / "hooks" / "post-tool-use.sh").read_text()
    assert "--with-coverage" in script, (
        "post-tool-use.sh must still be able to pass --with-coverage when opted in"
    )
    assert "PRAGMA_COVERAGE" in script, (
        "post-tool-use.sh must gate --with-coverage behind the PRAGMA_COVERAGE opt-in env var"
    )
    assert "PRAGMA_COVERAGE_DEFAULT_OFF" not in script, (
        "the PRAGMA_COVERAGE_DEFAULT_OFF opt-out path must be removed; coverage is now opt-in"
    )


POST_TOOL_USE = REPO_ROOT / "plugin" / "hooks" / "post-tool-use.sh"


def _run_post_tool_use_argv(tmp_path: Path, extra_env: dict[str, str]) -> list[str]:
    """Run post-tool-use.sh against a fake test edit; return the argv it execs.

    Points CLAUDE_PLUGIN_ROOT at a temp dir whose ``hooks/check_diff.py`` is a
    stub that dumps ``sys.argv`` (minus argv[0]) as JSON to a sentinel file, so
    we can assert which flags the wrapper forwards under a given environment.
    Returns [] if the wrapper short-circuited (exit 0 without exec).
    """
    if not shutil.which("bash"):
        pytest.skip("bash not on PATH")
    if not shutil.which("pragma"):
        pytest.skip("pragma not on PATH (wrapper would short-circuit)")

    plugin_root = tmp_path / "plugin_root"
    (plugin_root / "hooks").mkdir(parents=True)
    sentinel = tmp_path / "argv.json"
    stub = plugin_root / "hooks" / "check_diff.py"
    stub.write_text(
        f"import json, sys\nopen({str(sentinel)!r}, 'w').write(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )

    test_file = tmp_path / "tests" / "test_thing.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_thing():\n    assert True\n", encoding="utf-8")

    payload = '{"tool_name": "Edit", "tool_input": {"file_path": "' + str(test_file) + '"}}'
    env = {**__import__("os").environ, "CLAUDE_PLUGIN_ROOT": str(plugin_root), **extra_env}
    subprocess.run(
        ["bash", str(POST_TOOL_USE)],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if not sentinel.exists():
        return []
    import json as _json

    return _json.loads(sentinel.read_text(encoding="utf-8"))


def test_post_tool_use_omits_coverage_without_opt_in(tmp_path: Path) -> None:
    """With no PRAGMA_COVERAGE set, the wrapper must NOT forward --with-coverage."""
    argv = _run_post_tool_use_argv(tmp_path, {})
    assert argv, "stub check_diff.py was never invoked"
    assert "--with-coverage" not in argv, f"coverage leaked without opt-in: {argv}"


def test_post_tool_use_forwards_coverage_when_opted_in(tmp_path: Path) -> None:
    """With PRAGMA_COVERAGE=1, the wrapper must forward --with-coverage."""
    argv = _run_post_tool_use_argv(tmp_path, {"PRAGMA_COVERAGE": "1"})
    assert argv, "stub check_diff.py was never invoked"
    assert "--with-coverage" in argv, f"coverage not forwarded on opt-in: {argv}"


# ---------------------------------------------------------------------------
# Unit tests for --with-llm flag plumbing
# ---------------------------------------------------------------------------


def test_run_pragma_includes_with_llm_flag(tmp_path: Path) -> None:
    """_run_pragma(path, with_llm=True) must include --with-llm in argv."""
    mod = _import_check_diff()
    fake_file = tmp_path / "test_x.py"
    fake_file.write_text("def test_x(): pass\n")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        r = MagicMock()
        r.stdout = "{}"
        return r

    with patch("subprocess.run", side_effect=fake_run):
        mod._run_pragma(fake_file, with_llm=True)

    assert calls, "subprocess.run was never called"
    first_call = calls[0]
    assert "--with-llm" in first_call, f"--with-llm not found in argv: {first_call}"


def test_run_pragma_excludes_with_llm_flag_when_false(tmp_path: Path) -> None:
    """_run_pragma(path, with_llm=False) must NOT include --with-llm."""
    mod = _import_check_diff()
    fake_file = tmp_path / "test_x.py"
    fake_file.write_text("def test_x(): pass\n")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        r = MagicMock()
        r.stdout = "{}"
        return r

    with patch("subprocess.run", side_effect=fake_run):
        mod._run_pragma(fake_file, with_llm=False)

    assert calls, "subprocess.run was never called"
    first_call = calls[0]
    assert "--with-llm" not in first_call, f"--with-llm unexpectedly found in argv: {first_call}"


def test_run_pragma_default_excludes_with_llm_flag(tmp_path: Path) -> None:
    """_run_pragma(path) with no kwarg must NOT include --with-llm (backward compat)."""
    mod = _import_check_diff()
    fake_file = tmp_path / "test_x.py"
    fake_file.write_text("def test_x(): pass\n")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        r = MagicMock()
        r.stdout = "{}"
        return r

    with patch("subprocess.run", side_effect=fake_run):
        mod._run_pragma(fake_file)

    assert calls, "subprocess.run was never called"
    first_call = calls[0]
    assert "--with-llm" not in first_call, (
        f"--with-llm unexpectedly found in default argv: {first_call}"
    )


def test_main_parses_with_llm_flag_and_forwards(tmp_path: Path) -> None:
    """main() with --with-llm must call _run_pragma with with_llm=True."""
    mod = _import_check_diff()
    fake_file = tmp_path / "test_x.py"
    fake_file.write_text("def test_x(): pass\n")

    captured_kwargs = []

    def fake_run_pragma(path, *, with_coverage=False, with_llm=False):
        captured_kwargs.append({"path": path, "with_coverage": with_coverage, "with_llm": with_llm})
        return {}

    with patch.object(mod, "_run_pragma", side_effect=fake_run_pragma):
        mod.main(["check_diff", str(fake_file), str(fake_file), "--with-llm"])

    assert captured_kwargs, "_run_pragma was never called"
    assert captured_kwargs[0]["with_llm"] is True, (
        f"Expected with_llm=True, got: {captured_kwargs[0]}"
    )


def test_main_without_llm_flag_calls_run_pragma_with_llm_false(tmp_path: Path) -> None:
    """main() without --with-llm must call _run_pragma with with_llm=False."""
    mod = _import_check_diff()
    fake_file = tmp_path / "test_x.py"
    fake_file.write_text("def test_x(): pass\n")

    captured_kwargs = []

    def fake_run_pragma(path, *, with_coverage=False, with_llm=False):
        captured_kwargs.append({"path": path, "with_coverage": with_coverage, "with_llm": with_llm})
        return {}

    with patch.object(mod, "_run_pragma", side_effect=fake_run_pragma):
        mod.main(["check_diff", str(fake_file), str(fake_file)])

    assert captured_kwargs, "_run_pragma was never called"
    assert captured_kwargs[0]["with_llm"] is False, (
        f"Expected with_llm=False, got: {captured_kwargs[0]}"
    )


def test_post_tool_use_sh_supports_pragma_hook_with_llm() -> None:
    """post-tool-use.sh must reference PRAGMA_HOOK_WITH_LLM and --with-llm."""
    script = (REPO_ROOT / "plugin" / "hooks" / "post-tool-use.sh").read_text()
    assert "PRAGMA_HOOK_WITH_LLM" in script, (
        "post-tool-use.sh must respect PRAGMA_HOOK_WITH_LLM opt-in env var"
    )
    assert "--with-llm" in script, (
        "post-tool-use.sh must pass --with-llm to check_diff.py when PRAGMA_HOOK_WITH_LLM=1"
    )
