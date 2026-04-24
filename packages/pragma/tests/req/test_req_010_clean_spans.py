"""Dogfood tests for REQ-010 - `pragma doctor --clean-spans` retention.

`.pragma/spans/*.jsonl` accumulates one file per pytest run and was
called out as a v1.0.4-parked paper cut ("accumulates forever; doctor
should offer cleanup"). v1.0.5 closes it: retention policy via
manifest `spans_retention:` or CLI flags `--keep-runs` / `--keep-days`,
`--dry-run` for preview, `spans_cleaned` audit event on real runs,
and `doctor` base-mode reports `spans_count` + `spans_bytes` so users
see accumulation before it hurts.

Wrapped in @trace("REQ-010") so spans carry logic_id=REQ-010 and the
PIL aggregator does not tag these as mocked.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from pragma_sdk import set_permutation, trace
from typer.testing import CliRunner

from pragma.__main__ import app
from pragma.core.audit import read_audit
from pragma.core.spans import (
    DEFAULT_KEEP_RUNS,
    SpansRetention,
    clean_spans,
    span_files,
    summarize_spans,
)

runner = CliRunner()


def _seed_spans(spans_dir: Path, count: int, *, mtime_offset_days: float = 0.0) -> list[Path]:
    """Create `count` span JSONL files with monotonically increasing mtime.

    Oldest file gets lowest mtime. `mtime_offset_days` shifts the whole
    batch into the past (positive value => older).
    """
    spans_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()
    written: list[Path] = []
    for i in range(count):
        path = spans_dir / f"test-run-{i:04d}.jsonl"
        path.write_text('{"logic_id":"REQ-010","permutation":"x"}\n', encoding="utf-8")
        # Oldest = i=0, newest = i=count-1. Spread 1 minute apart so ordering is stable.
        mtime = now - mtime_offset_days * 86400.0 - (count - 1 - i) * 60.0
        import os

        os.utime(path, (mtime, mtime))
        written.append(path)
    return written


@trace("REQ-010")
def _assert_keep_runs_removes_oldest(tmp_path: Path) -> None:
    spans = tmp_path / ".pragma" / "spans"
    seeded = _seed_spans(spans, count=5)
    report = clean_spans(
        pragma_dir=tmp_path / ".pragma",
        retention=SpansRetention(keep_runs=2),
        dry_run=False,
    )
    remaining = sorted(span_files(spans))
    assert len(remaining) == 2
    # Kept: two newest (index 3, 4). Removed: three oldest (index 0, 1, 2).
    assert seeded[3] in remaining and seeded[4] in remaining
    for p in seeded[:3]:
        assert not p.exists()
    assert report.files_removed == 3
    assert report.strategy == "keep_runs=2"


@trace("REQ-010")
def _assert_keep_days_respects_mtime(tmp_path: Path) -> None:
    spans = tmp_path / ".pragma" / "spans"
    # 2 files from 10 days ago (should be removed with keep_days=3),
    # 2 files from 1 day ago (should be kept).
    old = _seed_spans(spans, count=2, mtime_offset_days=10.0)
    # Rename so mtimes don't collide on name order but do on time.
    for idx, p in enumerate(old):
        p.rename(p.with_name(f"old-{idx}.jsonl"))
    new = _seed_spans(spans, count=2, mtime_offset_days=1.0)
    for idx, p in enumerate(new):
        p.rename(p.with_name(f"new-{idx}.jsonl"))

    report = clean_spans(
        pragma_dir=tmp_path / ".pragma",
        retention=SpansRetention(keep_days=3),
        dry_run=False,
    )
    names = {p.name for p in span_files(spans)}
    assert names == {"new-0.jsonl", "new-1.jsonl"}
    assert report.files_removed == 2
    assert report.strategy == "keep_days=3"


@trace("REQ-010")
def _assert_dry_run_is_noop(tmp_path: Path) -> None:
    spans = tmp_path / ".pragma" / "spans"
    seeded = _seed_spans(spans, count=5)
    report = clean_spans(
        pragma_dir=tmp_path / ".pragma",
        retention=SpansRetention(keep_runs=2),
        dry_run=True,
    )
    assert report.files_removed == 3
    # Nothing actually deleted:
    for p in seeded:
        assert p.exists()
    assert report.dry_run is True


@trace("REQ-010")
def _assert_default_keep_runs_50(tmp_path: Path) -> None:
    assert DEFAULT_KEEP_RUNS == 50
    spans = tmp_path / ".pragma" / "spans"
    _seed_spans(spans, count=55)
    report = clean_spans(
        pragma_dir=tmp_path / ".pragma",
        retention=SpansRetention(),  # empty = use defaults
        dry_run=False,
    )
    assert report.files_removed == 5  # 55 - 50
    assert len(list(span_files(spans))) == 50
    assert report.strategy == "keep_runs=50"


@trace("REQ-010")
def _assert_manifest_config_used(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_project)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "example"]).exit_code == 0
    # Inject spans_retention into the manifest.
    manifest_path = tmp_project / "pragma.yaml"
    text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(text + "spans_retention:\n  keep_runs: 3\n", encoding="utf-8")
    assert runner.invoke(app, ["freeze"]).exit_code == 0

    spans = tmp_project / ".pragma" / "spans"
    _seed_spans(spans, count=10)
    result = runner.invoke(app, ["doctor", "--clean-spans"])
    assert result.exit_code == 0, result.stdout
    parsed = json.loads(result.stdout)
    assert parsed["ok"] is True
    assert parsed["action"] == "clean_spans"
    assert parsed["files_removed"] == 7  # 10 - 3
    assert parsed["strategy"] == "keep_runs=3"


@trace("REQ-010")
def _assert_audit_event_appended(tmp_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_project)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "example"]).exit_code == 0
    spans = tmp_project / ".pragma" / "spans"
    _seed_spans(spans, count=5)
    result = runner.invoke(app, ["doctor", "--clean-spans", "--keep-runs", "1"])
    assert result.exit_code == 0, result.stdout
    events = [e for e in read_audit(tmp_project / ".pragma") if e["event"] == "spans_cleaned"]
    assert len(events) == 1
    ctx = events[0]["context"]
    assert ctx["files_removed"] == 4
    assert ctx["strategy"] == "keep_runs=1"
    assert ctx["bytes_freed"] > 0


@trace("REQ-010")
def _assert_doctor_base_reports_spans_stats(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_project)
    assert runner.invoke(app, ["init", "--brownfield", "--name", "example"]).exit_code == 0
    spans = tmp_project / ".pragma" / "spans"
    _seed_spans(spans, count=3)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["spans_count"] == 3
    assert parsed["spans_bytes"] > 0


def test_req_010_clean_spans_keep_runs_removes_oldest(tmp_path: Path) -> None:
    with set_permutation("clean_spans_keep_runs_removes_oldest"):
        _assert_keep_runs_removes_oldest(tmp_path)


def test_req_010_clean_spans_keep_days_respects_mtime(tmp_path: Path) -> None:
    with set_permutation("clean_spans_keep_days_respects_mtime"):
        _assert_keep_days_respects_mtime(tmp_path)


def test_req_010_clean_spans_dry_run_no_fs_change(tmp_path: Path) -> None:
    with set_permutation("clean_spans_dry_run_no_fs_change"):
        _assert_dry_run_is_noop(tmp_path)


def test_req_010_clean_spans_default_keep_runs_50(tmp_path: Path) -> None:
    with set_permutation("clean_spans_default_keep_runs_50"):
        _assert_default_keep_runs_50(tmp_path)


def test_req_010_clean_spans_manifest_config_used(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("clean_spans_manifest_config_used"):
        _assert_manifest_config_used(tmp_project, monkeypatch)


def test_req_010_clean_spans_audit_event_appended(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("clean_spans_audit_event_appended"):
        _assert_audit_event_appended(tmp_project, monkeypatch)


def test_req_010_doctor_base_reports_spans_stats(
    tmp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with set_permutation("doctor_base_reports_spans_stats"):
        _assert_doctor_base_reports_spans_stats(tmp_project, monkeypatch)


def _verify_summarize() -> None:
    """Smoke: summarize_spans returns the expected shape."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        spans = Path(td) / "spans"
        _seed_spans(spans, count=2)
        info = summarize_spans(spans)
        assert info.count == 2
        assert info.bytes_total > 0


def test_req_010_summarize_spans_smoke(tmp_path: Path) -> None:
    # Doesn't need a permutation — helper smoke test.
    _verify_summarize()
