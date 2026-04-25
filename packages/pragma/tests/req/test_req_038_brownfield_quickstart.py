"""Red tests for REQ-038 — brownfield README quick-start works end-to-end.

BUG-045. The brownfield section of the README quick-start lands the
user in a dead end:
1. `pragma init --brownfield` writes `version: '1'` schema.
2. `pragma spec add-requirement` accepts `milestone:null, slice:null`.
3. `pragma freeze` succeeds with no slices declared.
4. README's "Ship a slice" step says `pragma slice activate M01.S1`,
   which fails with `slice_not_found` — the brownfield manifest has
   no M01.S1.

Fix - brownfield template ships v2 schema with M00.S0 implicit slice;
add-requirement defaults to the only-declared slice when caller
omits --milestone/--slice. Then the README quick-start works (with a
small README tweak: `M01.S1` → `M00.S0` for brownfield).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app

runner = CliRunner()


@trace("REQ-038")
def _assert_brownfield_emits_v2_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--brownfield"])
    assert result.exit_code == 0, result.stdout
    raw = yaml.safe_load((tmp_path / "pragma.yaml").read_text(encoding="utf-8"))
    assert raw["version"] == "2", f"brownfield template must emit v2 schema; got {raw!r}"
    milestones = raw.get("milestones") or []
    assert len(milestones) == 1, f"brownfield must ship one implicit milestone; got {milestones!r}"
    slices = milestones[0].get("slices") or []
    assert len(slices) == 1, f"brownfield must ship one implicit slice; got {slices!r}"
    assert slices[0]["id"] == "M00.S0", (
        f"implicit brownfield slice id must be M00.S0 (matches migrate); got {slices[0]!r}"
    )


@trace("REQ-038")
def _assert_add_requirement_defaults_to_only_slice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--brownfield"])
    result = runner.invoke(
        app,
        [
            "spec",
            "add-requirement",
            "--id",
            "REQ-001",
            "--title",
            "User can log in",
            "--description",
            "Operator signs in with email + password",
            "--touches",
            "src/auth/login.py",
            "--permutation",
            "valid|valid creds|success",
        ],
    )
    assert result.exit_code == 0, result.stdout
    raw = yaml.safe_load((tmp_path / "pragma.yaml").read_text(encoding="utf-8"))
    req = raw["requirements"][0]
    assert req["milestone"] == "M00", (
        f"REQ without --milestone flag must default to the only-declared milestone; got {req!r}"
    )
    assert req["slice"] == "M00.S0", (
        f"REQ without --slice flag must default to the only-declared slice; got {req!r}"
    )
    slice_reqs = raw["milestones"][0]["slices"][0]["requirements"]
    assert "REQ-001" in slice_reqs, (
        f"slices[*].requirements must list REQ-001 after default-slice add; got {slice_reqs!r}"
    )


@trace("REQ-038")
def _assert_brownfield_slice_activate_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--brownfield"])
    runner.invoke(
        app,
        [
            "spec",
            "add-requirement",
            "--id",
            "REQ-001",
            "--title",
            "x",
            "--description",
            "x",
            "--touches",
            "src/x.py",
            "--permutation",
            "valid|x|success",
        ],
    )
    runner.invoke(app, ["freeze"])
    result = runner.invoke(app, ["slice", "activate", "M00.S0"])
    assert result.exit_code == 0, (
        f"brownfield quick-start must reach slice activate; got {result.stdout!r}"
    )


def test_req_038_brownfield_emits_v2_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("brownfield_emits_v2_schema"):
        _assert_brownfield_emits_v2_schema(tmp_path, monkeypatch)


def test_req_038_add_requirement_defaults_to_only_slice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("add_requirement_defaults_to_only_slice"):
        _assert_add_requirement_defaults_to_only_slice(tmp_path, monkeypatch)


def test_req_038_brownfield_slice_activate_works(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("brownfield_slice_activate_works"):
        _assert_brownfield_slice_activate_works(tmp_path, monkeypatch)
