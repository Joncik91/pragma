from __future__ import annotations

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pragma_sdk import PERMUTATION_ATTR, set_permutation, trace


def test_permutation_flows_into_span(memory_exporter: InMemorySpanExporter) -> None:
    @trace("REQ-001")
    def do() -> None: ...

    with set_permutation("weak_password"):
        do()

    spans = memory_exporter.get_finished_spans()
    assert spans[0].attributes is not None
    assert spans[0].attributes[PERMUTATION_ATTR] == "weak_password"


def test_permutation_detaches_cleanly(memory_exporter: InMemorySpanExporter) -> None:
    @trace("REQ-001")
    def do() -> None: ...

    with set_permutation("first"):
        do()
    do()  # outside ctx manager

    spans = memory_exporter.get_finished_spans()
    assert spans[0].attributes is not None
    assert spans[0].attributes[PERMUTATION_ATTR] == "first"
    assert spans[1].attributes is not None
    assert spans[1].attributes[PERMUTATION_ATTR] == "none"
