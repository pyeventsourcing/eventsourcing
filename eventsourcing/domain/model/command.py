from typing import Any

from eventsourcing.domain.model.aggregate import BaseAggregateRoot
from eventsourcing.types import T_en


class Command(BaseAggregateRoot):
    def __init__(self, **kwargs: Any):
        super(Command, self).__init__(**kwargs)
        self._is_done = False

    class Event(BaseAggregateRoot.Event[T_en]):
        pass

    class Created(Event[T_en], BaseAggregateRoot.Created[T_en]):
        pass

    class AttributeChanged(Event[T_en], BaseAggregateRoot.AttributeChanged[T_en]):
        pass

    class Discarded(Event[T_en], BaseAggregateRoot.Discarded[T_en]):
        pass

    @property
    def is_done(self) -> bool:
        return self._is_done

    def done(self) -> None:
        self.__trigger_event__(self.Done)

    class Done(Event):
        def mutate(self, obj: "Command") -> None:
            obj._is_done = True
