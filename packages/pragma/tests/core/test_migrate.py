from __future__ import annotations

from pragma.core.migrate import migrate_v1_to_v2


def test_migrate_bumps_version(v1_manifest_dict: dict) -> None:
    result = migrate_v1_to_v2(v1_manifest_dict)
    assert result["version"] == "2"


def test_migrate_injects_m00_milestone(v1_manifest_dict: dict) -> None:
    result = migrate_v1_to_v2(v1_manifest_dict)
    assert len(result["milestones"]) == 1
    m00 = result["milestones"][0]
    assert m00["id"] == "M00"
    assert m00["depends_on"] == []
    assert len(m00["slices"]) == 1
    assert m00["slices"][0]["id"] == "M00.S0"
    assert m00["slices"][0]["requirements"] == ["REQ-001"]


def test_migrate_annotates_requirements(v1_manifest_dict: dict) -> None:
    result = migrate_v1_to_v2(v1_manifest_dict)
    req = result["requirements"][0]
    assert req["milestone"] == "M00"
    assert req["slice"] == "M00.S0"


def test_migrate_idempotent_on_v2(v2_manifest_dict: dict) -> None:
    result = migrate_v1_to_v2(v2_manifest_dict)
    assert result == v2_manifest_dict


def test_migrate_preserves_unrelated_fields(v1_manifest_dict: dict) -> None:
    result = migrate_v1_to_v2(v1_manifest_dict)
    assert result["project"] == v1_manifest_dict["project"]
    assert result["requirements"][0]["touches"] == v1_manifest_dict["requirements"][0]["touches"]
    assert (
        result["requirements"][0]["permutations"]
        == v1_manifest_dict["requirements"][0]["permutations"]
    )


def test_migrate_empty_requirements(v1_manifest_dict: dict) -> None:
    v1_manifest_dict["requirements"] = []
    result = migrate_v1_to_v2(v1_manifest_dict)
    assert result["milestones"][0]["slices"][0]["requirements"] == []
    assert result["requirements"] == []


def test_migrate_does_not_mutate_input(v1_manifest_dict: dict) -> None:
    snapshot = {**v1_manifest_dict, "requirements": list(v1_manifest_dict["requirements"])}
    migrate_v1_to_v2(v1_manifest_dict)
    assert v1_manifest_dict == snapshot
