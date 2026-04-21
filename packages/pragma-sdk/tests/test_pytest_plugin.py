from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_plugin_dumps_spans_to_jsonl(tmp_path: Path) -> None:
    """Run a subprocess pytest that uses pragma_sdk; verify JSONL exists."""
    test_file = tmp_path / "test_fake.py"
    test_file.write_text(
        "from pragma_sdk import trace\n"
        "@trace('REQ-042')\n"
        "def do(): pass\n"
        "def test_it():\n"
        "    do()\n",
        encoding="utf-8",
    )
    (tmp_path / ".pragma").mkdir()

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "-q"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    span_dir = tmp_path / ".pragma" / "spans"
    assert span_dir.exists()
    files = list(span_dir.glob("*.jsonl"))
    assert len(files) == 1

    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["attrs"]["pragma.logic_id"] == "REQ-042"
    assert payload["span_name"] == "REQ-042:do"
    assert "test_it" in payload["test_nodeid"]
