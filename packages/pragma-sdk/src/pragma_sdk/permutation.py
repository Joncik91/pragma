from __future__ import annotations

from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any, Type

from opentelemetry import baggage
from opentelemetry.context import attach, detach

from pragma_sdk.trace import PERMUTATION_ATTR


class set_permutation(AbstractContextManager["set_permutation"]):
    """Tag the running permutation for any spans opened inside."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._token: Any = None

    def __enter__(self) -> "set_permutation":
        self._token = attach(baggage.set_baggage(PERMUTATION_ATTR, self._name))
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._token is not None:
            detach(self._token)
