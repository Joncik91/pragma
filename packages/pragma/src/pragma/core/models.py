"""Pydantic schema for the Logic Manifest.

v0.1 shipped `version: "1"` with a flat requirements list. v0.2 adds
`version: "2"` which optionally declares `milestones:` and `slices:` and
requires each requirement to name its `milestone` and `slice`. v1
manifests are still accepted verbatim — `pragma migrate` upgrades them.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_REQUIREMENT_ID_RE = re.compile(r"REQ-\d{3,4}")
_PERMUTATION_ID_RE = re.compile(r"[a-z][a-z0-9_]*")
_MILESTONE_ID_RE = re.compile(r"M\d{2}")
_SLICE_ID_RE = re.compile(r"M\d{2}\.S\d{1,2}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Project(_StrictModel):
    name: str = Field(min_length=1)
    mode: Literal["brownfield", "greenfield"]
    language: Literal["python"]
    source_root: str = Field(min_length=1)
    tests_root: str = Field(min_length=1)


class Permutation(_StrictModel):
    id: str
    description: str = Field(min_length=1)
    expected: Literal["success", "reject"]

    @field_validator("id")
    @classmethod
    def _validate_permutation_id(cls, v: str) -> str:
        if not _PERMUTATION_ID_RE.fullmatch(v):
            raise ValueError(
                "permutation id must match ^[a-z][a-z0-9_]*$ (lowercase, "
                "starts with letter, no dashes or spaces)"
            )
        return v


class Slice(_StrictModel):
    id: str
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requirements: tuple[Annotated[str, Field(min_length=1)], ...] = Field(default=())

    @field_validator("id")
    @classmethod
    def _validate_slice_id(cls, v: str) -> str:
        if not _SLICE_ID_RE.fullmatch(v):
            raise ValueError("slice id must match ^M\\d{2}\\.S\\d{1,2}$ (e.g. M01.S1, M01.S12)")
        return v


class Milestone(_StrictModel):
    id: str
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    depends_on: tuple[str, ...] = Field(default=())
    slices: tuple[Slice, ...] = Field(default=())

    @field_validator("id")
    @classmethod
    def _validate_milestone_id(cls, v: str) -> str:
        if not _MILESTONE_ID_RE.fullmatch(v):
            raise ValueError("milestone id must match ^M\\d{2}$ (e.g. M01, M02)")
        return v


class Requirement(_StrictModel):
    id: str
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    touches: tuple[Annotated[str, Field(min_length=1)], ...] = Field(min_length=1)
    permutations: tuple[Permutation, ...] = Field(min_length=1)
    milestone: str | None = None
    slice: str | None = None

    @field_validator("id")
    @classmethod
    def _validate_requirement_id(cls, v: str) -> str:
        if not _REQUIREMENT_ID_RE.fullmatch(v):
            raise ValueError("requirement id must match ^REQ-\\d{3,4}$ (e.g. REQ-001, REQ-0017)")
        return v

    @model_validator(mode="after")
    def _check_unique_permutation_ids(self) -> Requirement:
        seen: set[str] = set()
        for perm in self.permutations:
            if perm.id in seen:
                raise ValueError(f"duplicate permutation id: {perm.id!r}")
            seen.add(perm.id)
        return self


class Manifest(_StrictModel):
    version: Literal["1", "2"]
    project: Project
    milestones: tuple[Milestone, ...] = Field(default=())
    requirements: tuple[Requirement, ...] = Field(default=())

    @model_validator(mode="after")
    def _check_unique_requirement_ids(self) -> Manifest:
        seen: set[str] = set()
        for req in self.requirements:
            if req.id in seen:
                raise ValueError(f"duplicate requirement id: {req.id!r}")
            seen.add(req.id)
        return self

    @model_validator(mode="after")
    def _check_unique_milestone_ids(self) -> Manifest:
        seen: set[str] = set()
        for m in self.milestones:
            if m.id in seen:
                raise ValueError(f"duplicate milestone id: {m.id!r}")
            seen.add(m.id)
        return self

    @model_validator(mode="after")
    def _check_unique_slice_ids(self) -> Manifest:
        seen: set[str] = set()
        for m in self.milestones:
            for s in m.slices:
                if s.id in seen:
                    raise ValueError(f"duplicate slice id: {s.id!r}")
                seen.add(s.id)
        return self

    @model_validator(mode="after")
    def _check_milestone_deps(self) -> Manifest:
        declared = {m.id for m in self.milestones}
        for m in self.milestones:
            for dep in m.depends_on:
                if dep not in declared:
                    raise ValueError(
                        f"unknown milestone in depends_on: {dep!r} (milestone {m.id!r})"
                    )
        graph = {m.id: set(m.depends_on) for m in self.milestones}
        WHITE, GRAY, BLACK = 0, 1, 2
        color = dict.fromkeys(graph, WHITE)

        def visit(node: str) -> None:
            color[node] = GRAY
            for nxt in graph[node]:
                if color[nxt] == GRAY:
                    raise ValueError(f"milestone dependency cycle through {node!r}")
                if color[nxt] == WHITE:
                    visit(nxt)
            color[node] = BLACK

        for node in graph:
            if color[node] == WHITE:
                visit(node)
        return self

    @model_validator(mode="after")
    def _check_requirement_references(self) -> Manifest:
        if self.version == "1":
            return self
        milestone_ids = {m.id for m in self.milestones}
        slice_ids = {s.id for m in self.milestones for s in m.slices}
        slice_to_reqs: dict[str, set[str]] = {
            s.id: set(s.requirements) for m in self.milestones for s in m.slices
        }

        if self.milestones and self.requirements:
            for req in self.requirements:
                if req.milestone is None:
                    raise ValueError(f"{req.id}: milestone is required when milestones: is present")
                if req.slice is None:
                    raise ValueError(f"{req.id}: slice is required when milestones: is present")
                if req.milestone not in milestone_ids:
                    raise ValueError(f"{req.id}: unknown milestone {req.milestone!r}")
                if req.slice not in slice_ids:
                    raise ValueError(f"{req.id}: unknown slice {req.slice!r}")
                if req.id not in slice_to_reqs.get(req.slice, set()):
                    raise ValueError(
                        f"{req.id}: slice/requirement mismatch — requirement "
                        f"declares slice {req.slice!r} but "
                        f"{req.slice!r}.requirements does not list {req.id!r}"
                    )
        return self
