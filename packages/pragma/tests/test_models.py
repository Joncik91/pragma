"""Tests for core/models.py — the Pydantic manifest schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pragma.core.models import (
    Manifest,
    Permutation,
    Project,
    Requirement,
)


class TestProject:
    def test_minimal_brownfield_project(self) -> None:
        p = Project(
            name="example",
            mode="brownfield",
            language="python",
            source_root="src/",
            tests_root="tests/",
        )
        assert p.name == "example"
        assert p.mode == "brownfield"

    def test_rejects_unknown_mode(self) -> None:
        with pytest.raises(ValidationError):
            Project(
                name="x",
                mode="whatever",  # type: ignore[arg-type]
                language="python",
                source_root="src/",
                tests_root="tests/",
            )

    def test_rejects_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            Project(
                name="",
                mode="brownfield",
                language="python",
                source_root="src/",
                tests_root="tests/",
            )


class TestPermutation:
    def test_valid_permutation(self) -> None:
        p = Permutation(
            id="valid_credentials",
            description="Valid email and strong password returns JWT",
            expected="success",
        )
        assert p.id == "valid_credentials"

    @pytest.mark.parametrize(
        "bad_id",
        ["BadCase", "1leading_digit", "has-dash", "has space", ""],
    )
    def test_rejects_invalid_permutation_id(self, bad_id: str) -> None:
        with pytest.raises(ValidationError):
            Permutation(id=bad_id, description="x", expected="success")

    def test_rejects_unknown_expected(self) -> None:
        with pytest.raises(ValidationError):
            Permutation(
                id="ok_id",
                description="x",
                expected="maybe",  # type: ignore[arg-type]
            )

    def test_rejects_blank_description(self) -> None:
        with pytest.raises(ValidationError):
            Permutation(id="ok_id", description="", expected="success")


class TestRequirement:
    def _perm(self, pid: str = "p1") -> Permutation:
        return Permutation(id=pid, description="d", expected="success")

    def test_valid_requirement(self) -> None:
        r = Requirement(
            id="REQ-001",
            title="User registers",
            description="A valid user can register with email and password.",
            touches=["src/auth/register.py"],
            permutations=[self._perm("happy"), self._perm("sad")],
        )
        assert r.id == "REQ-001"

    @pytest.mark.parametrize(
        "bad_id",
        ["REQ-1", "req-001", "REQ001", "REQ-12345", "REQ-XYZ"],
    )
    def test_rejects_bad_requirement_id_format(self, bad_id: str) -> None:
        with pytest.raises(ValidationError):
            Requirement(
                id=bad_id,
                title="t",
                description="d",
                touches=["src/x.py"],
                permutations=[self._perm()],
            )

    def test_requires_at_least_one_permutation(self) -> None:
        with pytest.raises(ValidationError):
            Requirement(
                id="REQ-001",
                title="t",
                description="d",
                touches=["src/x.py"],
                permutations=[],
            )

    def test_rejects_duplicate_permutation_ids(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Requirement(
                id="REQ-001",
                title="t",
                description="d",
                touches=["src/x.py"],
                permutations=[self._perm("dup"), self._perm("dup")],
            )
        assert "duplicate" in str(exc_info.value).lower()

    def test_rejects_blank_description(self) -> None:
        with pytest.raises(ValidationError):
            Requirement(
                id="REQ-001",
                title="t",
                description="",
                touches=["src/x.py"],
                permutations=[self._perm()],
            )

    def test_rejects_empty_touches(self) -> None:
        with pytest.raises(ValidationError):
            Requirement(
                id="REQ-001",
                title="t",
                description="d",
                touches=[],
                permutations=[self._perm()],
            )

    def test_rejects_empty_string_in_touches(self) -> None:
        with pytest.raises(ValidationError):
            Requirement(
                id="REQ-001",
                title="t",
                description="d",
                touches=["", "src/x.py"],
                permutations=[self._perm()],
            )


class TestManifest:
    def _project(self) -> Project:
        return Project(
            name="example",
            mode="brownfield",
            language="python",
            source_root="src/",
            tests_root="tests/",
        )

    def _req(self, rid: str = "REQ-001") -> Requirement:
        return Requirement(
            id=rid,
            title="t",
            description="d",
            touches=["src/x.py"],
            permutations=[Permutation(id="happy", description="d", expected="success")],
        )

    def test_empty_brownfield_manifest(self) -> None:
        m = Manifest(version="1", project=self._project(), requirements=[])
        assert m.version == "1"

    def test_rejects_unknown_version(self) -> None:
        with pytest.raises(ValidationError):
            Manifest(
                version="99",
                project=self._project(),
                requirements=[],
            )

    def test_rejects_duplicate_requirement_ids(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Manifest(
                version="1",
                project=self._project(),
                requirements=[self._req("REQ-001"), self._req("REQ-001")],
            )
        assert "duplicate" in str(exc_info.value).lower()

    def test_accepts_multiple_distinct_requirements(self) -> None:
        m = Manifest(
            version="1",
            project=self._project(),
            requirements=[self._req("REQ-001"), self._req("REQ-002")],
        )
        assert len(m.requirements) == 2
