"""Shared pytest fixtures for Pragma's own test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


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
