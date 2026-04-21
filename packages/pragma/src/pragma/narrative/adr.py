from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pragma.core.errors import PragmaError

_TPL_DIR = Path(__file__).parent.parent / "templates"

_REQUIRED_FIELDS = ("context", "decision", "consequences", "alternatives", "who")


def build_adr(
    *,
    slug: str,
    context: str,
    decision: str,
    consequences: str,
    alternatives: str,
    who: str,
) -> str:
    fields = {
        "context": context,
        "decision": decision,
        "consequences": consequences,
        "alternatives": alternatives,
        "who": who,
    }
    for name, value in fields.items():
        if not value.strip():
            raise PragmaError(
                code="adr_missing_field",
                message=f"ADR field '{name}' is required but empty.",
                remediation=f"Provide a value for the '{name}' field.",
                context={"field": name},
            )

    env = Environment(
        loader=FileSystemLoader(_TPL_DIR),
        autoescape=select_autoescape([]),
    )
    tpl = env.get_template("adr.tpl")
    return tpl.render(slug=slug, **fields)
