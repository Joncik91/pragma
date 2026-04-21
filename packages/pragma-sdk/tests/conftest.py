from __future__ import annotations

from collections.abc import Generator

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import pragma_sdk.pytest_plugin as _plugin


@pytest.fixture
def memory_exporter() -> Generator[InMemorySpanExporter, None, None]:
    assert _plugin._EXPORTER is not None
    _plugin._EXPORTER.clear()
    yield _plugin._EXPORTER
    _plugin._EXPORTER.clear()
