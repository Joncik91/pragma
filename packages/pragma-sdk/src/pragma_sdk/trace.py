from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from opentelemetry import baggage
from opentelemetry import trace as _otel_trace

LOGIC_ID_ATTR = "pragma.logic_id"
PERMUTATION_ATTR = "pragma.permutation"

_tracer = _otel_trace.get_tracer("pragma-sdk")

F = TypeVar("F", bound=Callable[..., Any])


def trace(req_id: str) -> Callable[[F], F]:
    """Mark a function as fulfilling a Pragma requirement."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            perm = baggage.get_baggage(PERMUTATION_ATTR)
            with _tracer.start_as_current_span(
                name=f"{req_id}:{fn.__name__}",
                attributes={
                    LOGIC_ID_ATTR: req_id,
                    PERMUTATION_ATTR: str(perm) if perm is not None else "none",
                },
            ):
                return fn(*args, **kwargs)

        wrapper.__pragma_req__ = req_id  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
