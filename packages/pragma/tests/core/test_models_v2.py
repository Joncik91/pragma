from __future__ import annotations

import pytest
from pydantic import ValidationError

from pragma.core.models import Manifest


def test_v2_manifest_accepts_milestones(v2_manifest_dict: dict) -> None:
    m = Manifest.model_validate(v2_manifest_dict)
    assert m.version == "2"
    assert len(m.milestones) == 1
    assert m.milestones[0].id == "M01"
    assert m.milestones[0].slices[0].id == "M01.S1"


def test_v1_manifest_still_accepted(v1_manifest_dict: dict) -> None:
    m = Manifest.model_validate(v1_manifest_dict)
    assert m.version == "1"
    assert m.milestones == ()


def test_milestone_id_format_enforced(v2_manifest_dict: dict) -> None:
    v2_manifest_dict["milestones"][0]["id"] = "milestone1"
    with pytest.raises(ValidationError, match=r"milestone id"):
        Manifest.model_validate(v2_manifest_dict)


def test_slice_id_format_enforced(v2_manifest_dict: dict) -> None:
    v2_manifest_dict["milestones"][0]["slices"][0]["id"] = "S1"
    with pytest.raises(ValidationError, match=r"slice id"):
        Manifest.model_validate(v2_manifest_dict)


def test_requirement_references_unknown_slice(v2_manifest_dict: dict) -> None:
    v2_manifest_dict["requirements"][0]["slice"] = "M01.S99"
    with pytest.raises(ValidationError, match=r"unknown slice"):
        Manifest.model_validate(v2_manifest_dict)


def test_requirement_references_unknown_milestone(v2_manifest_dict: dict) -> None:
    v2_manifest_dict["requirements"][0]["milestone"] = "M99"
    with pytest.raises(ValidationError, match=r"unknown milestone"):
        Manifest.model_validate(v2_manifest_dict)


def test_slice_requirement_list_must_match_requirement_slice(
    v2_manifest_dict: dict,
) -> None:
    v2_manifest_dict["requirements"][0]["slice"] = "M01.S1"
    v2_manifest_dict["milestones"][0]["slices"][0]["requirements"] = ["REQ-002"]
    with pytest.raises(ValidationError, match=r"slice/requirement mismatch"):
        Manifest.model_validate(v2_manifest_dict)


def test_milestone_depends_on_must_reference_declared(v2_manifest_dict: dict) -> None:
    v2_manifest_dict["milestones"][0]["depends_on"] = ["M99"]
    with pytest.raises(ValidationError, match=r"unknown milestone in depends_on"):
        Manifest.model_validate(v2_manifest_dict)


def test_milestone_dep_cycle_rejected(v2_manifest_dict: dict) -> None:
    v2_manifest_dict["milestones"].append(
        {
            "id": "M02",
            "title": "Two",
            "description": "x",
            "depends_on": ["M01"],
            "slices": [],
        }
    )
    v2_manifest_dict["milestones"][0]["depends_on"] = ["M02"]
    with pytest.raises(ValidationError, match=r"cycle"):
        Manifest.model_validate(v2_manifest_dict)


def test_v2_requirement_must_declare_milestone_and_slice(
    v2_manifest_dict: dict,
) -> None:
    del v2_manifest_dict["requirements"][0]["milestone"]
    with pytest.raises(ValidationError, match=r"milestone.*required"):
        Manifest.model_validate(v2_manifest_dict)


def test_v2_rejects_requirements_without_any_milestones(
    v2_manifest_dict: dict,
) -> None:
    """KI-2: v2 manifest with requirements but milestones=[] must fail validation.

    Before v1.0.2, the requirement-reference validator short-circuited
    on "milestones is empty OR requirements is empty". That let a
    manifest with requirements but no milestones pass silently - pragma
    freeze then hashed it, and the gate couldn't operate on it because
    nothing owned the requirements.
    """
    v2_manifest_dict["milestones"] = []
    with pytest.raises(ValidationError, match=r"requirements but no milestones"):
        Manifest.model_validate(v2_manifest_dict)
