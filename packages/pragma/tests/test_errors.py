"""Tests for core/errors.py — the structured-error payload shape."""

from __future__ import annotations

import json

import pytest

from pragma.core.errors import (
    ManifestHashMismatch,
    ManifestSchemaError,
    ManifestSyntaxError,
    PragmaError,
)


def test_pragma_error_serialises_to_expected_json_shape() -> None:
    err = PragmaError(
        code="example_error",
        message="Something broke.",
        remediation="Do the thing.",
        context={"file": "pragma.yaml"},
    )
    payload = err.to_json()
    parsed = json.loads(payload)
    assert parsed == {
        "error": "example_error",
        "message": "Something broke.",
        "remediation": "Do the thing.",
        "context": {"file": "pragma.yaml"},
    }


def test_pragma_error_defaults_context_to_empty_dict() -> None:
    err = PragmaError(code="x", message="m", remediation="r")
    parsed = json.loads(err.to_json())
    assert parsed["context"] == {}


def test_manifest_syntax_error_has_stable_code() -> None:
    err = ManifestSyntaxError(message="bad yaml", remediation="fix it")
    assert err.code == "manifest_syntax_error"


def test_manifest_schema_error_has_stable_code() -> None:
    err = ManifestSchemaError(message="bad schema", remediation="fix it")
    assert err.code == "manifest_schema_error"


def test_manifest_hash_mismatch_has_stable_code() -> None:
    err = ManifestHashMismatch(message="mismatch", remediation="run freeze")
    assert err.code == "manifest_hash_mismatch"


def test_pragma_error_is_raisable_and_catchable() -> None:
    with pytest.raises(PragmaError) as exc_info:
        raise ManifestSyntaxError(message="m", remediation="r")
    assert exc_info.value.code == "manifest_syntax_error"
