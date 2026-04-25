"""`pragma spec add-requirement` — append a requirement to pragma.yaml.

v0.1 ships Pattern A only (see spec §4.5). Patterns B (review) and C
(plan-greenfield) are deferred to v0.7 / v1.0 respectively.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml
from pydantic import ValidationError

from pragma.core.errors import (
    DuplicateRequirementId,
    ManifestSchemaError,
    PragmaError,
    SliceNotFound,
)
from pragma.core.manifest import load_manifest
from pragma.core.models import Manifest, Permutation, Requirement
from pragma.core.plan_greenfield import plan_greenfield

spec_app = typer.Typer(
    name="spec",
    help="Author and edit the Logic Manifest.",
    no_args_is_help=True,
)


@spec_app.command(name="add-requirement")
def add_requirement(
    id: str = typer.Option(..., "--id", help="Requirement ID, e.g. REQ-001"),
    title: str = typer.Option(..., "--title", help="Short one-line title."),
    description: str = typer.Option(..., "--description", help="Multi-sentence description."),
    touches: list[str] = typer.Option(
        ...,
        "--touches",
        help="File under src/ this requirement owns (repeatable).",
    ),
    permutation: list[str] = typer.Option(
        ...,
        "--permutation",
        help=(
            "Permutation in '<id>|<description>|<success|reject>' format "
            "(repeatable, at least one required)."
        ),
    ),
    milestone: str | None = typer.Option(
        None,
        "--milestone",
        help="Milestone id (e.g. M01) the new requirement belongs to. v2 schema.",
    ),
    slice_: str | None = typer.Option(
        None,
        "--slice",
        help="Slice id (e.g. M01.S1) the new requirement belongs to. v2 schema.",
    ),
) -> None:
    """Append one requirement to pragma.yaml. Idempotent-hostile: errors on duplicate id."""
    cwd = Path.cwd()
    try:
        parsed_permutations = [_parse_permutation_arg(p) for p in permutation]
        resolved_milestone, resolved_slice = _append_requirement(
            cwd / "pragma.yaml",
            rid=id,
            title=title,
            description=description,
            touches=list(touches),
            permutations=parsed_permutations,
            milestone=milestone,
            slice_id=slice_,
        )
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(
        _added_json(
            id,
            title,
            list(touches),
            len(parsed_permutations),
            resolved_milestone,
            resolved_slice,
        )
    )


def _added_json(
    rid: str,
    title: str,
    touches: list[str],
    permutation_count: int,
    milestone: str | None,
    slice_id: str | None,
) -> str:
    return json.dumps(
        {
            "ok": True,
            "added": {
                "id": rid,
                "title": title,
                "touches": touches,
                "permutation_count": permutation_count,
                "milestone": milestone,
                "slice": slice_id,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )


@spec_app.command(name="plan-greenfield")
def plan_greenfield_cmd(
    from_: Path = typer.Option(..., "--from", help="Path to a markdown problem statement."),
) -> None:
    """Bootstrap a greenfield manifest from a free-text problem statement.

    Parses `# Heading` sections and replaces the seed REQ-000 under M01.S1
    with one placeholder requirement per heading. Deterministic (no LLM).
    """
    cwd = Path.cwd()
    try:
        new_ids = plan_greenfield(cwd, from_)
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(
        json.dumps(
            {"ok": True, "wrote": "pragma.yaml", "requirements": new_ids},
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _parse_permutation_arg(arg: str) -> Permutation:
    # Split on the first '|' to extract the id, then rsplit on the last '|'
    # to extract the expected value. This allows the description field to
    # contain any number of '|' characters.
    first_split = arg.split("|", maxsplit=1)
    if len(first_split) < 2:
        raise PragmaError(
            code="invalid_permutation_spec",
            message=(f"--permutation must be '<id>|<description>|<success|reject>'; got {arg!r}."),
            remediation=(
                "Example: --permutation 'valid_email|Accepts well-formed emails|success'. "
                "The description field may contain '|'; only the first two '|' are significant."
            ),
        )
    perm_id, remainder = first_split
    last_split = remainder.rsplit("|", maxsplit=1)
    if len(last_split) < 2:
        raise PragmaError(
            code="invalid_permutation_spec",
            message=(f"--permutation must be '<id>|<description>|<success|reject>'; got {arg!r}."),
            remediation=(
                "Example: --permutation 'valid_email|Accepts well-formed emails|success'. "
                "The description field may contain '|'; only the first two '|' are significant."
            ),
        )
    desc, expected = last_split
    try:
        return Permutation(
            id=perm_id.strip(),
            description=desc.strip(),
            expected=expected.strip(),  # type: ignore[arg-type]
        )
    except ValidationError as exc:
        raise ManifestSchemaError(
            message=f"invalid permutation: {exc.errors(include_url=False)[0]['msg']}",
            remediation="Fix the --permutation argument and retry.",
            context={"raw": arg},
        ) from exc


def _build_requirement_or_raise(
    *,
    rid: str,
    title: str,
    description: str,
    touches: list[str],
    permutations: list[Permutation],
    milestone: str | None,
    slice_id: str | None,
) -> Requirement:
    try:
        return Requirement(
            id=rid,
            title=title,
            description=description,
            touches=tuple(touches),
            permutations=tuple(permutations),
            milestone=milestone,
            slice=slice_id,
        )
    except ValidationError as exc:
        raise ManifestSchemaError(
            message=f"invalid requirement: {exc.errors(include_url=False)[0]['msg']}",
            remediation="Fix the flagged field and retry.",
            context={"id": rid},
        ) from exc


def _raise_if_slice_unknown(manifest: Manifest, slice_id: str) -> None:
    """BUG-031 / REQ-028: refuse add-requirement --slice for unknown slice."""
    declared = [s.id for m in manifest.milestones for s in m.slices]
    if slice_id in declared:
        return
    raise SliceNotFound(
        message=f"Slice {slice_id!r} is not declared in the manifest.",
        remediation=(
            "Add the slice under milestones[].slices[] in "
            "pragma.yaml first, or pick one of the declared "
            f"slices: {', '.join(declared) if declared else '(none yet)'}."
        ),
        context={"slice": slice_id, "declared": declared},
    )


def _resolve_default_slice(manifest: Manifest) -> tuple[str | None, str | None]:
    """Return (milestone_id, slice_id) for an `add-requirement` without --slice.

    BUG-045 / REQ-038. Brownfield README quick-start runs
    `add-requirement` without --milestone or --slice, then says
    `pragma slice activate M01.S1`. Without a default-slice rule the
    new REQ lands with `slice: null` and the activate step fails with
    `slice_not_found`. With this rule, when the manifest declares
    exactly one milestone and one slice (the M00.S0 brownfield default),
    the new REQ is assigned there and the README walkthrough works
    end-to-end.

    Returns (None, None) when the manifest has zero or more than one
    candidate, leaving the caller to either pass --slice explicitly or
    leave the REQ unassigned.
    """
    if len(manifest.milestones) != 1:
        return None, None
    only_m = manifest.milestones[0]
    if len(only_m.slices) != 1:
        return None, None
    return only_m.id, only_m.slices[0].id


def _patch_slice_requirements(raw: dict[str, object], slice_id: str, rid: str) -> None:
    """BUG-031 / REQ-028: keep slices[*].requirements in sync with the new REQ."""
    milestones = raw.get("milestones") or []
    if not isinstance(milestones, list):
        return
    for m in milestones:
        if _try_patch_one_milestone(m, slice_id, rid):
            return


def _try_patch_one_milestone(m: object, slice_id: str, rid: str) -> bool:
    if not isinstance(m, dict):
        return False
    for s in m.get("slices") or []:
        if isinstance(s, dict) and s.get("id") == slice_id:
            reqs_list = s.setdefault("requirements", [])
            if isinstance(reqs_list, list) and rid not in reqs_list:
                reqs_list.append(rid)
            return True
    return False


def _append_requirement(
    yaml_path: Path,
    *,
    rid: str,
    title: str,
    description: str,
    touches: list[str],
    permutations: list[Permutation],
    milestone: str | None = None,
    slice_id: str | None = None,
) -> tuple[str | None, str | None]:
    manifest = load_manifest(yaml_path)
    # BUG-045 / REQ-038: default to the only-declared slice when caller
    # leaves both flags unset. Lets the README brownfield quick-start
    # work without an undocumented --slice step.
    if milestone is None and slice_id is None:
        milestone, slice_id = _resolve_default_slice(manifest)
    new_req = _build_requirement_or_raise(
        rid=rid,
        title=title,
        description=description,
        touches=touches,
        permutations=permutations,
        milestone=milestone,
        slice_id=slice_id,
    )
    if slice_id is not None:
        _raise_if_slice_unknown(manifest, slice_id)
    if any(r.id == rid for r in manifest.requirements):
        raise DuplicateRequirementId(
            message=f"Requirement {rid!r} already exists in pragma.yaml.",
            remediation="Pick a different --id, or edit the existing entry manually.",
            context={"id": rid},
        )

    # Append by round-tripping the full YAML. yaml.safe_dump has no
    # comment-AST awareness, so the template's human-facing comment
    # block AND the original quoting (double vs single quotes) are
    # discarded on the first append. v0.2+ can swap to ruamel.yaml.
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    raw.setdefault("requirements", [])
    raw["requirements"].append(new_req.model_dump(mode="json"))
    if slice_id is not None:
        _patch_slice_requirements(raw, slice_id, rid)

    yaml_text = yaml.safe_dump(
        raw,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")
    return milestone, slice_id
