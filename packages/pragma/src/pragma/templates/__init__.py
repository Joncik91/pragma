"""Jinja templates copied by `pragma init` into target projects."""

from __future__ import annotations

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent


def template_path(name: str) -> Path:
    """Return the absolute path of a shipped template file."""
    return TEMPLATES_DIR / name
