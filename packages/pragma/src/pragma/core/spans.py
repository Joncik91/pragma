"""Span-file retention for `.pragma/spans/*.jsonl`.

The v0.4 SDK writes one JSONL per pytest run (post-KI-1 each run gets a
unique `test-run-{ts}-{pid}-{uuid}.jsonl` name). On a long-running
project the directory grows without bound; v1.0.4's changelog parked a
cleanup (``span-file pruning — doctor should offer cleanup``) and
REQ-010 closes it.

Two retention strategies, both optional, both CLI- and manifest-
configurable:

- ``keep_runs`` — keep the N newest files (by mtime), remove the rest.
- ``keep_days`` — keep files whose mtime is within D days, remove older.

Defaults to ``keep_runs=50`` when neither CLI flag nor manifest config
is present. CLI flags override manifest config for the one invocation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import time

from pragma_sdk import trace

DEFAULT_KEEP_RUNS = 50
SPANS_SUBDIR = "spans"


@dataclass(frozen=True)
class SpansRetention:
    """Retention policy for `.pragma/spans/`.

    If both ``keep_runs`` and ``keep_days`` are set, files are kept iff
    they satisfy *either* rule (union — the more lenient wins).
    If both are ``None``, DEFAULT_KEEP_RUNS applies.
    """

    keep_runs: int | None = None
    keep_days: float | None = None


@dataclass(frozen=True)
class SpansSummary:
    count: int
    bytes_total: int


@dataclass(frozen=True)
class CleanReport:
    files_removed: int
    bytes_freed: int
    strategy: str
    dry_run: bool
    removed_paths: tuple[Path, ...] = field(default_factory=tuple)


def span_files(spans_dir: Path) -> list[Path]:
    """Return all `*.jsonl` files under `spans_dir`. Empty list if absent."""
    if not spans_dir.exists():
        return []
    return [p for p in spans_dir.iterdir() if p.is_file() and p.suffix == ".jsonl"]


def summarize_spans(spans_dir: Path) -> SpansSummary:
    files = span_files(spans_dir)
    total = sum(p.stat().st_size for p in files)
    return SpansSummary(count=len(files), bytes_total=total)


def _resolve_strategy(retention: SpansRetention) -> tuple[str, SpansRetention]:
    """Apply DEFAULT_KEEP_RUNS when neither field is set. Return (strategy_label, effective)."""
    if retention.keep_runs is None and retention.keep_days is None:
        effective = SpansRetention(keep_runs=DEFAULT_KEEP_RUNS)
    else:
        effective = retention
    parts: list[str] = []
    if effective.keep_runs is not None:
        parts.append(f"keep_runs={effective.keep_runs}")
    if effective.keep_days is not None:
        parts.append(f"keep_days={effective.keep_days:g}")
    return ",".join(parts), effective


def _files_to_remove(files: list[Path], retention: SpansRetention) -> list[Path]:
    """Return the subset of `files` that should be deleted under `retention`.

    A file is *kept* iff it satisfies at least one active rule.
    """
    if not files:
        return []
    stats = [(p, p.stat().st_mtime, p.stat().st_size) for p in files]

    # Build the kept-set.
    kept: set[Path] = set()

    if retention.keep_runs is not None:
        # Keep N newest by mtime. Tiebreak by path for determinism.
        ordered = sorted(stats, key=lambda t: (t[1], str(t[0])), reverse=True)
        for p, _, _ in ordered[: retention.keep_runs]:
            kept.add(p)

    if retention.keep_days is not None:
        cutoff = time() - retention.keep_days * 86400.0
        for p, mtime, _ in stats:
            if mtime >= cutoff:
                kept.add(p)

    return [p for p, _, _ in stats if p not in kept]


@trace("REQ-010")
def clean_spans(
    *,
    pragma_dir: Path,
    retention: SpansRetention,
    dry_run: bool,
) -> CleanReport:
    """Apply retention policy. Return report; if dry_run, no fs changes."""
    spans_dir = pragma_dir / SPANS_SUBDIR
    files = span_files(spans_dir)
    strategy, effective = _resolve_strategy(retention)
    to_remove = _files_to_remove(files, effective)
    # Determinism: sort removals lexicographically.
    to_remove_sorted = sorted(to_remove, key=lambda p: str(p))

    bytes_freed = sum(p.stat().st_size for p in to_remove_sorted)
    if not dry_run:
        for p in to_remove_sorted:
            p.unlink()

    return CleanReport(
        files_removed=len(to_remove_sorted),
        bytes_freed=bytes_freed,
        strategy=strategy,
        dry_run=dry_run,
        removed_paths=tuple(to_remove_sorted),
    )
