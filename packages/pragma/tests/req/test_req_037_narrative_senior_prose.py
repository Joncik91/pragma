"""Red tests for REQ-037 — narrative commit produces senior-engineer prose.

BUG-026. README headline is "Senior engineer on rails." The earlier
narrative output was mechanical: "WHY: <slice>: 2 permutations declared."
and "WHAT: Touched N file(s)." A reader could not tell what the slice
*was about* from the message — only how many things it counted.

Fix - WHY names REQ titles instead of permutation counts; WHAT lists
each REQ with its title and the per-permutation verdicts so a reader
sees the behaviour that landed without opening the manifest.
"""

from __future__ import annotations

from pathlib import Path

from pragma_sdk import set_permutation, trace


def _project(tmp_path: Path) -> Path:
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
            "    title: Authentication\n"
            "    description: User can log in.\n"
            "    requirements: [REQ-001, REQ-002]\n"
            "requirements:\n"
            "- id: REQ-001\n"
            "  title: User can log in\n"
            "  description: login\n"
            "  touches: [src/auth.py]\n"
            "  permutations:\n"
            "  - id: valid\n"
            "    description: valid creds\n"
            "    expected: success\n"
            "  - id: weak_pw\n"
            "    description: weak password rejected\n"
            "    expected: reject\n"
            "  milestone: M01\n"
            "  slice: M01.S1\n"
            "- id: REQ-002\n"
            "  title: Session token issued\n"
            "  description: jwt\n"
            "  touches: [src/auth.py]\n"
            "  permutations:\n"
            "  - id: jwt_returned\n"
            "    description: jwt on success\n"
            "    expected: success\n"
            "  milestone: M01\n"
            "  slice: M01.S1\n"
        ),
        encoding="utf-8",
    )
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
    return tmp_path


@trace("REQ-037")
def _assert_why_names_req_titles(tmp_path: Path) -> None:
    from pragma.narrative.commit import build_commit_message

    _project(tmp_path)
    msg = build_commit_message(
        cwd=tmp_path,
        staged_files=["src/auth.py"],
        subject_hint="feat(m01.s1): auth",
        why_hint=None,
    )
    assert "User can log in" in msg, (
        f"WHY must name the REQ-001 title to be more than a perm count; got:\n{msg}"
    )
    assert "Session token issued" in msg, (
        f"WHY must name the REQ-002 title for multi-REQ slices; got:\n{msg}"
    )


@trace("REQ-037")
def _assert_what_lists_reqs_with_perms(tmp_path: Path) -> None:
    from pragma.narrative.commit import build_commit_message

    _project(tmp_path)
    msg = build_commit_message(
        cwd=tmp_path,
        staged_files=["src/auth.py"],
        subject_hint="feat(m01.s1): auth",
        why_hint=None,
    )
    assert "REQ-001" in msg and "REQ-002" in msg, (
        f"WHAT must list each REQ in the slice; got:\n{msg}"
    )
    assert "valid=success" in msg or "valid =success" in msg, (
        f"WHAT must show permutation verdicts inline; got:\n{msg}"
    )
    assert "weak_pw=reject" in msg, f"WHAT must show the reject permutation verdict; got:\n{msg}"


def test_req_037_why_names_req_titles(tmp_path: Path) -> None:
    with set_permutation("why_names_req_titles"):
        _assert_why_names_req_titles(tmp_path)


def test_req_037_what_lists_reqs_with_perms(tmp_path: Path) -> None:
    with set_permutation("what_lists_reqs_with_perms"):
        _assert_what_lists_reqs_with_perms(tmp_path)
