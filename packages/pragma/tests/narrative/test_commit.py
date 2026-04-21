from __future__ import annotations

from pathlib import Path

import yaml

from pragma.core.commits import validate_commit_shape
from pragma.narrative.commit import build_commit_message


def test_commit_output_passes_verify(tmp_path: Path) -> None:
    """build_commit_message produces output that passes validate_commit_shape."""
    manifest = {
        "version": "2",
        "project": {
            "name": "demo",
            "mode": "brownfield",
            "language": "python",
            "source_root": "src/",
            "tests_root": "tests/",
        },
        "milestones": [
            {
                "id": "M01",
                "title": "Core",
                "description": "Core features.",
                "depends_on": [],
                "slices": [
                    {
                        "id": "M01.S1",
                        "title": "First slice",
                        "description": "First deliverable.",
                        "requirements": ["REQ-001"],
                    }
                ],
            }
        ],
        "requirements": [
            {
                "id": "REQ-001",
                "title": "Do a thing",
                "description": "The system does a thing that is important.",
                "touches": ["src/demo/thing.py"],
                "permutations": [
                    {"id": "happy", "description": "happy path", "expected": "success"},
                ],
                "milestone": "M01",
                "slice": "M01.S1",
            }
        ],
    }
    (tmp_path / "pragma.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    (tmp_path / ".pragma").mkdir()

    msg = build_commit_message(
        cwd=tmp_path,
        staged_files=["src/demo/thing.py", "tests/test_thing.py"],
        subject_hint="feat(thing): add thing processing",
        why_hint=None,
    )
    errors = validate_commit_shape(msg)
    assert errors == [], [f"{e.rule}: {e.remediation}" for e in errors]
    assert "WHY:" in msg
    assert "WHERE:" in msg
    assert "Co-Authored-By:" in msg
