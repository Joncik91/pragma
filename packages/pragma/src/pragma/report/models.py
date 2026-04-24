from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class PermutationStatus(StrEnum):
    ok = "ok"
    partial = "partial"
    mocked = "mocked"
    missing = "missing"
    red = "red"
    skipped = "skipped"


class ReportPermutation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    status: PermutationStatus
    test_nodeid: str | None
    span_count: int
    remediation: str | None = None


class ReportRequirement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    title: str
    permutations: tuple[ReportPermutation, ...]


class Report(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    slice: str | None
    gate: str | None
    generated_at: str
    requirements: tuple[ReportRequirement, ...]
    summary: dict[str, int]
    # BUG-020 / REQ-017: surfaced when an input artifact (junit.xml,
    # spans dir) is absent and that absence plausibly explains a wall
    # of `missing` rows. Each entry is a short human-readable string
    # rendered as a banner above the summary in the Markdown report.
    # Empty tuple on the happy path.
    diagnostics: tuple[str, ...] = ()
