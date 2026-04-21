"""`pragma spec plan-greenfield` — Pattern C bootstrap.

Parses a free-text markdown problem statement, extracts every single-``#``
heading, and replaces the seed ``REQ-000`` under ``M01.S1`` with one
placeholder requirement per heading. Deterministic — no LLM, no randomness,
no wallclock in the YAML payload. Refreezes ``pragma.lock.json`` so the
lockfile stays in sync with the rewritten manifest.

The LLM (Claude Code) is expected to walk each placeholder and fill in
real detail via Pattern A (``pragma spec add-requirement``) immediately
after.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pragma_sdk import trace

from pragma.core.errors import (
    PlanGreenfieldAlreadyPlanned,
    PlanGreenfieldOnBrownfield,
    ProblemStatementMissing,
    StateNotFound,
    StateSchemaError,
)
from pragma.core.lockfile import write_lock
from pragma.core.manifest import hash_manifest, load_manifest
from pragma.core.models import Permutation, Requirement
from pragma.core.state import read_state, write_state

_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _read_problem_headings(cwd: Path, problem_path: Path) -> list[str]:
    """Resolve, read, and parse `# Heading` sections from a problem.md path.

    Raises ProblemStatementMissing for the three failure modes
    (missing, empty, no top-level headings) so the caller only sees
    typed errors.
    """
    if not problem_path.is_absolute():
        problem_path = (cwd / problem_path).resolve()
    if not problem_path.exists():
        raise ProblemStatementMissing(
            message=f"problem statement not found at {problem_path}",
            remediation=(
                "Create a markdown file with `# Heading` sections and pass "
                "--from <path>. Each `#` heading becomes one placeholder "
                "requirement."
            ),
            context={"path": str(problem_path)},
        )
    text = problem_path.read_text(encoding="utf-8")
    if not text.strip():
        raise ProblemStatementMissing(
            message=f"problem statement at {problem_path} is empty",
            remediation=(
                "Write one `# Heading` per area of the product. Each heading "
                "becomes one placeholder requirement under M01.S1."
            ),
            context={"path": str(problem_path)},
        )
    headings = [m.group(1).strip() for m in _HEADING_RE.finditer(text)]
    headings = [h for h in headings if h]
    if not headings:
        raise ProblemStatementMissing(
            message=f"problem statement at {problem_path} contains no `# Heading` sections",
            remediation=(
                "Add at least one `# Heading` line. plan-greenfield only "
                "recognises single-`#` ATX headers; `##` and deeper are ignored."
            ),
            context={"path": str(problem_path)},
        )
    return headings


def _assert_pristine_greenfield(manifest) -> None:
    if manifest.project.mode != "greenfield":
        raise PlanGreenfieldOnBrownfield(
            message=(
                "plan-greenfield only applies to greenfield projects; "
                f"this manifest declares mode={manifest.project.mode!r}."
            ),
            remediation=(
                "Use `pragma spec add-requirement` to author brownfield requirements one at a time."
            ),
            context={"mode": manifest.project.mode},
        )
    if not _is_pristine_seed(manifest):
        raise PlanGreenfieldAlreadyPlanned(
            message=(
                "M01.S1 has already been planned (it does not contain exactly "
                "[REQ-000]); refusing to overwrite."
            ),
            remediation=(
                "plan-greenfield is a one-shot bootstrap. To add more "
                "requirements, use `pragma spec add-requirement`."
            ),
            context={},
        )


def _build_placeholder_requirements(headings: list[str]) -> list[Requirement]:
    return [
        Requirement(
            id=f"REQ-{i:03d}",
            title=f"TODO(pragma): {heading}",
            description=f"TODO(pragma): derive from '{heading}' section in problem.md.",
            touches=("src/todo.py",),
            permutations=(
                Permutation(
                    id="happy_path",
                    description=f"TODO(pragma): specify happy path for {heading}.",
                    expected="success",
                ),
            ),
            milestone="M01",
            slice="M01.S1",
        )
        for i, heading in enumerate(headings, start=1)
    ]


def _rewrite_manifest_with_requirements(yaml_path: Path, new_reqs: list[Requirement]) -> None:
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    raw["requirements"] = [r.model_dump(mode="json") for r in new_reqs]
    raw["milestones"][0]["slices"][0]["requirements"] = [r.id for r in new_reqs]
    yaml_path.write_text(
        yaml.safe_dump(
            raw,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=100,
        ),
        encoding="utf-8",
    )


@trace("REQ-001")
def plan_greenfield(cwd: Path, problem_path: Path) -> list[str]:
    """Bootstrap a greenfield manifest from a free-text problem statement.

    Reads ``problem_path`` (a markdown file), extracts its top-level
    ``# Heading`` sections, and rewrites ``cwd/pragma.yaml`` so M01.S1
    owns one placeholder requirement per heading (REQ-001..REQ-00N),
    replacing the seed REQ-000. Refreezes ``pragma.lock.json`` atomically.

    Returns the ordered list of new requirement IDs.
    """
    headings = _read_problem_headings(cwd, problem_path)
    yaml_path = cwd / "pragma.yaml"
    manifest = load_manifest(yaml_path)
    _assert_pristine_greenfield(manifest)
    new_reqs = _build_placeholder_requirements(headings)
    _rewrite_manifest_with_requirements(yaml_path, new_reqs)
    refreshed = load_manifest(yaml_path)
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_lock(cwd / "pragma.lock.json", refreshed, now_iso=now_iso)
    _rebind_state_to_new_hash(cwd, hash_manifest(refreshed))
    return [r.id for r in new_reqs]


def _rebind_state_to_new_hash(cwd: Path, new_hash: str) -> None:
    """Update .pragma/state.json to track the refrozen manifest.

    BUG-012: plan-greenfield rewrites pragma.yaml and refreezes the lock
    but used to leave state.manifest_hash pinned to the pre-plan hash.
    `pragma init --greenfield` primed state.json with the seed-manifest
    hash, so the very next `pragma verify all` after plan-greenfield
    failed with gate_hash_drift - for every greenfield user, on day
    one. Because plan-greenfield runs before any slice activation, the
    gate is neutral and it is safe to rebind state.manifest_hash to
    the new value without disturbing slice history.
    """
    pragma_dir = cwd / ".pragma"
    try:
        state = read_state(pragma_dir)
    except (StateNotFound, StateSchemaError):
        return
    if state.active_slice is not None:
        # Somebody activated a slice before plan-greenfield - don't
        # silently mutate under an active gate. _assert_pristine_greenfield
        # would have already rejected this, but guard defensively.
        return
    updated = state.model_copy(update={"manifest_hash": new_hash})
    write_state(pragma_dir, updated)


def _is_pristine_seed(manifest: object) -> bool:
    """Return True iff M01.S1 in the manifest contains exactly ``[REQ-000]``.

    Accepts the validated ``Manifest`` type; kept unannotated at the
    parameter-level to avoid circular-import noise.
    """
    milestones = getattr(manifest, "milestones", ())
    if not milestones:
        return False
    first = milestones[0]
    slices = getattr(first, "slices", ())
    if not slices:
        return False
    first_slice = slices[0]
    if getattr(first_slice, "id", None) != "M01.S1":
        return False
    return tuple(first_slice.requirements) == ("REQ-000",)
