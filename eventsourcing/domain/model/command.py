from typing import Any

from eventsourcing.domain.model.aggregate import BaseAggregateRoot, TAggregate


class Command(BaseAggregateRoot):
    def __init__(self, **kwargs: Any):
        super(Command, self).__init__(**kwargs)
        self._is_done = False

    class Event(BaseAggregateRoot.Event[TAggregate]):
        pass

    class Created(Event[TAggregate], BaseAggregateRoot.Created[TAggregate]):
        pass

    class AttributeChanged(
        Event[TAggregate], BaseAggregateRoot.AttributeChanged[TAggregate]
    ):
        pass

    class Discarded(Event[TAggregate], BaseAggregateRoot.Discarded[TAggregate]):
        pass

    @property
    def is_done(self) -> bool:
        return self._is_done

    def done(self) -> None:
        self.__trigger_event__(self.Done)

    class Done(Event):
        def mutate(self, obj: "Command") -> None:
            obj._is_done = True
