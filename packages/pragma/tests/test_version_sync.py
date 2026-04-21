"""v1.0.4: guard against drifting version pins across release prep.

The Pragma version is declared in three places:
- packages/pragma/pyproject.toml's ``[project] version``
- packages/pragma/src/pragma/__init__.py's ``__version__``
- packages/pragma/tests/test_cli_doctor.py's assertion on the doctor
  payload's ``pragma_version`` field

If any of those drifts during a release bump, the user sees a
mismatched `pragma doctor` output that claims one version while the
installed package reports another. This test fails the commit until
all three agree.

Added after v1.0.3.1, which shipped because the __init__.py pin was
forgotten during the v1.0.0 cut; v1.0.2's smoke run finally caught
it. Lock it in so the next version bump can't drift.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pragma


def _pkg_root() -> Path:
    # packages/pragma/tests/test_version_sync.py -> packages/pragma/
    return Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    pyproject = _pkg_root() / "pyproject.toml"
    with pyproject.open("rb") as f:
        return str(tomllib.load(f)["project"]["version"])


def _doctor_test_version() -> str:
    """Extract the version literal asserted in test_cli_doctor.

    Parsed with regex so the assertion string is the single source
    of truth - no import side effects from the test module itself.
    """
    test_file = _pkg_root() / "tests" / "test_cli_doctor.py"
    text = test_file.read_text(encoding="utf-8")
    m = re.search(r'pragma_version"\]\s*==\s*"([^"]+)"', text)
    assert m is not None, "test_cli_doctor assertion not found"
    return m.group(1)


def test_version_sync_across_pins() -> None:
    """__init__.__version__, pyproject version, and doctor test all match."""
    pkg_version = pragma.__version__
    pyproject_version = _pyproject_version()
    doctor_version = _doctor_test_version()
    assert pkg_version == pyproject_version, (
        f"pragma.__version__={pkg_version!r} but pyproject.toml declares "
        f"{pyproject_version!r} — version bump drift during release prep."
    )
    assert pkg_version == doctor_version, (
        f"pragma.__version__={pkg_version!r} but test_cli_doctor asserts "
        f"{doctor_version!r} — release-prep checklist missed the test file."
    )
