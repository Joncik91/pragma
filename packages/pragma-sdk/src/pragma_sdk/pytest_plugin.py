"""Pytest plugin that wires an InMemorySpanExporter and dumps spans to JSONL."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import pytest
from opentelemetry import trace as _otel_trace
from opentelemetry.context import Context
from opentelemetry.sdk.trace import Span, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pragma_sdk.trace import LOGIC_ID_ATTR

_EXPORTER: InMemorySpanExporter | None = None
_SPAN_NODEIDS: dict[str, str] = {}
_CURRENT_NODEID: str | None = None


class _NodeidSpanProcessor(SimpleSpanProcessor):
    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        if _CURRENT_NODEID is not None:
            _SPAN_NODEIDS[span.context.span_id] = _CURRENT_NODEID
        super().on_start(span, parent_context)


def pytest_configure(config: pytest.Config) -> None:
    global _EXPORTER
    _EXPORTER = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(_NodeidSpanProcessor(_EXPORTER))
    _otel_trace.set_tracer_provider(provider)


@pytest.fixture(autouse=True)
def _pragma_span_context(request: pytest.FixtureRequest) -> Any:
    global _CURRENT_NODEID
    _CURRENT_NODEID = request.node.nodeid
    yield
    _CURRENT_NODEID = None


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if _EXPORTER is None:
        return
    rootdir = session.config.rootpath
    span_dir = rootdir / ".pragma" / "spans"
    span_dir.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    for span in sorted(
        _EXPORTER.get_finished_spans(),
        key=lambda s: (
            s.attributes.get(LOGIC_ID_ATTR, "") if s.attributes else "",
            s.name,
        ),
    ):
        if LOGIC_ID_ATTR not in (span.attributes or {}):
            continue
        nodeid = _SPAN_NODEIDS.get(span.context.span_id, "")
        payload = {
            "test_nodeid": nodeid,
            "span_name": span.name,
            "attrs": dict(span.attributes or {}),
            "status": "ok" if span.status.is_ok else "error",
        }
        lines.append(json.dumps(payload, sort_keys=True, separators=(",", ":")))

    (span_dir / _session_span_filename()).write_text(
        "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
    )


def _session_span_filename() -> str:
    """Per-session filename so concurrent or sequential pytest runs don't collide.

    Before KI-1, every run overwrote test-run.jsonl - a second run
    (pragma-sdk then pragma, or pre-commit then CI) wiped the first
    run's spans and PIL collapsed to 0/N. Each session now writes to
    its own file; aggregators glob *.jsonl in the directory.
    """
    return (
        f"test-run-{int(time.time() * 1000)}-{os.getpid()}-{uuid.uuid4().hex[:8]}.jsonl"
    )
