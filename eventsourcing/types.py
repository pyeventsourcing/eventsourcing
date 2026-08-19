from __future__ import annotations

import contextlib
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING, Any, Protocol, Self, runtime_checkable

from eventsourcing.utils import resolve_multi_generic_target

if TYPE_CHECKING:
    from types import TracebackType

    from eventsourcing.domain import AggregateEvent

type Evolver[TState, TEvent] = Callable[
    [TState | None, TEvent],
    TState | None,
]

type Projector[TState, TEvent] = Callable[
    [TState | None, Iterable[TEvent]],
    TState | None,
]

if TYPE_CHECKING:
    from uuid import UUID


@runtime_checkable
class EventCollectorProtocol[TEvent: EventEnvelopeProtocol[Any]](Protocol):
    """Protocol for objects that support collecting pending events."""

    def collect_events(self) -> Sequence[TEvent]:
        """Returns a sequence of events."""
        raise NotImplementedError  # pragma: no cover


@runtime_checkable
class StateMutatorProtocol(Protocol):
    def mutate[TState](self, obj: TState | None) -> TState | None: ...


@runtime_checkable
class EventEnvelopeProtocol[TDecision](Protocol):
    @property
    def decision(self) -> TDecision: ...
    @property
    def uuid(self) -> UUID: ...
    @property
    def metadata(self) -> dict[str, str]: ...


@runtime_checkable
class AggregateEventProtocol[TDecision](EventEnvelopeProtocol[TDecision], Protocol):
    @property
    def originator_id(self) -> str: ...
    @property
    def originator_version(self) -> int: ...


@runtime_checkable
class TaggedEventProtocol[TDecision](EventEnvelopeProtocol[TDecision], Protocol):
    @property
    def tags(self) -> list[str]: ...


@runtime_checkable
class ImmutableAggregateProtocol(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def version(self) -> int: ...


@runtime_checkable
class MutableAggregateProtocol[
    TEnvelope: AggregateEventProtocol[Any],
](
    EventCollectorProtocol[TEnvelope],
    Protocol,
):
    id: str
    version: int


@runtime_checkable
class SelectorProtocol[TDecision](Protocol):
    types: Sequence[type[TDecision]] = ()
    tags: Sequence[str] = ()


@runtime_checkable
class PerspectiveProtocol[
    TEnvelope: TaggedEventProtocol[Any],
    TDecision,
](
    EventCollectorProtocol[TEnvelope],
    Protocol,
):
    last_known_position: int | None

    def consistency_boundary(
        self,
    ) -> SelectorProtocol[TDecision] | Sequence[SelectorProtocol[TDecision]]: ...


class WorksWithDecisions[TDecision]:
    works_with_decision_type: type[Any] | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """
        Initialises subclass by identifying which decision class it works with.
        """
        super().__init_subclass__(**kwargs)

        # Find the type arg for TDecision.
        if "works_with_decision_type" not in cls.__dict__:
            type_args = resolve_multi_generic_target(cls, WorksWithDecisions)
            assert len(type_args) == 1, type_args
            resolved_decision_type = type_args[0]

            # if not _is_valid_id_type(resolved_originator_id_type):
            #     msg = f"Aggregate ID type arg cannot be {resolved_originator_id_type}"
            #     raise TypeError(msg)

            cls.works_with_decision_type = resolved_decision_type

    @classmethod
    def check_decision_type(cls, decision_cls: Any) -> None:
        if cls.works_with_decision_type is None:
            msg = f"{cls} has no decision type argument"
            raise TypeError(msg)
        requirement = getattr(decision_cls, "works_with_decision_type", decision_cls)
        if requirement is None:
            msg = f"{decision_cls} has no decision type argument"
            raise TypeError(msg)

        if not issubclass(requirement, cls.works_with_decision_type):
            msg = f"{requirement} mismatches {cls.works_with_decision_type}"
            raise TypeError(msg)


@runtime_checkable
class SnapshotProtocol[TDecision](Protocol):
    def take(
        self, obj: MutableAggregateProtocol[Any] | ImmutableAggregateProtocol
    ) -> AggregateEvent[TDecision]: ...


class ClosingContextManager(ABC):
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> bool | None:
        self.close()
        return None

    @abstractmethod
    def close(self) -> None:
        pass

    def __del__(self) -> None:
        """Calls stop()."""
        with contextlib.suppress(AttributeError):
            self.close()


class StoppingContextManager(ABC):
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> bool | None:
        self.stop()
        return None

    @abstractmethod
    def stop(self) -> None:
        pass

    def __del__(self) -> None:
        """Calls stop()."""
        with contextlib.suppress(AttributeError):
            self.stop()
