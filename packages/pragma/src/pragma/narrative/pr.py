from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pragma.report.models import Report

_TPL_DIR = Path(__file__).parent.parent / "templates"


def build_pr_description(*, report: Report) -> str:
    env = Environment(
        loader=FileSystemLoader(_TPL_DIR),
        autoescape=select_autoescape([]),
    )
    tpl = env.get_template("pr-description.tpl")
    return tpl.render(report=report)
