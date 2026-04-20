from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


def handle(event_input: dict[str, Any], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "pragma", "verify", "all"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        return {"continue": True}

    reason = proc.stdout.strip().splitlines()[-1] if proc.stdout else "verify all failed"
    return {
        "decision": "block",
        "reason": (
            "Turn cannot end — project is in a half-finished state. "
            f"pragma verify all output: {reason}"
        ),
    }
