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


def test_trace_on_generator_covers_body(memory_exporter: InMemorySpanExporter) -> None:
    """BUG-010: @trace on a generator must span the actual execution.

    Before v1.0.2 the decorator returned the generator object with the
    span already closed, so the span existed but covered only
    fn(*args, **kwargs) (which for generators is "build the generator
    object and return") - no body code had run yet. Consumers that
    never iterated the result would see an empty-body span; the PIL
    aggregator couldn't tell such spans from real ones. The fix
    delegates via yield from inside the span context so the span stays
    open while the iterator is being consumed.
    """

    @trace("REQ-010")
    def nums():
        yield 1
        yield 2
        yield 3

    # Exhaust the generator. The span should be open across all three
    # yields + close cleanly after.
    assert list(nums()) == [1, 2, 3]

    spans = memory_exporter.get_finished_spans()
    assert any(s.name == "REQ-010:nums" for s in spans), (
        "generator body must produce a REQ-010:nums span"
    )


def test_trace_on_async_function(memory_exporter: InMemorySpanExporter) -> None:
    """@trace on an async def coroutine awaits the call inside the span."""
    import asyncio

    @trace("REQ-ASYNC")
    async def add_async(a: int, b: int) -> int:
        return a + b

    result = asyncio.run(add_async(2, 3))
    assert result == 5

    spans = memory_exporter.get_finished_spans()
    assert any(s.name == "REQ-ASYNC:add_async" for s in spans)
