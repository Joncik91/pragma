from __future__ import annotations

import json
import textwrap
from pathlib import Path

import yaml
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


def _bootstrap(tmp_path: Path, src: dict[str, str]) -> None:
    manifest = {
        "version": "2",
        "project": {
            "name": "demo",
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
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    for name, body in src.items():
        (src_dir / name).write_text(textwrap.dedent(body), encoding="utf-8")


def test_verify_discipline_clean(monkeypatch, tmp_path: Path) -> None:
    _bootstrap(tmp_path, {"ok.py": "def f(x): return x\n"})
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["verify", "discipline"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["ok"] is True


def test_verify_discipline_flags_complexity(monkeypatch, tmp_path: Path) -> None:
    branches = "\n    ".join(f"if x == {i}: return {i}" for i in range(11))
    _bootstrap(
        tmp_path,
        {
            "bad.py": f"def f(x):\n    {branches}\n    return -1\n",
        },
    )
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["verify", "discipline"])
    assert r.exit_code == 1
    payload = json.loads(r.output)
    assert payload["error"] == "discipline_violation"
    rules = [v["rule"] for v in payload["context"]["violations"]]
    assert "complexity" in rules


def test_verify_discipline_lists_multiple_violations(monkeypatch, tmp_path: Path) -> None:
    _bootstrap(
        tmp_path,
        {
            "bad.py": "# TODO: write it\nclass U:\n    def one(self, x): return x\n",
        },
    )
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["verify", "discipline"])
    assert r.exit_code == 1
    violations = json.loads(r.output)["context"]["violations"]
    rules = {v["rule"] for v in violations}
    assert "todo_sentinel" in rules
    assert "single_method_util" in rules
