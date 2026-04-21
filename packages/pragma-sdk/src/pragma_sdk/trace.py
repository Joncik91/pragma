from __future__ import annotations

import inspect
from functools import wraps
from typing import Any, Callable, TypeVar

from opentelemetry import baggage
from opentelemetry import trace as _otel_trace

LOGIC_ID_ATTR = "pragma.logic_id"
PERMUTATION_ATTR = "pragma.permutation"

_tracer = _otel_trace.get_tracer("pragma-sdk")

F = TypeVar("F", bound=Callable[..., Any])


def _span_attrs(req_id: str) -> dict[str, str]:
    perm = baggage.get_baggage(PERMUTATION_ATTR)
    return {
        LOGIC_ID_ATTR: req_id,
        PERMUTATION_ATTR: str(perm) if perm is not None else "none",
    }


def trace(req_id: str) -> Callable[[F], F]:
    """Mark a function as fulfilling a Pragma requirement.

    Handles three function shapes so the span covers actual execution,
    not just object construction (BUG-010):

    - async functions: await the coroutine inside the span.
    - generator functions: yield from the iterator inside the span so
      the span stays open across pulls; otherwise the span would close
      at the moment the generator object is created, before any body
      code ran, and the PIL aggregator would never see it.
    - plain sync functions: straight call.

    Async generators (``async def ... yield``) are detected and handled
    with the async-generator span lifetime (span open across anexts).
    """

    def decorator(fn: F) -> F:
        name = f"{req_id}:{fn.__name__}"

        if inspect.isasyncgenfunction(fn):

            @wraps(fn)
            async def async_gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                with _tracer.start_as_current_span(
                    name=name, attributes=_span_attrs(req_id)
                ):
                    async for item in fn(*args, **kwargs):
                        yield item

            async_gen_wrapper.__pragma_req__ = req_id  # type: ignore[attr-defined]
            return async_gen_wrapper  # type: ignore[return-value]

        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with _tracer.start_as_current_span(
                    name=name, attributes=_span_attrs(req_id)
                ):
                    return await fn(*args, **kwargs)

            async_wrapper.__pragma_req__ = req_id  # type: ignore[attr-defined]
            return async_wrapper  # type: ignore[return-value]

        if inspect.isgeneratorfunction(fn):

            @wraps(fn)
            def gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                with _tracer.start_as_current_span(
                    name=name, attributes=_span_attrs(req_id)
                ):
                    yield from fn(*args, **kwargs)

            gen_wrapper.__pragma_req__ = req_id  # type: ignore[attr-defined]
            return gen_wrapper  # type: ignore[return-value]

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with _tracer.start_as_current_span(
                name=name, attributes=_span_attrs(req_id)
            ):
                return fn(*args, **kwargs)

        wrapper.__pragma_req__ = req_id  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
