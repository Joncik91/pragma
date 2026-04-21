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
)
from pragma.core.manifest import load_manifest
from pragma.core.models import Permutation, Requirement
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
) -> None:
    """Append one requirement to pragma.yaml. Idempotent-hostile: errors on duplicate id."""
    cwd = Path.cwd()
    try:
        parsed_permutations = [_parse_permutation_arg(p) for p in permutation]
        _append_requirement(
            cwd / "pragma.yaml",
            rid=id,
            title=title,
            description=description,
            touches=list(touches),
            permutations=parsed_permutations,
        )
    except PragmaError as exc:
        typer.echo(exc.to_json())
        raise typer.Exit(code=1) from None

    typer.echo(
        json.dumps(
            {
                "ok": True,
                "added": {
                    "id": id,
                    "title": title,
                    "touches": list(touches),
                    "permutation_count": len(parsed_permutations),
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        )
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


def _append_requirement(
    yaml_path: Path,
    *,
    rid: str,
    title: str,
    description: str,
    touches: list[str],
    permutations: list[Permutation],
) -> None:
    # Validate the new requirement in isolation first.
    try:
        new_req = Requirement(
            id=rid,
            title=title,
            description=description,
            touches=tuple(touches),
            permutations=tuple(permutations),
        )
    except ValidationError as exc:
        raise ManifestSchemaError(
            message=f"invalid requirement: {exc.errors(include_url=False)[0]['msg']}",
            remediation="Fix the flagged field and retry.",
            context={"id": rid},
        ) from exc

    # Load current manifest (validates the existing file).
    manifest = load_manifest(yaml_path)

    if any(r.id == rid for r in manifest.requirements):
        raise DuplicateRequirementId(
            message=f"Requirement {rid!r} already exists in pragma.yaml.",
            remediation="Pick a different --id, or edit the existing entry manually.",
            context={"id": rid},
        )

    # Append by round-tripping the full YAML: load dict, append to
    # 'requirements' list, re-dump. yaml.safe_dump has no comment-AST
    # awareness, so the template's human-facing comment block AND the
    # original quoting (double vs single quotes) are discarded on the
    # first append. For v0.1 we accept that trade-off. Comment + quote
    # preservation is a v0.2+ concern that will require ruamel.yaml
    # (which does a text-level round-trip).
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    raw.setdefault("requirements", [])
    raw["requirements"].append(new_req.model_dump(mode="json"))

    yaml_text = yaml.safe_dump(
        raw,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )
    yaml_path.write_text(yaml_text, encoding="utf-8")
