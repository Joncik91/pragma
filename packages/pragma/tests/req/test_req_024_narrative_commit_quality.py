"""Red tests for REQ-024 — narrative commit filters noise + real WHY.

BUG-026. `pragma narrative commit` shipped a valid-shape message
but its WHAT / WHERE listed every staged file including `.pyc`,
`__pycache__/`, `.pragma/state.json.lock`, `.pragma/audit.jsonl`,
etc. WHY was either a blind first-line echo or a placeholder
string.

Fix: filter non-source/cache entries from the file list; when a
slice is active, derive WHY from slice.title + the declared
permutation verdict counts.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace


def _minimal_project(tmp_path: Path) -> Path:
    """Scaffold a minimal project with one active slice + one REQ."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".pragma").mkdir()
    (tmp_path / "pragma.yaml").write_text(
        (
            "version: '2'\n"
            "project:\n"
            "  name: demo\n"
            "  mode: greenfield\n"
            "  language: python\n"
            "  source_root: src/\n"
            "  tests_root: tests/\n"
            "milestones:\n"
            "- id: M01\n"
            "  title: m\n"
            "  description: m\n"
            "  depends_on: []\n"
            "  slices:\n"
            "  - id: M01.S1\n"
            "    title: Name greeter\n"
            "    description: Greet a user by name.\n"
            "    requirements: [REQ-001]\n"
            "requirements:\n"
            "- id: REQ-001\n"
            "  title: greet\n"
            "  description: greet\n"
            "  touches: [src/greeter.py]\n"
            "  permutations:\n"
            "  - id: valid\n"
            "    description: greet('Ada') returns greeting\n"
            "    expected: success\n"
            "  - id: empty_rejected\n"
            "    description: empty name raises ValueError\n"
            "    expected: reject\n"
            "  milestone: M01\n"
            "  slice: M01.S1\n"
        ),
        encoding="utf-8",
    )
    return tmp_path


def _active_state(tmp_path: Path) -> None:
    (tmp_path / ".pragma" / "state.json").write_text(
        (
            '{"version":1,"active_slice":"M01.S1","gate":"UNLOCKED",'
            '"manifest_hash":"sha256:' + "0" * 64 + '","slices":{"M01.S1":'
            '{"status":"in_progress","gate":"UNLOCKED",'
            '"activated_at":"2026-01-01T00:00:00Z",'
            '"unlocked_at":"2026-01-01T00:00:00Z",'
            '"completed_at":null}},"last_transition":null}'
        ),
        encoding="utf-8",
    )


@trace("REQ-024")
def _assert_filters_noise_files(tmp_path: Path) -> None:
    from pragma.narrative.commit import build_commit_message

    _minimal_project(tmp_path)
    _active_state(tmp_path)
    # Simulated staged list exactly as the dogfood saw it.
    staged = [
        ".claude/settings.json",
        ".gitignore",
        ".pragma/audit.jsonl",
        ".pragma/claude-settings.hash",
        ".pragma/state.json.lock",
        ".pre-commit-config.yaml",
        "PRAGMA.md",
        "claude.md",
        "pragma.lock.json",
        "pragma.yaml",
        "pytest.ini",
        "src/__pycache__/identity_mod.cpython-313.pyc",
        "src/__pycache__/validator_mod.cpython-313.pyc",
        "src/identity_mod.py",
        "src/validator_mod.py",
        "tests/__pycache__/conftest.cpython-313-pytest-9.0.3.pyc",
        "tests/__pycache__/test_req_001_identity.cpython-313-pytest-9.0.3.pyc",
        "tests/__pycache__/test_req_002_validator.cpython-313-pytest-9.0.3.pyc",
        "tests/conftest.py",
        "tests/test_req_001_identity.py",
        "tests/test_req_002_validator.py",
    ]
    msg = build_commit_message(
        cwd=tmp_path,
        staged_files=staged,
        subject_hint="feat(m01): test commit",
        why_hint=None,
    )
    # Noise must be gone.
    for noise in (
        ".pyc",
        "__pycache__",
        ".pragma/audit.jsonl",
        ".pragma/state.json.lock",
        ".pragma/claude-settings.hash",
    ):
        assert noise not in msg, f"commit message must not mention {noise!r}; got:\n{msg}"
    # Real source files must still appear (or their summary).
    assert "src/" in msg or "identity_mod.py" in msg or "validator_mod.py" in msg, (
        f"commit message must summarise real source changes; got:\n{msg}"
    )


@trace("REQ-024")
def _assert_why_derived_from_active_slice(tmp_path: Path) -> None:
    from pragma.narrative.commit import build_commit_message

    _minimal_project(tmp_path)
    _active_state(tmp_path)
    msg = build_commit_message(
        cwd=tmp_path,
        staged_files=["src/greeter.py", "tests/test_req_001_greeter.py"],
        subject_hint="feat(m01.s1): greeter",
        why_hint=None,
    )
    # WHY must reference slice title.
    assert "Name greeter" in msg, f"WHY must cite the active slice title; got:\n{msg}"
    # And should reference what landed: either the REQ title (BUG-026 / REQ-037
    # senior-engineer prose) or a permutation count (older, more mechanical
    # shape). Either is honest as long as it isn't the placeholder.
    assert "greet" in msg or "permutation" in msg, (
        f"WHY must say what the slice is about; got:\n{msg}"
    )


@trace("REQ-024")
def _assert_handles_no_active_slice(tmp_path: Path) -> None:
    from pragma.narrative.commit import build_commit_message

    _minimal_project(tmp_path)
    # No .pragma/state.json written — no active slice.
    msg = build_commit_message(
        cwd=tmp_path,
        staged_files=["src/greeter.py"],
        subject_hint="chore: no slice",
        why_hint=None,
    )
    # Must still include WHY and Co-Authored-By trailer so pragma
    # verify message stays happy.
    assert "WHY:" in msg
    assert "Co-Authored-By:" in msg
    # And the placeholder string that shipped on v0.1.0 should be gone —
    # even without a slice, WHY should be informative (the pragma repo
    # or the absence of an active slice is a fact the message can use).
    assert "Scope unclear; filling in." not in msg, (
        f"fallback WHY must not be a placeholder; got:\n{msg}"
    )


def test_req_024_filters_noise_files(tmp_path: Path) -> None:
    with set_permutation("filters_noise_files"):
        _assert_filters_noise_files(tmp_path)


def test_req_024_why_derived_from_active_slice(tmp_path: Path) -> None:
    with set_permutation("why_derived_from_active_slice"):
        _assert_why_derived_from_active_slice(tmp_path)


def test_req_024_handles_no_active_slice(tmp_path: Path) -> None:
    with set_permutation("handles_no_active_slice"):
        _assert_handles_no_active_slice(tmp_path)


def test_req_024_no_pytest_fixtures_unused() -> None:
    # Silences pyflakes on the unused `pytest` import above.
    assert pytest is not None
