from __future__ import annotations

from pathlib import Path

import pytest

from pragma.hooks.post_tool_use import handle


def _project(tmp_path: Path) -> Path:
    import yaml

    manifest = {
        "version": "2",
        "project": {
            "name": "d",
            "mode": "brownfield",
            "language": "python",
            "source_root": "src/",
            "tests_root": "tests/",
        },
        "requirements": [],
    }
    (tmp_path / "pragma.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    (tmp_path / "src").mkdir()
    return tmp_path


def test_allow_clean_file(tmp_path: Path) -> None:
    p = _project(tmp_path)
    src = p / "src" / "ok.py"
    src.write_text("def f(x): return x\n", encoding="utf-8")
    out = handle(
        {"tool_input": {"file_path": "src/ok.py"}},
        p,
    )
    assert out.get("decision") != "block"


def test_block_on_complexity_violation(tmp_path: Path) -> None:
    p = _project(tmp_path)
    src = p / "src" / "bad.py"
    branches = "\n    ".join(f"if x == {i}: return {i}" for i in range(11))
    src.write_text(f"def f(x):\n    {branches}\n    return -1\n", encoding="utf-8")
    out = handle(
        {"tool_input": {"file_path": "src/bad.py"}},
        p,
    )
    assert out["decision"] == "block"
    assert "complexity" in out["reason"].lower()


def test_non_src_file_skipped(tmp_path: Path) -> None:
    p = _project(tmp_path)
    (p / "notes.py").write_text(
        "\n".join(f"x{i} = {i}" for i in range(500)),
        encoding="utf-8",
    )
    out = handle({"tool_input": {"file_path": "notes.py"}}, p)
    assert out.get("decision") != "block"


def test_non_python_file_skipped(tmp_path: Path) -> None:
    p = _project(tmp_path)
    out = handle({"tool_input": {"file_path": "src/data.json"}}, p)
    assert out.get("decision") != "block"
