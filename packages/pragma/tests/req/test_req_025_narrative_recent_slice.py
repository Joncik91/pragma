"""Red tests for REQ-025 — narrative commit remembers shipped slice.

BUG-027. Between `pragma slice complete` and the next
`pragma slice activate`, state.active_slice is None but state.slices
holds the just-shipped records. `pragma narrative commit` in that
window emitted the generic "outside any active slice" WHY, reading
as amnesia. Also _summarise_files appended "/" to every segment of
its "N files across ..." summary — top-level files looked like
directories ("pragma.yaml/" instead of "pragma.yaml").
"""

from __future__ import annotations

from pathlib import Path

from pragma_sdk import set_permutation, trace

from pragma.narrative.commit import _summarise_files, build_commit_message


def _minimal_project_with_shipped_slice(tmp_path: Path) -> None:
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
            "    description: returns greeting\n"
            "    expected: success\n"
            "  milestone: M01\n"
            "  slice: M01.S1\n"
        ),
        encoding="utf-8",
    )
    # active_slice is None (slice just shipped) but state.slices has the record.
    (tmp_path / ".pragma" / "state.json").write_text(
        (
            '{"version":1,"active_slice":null,"gate":null,'
            '"manifest_hash":"sha256:' + "0" * 64 + '",'
            '"slices":{"M01.S1":{"status":"shipped","gate":null,'
            '"activated_at":"2026-01-01T00:00:00Z",'
            '"unlocked_at":"2026-01-01T00:01:00Z",'
            '"completed_at":"2026-01-01T00:02:00Z"}},'
            '"last_transition":{"event":"slice_completed",'
            '"at":"2026-01-01T00:02:00Z",'
            '"reason":"pragma slice complete (slice M01.S1)",'
            '"from_gate":"UNLOCKED","to_gate":null,"slice":"M01.S1"}}'
        ),
        encoding="utf-8",
    )


@trace("REQ-025")
def _assert_why_uses_recent_shipped_when_no_active_slice(tmp_path: Path) -> None:
    _minimal_project_with_shipped_slice(tmp_path)
    msg = build_commit_message(
        cwd=tmp_path,
        staged_files=["src/greeter.py", "tests/test_req_001_greeter.py"],
        subject_hint="feat(m01.s1): greeter",
        why_hint=None,
    )
    assert "Maintenance change outside any active slice." not in msg, (
        f"WHY must not fall back to the amnesia placeholder when a slice "
        f"was just shipped; got:\n{msg}"
    )
    assert "Name greeter" in msg or "M01.S1" in msg, (
        f"WHY must cite the just-shipped slice (title or id); got:\n{msg}"
    )


@trace("REQ-025")
def _assert_summarise_does_not_add_slash_to_top_level_files() -> None:
    # 9 entries: 5 top-level files + 4 paths under src/. Triggers the
    # collapsed-summary path (cap=8).
    files = [
        "README.md",
        "pragma.yaml",
        "pragma.lock.json",
        "pytest.ini",
        ".gitignore",
        "src/a.py",
        "src/b.py",
        "src/c.py",
        "src/d.py",
    ]
    summary = _summarise_files(files)
    # Top-level files must NOT have a trailing slash.
    for name in ("README.md", "pragma.yaml", "pragma.lock.json", "pytest.ini", ".gitignore"):
        # The bug form was "README.md/ (1)"; we accept "README.md (1)"
        # or a list form without the spurious slash.
        assert f"{name}/" not in summary, (
            f"summary must not append '/' to top-level file {name!r}; got:\n{summary}"
        )
    # Directory form stays intact.
    assert "src/" in summary, f"src/ directory label missing; got:\n{summary}"


def test_req_025_why_uses_recent_shipped_when_no_active_slice(tmp_path: Path) -> None:
    with set_permutation("why_uses_recent_shipped_when_no_active_slice"):
        _assert_why_uses_recent_shipped_when_no_active_slice(tmp_path)


def test_req_025_summarise_does_not_add_slash_to_top_level_files() -> None:
    with set_permutation("summarise_does_not_add_slash_to_top_level_files"):
        _assert_summarise_does_not_add_slash_to_top_level_files()
