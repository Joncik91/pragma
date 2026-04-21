from __future__ import annotations

from collections.abc import Generator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_exporter = InMemorySpanExporter()


@pytest.fixture(scope="session", autouse=True)
def _setup_tracer_provider() -> None:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_exporter))
    trace.set_tracer_provider(provider)


@pytest.fixture
def memory_exporter() -> Generator[InMemorySpanExporter, None, None]:
    _exporter.clear()
    yield _exporter
    _exporter.clear()
