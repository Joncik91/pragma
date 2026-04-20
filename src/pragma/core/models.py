"""Pydantic schema for the v0.1 Logic Manifest (brownfield only).

v0.1 deliberately omits milestones, slices, vision, security_notes,
and single_permutation_reason fields — those land in v0.2-v1.0.
Adding them early here would invite YAGNI fixes.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_REQUIREMENT_ID_RE = re.compile(r"REQ-\d{3,4}")
_PERMUTATION_ID_RE = re.compile(r"[a-z][a-z0-9_]*")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class Project(_StrictModel):
    name: str = Field(min_length=1)
    mode: Literal["brownfield", "greenfield"]
    language: Literal["python"]  # v0.1 supports Python only
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


class Requirement(_StrictModel):
    id: str
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    touches: tuple[Annotated[str, Field(min_length=1)], ...] = Field(min_length=1)
    permutations: tuple[Permutation, ...] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def _validate_requirement_id(cls, v: str) -> str:
        if not _REQUIREMENT_ID_RE.fullmatch(v):
            raise ValueError(
                "requirement id must match ^REQ-\\d{3,4}$ (e.g. REQ-001, REQ-0017)"
            )
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
    version: Literal["1"]
    project: Project
    requirements: tuple[Requirement, ...] = Field(default=())

    @model_validator(mode="after")
    def _check_unique_requirement_ids(self) -> Manifest:
        seen: set[str] = set()
        for req in self.requirements:
            if req.id in seen:
                raise ValueError(f"duplicate requirement id: {req.id!r}")
            seen.add(req.id)
        return self
