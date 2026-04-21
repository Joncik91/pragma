from __future__ import annotations

import pytest

from pragma.core.errors import PragmaError
from pragma.narrative.adr import build_adr


def test_adr_renders_markdown() -> None:
    md = build_adr(
        slug="use-fastapi",
        context="Need a web framework for the API.",
        decision="Use FastAPI over Flask.",
        consequences="Async support, auto-generated OpenAPI docs.",
        alternatives="Flask, Django REST Framework.",
        who="alice",
    )
    assert "# ADR: use-fastapi" in md
    assert "FastAPI" in md
    assert "Flask" in md
    assert "alice" in md


def test_adr_raises_on_missing_field() -> None:
    with pytest.raises(PragmaError) as exc_info:
        build_adr(
            slug="test",
            context="",
            decision="Pick A.",
            consequences="None.",
            alternatives="B.",
            who="bob",
        )
    assert "adr_missing_field" in str(exc_info.value)
