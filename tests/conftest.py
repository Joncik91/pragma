"""Shared pytest fixtures for Pragma's own test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Iterator[Path]:
    """An empty directory that stands in for a target project."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    yield tmp_path


@pytest.fixture()
def minimal_valid_yaml() -> str:
    """A minimal brownfield manifest that passes schema validation."""
    return (
        'version: "1"\n'
        "project:\n"
        "  name: example\n"
        "  mode: brownfield\n"
        "  language: python\n"
        "  source_root: src/\n"
        "  tests_root: tests/\n"
        "requirements: []\n"
    )


@pytest.fixture
def v2_manifest_dict() -> dict:
    """A minimal v2 manifest with one milestone, one slice, one requirement."""
    return {
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
                "description": "The system does a thing.",
                "touches": ["src/demo/thing.py"],
                "permutations": [
                    {"id": "happy", "description": "happy path", "expected": "success"},
                    {"id": "sad", "description": "sad path", "expected": "reject"},
                ],
                "milestone": "M01",
                "slice": "M01.S1",
            }
        ],
    }


@pytest.fixture
def v1_manifest_dict() -> dict:
    """A minimal v1 manifest (pre-migration)."""
    return {
        "version": "1",
        "project": {
            "name": "demo",
            "mode": "brownfield",
            "language": "python",
            "source_root": "src/",
            "tests_root": "tests/",
        },
        "requirements": [
            {
                "id": "REQ-001",
                "title": "Do a thing",
                "description": "The system does a thing.",
                "touches": ["src/demo/thing.py"],
                "permutations": [
                    {"id": "happy", "description": "happy path", "expected": "success"}
                ],
            }
        ],
    }


@pytest.fixture
def tmp_project_v2(tmp_path: Path, v2_manifest_dict: dict) -> Path:
    """Project dir containing a valid v2 pragma.yaml + fresh pragma.lock.json."""
    (tmp_path / "pragma.yaml").write_text(
        yaml.safe_dump(v2_manifest_dict, sort_keys=False), encoding="utf-8"
    )
    (tmp_path / ".pragma").mkdir()
    return tmp_path


@pytest.fixture
def tmp_project_v1(tmp_path: Path, v1_manifest_dict: dict) -> Path:
    """Project dir containing a v1 pragma.yaml (pre-migration)."""
    (tmp_path / "pragma.yaml").write_text(
        yaml.safe_dump(v1_manifest_dict, sort_keys=False), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def hook_input_pre_tool_use() -> dict:
    return {
        "session_id": "abc123",
        "tool_name": "Edit",
        "tool_input": {"file_path": "src/example.py", "old_string": "x", "new_string": "y"},
    }


@pytest.fixture
def hook_input_session_start() -> dict:
    return {"session_id": "abc123", "source": "startup"}


@pytest.fixture
def hook_input_post_tool_use() -> dict:
    return {
        "session_id": "abc123",
        "tool_name": "Write",
        "tool_input": {"file_path": "src/example.py", "content": "..."},
        "tool_result": {"success": True},
    }


@pytest.fixture
def hook_input_stop() -> dict:
    return {"session_id": "abc123"}
