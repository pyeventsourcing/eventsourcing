from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

_ctx_event_metadata: contextvars.ContextVar[dict[str, str] | None] = (
    contextvars.ContextVar("ctx_event_metadata", default=None)
)


def get_metadata_from_context() -> dict[str, str]:
    """
    Copies metadata dict from context variable. Used to initialise event attribute.
    """
    current = _ctx_event_metadata.get()
    return current.copy() if current is not None else {}


@contextmanager
def put_metadata_in_context(metadata: dict[str, str]) -> Generator[None]:
    """
    Updates metadata dict in context variable. Use this in your request handlers.
    """
    token: contextvars.Token[dict[str, str] | None] | None = None
    try:
        existing = _ctx_event_metadata.get() or {}
        merged_metadata = {**existing, **metadata}
        token = _ctx_event_metadata.set(merged_metadata)
        yield
    finally:
        if token is not None:
            _ctx_event_metadata.reset(token)
        else:
            pass  # pragma: no cover


@contextmanager
def set_metadata_in_context(metadata: dict[str, str]) -> Generator[None]:
    """
    Overrides metadata dict in context variable. Used when mutating perspectives.
    """
    token: contextvars.Token[dict[str, str] | None] | None = None
    try:
        token = _ctx_event_metadata.set(metadata)
        yield
    finally:
        if token is not None:
            _ctx_event_metadata.reset(token)
        else:
            pass  # pragma: no cover


@contextmanager
def null_metadata_in_context() -> Generator[None]:
    """
    Masks metadata with an empty dict. Used when reconstructing domain events.
    """
    token: contextvars.Token[dict[str, str] | None] | None = None
    try:
        token = _ctx_event_metadata.set({})
        yield
    finally:
        if token is not None:
            _ctx_event_metadata.reset(token)
        else:
            pass  # pragma: no cover
