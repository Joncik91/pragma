"""Tests for core/manifest.py — YAML loading, canonicalisation, hashing."""

from __future__ import annotations

from pathlib import Path

import pytest

from pragma.core.errors import (
    ManifestNotFound,
    ManifestSchemaError,
    ManifestSyntaxError,
)
from pragma.core.manifest import (
    canonicalise,
    hash_manifest,
    load_manifest,
)
from pragma.core.models import Manifest


def test_load_valid_manifest_from_disk(tmp_project: Path, minimal_valid_yaml: str) -> None:
    (tmp_project / "pragma.yaml").write_text(minimal_valid_yaml)
    m = load_manifest(tmp_project / "pragma.yaml")
    assert isinstance(m, Manifest)
    assert m.project.name == "example"


def test_load_missing_file_raises_typed_error(tmp_project: Path) -> None:
    with pytest.raises(ManifestNotFound) as exc_info:
        load_manifest(tmp_project / "pragma.yaml")
    assert "pragma.yaml" in exc_info.value.message
    assert "pragma init" in exc_info.value.remediation


def test_load_malformed_yaml_raises_syntax_error(tmp_project: Path) -> None:
    (tmp_project / "pragma.yaml").write_text("project: [unclosed")
    with pytest.raises(ManifestSyntaxError) as exc_info:
        load_manifest(tmp_project / "pragma.yaml")
    assert exc_info.value.code == "manifest_syntax_error"


def test_load_schema_violation_raises_schema_error(tmp_project: Path) -> None:
    (tmp_project / "pragma.yaml").write_text(
        'version: "1"\n'
        "project:\n"
        "  name: example\n"
        "  mode: brownfield\n"
        "  language: python\n"
        "  source_root: src/\n"
        "  tests_root: tests/\n"
        "requirements:\n"
        "  - id: not-a-real-req-id\n"
        "    title: t\n"
        "    description: d\n"
        "    touches: [src/x.py]\n"
        "    permutations: [{id: happy, description: d, expected: success}]\n"
    )
    with pytest.raises(ManifestSchemaError) as exc_info:
        load_manifest(tmp_project / "pragma.yaml")
    assert "requirement id" in exc_info.value.message.lower()


def test_canonicalise_produces_deterministic_bytes(
    minimal_valid_yaml: str, tmp_project: Path
) -> None:
    (tmp_project / "pragma.yaml").write_text(minimal_valid_yaml)
    m1 = load_manifest(tmp_project / "pragma.yaml")
    m2 = load_manifest(tmp_project / "pragma.yaml")
    assert canonicalise(m1) == canonicalise(m2)


def test_canonicalise_is_sorted_json(minimal_valid_yaml: str, tmp_project: Path) -> None:
    (tmp_project / "pragma.yaml").write_text(minimal_valid_yaml)
    m = load_manifest(tmp_project / "pragma.yaml")
    canonical = canonicalise(m).decode()
    # sort_keys=True means 'project' alphabetises before 'requirements' and 'version'
    assert canonical.startswith(b'{"project":'.decode())


def test_hash_is_sha256_hex(minimal_valid_yaml: str, tmp_project: Path) -> None:
    (tmp_project / "pragma.yaml").write_text(minimal_valid_yaml)
    m = load_manifest(tmp_project / "pragma.yaml")
    h = hash_manifest(m)
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_hash_is_stable_across_loads(minimal_valid_yaml: str, tmp_project: Path) -> None:
    (tmp_project / "pragma.yaml").write_text(minimal_valid_yaml)
    h1 = hash_manifest(load_manifest(tmp_project / "pragma.yaml"))
    h2 = hash_manifest(load_manifest(tmp_project / "pragma.yaml"))
    assert h1 == h2


def test_hash_changes_when_content_changes(tmp_project: Path, minimal_valid_yaml: str) -> None:
    (tmp_project / "pragma.yaml").write_text(minimal_valid_yaml)
    h1 = hash_manifest(load_manifest(tmp_project / "pragma.yaml"))

    modified = minimal_valid_yaml.replace("name: example", "name: example2")
    (tmp_project / "pragma.yaml").write_text(modified)
    h2 = hash_manifest(load_manifest(tmp_project / "pragma.yaml"))

    assert h1 != h2
