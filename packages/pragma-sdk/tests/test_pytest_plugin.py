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


def test_plugin_preserves_spans_from_prior_runs(tmp_path: Path) -> None:
    """Running pytest twice in the same cwd must preserve spans from both runs.

    Before KI-1, the plugin wrote to a fixed test-run.jsonl and the
    second run overwrote the first. Any project with more than one
    test suite (pragma + pragma-sdk, pre-commit hook + CI re-run,
    etc.) saw PIL collapse to 0/N as soon as the second suite ran.
    The v1.0.2 contract: every pytest invocation lands in its own
    per-session file under .pragma/spans/, and aggregators read
    every *.jsonl in the directory.
    """
    test_a = tmp_path / "test_a.py"
    test_a.write_text(
        "from pragma_sdk import trace\n"
        "@trace('REQ-001')\n"
        "def do_a(): pass\n"
        "def test_it_a():\n"
        "    do_a()\n",
        encoding="utf-8",
    )
    test_b = tmp_path / "test_b.py"
    test_b.write_text(
        "from pragma_sdk import trace\n"
        "@trace('REQ-002')\n"
        "def do_b(): pass\n"
        "def test_it_b():\n"
        "    do_b()\n",
        encoding="utf-8",
    )
    (tmp_path / ".pragma").mkdir()

    for test_file in (test_a, test_b):
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-q"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr

    span_dir = tmp_path / ".pragma" / "spans"
    files = sorted(span_dir.glob("*.jsonl"))
    # Two invocations -> two files (one per session).
    assert len(files) == 2

    all_logic_ids = set()
    for f in files:
        for line in f.read_text(encoding="utf-8").strip().splitlines():
            if line:
                all_logic_ids.add(json.loads(line)["attrs"]["pragma.logic_id"])
    assert all_logic_ids == {"REQ-001", "REQ-002"}
