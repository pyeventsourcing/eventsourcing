from typing import Any

from eventsourcing.domain.model.aggregate import BaseAggregateRoot, T_ag


class Command(BaseAggregateRoot):
    def __init__(self, **kwargs: Any):
        super(Command, self).__init__(**kwargs)
        self._is_done = False

    class Event(BaseAggregateRoot.Event[T_ag]):
        pass

    class Created(Event[T_ag], BaseAggregateRoot.Created[T_ag]):
        pass

    class AttributeChanged(Event[T_ag], BaseAggregateRoot.AttributeChanged[T_ag]):
        pass

    class Discarded(Event[T_ag], BaseAggregateRoot.Discarded[T_ag]):
        pass

    @property
    def is_done(self) -> bool:
        return self._is_done

    def done(self) -> None:
        self.__trigger_event__(self.Done)

    class Done(Event):
        def mutate(self, obj: "Command") -> None:
            obj._is_done = True
