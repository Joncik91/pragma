"""Red tests for REQ-041 — remediation strings reference real surface.

Edge-case dogfood (round 19) found three remediation-string defects:

- BUG-049: PIL `mocked` remediation references nonexistent
  `pragma spec mark-mocked` subcommand. Real solution is to wrap the
  test in `with set_permutation('<id>'):` — the SDK already provides it.
- BUG-051: `pragma slice activate <unknown>` did not list the declared
  slice ids. `add-requirement --slice` already does; should be
  consistent.
- BUG-050: `pragma init --greenfield` on an already-initialised dir
  said "Remove pragma.yaml manually" without acknowledging --force.
  Greenfield genuinely doesn't support --force (would erase the
  manifest), but the remediation should say so explicitly and point
  at the brownfield --force escape hatch for hooks/templates refresh.
"""

from __future__ import annotations

from pathlib import Path

from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.errors import SliceNotFound
from pragma.core.gate import _locate_slice_or_raise
from pragma.core.models import Manifest, Milestone, Project, Slice
from pragma.report.aggregator import _MOCKED_REMEDIATION

runner = CliRunner()


@trace("REQ-041")
def _assert_mocked_remediation_no_fake_command() -> None:
    template = _MOCKED_REMEDIATION
    assert "mark-mocked" not in template, (
        f"PIL must not cite the nonexistent `spec mark-mocked`; got:\n{template}"
    )
    assert "set_permutation" in template, (
        f"PIL must cite set_permutation as the real fix; got:\n{template}"
    )


@trace("REQ-041")
def _assert_slice_not_found_lists_declared() -> None:
    manifest = Manifest(
        version="2",
        project=Project(
            name="t",
            mode="greenfield",
            language="python",
            source_root="src/",
            tests_root="tests/",
        ),
        milestones=(
            Milestone(
                id="M01",
                title="t",
                description="t",
                slices=(Slice(id="M01.S1", title="t", description="t", requirements=()),),
            ),
        ),
        requirements=(),
    )
    try:
        _locate_slice_or_raise(manifest, "M99.S99")
    except SliceNotFound as exc:
        assert "M01.S1" in exc.remediation, (
            f"slice_not_found remediation must list the declared slice ids; got:\n{exc.remediation}"
        )
    else:
        raise AssertionError("expected SliceNotFound")


@trace("REQ-041")
def _assert_greenfield_already_init_remediation_honest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "--greenfield", "--name", "x", "--language", "python"])
    # Re-init should fail with the new, more helpful remediation.
    result = runner.invoke(app, ["init", "--greenfield", "--name", "x", "--language", "python"])
    assert result.exit_code == 1
    assert "--force" in result.stdout, (
        f"remediation must mention --force scope; got:\n{result.stdout}"
    )
    assert "brownfield --force" in result.stdout, (
        f"remediation must cite brownfield --force as the escape hatch; got:\n{result.stdout}"
    )


def test_req_041_mocked_remediation_no_fake_command() -> None:
    with set_permutation("mocked_remediation_no_fake_command"):
        _assert_mocked_remediation_no_fake_command()


def test_req_041_slice_not_found_lists_declared() -> None:
    with set_permutation("slice_not_found_lists_declared"):
        _assert_slice_not_found_lists_declared()


def test_req_041_greenfield_already_init_remediation_honest(tmp_path: Path, monkeypatch) -> None:
    with set_permutation("greenfield_already_init_remediation_honest"):
        _assert_greenfield_already_init_remediation_honest(tmp_path, monkeypatch)
