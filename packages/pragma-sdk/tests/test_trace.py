from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pragma_sdk import LOGIC_ID_ATTR, trace


def test_trace_emits_span_with_logic_id(memory_exporter: InMemorySpanExporter) -> None:
    @trace("REQ-001")
    def register(email: str) -> str:
        return email

    result = register("alice@example.com")

    assert result == "alice@example.com"
    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "REQ-001:register"
    attrs = spans[0].attributes
    assert attrs is not None
    assert attrs.get(LOGIC_ID_ATTR) == "REQ-001"


def test_trace_preserves_pragma_req_attr() -> None:
    @trace("REQ-042")
    def fn() -> None: ...

    assert fn.__pragma_req__ == "REQ-042"  # type: ignore[attr-defined]
    assert fn.__wrapped__.__name__ == "fn"  # type: ignore[attr-defined]


def test_trace_preserves_return_value(memory_exporter: InMemorySpanExporter) -> None:
    @trace("REQ-007")
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5
