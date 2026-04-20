from __future__ import annotations

from pathlib import Path


def handle(event_input: dict, cwd: Path) -> dict:
    return {"continue": True}
